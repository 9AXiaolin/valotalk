"""采集稳定性：采 12 秒，统计成功帧数 / 异常次数 / 有效样本占比。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.capture import _to_mono, com_initialize, find_loopback  # noqa: E402

SR = 48000
DEV = "扬声器 (MCHOSE V9 PRO)"
SECS = 12


def run(blocksize: int) -> None:
    com_initialize()
    dev = find_loopback(DEV)
    frames = 1440
    got_frames = 0
    errors = 0
    err_msgs = {}
    t_end = time.time() + SECS
    tries = 0
    while time.time() < t_end:
        try:
            with dev.recorder(samplerate=SR, blocksize=blocksize or frames) as rec:
                while time.time() < t_end:
                    tries += 1
                    d = rec.record(numframes=frames)
                    a = _to_mono(d)
                    if a.size:
                        got_frames += a.size
        except Exception as exc:
            errors += 1
            key = f"{type(exc).__name__}: {exc}"
            err_msgs[key] = err_msgs.get(key, 0) + 1
            time.sleep(0.15)
    real = got_frames / SR
    print(f"  blocksize={blocksize or 'auto'}  尝试 {tries} 次  异常 {errors} 次  "
          f"有效音频 {real:.1f}s / {SECS}s = {real/SECS*100:.0f}%", flush=True)
    for k, v in err_msgs.items():
        print(f"      x{v} {k[:90]}", flush=True)


print("[采集稳定性]")
run(0)      # 交给 soundcard 自己定
run(1440)   # 固定 30ms
run(4800)   # 固定 100ms