"""后台诊断：游戏全屏时，低级键盘/鼠标钩子能不能收到按键。

用法：
  1. 运行这个脚本（它会一直记录）
  2. 切到游戏里，按几下 F2、鼠标侧键、V
  3. 切回来按 Ctrl+C 停止，看记录
  4. 结果会同时写进 cache/hook_capture.log

关键判断：
  - 如果游戏里按 F2/侧键，这里记录到了  -> 钩子能用，改钩子就行
  - 如果一条都没记录到                    -> 输入被游戏/反作弊独占了，得换方案
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

u = winapi.user32
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

LOG = Path(__file__).resolve().parent.parent / "cache" / "hook_capture.log"
LOG.parent.mkdir(exist_ok=True)

records: list[str] = []
lock = threading.Lock()
kb_hook = [0]
ms_hook = [0]

VK_NAME = {0x71: "F2", 0x70: "F1", 0x72: "F3", 0x73: "F4", 0x74: "F5",
           0x56: "V", 0x05: "MOUSE4", 0x06: "MOUSE5", 0x21: "PgUp",
           0x22: "PgDn", 0x2D: "Insert", 0x14: "CapsLock"}


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with lock:
        records.append(line)
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------- 键盘钩子 ----------
KBD_PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                              wintypes.WPARAM, wintypes.LPARAM)


def kb_callback(n_code, w_param, l_param):
    if n_code >= 0 and w_param in (WM_KEYDOWN, WM_KEYUP,
                                   WM_SYSKEYDOWN, WM_SYSKEYUP):
        try:
            vk = ctypes.cast(l_param, ctypes.POINTER(wintypes.DWORD)).contents.value
            name = VK_NAME.get(vk, f"0x{vk:02X}")
            if vk in VK_NAME:                       # 只看关心的键
                action = "DOWN" if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN) else "UP"
                log(f"KEY  {name:9s} {action}")
        except Exception:
            pass
    return u.CallNextHookEx(kb_hook[0], n_code, w_param, l_param)


# ---------- 鼠标钩子 ----------
MS_PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                             wintypes.WPARAM, wintypes.LPARAM)


def ms_callback(n_code, w_param, l_param):
    if n_code >= 0 and w_param in (winapi.WM_XBUTTONDOWN, winapi.WM_XBUTTONUP):
        try:
            info = ctypes.cast(l_param, ctypes.POINTER(
                winapi._MSLLHOOKSTRUCT)).contents
            which = (info.mouseData >> 16) & 0xFFFF
            name = "MOUSE4" if which == 1 else "MOUSE5"
            action = "DOWN" if w_param == winapi.WM_XBUTTONDOWN else "UP"
            log(f"MOUSE {name} {action}")
        except Exception:
            pass
    return u.CallNextHookEx(ms_hook[0], n_code, w_param, l_param)


kb_proc = KBD_PROC(kb_callback)
ms_proc = MS_PROC(ms_callback)


def kb_loop():
    kb_hook[0] = u.SetWindowsHookExW(WH_KEYBOARD_LL, kb_proc, None, 0)
    log(f"键盘钩子 = {kb_hook[0]}  (0 表示失败)")
    if not kb_hook[0]:
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))


def ms_loop():
    ms_hook[0] = u.SetWindowsHookExW(WH_MOUSE_LL, ms_proc, None, 0)
    log(f"鼠标钩子 = {ms_hook[0]}  (0 表示失败)")
    if not ms_hook[0]:
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    LOG.write_text("", encoding="utf-8")
    log("=== 开始记录（Ctrl+C 停止）===")
    threading.Thread(target=kb_loop, daemon=True).start()
    threading.Thread(target=ms_loop, daemon=True).start()
    time.sleep(0.5)
    log("现在切到游戏，按几下 F2 / 鼠标侧键 / V，然后回来 Ctrl+C")
    log("提示：先在桌面按一次 F2 做对照，确认钩子本身是好的")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if kb_hook[0]:
            u.UnhookWindowsHookEx(kb_hook[0])
        if ms_hook[0]:
            u.UnhookWindowsHookEx(ms_hook[0])
        log(f"=== 停止，共 {len(records)} 条记录，已写入 {LOG} ===")