"""验证扩充后的打瓦术语库。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import terms
from valotalk.translate import (VALORANT_TERMS, VOICE_LINES, _DIRECT_EN_ZH,
                                parse_hero_damage)
from valotalk.config import CONFIG

print("=== 词库规模 ===")
print(f"  聊天缩写   {len(terms.ABBR_CHAT)} 条")
print(f"  术语/短语 {len(terms.CALLS)} 条")
print(f"  中文喊话   {len(terms.VOICE)} 条")
print(f"  合并后 VALORANT_TERMS = {len(VALORANT_TERMS)} 条")
print(f"  直出表     {len(_DIRECT_EN_ZH)} 条")

print("\n=== 缩写直出（不联网）===")
from valotalk.translate import Translator
t = Translator(CONFIG.get)
for s in ["gg", "nt", "ns", "glhf", "mb", "dc", "ggez", "afk", "wp"]:
    print(f"  {s:8s} → {t.translate(s, 'en', 'zh-CN'):16s} [{t.backend_used}]")

print("\n=== 伤害报点 ===")
for s in ["Jett 120", "Omen 1", "Raze 140", "Omen one", "wait 5"]:
    r = parse_hero_damage(s)
    print(f"  {s:12s} → {r or '（不匹配，走正常翻译）'}")

print("\n=== 中文喊话 → 英文 ===")
for s in ["给个闪", "这里封烟", "抱团", "搜角落", "别开大", "他摸包了",
          "有个绕后的", "全起", "一波冲B"]:
    print(f"  {s:10s} → {t.translate(s, 'zh', 'en'):34s} [{t.backend_used}]")

print("\n=== 术语表抽样（按分类）===")
groups = {
    "地图": ["heaven", "hell", "main", "long", "short", "mid", "flank", "ct", "site"],
    "经济": ["eco", "full save", "half buy", "full buy", "force buy", "anti-eco"],
    "战术": ["rotate", "rush b", "default", "execute", "lurk", "hold", "clear",
             "plant", "defuse", "tap", "stick it", "camp"],
}
for g, keys in groups.items():
    print(f"  [{g}] " + "  ".join(f"{k}={VALORANT_TERMS.get(k, '?')}" for k in keys))