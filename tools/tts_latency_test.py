"""TTS 延迟对比：缓存命中 / edge 首次 / SAPI 离线。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import CONFIG
from valotalk.tts import TTS

TEXTS = [
    "Cover me.",
    "Enemy one tap on A site, watch the flank.",
    "I'm rotating to B now, hold the mid.",
]


def bench(label: str, fn, n: int = 2) -> None:
    times = []
    for _ in range(n):
        t0 = time.time()
        r = fn()
        times.append(time.time() - t0)
        if r is None:
            print(f"  {label}: 失败")
            return
    print(f"  {label:28s} {min(times):5.2f} ~ {max(times):5.2f}s")


def main() -> None:
    tts = TTS(CONFIG.get, log=lambda m: None)
    print("=== edge-tts 合成（不含播放）===")
    for t in TEXTS:
        times = []
        for _ in range(2):
            t0 = time.time()
            pcm = tts._via_edge(t)
            times.append(time.time() - t0)
            if pcm is None:
                print(f"  失败: {tts.last_error}")
                break
        else:
            print(f"  {min(times):5.2f} ~ {max(times):5.2f}s  {t[:44]}")

    print("\n=== SAPI 离线合成 ===")
    for t in TEXTS[:2]:
        t0 = time.time()
        pcm = tts._via_sapi(t)
        dt = time.time() - t0
        print(f"  {dt:5.2f}s  {'OK' if pcm is not None else '失败'}  {t[:44]}")

    print("\n=== 缓存命中（第二次相同文本）===")
    for t in TEXTS[:2]:
        path = tts._cache_path(t)
        t0 = time.time()
        pcm = tts._via_edge(t)
        first = time.time() - t0
        if pcm is not None:
            import numpy as np
            np.save(path, pcm)
        t1 = time.time()
        loaded = np.load(path) if path.exists() else None
        print(f"  首次 {first:5.2f}s  →  读缓存 {(time.time()-t1)*1000:5.1f}ms  "
              f"({0 if loaded is None else len(loaded)/24000:.2f}s 音频)")


if __name__ == "__main__":
    main()