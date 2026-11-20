"""生成多个音色的样音，方便自己对比挑选。"""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

TEXT = "Enemy one tap on A site, watch the flank."
VOICES = {
    "01_GuyNeural_当前默认": "en-US-GuyNeural",
    "02_AndrewNeural_更自然": "en-US-AndrewNeural",
    "03_AriaNeural_女声": "en-US-AriaNeural",
    "04_JennyNeural_女声友好": "en-US-JennyNeural",
    "05_RyanNeural_英音男": "en-GB-RyanNeural",
    "06_AvaMultilingual_表现力": "en-US-AvaMultilingualNeural",
}

OUT = Path(__file__).resolve().parent.parent / "cache" / "voice_samples"


async def gen(name: str, voice: str) -> None:
    path = OUT / f"{name}.mp3"
    try:
        comm = edge_tts.Communicate(TEXT, voice, rate="+10%", volume="+0%")
        await comm.save(str(path))
        size = path.stat().st_size
        print(f"  ✓ {name:28s} {voice:36s} {size} B")
    except Exception as exc:
        print(f"  ✗ {name:28s} {type(exc).__name__}: {str(exc)[:60]}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"句子: {TEXT}")
    print(f"输出: {OUT}\n")
    for name, voice in VOICES.items():
        await gen(name, voice)


if __name__ == "__main__":
    asyncio.run(main())