"""按风格预设生成样音，用来挑选。"""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

TEXT = "Enemy one tap on A site, watch the flank."
OUT = Path(__file__).resolve().parent.parent / "cache" / "voice_samples" / "styles"

PRESETS = {
    "00_原声_Guy": ("en-US-GuyNeural", "+0Hz", "+10%"),
    "01_萝莉音_Ana": ("en-US-AnaNeural", "+35Hz", "+15%"),
    "02_正太音_Brian": ("en-US-BrianNeural", "+25Hz", "+12%"),
    "03_御姐音_Aria": ("en-US-AriaNeural", "-20Hz", "-5%"),
    "04_大叔音_Christopher": ("en-US-ChristopherNeural", "-25Hz", "-8%"),
    "05_气泡音_Christopher": ("en-US-ChristopherNeural", "-35Hz", "-12%"),
    "06_青年音_Brian": ("en-US-BrianNeural", "+5Hz", "+8%"),
    "07_Emma_开朗": ("en-US-EmmaNeural", "+0Hz", "+10%"),
    "08_Ava_表现力": ("en-US-AvaNeural", "+0Hz", "+10%"),
    "09_印式英语_NeerjaExpressive": ("en-IN-NeerjaExpressiveNeural", "+0Hz", "+10%"),
    "10_港式英语_Yan": ("en-HK-YanNeural", "+0Hz", "+10%"),
    "11_南非英语_Leah": ("en-ZA-LeahNeural", "+0Hz", "+10%"),
}


async def gen(name: str, voice: str, pitch: str, rate: str) -> None:
    path = OUT / f"{name}.mp3"
    try:
        comm = edge_tts.Communicate(TEXT, voice, rate=rate, pitch=pitch)
        await comm.save(str(path))
        print(f"  ✓ {name:34s} {voice:34s} {pitch:>6s} {rate:>5s}  "
              f"{path.stat().st_size} B")
    except Exception as exc:
        print(f"  ✗ {name:34s} {type(exc).__name__}: {str(exc)[:60]}")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"句子: {TEXT}\n输出: {OUT}\n")
    for name, (voice, pitch, rate) in PRESETS.items():
        await gen(name, voice, pitch, rate)


if __name__ == "__main__":
    asyncio.run(main())