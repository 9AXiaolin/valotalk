"""查钩子线程为什么退出：GetMessageW 的返回值。"""
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
k32 = ctypes.windll.kernel32
WH_MOUSE_LL = 14
state = {"hook": 0, "msg_ret": None, "msg_err": None, "loop_count": 0}
seen: list[str] = []

PROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def callback(n_code, w_param, l_param):
    if n_code >= 0:
        seen.append(f"0x{w_param & 0xFFFF:04X}")
    return u.CallNextHookEx(state["hook"], n_code, w_param, l_param)


proc = PROC(callback)


def run():
    tid = k32.GetCurrentThreadId()
    print(f"  钩子线程 tid={tid}", flush=True)
    state["hook"] = u.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
    err = ctypes.get_last_error()
    print(f"  SetWindowsHookEx -> {state['hook']}  err={err}", flush=True)
    if not state["hook"]:
        return
    msg = wintypes.MSG()
    while True:
        ctypes.set_last_error(0)
        r = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
        state["msg_ret"] = r
        state["msg_err"] = ctypes.get_last_error()
        state["loop_count"] += 1
        print(f"  GetMessageW -> {r}  err={state['msg_err']}  msg=0x{msg.message:04X}",
              flush=True)
        if r <= 0:
            break
        u.TranslateMessage(ctypes.byref(msg))
        u.DispatchMessageW(ctypes.byref(msg))
    print(f"  循环结束，共 {state['loop_count']} 次", flush=True)


th = threading.Thread(target=run, daemon=True)
th.start()
time.sleep(0.3)
print("  线程存活:", th.is_alive())

print("\n=== 注入 XBUTTON ===")
for flags in (0x0080, 0x0100):
    inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
    mi = winapi._MOUSEINPUT()
    mi.dx = mi.dy = 0
    mi.mouseData = 0x0001
    mi.dwFlags = flags
    mi.time = 0
    mi.dwExtraInfo = None
    inp.union.mi = mi
    r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
    print(f"  SendInput flags=0x{flags:04X} -> {r}")
    time.sleep(0.1)

time.sleep(0.5)
print(f"\n  收到事件: {seen}")
print(f"  线程存活: {th.is_alive()}  loop_count={state['loop_count']}")

if state["hook"]:
    u.UnhookWindowsHookEx(state["hook"])