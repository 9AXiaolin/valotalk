"""验证「以管理员运行后，模拟的 V 能不能真的进去」。

普通进程（Medium）向游戏（High）SendInput 会被 UIPI **静默丢弃**，
所以这个脚本会先把自己提权，再注入 V 并读回键状态：

  GetAsyncKeyState(V) & 0x8000 == True  → 注入真的进去了
  == False                              → 还是被拦（或被 Vanguard 拦）

结果同时写到 cache/keyinject_elevated.txt，方便提权后主进程看不到输出时读取。

跑：D:\\python\\python.exe -X utf8 tools\\keyinject_elevated_probe.py
（会弹一次 UAC，点「是」）
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk import winapi  # noqa: E402

OUT = ROOT / "cache" / "keyinject_elevated.txt"
VK_V = 0x56

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]
kernel32.GetCurrentProcessId.restype = wintypes.DWORD


def fg_pid() -> int:
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(p))
    return int(p.value)


def elevate_self() -> bool:
    py = sys.executable
    script = str(Path(__file__).resolve())
    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", py, f'-X utf8 "{script}"', str(ROOT), 1)
    return int(r) > 32


def emit(lines: list[str], code: int) -> int:
    text = "\n".join(lines)
    print(text)
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"（写结果文件失败：{exc}）")
    return code


def main() -> int:
    lines: list[str] = []
    elevated = winapi.is_elevated()
    own = winapi.own_integrity_rid()
    game = winapi.game_integrity_rid()

    lines.append("=" * 58)
    lines.append(f"管理员权限     : {'是' if elevated else '否'}")
    lines.append(f"本进程完整性   : {'0x%04X' % own if own else '未知'}")
    lines.append(f"游戏完整性     : {'0x%04X' % game if game else '（没找到游戏进程）'}")
    lines.append(f"注入会被拦吗   : {'是' if winapi.keyinject_blocked() else '否'}")
    lines.append("-" * 58)

    if not elevated:
        lines.append("现在提权，UAC 弹窗里点「是」…")
        emit(lines, 2)
        if elevate_self():
            return 2
        lines.append("提权被拒绝 —— 没法继续。")
        return emit(lines, 1)

    # 已提权：注入并读回
    fg = fg_pid()
    lines.append(f"注入时前台 pid : {fg}（{kernel32.GetCurrentProcessId()} = 本进程）")

    winapi.key_down("v")
    seen = False
    for _ in range(8):
        time.sleep(0.02)
        if user32.GetAsyncKeyState(VK_V) & 0x8000:
            seen = True
            break
    winapi.key_up("v")
    time.sleep(0.05)

    lines.append(f"注入后读到 V   : {'是' if seen else '否'}")
    lines.append("-" * 58)
    if seen:
        lines.append("✓ 提权后注入有效。以管理员运行 ValoTalk 即可让队友听到英文。")
        if fg and fg != kernel32.GetCurrentProcessId():
            lines.append("  注意：当时前台不是本进程，说明注入穿过了别的窗口，")
            lines.append("  这正是「送进游戏」需要的效果。")
        return emit(lines, 0)

    lines.append("✗ 提权后仍然读不到 V。可能原因：")
    lines.append("  · Vanguard 拦了模拟输入（那就只能用开放式麦克风）")
    lines.append("  · 游戏没在前台（注入落到了别处，GetAsyncKeyState 读不到）")
    lines.append("  下一步：游戏设「开放式麦克风」，并把 tts.game_ptt_enabled 设 false。")
    return emit(lines, 1)


if __name__ == "__main__":
    raise SystemExit(main())