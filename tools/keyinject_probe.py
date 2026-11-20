"""诊断：程序模拟的 V 键到底有没有发出去、有没有被系统拦掉。

`_send_key` 忽略了 SendInput 的返回值，所以「按了但被拒」和「按成功了」
在程序里看起来一模一样。这个脚本把真正的结果打出来：

  1) 我们自己的进程完整性级别（Medium / High …）
  2) 游戏进程的完整性级别 —— 比我们高就说明会被 UIPI 拦
  3) SendInput 的实际返回值 + GetLastError
  4) 注入之后 GetAsyncKeyState 能不能读到（验证注入本身有效）

跑：D:\\python\\python.exe -X utf8 tools\\keyinject_probe.py
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# 64 位下不声明 argtypes，句柄/指针会被当成 32 位 int 传，直接 Overflow
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel32.Process32NextW.restype = wintypes.BOOL

advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.HANDLE)]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                        ctypes.c_void_p, wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD)]
advapi32.GetTokenInformation.restype = wintypes.BOOL
advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)

user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

ERROR_ACCESS_DENIED = 5

# ---------------------------------------------------------------- 完整性级别
TOKEN_QUERY = 0x0008
TokenIntegrityLevel = 25
SECURITY_MANDATORY_UNTRUSTED_RID = 0x0000
SECURITY_MANDATORY_LOW_RID = 0x1000
SECURITY_MANDATORY_MEDIUM_RID = 0x2000
SECURITY_MANDATORY_HIGH_RID = 0x3000
SECURITY_MANDATORY_SYSTEM_RID = 0x4000

_LEVELS = [
    (SECURITY_MANDATORY_UNTRUSTED_RID, "Untrusted"),
    (SECURITY_MANDATORY_LOW_RID, "Low"),
    (SECURITY_MANDATORY_MEDIUM_RID, "Medium"),
    (SECURITY_MANDATORY_HIGH_RID, "High"),
    (SECURITY_MANDATORY_SYSTEM_RID, "System"),
]


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", SID_AND_ATTRIBUTES)]


def _sid_rid(sid_ptr) -> int:
    n = advapi32.GetSidSubAuthorityCount(sid_ptr)
    cnt = n[0]
    sub = advapi32.GetSidSubAuthority(sid_ptr, cnt - 1)
    return int(sub[0])


def level_name(rid: int) -> str:
    name = "Unknown"
    for bound, label in _LEVELS:
        if rid >= bound:
            name = label
    return f"{name}(0x{rid:04X})"


def integrity_of_process(h_process) -> tuple[str, int | None]:
    tok = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(h_process, TOKEN_QUERY, ctypes.byref(tok)):
        return f"打不开令牌(err={ctypes.get_last_error()})", None
    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(tok, TokenIntegrityLevel, None, 0,
                                     ctypes.byref(size))
        buf = ctypes.create_string_buffer(max(size.value, 64))
        if not advapi32.GetTokenInformation(tok, TokenIntegrityLevel, buf,
                                            size, ctypes.byref(size)):
            return f"查询失败(err={ctypes.get_last_error()})", None
        tml = ctypes.cast(buf, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
        sid = tml.Label.Sid
        if not sid:
            return "SID 为空", None
        rid = _sid_rid(sid)
        return level_name(rid), rid
    finally:
        kernel32.CloseHandle(tok)


def own_integrity():
    return integrity_of_process(kernel32.GetCurrentProcess())


# ---------------------------------------------------------------- 找游戏进程
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400

GAME_NAMES = ("valorant.exe", "valorant-win64-shipping.exe",
              "riotclientux.exe", "riotclientcrashhandler.exe")


def find_games() -> list[tuple[int, str, str]]:
    """返回 [(pid, 名字, 完整性级别)]，用 CreateToolhelp32Snapshot 枚举。"""
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    out = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            name = pe.szExeFile
            if name.lower() in GAME_NAMES:
                h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                                         pe.th32ProcessID)
                lvl = "无法查询（可能被 Vanguard 保护）"
                if h:
                    try:
                        lvl, _ = integrity_of_process(h)
                    finally:
                        kernel32.CloseHandle(h)
                out.append((int(pe.th32ProcessID), name, lvl))
            ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        kernel32.CloseHandle(snap)
    return out


# ---------------------------------------------------------------- 注入测试
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


def send_v(up: bool, use_scancode: bool) -> tuple[int, int]:
    """返回 (SendInput 返回值, GetLastError)。"""
    vk = 0x56                       # V
    scan = user32.MapVirtualKeyW(vk, 0)
    size = ctypes.sizeof(winapi._INPUT)
    inp = winapi._INPUT()
    inp.type = winapi.INPUT_KEYBOARD
    if use_scancode:
        inp.union.ki = winapi._KEYBDINPUT(
            wVk=0, wScan=scan,
            dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0),
            time=0, dwExtraInfo=None)
    else:
        inp.union.ki = winapi._KEYBDINPUT(
            wVk=vk, wScan=0,
            dwFlags=(KEYEVENTF_KEYUP if up else 0),
            time=0, dwExtraInfo=None)
    ctypes.set_last_error(0)
    r = user32.SendInput(1, ctypes.byref(inp), size)
    return int(r), ctypes.get_last_error()


def main() -> int:
    ok = True
    print("=" * 62)
    print("1) 本进程完整性级别")
    lvl, rid = own_integrity()
    print(f"   {lvl}    pid={kernel32.GetCurrentProcess()}")
    try:
        elevated = bool(user32.IsUserAnAdmin())
    except Exception:
        elevated = False
    print(f"   管理员权限: {'是' if elevated else '否'}")
    print()

    print("2) 游戏进程")
    games = find_games()
    if not games:
        print("   没找到 VALORANT 进程（游戏没开，或名字不在这份列表里）")
    for pid, name, glvl in games:
        print(f"   {name}  pid={pid}  完整性={glvl}")
        if rid is not None and "High" in glvl and rid < SECURITY_MANDATORY_HIGH_RID:
            print("   ⚠ 游戏比我们高一级 → SendInput 会被 UIPI 直接拒掉")
    print()

    print("3) SendInput 是否被拒（当前前台窗口是什么都不影响这一步）")
    for label, sc in (("扫描码模式（程序现在用的）", True),
                      ("虚拟键模式", False)):
        r, err = send_v(False, sc)
        time.sleep(0.05)
        r2, err2 = send_v(True, sc)
        if r == 1 and r2 == 1:
            print(f"   {label}: 发送成功 (down={r} up={r2})")
        else:
            print(f"   {label}: 被拒 down={r}(err={err}) up={r2}(err={err2})")
            if err == ERROR_ACCESS_DENIED or err2 == ERROR_ACCESS_DENIED:
                print("      → 错误 5 = 拒绝访问，典型的 UIPI/权限不足")
            ok = False
    print()

    print("4) 注入后我们能不能读到（验证注入本身是不是有效）")
    ok_scan = False
    for attempt, sc in enumerate((True, False)):
        name = "扫描码" if sc else "虚拟键"
        # 先按住，再查状态
        r, err = send_v(False, sc)
        time.sleep(0.02)
        state = user32.GetAsyncKeyState(0x56)
        send_v(True, sc)
        pressed = bool(state & 0x8000)
        print(f"   {name}注入 → GetAsyncKeyState(0x56) & 0x8000 = {pressed}")
        if pressed:
            ok_scan = True
    if not ok_scan:
        print("   → 两种模式都读不到，注入链路整体不通")
        ok = False
    print()

    print("=" * 62)
    if ok:
        print("结论：注入链路是通的。游戏里没反应的话，是游戏不认注入的键 ——")
        print("      改用「开放式麦克风」(tts.game_ptt_enabled=false) 即可。")
    else:
        print("结论：注入链路有硬问题（见上面 ⚠ / 被拒 / 读不到）。")
        print("      先试：右键 run.bat → 以管理员身份运行，再跑一次本脚本。")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())