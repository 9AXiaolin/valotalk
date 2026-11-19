"""Windows 原生交互：全局热键轮询、按键注入、窗口样式。

零第三方依赖，全部走 ctypes：不装键盘钩子，避免与游戏输入层互相干扰。
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# ---------------- 按键常量 ----------------
VK = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "capslock": 0x14, "tab": 0x09, "space": 0x20, "enter": 0x0D, "esc": 0x1B,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "delete": 0x2E,
    "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA,
    "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)

# 界面上可选的热键（避开字母，免得打字时误触；V 留给游戏开麦）
HOTKEY_CHOICES = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "CAPSLOCK", "TAB", "INSERT", "HOME", "END", "DELETE", "PAGEUP", "PAGEDOWN",
    "`",
]


def vk_of(name: str) -> int:
    key = (name or "").strip().lower()
    if key in VK:
        return VK[key]
    if len(key) == 1:
        return ord(key.upper())
    raise KeyError(f"未知按键: {name}")


# ---------------- 按键注入 ----------------
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008


def _send_key(vk: int, up: bool) -> None:
    scan = user32.MapVirtualKeyW(vk, 0)
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = _KEYBDINPUT(
        wVk=0, wScan=scan,
        dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0),
        time=0, dwExtraInfo=None,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def key_down(name: str) -> None:
    try:
        _send_key(vk_of(name), up=False)
    except Exception:
        pass


def key_up(name: str) -> None:
    try:
        _send_key(vk_of(name), up=True)
    except Exception:
        pass


class VirtualKeyHold:
    """按住某个键一段时间（用于游戏内语音键）。支持重入计数。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self._key = ""

    def acquire(self, key: str) -> None:
        with self._lock:
            if not key:
                return
            if self._count == 0:
                self._key = key
                key_down(key)
            self._count += 1

    def release(self, settle_ms: int = 0) -> None:
        with self._lock:
            if self._count <= 0:
                return
            self._count -= 1
            if self._count == 0 and self._key:
                if settle_ms > 0:
                    time.sleep(settle_ms / 1000.0)
                key_up(self._key)


# ---------------- 热键轮询 ----------------
class HotkeyWatcher:
    """轮询 GetAsyncKeyState，检测按下/松开边沿。"""

    def __init__(self, poll_ms: int = 25):
        self.poll_ms = poll_ms
        self._bindings: dict[str, int] = {}
        self._on_press: dict[str, callable] = {}
        self._on_release: dict[str, callable] = {}
        self._state: dict[str, bool] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def bind(self, action: str, key: str, on_press=None, on_release=None) -> None:
        if not key:
            return
        try:
            self._bindings[action] = vk_of(key)
        except KeyError:
            return
        if on_press:
            self._on_press[action] = on_press
        if on_release:
            self._on_release[action] = on_release
        self._state[action] = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="hotkeys", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.0)
        self._thread = None

    def reset(self) -> None:
        """清空所有绑定，用于界面上改键后重建。"""
        self.stop()
        self._bindings.clear()
        self._on_press.clear()
        self._on_release.clear()
        self._state.clear()

    def _loop(self) -> None:
        while not self._stop.is_set():
            for action, vk in list(self._bindings.items()):
                down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                was = self._state.get(action, False)
                if down and not was:
                    self._state[action] = True
                    cb = self._on_press.get(action)
                    if cb:
                        threading.Thread(target=_safe, args=(cb,), daemon=True).start()
                elif not down and was:
                    self._state[action] = False
                    cb = self._on_release.get(action)
                    if cb:
                        threading.Thread(target=_safe, args=(cb,), daemon=True).start()
            time.sleep(self.poll_ms / 1000.0)


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        pass


# ---------------- 窗口样式 ----------------
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


def top_level_hwnd(tk_widget) -> int:
    """tkinter 的 winfo_id 只给出子窗口，取父窗口才是真顶层。"""
    hwnd = tk_widget.winfo_id()
    parent = user32.GetParent(hwnd)
    return parent or hwnd


def set_click_through(hwnd: int, enabled: bool) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    base = style | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    new_style = (base | WS_EX_TRANSPARENT) if enabled else (base & ~WS_EX_TRANSPARENT)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def keep_topmost(hwnd: int) -> None:
    HWND_TOPMOST = -1
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def enable_dpi_awareness() -> None:
    """避免在高 DPI / 全屏下截图坐标错位。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_PRIORITY_CLASS = 0x00000040


def set_low_priority() -> bool:
    """把自身降到「低于正常」，让游戏优先拿到 CPU 时间片。

    实时翻译是个后台活，晚几十毫秒无所谓；游戏掉帧才是大问题。
    """
    try:
        k32 = ctypes.WinDLL("kernel32")
        h = k32.GetCurrentProcess()
        return bool(k32.SetPriorityClass(h, BELOW_NORMAL_PRIORITY_CLASS))
    except Exception:
        return False