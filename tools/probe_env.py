"""环境自检：设备、依赖、翻译通道、OCR、TTS。直接看输出即可定位问题。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import capture  # noqa: E402
from valotalk.config import CONFIG  # noqa: E402


def line(title: str) -> None:
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


def check_deps() -> None:
    line("1. 依赖")
    mods = [
        ("numpy", "numpy"),
        ("soundcard", "soundcard"),
        ("mss", "mss"),
        ("requests", "requests"),
        ("miniaudio", "miniaudio（mp3 解码）"),
        ("edge_tts", "edge-tts（联网 TTS）"),
        ("faster_whisper", "faster-whisper（语音识别）"),
        ("cv2", "opencv（OCR 前置）"),
        ("rapidocr_onnxruntime", "rapidocr（聊天 OCR）"),
        ("onnxruntime", "onnxruntime"),
    ]
    for mod, label in mods:
        try:
            __import__(mod)
            print(f"  [OK]   {label}")
        except Exception as exc:
            print(f"  [MISS] {label}  ->  {exc.__class__.__name__}: {exc}")


def check_devices() -> None:
    line("2. 音频设备")
    print("-- 输出设备（可选作『游戏输出』采集源 / 『TTS 输出』目标）--")
    for d in capture.list_outputs():
        print("   ", d["name"])
    print("-- 输入设备（麦克风）--")
    for d in capture.list_inputs():
        print("   ", d["name"])
    print("\n自动识别结果：")
    print("   游戏输出 →", capture.guess_game_output() or "(未找到)")
    print("   TTS 输出 →", capture.guess_tts_output() or "(未找到 VB-Audio Cable)")
    cfg = CONFIG.all
    print("\n当前配置：")
    for k in ("game_output_device", "mic_device", "tts_output_device"):
        print(f"   {k:22s} = {cfg['audio'].get(k) or '(空)'}")


def check_translate() -> None:
    line("3. 翻译通道")
    from valotalk.translate import Translator
    tr = Translator(CONFIG.get)
    samples = [
        ("en", "zh-CN", "Rush B, I'll plant the spike behind the box."),
        ("zh", "en", "我从中路过去，你们看住绕后。"),
    ]
    for src, dst, text in samples:
        out = tr.translate(text, src, dst)
        status = "OK" if out else f"失败（{tr.last_error}）"
        print(f"  [{status}] {text}\n      → {out}\n      (backend={tr.backend_used})")


def check_ocr() -> None:
    line("4. 聊天 OCR")
    import numpy as np
    from valotalk.ocr import ChatOCR
    ocr = ChatOCR(CONFIG.get)
    if not ocr.ensure_engine():
        print("  [MISS] 没有可用 OCR 引擎：", ocr.last_error)
        return
    print("  引擎：", ocr.kind)

    # 合成一张"聊天框"样张，白字黑底
    h, w = 120, 620
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (18, 20, 24)
    try:
        from PIL import Image, ImageDraw, ImageFont
        pil = Image.fromarray(img[:, :, ::-1])
        draw = ImageDraw.Draw(pil)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
        except Exception:
            font = ImageFont.load_default()
        draw.text((10, 12), "s0mebody: nice shot bro", fill=(235, 240, 245), font=font)
        draw.text((10, 46), "Teammate1: they are rotating A", fill=(235, 240, 245), font=font)
        draw.text((10, 80), "you: gg wp", fill=(235, 240, 245), font=font)
        img = np.asarray(pil)[:, :, ::-1].copy()
    except Exception as exc:
        print("  (跳过样张绘制：", exc, ")")

    lines = ocr.read_lines(img)
    if lines:
        print("  识别结果：")
        for ln in lines:
            print("    |", ln)
    else:
        print("  [WARN] 没识别出内容：", ocr.last_error)


def check_tts() -> None:
    line("5. TTS（只合成，不播放）")
    from valotalk.tts import TTS
    t = TTS(CONFIG.get)
    pcm = t._via_edge("Enemy on B, watch the flank.")
    if pcm is None:
        print("  [edge] 失败：", t.last_error)
        pcm = t._via_sapi("Enemy on B, watch the flank.")
        if pcm is None:
            print("  [sapi] 也失败：", t.last_error)
            return
        print("  [sapi] OK，采样点：", len(pcm))
        return
    print(f"  [edge] OK，采样点：{len(pcm)}（约 {len(pcm)/24000:.2f}s）")


def check_asr() -> None:
    line("6. 语音识别（不加载模型，只看装没装）")
    try:
        import faster_whisper  # noqa: F401
        import ctranslate2
        print("  faster-whisper OK，ctranslate2", ctranslate2.__version__)
        try:
            import torch  # noqa: F401
            print("  torch:", torch.__version__,
                  "cuda:", torch.cuda.is_available())
        except Exception:
            print("  未装 torch（不需要，faster-whisper 自带推理后端）")
    except Exception as exc:
        print("  [MISS]", exc)


if __name__ == "__main__":
    print("ValoTalk 环境自检")
    check_deps()
    check_devices()
    check_translate()
    check_ocr()
    check_tts()
    check_asr()
    print("\n自检结束。")