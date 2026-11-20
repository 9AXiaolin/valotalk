"""验证包点 A/B/C 的识别与翻译。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import valotalk.terms as T
from valotalk.config import CONFIG
from valotalk.translate import Translator

print("=== ABBR_CHAT 包点条目 ===")
for k in ["a", "b", "c", "asite", "bsite", "csite",
          "ona", "onb", "onc", "goa", "gob", "goc"]:
    print(f"  {k:8s} -> {T.ABBR_CHAT.get(k)}")

t = Translator(CONFIG.get)

print("\n=== 英→中 直出（不联网）===")
for s in ["A", "a", "B", "b", "C", "c",
          "A site", "B site", "C site",
          "on A", "at B", "go C"]:
    out = t.translate(s, "en", "zh-CN")
    print(f"  {s!r:10s} -> {out!r:14s} [{t.backend_used}]")

print("\n=== 长句里带包点（走机翻 + 追注）===")
for s in ["two enemies on A site", "they are rotating to C"]:
    print(f"  {s:32s} -> {t.translate(s, 'en', 'zh-CN')}")

print("\n=== 中→英 包点喊话 ===")
for zh in ["A包", "B包", "C包", "A包点", "去A"]:
    en = t.translate(zh, "zh", "en")
    print(f"  {zh:8s} -> {en!r:24s} [{t.backend_used}]")