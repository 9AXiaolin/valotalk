"""验证日语战术术语翻译。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.translate import Translator

t = Translator(CONFIG.get)
cases = [
    ("Aサイトに敵、フランクに注意。", "侧翼/绕后"),
    ("Bサイトにスパイク設置", "下包"),
    ("敵が一人残り、ローテート中", "剩余/转点"),
    ("味方がエコー中", "经济局"),
    ("敵が上にいる", "高处"),
]
for ja, expect in cases:
    out = t.translate(ja, "ja", "zh-CN")
    ok = "?" if not out else ("✓" if expect.split("/")[0] in out or
                              any(x in out for x in expect.split("/")) else "?")
    print(f"  {ja}")
    print(f"    -> {out}   ({ok} 期望含「{expect}」)")
    print()