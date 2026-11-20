"""验证按钮四角不再露出更暗的颜色。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import ui_theme as ui
from valotalk.app import App

app = App()
app._running = True
for _ in range(12):
    app.root.update()
    time.sleep(0.06)

print("=== 检查所有 Canvas 控件的背景色 vs 父容器背景色 ===\n")


def describe(w, depth=0):
    """遍历，找出 Canvas 的 bg 和父容器 bg 不一致的。"""
    issues = []
    for c in w.winfo_children():
        try:
            cls = c.winfo_class()
            if cls == "Canvas":
                cb = str(c.cget("bg")).lower()
                try:
                    pb = str(c.master.cget("bg")).lower()
                except Exception:
                    pb = "?"
                if pb != "?" and cb != pb:
                    txt = ""
                    if hasattr(c, "_text"):
                        txt = f' "{c._text}"'
                    issues.append((cb, pb, txt))
        except Exception:
            pass
        issues.extend(describe(c, depth + 1))
    return issues


bad = describe(app.root)
print(f"背景色不一致的 Canvas: {len(bad)} 个")
for cb, pb, txt in bad[:12]:
    print(f"  Canvas={cb}  父={pb}{txt}")
if not bad:
    print("  ✓ 全部一致，圆角处不会再露暗色")

print("\n=== 按钮四角像素抽样 ===")
try:
    import mss
    import numpy as np
    from PIL import Image

    factory = getattr(mss, "MSS", None) or mss.mss
    x = app.root.winfo_rootx()
    y = app.root.winfo_rooty()
    w = app.root.winfo_width()
    h = app.root.winfo_height()
    with factory() as sct:
        shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
        arr = np.asarray(shot)[:, :, :3][:, :, ::-1]
    img = Image.fromarray(arr)

    # 找「保存」按钮并检查它四角
    target = None


    def find(wd):
        global target
        for c in wd.winfo_children():
            if c.winfo_class() == "Canvas" and hasattr(c, "_text"):
                if "保存" in str(c._text):
                    target = c
            find(c)


    find(app.root)
    if target:
        bx = target.winfo_rootx() - x
        by = target.winfo_rooty() - y
        bw = target.winfo_width()
        bh = target.winfo_height()
        px = img.load()
        print(f"  保存按钮 ({bx},{by}) {bw}x{bh}")
        for name, (cx, cy) in {
            "左上角": (bx, by),
            "右上角": (bx + bw - 1, by),
            "左下角": (bx, by + bh - 1),
            "右下角": (bx + bw - 1, by + bh - 1),
            "中心": (bx + bw // 2, by + bh // 2),
        }.items():
            r, g, b = px[cx, cy]
            print(f"    {name}: #{r:02X}{g:02X}{b:02X}")
    else:
        print("  没找到保存按钮")
except Exception as exc:
    print("  截图失败:", type(exc).__name__, exc)

app.shutdown()