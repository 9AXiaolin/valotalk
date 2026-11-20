"""列出 edge-tts 可用的英文音色。"""
from __future__ import annotations

import asyncio

import edge_tts


async def main() -> None:
    voices = await edge_tts.list_voices()
    en = [v for v in voices if v["Locale"].startswith("en-")]
    print(f"英文音色共 {len(en)} 个\n")

    groups: dict[str, list[dict]] = {}
    for v in en:
        groups.setdefault(v["Locale"], []).append(v)

    for loc in sorted(groups):
        print(f"--- {loc} ---")
        for v in sorted(groups[loc], key=lambda x: x["ShortName"]):
            tags = []
            if "Male" in v.get("Gender", ""):
                tags.append("男")
            elif "Female" in v.get("Gender", ""):
                tags.append("女")
            # 常见标签
            for t in v.get("VoiceTag", {}).get("VoicePersonalities", []):
                tags.append(t)
            print(f"  {v['ShortName']:34s} {'/'.join(tags)}")
        print()


if __name__ == "__main__":
    asyncio.run(main())