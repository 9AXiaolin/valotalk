"""实测：港/美服模式识别英语，日服模式识别日语。"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.asr import WhisperASR  # noqa: E402
from valotalk.capture import TARGET_SR, resample  # noqa: E402
from valotalk.config import CONFIG  # noqa: E402
from valotalk.translate import Translator  # noqa: E402

OUT = ROOT / "cache" / "lang_tests"


def gen(text: str, voice: str, name: str) -> np.ndarray | None:
    import edge_tts
    import miniaudio
    OUT.mkdir(parents=True, exist_ok=True)
    mp3 = OUT / f"sv_{name}.mp3"

    async def run():
        await edge_tts.Communicate(text, voice).save(str(mp3))

    try:
        asyncio.run(run())
        dec = miniaudio.decode(mp3.read_bytes(),
                               output_format=miniaudio.SampleFormat.FLOAT32,
                               nchannels=1, sample_rate=24000)
        return resample(np.asarray(dec.samples, dtype=np.float32), 24000, TARGET_SR)
    except Exception as exc:
        print(f"  合成失败: {type(exc).__name__} {str(exc)[:60]}")
        return None


def main() -> None:
    asr = WhisperASR(CONFIG.get)
    if not asr.ensure_loaded(on_status=lambda s: None):
        print("模型加载失败")
        return
    print(f"模型就绪 device={asr.device}\n")
    tr = Translator(CONFIG.get)

    # 港/美服模式
    CONFIG.set("asr.lang_teammates", "en", save=False)
    en_pcm = gen("Enemy one tap on A site, watch the flank.",
                 "en-US-GuyNeural", "en")
    if en_pcm is not None:
        t0 = time.time()
        heard = asr.transcribe(en_pcm, "en")
        print(f"[港/美服 英语] 识别 {time.time()-t0:.2f}s")
        print(f"   原文: Enemy one tap on A site, watch the flank.")
        print(f"   识别: {heard!r}")
        if heard:
            print(f"   译文: {tr.translate(heard, 'en', 'zh-CN')}")

    print()
    # 日服模式
    CONFIG.set("asr.lang_teammates", "ja", save=False)
    ja_pcm = gen("Aサイトに敵、フランクに注意。", "ja-JP-KeitaNeural", "ja")
    if ja_pcm is not None:
        t0 = time.time()
        heard = asr.transcribe(ja_pcm, "ja")
        print(f"[日服 日语] 识别 {time.time()-t0:.2f}s")
        print(f"   原文: Aサイトに敵、フランクに注意。")
        print(f"   识别: {heard!r}")
        if heard:
            print(f"   译文: {tr.translate(heard, 'ja', 'zh-CN')}")

    CONFIG.set("asr.lang_teammates", "en", save=True)


if __name__ == "__main__":
    main()