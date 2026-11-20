"""验证伤害报点识别（收紧后不该误判普通短语）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.translate import parse_hero_damage

cases = [
    ("Jett 120", "应该识别"),
    ("Omen 1", "应该识别"),
    ("Raze 140", "应该识别"),
    ("Sage 100", "应该识别"),
    ("Neon one", "应该识别"),
    ("wait 5", "不该识别（小写）"),
    ("go 3", "不该识别（停用词）"),
    ("you 2", "不该识别（停用词）"),
    ("and 1", "不该识别（停用词）"),
    ("hello", "不该识别（无数字）"),
    ("spike planted", "不该识别"),
]

for text, expect in cases:
    r = parse_hero_damage(text)
    mark = "✓" if bool(r) == ("应该识别" in expect) else "✗"
    print(f"  {mark} {text:16s} -> {r or '（不处理）':24s}   {expect}")