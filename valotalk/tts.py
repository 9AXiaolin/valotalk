"""TTS：edge-tts（联网、音色好）→ Windows SAPI（离线兜底），一律送到指定输出设备。

要点：播放前按住游戏内语音键（PTT），播完再松，游戏才会把音频当麦克风输入发出去。
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from .capture import SpeakerSink, resample
from .config import CACHE_DIR, TMP_DIR
from .winapi import VirtualKeyHold

TTS_SR = 24000

_PS_SAPI = r"""
param([string]$Text, [string]$Out)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 2
$s.Volume = 100
$s.SetOutputToWaveFile($Out)
$s.Speak($Text)
$s.Dispose()
"""


class TTS:
    def __init__(self, cfg_get, log=None):
        self._get = cfg_get
        self._log = log or (lambda *a, **k: None)
        self._lock = threading.Lock()
        self._hold = VirtualKeyHold()
        self.last_error = ""
        self._inject_warned = False
        self._tmp = TMP_DIR
        self._tmp.mkdir(parents=True, exist_ok=True)
        self._cache_dir = CACHE_DIR / "tts_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- synth 缓存 ----------------
    def _cache_path(self, text: str) -> Path:
        key = "|".join([
            text,
            str(self._get("tts.voice", "en-US-GuyNeural")),
            str(self._get("tts.rate", "+10%")),
            str(self._get("tts.pitch", "+0Hz")),
            str(self._get("tts.volume", "+0%")),
        ]).encode("utf-8")
        return self._cache_dir / (hashlib.md5(key).hexdigest() + ".npy")

    def warmup(self, phrases) -> None:
        """后台把常用喊话合成好，游戏里命中时零延迟。"""
        def run():
            made = 0
            for p in dict.fromkeys(phrases):
                if not p:
                    continue
                path = self._cache_path(p)
                if path.exists():
                    continue
                pcm = self._via_edge(p)
                if pcm is None:
                    break                      # 网络不通就别继续耗
                try:
                    np.save(path, pcm)
                    made += 1
                except Exception:
                    break
            if made:
                self._log(f"TTS 预热完成 {made} 句")

        threading.Thread(target=run, name="tts-warmup", daemon=True).start()

    # ---------------- 对外 ----------------
    def speak(self, text: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        max_chars = int(self._get("tts.max_chars", 220) or 220)
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + "…"

        with self._lock:
            cached = self._cache_path(text)
            if cached.exists():
                try:
                    pcm = np.load(cached)
                    return self._play_into_game(pcm, TTS_SR)
                except Exception:
                    pass
            pcm, sr = self._synthesize(text)
            if pcm is None:
                return False
            try:
                np.save(cached, pcm)
            except Exception:
                pass
            return self._play_into_game(pcm, sr)

    # ---------------- 合成 ----------------
    def _synthesize(self, text: str) -> tuple[np.ndarray | None, int]:
        engine = (self._get("tts.engine", "edge") or "edge").lower()
        if engine in ("edge", "auto"):
            pcm = self._via_edge(text)
            if pcm is not None:
                return pcm, TTS_SR
            self._log("edge-tts 失败，改用离线 SAPI：" + self.last_error)
        pcm = self._via_sapi(text)
        if pcm is not None:
            return pcm, TTS_SR
        return None, TTS_SR

    def _via_edge(self, text: str) -> np.ndarray | None:
        try:
            import edge_tts
        except Exception as exc:
            self.last_error = f"edge-tts 未安装: {exc}"
            return None
        voice = self._get("tts.voice", "en-US-GuyNeural")
        rate = self._get("tts.rate", "+10%")
        volume = self._get("tts.volume", "+0%")
        pitch = self._get("tts.pitch", "+0Hz")
        out = self._tmp / f"{uuid.uuid4().hex}.mp3"

        async def run():
            comm = edge_tts.Communicate(text, voice, rate=rate, volume=volume,
                                        pitch=pitch)
            await comm.save(str(out))

        try:
            asyncio.run(run())
        except Exception as exc:
            self.last_error = f"edge-tts: {exc}"
            return None
        if not out.exists() or out.stat().st_size < 512:
            self.last_error = "edge-tts 输出为空"
            return None
        pcm = self._decode_audio(out)
        try:
            out.unlink()
        except Exception:
            pass
        return pcm

    def _decode_audio(self, path: Path) -> np.ndarray | None:
        # 先读字节再解码：miniaudio 的 C 层用 ANSI 路径，中文路径会报 -7(不存在)
        try:
            raw = Path(path).read_bytes()
        except Exception as exc:
            self.last_error = f"读取音频失败: {exc}"
            return None
        if len(raw) < 256:
            self.last_error = "音频文件过小"
            return None
        # 首选 miniaudio（纯 wheel，支持 mp3/wav）
        try:
            import miniaudio
            dec = miniaudio.decode(
                raw,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
                sample_rate=TTS_SR,
            )
            return np.asarray(dec.samples, dtype=np.float32)
        except Exception as exc:
            self.last_error = f"miniaudio 解码失败: {exc}"
        # 兜底：soundfile（只吃 wav/flac）
        try:
            import io

            import soundfile as sf
            data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
            if getattr(data, "ndim", 1) > 1:
                data = data.mean(axis=1)
            return resample(np.asarray(data, dtype=np.float32), sr, TTS_SR)
        except Exception:
            return None

    def _via_sapi(self, text: str) -> np.ndarray | None:
        out = self._tmp / f"{uuid.uuid4().hex}.wav"
        script = Path(tempfile.gettempdir()) / "valotalk_sapi.ps1"
        try:
            script.write_text(_PS_SAPI, encoding="utf-8-sig")
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-Text", text, "-Out", str(out)],
                capture_output=True, timeout=25,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode != 0:
                err = (proc.stderr or b"").decode("utf-8", "ignore")[:160]
                self.last_error = f"sapi rc={proc.returncode} {err}"
        except Exception as exc:
            self.last_error = f"sapi: {exc}"
            return None
        if not out.exists() or out.stat().st_size < 1024:
            self.last_error = "sapi 输出为空"
            return None
        pcm = self._decode_audio(out)
        try:
            out.unlink()
        except Exception:
            pass
        return pcm

    def _check_inject(self) -> None:
        """第一次播放时提醒一次：跨完整性级别的模拟按键会被系统丢掉。"""
        if self._inject_warned:
            return
        self._inject_warned = True
        try:
            from .winapi import keyinject_blocked
            blocked = keyinject_blocked()
        except Exception:
            return
        if blocked:
            self._log("⚠ 未以管理员运行：模拟的 V 会被系统丢弃，队友听不到英文")
            self._log("   右键 run.bat → 以管理员身份运行，或面板点「以管理员重启」")

    # ---------------- 播放（送进游戏） ----------------
    def _play_into_game(self, pcm: np.ndarray, sr: int) -> bool:
        device = self._get("audio.tts_output_device", "")
        if not device:
            self.last_error = "未设置 TTS 输出设备"
            return False
        ptt_on = bool(self._get("tts.game_ptt_enabled", True))
        ptt_key = self._get("tts.game_ptt_key", "v")
        after = int(self._get("tts.ptt_hold_after_ms", 400) or 400)
        sink = SpeakerSink(device)
        try:
            if ptt_on and ptt_key:
                self._hold.acquire(ptt_key)
                self._check_inject()
                time.sleep(0.12)  # 等游戏打开话筒
            ok = sink.play(pcm, sr)
            if not ok:
                self.last_error = f"播放失败：{device}"
            if ptt_on and ptt_key:
                time.sleep(after / 1000.0)
            return ok
        finally:
            if ptt_on and ptt_key:
                self._hold.release()

    def speak_blocking_async(self, text: str) -> None:
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()