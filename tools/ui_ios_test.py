"""验证 iOS 圆角风格界面能正常构建。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import ui_theme as ui
from valotalk.app import App

app = App()
app._running = True
for _ in range(10):
    app.root.update()
    time.sleep(0.05)

print("=== 窗口 ===")
print(f"  尺寸: {app.root.winfo_width()} x {app.root.winfo_height()}")
print(f"  背景: {app.root.cget('bg')}")

print("\n=== 关键属性是否齐全 ===")
need = ["state_lbl", "meter_lbl", "model_var", "cb_game", "cb_mic", "cb_tts",
        "cb_server", "cb_voice", "cb_style", "v_team", "v_me", "v_chat",
        "v_orig", "v_through", "v_cpu", "chk_me", "hk_vars", "hk_combos",
        "region_lbl", "backend", "e_base", "e_model", "e_key", "txt"]
missing = [n for n in need if not hasattr(app, n)]
print(f"  {'全部存在' if not missing else '缺少: ' + str(missing)}")

print("\n=== 功能验证 ===")
# 设备下拉
print(f"  游戏输出: {app.cb_game.get()[:30]!r}")
print(f"  麦克风  : {app.cb_mic.get()[:30]!r}")
print(f"  TTS输出 : {app.cb_tts.get()[:30]!r}")
# 服务器切换
app.cb_server.set("日服（日语）")
app._on_server_change()
app.root.update()
print(f"  切日服后语言: {app._get('asr.lang_teammates')}  音色: {app._get('tts.voice')}")
app.cb_server.set("港/美服（英语）")
app._on_server_change()
app.root.update()
print(f"  切回后语言: {app._get('asr.lang_teammates')}  音色: {app._get('tts.voice')}")

# 开关
app.v_team.set(False)
app._set_flag("team", False)
print(f"  开关 team -> {app.flags['team']}")
app.v_team.set(True)
app._set_flag("team", True)

# 快捷键
print(f"  快捷键值: {{k: v.get() for k, v in app.hk_vars.items()}}")

# 日志
app.log("UI 测试日志一行")
for _ in range(6):
    app.root.update()
    time.sleep(0.05)
content = app.txt.get("1.0", "end").strip()
print(f"  日志内容: {content[-40:]!r}")

print("\n=== 圆角图缓存 ===")
print(f"  {len(ui._img_cache)} 张")

app.shutdown()
print("\nOK")