"""手机遥控：局域网 HTTP 服务，手机浏览器按住按钮 = 游戏里"我说中文"。

为什么要有这个：无畏契约用 Raw Input 独占键鼠，程序在游戏有焦点时收不到
任何热键；反过来程序抢到焦点游戏就收不到键。手机走 WiFi，完全绕开这套
输入通道 —— 按一下就相当于按下了 PTT 键。

设计要点
  * 纯标准库（http.server），不引依赖
  * 手机端"按住说话"：touchstart 立刻 /down，touchend 立刻 /up
  * 保活兜底：按住期间每 400ms /ping 一次；服务端看门狗 1.8s 没收到
    ping 就自动 /up。手机锁屏、切后台、WiFi 抖动都不会把 PTT 卡在按下态
  * 只接受局域网来源，公网 IP 直接 403
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

__all__ = ["RemoteControl", "local_ips"]

PING_TIMEOUT = 1.8          # 秒：多久没 ping 就自动松手
WATCHDOG_TICK = 0.25


# ---------------------------------------------------------------- 网络工具
def local_ips() -> list[str]:
    """本机局域网 IPv4，按"手机最可能连上"的顺序排。

    家用路由器常见 192.168.x.x，其次 10.x，最后 172.16-31。
    虚拟网卡（VMware/WSL/Hyper-V）也在这几段里，没法可靠剔除，
    所以全列出来 —— 第一个连不上就试下一个。
    """
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("223.5.5.5", 80))       # 不发包，只为让系统选出默认出口网卡
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            ips.append(ip)
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    def rank(ip: str) -> int:
        if ip.startswith("192.168."):
            return 0
        if ip.startswith("10."):
            return 1
        if ip.startswith("172."):
            return 2
        return 3

    ips.sort(key=rank)
    return ips


def _is_lan(ip: str) -> bool:
    """127/8、10/8、172.16/12、192.168/16 视为局域网。"""
    if not ip:
        return False
    if ip.startswith("127.") or ip in ("::1", "localhost"):
        return True
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    return (a == 10) or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31)


# ---------------------------------------------------------------- 手机页面
_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#121212">
<title>ValoTalk 遥控</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;overflow:hidden;overscroll-behavior:none}
/* iOS 的 100% 含地址栏高度，内容会被盖住底部；dvh 才是真正的可视高 */
@supports(height:100dvh){html,body{height:100dvh}}
body{
  background:#121212;color:#fff;
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  display:flex;flex-direction:column;
  padding:calc(env(safe-area-inset-top) + 14px) 16px calc(env(safe-area-inset-bottom) + 16px);
  user-select:none;-webkit-user-select:none;
  touch-action:none;
}
header{display:flex;align-items:center;gap:8px;flex:none}
.dot{width:9px;height:9px;border-radius:50%;background:#3A3A3C;transition:background .25s}
.dot.ok{background:#30D158;box-shadow:0 0 8px #30D15866}
.dot.bad{background:#FF453A}
header .t{font-size:17px;font-weight:700;letter-spacing:.3px}
header .ip{margin-left:auto;font-size:11px;color:#636366;font-variant-numeric:tabular-nums}
main{flex:1;display:flex;align-items:center;justify-content:center;min-height:0;
     padding:10px 0 24px}
#btn{
  position:relative;border:0;padding:0;
  width:min(76vw,44vh,350px);aspect-ratio:1;border-radius:50%;
  background:radial-gradient(circle at 50% 34%,#2C2C2E,#1C1C1E 62%,#151517);
  box-shadow:0 10px 34px #00000066,inset 0 1px 0 #ffffff12,inset 0 -2px 12px #00000055;
  color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
  transition:transform .09s ease,box-shadow .16s ease,background .16s ease;
  touch-action:none;-webkit-touch-callout:none;
}
#btn .big{font-size:26px;font-weight:700;letter-spacing:2px}
#btn .sub{font-size:12px;color:#8E8E93;letter-spacing:1px}
#btn.on{
  background:radial-gradient(circle at 50% 34%,#3DDC84,#1FA85C 62%,#167A42);
  box-shadow:0 0 0 6px #30D15822,0 12px 44px #30D15855,inset 0 1px 0 #ffffff33;
  transform:scale(.965);
}
#btn.on .sub{color:#ffffffC0}
#btn .ring{
  position:absolute;inset:-10px;border-radius:50%;
  border:2px solid #30D15800;transition:border-color .2s;
}
#btn.on .ring{border-color:#30D15866;animation:pulse 1.1s ease-out infinite}
@keyframes pulse{0%{transform:scale(1);opacity:.9}100%{transform:scale(1.1);opacity:0}}
footer{flex:none;display:flex;gap:12px;padding-top:16px}
.mini{
  flex:1 1 0;width:0;min-width:0;height:52px;border:0;border-radius:15px;
  background:#1C1C1E;color:#E5E5EA;
  font-size:15px;font-weight:600;font-family:inherit;
  box-shadow:inset 0 1px 0 #ffffff0F;transition:background .12s,transform .08s;
}
.mini:active{background:#2C2C2E;transform:scale(.97)}
.mini.hot{background:#0A84FF33;color:#64B5FF}

/* 按住 / 点按 切换 —— 打起来两只手都要用，点按才是常态 */
#mode{
  flex:none;display:flex;gap:4px;padding:4px;border-radius:13px;
  background:#1C1C1E;box-shadow:inset 0 1px 0 #ffffff0F;margin:0 auto;
}
#mode button{
  border:0;padding:8px 20px;border-radius:10px;background:transparent;
  color:#8E8E93;font-size:13px;font-weight:600;font-family:inherit;
  transition:background .14s,color .14s;
}
#mode button.sel{background:#3A3A3C;color:#fff}
#hint{
  flex:none;text-align:center;font-size:11px;color:#636366;padding-top:10px;
  height:16px;letter-spacing:.5px;
}
</style>
</head>
<body>
<header>
  <div class="dot" id="dot"></div>
  <div class="t">ValoTalk</div>
  <div class="ip" id="ip"></div>
</header>

<main>
  <button id="btn">
    <div class="ring"></div>
    <div class="big" id="big">按住说话</div>
    <div class="sub" id="sub">松手播英文</div>
  </button>
</main>

<div id="mode">
  <button id="mHold" class="sel">按住</button>
  <button id="mTap">点按</button>
</div>

<footer>
  <button class="mini" id="bClear">清屏</button>
  <button class="mini" id="bMute">静音</button>
</footer>
<div id="hint">按住按钮 = 游戏里已开麦</div>

<script>
(function(){
  var TOK = new URLSearchParams(location.search).get('t') || '';
  var btn  = document.getElementById('btn');
  var dot  = document.getElementById('dot');
  var big  = document.getElementById('big');
  var sub  = document.getElementById('sub');
  var hint = document.getElementById('hint');
  var bMute = document.getElementById('bMute');
  var mHold = document.getElementById('mHold');
  var mTap  = document.getElementById('mTap');
  var holding = false, ping = null, t0 = 0, timer = null, wake = null;

  // 'hold' 按住才说｜'tap' 点一下开始、再点一下结束（打起来两只手都要用）
  var mode = 'hold';
  try { if (localStorage.getItem('vt_mode') === 'tap') mode = 'tap'; } catch(e){}

  var LABEL = {
    hold: { idle:'按住说话', idleSub:'松手播英文', on:'正在听…', onSub:'松手就翻译' },
    tap:  { idle:'点一下',   idleSub:'开始说话',   on:'正在听…', onSub:'再点一下结束' }
  };

  function applyMode(){
    var L = LABEL[mode];
    mHold.classList.toggle('sel', mode === 'hold');
    mTap.classList.toggle('sel', mode === 'tap');
    hint.textContent = mode === 'hold'
      ? '按住按钮 = 正在说话'
      : '点一下开始，再点一下结束';
    if (!holding){ big.textContent = L.idle; sub.textContent = L.idleSub; }
  }

  // 打游戏时手机不能黑屏，不然点第二下时页面已经被挂起了
  function keepAwake(){
    try{
      if (wake || !('wakeLock' in navigator)) return;
      navigator.wakeLock.request('screen').then(function(w){ wake = w;
        w.addEventListener('release', function(){ wake = null; });
      }).catch(function(){});
    }catch(e){}
  }

  function url(p){
    return p + (TOK ? (p.indexOf('?')<0?'?':'&') + 't=' + encodeURIComponent(TOK) : '');
  }
  function call(p){
    return fetch(url(p), {method:'POST', cache:'no-store', keepalive:true})
      .then(function(r){ return r.json(); })
      .catch(function(){ return null; });
  }
  function buzz(p){ try{ navigator.vibrate && navigator.vibrate(p); }catch(e){} }

  function down(){
    if (holding) return;
    holding = true;
    var L = LABEL[mode];
    btn.classList.add('on');
    big.textContent = L.on;
    sub.textContent = '0.0s';
    buzz(mode === 'tap' ? 30 : 18);
    keepAwake();
    call('/down');
    clearInterval(ping);
    // 点按模式下靠心跳一直续着；按住模式松手会停掉
    ping = setInterval(function(){ call('/ping'); }, 400);
    t0 = Date.now();
    clearInterval(timer);
    timer = setInterval(function(){
      var s = (Date.now() - t0) / 1000;
      sub.textContent = s.toFixed(1) + 's';
      if (s > 25 && mode === 'hold') big.textContent = '快松手';
    }, 100);
  }

  function up(){
    if (!holding) return;
    holding = false;
    var L = LABEL[mode];
    btn.classList.remove('on');
    big.textContent = L.idle;
    sub.textContent = L.idleSub;
    buzz([12, 40, 12]);
    clearInterval(ping); ping = null;
    clearInterval(timer); timer = null;
    call('/up');
  }

  // 按住模式：按下说，松开停
  function pressStart(ev){
    if (ev) ev.preventDefault();
    if (mode === 'hold') down();
  }
  function pressEnd(ev){
    if (ev) ev.preventDefault();
    if (mode === 'hold') up();
  }
  // 点按模式：点一下切换
  function pressTap(ev){
    if (ev) ev.preventDefault();
    if (mode !== 'tap') return;
    if (holding) up(); else down();
  }
  function onStart(ev){
    if (mode === 'hold') pressStart(ev); else pressTap(ev);
  }
  function onEnd(ev){
    if (mode === 'hold') pressEnd(ev);
    else if (ev) ev.preventDefault();     // 点按模式松手什么都不做
  }

  btn.addEventListener('touchstart', onStart, {passive:false});
  btn.addEventListener('touchend', onEnd, {passive:false});
  btn.addEventListener('touchcancel', function(ev){ if (mode==='hold') up(); }, {passive:false});
  btn.addEventListener('mousedown', onStart);
  btn.addEventListener('mouseup', onEnd);
  btn.addEventListener('mouseleave', function(){ if (mode === 'hold') up(); });
  btn.addEventListener('contextmenu', function(e){ e.preventDefault(); });

  mHold.addEventListener('click', function(){
    if (holding) up();
    mode = 'hold';
    try { localStorage.setItem('vt_mode', 'hold'); } catch(e){}
    buzz(8); applyMode();
  });
  mTap.addEventListener('click', function(){
    mode = 'tap';
    try { localStorage.setItem('vt_mode', 'tap'); } catch(e){}
    buzz(8); applyMode();
  });

  document.getElementById('bClear').addEventListener('click', function(){
    buzz(10); call('/clear');
  });
  bMute.addEventListener('click', function(){
    buzz(10);
    call('/mute').then(function(s){ if (s) paint(s); });
  });

  // 页面被切走 / 锁屏：立刻结束，别让程序一直以为你在说
  document.addEventListener('visibilitychange', function(){
    if (document.hidden && holding) up();
  });
  window.addEventListener('pagehide', function(){ if (holding) up(); });
  window.addEventListener('blur', function(){ if (holding && mode === 'hold') up(); });

  function paint(s){
    if (!s) { dot.className = 'dot bad'; hint.textContent = '电脑那边没有响应'; return; }
    dot.className = 'dot ok';
    document.getElementById('ip').textContent = s.ip || '';
    if (s.running) {
      hint.textContent = s.muted
        ? '电脑：英文语音已暂停'
        : (mode === 'hold' ? '按住按钮 = 正在说话' : '点一下开始，再点一下结束');
    } else {
      hint.textContent = '电脑：未启动，先点 ▶ 开始';
    }
    bMute.classList.toggle('hot', !!s.muted);
    bMute.textContent = s.muted ? '恢复' : '静音';
    // 电脑那边状态和本页不一致（另一个标签页 / 刷新过）→ 同步过来
    if (!s.holding && holding) {
      holding = false; btn.classList.remove('on');
      clearInterval(ping); ping = null;
      clearInterval(timer); timer = null;
      var L = LABEL[mode]; big.textContent = L.idle; sub.textContent = L.idleSub;
    } else if (s.holding && !holding) {
      holding = true; btn.classList.add('on');
      big.textContent = LABEL[mode].on;
    }
  }

  applyMode();
  function tick(){
    fetch(url('/state'), {cache:'no-store'})
      .then(function(r){ return r.json(); })
      .then(paint)
      .catch(function(){ paint(null); });
  }
  tick(); setInterval(tick, 1200);
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- HTTP
class _Handler(BaseHTTPRequestHandler):
    server_version = "ValoTalkRemote/1.0"
    protocol_version = "HTTP/1.1"

    # 默认实现每请求往 stderr 打一行，跑步机上刷屏，静掉
    def log_message(self, fmt, *args):
        pass

    # ---- 工具 ----
    def _rc(self) -> "RemoteControl":
        return self.server.rc  # type: ignore[attr-defined]

    def _query(self) -> dict:
        try:
            return parse_qs(urlparse(self.path).query)
        except Exception:
            return {}

    def _deny(self) -> bool:
        rc = self._rc()
        ip = self.client_address[0] if self.client_address else ""
        if not _is_lan(ip):
            self._send(403, b'{"ok":false,"err":"lan only"}')
            return True
        if rc.token:
            got = (self._query().get("t") or [""])[0] or self.headers.get("X-Token", "")
            if got != rc.token:
                self._send(401, b'{"ok":false,"err":"token"}')
                return True
        return False

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            if body:
                self.wfile.write(body)
        except Exception:
            pass

    def _json(self, obj) -> None:
        self._send(200, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _drain(self) -> None:
        n = 0
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > 0:
            try:
                self.rfile.read(min(n, 8192))
            except Exception:
                pass

    # ---- GET ----
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/i"):
            if self._deny():
                return
            self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self._deny():
            return
        if path == "/state":
            self._json(self._rc().state())
        elif path == "/favicon.ico":
            self._send(204, b"")
        else:
            self._send(404, b'{"ok":false}')

    # ---- POST ----
    def do_POST(self):
        self._drain()
        if self._deny():
            return
        rc = self._rc()
        path = urlparse(self.path).path
        if path == "/down":
            rc.down()
            self._json(rc.state())
        elif path == "/ping":
            rc.ping()
            self._json(rc.state())
        elif path == "/up":
            rc.up()
            self._json(rc.state())
        elif path == "/clear":
            rc.clear()
            self._json(rc.state())
        elif path == "/mute":
            rc.toggle_mute()
            self._json(rc.state())
        else:
            self._send(404, b'{"ok":false}')


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------- 控制器
class RemoteControl:
    """把手机上的按钮映射成 on_down / on_up 回调。

    on_down / on_up / on_clear / on_mute 都会在网络线程里执行，
    调用方自己负责切回主线程（app.py 用 self._uiq 队列）。
    """

    def __init__(self, on_down, on_up,
                 on_clear=None, on_mute=None,
                 get_state=None, log=None,
                 port: int = 8765, token: str = ""):
        self.on_down = on_down
        self.on_up = on_up
        self.on_clear = on_clear
        self.on_mute = on_mute
        self._get_state = get_state
        self.log = log or (lambda *_a, **_k: None)
        self.port = int(port)
        self.token = (token or "").strip()

        self._lock = threading.Lock()
        self._holding = False
        self._last_ping = 0.0
        self._srv: _Server | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.url = ""
        self.ip = ""
        self.error = ""

    # ---- 状态 ----
    def state(self) -> dict:
        extra = {}
        try:
            extra = self._get_state() or {}
        except Exception:
            extra = {}
        with self._lock:
            holding = self._holding
        out = {"ok": True, "holding": holding, "ip": self.ip,
               "running": bool(extra.get("running", False)),
               "muted": bool(extra.get("muted", False)),
               "port": self.port}
        return out

    # ---- 动作（网络线程调用） ----
    def down(self) -> None:
        with self._lock:
            first = not self._holding
            self._holding = True
            self._last_ping = time.time()
        if first:
            self.log("[手机] 按下 → 开始听你说中文")
            _safe(self.on_down)

    def ping(self) -> None:
        with self._lock:
            if not self._holding:
                return
            self._last_ping = time.time()

    def up(self, reason: str = "") -> None:
        with self._lock:
            if not self._holding:
                return
            self._holding = False
        self.log("[手机] 松手 → 翻译并播报" + (f"（{reason}）" if reason else ""))
        _safe(self.on_up)

    def clear(self) -> None:
        self.log("[手机] 清屏")
        if self.on_clear:
            _safe(self.on_clear)

    def toggle_mute(self) -> None:
        if self.on_mute:
            _safe(self.on_mute)

    # ---- 看门狗：手机掉线自动松手 ----
    def _watchdog(self) -> None:
        while not self._stop.wait(WATCHDOG_TICK):
            stale = False
            with self._lock:
                if self._holding and time.time() - self._last_ping > PING_TIMEOUT:
                    self._holding = False
                    stale = True
            if stale:
                self.log("[手机] 超过 %.1fs 没收到心跳，自动松手" % PING_TIMEOUT)
                _safe(self.on_up)

    # ---- 生命周期 ----
    def start(self) -> str:
        """起服务，返回手机要打开的网址；失败返回空串。"""
        if self._srv is not None:
            return self.url
        for attempt in range(4):
            port = self.port + attempt
            try:
                srv = _Server(("0.0.0.0", port), _Handler)
                srv.rc = self  # type: ignore[attr-defined]
            except OSError as e:
                self.error = f"端口 {port} 被占用：{e}"
                continue
            self._srv = srv
            self.port = port
            ips = local_ips()
            self.ip = ips[0] if ips else ""
            q = f"?t={self.token}" if self.token else ""
            self.url = f"http://{self.ip}:{port}/{q}" if self.ip else ""
            self._thread = threading.Thread(target=srv.serve_forever,
                                            kwargs={"poll_interval": 0.3},
                                            name="remote-http", daemon=True)
            self._thread.start()
            threading.Thread(target=self._watchdog, name="remote-dog",
                             daemon=True).start()
            self.error = ""
            return self.url
        return ""

    def stop(self) -> None:
        self._stop.set()
        srv = self._srv
        self._srv = None
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass
            try:
                srv.server_close()
            except Exception:
                pass
        self.url = ""


def _safe(fn) -> None:
    try:
        fn()
    except Exception as e:  # 回调炸了不能把 HTTP 线程带走
        try:
            print(f"[remote] 回调异常：{e}", flush=True)
        except Exception:
            pass
