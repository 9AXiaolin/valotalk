"""验证采集线程 feed 与手机线程 flush 并发时不炸、不丢段。

手机遥控把 flush 挪到了 HTTP 线程，和采集线程同时碰分段器的缓冲。
这段测试反复并发喂音频 + flush，出异常就算失败。

跑：D:\\python\\python.exe -X utf8 tools\\segmenter_race_test.py
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import capture  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SR = 16000
CFG = {
    "silero_threshold": 0.5,
    "silero_min_speech_ms": 200,
    "silero_min_silence_ms": 200,
    "silero_pad_ms": 80,
    "silero_window_s": 8.0,
    "max_utterance_ms": 8000,
}


def tone(sec: float, amp: float = 0.25, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(SR * sec), dtype=np.float32) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def silence(sec: float) -> np.ndarray:
    return np.zeros(int(SR * sec), dtype=np.float32)


def load_speech() -> np.ndarray | None:
    """找一段真人声（缓存里的 edge-tts 产物）——纯正弦波 Silero 不认，
    它只对人声有反应，所以正确性测试必须用真语音。"""
    import miniaudio

    for f in sorted((ROOT / "cache" / "tts").glob("*.mp3")):
        if f.stat().st_size < 2048:
            continue
        try:
            d = miniaudio.decode_file(str(f), output_format=miniaudio.SampleFormat.FLOAT32,
                                      nchannels=1, sample_rate=SR)
            a = np.array(d.samples, dtype=np.float32)
        except Exception:
            continue
        if a.size > SR * 0.4 and float(np.abs(a).max()) > 0.05:
            return a
    return None


def main() -> int:
    ok = True
    speech = load_speech()
    if speech is None:
        print("提示：cache/tts 里没有可用的语音缓存，正确性用例会跳过\n")
    else:
        print(f"真人声样本：{speech.size / SR:.2f}s\n")

    for name, factory in (("SileroSegmenter", lambda: capture.SileroSegmenter(CFG)),
                          ("Segmenter", lambda: capture.Segmenter(CFG))):
        seg = factory()
        if getattr(seg, "ok", True) is False:
            print(f"{name}: Silero 不可用，跳过（{getattr(seg, 'error', '')}）\n")
            continue

        # ---- 1) 并发：一个线程狂喂，主线程狂 flush ----
        errors: list[str] = []
        got: list[int] = []
        stop = threading.Event()

        def feeder():
            try:
                while not stop.is_set():
                    seg.feed(tone(0.03))
            except Exception as exc:      # noqa: BLE001
                errors.append(f"feed: {type(exc).__name__}: {exc}")

        th = threading.Thread(target=feeder, daemon=True)
        th.start()
        t0 = time.time()
        flushes = 0
        try:
            while time.time() - t0 < 2.0:
                out = seg.flush()
                flushes += 1
                if out is not None:
                    got.append(out.size)
        except Exception as exc:          # noqa: BLE001
            errors.append(f"flush: {type(exc).__name__}: {exc}")
        stop.set()
        th.join(timeout=2)

        print(f"{name}: 2s 内 flush {flushes} 次，吐出 {len(got)} 段，"
              f"异常 {len(errors)} 个")
        for e in errors[:3]:
            print("   ", e)
        if errors:
            ok = False

        # ---- 2) 顺序正确性：真语音 → flush 必须吐出这一段 ----
        if speech is not None:
            seg.reset()
            seg.feed(silence(0.25))
            seg.feed(speech)
            seg.feed(silence(0.10))
            out = seg.flush()
            got_s = 0.0 if out is None else out.size / SR
            want = speech.size / SR
            good = out is not None and got_s >= want * 0.5
            print(f"{name}: 喂 {want:.2f}s 语音 → flush 得到 {got_s:.2f}s  "
                  f"{'OK' if good else 'FAIL'}")
            if not good:
                ok = False
        else:
            print(f"{name}: 正确性用例跳过（没有语音样本）")

        # ---- 3) reset 之后缓冲区确实清空 ----
        seg.reset()
        out = seg.flush()
        print(f"{name}: reset 后立即 flush → "
              f"{'None OK' if out is None else 'FAIL 还有残留'}")
        if out is not None:
            ok = False
        print()

    print("=" * 52)
    print("全部通过 ✅" if ok else "有失败项 ❌")
    print("=" * 52)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())