"""验证鼠标钩子回调的耗时（必须微秒级，否则会卡系统鼠标）。"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

hook = winapi.MouseHook()
hook.bind(0x05, on_press=lambda: None, on_release=lambda: None)
hook.bind(0x06, on_press=lambda: None)

info = winapi._MSLLHOOKSTRUCT()
info.mouseData = 1 << 16      # XBUTTON1
addr = ctypes.addressof(info)
down_msg = winapi.WM_XBUTTONDOWN
up_msg = winapi.WM_XBUTTONUP

# 预热
for _ in range(10):
    hook._callback(0, down_msg, addr)
hook.drain()

N = 2000
t0 = time.perf_counter()
for i in range(N):
    hook._callback(0, down_msg if i % 2 == 0 else up_msg, addr)
elapsed = time.perf_counter() - t0

print(f"回调 {N} 次耗时 {elapsed*1e6:.0f} µs，平均 {elapsed/N*1e6:.2f} µs/次")
print(f"  → 单次 {'✓ 安全（<50µs）' if elapsed/N*1e6 < 50 else '✗ 太慢，会卡鼠标'}")

q = hook.drain()
print(f"\n队列收到 {len(q)} 个事件（maxlen={hook._queue.maxlen}）")
print(f"  丢弃计数: {hook.dropped}")
print(f"  前 4 个: {q[:4]}")

# 验证 maxlen 保护
print("\n=== 灌爆队列测试 ===")
for _ in range(500):
    hook._callback(0, down_msg, addr)
print(f"  灌入 500 个后队列长度: {len(hook._queue)}（应被 maxlen 截断到 256）")
print(f"  丢弃计数: {hook.dropped}")
hook.drain()

# 验证 drain 后队列为空
print(f"\ndrain 后队列长度: {len(hook._queue)}（应为 0）")

# 验证非侧键事件被忽略
print("\n=== 非 XBUTTON 事件 ===")
other = winapi._MSLLHOOKSTRUCT()
other.mouseData = 0
hook._callback(0, 0x0200, ctypes.addressof(other))   # WM_MOUSEMOVE
print(f"  鼠标移动后队列长度: {len(hook._queue)}（应为 0，只关心侧键）")