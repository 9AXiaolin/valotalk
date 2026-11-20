"""检查低级鼠标钩子是否真的活着：收所有鼠标事件，不只是侧键。"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

u = winapi.user32
WH_MOUSE_LL = 14

seen: list[str] = []

# 自己写一个最直白的钩子，打印一切
PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
hook_handle = [0]


def callback(n_code, w_param, l_param):
    if n_code >= 0:
        seen.append(f"wParam=0x{w_param & 0xFFFF:04X} nCode={n_code}")
    return u.CallNextHookEx(hook_handle[0], n_code, w_param, l_param)


import threading
import time as _t

proc = PROC(callback)


def run():
    hook_handle[0] = u.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
    print(f"  钩子句柄 = {hook_handle[0]}  err={ctypes.get_last_error()}", flush=True)
    if not hook_handle[0]:
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))


th = threading.Thread(target=run, daemon=True)
th.start()
_t.sleep(0.3)
print("  线程存活:", th.is_alive())

print("\n=== 发送鼠标事件 ===")
# 1. 鼠标移动（最基础的事件）
u.SetCursorPos(100, 100)
_t.sleep(0.1)
u.SetCursorPos(120, 120)
_t.sleep(0.2)
print("  SetCursorPos 后收到事件数:", len(seen))

# 2. SendInput 移动
seen.clear()
inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
mi = winapi._MOUSEINPUT()
mi.dx = 10
mi.dy = 10
mi.mouseData = 0
mi.dwFlags = 0x0001  # MOUSEEVENTF_MOVE
mi.time = 0
mi.dwExtraInfo = None
inp.union.mi = mi
r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
_t.sleep(0.2)
print(f"  SendInput MOVE 返回 {r}，收到 {len(seen)} 个事件")

# 3. XBUTTON
seen.clear()
for up in (False, True):
    inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
    mi = winapi._MOUSEINPUT()
    mi.dx = 0
    mi.dy = 0
    mi.mouseData = 0x0001
    mi.dwFlags = 0x0100 if up else 0x0080
    mi.time = 0
    mi.dwExtraInfo = None
    inp.union.mi = mi
    u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
    _t.sleep(0.1)
print(f"  XBUTTON down/up 后收到 {len(seen)} 个事件")
for s in seen[:6]:
    print("   ", s)

if hook_handle[0]:
    u.UnhookWindowsHookEx(hook_handle[0])
print("\n结论：", "钩子工作正常" if seen else "钩子收不到任何事件")