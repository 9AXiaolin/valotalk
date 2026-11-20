"""用像素分析验证截图渲染是否正确（圆角、配色、卡片）。"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PIL import Image

p = Path(__file__).resolve().parent.parent / "cache" / "ui_ios.png"
img = Image.open(p).convert("RGB")
w, h = img.size
print(f"截图 {w} x {h}")

px = img.load()


def hexat(x, y):
    r, g, b = px[x, y]
    return f"#{r:02X}{g:02X}{b:02X}"


print("\n=== 关键位置取色 ===")
spots = {
    "左上角(窗口背景)": (2, 2),
    "右上角": (w - 3, 2),
    "标题文字区": (30, 24),
    "第一张卡片内": (60, 120),
    "卡片外的间隙": (w // 2, 100),
    "日志区": (60, h - 120),
}
for name, (x, y) in spots.items():
    print(f"  {name:16s} ({x:4d},{y:4d}) = {hexat(x, y)}")

print("\n=== 出现最多的 6 种颜色 ===")
small = img.resize((w // 2, h // 2))
cnt = Counter(small.getdata())
for color, n in cnt.most_common(6):
    r, g, b = color
    print(f"  #{r:02X}{g:02X}{b:02X}  {n:6d} 像素  ({n / (small.size[0] * small.size[1]) * 100:.1f}%)")

print("\n=== 圆角检测（找第一张卡片的左上圆角）===")
# 卡片大致从 (18, 76) 开始，宽约 884
cx, cy = 18, 76
print(f"  卡片左上角附近:")
for dy in range(0, 14, 2):
    row = []
    for dx in range(0, 14, 2):
        row.append(hexat(cx + dx, cy + dy))
    print(f"    y+{dy:2d}: " + " ".join(row))

print("\n=== 判定 ===")
bg_ok = hexat(2, 2) == "#000000"
print(f"  背景纯黑: {'✓' if bg_ok else '✗ ' + hexat(2, 2)}")
card = px[60, 120]
is_card = card[0] < 40 and abs(card[0] - card[1]) < 6
print(f"  卡片是深灰: {'✓' if is_card else '✗'} ({hexat(60, 120)})")
# 圆角处应有背景色混入（不是硬直角）
corner = px[cx, cy]
corner_is_bg = corner[0] < 12
print(f"  圆角处露出背景: {'✓' if corner_is_bg else '✗ 直角没倒角'} ({hexat(cx, cy)})")