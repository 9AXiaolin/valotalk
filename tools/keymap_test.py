"""确认可选键位的 VK 映射与物理位置。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk import winapi

# (名字, VK, 物理位置说明)
TABLE = [
    ("`", 0xC0, "数字 1 左边、Esc 正下方"),
    ("tab", 0x09, "` 的下方，第三行最左"),
    ("capslock", 0x14, "Tab 下方，A 左边"),
    ("f2", 0x71, "功能键区，笔记本常需 Fn"),
    ("insert", 0x2D, "编辑键区"),
    ("mouse4", 0x05, "鼠标侧键（后退）"),
]

print(f"{'名称':10s} {'VK':8s} {'程序值':8s} 物理位置")
print("-" * 60)
for name, expect_vk, where in TABLE:
    got = winapi.vk_of(name)
    mark = "✓" if got == expect_vk else "✗"
    print(f"{mark} {name:9s} 0x{got:02X}    {got:8d} {where}")

print("\n下拉框里显示的是：")
for c in winapi.HOTKEY_CHOICES:
    print(f"  {c}")