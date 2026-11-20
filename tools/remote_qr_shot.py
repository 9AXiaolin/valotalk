"""截图：主界面的"手机"行 + 扫码弹窗。

跑法：D:\\python\\python.exe -X utf8 tools\\remote_qr_shot.py
产出：cache/ui_remote.png / cache/ui_remote_qr.png
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.app import App  # noqa: E402

OUT = ROOT / "cache"


def pump(app, n=14, gap=0.06):
    for _ in range(n):
        app.root.update()
        time.sleep(gap)


def shot(win, path: Path, pad=10):
    import mss
    import numpy as np
    from PIL import Image

    factory = getattr(mss, "MSS", None) or mss.mss
    win.update_idletasks()
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    with factory() as sct:
        g = sct.grab({"left": x - pad, "top": y - pad,
                      "width": w + pad * 2, "height": h + pad * 2})
        arr = np.asarray(g)[:, :, :3][:, :, ::-1]
    Image.fromarray(arr).save(path)
    print(f"  已保存 {path.name}  ({w}x{h})")


def main():
    app = App()
    app._running = True
    pump(app, 20, 0.08)

    OUT.mkdir(exist_ok=True)
    app.log("[手机] 遥控已开启：10.0.0.12:8765")
    pump(app, 6)
    shot(app.root, OUT / "ui_remote.png")

    # 二维码弹窗
    app._show_remote_qr()
    pump(app, 10, 0.1)
    tops = [w for w in app.root.winfo_children()
            if w.winfo_class() == "Toplevel" and "手机" in w.title()]
    if tops:
        shot(tops[0], OUT / "ui_remote_qr.png")
        for t in tops:
            t.destroy()
    else:
        print("  没找到二维码窗口")

    app.shutdown()


if __name__ == "__main__":
    main()
