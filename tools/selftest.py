"""离线冒烟测试：不碰麦克风、不加载大模型，验证纯逻辑与网络通道。

跑法：
    python tools/selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.capture import Segmenter, resample  # noqa: E402
from valotalk.config import CONFIG  # noqa: E402
from valotalk.ocr import LineDiffer, _merge_rows  # noqa: E402
from valotalk.translate import VALORANT_TERMS, Translator  # noqa: E402

PASS, FAIL = "  [PASS] ", "  [FAIL] "
fails = 0


def ok(cond: bool, name: str, extra: str = "") -> None:
    global fails
    if cond:
        print(PASS + name + (f"  {extra}" if extra else ""))
    else:
        fails += 1
        print(FAIL + name + (f"  {extra}" if extra else ""))


def test_resample() -> None:
    print("\n[1] 重采样 48k → 16k")
    x = np.sin(np.linspace(0, 200 * np.pi, 48000)).astype(np.float32)
    y = resample(x, 48000, 16000)
    ok(len(y) == 16000, "长度 48000→16000", f"得到 {len(y)}")
    ok(abs(float(np.max(np.abs(y))) - 1.0) < 0.2, "幅度保持")


def test_segmenter() -> None:
    print("\n[2] VAD 断句")
    cfg = {"noise_floor": 0.003, "start_ratio": 3.0, "start_rms": 0.01,
           "silence_ms": 300, "min_speech_ms": 200, "max_utterance_ms": 8000,
           "preroll_ms": 240}
    seg = Segmenter(cfg)
    sr = 16000
    silence = (np.random.randn(sr).astype(np.float32) * 0.001)
    speech = (np.random.randn(sr).astype(np.float32) * 0.15)
    out = seg.feed(silence)
    ok(len(out) == 0, "纯静音不出段", f"出 {len(out)} 段")
    out = seg.feed(speech)          # 1 秒说话
    out += seg.feed(silence * 1)    # 1 秒静音收尾
    out += [s for s in [seg.flush()] if s is not None]
    ok(len(out) >= 1, "说话出 1 段", f"出 {len(out)} 段，长度 {[len(s) for s in out]}")
    if out:
        dur = len(out[0]) / sr
        ok(0.5 < dur < 3.5, "段长合理", f"{dur:.2f}s")


def test_differ() -> None:
    print("\n[3] 聊天行去重")
    d = LineDiffer()
    a = d.push(["a: hi", "b: hello"])
    ok(a == ["a: hi", "b: hello"], "首帧全出", str(a))
    b = d.push(["a: hi", "b: hello", "c: rush b"])
    ok(b == ["c: rush b"], "只出新增行", str(b))
    c = d.push(["b: hello", "c: rush b", "d: gg"])
    ok(c == ["d: gg"], "滚动后只出新增", str(c))
    e = d.push(["b: hello", "c: rush b", "d: gg"])
    ok(e == [], "重复帧不出", str(e))


def test_merge_rows() -> None:
    print("\n[4] OCR 碎片合并成行")
    rows = [(10.0, 5.0, "aa"), (11.0, 60.0, "bb"), (40.0, 5.0, "cc")]
    out = _merge_rows(rows)
    ok(out == ["aa bb", "cc"], "同一 y 合并", str(out))


def test_translate() -> None:
    print("\n[5] 翻译（走网络，失败会跳过）")
    tr = Translator(CONFIG.get)
    out = tr.translate("Rush B, plant the spike.", "en", "zh-CN")
    ok(bool(out), "英→中", (out or tr.last_error)[:60])
    out2 = tr.translate("我从中路绕过去，你们看好后面。", "zh", "en")
    ok(bool(out2), "中→英", (out2 or tr.last_error)[:60])
    ok(len(VALORANT_TERMS) > 30, "术语表非空", f"{len(VALORANT_TERMS)} 条")
    if out:
        tr._get = lambda k, d=None: (True if k == "translate.glossary" else
                                     ("en" if k == "translate.backend" else d))
        ann = tr._annotate("eco round rush", "经济局")
        ok("术语" in ann or "=" in ann, "术语追注", ann[:50])


def test_glossary_annotate() -> None:
    print("\n[6] 术语追注")
    orig_get = CONFIG.get

    def fake(k, d=None):
        if k == "translate.glossary":
            return True
        if k == "translate.backend":
            return "google"
        return orig_get(k, d)

    tr = Translator(fake)
    a = tr._annotate("rush b and plant", "冲B点")
    ok("plant=" in a, "命中的术语被追注", a[:60])


if __name__ == "__main__":
    print("ValoTalk 离线自检")
    test_resample()
    test_segmenter()
    test_differ()
    test_merge_rows()
    test_translate()
    test_glossary_annotate()
    print(f"\n完成，失败 {fails} 项。")
    sys.exit(1 if fails else 0)