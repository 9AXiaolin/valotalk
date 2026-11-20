"""Windows 原生交互：全局热键轮询、按键注入、窗口样式。

零第三方依赖，全部走 ctypes：不装键盘钩子，避免与游戏输入层互相干扰。
"""
from __future__ import annotations

import ctypes
import threading
import time
from collections import deque
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

# 鼠标侧键（后退/前进）。左右中键故意不给 —— 会干扰正常点击。
# GetAsyncKeyState 能直接读到这两个键的状态，所以当热键用是安全的。
VK["mouse4"] = 0x05      # XBUTTON1 侧键（后退）
VK["mouse5"] = 0x06      # XBUTTON2 侧键（前进）
MOUSE_KEYS = {0x05: 0x0001, 0x06: 0x0002}   # vk -> XBUTTON 标识

# 界面上可选的热键（避开字母，免得打字时误触；V 留给游戏开麦）
HOTKEY_CHOICES = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "CAPSLOCK", "TAB", "INSERT", "HOME", "END", "DELETE", "PAGEUP", "PAGEDOWN",
    "MOUSE4", "MOUSE5", "`",
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
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100


def _send_key(vk: int, up: bool) -> None:
    scan = user32.MapVirtualKeyW(vk, 0)
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = _KEYBDINPUT(
        wVk=0, wScan=scan,
        dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0),
        time=0, dwExtraInfo=None,
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_xbutton(xbutton: int, up: bool) -> None:
    """模拟鼠标侧键（游戏的语音键也可以绑侧键）。"""
    inp = _INPUT(type=INPUT_MOUSE)
    mi = _MOUSEINPUT()
    mi.dx = 0
    mi.dy = 0
    mi.mouseData = xbutton
    mi.dwFlags = MOUSEEVENTF_XUP if up else MOUSEEVENTF_XDOWN
    mi.time = 0
    mi.dwExtraInfo = None
    inp.union.mi = mi
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def key_down(name: str) -> None:
    try:
        vk = vk_of(name)
        if vk in MOUSE_KEYS:
            _send_xbutton(MOUSE_KEYS[vk], up=False)
        else:
            _send_key(vk, up=False)
    except Exception:
        pass


def key_up(name: str) -> None:
    try:
        vk = vk_of(name)
        if vk in MOUSE_KEYS:
            _send_xbutton(MOUSE_KEYS[vk], up=True)
        else:
            _send_key(vk, up=True)
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
# 低级鼠标钩子：GetAsyncKeyState 对 XBUTTON1/2 不可靠（微软文档说它主要管键盘），
# 游戏里按侧键基本读不到。WH_MOUSE_LL 是系统级钩子，在 Raw Input 之前就能拿到事件。
WH_MOUSE_LL = 14
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_QUIT = 0x0012


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


_LowLevelMouseProc = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# 显式声明签名：不声明的话 64 位 LPARAM 会被当成 32 位 int，溢出报错
try:
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _LowLevelMouseProc,
                                         wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE
    user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                      wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                   wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = ctypes.c_int
except Exception:
    pass


class MouseHook:
    """捕获鼠标侧键（XBUTTON1/2），游戏独占输入时也能拿到。

    ⚠ 低级钩子的回调运行在系统输入链路上：Windows 必须等它返回才继续派发鼠标事件。
    所以回调里只能做「往队列塞一个元组」这种微秒级操作 —— 一旦在里面创建线程或
    调用重逻辑，GIL 被别的线程占住时就会**卡死整个系统的鼠标**。
    真正的处理交给 HotkeyWatcher 的轮询线程消费 self._queue。
    """

    def __init__(self):
        self._proc = None
        self._hook = 0
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._handlers: dict[int, tuple] = {}   # vk -> (on_press, on_release)
        self._queue: deque = deque(maxlen=256)
        self.error: str | None = None
        self.dropped = 0

    def bind(self, vk: int, on_press=None, on_release=None) -> None:
        self._handlers[vk] = (on_press, on_release)

    def drain(self) -> list[tuple[int, bool]]:
        """由轮询线程调用，取走回调塞进来的事件。"""
        out: list[tuple[int, bool]] = []
        while True:
            try:
                out.append(self._queue.popleft())
            except IndexError:
                break
        return out

    def start(self) -> bool:
        if not self._handlers:
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._thread = threading.Thread(target=self._run, name="mouse-hook", daemon=True)
        self._thread.start()
        time.sleep(0.05)
        return bool(self._hook)

    def stop(self) -> None:
        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = 0
        if self._tid:
            try:
                user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except Exception:
                pass
        self._thread = None

    def _run(self) -> None:
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        self._proc = _LowLevelMouseProc(self._callback)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        if not self._hook:
            self.error = f"SetWindowsHookEx 失败 err={ctypes.get_last_error()}"
            return
        msg = wintypes.MSG()
        # 消息循环，钩子靠它活着。必须用 > 0：GetMessage 返回 -1 是错误
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _callback(self, n_code, w_param, l_param):
        # ★ 系统输入链路上执行：这里只允许塞队列，绝不创建线程、不做字符串处理
        if n_code >= 0 and w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                which = (info.mouseData >> 16) & 0xFFFF   # XBUTTON1=1, XBUTTON2=2
                if which == 1 or which == 2:
                    if len(self._queue) >= self._queue.maxlen:
                        self.dropped += 1
                    self._queue.append((0x05 if which == 1 else 0x06,
                                        w_param == WM_XBUTTONDOWN))
            except Exception:
                pass
        return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)


