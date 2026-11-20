"""用新词库跑一批真实对局句子。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.translate import Translator, parse_hero_damage

t = Translator(CONFIG.get)

EN = [
    "gg wp",
    "nt, close one",
    "Jett 120",
    "Vandal 100 low",
    "A main push, two coming",
    "they are stacking B site",
    "one heaven, watch flank",
    "ninja defuse, get off",
    "save this round, force buy next",
    "Radiant smurf in their team",
    "Jett ult ready, execute now",
    "catwalk clear, no contact",
]

ZH = [
    "给个闪",
    "这里封烟，我下包",
    "别开大，留着",
    "他残血，一枪",
    "A大有人，抱团",
    "回防，他们在下包",
    "强拆，别松手",
    "对面经济局，别强起",
    "我卡了，等我一下",
    "发把枪",
]

print("=== 英 → 中 ===")
for s in EN:
    direct = parse_hero_damage(s)
    out = t.translate(s, "en", "zh-CN")
    tag = "直出" if t.backend_used == "script" else t.backend_used
    print(f"  {s:42s}")
    print(f"     → {out}   [{tag}]")

print("\n=== 中 → 英 ===")
for s in ZH:
    out = t.translate(s, "zh", "en")
    tag = "直出" if t.backend_used == "script" else t.backend_used
    print(f"  {s:16s} → {out:44s} [{tag}]")