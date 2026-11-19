"""启动冒烟：真的跑一遍启动流程（模型加载 + 采集线程），几秒后收工。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.app import App  # noqa: E402


def main() -> None:
    app = App()
    app.start()
    print("启动中，等 40 秒看模型与采集是否就绪 …", flush=True)
    t0 = time.time()
    while time.time() - t0 < 40:
        app.root.update()
        time.sleep(0.1)
    print("\n==== 日志 ====")
    for line in app.log_lines:
        print("  ", line)
    print("\n==== 状态 ====")
    print("  模型:", app.asr.status, "| device:", app.asr.device)
    print("  采集源:", {k: (v.running, round(v.peak, 4), v.error) for k, v in app._sources.items()})
    app.shutdown()


if __name__ == "__main__":
    main()