"""测通义千问 OpenAI 兼容模式是否支持 cache_control，以及 DeepSeek 的缓存字段。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG

base = (CONFIG.get("translate.llm.base_url", "") or "").rstrip("/")
key = CONFIG.get("translate.llm.api_key", "")
model = CONFIG.get("translate.llm.model", "")
print(f"base_url = {base}")
print(f"model    = {model}")
print(f"key      = {key[:6]}...{key[-4:] if len(key) > 10 else ''}（长度 {len(key)}）\n")

if not base or not key:
    print("没配置 LLM，跳过")
    sys.exit(0)

SYS = "你是《无畏契约》队内翻译。只输出译文。" + "测试填充" * 40
s = requests.Session()
s.proxies.update({})
H = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def call(label: str, payload: dict) -> dict | None:
    try:
        r = s.post(base + "/chat/completions", headers=H,
                   data=json.dumps(payload), timeout=30)
        print(f"=== {label} ===")
        print(f"  HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"  响应: {r.text[:300]}")
            return None
        data = r.json()
        usage = data.get("usage", {})
        print(f"  usage: {json.dumps(usage, ensure_ascii=False)}")
        msg = data["choices"][0]["message"]["content"]
        print(f"  译文: {msg[:60]!r}")
        return data
    except Exception as exc:
        print(f"=== {label} ===\n  异常: {type(exc).__name__} {exc}")
        return None


# ① 基线：普通字符串 system
call("① 普通 system（基线）", {
    "model": model, "temperature": 0.1, "max_tokens": 64,
    "messages": [
        {"role": "system", "content": SYS},
        {"role": "user", "content": "翻译成中文：Rush B"},
    ],
})

# ② system 用 content 数组 + cache_control
call("② system 加 cache_control", {
    "model": model, "temperature": 0.1, "max_tokens": 64,
    "messages": [
        {"role": "system", "content": [
            {"type": "text", "text": SYS, "cache_control": {"type": "ephemeral"}}
        ]},
        {"role": "user", "content": "翻译成中文：Rush B"},
    ],
})

# ③ 再打一次同样的（看能不能命中缓存）
call("③ 重复请求（看缓存命中）", {
    "model": model, "temperature": 0.1, "max_tokens": 64,
    "messages": [
        {"role": "system", "content": [
            {"type": "text", "text": SYS, "cache_control": {"type": "ephemeral"}}
        ]},
        {"role": "user", "content": "翻译成中文：Rush B"},
    ],
})