"""列出全部英文音色（含性别与性格标签），用于挑「萝莉/御姐/气泡/青年」气质的声线。"""
from __future__ import annotations

import asyncio

import edge_tts


async def main() -> None:
    voices = await edge_tts.list_voices()
    en = [v for v in voices if v["Locale"].startswith("en-")]
    print(f"英文音色共 {len(en)} 个\n")

    for v in sorted(en, key=lambda x: (x["Locale"], x["ShortName"])):
        g = "男" if "Male" in v.get("Gender", "") else ("女" if "Female" in v.get("Gender", "") else "?")
        tags = v.get("VoiceTag", {}).get("VoicePersonalities", [])
        print(f"  {v['Locale']:8s} {v['ShortName']:36s} {g}  {'/'.join(tags)}")


if __name__ == "__main__":
    asyncio.run(main())