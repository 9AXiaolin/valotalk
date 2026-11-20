"""验证英/俄/日/韩 四种队友语音都能识别并翻成中文。"""
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
from valotalk.tts import TTS  # noqa: E402

# 每个语种一句同义的战术语音
CASES = [
    ("en", "en-US-GuyNeural", "Enemy one tap on A site, watch the flank."),
    ("ru", "ru-RU-DmitryNeural", "Враг на точке А, следи за флангом."),
    ("ja", "ja-JP-KeitaNeural", "Aサイトに敵、フランクに注意。"),
    ("ko", "ko-KR-InJoonNeural", "A 사이트에 적, 측면 조심해."),
]

OUT = ROOT / "cache" / "lang_tests"


def gen(text: str, voice: str, name: str) -> np.ndarray | None:
    import edge_tts
    import miniaudio
    OUT.mkdir(parents=True, exist_ok=True)
    mp3 = OUT / f"{name}.mp3"

    async def run():
        await edge_tts.Communicate(text, voice).save(str(mp3))

    try:
        asyncio.run(run())
        raw = mp3.read_bytes()
        dec = miniaudio.decode(raw, output_format=miniaudio.SampleFormat.FLOAT32,
                               nchannels=1, sample_rate=24000)
        return resample(np.asarray(dec.samples, dtype=np.float32), 24000, TARGET_SR)
    except Exception as exc:
        print(f"  合成失败 {name}: {type(exc).__name__} {str(exc)[:70]}")
        return None


def main() -> None:
    asr = WhisperASR(CONFIG.get)
    t0 = time.time()
    if not asr.ensure_loaded(on_status=lambda s: None):
        print("模型加载失败:", asr.load_error)
        return
    print(f"模型就绪 {time.time()-t0:.1f}s  device={asr.device}")
    print(f"asr.lang_teammates = {CONFIG.get('asr.lang_teammates')!r}\n")

    tr = Translator(CONFIG.get)

    for lang, voice, text in CASES:
        print(f"=== [{lang}] {text}")
        pcm = gen(text, voice, f"test_{lang}")
        if pcm is None:
            continue
        print(f"    音频 {len(pcm)/TARGET_SR:.2f}s")
        t0 = time.time()
        heard = asr.transcribe(pcm, None)        # None = 自动检测
        dt = time.time() - t0
        detected = asr.last_language
        prob = asr.last_language_prob
        print(f"    检测语种 = {detected} (置信度 {prob:.2f})  识别 {dt:.2f}s")
        print(f"    识别文本 = {heard!r}")
        if heard:
            zh = tr.translate(heard, detected or "en", "zh-CN")
            print(f"    中文译文 = {zh}  [{tr.backend_used}]")
        else:
            print("    !! 没识别出内容")
        print()


if __name__ == "__main__":
    main()