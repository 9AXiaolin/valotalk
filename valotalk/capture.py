"""音频采集：WASAPI loopback（采集游戏播出的队友语音）+ 麦克风，以及 VAD 断句。"""
from __future__ import annotations

import ctypes
import threading
import time
from collections import deque
from typing import Callable

import numpy as np

try:
    import soundcard as sc
    import warnings as _warnings
    # soundcard 大块读会刷 "data discontinuity"，分块读时是噪声，压掉
    try:
        from soundcard.mediafoundation import SoundcardRuntimeWarning
        _warnings.filterwarnings("ignore", category=SoundcardRuntimeWarning)
    except Exception:
        _warnings.filterwarnings("ignore", message=".*discontinuity.*")
except Exception:  # pragma: no cover
    sc = None

TARGET_SR = 16000

# ---------------------------------------------------------------- COM
# soundcard 走 WASAPI/MediaFoundation，在非主线程使用前必须初始化 COM，
# 否则抛 0x800401f0(CO_E_NOTINITIALIZED)，采集线程会静默失败并一直重试。
try:
    _ole32 = ctypes.WinDLL("ole32")
except Exception:  # pragma: no cover
    _ole32 = None

_COINIT_APARTMENTTHREADED = 0x2


def _to_mono(data) -> np.ndarray:
    """把采集到的数据统一成单声道 float32。

    注意：7.1 声卡 / loopback 常是 8 通道，直接 mean(axis=1) 会把只出现在
    前场的人声衰减 4 倍（实测 RMS 从 0.07 掉到 0.018）。这里只取 L/R。
    """
    if data is None:
        return np.zeros(0, dtype=np.float32)
    if isinstance(data, (bytes, bytearray, memoryview)):
        arr = np.frombuffer(bytes(data), dtype=np.float32)
    else:
        arr = np.asarray(data, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr[:, :2].mean(axis=1) if arr.shape[1] >= 2 else arr[:, 0]
    return np.ascontiguousarray(arr.reshape(-1), dtype=np.float32)


def com_initialize() -> None:
    if _ole32 is None:
        return
    try:
        _ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
    except Exception:
        pass


def com_uninitialize() -> None:
    if _ole32 is None:
        return
    try:
        _ole32.CoUninitialize()
    except Exception:
        pass


# ---------------------------------------------------------------- 设备枚举
def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def list_outputs() -> list[dict]:
    """所有播放设备（可作为 loopback 采集源 / TTS 输出）。"""
    out = []
    for spk in _safe(sc.all_speakers, []) or []:
        out.append({"name": spk.name, "id": spk.id, "kind": "output"})
    return out


def list_inputs() -> list[dict]:
    """所有真实输入设备（麦克风）。"""
    out = []
    for mic in _safe(lambda: sc.all_microphones(include_loopback=False), []) or []:
        out.append({"name": mic.name, "id": mic.id, "kind": "input"})
    return out


def find_speaker(name_or_id: str):
    if not sc or not name_or_id:
        return None
    spk = _safe(lambda: sc.get_speaker(name_or_id))
    if spk:
        return spk
    for s in _safe(sc.all_speakers, []) or []:
        if name_or_id.lower() in s.name.lower():
            return s
    return None


def find_microphone(name_or_id: str):
    if not sc or not name_or_id:
        return None
    mic = _safe(lambda: sc.get_microphone(name_or_id))
    if mic:
        return mic
    for m in _safe(lambda: sc.all_microphones(include_loopback=False), []) or []:
        if name_or_id.lower() in m.name.lower():
            return m
    return None


def find_loopback(name_or_id: str):
    """拿到某个播放设备对应的 loopback 采集端点。"""
    if not sc or not name_or_id:
        return None
    mic = _safe(lambda: sc.get_microphone(name_or_id, include_loopback=True))
    if mic:
        return mic
    targets = _safe(lambda: sc.all_microphones(include_loopback=True), []) or []
    lowered = name_or_id.lower()
    for m in targets:
        if lowered in m.name.lower():
            return m
    return None


def guess_game_output() -> str:
    """猜游戏输出：优先物理耳机/扬声器，避开虚拟线缆。"""
    speakers = _safe(sc.all_speakers, []) or []
    bad = ("cable", "virtual", "vb-audio", "voicemeeter", "steam streaming",
           "nvidia", "mirroring", "mixline", "疯歌")
    cands = [(s.name, s.name) for s in speakers if not any(b in s.name.lower() for b in bad)]
    if cands:
        return cands[0][0]
    return speakers[0].name if speakers else ""


def guess_tts_output() -> str:
    """猜 TTS 输出：优先 VB-Audio Cable Input（游戏把它当麦克风）。"""
    for s in _safe(sc.all_speakers, []) or []:
        low = s.name.lower()
        if "cable input" in low or ("cable" in low and "output" not in low):
            return s.name
    for s in _safe(sc.all_speakers, []) or []:
        if "cable" in s.name.lower() or "virtual" in s.name.lower():
            return s.name
    return ""


# ---------------------------------------------------------------- 重采样
def resample(x: np.ndarray, sr_in: int, sr_out: int = TARGET_SR) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    if sr_in == sr_out or x.size == 0:
        return x
    if sr_in % sr_out == 0:  # 整数倍：取块均值，顺手做抗混叠
        k = sr_in // sr_out
        n = x.size // k
        if n > 0:
            return x[: n * k].reshape(n, k).mean(axis=1).astype(np.float32)
    n_out = max(1, int(round(x.size * sr_out / sr_in)))
    idx = np.linspace(0, x.size - 1, n_out, dtype=np.float32)
    return np.interp(idx, np.arange(x.size, dtype=np.float32), x).astype(np.float32)


# ---------------------------------------------------------------- Silero VAD 断句
class SileroSegmenter:
    """神经网络 VAD 分段（faster-whisper 自带的 silero_vad_v6.onnx，零额外下载）。

    为什么不用能量 VAD：实测打游戏时背景音乐/枪声让 64.8% 的帧都超过能量阈值，
    能量法师会把音乐和人声一起切成 9 秒大块，whisper 拿到的全是垃圾。
    Silero 能区分「人声 / 非人声」，只把人声片段送去做识别。
    """

    def __init__(self, cfg: dict, sr: int = TARGET_SR):
        self.sr = sr
        self.buf = np.zeros(0, dtype=np.float32)
        self.since_check = 0
        # feed 在采集线程，flush 在热键/手机线程 —— 不加锁会抢 buf
        self._lock = threading.Lock()
        self.check_every = max(1, int(0.30 * sr))
        self.min_speech_s = float(cfg.get("silero_min_speech_ms", 300)) / 1000.0
        self.end_gap_s = float(cfg.get("silero_end_gap_ms", 380)) / 1000.0
        self.max_len_s = float(cfg.get("max_utterance_ms", 9000)) / 1000.0
        self.window_s = float(cfg.get("silero_window_s", 12.0))
        self.ok = False
        self._fn = None
        self._opts = None
        try:
            from faster_whisper.vad import VadOptions, get_speech_timestamps
            self._fn = get_speech_timestamps
            self._opts = VadOptions(
                threshold=float(cfg.get("silero_threshold", 0.5)),
                min_speech_duration_ms=int(cfg.get("silero_min_speech_ms", 300)),
                min_silence_duration_ms=int(cfg.get("silero_min_silence_ms", 220)),
                speech_pad_ms=int(cfg.get("silero_pad_ms", 120)),
            )
            self.ok = True
        except Exception as exc:
            self.error = str(exc)

    def reset(self) -> None:
        with self._lock:
            self.buf = np.zeros(0, dtype=np.float32)
            self.since_check = 0

    def flush(self) -> np.ndarray | None:
        """接口与能量 VAD 保持一致：返回单个音频段或 None。"""
        with self._lock:
            out = self._extract(self.buf, force=True)
        return out[0] if out else None

    def feed(self, pcm: np.ndarray) -> list[np.ndarray]:
        pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if pcm.size == 0:
            return []
        with self._lock:
            self.buf = np.concatenate([self.buf, pcm])
            self.since_check += pcm.size
            if self.since_check < self.check_every:
                return []
            self.since_check = 0
            return self._extract(self.buf)

    def _spans(self, audio: np.ndarray):
        if not self.ok or audio.size < int(0.5 * self.sr):
            return []
        try:
            return self._fn(audio, vad_options=self._opts, sampling_rate=self.sr) or []
        except Exception:
            return []

    def _extract(self, audio: np.ndarray, force: bool = False) -> list[np.ndarray]:
        window = audio[-int(self.window_s * self.sr):]
        spans = self._spans(window)
        dur = window.size / self.sr

        if not spans:
            # 一直没人声：只保留最近 1 秒，别让缓冲无限长
            if audio.size > 2 * self.sr:
                self.buf = audio[-self.sr:].copy()
            return []

        gap = dur - spans[-1]["end"] / self.sr
        if not force and gap < self.end_gap_s and dur < self.max_len_s:
            return []                       # 还在说，继续等

        parts = [window[int(s["start"]):int(s["end"])] for s in spans]
        speech = float(sum(p.size for p in parts)) / self.sr
        # 消费掉已处理的部分，保留尾巴一点点，避免和下一段重叠
        tail = window[int(spans[-1]["end"]):]
        self.buf = tail[-self.check_every:].copy() if tail.size else np.zeros(0, np.float32)

        if speech < self.min_speech_s:
            return []
        return [np.concatenate(parts).astype(np.float32)]


# ---------------------------------------------------------------- 能量 VAD（兜底）
class Segmenter:
    """能量型 VAD：自带噪声底跟踪、前置缓冲、最长时长保护。"""

    def __init__(self, cfg: dict, sr: int = TARGET_SR, frame_ms: int = 30):
        self.sr = sr
        self.frame_len = max(1, int(sr * frame_ms / 1000))
        self.frame_ms = frame_ms

        self.noise_floor = float(cfg.get("noise_floor", 0.004))
        self.start_ratio = float(cfg.get("start_ratio", 3.0))
        self.start_rms = float(cfg.get("start_rms", 0.010))
        self.silence_frames = max(1, int(cfg.get("silence_ms", 420) / frame_ms))
        self.min_frames = max(1, int(cfg.get("min_speech_ms", 250) / frame_ms))
        self.max_frames = max(1, int(cfg.get("max_utterance_ms", 12000) / frame_ms))
        preroll_frames = max(1, int(cfg.get("preroll_ms", 240) / frame_ms))

        self._tail = np.zeros(0, dtype=np.float32)
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_frames)
        self._cur: list[np.ndarray] = []
        self._cur_frames = 0
        self._silent = 0
        self._in_speech = False
        # feed 在采集线程，flush 在热键/手机线程 —— 不加锁会抢内部缓冲
        self._lock = threading.Lock()

    @property
    def threshold(self) -> float:
        return max(self.start_rms, self.noise_floor * self.start_ratio)

    def reset(self) -> None:
        with self._lock:
            self._tail = np.zeros(0, dtype=np.float32)
            self._preroll.clear()
            self._cur.clear()
            self._cur_frames = 0
            self._silent = 0
            self._in_speech = False

    def feed(self, pcm: np.ndarray) -> list[np.ndarray]:
        """喂入 16k float32 连续音频，返回已完成的语音段列表。"""
        pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if pcm.size == 0:
            return []
        with self._lock:
            if self._tail.size:
                pcm = np.concatenate([self._tail, pcm])
            out: list[np.ndarray] = []
            n_full = pcm.size // self.frame_len
            for i in range(n_full):
                frame = pcm[i * self.frame_len : (i + 1) * self.frame_len]
                done = self._frame(frame)
                if done is not None:
                    out.append(done)
            rest = pcm[n_full * self.frame_len :]
            self._tail = rest.copy()
            return out

    def flush(self) -> np.ndarray | None:
        """说话未收尾时强制吐出（用于热键松开）。"""
        with self._lock:
            if self._in_speech and self._cur_frames >= self.min_frames:
                seg = np.concatenate(self._cur) if self._cur else None
                self._reset_current()
                return seg
            self._reset_current()
            return None

    def _reset_current(self) -> None:
        self._cur.clear()
        self._cur_frames = 0
        self._silent = 0
        self._in_speech = False

    def _frame(self, frame: np.ndarray) -> np.ndarray | None:
        rms = float(np.sqrt(np.mean(np.square(frame)) + 1e-12))
        thr = self.threshold

        if not self._in_speech:
            if rms > thr:
                self._in_speech = True
                self._cur = list(self._preroll)
                self._cur_frames = len(self._cur)
                self._preroll.clear()
                self._cur.append(frame)
                self._cur_frames += 1
                self._silent = 0
            else:
                self._preroll.append(frame)
                # 噪声底只慢速下调，避免被人声带偏
                self.noise_floor = 0.995 * self.noise_floor + 0.005 * rms
                if self.noise_floor < 1e-5:
                    self.noise_floor = 1e-5
            return None

        # 说话中
        self._cur.append(frame)
        self._cur_frames += 1
        if rms < thr * 0.6:
            self._silent += 1
        else:
            self._silent = 0

        if self._silent >= self.silence_frames:
            return self._finish()
        if self._cur_frames >= self.max_frames:
            return self._finish()
        return None

    def _finish(self) -> np.ndarray | None:
        seg = np.concatenate(self._cur) if self._cur else None
        frames = self._cur_frames
        self._reset_current()
        if seg is None or frames < self.min_frames:
            return None
        # 去掉尾部静音
        keep = max(0, frames - self._silent) * self.frame_len
        if keep > 0:
            seg = seg[:keep]
        if seg.size < int(self.sr * 0.15):
            return None
        return seg.astype(np.float32)


