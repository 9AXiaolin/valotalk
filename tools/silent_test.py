"""完全静音的链路验证（不打游戏、不联网、不出声也能跑）：

  1) 识别：把已合成的 mp3 直接喂 whisper（不经任何音频设备）
  2) 送游戏：播放到 VB-Cable（虚拟线缆，无物理输出，不会响）→ 从另一端录回 → 再识别
     顺便用「录回时长 vs 原始时长」判断有没有变速
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.asr import WhisperASR  # noqa: E402
from valotalk.capture import (TARGET_SR, find_microphone, find_speaker,  # noqa: E402
                              resample)
from valotalk.config import CONFIG  # noqa: E402
from valotalk.translate import Translator  # noqa: E402
from valotalk.tts import TTS  # noqa: E402

SR = 48000
CABLE_PLAY = "变声器输出 (VB-Audio Virtual Cable)"
CABLE_REC = "变音麦克风 (VB-Audio Virtual Cable)"


def rms(x) -> float:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def active_len(x, sr, rel=0.10) -> float:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    fr = max(1, int(sr * 0.01))
    n = x.size // fr
    if n == 0:
        return 0.0
    env = np.sqrt(np.mean(x[: n * fr].reshape(n, fr) ** 2, axis=1) + 1e-12)
    peak = float(env.max())
    if peak < 1e-3:
        return 0.0
    idx = np.where(env > peak * rel)[0]
    return float(idx.size) * fr / sr if idx.size else 0.0


def trim(x, sr, rel=0.10):
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    fr = max(1, int(sr * 0.02))
    n = x.size // fr
    if n == 0:
        return x
    env = np.sqrt(np.mean(x[: n * fr].reshape(n, fr) ** 2, axis=1) + 1e-12)
    peak = float(env.max())
    if peak < 1e-4:
        return x
    idx = np.where(env > peak * rel)[0]
    if idx.size == 0:
        return x
    return x[max(0, idx[0] - 2) * fr: min(n, idx[-1] + 3) * fr]


def main() -> None:
    tts = TTS(CONFIG.get, log=print)
    tr = Translator(CONFIG.get)

    print("=" * 62)
    print("1. 识别（纯文件，不碰音频设备、不发声）")
    print("=" * 62)
    asr = WhisperASR(CONFIG.get)
    t0 = time.time()
    ok = asr.ensure_loaded(on_status=lambda s: print("   ", s))
    print(f"   whisper 就绪={ok}  用时 {time.time()-t0:.1f}s")
    if not ok:
        return

    for path, lang, expect in [
        (ROOT / "cache" / "diag.mp3", "en", "Enemy on B, watch the flank."),
        (ROOT / "cache" / "zh_src.mp3", "zh", "我从中路过去，你们看住绕后。"),
    ]:
        if not path.exists():
            print(f"   跳过（缺文件）{path.name}")
            continue
        pcm = tts._decode_audio(path)
        if pcm is None:
            print(f"   解码失败 {path.name}: {tts.last_error}")
            continue
        a16 = resample(pcm, 24000, TARGET_SR)
        t0 = time.time()
        text = asr.transcribe(a16, lang)
        dt = time.time() - t0
        print(f"\n   [{lang}] {path.name}  {len(pcm)/24000:.2f}s  识别耗时 {dt:.2f}s")
        print(f"        期望: {expect}")
        print(f"        识别: {text!r}")
        if text:
            tgt = ("zh-CN" if lang == "en" else "en")
            out = tr.translate(text, lang, tgt)
            print(f"        翻译: {out}   (backend={tr.backend_used})")

    print("\n" + "=" * 62)
    print("2. TTS → 虚拟麦克风（VB-Cable，静音），验证队友能听到 + 有无变速")
    print("=" * 62)
    SPK_N, MIC_N = find_speaker(CABLE_PLAY), find_microphone(CABLE_REC)
    if SPK_N is None or MIC_N is None:
        print("   找不到 VB-Cable 端点，跳过")
        return

    # 底噪
    cap = {}
    with MIC_N.recorder(samplerate=SR) as r:
        cap["n"] = np.asarray(r.record(numframes=int(SR * 0.8)), dtype=np.float32).reshape(-1)
    print(f"   VB-Cable 底噪 RMS={rms(cap['n']):.5f}")

    en = "Rotating to A now, cover me."
    pcm = tts._via_edge(en)
    if pcm is None:
        print("   TTS 合成失败:", tts.last_error)
        return
    src_len = len(pcm) / 24000
    print(f"   原文: {en}")
    print(f"   合成: {src_len:.2f}s  →  播放到 {CABLE_PLAY}")

    dur = src_len + 2.0
    got: dict = {}

    def rec():
        with MIC_N.recorder(samplerate=SR) as r:
            got["d"] = np.asarray(r.record(numframes=int(SR * dur)), dtype=np.float32).reshape(-1)

    th = threading.Thread(target=rec, daemon=True)
    th.start()
    time.sleep(0.5)
    with SPK_N.player(samplerate=SR, channels=1) as p:
        p.play(resample(pcm, 24000, SR).reshape(-1, 1))
    th.join(timeout=dur + 8)

    d = got.get("d")
    if d is None:
        print("   录回失败")
        return
    al = active_len(d, SR)
    print(f"   录回: 总长 {len(d)/SR:.2f}s  有声段 {al:.2f}s  RMS={rms(d):.4f}")
    ratio = al / src_len if src_len else 0
    print(f"   有声段/原始 = {ratio:.2f}x  " +
          ("[OK] 无变速" if 0.85 < ratio < 1.20 else "[WARN] 疑似变速，需换 sounddevice 输出"))

    heard = asr.transcribe(resample(trim(d, SR), SR, TARGET_SR), "en")
    print(f"   对方会听到: {heard!r}")
    if heard:
        word_hit = len(set(heard.lower().split()) & set(en.lower().split()))
        print(f"   词重合 {word_hit} 个 → " +
              ("[OK] 语音链路可用" if word_hit >= 3 else "[WARN] 重合偏低"))

    print("\n完成。")


if __name__ == "__main__":
    main()