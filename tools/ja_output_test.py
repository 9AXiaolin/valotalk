"""验证日服模式：我说中文 → 日语文本 → 日语 TTS。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App
from valotalk.config import CONFIG
from valotalk.translate import Translator

print("=== 翻译层：中文 → 日语 ===")
t = Translator(CONFIG.get)
for zh in ["掩护我", "我开大了", "一波冲B", "他残血", "转点",
           "我要去拆包，掩护我", "对面在打B点，小心绕后"]:
    out = t.translate(zh, "zh", "ja")
    print(f"  {zh:22s} -> {out}   [{t.backend_used}]")

print("\n=== 对比：同样的话翻成英文 ===")
for zh in ["掩护我", "我开大了", "一波冲B"]:
    print(f"  {zh:12s} -> {t.translate(zh, 'zh', 'en')}")

print("\n=== 界面：切换服务器看音色是否跟着换 ===")
app = App()
app._running = True
for _ in range(6):
    app.root.update()
    time.sleep(0.05)

print(f"  初始: 服务器={app.cb_server.get()}  音色={app._get('tts.voice')}")
print(f"        下拉框有 {len(list(app.cb_voice['values']))} 个音色")

app.cb_server.set("日服（日语）")
app.cb_server.event_generate("<<ComboboxSelected>>")
app.root.update()
vals = list(app.cb_voice["values"])
print(f"  切日服: 语言={app._get('asr.lang_teammates')}  音色={app._get('tts.voice')}")
print(f"        下拉框 {len(vals)} 个: {vals}")

app.cb_server.set("港/美服（英语）")
app.cb_server.event_generate("<<ComboboxSelected>>")
app.root.update()
vals = list(app.cb_voice["values"])
print(f"  切回美服: 语言={app._get('asr.lang_teammates')}  音色={app._get('tts.voice')}")
print(f"        下拉框 {len(vals)} 个")

app.shutdown()