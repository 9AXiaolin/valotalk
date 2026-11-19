"""Silero 实测：直接从当前游戏输出采集，分段 → 识别 → 翻译，看真实效果。

用法（打游戏时跑）：python tools/silero_live_test.py [秒数]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.asr import WhisperASR  # noqa: E402
from valotalk.capture import (TARGET_SR, SileroSegmenter, _to_mono,  # noqa: E402
                              com_initialize, resample)
from valotalk.config import CONFIG  # noqa: E402
from valotalk.translate import Translator  # noqa: E402

import soundcard as sc  # noqa: E402

SR = 48000
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 25.0


def main() -> None:
    com_initialize()
    dev_name = CONFIG.get("audio.game_output_device")
    print(f"采集: {dev_name}   {SECS:.0f}s", flush=True)

    asr = WhisperASR(CONFIG.get)
    t0 = time.time()
    if not asr.ensure_loaded(on_status=lambda s: print("  ", s, flush=True)):
        return
    print(f"模型 {time.time()-t0:.1f}s  ({asr.device})", flush=True)
    tr = Translator(CONFIG.get)

    seg = SileroSegmenter(CONFIG.get("audio.vad", {}))
    print(f"Silero VAD: {'OK' if seg.ok else '不可用'}\n", flush=True)

    dev = sc.get_microphone(sc.get_speaker(dev_name).id, include_loopback=True)
    frames = 1440
    n_seg = 0
    peak_rms = 0.0
    t_end = time.time() + SECS
    segments = []

    with dev.recorder(samplerate=SR, blocksize=frames) as rec:
        while time.time() < t_end:
            raw = rec.record(numframes=frames)
            a = _to_mono(raw)
            if a.size == 0:
                continue
            peak_rms = max(peak_rms, float(np.sqrt(np.mean(a ** 2))))
            for s in seg.feed(resample(a, SR, TARGET_SR)) or []:
                n_seg += 1
                segments.append(s)
                print(f"  [段 {n_seg}] {len(s)/TARGET_SR:.2f}s 音量"
                      f"{float(np.sqrt(np.mean(s**2))):.4f} → 识别中…", flush=True)
                t1 = time.time()
                txt = asr.transcribe(s, "en")
                if not txt:
                    print("      （没识别出内容，多半是音效）", flush=True)
                    continue
                zh = tr.translate(txt, "en", "zh-CN")
                print(f"      识别 {time.time()-t1:.2f}s: {txt}", flush=True)
                print(f"      译文: {zh}  [{tr.backend_used}]", flush=True)

    tail = seg.flush()
    if tail is not None and tail.size:
        n_seg += 1
        txt = asr.transcribe(tail, "en")
        print(f"  [尾段] {len(tail)/TARGET_SR:.2f}s → {txt}", flush=True)

    print(f"\n峰值 RMS={peak_rms:.4f}  切出 {n_seg} 段")
    if n_seg == 0:
        print("  ⚠ 一段都没切出来：游戏此刻可能没人在说话，或者语音确实没进这条输出")
        print("     → 让队友说句话，或自己对着麦克风说，再跑一次")


if __name__ == "__main__":
    main()