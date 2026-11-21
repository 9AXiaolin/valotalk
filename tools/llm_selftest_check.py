"""验证 test_llm 绕过缓存/直出表的逻辑（mock LLM 调用）。"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valotalk.config import Config
from valotalk.translate import Translator

cfg = Config()

# 预填配置
cfg.set("translate.llm.base_url", "https://api.deepseek.com/v1")
cfg.set("translate.llm.model", "deepseek-chat")
cfg.set("translate.llm.api_key", "sk-test123")

t = Translator(cfg.get)

# Mock _via_llm 返回固定结果
orig_via_llm = t._via_llm
t._via_llm = lambda text, src, dst: "北纬四十二度坐标是四十度"  # 成功

ok, msg = t.test_llm()
print(f"1) LLM 有配置 + 调用成功: ok={ok}  msg={msg!r}")
assert ok and "四十" in msg, "FAIL"

# Mock _via_llm 抛异常
t._via_llm = lambda text, src, dst: (_ for _ in ()).throw(RuntimeError("连接超时"))
ok, msg = t.test_llm()
print(f"2) LLM 调用异常:        ok={ok}  msg={msg!r}")
assert not ok and "连接超时" in msg, "FAIL"

# Mock _via_llm 返回空
t._via_llm = lambda text, src, dst: ""
t._last_error = "HTTP 401"
ok, msg = t.test_llm()
print(f"3) LLM 返回空:          ok={ok}  msg={msg!r}")
assert not ok and "401" in msg, "FAIL"

# 缺配置
cfg.set("translate.llm.api_key", "")
ok, msg = t.test_llm()
print(f"4) api_key 为空:        ok={ok}  msg={msg!r}")
assert not ok and "未填全" in msg, "FAIL"

print("\n全部通过 ✅")
