"""列出日语可用音色。"""
from __future__ import annotations

import asyncio

import edge_tts


async def main() -> None:
    voices = await edge_tts.list_voices()
    ja = [v for v in voices if v["Locale"].startswith("ja-")]
    print(f"日语音色共 {len(ja)} 个\n")
    for v in sorted(ja, key=lambda x: x["ShortName"]):
        g = "男" if "Male" in v.get("Gender", "") else "女"
        tags = v.get("VoiceTag", {}).get("VoicePersonalities", [])
        print(f"  {v['ShortName']:32s} {g}  {'/'.join(tags)}")


if __name__ == "__main__":
    asyncio.run(main())