class HotkeyWatcher:
    """键盘走 GetAsyncKeyState 轮询，鼠标侧键走低级钩子。"""

    def __init__(self, poll_ms: int = 25):
        self.poll_ms = poll_ms
        self._bindings: dict[str, int] = {}
        self._on_press: dict[str, callable] = {}
        self._on_release: dict[str, callable] = {}
        self._state: dict[str, bool] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.mouse_hook = MouseHook()
        self._mouse_label_map: dict[int, str] = {}

    def bind(self, action: str, key: str, on_press=None, on_release=None) -> None:
        if not key:
            return
        try:
            vk = vk_of(key)
        except KeyError:
            return
        if vk in MOUSE_KEYS:
            # 鼠标键不进轮询表，交给钩子
            self.mouse_hook.bind(vk, on_press, on_release)
            self._mouse_labels[vk] = action
            return
        self._bindings[action] = vk
        if on_press:
            self._on_press[action] = on_press
        if on_release:
            self._on_release[action] = on_release
        self._state[action] = False

    @property
    def _mouse_labels(self) -> dict[int, str]:
        return self._mouse_label_map

    def start(self) -> None:
        # 只要有键盘绑定或鼠标钩子，就需要轮询线程（鼠标队列也靠它消费）
        if (self._bindings or self.mouse_hook._handlers) and not (
                self._thread and self._thread.is_alive()):
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="hotkeys", daemon=True)
            self._thread.start()
        if self.mouse_hook._handlers:
            self.mouse_hook.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.0)
        self._thread = None
        self.mouse_hook.stop()

    def reset(self) -> None:
        """清空所有绑定，用于界面上改键后重建。"""
        self.stop()
        self._bindings.clear()
        self._on_press.clear()
        self._on_release.clear()
        self._state.clear()
        self._mouse_labels.clear()
        self.mouse_hook = MouseHook()

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
            # 消费鼠标钩子塞进来的事件（绝不能在钩子回调里做这件事）
            try:
                _dispatch_mouse_events(self)
            except Exception:
                pass
            time.sleep(self.poll_ms / 1000.0)


def _safe(fn) -> None:
    try:
        fn()
    except Exception:
        pass


def _dispatch_mouse_events(watcher: "HotkeyWatcher") -> None:
    """在轮询线程里消费钩子队列，避免在系统输入链路上做事。"""
    hook = watcher.mouse_hook
    for vk, down in hook.drain():
        pair = hook._handlers.get(vk)
        if not pair:
            continue
        cb = pair[0] if down else pair[1]
        if cb:
            threading.Thread(target=_safe, args=(cb,), daemon=True).start()


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

# Windows 11 的窗口圆角
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


def set_rounded_window(hwnd: int, mode: int = DWMWCP_ROUND) -> bool:
    """让窗口四角变圆（Windows 11）。Win10 上会失败，忽略即可。"""
    try:
        dwm = ctypes.WinDLL("dwmapi")
        val = ctypes.c_int(mode)
        r = dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                      ctypes.byref(val), ctypes.sizeof(val))
        return r == 0
    except Exception:
        return False


def set_dark_titlebar(hwnd: int, dark: bool = True) -> bool:
    """标题栏深色（Win11 / 新版 Win10）。"""
    try:
        dwm = ctypes.WinDLL("dwmapi")
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1 if dark else 0)
        r = dwm.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                      ctypes.byref(val), ctypes.sizeof(val))
        return r == 0
    except Exception:
        return False


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