"""扫描截图里的白色线条，定位是哪个控件画的边。"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

p = Path(__file__).resolve().parent.parent / "cache" / "ui_ios.png"
img = Image.open(p).convert("RGB")
w, h = img.size
px = img.load()
print(f"截图 {w}x{h}")

# 找亮色像素（>150）聚成行/列
rows: dict[int, int] = {}
cols: dict[int, int] = {}
for y in range(h):
    for x in range(w):
        r, g, b = px[x, y]
        if r > 150 and g > 150 and b > 150:
            rows[y] = rows.get(y, 0) + 1
            cols[x] = cols.get(x, 0) + 1

print("\n=== 亮色像素最多的水平行 ===")
for y, n in sorted(rows.items(), key=lambda kv: -kv[1])[:8]:
    print(f"  y={y:4d}  {n:4d} 个亮像素")

print("\n=== 亮色像素最多的垂直列 ===")
for x, n in sorted(cols.items(), key=lambda kv: -kv[1])[:8]:
    print(f"  x={x:4d}  {n:4d} 个亮像素")

# 检查典型边框位置：卡片边缘
print("\n=== 卡片边缘取色（x=18 是第一张卡片左边缘）===")
for y in (90, 120, 160, 200):
    row = []
    for x in range(14, 30, 2):
        r, g, b = px[x, y]
        row.append(f"#{r:02X}{g:02X}{b:02X}")
    print(f"  y={y:3d}: " + " ".join(row))

print("\n=== 下拉框边框（第一张卡片内，y≈118）===")
for y in (112, 116, 120):
    row = []
    for x in (150, 200, 250, 300, 350):
        r, g, b = px[x, y]
        row.append(f"#{r:02X}{g:02X}{b:02X}")
    print(f"  y={y}: " + " ".join(row))