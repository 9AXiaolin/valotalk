"""检查术语追注为何失败。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import terms
from valotalk.config import CONFIG
from valotalk.translate import Translator

print("terms 里有哪些表:")
for n in dir(terms):
    v = getattr(terms, n)
    if isinstance(v, dict) and not n.startswith("_"):
        print(f"  {n:14s} {len(v):4d} 条")

calls = getattr(terms, "CALLS", {})
print("\nCALLS 里 rush 的译法:", repr(calls.get("rush")))
print("CALLS 里 rush b 的译法:", repr(calls.get("rush b")))
print("CALLS 里 plant 的译法:", repr(calls.get("plant")))

CONFIG.set("translate.backend", "bing", save=False)
t = Translator(CONFIG.get)
out = t._annotate("rush b and plant", "冲B点")
print("\n_annotate 输出:", out)
for probe in ["rush=快冲", "rush b=", "plant="]:
    print(f"  含 {probe!r}: {probe in out}")