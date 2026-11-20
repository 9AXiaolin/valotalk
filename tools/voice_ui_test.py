"""验证音色选择器 UI 与配置写回。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import VOICE_CHOICES, App

app = App()
app._running = True
for _ in range(6):
    app.root.update()
    time.sleep(0.05)

print("音色下拉框存在:", hasattr(app, "cb_voice"))
vals = list(app.cb_voice["values"])
print(f"可选音色 {len(vals)} 个:")
for v in vals:
    print("   ", v)

print("\n当前值:", app.cb_voice.get())
print("配置里的 tts.voice:", app._get("tts.voice"))

# 切一个音色（不点试听，避免真的出声）
app.cb_voice.set("en-US-AndrewNeural")
app.cb_voice.event_generate("<<ComboboxSelected>>")
app.root.update()
print("\n切换后配置:", app._get("tts.voice"))
print("试听方法存在:", hasattr(app, "_preview_voice"))

# 改回默认
app.cb_voice.set("en-US-GuyNeural")
app.cb_voice.event_generate("<<ComboboxSelected>>")
app.root.update()
print("已恢复:", app._get("tts.voice"))

print("\n布局检查:")
w = app.root.winfo_width()
right = app.cb_voice.winfo_x() + app.cb_voice.winfo_width()
print(f"  面板宽 {w}，音色框右边缘 {right}，余量 {w - right}px")

app.shutdown()