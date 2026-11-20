"""用 mouse_event（旧 API）和 SendInput 分别注入鼠标，看钩子能否收到。"""
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
WH_MOUSE_LL = 14
seen: list[str] = []
hook_handle = [0]

PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def callback(n_code, w_param, l_param):
    if n_code >= 0:
        wp = w_param & 0xFFFF
        if wp in (0x020B, 0x020C):
            info = ctypes.cast(l_param, ctypes.POINTER(winapi._MSLLHOOKSTRUCT)).contents
            which = (info.mouseData >> 16) & 0xFFFF
            flags = "注入" if info.flags & 1 else "真实"
            seen.append(f"XBUTTON{which} {'DOWN' if wp == 0x020B else 'UP'} ({flags})")
        elif wp in (0x0200, 0x0201, 0x0202):
            seen.append(f"鼠标移动/点击 wParam=0x{wp:04X}")
    return u.CallNextHookEx(hook_handle[0], n_code, w_param, l_param)


proc = PROC(callback)


def run():
    hook_handle[0] = u.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
    print(f"钩子 = {hook_handle[0]}", flush=True)
    if not hook_handle[0]:
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))


threading.Thread(target=run, daemon=True).start()
time.sleep(0.3)

print("=== A. mouse_event 移动 ===")
seen.clear()
u.mouse_event(0x0001, 30, 30, 0, 0)
time.sleep(0.2)
print(f"  收到 {len(seen)} 个事件: {seen[:3]}")

print("\n=== B. mouse_event XBUTTON1 ===")
seen.clear()
u.mouse_event(0x0080, 0, 0, 0x0001, 0)
time.sleep(0.1)
u.mouse_event(0x0100, 0, 0, 0x0001, 0)
time.sleep(0.2)
print(f"  收到 {len(seen)} 个事件: {seen}")

print("\n=== C. SendInput XBUTTON1（带 LLMHF 检查）===")
seen.clear()
for flags, up in ((0x0080, False), (0x0100, True)):
    inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
    mi = winapi._MOUSEINPUT()
    mi.dx = 0
    mi.dy = 0
    mi.mouseData = 0x0001
    mi.dwFlags = flags
    mi.time = 0
    mi.dwExtraInfo = None
    inp.union.mi = mi
    r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
    print(f"  flags=0x{flags:04X} 返回 {r}")
    time.sleep(0.1)
time.sleep(0.2)
print(f"  收到 {len(seen)} 个事件: {seen}")

print("\n=== D. 真实鼠标（如果你现在动一下鼠标会出现在这里）===")
seen.clear()
print("  等 3 秒，请移动/点击鼠标 …", flush=True)
time.sleep(3)
print(f"  收到 {len(seen)} 个事件: {seen[:5]}")

if hook_handle[0]:
    u.UnhookWindowsHookEx(hook_handle[0])

print("\n结论:",
      "钩子能收到注入事件" if any("XBUTTON" in s for s in seen) or seen else "钩子没收到任何东西")