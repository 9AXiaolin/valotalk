"""验证 LLM 输入框 placeholder 与保存流程兼容。"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from valotalk.app import App

app = App()
app._running = True
for _ in range(18):
    app.root.update(); time.sleep(0.05)

print("=== 有值时 get() 返回值 ===")
for name, attr in [('base_url','e_base'), ('model','e_model'), ('api_key','e_key')]:
    e = getattr(app, attr)
    print(f"  {name:10s} get()={e.get()[:30]!r}  showing_ph={e._showing_ph}")

print("\n=== 清空后 get() 返回空串（不存水印文字）===")
app.e_base.set("")
app.e_model.set("")
app.e_key.set("")
for name, attr in [('base_url','e_base'), ('model','e_model'), ('api_key','e_key')]:
    e = getattr(app, attr)
    ok = e.get() == "" and e._showing_ph
    print(f"  {name:10s} get()={e.get()!r}  showing_ph={e._showing_ph}  {'OK' if ok else 'FAIL'}")

print("\n=== 重新输入后 get() 正常 ===")
app.e_base.set("https://api.deepseek.com/v1")
app.e_model.set("deepseek-chat")
app.e_key.set("sk-abc123")
for name, attr in [('base_url','e_base'), ('model','e_model'), ('api_key','e_key')]:
    e = getattr(app, attr)
    print(f"  {name:10s} get()={e.get()!r}  showing_ph={e._showing_ph}")

print("\n=== 模拟保存流程（_save_llm 调 get()）===")
app.e_base.set("")
app.e_model.set("")
app.e_key.set("")
# _save_llm 的核心逻辑
b = app.e_base.get().strip()
m = app.e_model.get().strip()
k = app.e_key.get().strip()
print(f"  save: base={b!r} model={m!r} key={k!r}")
print(f"  {'OK (空值不存)' if not b and not m and not k else 'FAIL (水印被当成值存了)'}")

app.shutdown()
