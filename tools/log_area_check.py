"""查日志区那个暗红色是什么。"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

p = Path(__file__).resolve().parent.parent / "cache" / "ui_ios.png"
img = Image.open(p).convert("RGB")
w, h = img.size
px = img.load()

print("=== 日志区纵向扫描 (x=60) ===")
for y in range(h - 200, h, 12):
    r, g, b = px[60, y]
    tag = ""
    if r > 100 and r > b + 40:
        tag = "  ← 偏红"
    print(f"  y={y:4d}  #{r:02X}{g:02X}{b:02X}{tag}")

print("\n=== 横向扫描 (y=780) ===")
for x in range(20, 500, 40):
    r, g, b = px[x, 780]
    print(f"  x={x:4d}  #{r:02X}{g:02X}{b:02X}")

print("\n=== 日志卡片背景应该是什么 ===")
import tkinter as tk
print("  CARD2 = #2C2C2E（日志框背景）")
print("  TEXT2 = #98989F（日志文字）")
print("  RED   = #FF453A（只用在状态灯）")

# 统计日志区域颜色
from collections import Counter
region = img.crop((30, h - 180, w - 40, h - 20))
cnt = Counter(region.convert("RGB").getdata() if hasattr(region, "getdata")
              else region.getdata())
print("\n=== 日志区域前 8 种颜色 ===")
for color, n in cnt.most_common(8):
    r, g, b = color
    flag = "  ← 红" if r > 100 and r > b + 40 else ""
    print(f"  #{r:02X}{g:02X}{b:02X}  {n:5d}{flag}")