"""定位掉帧元凶：分别测量两个会碰 GPU 的操作。

1. mss 截屏（每 1.2 秒一次）—— BitBlt 从显存读回，可能造成 pipeline stall
2. whisper 推理 —— CUDA 抢占 GPU 计算单元
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def gpu() -> tuple[int, int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        mem, util = out.split(",")
        return int(mem), int(util)
    except Exception:
        return -1, -1


def label(msg: str) -> None:
    print(f"\n{'=' * 58}\n{msg}\n{'=' * 58}", flush=True)


def test_capture() -> None:
    label("1. mss 截屏耗时（500x233 聊天区域）")
    import mss
    factory = getattr(mss, "MSS", None) or mss.mss
    region = {"left": 0, "top": 1202, "width": 500, "height": 233}
    with factory() as sct:
        for _ in range(3):
            sct.grab(region)
        times = []
        stall = 0
        for _ in range(int.__call__(int) if False else 30):
            t0 = time.perf_counter()
            sct.grab(region)
            dt = (time.perf_counter() - t0) * 1000
            times.append(dt)
            time.sleep(0.05)
    times.sort()
    print(f"  30 次: 中位 {times[15]:.1f}ms  p90 {times[int(len(times)*0.9)]:.1f}ms  "
          f"最大 {times[-1]:.1f}ms")
    print(f"  超过 20ms 的卡顿次数: {sum(1 for t in times if t > 20)}")


def test_whisper(models: list[str]) -> None:
    for size in models:
        label(f"2. whisper {size} 推理对 GPU 的影响")
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            print("  faster-whisper 不可用:", exc)
            return
        base_mem, _ = gpu()
        t0 = time.perf_counter()
        try:
            m = WhisperModel(size, device="cuda", compute_type="float16",
                             download_root="models", num_workers=1, cpu_threads=2)
        except Exception as exc:
            print(f"  加载失败: {str(exc)[:120]}")
            continue
        load = time.perf_counter() - t0
        after_mem, _ = gpu()
        print(f"  加载 {load:.1f}s  显存 {base_mem} → {after_mem} MiB "
              f"(+{after_mem - base_mem})")

        audio = (0.1 * np.sin(np.arange(16000 * 3, dtype=np.float32) * 0.05))
        m.transcribe(audio, language="en", beam_size=1)[0]

        # 采样推理期间的 GPU 利用率
        samples = []
        lat = []
        for _ in range(5):
            t0 = time.perf_counter()
            segs, _ = m.transcribe(audio, language="en", beam_size=1, vad_filter=False)
            list(segs)
            lat.append((time.perf_counter() - t0) * 1000)
            samples.append(gpu()[1])
            time.sleep(0.1)
        print(f"  单句 3s 音频推理: {min(lat):.0f}~{max(lat):.0f}ms")
        print(f"  推理瞬间 GPU 利用率采样: {samples}")
        del m
        try:
            import gc
            import ctranslate2
            gc.collect()
        except Exception:
            pass


def test_vision_probe() -> None:
    label("3. 当前 GPU 状态")
    mem, util = gpu()
    print(f"  显存 {mem} MiB  利用率 {util}%")
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,clocks.sm,clocks.max.sm",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=5).stdout.strip()
        print(f"  {out}")
    except Exception:
        pass


if __name__ == "__main__":
    test_vision_probe()
    test_capture()
    test_whisper(["base", "small"])
    print("\n完成。")