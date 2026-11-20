"""全链路验证：模拟 F2 按住 → 中文语音 → 识别 → 翻英文 → 按住 V → 播放。

不依赖真实麦克风：用 edge-tts 合成一句中文，分块喂进麦克风处理链路。
按键与播放会被记录下来，用来确认「V 真的被按了」。
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk import winapi  # noqa: E402
from valotalk.app import App  # noqa: E402
from valotalk.capture import TARGET_SR, resample  # noqa: E402

ZH = "我要去拆包，掩护我"
fails = 0


def ok(cond: bool, name: str, extra: str = "") -> None:
    global fails
    if cond:
        print("  [PASS] " + name + (f"  {extra}" if extra else ""), flush=True)
    else:
        fails += 1
        print("  [FAIL] " + name + (f"  {extra}" if extra else ""), flush=True)


def make_zh_audio() -> np.ndarray:
    import edge_tts
    out = ROOT / "cache" / "zh_ptt_test.mp3"
    out.parent.mkdir(exist_ok=True)

    async def gen():
        await edge_tts.Communicate(ZH, "zh-CN-XiaoxiaoNeural").save(str(out))

    asyncio.run(gen())
    from valotalk.tts import TTS
    tts = TTS(lambda k, d=None: d if d is not None else None)
    pcm = tts._decode_audio(out)
    if pcm is None:
        raise RuntimeError("解码失败: " + tts.last_error)
    return resample(pcm, 24000, TARGET_SR)


def main() -> None:
    # 记录按键与播放
    events: list[tuple[str, str]] = []
    orig_down, orig_up = winapi.key_down, winapi.key_up

    def rec_down(name):
        events.append(("down", name))
        orig_down(name)

    def rec_up(name):
        events.append(("up", name))
        orig_up(name)

    winapi.key_down, winapi.key_up = rec_down, rec_up

    app = App()
    app._running = True          # 不自动开采集，避免真麦克风的杂音混进来

    # 手动搭起「说话 → 识别 → 翻译」的链路（正常由 start() 完成）
    import threading
    app._seg_me = app._make_segmenter(app._get("audio.vad", {}))
    threading.Thread(target=app._asr_worker, name="asr-worker", daemon=True).start()
    threading.Thread(target=app._post_worker, name="post-worker", daemon=True).start()
    print(f"  麦克风分段器: {type(app._seg_me).__name__}", flush=True)

    print("[1] 加载模型 …", flush=True)
    t0 = time.time()
    if not app.asr.ensure_loaded(on_status=lambda s: None):
        print("  模型加载失败:", app.asr.load_error)
        return
    print(f"  就绪 {time.time()-t0:.1f}s  device={app.asr.device}", flush=True)

    plays: list[str] = []
    orig_speak = app.tts.speak

    def rec_speak(text):
        plays.append(text)
        return orig_speak(text)

    app.tts.speak = rec_speak

    print(f"[2] 合成中文语音：{ZH}", flush=True)
    audio = make_zh_audio()
    print(f"  {len(audio)/TARGET_SR:.2f}s", flush=True)

    print("[3] 模拟按住 F2 → 喂音频 → 松开", flush=True)
    app._ptt_down()
    ok(app._me_armed, "F2 按下后进入录音状态")
    block = int(TARGET_SR * 0.03)
    for i in range(0, len(audio), block):
        app._on_mic_audio(audio[i:i + block])
    # 补一段静音让 VAD 收尾
    for _ in range(30):
        app._on_mic_audio(np.zeros(block, dtype=np.float32))
    app._ptt_up()
    ok(not app._me_armed, "F2 松开后退出录音状态")

    print("[4] 等待识别 + 翻译 + TTS + 按键 …", flush=True)
    deadline = time.time() + 60
    got = None
    t_speak = None
    while time.time() < deadline:
        app.root.update()
        for line in app.log_lines:
            if "我：" in line:
                got = line
        # TTS 合成要几秒，必须等按键真的发生
        if got and not t_speak:
            t_speak = time.time()
        if got and len(events) >= 2:
            break
        time.sleep(0.1)
    if t_speak:
        print(f"  识别+翻译完成，等待 TTS 与按键 {time.time()-t_speak:.1f}s", flush=True)

    print()
    print("=== 日志 ===")
    for line in app.log_lines[-12:]:
        print("   ", line)

    print("\n=== 按键事件 ===")
    if events:
        for kind, name in events:
            print(f"    {kind:4s} {name}")
    else:
        print("    （无）")

    print()
    ok(got is not None, "中文被识别并翻译", got.split("我：")[-1][:70] if got else "超时未完成")
    if got:
        parts = got.split("→")
        zh_part = parts[0].split("我：")[-1].strip()
        en_part = parts[-1].strip() if len(parts) > 1 else ""
        print(f"    识别中文: {zh_part}")
        print(f"    译成英文: {en_part}")
        ok(bool(zh_part), "识别结果非空")
        ok(bool(en_part) and not any("\u4e00" <= c <= "\u9fff" for c in en_part),
           "译文是英文", en_part[:50])
    ok(len(plays) >= 1, "TTS 被调用", plays[-1][:60] if plays else "（没调用）")
    downs = [n for k, n in events if k == "down"]
    ups = [n for k, n in events if k == "up"]
    ok("v" in downs, "按下了 V（游戏开麦键）", str(downs))
    ok("v" in ups, "松开了 V", str(ups))

    app.shutdown()
    print(f"\n完成，失败 {fails} 项。")


if __name__ == "__main__":
    main()