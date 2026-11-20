"""验证加了 prompt caching 后翻译仍正常，并且能看到缓存命中。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.translate import Translator

print("=== 配置 ===")
print(f"  backend      = {CONFIG.get('translate.backend')}")
print(f"  model        = {CONFIG.get('translate.llm.model')}")
print(f"  prompt_cache = {CONFIG.get('translate.llm.prompt_cache', '(未设置，默认 True)')}")

t = Translator(CONFIG.get)
cases = [
    ("en", "zh-CN", "Enemy one tap on A site, watch the flank."),
    ("en", "zh-CN", "they are rotating to B, stack mid"),
    ("en", "zh-CN", "Rush B, plant the spike behind the box."),
    ("zh", "en", "掩护我，我要开大了"),
]
print("\n=== 翻译 + 缓存命中 ===")
for i, (src, dst, text) in enumerate(cases, 1):
    t0 = time.time()
    out = t.translate(text, src, dst)
    dt = (time.time() - t0) * 1000
    u = t.last_usage or {}
    det = u.get("prompt_tokens_details") or {}
    cached = det.get("cached_tokens", 0)
    pt = u.get("prompt_tokens", 0)
    pct = (cached / pt * 100) if pt else 0
    print(f"  #{i} [{dt:5.0f}ms] {text[:34]}")
    print(f"       -> {out}")
    print(f"      prompt={pt} cached={cached} ({pct:.0f}%)  [{t.backend_used}]")

print("\n=== 关闭 caching 对比 ===")
CONFIG.set("translate.llm.prompt_cache", False, save=False)
t2 = Translator(CONFIG.get)
t2.translate("Enemy one tap on A site", "en", "zh-CN")   # 预热
t0 = time.time()
t2.translate("Rush B, plant the spike", "en", "zh-CN")
dt = (time.time() - t0) * 1000
u = t2.last_usage or {}
det = u.get("prompt_tokens_details") or {}
print(f"  关闭后: prompt={u.get('prompt_tokens')} "
      f"cached={det.get('cached_tokens', 0)}  {dt:.0f}ms")

CONFIG.set("translate.llm.prompt_cache", True, save=True)
print("\n已恢复 prompt_cache = True")