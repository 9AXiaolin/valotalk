"""验证「我们自己模拟按键」到底行不行 —— 用一个同级窗口当靶子。

背景：游戏（VALORANT.exe）跑在 High 完整性级别，本程序是 Medium。
Windows 的 UIPI 会**静默丢弃** Medium → High 的 SendInput，
而 SendInput 的返回值照样是 1，所以在程序里完全看不出失败。

这个脚本把靶子换成本进程自己的 Tk 窗口（同为 Medium）：
- 收到注入的 V  → 注入代码本身没问题，问题就是 UIPI/权限
- 收不到         → 注入代码有 bug

跑：D:\\python\\python.exe -X utf8 tools\\keyinject_selftest.py
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32")
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                            ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32.GetCurrentProcessId.restype = wintypes.DWORD

VK_V = 0x56
received: list[str] = []
info = {"fg_before": 0, "fg_after": 0, "mine": 0}


def fg_pid() -> int:
    h = user32.GetForegroundWindow()
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return int(p.value)


def main() -> int:
    root = tk.Tk()
    root.title("按键注入自测 · 别碰键盘")
    root.geometry("460x230+300+300")
    root.configure(bg="#1C1C1E")
    root.attributes("-topmost", True)

    lbl = tk.Label(root, text="准备中…", bg="#1C1C1E", fg="#FFFFFF",
                   font=("Microsoft YaHei UI", 13, "bold"),
                   wraplength=420, justify="center")
    lbl.pack(expand=True, padx=20, pady=20)

    root.bind("<KeyPress>", lambda ev: (
        received.append(str(ev.keysym)),
        lbl.configure(text=f"收到按键：{ev.keysym}", fg="#30D158")))

    my_pid = int(kernel32.GetCurrentProcessId())

    def run_test():
        root.lift()
        root.focus_force()
        root.update()
        time.sleep(0.3)
        root.update()
        info["mine"] = my_pid
        info["fg_before"] = fg_pid()
        focus_ok = info["fg_before"] == my_pid

        lbl.configure(
            text=("正在注入 V …" if focus_ok
                  else f"⚠ 窗口没能抢到前台（前台 pid={info['fg_before']}），"
                       "仍会注入，但结果不作准"),
            fg="#FFD60A" if not focus_ok else "#FFFFFF")

        def inject():
            time.sleep(0.7)
            winapi.key_down("v")
            time.sleep(0.15)
            winapi.key_up("v")
            time.sleep(0.45)
            info["fg_after"] = fg_pid()
            root.after(0, lambda: report(focus_ok))

        threading.Thread(target=inject, daemon=True).start()

    def report(focus_ok: bool):
        got = [k for k in received if k.lower() == "v"]
        print()
        print("=" * 56)
        print(f"本进程 pid = {my_pid}   注入时前台 pid = {info['fg_before']}")
        print(f"注入后前台 pid = {info['fg_after']}")
        print(f"收到的按键 = {received or '（一个都没有）'}")
        print("-" * 56)
        if not focus_ok:
            print("⚠ 靶子窗口没拿到前台，这次结果没有意义。")
            print("  原因：前台是别的程序（游戏？），Windows 不许后台抢焦点。")
            print("  关掉游戏 / 点一下这个窗口再重跑一次。")
            lbl.configure(text="⚠ 窗口没能抢到前台\n先点一下这个窗口，再重跑",
                          fg="#FF453A")
        elif got:
            print("✓ 注入成功 → 注入代码没问题。")
            print("  游戏里没反应 = UIPI/权限：游戏 High，我们 Medium，被静默丢弃。")
            print("  解决：以管理员身份运行 ValoTalk。")
            lbl.configure(text="✓ 注入成功\n→ 问题在权限，用管理员运行", fg="#30D158")
        else:
            print("✗ 靶子窗口（同进程、同级别）收不到 V → 注入代码本身有问题。")
            lbl.configure(text="✗ 同级别的窗口都收不到\n→ 注入代码有 bug", fg="#FF453A")
        print("=" * 56)
        root.after(2600, root.destroy)

    root.after(700, run_test)
    root.mainloop()
    if not received:
        return 1
    return 0 if any(k.lower() == "v" for k in received) else 1


if __name__ == "__main__":
    raise SystemExit(main())