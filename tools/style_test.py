"""验证：聊天过滤规则 + 字幕样式（无黑底、字号变小、有描边）。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App  # noqa: E402
from valotalk.ocr import is_player_chat  # noqa: E402

fails = 0


def ok(cond: bool, name: str, extra: str = "") -> None:
    global fails
    if cond:
        print("  [PASS] " + name + (f"  {extra}" if extra else ""))
    else:
        fails += 1
        print("  [FAIL] " + name + (f"  {extra}" if extra else ""))


def test_filter() -> None:
    print("\n[1] 聊天行过滤：玩家说话要看，系统广播要丢")
    keep = [
        "s0mebody: nice shot bro",
        "PlayerName: rush b",
        "[TAG] Player1: gg wp",
        "张三：我下包",
        "Name#1234: rotate",
        "亚索: hello",
    ]
    drop = [
        "Spike has been planted.",
        "Round 5",
        "Enemy remaining: 2",
        "PlayerName joined the party.",
        "PlayerName left the party.",
        "You have been disconnected.",
        "系统: 已进入队伍",
        "System: warning",
        "Match starting in 5 seconds",
        "",
        "gg",
    ]
    for s in keep:
        ok(is_player_chat(s), f"保留 {s!r}")
    for s in drop:
        ok(not is_player_chat(s), f"丢弃 {s!r}")


def test_style() -> None:
    print("\n[2] 字幕样式")
    app = App()
    app._running = True
    app.overlay.add("队友", "他们转B点，中路抱团", "they are rotating to B, stack mid")
    for _ in range(8):
        app.root.update()
        time.sleep(0.05)

    c = app.overlay.canvas
    items = c.find_all()
    kinds = {}
    for i in items:
        k = c.type(i)
        kinds[k] = kinds.get(k, 0) + 1

    print(f"      canvas 元素统计: {kinds}")
    ok(kinds.get("rectangle", 0) == 0, "没有黑色底板", f"rectangle={kinds.get('rectangle',0)}")
    ok(kinds.get("text", 0) >= 8, "有描边副本（≥8 层黑字）", f"text={kinds.get('text',0)}")

    sizes = []
    for i in items:
        if c.type(i) == "text":
            f = c.itemcget(i, "font")
            sizes.append(f)
    main = [f for f in sizes if "-19" in f]
    ok(bool(main), "主文字 19px", main[0] if main else str(sizes[:2]))

    print(f"      overlay.font_size={app._get('overlay.font_size')} "
          f"backdrop={app._get('overlay.backdrop')} outline={app._get('overlay.outline')}")
    ok(app._get("overlay.font_size") == 19, "字号已从 26 降到 19")
    ok(app._get("overlay.backdrop") is False, "黑底已关闭")
    app.shutdown()


if __name__ == "__main__":
    test_filter()
    test_style()
    print(f"\n完成，失败 {fails} 项。")
    sys.exit(1 if fails else 0)