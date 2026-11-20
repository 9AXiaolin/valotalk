"""验证 LLM 专有名词约束（武器/段位）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.translate import _LLM_SYSTEM, Translator
from valotalk.config import CONFIG

print(f"system prompt: {len(_LLM_SYSTEM)} 字符\n")

t = Translator(CONFIG.get)
cases = [
    ("vandal is strong", "暴徒"),
    ("sheriff headshot", "神射"),
    ("phantom better than vandal", "幻象"),
    ("immortal lobby", "神话"),
    ("they have an operator", "大狙"),
    ("diamond rank", "钻石"),
    ("raze used her ult", "Raze/芮兹"),
]
for en, expect in cases:
    out = t.translate(en, "en", "zh-CN")
    hit = expect in (out or "") or any(p in (out or "") for p in expect.split("/"))
    print(f"  {'✓' if hit else '✗'} {en:30s} -> {out}   (期望含「{expect}」)")