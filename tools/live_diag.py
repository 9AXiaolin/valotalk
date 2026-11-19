"""实时诊断：同时监听所有输出设备的 loopback + 麦克风，看声音到底在哪条线上。

用法（打游戏时跑）：python tools/live_diag.py [秒数]
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk.capture import _to_mono, com_initialize  # noqa: E402

import soundcard as sc  # noqa: E402

SR = 48000
SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0


def probe_loopback(spk, out: dict) -> None:
    try:
        dev = sc.get_microphone(spk.id, include_loopback=True)
        with dev.recorder(samplerate=SR) as r:
            raw = r.record(numframes=int(SR * SECS))
        a = _to_mono(raw)
        out[spk.name] = (float(np.sqrt(np.mean(a ** 2))), float(np.max(np.abs(a))))
    except Exception as exc:
        out[spk.name] = (-1.0, f"{type(exc).__name__}")


def probe_input(mic, out: dict) -> None:
    try:
        with mic.recorder(samplerate=SR) as r:
            raw = r.record(numframes=int(SR * SECS))
        a = _to_mono(raw)
        out[mic.name] = (float(np.sqrt(np.mean(a ** 2))), float(np.max(np.abs(a))))
    except Exception as exc:
        out[mic.name] = (-1.0, f"{type(exc).__name__}")


def main() -> None:
    com_initialize()
    print(f"监听 {SECS:.0f} 秒 …（现在游戏里有声音/有人说话最好）\n", flush=True)

    outs: dict = {}
    threads = []
    for spk in sc.all_speakers():
        t = threading.Thread(target=probe_loopback, args=(spk, outs), daemon=True)
        t.start()
        threads.append(t)

    ins: dict = {}
    for mic in sc.all_microphones(include_loopback=False):
        t = threading.Thread(target=probe_input, args=(mic, ins), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=SECS + 8)

    print("=== 输出设备（游戏声音在这里）===")
    for name, (rms, peak) in sorted(outs.items(), key=lambda kv: -(kv[1][0] if isinstance(kv[1][0], float) else -1)):
        flag = "  <<< 有声音" if isinstance(rms, float) and rms > 0.003 else ""
        print(f"  {name[:46]:48s} RMS={rms if isinstance(rms,str) else f'{rms:.5f}':>9} peak={peak}{flag}")

    print("\n=== 输入设备（你的麦克风）===")
    for name, (rms, peak) in sorted(ins.items(), key=lambda kv: -(kv[1][0] if isinstance(kv[1][0], float) else -1)):
        flag = "  <<< 有声音" if isinstance(rms, float) and rms > 0.003 else ""
        print(f"  {name[:46]:48s} RMS={rms if isinstance(rms,str) else f'{rms:.5f}':>9} peak={peak}{flag}")

    print("\n结论：")
    loud = [n for n, (r, _p) in outs.items() if isinstance(r, float) and r > 0.003]
    if loud:
        print("  有声音的输出设备:", ", ".join(loud))
        print("  → 把面板里「游戏输出（采队友语音）」设成这里面音量最大的那个")
    else:
        print("  所有输出设备都没声音：游戏可能在独占全屏、或声音走了别处")


if __name__ == "__main__":
    main()