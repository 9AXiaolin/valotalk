"""验证三项修复：白色边框、圆角发黑、日服是否在首屏。"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

p = Path(__file__).resolve().parent.parent / "cache" / "ui_ios.png"
img = Image.open(p).convert("RGB")
w, h = img.size
px = img.load()
print(f"截图 {w}x{h}")

print("\n=== ① 圆角处（应该是 #121212 窗口背景，不是纯黑）===")
for y in (80, 120):
    row = []
    for x in range(12, 26, 2):
        r, g, b = px[x, y]
        row.append(f"#{r:02X}{g:02X}{b:02X}")
    print(f"  y={y}: " + " ".join(row))

print("\n=== ② 窗口背景色 ===")
for spot, (x, y) in {"左上": (3, 3), "右上": (w - 4, 3), "底部": (w // 2, h - 4)}.items():
    r, g, b = px[x, y]
    print(f"  {spot}: #{r:02X}{g:02X}{b:02X}")

print("\n=== ③ 左列纵向扫描（找日服下拉框位置）===")
# 左列 x 大约 20~490
for y in range(60, min(h, 420), 20):
    r, g, b = px[200, y]
    print(f"  y={y:3d}  #{r:02X}{g:02X}{b:02X}")

print("\n=== ④ 日志区是否可见（右下区域）===")
for y in range(h - 160, h, 24):
    r, g, b = px[w - 200, y]
    print(f"  y={y:3d}  #{r:02X}{g:02X}{b:02X}")

print("\n=== 判定 ===")
bg = px[3, 3]
print(f"  背景 #121212: {'✓' if (bg[0], bg[1], bg[2]) == (0x12, 0x12, 0x12) else '✗ ' + str(bg)}")
corner = px[16, 80]
print(f"  圆角露背景(非纯黑): {'✓' if corner[0] > 8 else '✗ 还是纯黑'}  {corner}")

# 统计亮像素总数，判断还有没有成片的边框
bright = 0
for y in range(0, h, 2):
    for x in range(0, w, 2):
        r, g, b = px[x, y]
        if r > 150 and g > 150 and b > 150:
            bright += 1
total = (h // 2) * (w // 2)
print(f"  亮像素占比: {bright / total * 100:.1f}%（主要是文字）")