# ---------------------------------------------------------------- 采集线程
class AudioSource:
    """持续采集一个设备，把 16k 单声道数据抛给回调。soundcard 阻塞读，线程安全。"""

    def __init__(self, device_name: str, loopback: bool, samplerate: int,
                 block_ms: int, on_chunk: Callable[[np.ndarray], None], label: str = ""):
        self.device_name = device_name
        self.loopback = loopback
        self.samplerate = samplerate
        self.block_ms = block_ms
        self.on_chunk = on_chunk
        self.label = label or device_name
        self.error: str | None = None
        self.running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name=f"cap-{self.label}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)

    def _open(self):
        if self.loopback:
            dev = find_loopback(self.device_name)
        else:
            dev = find_microphone(self.device_name)
        if dev is None:
            raise RuntimeError(f"找不到设备: {self.device_name}")
        return dev

    def _loop(self) -> None:
        if sc is None:
            self.error = "soundcard 未安装"
            return
        com_initialize()          # 必须在工作线程里初始化 COM
        try:
            dev = self._open()
        except Exception as exc:
            self.error = str(exc)
            com_uninitialize()
            return
        frames = max(128, int(self.samplerate * self.block_ms / 1000))
        self.running = True
        backoff = 0.2
        err_count = 0
        while not self._stop.is_set():
            try:
                with dev.recorder(samplerate=self.samplerate, blocksize=frames) as rec:
                    backoff = 0.2
                    while not self._stop.is_set():
                        data = rec.record(numframes=frames)
                        arr = _to_mono(data)
                        if arr.size == 0:
                            continue
                        self.peak = float(np.max(np.abs(arr)))
                        self.on_chunk(resample(arr, self.samplerate, TARGET_SR))
            except Exception as exc:
                err_count += 1
                if err_count <= 3:
                    self.error = f"{type(exc).__name__}: {exc}"
                if self._stop.is_set():
                    break
                time.sleep(backoff)
                backoff = min(backoff * 2, 3.0)
        self.running = False
        com_uninitialize()


