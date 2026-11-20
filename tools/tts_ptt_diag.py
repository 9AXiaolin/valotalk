"""诊断 TTS 播放与按键模拟。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi
from valotalk.config import CONFIG
from valotalk.tts import TTS

print("=== tts 配置 ===")
print(json.dumps(CONFIG.get("tts"), ensure_ascii=False, indent=2))

print("\n=== 音频设备 ===")
for k in ("game_output_device", "mic_device", "tts_output_device"):
    print(f"  {k:22s} = {CONFIG.get('audio.' + k)!r}")

# 拦截按键
events: list[tuple[str, str]] = []
od, ou = winapi.key_down, winapi.key_up
winapi.key_down = lambda n: (events.append(("down", n)), od(n))
winapi.key_up = lambda n: (events.append(("up", n)), ou(n))

print("\n=== 直接调用 speak（英文短句）===")
tts = TTS(CONFIG.get, log=lambda m: print("   log:", m))
t0 = time.time()
res = tts.speak("Cover me, I'm defusing.")
print(f"  返回: {res}   用时 {time.time()-t0:.2f}s")
print(f"  last_error: {tts.last_error!r}")
print(f"  按键事件: {events}")

print("\n=== 检查 _play_into_game 内部判断 ===")
dev = CONFIG.get("audio.tts_output_device", "")
print(f"  device 非空: {bool(dev)}  ({dev!r})")
print(f"  game_ptt_enabled: {CONFIG.get('tts.game_ptt_enabled')}")
print(f"  game_ptt_key: {CONFIG.get('tts.game_ptt_key')!r}")

print("\n=== 检查 SpeakerSink 能否找到设备 ===")
from valotalk.capture import SpeakerSink, sd_pick_output, find_speaker
print(f"  sd_pick_output: {sd_pick_output(dev)}")
print(f"  find_speaker: {find_speaker(dev)}")

print("\n=== 只用按键模拟（不播放）===")
hold = winapi.VirtualKeyHold()
events.clear()
hold.acquire("v")
time.sleep(0.05)
hold.release()
print(f"  acquire/release 后事件: {events}")