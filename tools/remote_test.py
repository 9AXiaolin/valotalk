"""离线自测手机遥控服务：起服务 → 打接口 → 验证看门狗。

不用开主程序，也不碰 tkinter。跑：
    D:\\python\\python.exe -X utf8 tools\\remote_test.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from valotalk import remote  # noqa: E402

hits: list[str] = []
state = {"running": True, "muted": False}


def hit(name):
    def fn():
        hits.append(name)
        print(f"      ← 回调 {name}")
    return fn


def call(base: str, path: str, method: str = "POST") -> dict:
    req = urllib.request.Request(base.rstrip("/") + path, method=method)
    with urllib.request.urlopen(req, timeout=4) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def main() -> int:
    rc = remote.RemoteControl(
        on_down=hit("down"),
        on_up=hit("up"),
        on_clear=hit("clear"),
        on_mute=hit("mute"),
        get_state=lambda: state,
        log=print,
        port=8799,
    )
    url = rc.start()
    if not url:
        print("启动失败：", rc.error)
        return 1
    base = url.split("?")[0]
    print("服务地址:", url)
    print("局域网 IP:", remote.local_ips())
    print()

    ok = True

    # 1) 首页
    try:
        with urllib.request.urlopen(base + "/", timeout=4) as r:
            body = r.read().decode("utf-8")
        print(f"1) GET /           → {r.status}  {len(body)} bytes  "
              f"{'含按住说话' if '按住说话' in body else '❌ 页面异常'}")
        ok &= "按住说话" in body
    except Exception as e:
        print(f"1) GET /           → 失败 {e}")
        ok = False

    # 2) 状态
    try:
        s = call(base, "/state", "GET")
        print(f"2) GET /state      → {s}")
        ok &= s.get("running") is True
    except Exception as e:
        print(f"2) GET /state      → 失败 {e}")
        ok = False

    # 3) 按住 → 松手
    hits.clear()
    call(base, "/down")
    time.sleep(0.15)
    call(base, "/ping")
    time.sleep(0.15)
    s = call(base, "/up")
    print(f"3) down→ping→up    → holding={s.get('holding')}  回调={hits}")
    ok &= hits == ["down", "up"] and s.get("holding") is False

    # 4) 重复 down 只算一次（手机 touchend+mouseup 双触发）
    hits.clear()
    call(base, "/down")
    call(base, "/down")
    call(base, "/up")
    call(base, "/up")
    print(f"4) 重复 down/up    → 回调={hits}（应为 ['down','up']）")
    ok &= hits == ["down", "up"]

    # 5) 保活：一直 ping 不会自动松手
    hits.clear()
    call(base, "/down")
    for _ in range(6):
        time.sleep(0.4)
        call(base, "/ping")
    print(f"5) 按住 2.4s 持续 ping → 回调={hits}（应为 ['down'] = 没被自动松手）")
    ok &= hits == ["down"]
    call(base, "/up")

    # 6) 看门狗：按下后不 ping，1.8s 后应自动松手
    hits.clear()
    call(base, "/down")
    print("6) 按下后静默，等 2.6s …")
    time.sleep(2.6)
    print(f"   看门狗 → 回调={hits}（应含 'up'）")
    ok &= "up" in hits

    # 7) 清屏 / 静音
    hits.clear()
    call(base, "/clear")
    call(base, "/mute")
    print(f"7) clear/mute      → 回调={hits}")
    ok &= hits == ["clear", "mute"]

    # 8) 未知路径 404
    try:
        call(base, "/nope")
        print("8) GET /nope       → ❌ 应该是 404")
        ok = False
    except urllib.error.HTTPError as e:
        print(f"8) GET /nope       → {e.code} ✅")

    # 9) 口令校验
    rc2 = remote.RemoteControl(
        on_down=hit("down2"), on_up=hit("up2"),
        get_state=lambda: state, log=lambda *_: None,
        port=8801, token="Abc-123_xyz",
    )
    url2 = rc2.start()
    if url2:
        b2 = url2.split("?")[0]
        print(f"9) 带口令服务       → {url2}")
        # 9a 不带口令 → 401
        try:
            call(b2, "/state", "GET")
            print("   无口令访问        → ❌ 应该 401")
            ok = False
        except urllib.error.HTTPError as e:
            print(f"   无口令访问        → {e.code} {'✅' if e.code == 401 else '❌'}")
            ok &= e.code == 401
        # 9b 错口令 → 401
        try:
            call(b2, "/state?t=wrong", "GET")
            print("   错口令            → ❌ 应该 401")
            ok = False
        except urllib.error.HTTPError as e:
            print(f"   错口令            → {e.code} {'✅' if e.code == 401 else '❌'}")
            ok &= e.code == 401
        # 9c 对的口令 → 200
        try:
            s = call(b2, "/state?t=Abc-123_xyz", "GET")
            print(f"   对的口令          → 200 holding={s.get('holding')} ✅")
        except Exception as e:
            print(f"   对的口令          → ❌ {e}")
            ok = False
        # 9d POST 也要口令
        try:
            call(b2, "/down")
            print("   POST 无口令       → ❌ 应该 401")
            ok = False
        except urllib.error.HTTPError as e:
            print(f"   POST 无口令       → {e.code} {'✅' if e.code == 401 else '❌'}")
            ok &= e.code == 401
        hits.clear()
        call(b2, "/down?t=Abc-123_xyz")
        call(b2, "/up?t=Abc-123_xyz")
        print(f"   POST 带口令       → 回调={hits} "
              f"{'✅' if hits == ['down2', 'up2'] else '❌'}")
        ok &= hits == ["down2", "up2"]
        rc2.stop()
    else:
        print("9) 带口令服务       → 启动失败", rc2.error)
        ok = False

    rc.stop()
    print()
    print("=" * 56)
    print("全部通过 ✅" if ok else "有失败项 ❌")
    print("=" * 56)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
