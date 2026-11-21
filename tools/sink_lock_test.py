"""验证 SpeakerSink 类级锁 + sd.play() 播完才返回。

测试点：
1. 两个 SpeakerSink 实例同时 play() → 第二个必须等第一个播完（类级锁）
2. play() 返回时音频确实播完（不是 write 完缓冲就返回）
3. 实例锁被移除后 play() 仍能正常工作
"""
from __future__ import annotations
import sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from valotalk.capture import SpeakerSink

SR = 48000

def tone(sec: float, freq: float = 440.0) -> np.ndarray:
    t = np.arange(int(SR * sec), dtype=np.float32) / SR
    return (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

# 找一个真实输出设备
import sounddevice as sd
devices = [d for d in sd.query_devices() if d.get("max_output_channels", 0) >= 1]
if not devices:
    print("没有输出设备，跳过")
    sys.exit(0)
dev_name = devices[0]["name"]
print(f"用设备: {dev_name}")

print("\n=== 1) 类级锁存在 ===")
assert hasattr(SpeakerSink, '_play_lock'), "没有 _play_lock"
assert isinstance(SpeakerSink._play_lock, type(threading.Lock())), "不是锁"
print("  ✓ SpeakerSink._play_lock 存在且是 threading.Lock")

print("\n=== 2) 两个实例同时 play() 串行执行（类级锁）===")
s1 = SpeakerSink(dev_name)
s2 = SpeakerSink(dev_name)
audio = tone(0.8)  # 0.8 秒

wall_t0 = time.time()
results = {}

def play_and_time(sink, label):
    sink.play(audio, SR)
    results[label] = time.time()

th1 = threading.Thread(target=play_and_time, args=(s1, "s1"))
th2 = threading.Thread(target=play_and_time, args=(s2, "s2"))
th1.start(); th2.start()
th1.join(); th2.join()
wall_total = time.time() - wall_t0

print(f"  总耗时 {wall_total:.2f}s（音频 0.8s × 2 = 1.6s，串行应 >= 1.6s）")
assert wall_total >= 1.5, f"FAIL - 两个播放没有串行（{wall_total:.2f}s < 1.5s）"
print(f"  OK - 串行执行，总耗时 >= 1.5s")

print("\n=== 3) play() 返回时确实播完 ===")
# 0.5 秒音频，play() 应该 >= 0.45s 才返回（不是瞬间返回）
short = tone(0.5)
t0 = time.time()
s1.play(short, SR)
elapsed = time.time() - t0
print(f"  播 0.5s 音频，play() 耗时 {elapsed:.2f}s")
assert elapsed >= 0.40, f"FAIL - play() 太快返回 ({elapsed:.2f}s)，可能掐断了"
print(f"  OK - 播完才返回")

print("\n全部通过 ✅")
