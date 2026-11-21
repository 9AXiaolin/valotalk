"""布局检查：LLM 三个输入框 + 标签是否超出卡片/窗口边界。"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from valotalk.app import App

app = App()
app._running = True
for _ in range(20):
    app.root.update(); time.sleep(0.05)

RX, RY = app.root.winfo_rootx(), app.root.winfo_rooty()
RW, RH = app.root.winfo_width(), app.root.winfo_height()

def rel(w):
    return (w.winfo_rootx()-RX, w.winfo_rooty()-RY, w.winfo_width(), w.winfo_height())

print("=== 三个输入框位置 ===")
for name, attr in [('e_base','e_base'), ('e_model','e_model'), ('e_key','e_key')]:
    x, y, w, h = rel(getattr(app, attr))
    tag = "OK" if x+w <= RW else "OVERFLOW"
    print(f"  {name:8s} x={x:4d} y={y:3d} w={w:3d} h={h:2d}  right={x+w:4d}/{RW}  {tag}")

body = app.e_base.master.master
bx, by, bw, bh = rel(body)
print(f"\nLLM card body: x={bx} y={by} w={bw} h={bh}")
bad = 0
for ch in body.winfo_children():
    x, y, w, h = rel(ch)
    if not ch.winfo_ismapped():
        continue
    inside = (x >= bx-1 and y >= by-1 and x+w <= bx+bw+1 and y+h <= by+bh+1)
    if not inside:
        print(f"  CLIPPED {ch.winfo_class()} {rel(ch)}")
        bad += 1
print(f"clipped={bad}")

lb = app.txt.winfo_rooty()-RY + app.txt.winfo_height()
print(f"\nlog h={app.txt.winfo_height()}  bottom={lb}/{RH}")
app.shutdown()
