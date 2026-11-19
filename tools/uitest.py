"""界面冒烟测试：建面板 + 字幕窗 → 塞几条示例 → 截图 → 退出。

跑法： python tools/uitest.py
产出： cache/ui_shot.png（看一眼字幕排版对不对）
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App  # noqa: E402


def main() -> None:
    app = App()
    app._running = True          # 阻止自动启动采集/模型，UI 测试不需要
    root = app.root
    for _ in range(6):
        root.update()
        time.sleep(0.05)

    samples = [
        ("队友", "他们在转A点，注意侧翼（rotating=在转点，flank=绕后）",
         "they are rotating to A, watch the flank"),
        ("队友", "一击，漂亮的射击。最后一个在你身后", "one tap, nice shot. last one behind you"),
        ("我", "Rotating now, cover me.", "我在转点，掩护我"),
        ("聊天", "冲B，在箱子后面放置炸弹包", "Rush B, plant the spike behind the box."),
    ]
    for tag, text, orig in samples:
        app.overlay.add(tag, text, orig)
    for _ in range(10):
        root.update()
        time.sleep(0.05)

    # 截屏看效果
    try:
        import mss
        import numpy as np
        out = Path(__file__).resolve().parent.parent / "cache" / "ui_shot.png"
        out.parent.mkdir(exist_ok=True)
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            arr = np.asarray(shot)[:, :, :3][:, :, ::-1]
        from PIL import Image
        Image.fromarray(arr).save(out)
        print("截图:", out)
    except Exception as exc:
        print("截图失败:", exc)

    print("overlay 条目数:", len(app.overlay.items))
    print("overlay 位置:", app.overlay.win.geometry())
    print("hwnd:", app.overlay._hwnd, "穿透:", app.overlay._click_through)
    print("设备:", app.cb_game.get(), "|", app.cb_mic.get(), "|", app.cb_tts.get())
    app.shutdown()
    print("OK")


if __name__ == "__main__":
    main()