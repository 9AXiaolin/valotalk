"""配置读写。config.json 不存在时用默认值生成。"""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
MODELS_DIR = ROOT / "models"
CACHE_DIR = ROOT / "cache"
TMP_DIR = CACHE_DIR / "tts"
LOG_DIR = ROOT / "logs"

DEFAULTS: dict = {
    "asr": {
        "model": "small",              # tiny / base / small / medium
        "device": "auto",              # auto / cuda / cpu
        "compute_type": "auto",        # auto / float16 / int8 / int8_float16
        "lang_teammates": "auto",      # auto = 自动识别语种（英/俄/日/韩都能听）
        "lang_me": "zh",               # 我说的语言
        "beam_size": 1,
        "cpu_threads": 2,              # 别让推理线程池吃满所有核心
        "warmup": True,
        "download_root": str(MODELS_DIR),
    },
    "audio": {
        "game_output_device": "",      # 游戏声音输出（loopback 采集源，通常=耳机）
        "mic_device": "",              # 我的麦克风
        "tts_output_device": "",       # 播放给游戏（VB-Audio Cable Input）
        "capture_samplerate": 48000,
        "block_ms": 30,
        "vad": {
            "noise_floor": 0.004,
            "start_ratio": 3.0,        # 触发阈值 = 噪声底 * ratio
            "start_rms": 0.010,
            "silence_ms": 420,
            "min_speech_ms": 250,
            "max_utterance_ms": 8000,
            "preroll_ms": 240,
            "silero_window_s": 8.0,    # 与 max_utterance 对齐，别互相截断
        },
    },
    "translate": {
        "backend": "auto",             # auto / llm / bing / google
        "google_endpoint": "https://translate.googleapis.com/translate_a/single",
        "proxy": "",                   # 有梯子填 http://127.0.0.1:7890，Google 会更准
        "google_timeout": 3,
        "mymemory_timeout": 6,
        "llm": {
            "base_url": "",            # 例 https://api.deepseek.com/v1
            "api_key": "",
            "model": "",               # 例 deepseek-chat
            "timeout": 12,
            "prompt_cache": True,      # system prompt 标记缓存，省输入 token
        },
        "glossary": True,
        "cache_size": 4000,
        "timeout": 8,
    },
    "ocr": {
        "engine": "auto",              # auto / rapidocr / winrt
        "region": [0, 0, 0, 0],        # [x1,y1,x2,y2]，全 0 表示未设置
        "interval_ms": 2000,           # 聊天扫描间隔；抓屏会读回显存，别太勤
        "min_confidence": 0.50,
        "max_lines": 10,
        "translate": True,
    },
    "tts": {
        "engine": "edge",              # edge / sapi
        "voice": "en-US-GuyNeural",
        "rate": "+10%",
        "pitch": "+0Hz",               # 音高：萝莉 +35Hz、御姐 -20Hz、气泡 -35Hz
        "volume": "+0%",
        "game_ptt_enabled": True,      # 播放前按住游戏内语音键
        "game_ptt_key": "v",
        "ptt_hold_after_ms": 400,
        "max_chars": 220,
    },
    "hotkeys": {
        "ptt": "f2",                   # 按住说话
        "toggle_click_through": "f3",
        "clear_overlay": "f4",
        "toggle_mute_outgoing": "f5",
    },
    "remote": {
        "enabled": True,               # 手机遥控（局域网 HTTP）：游戏独占键鼠时的唯一出路
        "port": 8765,
        "token": "",                   # 访问口令，二维码/复制都带着它
        "auto_token": True,            # token 为空时自动生成（公用 WiFi 下强烈建议）
        "start_with_app": True,        # 程序启动时自动开
    },
    "overlay": {
        "font_family": "Microsoft YaHei UI",
        "font_size": 19,
        "backdrop": False,             # 不要黑色底板
        "outline": True,               # 改用文字描边保证可读性
        "outline_layers": 4,           # 描边层数：8 最清晰但重绘翻倍，4 够用
        "topmost_interval_s": 3.0,     # 置顶检查间隔，太勤会打断全屏合成
        "x": -1,                        # -1 = 自动贴屏幕下方居中
        "y": -1,
        "width": 1120,
        "height": 300,
        "max_lines": 6,
        "ttl_seconds": 30,
        "show_original": True,
        "click_through": True,
        "show_me": True,
        "show_teammates": True,
        "show_chat": True,
    },
    "ui": {
        "panel_on_top": True,
    },
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = _deep_merge(DEFAULTS, raw)
            except Exception:
                pass
        else:
            self.save()

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self.path)

    # ---- 访问器 ----
    def get(self, dotted: str, default=None):
        cur = self._data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted: str, value, save: bool = True) -> None:
        with self._lock:
            parts = dotted.split(".")
            cur = self._data
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = value
            if save:
                self.save()

    def section(self, name: str) -> dict:
        return self._data.get(name, {})

    @property
    def all(self) -> dict:
        return self._data


CONFIG = Config()