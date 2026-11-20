"""给新界面截图，方便先看效果再启动。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App

app = App()
app._running = True
for _ in range(14):
    app.root.update()
    time.sleep(0.06)

# 塞几条字幕进日志区，看起来更真实
app.log("设备：8 个输出 / 7 个输入")
app.log("断句: Silero VAD（只把人声送去做识别）")
app.log("[模型] 就绪（cuda / float16）")
app.log("采集队友语音：扬声器 (MCHOSE V9 PRO)")
app.log("队友：Enemy one tap on A site, watch the flank. → 敌人在包点一枪头，注意绕后")
app.log("队友：they are rotating to B → 他们正在转点去B包点")
app.log("我：掩护我，我要开大了 → Cover me, I'm ulting!")
for _ in range(10):
    app.root.update()
    time.sleep(0.06)

out = Path(__file__).resolve().parent.parent / "cache" / "ui_ios.png"
out.parent.mkdir(exist_ok=True)

try:
    import mss
    import numpy as np
    from PIL import Image

    factory = getattr(mss, "MSS", None) or mss.mss
    x, y = app.root.winfo_rootx(), app.root.winfo_rooty()
    w, h = app.root.winfo_width(), app.root.winfo_height()
    pad = 10                                  # 往外扩一点，能看到窗口圆角
    with factory() as sct:
        shot = sct.grab({"left": x - pad, "top": y - pad,
                         "width": w + pad * 2, "height": h + pad * 2})
        arr = np.asarray(shot)[:, :, :3][:, :, ::-1]
    Image.fromarray(arr).save(out)
    print(f"截图已保存: {out}")
    print(f"  窗口 {w} x {h}（截图含 {pad}px 外边距，可看圆角）")
except Exception as exc:
    print("截图失败:", type(exc).__name__, exc)

print(f"圆角图缓存: {len(__import__('valotalk.ui_theme', fromlist=['_img_cache'])._img_cache)} 张")
app.shutdown()