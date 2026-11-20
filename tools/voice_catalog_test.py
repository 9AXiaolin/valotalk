"""验证 47 音色目录 + 风格预设 + pitch 生效。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import (LABEL_BY_VOICE, STYLE_PRESETS, VOICE_BY_LABEL,
                          VOICE_CATALOG, App)

print(f"音色目录 {len(VOICE_CATALOG)} 个\n")
by_locale: dict[str, int] = {}
for short, label in VOICE_CATALOG:
    loc = short.split("-")[0] + "-" + short.split("-")[1]
    by_locale[loc] = by_locale.get(loc, 0) + 1
print("按地区:")
for loc, n in sorted(by_locale.items()):
    print(f"  {loc}  {n} 个")

print("\n萝莉/御姐类候选:")
for short, label in VOICE_CATALOG:
    if any(k in label for k in ("可爱", "自信", "有表现力", "开朗")):
        print(f"  {label}")

app = App()
app._running = True
for _ in range(6):
    app.root.update()
    time.sleep(0.05)

print(f"\n下拉框里有 {len(list(app.cb_voice['values']))} 项")
print("当前音色标签:", app.cb_voice.get())
print("当前配置 voice:", app._get("tts.voice"))

print("\n=== 逐个试风格预设（只改配置，不播放）===")
for name in STYLE_PRESETS:
    app.cb_style.set(name)
    app.cb_style.event_generate("<<ComboboxSelected>>")
    app.root.update()
    print(f"  {name:10s} → voice={app._get('tts.voice'):34s} "
          f"pitch={app._get('tts.pitch'):7s} rate={app._get('tts.rate')}")

# 复位
app.cb_style.set("原声（不调）")
app.cb_style.event_generate("<<ComboboxSelected>>")
app.root.update()
print(f"\n复位后 pitch: {app._get('tts.pitch')}")

app.shutdown()