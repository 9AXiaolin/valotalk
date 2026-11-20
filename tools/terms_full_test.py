"""按三张图逐类验证术语库。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import terms
from valotalk.translate import VALORANT_TERMS, Translator, parse_hero_damage
from valotalk.config import CONFIG

print("=== 表规模 ===")
for n in ["ABBR_CHAT", "CALLS", "VOICE", "AGENTS", "WEAPONS", "ROLES", "RANKS", "MAPS"]:
    print(f"  {n:12s} {len(getattr(terms, n)):4d}")
print(f"  {'合并术语表':12s} {len(VALORANT_TERMS):4d}")

t = Translator(CONFIG.get)

print("\n=== 图1：特工 ===")
for k in ["jett", "omen", "raze", "sage", "kay/o", "deadlock", "clove"]:
    print(f"  {k:10s} {terms.AGENTS.get(k)}")

print("\n=== 图1：武器 ===")
for k in ["classic", "sheriff", "spectre", "vandal", "operator", "marshal", "odin"]:
    print(f"  {k:10s} {terms.WEAPONS.get(k)}")

print("\n=== 图1：职责定位 ===")
for k, v in terms.ROLES.items():
    print(f"  {k:12s} {v}")

print("\n=== 图2/3：通用报点（抽样 20 条）===")
sample = ["ct spawn", "a main", "a short", "care a", "a many", "last a",
          "spike down", "nest", "rafters", "on top", "hell", "cubby",
          "green box", "stairs", "elbow", "jiggle peek", "wallbang",
          "one way smoke", "cut noise", "lurk"]
for k in sample:
    print(f"  {k:18s} {terms.CALLS.get(k)}")

print("\n=== 图3：经济与残局 ===")
for k in ["retake", "fake", "split", "rehit", "ninja defuse", "off spike",
          "buy time", "anti eco", "half buy", "full buy", "force buy",
          "drop me", "armor", "lagging", "feeding"]:
    print(f"  {k:18s} {terms.CALLS.get(k)}")

print("\n=== 图3：段位 ===")
for k, v in terms.RANKS.items():
    print(f"  {k:12s} {v}")

print("\n=== 图3：地图 ===")
for k, v in terms.MAPS.items():
    print(f"  {k:12s} {v}")

print("\n=== 实际翻译效果 ===")
for s in ["enemy jett one tap", "vandal is strong", "they are pushing mid",
          "one heaven", "Jett 120", "immortal lobby"]:
    print(f"  {s:26s} → {t.translate(s, 'en', 'zh-CN')}")