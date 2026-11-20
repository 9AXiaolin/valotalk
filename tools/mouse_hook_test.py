"""验证鼠标侧键走低级钩子能被捕获。

用 SendInput 自己发一个 XBUTTON 事件，钩子应该立刻收到 ——
这同时证明了「游戏里按侧键也能读到」的基础能力。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

events: list[tuple[str, str]] = []

w = winapi.HotkeyWatcher()
w.bind("ptt", "mouse4",
       on_press=lambda: events.append(("down", "mouse4")),
       on_release=lambda: events.append(("up", "mouse4")))
w.bind("through", "mouse5",
       on_press=lambda: events.append(("down", "mouse5")))
w.bind("clear", "f4", on_press=lambda: events.append(("down", "f4")))

print("键盘绑定表:", w._bindings)
print("鼠标钩子处理表:", w.mouse_hook._handlers)

ok = w.start()
print(f"钩子已安装: {ok}  handle={w.mouse_hook._hook}  错误={w.mouse_hook.error}")

print("\n=== 用 SendInput 模拟 XBUTTON1 按下/松开 ===")
time.sleep(0.2)
winapi._send_xbutton(0x0001, up=False)
time.sleep(0.15)
winapi._send_xbutton(0x0001, up=True)
time.sleep(0.3)
print("  事件:", events)

print("\n=== 模拟 XBUTTON2 按下 ===")
events.clear()
winapi._send_xbutton(0x0002, up=False)
time.sleep(0.2)
winapi._send_xbutton(0x0002, up=True)
time.sleep(0.3)
print("  事件:", events)

print("\n=== 对照：GetAsyncKeyState 对 XBUTTON 的表现 ===")
winapi._send_xbutton(0x0001, up=False)
time.sleep(0.05)
state = winapi.user32.GetAsyncKeyState(0x05)
print(f"  GetAsyncKeyState(0x05) = 0x{state & 0xFFFF:04X}  "
      f"按下位={'是' if state & 0x8000 else '否'}")
winapi._send_xbutton(0x0001, up=True)
time.sleep(0.1)

w.stop()
print("\n结果:", "钩子可用" if any(e[0] == "down" for e in [("down", "x")]) and events else "见上")