# ---------------------------------------------------------------- 播放到指定设备
_SD_CACHE: dict[str, tuple[int, int] | None] = {}


def sd_pick_output(name: str) -> tuple[int, int] | None:
    """在 PortAudio 里找匹配的输出设备，优先 WASAPI，返回 (device_index, 原生采样率)。

    soundcard 的 player 在部分设备上会把 48k 音频按错采样率播放（变调变慢），
    WASAPI 直连并按设备原生采样率喂数据才稳。
    """
    if not name:
        return None
    key = name.lower()
    if key in _SD_CACHE:
        return _SD_CACHE[key]
    try:
        import sounddevice as sd
    except Exception:
        _SD_CACHE[key] = None
        return None
    try:
        hostapis = sd.query_hostapis()
        wasapi = {i for i, h in enumerate(hostapis) if "WASAPI" in h["name"].upper()}
        best = None
        for idx, d in enumerate(sd.query_devices()):
            if d.get("max_output_channels", 0) < 1:
                continue
            if key not in d["name"].lower():
                continue
            score = 10 if d["hostapi"] in wasapi else 0
            score -= abs(len(d["name"]) - len(name))          # 名字越贴合越好
            cand = (score, idx, int(d.get("default_samplerate") or 48000))
            if best is None or cand[0] > best[0]:
                best = cand
        res = (best[1], best[2]) if best else None
    except Exception:
        res = None
    _SD_CACHE[key] = res
    return res


