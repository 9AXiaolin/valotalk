"""验证日语 TTS 合成与播放。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.tts import TTS

CONFIG.set("tts.voice", "ja-JP-KeitaNeural", save=False)
CONFIG.set("tts.pitch", "+0Hz", save=False)
CONFIG.set("tts.rate", "+10%", save=False)

tts = TTS(CONFIG.get, log=lambda m: None)

cases = [
    "カバーして！",
    "Bをラッシュ！",
    "ボム解除に行くから、カバーして！",
    "残りHP少ない。",
]
print("=== 日语 TTS 合成 ===")
for text in cases:
    t0 = time.time()
    pcm = tts._via_edge(text)
    dt = time.time() - t0
    if pcm is None:
        print(f"  ✗ {text}  失败: {tts.last_error[:60]}")
    else:
        print(f"  ✓ {text:32s} {len(pcm)/24000:.2f}s  合成 {dt:.2f}s")

print("\n=== 播放链路（日语音色 → 虚拟麦克风）===")
dev = CONFIG.get("audio.tts_output_device", "")
print(f"  目标设备: {dev}")
pcm = tts._via_edge("カバーして！")
if pcm is not None:
    from valotalk.capture import SpeakerSink
    sink = SpeakerSink(dev)
    ok = sink.play(pcm, 24000)
    print(f"  播放: {'成功' if ok else '失败 ' + sink.last_error}")
else:
    print("  合成失败")