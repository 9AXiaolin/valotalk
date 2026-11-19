"""测 whisper 推理瞬间对 GPU 的抢占程度（走 valotalk 的加载路径，含 DLL 注入）。"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import asr as A  # noqa: E402
from valotalk.config import CONFIG  # noqa: E402


def gpu() -> tuple[int, int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        m, u = out.split(",")
        return int(m), int(u)
    except Exception:
        return -1, -1


def monitor(stop: threading.Event, samples: list) -> None:
    while not stop.is_set():
        samples.append(gpu())
        time.sleep(0.05)


def main() -> None:
    print("CUDA DLL 已注入:", A.CUDA_DLL_DIRS)
    print("初始 GPU:", gpu())

    t0 = time.time()
    model = None
    try:
        from faster_whisper import WhisperModel
        size = CONFIG.get("asr.model", "small")
        model = WhisperModel(size, device="cuda", compute_type="float16",
                             download_root=str(Path("models")), num_workers=1,
                             cpu_threads=2)
        print(f"加载 {size} 用时 {time.time()-t0:.1f}s  显存 → {gpu()[0]} MiB")
    except Exception as exc:
        print("加载失败:", str(exc)[:200])
        return

    audio = (0.1 * np.sin(np.arange(16000 * 3, dtype=np.float32) * 0.05))
    list(model.transcribe(audio, language="en", beam_size=1)[0])   # 预热

    print("\n=== 单次推理（3 秒音频）期间的 GPU 采样 ===")
    for i in range(3):
        samples: list = []
        stop = threading.Event()
        th = threading.Thread(target=monitor, args=(stop, samples), daemon=True)
        th.start()
        t0 = time.perf_counter()
        list(model.transcribe(audio, language="en", beam_size=1, vad_filter=False)[0])
        dt = (time.perf_counter() - t0) * 1000
        time.sleep(0.15)
        stop.set()
        th.join(timeout=2)
        utils = [u for _m, u in samples if u >= 0]
        print(f"  #{i+1} 推理 {dt:.0f}ms  GPU 利用率峰值 {max(utils) if utils else '?'}%  "
              f"采样 {utils}")
        time.sleep(0.3)

    print("\n=== 连续 6 次推理（模拟队友连续说话）===")
    samples = []
    stop = threading.Event()
    th = threading.Thread(target=monitor, args=(stop, samples), daemon=True)
    th.start()
    t0 = time.perf_counter()
    for _ in range(6):
        list(model.transcribe(audio, language="en", beam_size=1, vad_filter=False)[0])
    total = (time.perf_counter() - t0) * 1000
    stop.set()
    th.join(timeout=2)
    utils = [u for _m, u in samples if u >= 0]
    busy = sum(1 for u in utils if u > 80)
    print(f"  总耗时 {total:.0f}ms，其中 GPU>80% 的采样 {busy}/{len(utils)} "
          f"= {busy/max(1,len(utils))*100:.0f}% 的时间显卡被占满")
    print(f"  峰值显存 {max(m for m, _u in samples if m >= 0)} MiB")


if __name__ == "__main__":
    main()