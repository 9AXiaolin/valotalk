"""验证服务器选择：港/美服→英语，日服→日语。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import SERVER_CHOICES, App

app = App()
app._running = True
for _ in range(6):
    app.root.update()
    time.sleep(0.05)

print("=== 下拉框选项 ===")
for label, lang in SERVER_CHOICES.items():
    print(f"  {label:16s} -> asr.lang_teammates = {lang!r}")

print(f"\n当前选择: {app.cb_server.get()}")
print(f"当前配置: {app._get('asr.lang_teammates')}")

print("\n=== 切换测试 ===")
for label in SERVER_CHOICES:
    app.cb_server.set(label)
    app.cb_server.event_generate("<<ComboboxSelected>>")
    app.root.update()
    print(f"  选「{label}」 -> {app._get('asr.lang_teammates')}")

# 恢复
app.cb_server.set("港/美服（英语）")
app.cb_server.event_generate("<<ComboboxSelected>>")
app.root.update()
print(f"\n已恢复: {app._get('asr.lang_teammates')}")

print("\n=== 布局检查 ===")
w = app.root.winfo_width()
for name in ("cb_game", "cb_server", "cb_voice", "cb_style"):
    cb = getattr(app, name, None)
    if cb is not None:
        right = cb.winfo_x() + cb.winfo_width()
        print(f"  {name:10s} x={cb.winfo_x():4d} 右边缘={right:4d} "
              f"{'OK' if right < w - 10 else '溢出'}")

app.shutdown()