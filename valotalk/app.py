"""ValoTalk —— 无畏契约国际服实时语音 / 聊天翻译。

链路：
  1) 队友语音：系统声音 loopback → VAD → whisper(en) → 翻译 → 屏幕下方中文字幕
  2) 我说中文：按住 F2 → 麦克风 → whisper(zh) → 翻译成英文 → TTS 送进 VB-Cable → 队友听到
  3) 左下角聊天：截图 → OCR → 逐行翻译 → 同一处字幕
"""
from __future__ import annotations

import os

# 国内下模型走镜像（用户已设置则以用户为准）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

import numpy as np

from . import __version__
from . import capture, winapi
from .asr import WhisperASR
from .config import CONFIG
from .ocr import ChatOCR, LineDiffer, is_player_chat
from .overlay import Overlay
from .translate import VOICE_LINES, Translator
from .tts import TTS

FONT = "Microsoft YaHei UI"


@dataclass
class Job:
    kind: str                 # teammates / me / chat
    pcm: np.ndarray | None = None
    text: str = ""            # chat 已有文本
    t0: float = field(default_factory=time.time)


class App:
    def __init__(self):
        winapi.enable_dpi_awareness()
        winapi.set_low_priority()          # 后台活，别跟游戏抢 CPU
        self.cfg = CONFIG
        self._get = self.cfg.get
        self._set = self.cfg.set
        self.log_lines: list[str] = []

        self.asr = WhisperASR(self._get)
        self.translator = Translator(self._get)
        self.tts = TTS(self._get, log=self.log)
        self.ocr = ChatOCR(self._get)
        self.differ = LineDiffer()

        self.asr_q: queue.Queue[Job] = queue.Queue(maxsize=8)
        self.post_q: queue.Queue[Job] = queue.Queue(maxsize=32)
        self._uiq: queue.Queue = queue.Queue()

        self._sources: dict[str, capture.AudioSource] = {}
        # 开关状态镜像：tkinter 变量只能在主线程读，工作线程一律读这里
        self.flags = {"team": True, "me": True, "chat": True}
        self._seg_team: capture.Segmenter | None = None
        self._seg_me: capture.Segmenter | None = None
        self._me_armed = False
        self._running = False
        self._muted_outgoing = False
        self._chat_stop = threading.Event()
        self._chat_thread: threading.Thread | None = None

        self.hotkeys = winapi.HotkeyWatcher()
        self._build_ui()
        self._bind_hotkeys()

        self.overlay = Overlay(self.root, self._get, self._set)
        if not self._get("overlay.click_through", True):
            self.overlay.bind_drag()

        self.root.after(40, self._pump_ui)
        self.root.after(300, self._autostart)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    # ============================================================ UI
    def _build_ui(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"ValoTalk v{__version__} · 无畏契约实时翻译")
        self.root.geometry("880x780")
        self.root.minsize(780, 640)
        self.root.configure(bg="#11151c")
        if self._get("ui.panel_on_top", True):
            self.root.attributes("-topmost", True)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background="#11151c")
        style.configure("TLabel", background="#11151c", foreground="#dbe4ee",
                        font=(FONT, 10))
        style.configure("Head.TLabel", font=(FONT, 15, "bold"), foreground="#7DD3FC")
        style.configure("Hint.TLabel", foreground="#7f8c9b", font=(FONT, 9))
        style.configure("TCheckbutton", background="#11151c", foreground="#dbe4ee",
                        font=(FONT, 10))
        style.map("TCheckbutton", background=[("active", "#11151c")])
        style.configure("TButton", font=(FONT, 10), padding=6)
        style.configure("Run.TButton", font=(FONT, 11, "bold"))

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x")
        ttk.Label(head, text="ValoTalk", style="Head.TLabel").pack(side="left")
        ttk.Label(head, text=f"v{__version__}", style="Hint.TLabel").pack(
            side="left", padx=(5, 0))
        self.state_lbl = ttk.Label(head, text="● 未启动", foreground="#f87171",
                                   font=(FONT, 11, "bold"))
        self.state_lbl.pack(side="left", padx=12)
        self.meter_lbl = ttk.Label(head, text="", style="Hint.TLabel")
        self.meter_lbl.pack(side="left", padx=4)
        ttk.Label(head, text="模型").pack(side="right", padx=(0, 6))
        self.model_var = tk.StringVar(value=str(self._get("asr.model", "small")))
        cb_model = ttk.Combobox(head, textvariable=self.model_var, width=7, state="readonly",
                                values=["tiny", "base", "small", "medium"])
        cb_model.pack(side="right", padx=(0, 6))
        cb_model.bind("<<ComboboxSelected>>", lambda _e: self._on_model_change())
        ttk.Button(head, text="▶ 开始", style="Run.TButton",
                   command=self.start).pack(side="right", padx=(0, 10))
        ttk.Button(head, text="■ 停止", command=self.stop).pack(side="right", padx=6)

        # ---- 设备 ----
        dev = ttk.LabelFrame(outer, text=" 音频设备 ", padding=10)
        dev.pack(fill="x", pady=(10, 6))
        self.cb_game = self._device_row(dev, 0, "游戏输出（采队友语音）", "audio.game_output_device")
        self.cb_mic = self._device_row(dev, 1, "我的麦克风", "audio.mic_device")
        self.cb_tts = self._device_row(dev, 2, "TTS 输出（VB-Cable Input）",
                                       "audio.tts_output_device")
        row = ttk.Frame(dev)
        row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(row, text="刷新设备", command=self._refresh_devices).pack(side="left")
        ttk.Button(row, text="自动识别", command=self._autofill_devices).pack(side="left", padx=6)
        ttk.Button(row, text="测试 TTS→游戏", command=self._test_tts).pack(side="left", padx=6)
        dev.columnconfigure(1, weight=1)

        # ---- 开关 ----
        sw = ttk.LabelFrame(outer, text=" 功能开关 ", padding=10)
        sw.pack(fill="x", pady=6)
        self.v_team = tk.BooleanVar(value=True)
        self.v_me = tk.BooleanVar(value=True)
        self.v_chat = tk.BooleanVar(value=True)
        self.v_orig = tk.BooleanVar(value=bool(self._get("overlay.show_original", True)))
        self.v_through = tk.BooleanVar(value=bool(self._get("overlay.click_through", True)))
        ttk.Checkbutton(sw, text="队友语音 → 中文字幕", variable=self.v_team,
                        command=lambda: self._set_flag("team", self.v_team.get())
                        ).grid(row=0, column=0, sticky="w", padx=(0, 18))
        self.chk_me = ttk.Checkbutton(
            sw, text=self._me_label(), variable=self.v_me,
            command=lambda: self._set_flag("me", self.v_me.get()))
        self.chk_me.grid(row=0, column=1, sticky="w", padx=(0, 18))
        ttk.Checkbutton(sw, text="左下角聊天翻译", variable=self.v_chat,
                        command=lambda: self._set_flag("chat", self.v_chat.get())
                        ).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(sw, text="字幕显示原文", variable=self.v_orig,
                        command=lambda: self._set("overlay.show_original", self.v_orig.get())
                        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(sw, text="字幕穿透鼠标", variable=self.v_through,
                        command=self._on_through_toggle).grid(row=1, column=1, sticky="w",
                                                              pady=(6, 0))
        self.v_cpu = tk.BooleanVar(value=str(self._get("asr.device", "auto")) == "cpu")
        ttk.Checkbutton(sw, text="识别用 CPU（不抢显卡，稍慢）", variable=self.v_cpu,
                        command=self._on_cpu_toggle).grid(row=2, column=0, sticky="w",
                                                          pady=(6, 0))
        ttk.Button(sw, text="字幕贴回屏幕下方",
                   command=lambda: self.overlay.reset_position()).grid(
            row=1, column=2, sticky="w", pady=(6, 0))

        # ---- 快捷键 ----
        hk = ttk.LabelFrame(outer, text=" 快捷键（改完立刻生效） ", padding=10)
        hk.pack(fill="x", pady=6)
        self.hk_vars: dict[str, tk.StringVar] = {}
        self.hk_combos: dict[str, ttk.Combobox] = {}
        specs = [
            ("ptt", "说中文"),
            ("toggle_click_through", "字幕穿透"),
            ("clear_overlay", "清屏"),
            ("toggle_mute_outgoing", "静音输出"),
        ]
        cur = self._get("hotkeys", {}) or {}
        for i, (key, label) in enumerate(specs):
            ttk.Label(hk, text=label + "：").grid(row=0, column=i * 2, sticky="e",
                                                  padx=(10 if i else 0, 3))
            var = tk.StringVar(value=str(cur.get(key, "")).upper())
            cb = ttk.Combobox(hk, textvariable=var, width=10, state="readonly",
                             values=winapi.HOTKEY_CHOICES)
            cb.grid(row=0, column=i * 2 + 1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_hotkeys())
            self.hk_vars[key] = var
            self.hk_combos[key] = cb

        ttk.Label(hk, text="MOUSE4 / MOUSE5 = 鼠标侧键（后退 / 前进）；"
                           "字母键故意不开放，防止打字时误触",
                  style="Hint.TLabel").grid(row=2, column=0, columnspan=8,
                                            sticky="w", pady=(6, 0))
        ttk.Button(hk, text="检测按键（才知道键盘真正发出什么）",
                   command=self._key_probe).grid(row=1, column=0, columnspan=3,
                                                 sticky="w", pady=(6, 0))

        # ---- 聊天区域 / 翻译后端 ----
        box = ttk.LabelFrame(outer, text=" 聊天区域 & 翻译后端 ", padding=10)
        box.pack(fill="x", pady=6)
        r0 = ttk.Frame(box)
        r0.pack(fill="x")
        ttk.Label(r0, text="聊天框区域：").pack(side="left")
        self.region_lbl = ttk.Label(r0, text="未设置", style="Hint.TLabel")
        self.region_lbl.pack(side="left")
        ttk.Button(r0, text="框选左下角聊天", command=self._pick_region).pack(side="left", padx=10)

        r1 = ttk.Frame(box)
        r1.pack(fill="x", pady=(8, 0))
        ttk.Label(r1, text="翻译：").pack(side="left")
        self.backend = tk.StringVar(value=self._get("translate.backend", "auto"))
        ttk.Combobox(r1, textvariable=self.backend, width=8, state="readonly",
                     values=["auto", "google", "llm"]).pack(side="left")
        self.backend.trace_add("write", lambda *_: self._set(
            "translate.backend", self.backend.get()))
        ttk.Label(r1, text="  LLM base_url：").pack(side="left")
        self.e_base = ttk.Entry(r1, width=26)
        self.e_base.insert(0, self._get("translate.llm.base_url", ""))
        self.e_base.pack(side="left")

        r2 = ttk.Frame(box)
        r2.pack(fill="x", pady=(6, 0))
        ttk.Label(r2, text="model：").pack(side="left")
        self.e_model = ttk.Entry(r2, width=18)
        self.e_model.insert(0, self._get("translate.llm.model", ""))
        self.e_model.pack(side="left")
        ttk.Label(r2, text="  api_key：").pack(side="left")
        self.e_key = ttk.Entry(r2, width=30, show="*")
        self.e_key.insert(0, self._get("translate.llm.api_key", ""))
        self.e_key.pack(side="left")
        ttk.Button(r2, text="保存", command=self._save_llm).pack(side="left", padx=8)

        # ---- 日志 ----
        lg = ttk.LabelFrame(outer, text=" 运行日志 ", padding=8)
        lg.pack(fill="both", expand=True, pady=(6, 0))
        self.txt = tk.Text(lg, height=14, bg="#0b0f14", fg="#cbd5e1", insertbackground="#fff",
                           font=("Consolas", 9), relief="flat", wrap="word")
        self.txt.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lg, command=self.txt.yview)
        sb.pack(side="right", fill="y")
        self.txt.configure(yscrollcommand=sb.set)
        self.txt.configure(state="disabled")

        self._refresh_devices(initial=True)

    def _device_row(self, parent, row: int, label: str, key: str) -> ttk.Combobox:
        ttk.Label(parent, text=label + "：").grid(row=row, column=0, sticky="w", pady=2)
        cb = ttk.Combobox(parent, width=52, state="readonly")
        cb.grid(row=row, column=1, sticky="ew", padx=8, pady=2)
        cb.set(self._get(key, "") or "")
        cb.bind("<<ComboboxSelected>>", lambda _e, k=key, c=cb: self._set(k, c.get()))
        ttk.Label(parent, text="").grid(row=row, column=2)
        return cb

    # ============================================================ 设备
    def _on_model_change(self) -> None:
        size = self.model_var.get()
        self._set("asr.model", size)
        # 换模型必须重建（旧模型还占着内存）
        self.asr._model = None
        self.asr.loaded = False
        import valotalk.asr as asr_mod
        asr_mod._MODEL = None
        asr_mod._MODEL_KEY = None
        self.log(f"模型切换为 {size}，下次识别时重新加载")
        threading.Thread(
            target=lambda: self.asr.ensure_loaded(
                on_status=lambda s: self.log(f"[模型] {s}")),
            daemon=True,
        ).start()

    def _me_label(self) -> str:
        """跟着当前触发键走，改成鼠标侧键后这里也显示 MOUSE4。"""
        key = str(self._get("hotkeys.ptt", "f2") or "f2").upper()
        return f"我说中文 → 英文语音（按住 {key}）"

    def _refresh_me_label(self) -> None:
        try:
            self.chk_me.configure(text=self._me_label())
        except Exception:
            pass

    def _on_cpu_toggle(self) -> None:
        """显卡紧张时完全退出 GPU：识别改走 CPU。"""
        dev = "cpu" if self.v_cpu.get() else "auto"
        self._set("asr.device", dev)
        self.log(f"识别设备切换为 {dev}，重新加载模型 …")
        if dev == "cpu":
            self.log("  提示：CPU 上 small 很慢（RTF≈1.8），建议把右上角模型改成 base 或 tiny")

        def reload():
            self.asr._model = None
            self.asr.loaded = False
            import valotalk.asr as asr_mod
            asr_mod._MODEL = None
            asr_mod._MODEL_KEY = None
            self.asr.ensure_loaded(on_status=lambda s: self.log(f"[模型] {s}"))

        threading.Thread(target=reload, daemon=True).start()

    def _key_probe(self) -> None:
        """按住任意键，看键盘到底发出什么虚拟键码。用来确认 Fn 组合的真实行为。"""
        top = tk.Toplevel(self.root)
        top.title("按键检测")
        top.geometry("420x180")
        top.attributes("-topmost", True)
        ttk.Label(top, text="按住你想用的那个键（含 Fn 组合），下面是实际键码",
                  font=(FONT, 10)).pack(pady=(14, 6))
        big = ttk.Label(top, text="等待按键…", font=(FONT, 16, "bold"),
                        foreground="#7DD3FC")
        big.pack(pady=6)
        hint = ttk.Label(top, text="", style="Hint.TLabel")
        hint.pack(pady=4)

        names = {v: k.upper() for k, v in winapi.VK.items()}
        deadline = time.time() + 20
        last_vk = 0

        def poll():
            nonlocal last_vk
            if not top.winfo_exists():
                return
            if time.time() > deadline:
                big.configure(text="超时，已停止")
                return
            for vk in range(0x01, 0xFF):
                if winapi.user32.GetAsyncKeyState(vk) & 0x8000:
                    if vk != last_vk:
                        last_vk = vk
                        name = names.get(vk, "?")
                        big.configure(text=f"VK 0x{vk:02X}   ({name})")
                        if vk == 0x71:
                            hint.configure(text="这就是 F2，程序能识别 ✓")
                        elif vk == 0x32:
                            hint.configure(text="这是数字 2 ！键盘没发出 F2 —— "
                                                "游戏会切枪，程序也认不到")
                        elif 0x70 <= vk <= 0x7B:
                            hint.configure(text="F 区键，可以选")
                        elif vk in (0x05, 0x06):
                            hint.configure(text="鼠标侧键，推荐用在 FPS 里")
                        else:
                            hint.configure(text="")
                    break
                last_vk = 0 if last_vk == vk else last_vk
            top.after(25, poll)

        ttk.Button(top, text="关闭", command=top.destroy).pack(pady=6)
        poll()

    def _set_flag(self, name: str, value: bool) -> None:
        self.flags[name] = bool(value)
        self.log(f"开关 {name} → {'开' if value else '关'}")

    def _refresh_devices(self, initial: bool = False) -> None:
        outs = [d["name"] for d in capture.list_outputs()]
        ins = [d["name"] for d in capture.list_inputs()]
        self.cb_game["values"] = outs
        self.cb_tts["values"] = outs
        self.cb_mic["values"] = ins
        if initial:
            self._autofill_devices(quiet=True)
        self.log(f"设备：{len(outs)} 个输出 / {len(ins)} 个输入")

    def _autofill_devices(self, quiet: bool = False) -> None:
        if not self._get("audio.game_output_device"):
            name = capture.guess_game_output()
            if name:
                self._set("audio.game_output_device", name, save=False)
                self.cb_game.set(name)
        if not self._get("audio.mic_device"):
            ins = capture.list_inputs()
            if ins:
                self._set("audio.mic_device", ins[0]["name"], save=False)
                self.cb_mic.set(ins[0]["name"])
        if not self._get("audio.tts_output_device"):
            name = capture.guess_tts_output()
            if name:
                self._set("audio.tts_output_device", name, save=False)
                self.cb_tts.set(name)
        self.cfg.save()
        if not quiet:
            self.log("已自动识别设备，可在上面手动改。")

    def _save_llm(self) -> None:
        self._set("translate.llm.base_url", self.e_base.get().strip())
        self._set("translate.llm.model", self.e_model.get().strip())
        self._set("translate.llm.api_key", self.e_key.get().strip())
        self.log("LLM 配置已保存，正在自测 …")
        threading.Thread(target=self._test_translate, daemon=True).start()

    def _test_translate(self) -> None:
        self.translator._setup_proxy()
        try:
            out = self.translator.translate(
                "Rush B, plant the spike behind the box.", "en", "zh-CN")
            zh = self.translator.translate("掩护我，我要开大了", "zh", "en")
        except Exception as exc:
            self.log(f"[翻译自测] 异常: {exc}")
            return
        which = self.translator.backend_used
        if out:
            self.log(f"[翻译自测] 通道={which}")
            self.log(f"   英→中: {out}")
            self.log(f"   中→英: {zh}")
            if which != "llm":
                self.log("   注：没走 LLM —— 检查 base_url 是否以 /v1 结尾、model 名、api_key")
        else:
            self.log(f"[翻译自测] 全部失败: {self.translator.last_error}")

    def _on_through_toggle(self) -> None:
        self.overlay.set_click_through(self.v_through.get())
        if not self.v_through.get():
            self.overlay.bind_drag()

    # ============================================================ 热键
    def _apply_hotkeys(self) -> None:
        """界面改了快捷键后立即重建绑定，不用重启。"""
        hk = {k: (v.get() or "").strip().lower() for k, v in self.hk_vars.items()}
        if not all(hk.values()):
            self.log("[快捷键] 有键位为空，已忽略本次修改")
            return
        vals = list(hk.values())
        dup = sorted({v for v in vals if vals.count(v) > 1})
        if dup:
            self.log(f"[快捷键] {', '.join(k.upper() for k in dup)} 被重复绑定，已忽略")
            return
        if "v" in vals:
            self.log("[快捷键] V 是游戏开麦键，占用会冲突，已忽略")
            return
        for k, v in hk.items():
            self._set("hotkeys." + k, v, save=False)
        self.cfg.save()
        self._bind_hotkeys()
        self._refresh_me_label()
        self.log("快捷键已更新：" + "  ".join(f"{k} → {v.upper()}" for k, v in hk.items()))
        self._ui_state(self.state_lbl.cget("text"), self.state_lbl.cget("foreground"))

    def _bind_hotkeys(self) -> None:
        self.hotkeys.reset()
        hk = self._get("hotkeys", {}) or {}
        self.hotkeys.bind("ptt", hk.get("ptt", "f2"),
                          on_press=self._ptt_down, on_release=self._ptt_up)
        self.hotkeys.bind("through", hk.get("toggle_click_through", "f3"),
                          on_press=self._toggle_through_hotkey)
        self.hotkeys.bind("clear", hk.get("clear_overlay", "f4"),
                          on_press=lambda: self.overlay.clear())
        self.hotkeys.bind("mute", hk.get("toggle_mute_outgoing", "f5"),
                          on_press=self._toggle_mute_outgoing)
        self.hotkeys.start()

    def _ptt_down(self) -> None:
        self._me_armed = True
        self._ui_state("● 正在听你说…", "#fbbf24")

    def _ptt_up(self) -> None:
        self._me_armed = False
        seg = self._seg_me.flush() if self._seg_me else None
        if seg is not None and self.flags["me"] and not self._muted_outgoing:
            self._submit_asr("me", seg)
        self._ui_state("● 运行中", "#34d399")

    def _toggle_through_hotkey(self) -> None:
        self.root.after(0, lambda: (self.v_through.set(not self.v_through.get()),
                                    self._on_through_toggle()))

    def _toggle_mute_outgoing(self) -> None:
        self._muted_outgoing = not self._muted_outgoing
        self.log("英文语音输出：" + ("已暂停" if self._muted_outgoing else "已恢复"))

    # ============================================================ 启停
    def _autostart(self) -> None:
        self.start()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.differ.reset()
        self._ui_state("● 启动中…", "#fbbf24")

        threading.Thread(target=self._boot_bg, daemon=True).start()
        threading.Thread(target=self._asr_worker, name="asr-worker", daemon=True).start()
        threading.Thread(target=self._post_worker, name="post-worker", daemon=True).start()
        self._start_chat_loop()

    def _boot_bg(self) -> None:
        # 1) 模型
        ok = self.asr.ensure_loaded(on_status=lambda s: self.log(f"[模型] {s}"))
        if not ok:
            self.log("[模型] 加载失败：" + (self.asr.load_error or ""))
            self.log("       先跑 setup.ps1 装依赖，或把 asr.model 改小（base/tiny）。")
        # 2) 采集
        self._start_capture()
        # 3) 常用喊话的英文语音先合成好，游戏里命中时零延迟
        self.tts.warmup(sorted(set(VOICE_LINES.values())))
        self._ui_state("● 运行中", "#34d399")

    def _make_segmenter(self, vad: dict):
        """优先 Silero（能区分人声和音效），不可用才退回能量 VAD。"""
        seg = capture.SileroSegmenter(vad)
        if getattr(seg, "ok", False):
            self.log("断句: Silero VAD（只把人声送去做识别）")
            return seg
        self.log("断句: Silero 不可用，退回能量 VAD —— 背景音大时会失准")
        return capture.Segmenter(vad)

    def _start_capture(self) -> None:
        game_dev = self._get("audio.game_output_device", "")
        mic_dev = self._get("audio.mic_device", "")
        sr = int(self._get("audio.capture_samplerate", 48000) or 48000)
        block = int(self._get("audio.block_ms", 30) or 30)
        vad = self._get("audio.vad", {}) or {}

        if game_dev:
            self._seg_team = self._make_segmenter(vad)
            src = capture.AudioSource(game_dev, True, sr, block, self._on_team_audio,
                                      label="game")
            src.start()
            self._sources["game"] = src
            self.log(f"采集队友语音：{game_dev}" + (f"（{src.error}）" if src.error else ""))
        else:
            self.log("未设置游戏输出设备，队友语音字幕不会工作。")

        if mic_dev:
            self._seg_me = self._make_segmenter(vad)
            src = capture.AudioSource(mic_dev, False, sr, block, self._on_mic_audio,
                                      label="mic")
            src.start()
            self._sources["mic"] = src
            self.log(f"采集麦克风：{mic_dev}" + (f"（{src.error}）" if src.error else ""))

        self.log(f"英文语音输出设备：{self._get('audio.tts_output_device', '(未设置)')}")

    def stop(self) -> None:
        self._running = False
        for src in self._sources.values():
            src.stop()
        self._sources.clear()
        self._chat_stop.set()
        self._ui_state("● 已停止", "#f87171")
        self.log("已停止采集。")

    def shutdown(self) -> None:
        try:
            self.stop()
            self.hotkeys.stop()
            self._set("overlay.x", self.overlay.x, save=False)
            self._set("overlay.y", self.overlay.y, save=True)
        except Exception:
            pass
        self.root.destroy()

    # ============================================================ 采集回调
    def _on_team_audio(self, pcm: np.ndarray) -> None:
        if not self.flags["team"] or self._seg_team is None:
            return
        for seg in self._seg_team.feed(pcm):
            self._submit_asr("teammates", seg)

    def _on_mic_audio(self, pcm: np.ndarray) -> None:
        if self._seg_me is None:
            return
        for seg in self._seg_me.feed(pcm):
            if not self._me_armed or not self.flags["me"]:
                continue
            if self._muted_outgoing:
                continue
            self._submit_asr("me", seg)

    def _submit_asr(self, kind: str, pcm: np.ndarray) -> None:
        job = Job(kind=kind, pcm=pcm)
        try:
            self.asr_q.put_nowait(job)
        except queue.Full:
            try:
                self.asr_q.get_nowait()
                self.asr_q.put_nowait(job)
            except Exception:
                pass

    # ============================================================ 工作线程
    def _asr_worker(self) -> None:
        while True:
            try:
                job = self.asr_q.get()
            except Exception:
                continue
            if job is None:
                continue
            # 模型失效（比如 CUDA 库缺失）时按节奏重试，不要每句都炸
            if not self.asr.loaded and not self._reload_asr():
                continue
            lang = (self._get("asr.lang_teammates", "en") if job.kind == "teammates"
                    else self._get("asr.lang_me", "zh"))
            try:
                text = self.asr.transcribe(job.pcm, lang)
            except Exception as exc:
                self.log(f"[识别异常] {exc}")
                continue
            if not text:
                continue
            job.text = text
            try:
                self.post_q.put_nowait(job)
            except queue.Full:
                try:
                    self.post_q.get_nowait()
                    self.post_q.put_nowait(job)
                except Exception:
                    pass

    def _reload_asr(self) -> bool:
        """失效后重建，最多每 10 秒试一次。"""
        now = time.time()
        if now - getattr(self, "_asr_retry_at", 0) < 10:
            return False
        self._asr_retry_at = now
        self.log("[模型] 重新加载 …")
        ok = self.asr.ensure_loaded(on_status=lambda s: self.log(f"[模型] {s}"))
        if ok:
            self.log("[模型] 已恢复")
        else:
            self.log("[模型] 仍失败：" + (self.asr.load_error or "") + self.asr._load_error_hint())
        return ok

    def _post_worker(self) -> None:
        while True:
            try:
                job = self.post_q.get()
            except Exception:
                continue
            try:
                self._dispatch(job)
            except Exception as exc:
                self.log(f"[处理异常] {exc}")

    def _dispatch(self, job: Job) -> None:
        if job.kind == "teammates":
            if not self.flags["team"]:
                return
            zh = self.translator.translate(job.text, "en", "zh-CN")
            shown = zh or "（翻译失败）" + job.text
            self.log(f"队友：{job.text} → {zh}")
            self._overlay("队友", shown, job.text if zh else "")
        elif job.kind == "me":
            if not self.flags["me"] or self._muted_outgoing:
                return
            en = self.translator.translate(job.text, "zh", "en")
            if not en:
                self.log(f"[翻译失败] {job.text}")
                return
            self.log(f"我：{job.text} → {en}")
            self._overlay("我", en, job.text)
            self.tts.speak(en)
        elif job.kind == "chat":
            if not self.flags["chat"] or not job.text:
                return
            zh = self.translator.translate(job.text, "en", "zh-CN")
            self.log(f"聊天：{job.text} → {zh or '（失败）'}")
            self._overlay("聊天", zh or job.text, job.text if zh else "")

    # ============================================================ 聊天 OCR
    def _start_chat_loop(self) -> None:
        if self._chat_thread and self._chat_thread.is_alive():
            return
        self._chat_stop.clear()
        self._chat_thread = threading.Thread(target=self._chat_loop, name="chat-ocr",
                                             daemon=True)
        self._chat_thread.start()

    def _chat_loop(self) -> None:
        miss = 0
        while not self._chat_stop.is_set():
            interval = max(400, int(self._get("ocr.interval_ms", 1200) or 1200))
            region = self._get("ocr.region", [0, 0, 0, 0])
            if not self.flags["chat"] or not region or region[2] <= region[0]:
                time.sleep(0.4)
                continue
            img = self.ocr.grab(region)
            if img is None:
                miss += 1
                if miss in (10, 60):
                    self.log(f"[聊天OCR] {self.ocr.last_error}")
                time.sleep(interval / 1000.0)
                continue
            miss = 0
            lines = self.ocr.read_lines(img)
            fresh = self.differ.push(lines)
            # 只翻玩家说的话；系统广播（下包/回合/上线提示）整行无视
            fresh = [ln for ln in fresh if is_player_chat(ln)]
            for ln in fresh[:4]:
                try:
                    self.post_q.put_nowait(Job(kind="chat", text=ln))
                except queue.Full:
                    break
            time.sleep(interval / 1000.0)

    def _pick_region(self) -> None:
        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-alpha", 0.30)
        top.attributes("-topmost", True)
        top.configure(bg="black")
        top.config(cursor="crosshair")
        cv = tk.Canvas(top, bg="black", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        cv.create_text(
            top.winfo_screenwidth() // 2, 60,
            text="拖一个框住左下角聊天框的矩形（Esc 取消）",
            fill="#7DD3FC", font=(FONT, 26, "bold"),
        )
        state = {"sx": 0, "sy": 0, "cx": 0, "cy": 0, "rect": None}

        def press(e):
            state["sx"], state["sy"] = e.x_root, e.y_root
            state["cx"], state["cy"] = e.x, e.y
            state["rect"] = cv.create_rectangle(e.x, e.y, e.x, e.y,
                                                outline="#34d399", width=3)

        def drag(e):
            if state["rect"]:
                cv.coords(state["rect"], state["cx"], state["cy"], e.x, e.y)

        def release(e):
            x1, y1 = min(state["sx"], e.x_root), min(state["sy"], e.y_root)
            x2, y2 = max(state["sx"], e.x_root), max(state["sy"], e.y_root)
            if x2 - x1 > 40 and y2 - y1 > 30:
                self._set("ocr.region", [int(x1), int(y1), int(x2), int(y2)])
                self._update_region_label()
                self.differ.reset()
                self.log(f"聊天区域已设置：({x1},{y1}) - ({x2},{y2})")
            top.destroy()

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", drag)
        cv.bind("<ButtonRelease-1>", release)
        top.bind("<Escape>", lambda _e: top.destroy())

    def _update_region_label(self) -> None:
        r = self._get("ocr.region", [0, 0, 0, 0]) or [0, 0, 0, 0]
        if r[2] > r[0]:
            self.region_lbl.configure(
                text=f"{r[0]},{r[1]} → {r[2]},{r[3]}（{r[2]-r[0]}×{r[3]-r[1]}）")
        else:
            self.region_lbl.configure(text="未设置")

    # ============================================================ 小工具
    def _test_tts(self) -> None:
        self.log("TTS 测试：I am rotating to B site, watch the flank.")

        def run():
            ok = self.tts.speak("I am rotating to B site, watch the flank.")
            self.log("TTS 测试" + ("成功（游戏应能听到）" if ok else
                                   "失败：" + (self.tts.last_error or "未知")))

        threading.Thread(target=run, daemon=True).start()

    def _overlay(self, tag: str, text: str, original: str = "") -> None:
        self._ui_call(self.overlay, "add", tag, text, original)

    def _ui_state(self, text: str, color: str) -> None:
        def apply():
            self.state_lbl.configure(text=text, foreground=color)
        self._uiq.put(apply)

    def _ui_call(self, obj, method: str, *args) -> None:
        def apply():
            try:
                getattr(obj, method)(*args)
            except Exception:
                pass
        self._uiq.put(apply)

    def _pump_ui(self) -> None:
        for _ in range(40):
            try:
                fn = self._uiq.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass
        # 采集电平：一眼看出有没有真的在收声音。
        # 200ms 刷一次即可 —— 40ms 一次等于每秒重排 25 次界面，白占资源
        now = time.time()
        if now - getattr(self, "_last_meter", 0.0) > 0.2:
            self._last_meter = now
            try:
                game = self._sources.get("game")
                mic = self._sources.get("mic")
                bar = ""
                for name, src in (("游戏", game), ("麦", mic)):
                    if src is None:
                        bar += f"{name} —  "
                    else:
                        p = src.peak
                        n = 0 if p < 0.005 else (1 if p < 0.02 else 2 if p < 0.06
                                                 else 3 if p < 0.15 else 4)
                        bar += f"{name} {'▁▃▅▇█'[n]}  "
                self.meter_lbl.configure(text=bar)
            except Exception:
                pass
        self.root.after(40, self._pump_ui)

    def log(self, msg: str) -> None:
        line = time.strftime("%H:%M:%S ") + str(msg)
        self.log_lines.append(line)
        if len(self.log_lines) > 800:
            self.log_lines = self.log_lines[-500:]

        def apply():
            try:
                self.txt.configure(state="normal")
                self.txt.insert("end", line + "\n")
                self.txt.see("end")
                self.txt.configure(state="disabled")
            except Exception:
                pass

        self._uiq.put(apply)
        try:
            print(line, flush=True)
        except Exception:
            pass

    # ============================================================ 主循环
    def run(self) -> None:
        self._update_region_label()
        self.log("ValoTalk 启动。F2=按住说中文  F3=字幕穿透  F4=清屏  F5=静音英文输出")
        self.root.mainloop()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()