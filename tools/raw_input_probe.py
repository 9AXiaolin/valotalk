"""测 Raw Input 能否收到按键。

注意：SendInput 注入的输入【不一定】会出现在 Raw Input 里
（Raw Input 主要报告物理 HID 设备事件）。
所以这里分两步：
  ① 先看 SendInput 能不能触发（能触发最好）
  ② 让用户手动按键，看物理按键能不能触发
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

raw = winapi.RawKeyboardInput()
ok = raw.start()
print(f"Raw Input 启动: {ok}")
print(f"  窗口句柄: {raw._hwnd}")
print(f"  错误: {raw.error}")
print(f"  线程存活: {raw._thread.is_alive() if raw._thread else False}")

if not ok:
    print("\n启动失败，无法继续")
    sys.exit(1)

print("\n=== ① SendInput 注入 F2 ===")
winapi._send_key(0x71, up=False)
time.sleep(0.15)
winapi._send_key(0x71, up=True)
time.sleep(0.3)
got = raw.drain()
print(f"  收到: {got}")
print(f"  {'✓ 注入能触发' if got else '✗ 注入不触发（正常，Raw Input 只看物理设备）'}")

print("\n=== ② 请手动按 F2 和 B 键（5 秒）===")
print("  现在按：F2、B、鼠标侧键", flush=True)
time.sleep(5)
got2 = raw.drain()
print(f"  收到 {len(got2)} 个事件: {got2}")

if got2:
    names = {0x71: "F2", 0x42: "B", 0x05: "MOUSE4", 0x06: "MOUSE5"}
    for vk, down in got2[:10]:
        print(f"    {names.get(vk, hex(vk)):8s} {'DOWN' if down else 'UP'}")
    print("\n✓ Raw Input 能收到物理按键")
else:
    print("\n✗ 5 秒内没收到任何按键")

raw.stop()
print("\n完成")