class SpeakerSink:
    """把 PCM 播放到指定输出设备（TTS 送进游戏靠这个）。

    注意：用**类级锁**而非实例锁 —— 每次播放都 new 一个 SpeakerSink，
    实例锁挡不住并发。两个流同时开在同一设备上就是"鬼畜音"的来源。
    """

    _play_lock = threading.Lock()          # 类级：同一时间只允许一个播放

    def __init__(self, device_name: str):
        self.device_name = device_name
        self.last_error = ""

    def play(self, pcm: np.ndarray, samplerate: int) -> bool:
        pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if pcm.size == 0:
            return False
        with SpeakerSink._play_lock:
            if self._play_sounddevice(pcm, samplerate):
                return True
            return self._play_soundcard(pcm, samplerate)

    def _play_sounddevice(self, pcm: np.ndarray, sr: int) -> bool:
        picked = sd_pick_output(self.device_name)
        if picked is None:
            self.last_error = f"sounddevice 找不到输出: {self.device_name}"
            return False
        idx, native = picked
        if native != sr:
            pcm = resample(pcm, sr, native)
        try:
            import sounddevice as sd
            # sd.play() 是一次性播放 API：内部管理流的开/关，
            # sd.wait() 等播完才返回 —— 不像 OutputStream.write()
            # 那样写完缓冲就退出导致掐断
            sd.play(pcm.reshape(-1, 1), samplerate=native, device=idx)
            sd.wait()
            return True
        except Exception as exc:
            self.last_error = f"sounddevice: {exc}"
            return False

    def _play_soundcard(self, pcm: np.ndarray, sr: int) -> bool:
        if sc is None:
            return False
        spk = find_speaker(self.device_name)
        if spk is None:
            return False
        try:
            with spk.player(samplerate=sr, channels=1) as player:
                player.play(pcm.reshape(-1, 1))
            return True
        except Exception as exc:
            self.last_error = f"soundcard: {exc}"
            return False