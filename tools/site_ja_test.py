"""验证日语的包点喊话。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.translate import Translator

t = Translator(CONFIG.get)
print("=== 中→日 包点 ===")
for zh in ["A包", "B包", "C包", "A点", "去A", "在B", "打C"]:
    out = t.translate(zh, "zh", "ja")
    print(f"  {zh:6s} -> {out}   [{t.backend_used}]")

print("\n=== 中→英 包点（对比）===")
for zh in ["A包", "B包", "C包"]:
    out = t.translate(zh, "zh", "en")
    print(f"  {zh:6s} -> {out}   [{t.backend_used}]")