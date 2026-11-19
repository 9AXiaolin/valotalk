"""分发链路端到端：直接喂 Job 给 _dispatch，验证 识别后 → 翻译 → 字幕/日志/TTS 全通。

这一段之前没有覆盖，导致 self._log 这种错别字直到用户实跑才暴露。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App, Job  # noqa: E402

fails = 0


def ok(cond: bool, name: str, extra: str = "") -> None:
    global fails
    if cond:
        print("  [PASS] " + name + (f"  {extra}" if extra else ""))
    else:
        fails += 1
        print("  [FAIL] " + name + (f"  {extra}" if extra else ""))


def main() -> None:
    app = App()
    app._running = True                     # 不启动采集/模型
    app.flags = {"team": True, "me": True, "chat": True}

    # TTS 不真播（避免往虚拟麦克风灌声音）
    spoken = []
    app.tts.speak = lambda t: (spoken.append(t), True)[1]

    print("\n[1] 队友语音：英文 → 中文 → 字幕")
    n0 = len(app.log_lines)
    app._dispatch(Job(kind="teammates", text="Rush B, plant the spike behind the box."))
    app.root.update()
    added = app.log_lines[n0:]
    ok(len(added) >= 1, "产生日志", added[-1][:70] if added else "(无)")
    ok(any("队友" in l for l in added), "日志含『队友』")
    ok(len(app.overlay.items) >= 1, "字幕有条目", f"{len(app.overlay.items)} 条")
    if app.overlay.items:
        it = app.overlay.items[-1]
        ok(it.tag == "队友", "标签正确", it.tag)
        ok(bool(it.text) and "Rush" not in it.text, "已译成中文", it.text[:40])

    print("\n[2] 聊天：英文 → 中文")
    app._dispatch(Job(kind="chat", text="gg wp nice shot"))
    app.root.update()
    added = app.log_lines[n0:]
    ok(any("聊天" in l for l in added), "日志含『聊天』")
    ok(app.overlay.items and app.overlay.items[-1].tag == "聊天", "字幕标签=聊天")

    print("\n[3] 我说中文：中文 → 英文 → 触发 TTS")
    app._dispatch(Job(kind="me", text="掩护我，我要开大了"))
    app.root.update()
    added = app.log_lines[n0:]
    ok(any("我：" in l for l in added), "日志含『我：』")
    ok(len(spoken) >= 1, "TTS 被调用", spoken[-1][:60] if spoken else "(没调用)")
    if spoken:
        ok(not any("\u4e00" <= c <= "\u9fff" for c in spoken[-1]),
           "TTS 内容是英文", spoken[-1][:60])
    ok(app.overlay.items and app.overlay.items[-1].tag == "我", "字幕标签=我")

    print("\n[4] 关闭开关后不应再处理")
    app.flags["team"] = False
    m = len(app.overlay.items)
    app._dispatch(Job(kind="teammates", text="they are rotating A"))
    app.root.update()
    ok(len(app.overlay.items) == m, "关掉后不再冒出字幕")

    print("\n[5] 字幕窗几何")
    app.overlay.reset_position()
    app.root.update()
    sw, sh = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
    x, y, w, h = app.overlay.x, app.overlay.y, app.overlay.width, app.overlay.height
    ok(abs(x - (sw - w) // 2) <= 2, "水平居中", f"x={x} 屏宽={sw} 窗宽={w}")
    ok(y + h >= sh - 140, "贴近屏幕下方", f"y={y} h={h} 屏高={sh}")

    print(f"\n完成，失败 {fails} 项。")
    app.shutdown()
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()