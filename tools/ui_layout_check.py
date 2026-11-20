"""验证：窗口圆角、LLM 保存按钮可见、各控件不超出窗口。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App

app = App()
app._running = True
for _ in range(12):
    app.root.update()
    time.sleep(0.06)

W = app.root.winfo_width()
H = app.root.winfo_height()
print(f"窗口: {W} x {H}\n")

print("=== ① 控件是否超出右边界 ===")
def check(widget, name):
    try:
        right = widget.winfo_rootx() - app.root.winfo_rootx() + widget.winfo_width()
        ok = right <= W
        print(f"  {'✓' if ok else '✗ 超出'} {name:12s} 右边缘={right:4d} / {W}")
        return ok
    except Exception as exc:
        print(f"  ? {name}: {exc}")
        return False

check(app.e_base, "base_url")
check(app.e_model, "model")
check(app.e_key, "api_key")
for name in ("cb_voice", "cb_server", "cb_game", "cb_tts"):
    check(getattr(app, name), name)

print("\n=== ② 保存按钮是否存在且可见 ===")
found = []
def walk(w):
    for c in w.winfo_children():
        try:
            if c.winfo_class() == "Canvas" and hasattr(c, "_text"):
                if "保存" in str(c._text):
                    found.append(c)
        except Exception:
            pass
        walk(c)
walk(app.root)
print(f"  找到 {len(found)} 个「保存」按钮")
if found:
    b = found[0]
    x = b.winfo_rootx() - app.root.winfo_rootx()
    y = b.winfo_rooty() - app.root.winfo_rooty()
    print(f"  位置: ({x}, {y})  尺寸 {b.winfo_width()}x{b.winfo_height()}")
    print(f"  在窗口内: {'✓' if x + b.winfo_width() <= W and y + b.winfo_height() <= H else '✗'}")

print("\n=== ③ 窗口圆角 API ===")
from valotalk import winapi
hwnd = winapi.top_level_hwnd(app.root)
print(f"  hwnd = {hwnd}")
print(f"  DwmSetWindowAttribute 圆角: {'生效' if winapi.set_rounded_window(hwnd, 2) else '不支持'}")

print("\n=== ④ 关键属性 ===")
need = ["state_lbl", "meter_lbl", "model_var", "cb_game", "cb_mic", "cb_tts",
        "cb_server", "cb_voice", "cb_style", "v_team", "v_me", "v_chat",
        "v_orig", "v_through", "v_cpu", "chk_me", "hk_vars", "hk_combos",
        "region_lbl", "backend", "e_base", "e_model", "e_key", "txt"]
missing = [n for n in need if not hasattr(app, n)]
print(f"  {'全部存在' if not missing else '缺少: ' + str(missing)}")

app.shutdown()
print("\nOK")