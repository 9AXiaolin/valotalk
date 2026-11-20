"""定位：SendInput 发 XBUTTON 到底成不成功。"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

u = winapi.user32


def send_input_raw(xbutton: int, up: bool) -> tuple[int, int]:
    inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
    mi = winapi._MOUSEINPUT()
    mi.dx = 0
    mi.dy = 0
    mi.mouseData = xbutton
    mi.dwFlags = winapi.MOUSEEVENTF_XUP if up else winapi.MOUSEEVENTF_XDOWN
    mi.time = 0
    mi.dwExtraInfo = None
    inp.union.mi = mi
    ctypes.set_last_error(0)
    r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
    return r, ctypes.get_last_error()


print(f"sizeof(INPUT) = {ctypes.sizeof(winapi._INPUT)}  (x64 应为 40)")
print(f"sizeof(MOUSEINPUT) = {ctypes.sizeof(winapi._MOUSEINPUT)}  (应为 32)")
print(f"sizeof(KEYBDINPUT) = {ctypes.sizeof(winapi._KEYBDINPUT)}")
print(f"union 大小 = {ctypes.sizeof(winapi._INPUTUNION)}")

print("\n=== 对照：键盘 SendInput（已知能工作）===")
inp = winapi._INPUT(type=winapi.INPUT_KEYBOARD)
scan = u.MapVirtualKeyW(0x71, 0)  # F2
inp.union.ki = winapi._KEYBDINPUT(wVk=0, wScan=scan, dwFlags=0x0008,
                                  time=0, dwExtraInfo=None)
ctypes.set_last_error(0)
r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
print(f"  键盘 down 返回 {r} err={ctypes.get_last_error()}")
inp.union.ki.dwFlags = 0x0008 | 0x0002
r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
print(f"  键盘 up   返回 {r} err={ctypes.get_last_error()}")

print("\n=== XBUTTON1 ===")
r, e = send_input_raw(0x0001, up=False)
print(f"  XDOWN 返回 {r}  err={e}  (1=成功, 0=失败)")
time.sleep(0.05)
print(f"  GetAsyncKeyState(0x05) = 0x{u.GetAsyncKeyState(0x05) & 0xFFFF:04X}")
r, e = send_input_raw(0x0001, up=True)
print(f"  XUP   返回 {r}  err={e}")

print("\n=== 用 GetKeyState 也看一眼 ===")
time.sleep(0.05)
print(f"  GetKeyState(0x05) = 0x{u.GetKeyState(0x05) & 0xFFFF:04X}")

print("\n=== 换了 dwExtraInfo=0 再试 ===")


def send_input_zero(xbutton: int, up: bool):
    inp = winapi._INPUT(type=winapi.INPUT_MOUSE)
    mi = winapi._MOUSEINPUT()
    mi.dx = 0
    mi.dy = 0
    mi.mouseData = xbutton
    mi.dwFlags = winapi.MOUSEEVENTF_XUP if up else winapi.MOUSEEVENTF_XDOWN
    mi.time = 0
    mi.dwExtraInfo = ctypes.cast(0, ctypes.POINTER(ctypes.c_ulong))
    inp.union.mi = mi
    ctypes.set_last_error(0)
    r = u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(winapi._INPUT))
    return r, ctypes.get_last_error()


r, e = send_input_zero(0x0001, up=False)
print(f"  XDOWN 返回 {r}  err={e}")
time.sleep(0.05)
print(f"  GetAsyncKeyState(0x05) = 0x{u.GetAsyncKeyState(0x05) & 0xFFFF:04X}")
send_input_zero(0x0001, up=True)