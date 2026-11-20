"""用真实的 _LLM_SYSTEM 测缓存命中，连打 4 次看 cached_tokens 变化。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.translate import _LLM_SYSTEM

base = (CONFIG.get("translate.llm.base_url", "") or "").rstrip("/")
key = CONFIG.get("translate.llm.api_key", "")
model = CONFIG.get("translate.llm.model", "")

print(f"真实 system prompt: {len(_LLM_SYSTEM)} 字符")
print(f"（中文约 1 字符 ≈ 1.5 tokens，估计 {int(len(_LLM_SYSTEM) * 1.4)} tokens）\n")

s = requests.Session()
s.proxies.update({})
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def call(tag: str, use_cache: bool, user_text: str) -> None:
    # content 必须是字符串或「对象数组」，单个对象会 400
    sys_msg = ([{"type": "text", "text": _LLM_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}]
               if use_cache else _LLM_SYSTEM)
    payload = {
        "model": model, "temperature": 0.1, "max_tokens": 64,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": f"把这句英文翻译成中文：{user_text}"},
        ],
    }
    t0 = time.time()
    r = s.post(base + "/chat/completions", headers=H,
               data=json.dumps(payload), timeout=30)
    dt = (time.time() - t0) * 1000
    if r.status_code != 200:
        print(f"  {tag}: HTTP {r.status_code} {r.text[:150]}")
        return
    u = r.json().get("usage", {})
    det = u.get("prompt_tokens_details", {}) or {}
    cached = det.get("cached_tokens", 0)
    created = det.get("cache_creation_input_tokens", 0)
    print(f"  {tag:22s} prompt={u.get('prompt_tokens'):4d}  "
          f"cached={cached:4d}  created={created:4d}  {dt:.0f}ms")


print("=== 不带 cache_control（基线）===")
call("第1次", False, "Rush B, plant the spike")
call("第2次", False, "Rush B, plant the spike")

print("\n=== 带 cache_control（连打 4 次）===")
call("第1次", True, "Rush B, plant the spike")
time.sleep(0.5)
call("第2次", True, "they are rotating to A")
time.sleep(0.5)
call("第3次", True, "one enemy remaining mid")
time.sleep(0.5)
call("第4次", True, "nice shot, watch the flank")

print("\n说明：")
print("  cached > 0    = 命中缓存，这部分 token 按低价计费")
print("  created > 0   = 这次把 prompt 写入了缓存")
print("  两个都是 0    = 没缓存（prompt 太短，或该模型不支持）")