"""验证紧凑键盘上实际存在的键都能绑定为触发键。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi
from valotalk.app import App

app = App()
app._running = True
for _ in range(6):
    app.root.update()
    time.sleep(0.05)

# 68 键键盘上确实存在的键
AVAILABLE = ["PAGEUP", "PAGEDOWN", "INSERT", "DELETE", "CAPSLOCK", "TAB", "`"]
# 68 键键盘上没有独立键的
MISSING = ["F1", "F2", "HOME", "END"]

print("=== 紧凑键盘上有的键（应能绑定）===")
for k in AVAILABLE:
    app.hk_vars["ptt"].set(k)
    app._apply_hotkeys()
    app.root.update()
    vk = app.hotkeys._bindings.get("ptt")
    print(f"  {'✓' if vk else '✗'} {k:10s} VK={f'0x{vk:02X}' if vk else '未绑定'}")

print("\n=== 紧凑键盘上可能没有的键（能绑但当心按不到）===")
for k in MISSING:
    app.hk_vars["ptt"].set(k)
    app._apply_hotkeys()
    app.root.update()
    vk = app.hotkeys._bindings.get("ptt")
    print(f"  {'能绑定' if vk else '失败'} {k:10s} VK={f'0x{vk:02X}' if vk else '-'}")

# 恢复
app.hk_vars["ptt"].set("F2")
app._apply_hotkeys()
app.root.update()
print(f"\n已恢复 ptt = {app._get('hotkeys.ptt')}")
app.shutdown()