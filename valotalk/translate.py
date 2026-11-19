"""翻译层：LLM（OpenAI 兼容）→ Bing → Google → MyMemory 逐级降级。

设计要点：
  * 实时场景最怕慢。每条通道都有短超时，失败立刻换下一条，绝不干等。
  * 游戏喊话 90% 是固定短句，中→英先用短语表直出，比任何机翻都准。
  * 术语用词边界匹配追注，避免 "plant" 里的 "nt" 被当成 "nt=可惜"。
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
from collections import OrderedDict

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# ---------------- 无畏契约英文术语 → 中文 ----------------
VALORANT_TERMS: dict[str, str] = {
    "eco round": "经济局", "eco": "经济局", "full buy": "全起", "save": "保枪",
    "rush": "快冲", "rotate": "转点", "rotating": "在转点", "flank": "绕后",
    "flanking": "在绕后", "push": "前压", "peek": "探头拉枪", "one tap": "一枪头",
    "operator": "大狙", "op": "大狙", "plant": "下包", "planting": "在放包",
    "defuse": "拆包", "defusing": "在拆包", "spike": "炸弹", "site": "包点",
    "mid": "中路", "heaven": "天堂", "clutch": "残局", "lit": "打残",
    "tagged": "打上了", "trade": "换人", "crossfire": "交叉火力",
    "smoke": "烟", "flash": "闪光", "ultimate": "大招", "ult": "大招",
    "orbs": "能量球", "ult orb": "大招球", "spray": "扫射", "boost": "跳人",
    "afk": "挂机", "nt": "可惜", "wp": "漂亮", "gj": "干得漂亮",
    "ns": "好枪", "nice shot": "好枪", "on me": "我这边有人",
    "behind you": "你后面", "last one": "还剩一个", "one left": "还剩一个",
    "low": "残血", "cubby": "墙角", "wide": "拉宽",
}

# ---------------- 中文喊话 → 英文（整句命中直接出，绕开机翻） ----------------
VOICE_LINES: dict[str, str] = {
    "我开大了": "Using my ultimate now.",
    "开大了": "Ult going out!",
    "我要开大": "I'm using my ult.",
    "大招好了": "My ult is ready.",
    "掩护我": "Cover me.",
    "给我掩护": "Cover me, please.",
    "我上了": "I'm going in.",
    "我冲了": "I'm pushing in.",
    "等我": "Wait for me.",
    "等一下": "Hold on.",
    "别冲": "Don't push. Hold.",
    "先别动": "Hold position, don't peek.",
    "撤": "Fall back.",
    "撤退": "Fall back now.",
    "换点": "Rotate.",
    "转点": "Rotating now.",
    "打a": "Taking A site.",
    "打b": "Taking B site.",
    "打a点": "Taking A site.",
    "打b点": "Taking B site.",
    "去a": "Going A.",
    "去b": "Going B.",
    "中路": "Going mid.",
    "我走中路": "I'm taking mid.",
    "我绕后": "I'm flanking.",
    "有人": "Enemy here.",
    "这边有人": "Enemy on me.",
    "后面有人": "Enemy behind us.",
    "小心后面": "Watch our backs.",
    "下包": "Planting the spike.",
    "我在下包": "I'm planting.",
    "拆包": "Defusing.",
    "我在拆包": "I'm defusing, cover me.",
    "保枪": "Saving this round.",
    "经济局": "Eco round, save your guns.",
    "一起上": "Let's go together.",
    "一起进": "Let's push together.",
    "打残了": "He's lit.",
    "他残血": "He's low HP.",
    "还剩一个": "One left.",
    "最后一个": "Last one standing.",
    "好了": "Ready.",
    "我准备好了": "I'm ready.",
    "打得好": "Nice shot.",
    "干得漂亮": "Well played.",
    "别急": "Take it slow.",
    "小心狙": "Watch the OP.",
    "有狙": "They have an OP.",
    "他们没枪": "They're on eco.",
}

_LLM_SYSTEM = (
    "你是《无畏契约》(VALORANT) 队内语音实时翻译。把用户给的句子翻译成简洁、"
    "口语化、像真人队友喊话的目标语言。只输出译文本身，不要解释、不要引号、"
    "不要加括号注释。游戏术语按国内/国际玩家习惯：eco=经济局、plant=下包、"
    "defuse=拆包、op=大狙、one tap=一枪头、clutch=残局、rotate=转点、"
    "ult=大招、lit=打残。不要使用俚语歧义表达。"
)

_BING_TOKEN_TTL = 600.0


class _LRU:
    def __init__(self, size: int = 4000):
        self.size = max(64, size)
        self._d: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        return None

    def put(self, key, value) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.size:
                self._d.popitem(last=False)


class Translator:
    def __init__(self, cfg_get):
        self._get = cfg_get
        self._cache = _LRU(int(cfg_get("translate.cache_size", 4000) or 4000))
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self._setup_proxy()
        self._last_error = ""
        self.backend_used = ""
        self._min_gap = 0.12
        self._last_call = 0.0
        self._rl_lock = threading.Lock()
        self._bing: dict = {}
        self._bing_lock = threading.Lock()

    def _setup_proxy(self) -> None:
        proxy = (self._get("translate.proxy", "") or "").strip()
        if proxy:
            self._session.proxies.update({"http": proxy, "https": proxy})

    # ---------------- 对外 ----------------
    def translate(self, text: str, src: str = "en", dst: str = "zh-CN") -> str:
        text = (text or "").strip().strip('"“”')
        if not text:
            return ""
        key = (text, src, dst)
        hit = self._cache.get(key)
        if hit is not None:
            self.backend_used = "cache"
            return hit

        # 中文喊话直出（最快最准）
        if src == "zh" and dst.startswith("en"):
            direct = self._voice_line(text)
            if direct:
                self.backend_used = "script"
                self._cache.put(key, direct)
                return direct

        self._throttle()
        result = ""
        for backend in self._backend_order():
            try:
                result = self._call(backend, text, src, dst)
            except Exception as exc:
                self._last_error = f"{backend}: {_short(exc)}"
                result = ""
            if result:
                self.backend_used = backend
                break

        if result:
            result = self._postprocess(result.strip(), src, dst, text)
            if result:
                self._cache.put(key, result)
        return result

    @property
    def last_error(self) -> str:
        return self._last_error

    # ---------------- 内部 ----------------
    def _call(self, backend: str, text: str, src: str, dst: str) -> str:
        if backend == "llm":
            return self._via_llm(text, src, dst)
        if backend == "bing":
            return self._via_bing(text, src, dst)
        if backend == "google":
            return self._via_google(text, src, dst)
        if backend == "mymemory":
            return self._via_mymemory(text, src, dst)
        return ""

    def _backend_order(self) -> list[str]:
        want = (self._get("translate.backend", "auto") or "auto").lower()
        llm_ready = bool(self._get("translate.llm.base_url", "")) and bool(
            self._get("translate.llm.model", "")
        )
        base = ["bing", "google", "mymemory"]
        if want == "llm":
            return (["llm"] if llm_ready else []) + base
        if want == "bing":
            return ["bing"] + base[1:] + (["llm"] if llm_ready else [])
        if want == "google":
            return ["google", "bing", "mymemory"] + (["llm"] if llm_ready else [])
        return (["llm"] if llm_ready else []) + base

    def _throttle(self) -> None:
        with self._rl_lock:
            gap = time.time() - self._last_call
            if gap < self._min_gap:
                time.sleep(self._min_gap - gap)
            self._last_call = time.time()

    def _voice_line(self, text: str) -> str:
        norm = re.sub(r"[\s，。,.!！?？~～]+", "", text)
        for zh, en in VOICE_LINES.items():
            if re.sub(r"[\s，。,.!！?？~～]+", "", zh) == norm:
                return en
        return ""

    def _postprocess(self, out: str, src: str, dst: str, source_text: str) -> str:
        out = re.sub(r"\s+", " ", out).strip()
        if not out:
            return ""
        # 机翻常见的错义补丁（中→英）
        if dst.startswith("en"):
            patches = {
                r"\bbig dump\b": "ult", r"\btake a (big )?dump\b": "use my ult",
                r"\bcover me a bit\b": "cover me", r"\bmiddle road\b": "mid",
            }
            for pat, rep in patches.items():
                out = re.sub(pat, rep, out, flags=re.I)
        # 英→中：补术语注释（词边界，最多 2 条）。LLM 已经译准了，不用再追注
        if (dst.startswith("zh") and self._get("translate.glossary", True)
                and self.backend_used != "llm"):
            out = self._annotate(source_text, out)
        return out

    def _annotate(self, src: str, zh: str) -> str:
        low = src.lower()
        hits: list[tuple[int, str]] = []
        for term, zh_term in VALORANT_TERMS.items():
            pat = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
            if re.search(pat, low) and zh_term not in zh:
                hits.append((len(term), f"{term}={zh_term}"))
        if not hits:
            return zh
        hits.sort(key=lambda h: -h[0])          # 长词优先，避免 op 抢 operator
        picked, used = [], set()
        for _n, tag in hits:
            base = tag.split("=")[0]
            if any(base in u or u in base for u in used):
                continue
            used.add(base)
            picked.append(tag)
            if len(picked) >= 2:
                break
        return f"{zh}（{'，'.join(picked)}）" if picked else zh

    # ---------------- Bing（国内可直连） ----------------
    def _bing_params(self) -> dict:
        with self._bing_lock:
            now = time.time()
            if self._bing.get("t", 0) + _BING_TOKEN_TTL > now and self._bing.get("ig"):
                return self._bing
            r = self._session.get("https://cn.bing.com/translator",
                                  timeout=float(self._get("translate.timeout", 5)),
                                  headers={"Referer": "https://cn.bing.com/"})
            html = r.text
            m = re.search(r'params_AbusePreventionHelper\s*=\s*\[\s*(\d+)\s*,\s*"([^"]+)"', html)
            ig = re.search(r'IG:"([^"]+)"', html)
            iid = re.search(r'data-iid="([^"]+)"', html)
            if not (m and ig):
                raise RuntimeError("Bing token 解析失败")
            self._bing = {
                "key": m.group(1), "token": m.group(2),
                "ig": ig.group(1), "iid": iid.group(1) if iid else "translator.5028",
                "t": now,
            }
            return self._bing

    def _bing_lang(self, code: str) -> str:
        c = code.lower()
        if c.startswith("zh"):
            return "zh-Hans"
        return c.split("-")[0]

    def _via_bing(self, text: str, src: str, dst: str) -> str:
        p = self._bing_params()
        url = f"https://cn.bing.com/ttranslatev3?isVertical=1&IG={p['ig']}&IID={p['iid']}"
        data = {
            "fromLang": "auto-detect",
            "to": self._bing_lang(dst),
            "text": text,
            "token": p["token"],
            "key": p["key"],
        }
        r = self._session.post(url, data=data, timeout=float(self._get("translate.timeout", 5)),
                               headers={"Referer": "https://cn.bing.com/translator"})
        if r.status_code != 200:
            with self._bing_lock:
                self._bing = {}
            raise RuntimeError(f"Bing HTTP {r.status_code}")
        js = r.json()
        if isinstance(js, dict) and js.get("statusCode"):
            with self._bing_lock:
                self._bing = {}
            raise RuntimeError(f"Bing {js.get('statusCode')}")
        try:
            return js[0]["translations"][0]["text"]
        except Exception:
            return ""

    # ---------------- Google ----------------
    def _via_google(self, text: str, src: str, dst: str) -> str:
        endpoint = self._get("translate.google_endpoint",
                             "https://translate.googleapis.com/translate_a/single")
        params = {"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text}
        url = endpoint + "?" + urllib.parse.urlencode(params)
        r = self._session.get(url, timeout=float(self._get("translate.google_timeout", 3)))
        r.raise_for_status()
        data = r.json()
        if not data or not data[0]:
            return ""
        return "".join(seg[0] for seg in data[0] if seg and seg[0])

    # ---------------- MyMemory（最后兜底） ----------------
    def _via_mymemory(self, text: str, src: str, dst: str) -> str:
        if len(text) > 480:
            text = text[:480]
        pair = f"{src}|{'zh-CN' if dst.startswith('zh') else dst}"
        url = ("https://api.mymemory.translated.net/get?"
               + urllib.parse.urlencode({"q": text, "langpair": pair}))
        r = self._session.get(url, timeout=float(self._get("translate.mymemory_timeout", 6)))
        r.raise_for_status()
        data = r.json()
        out = (data.get("responseData") or {}).get("translatedText") or ""
        if "MYMEMORY WARNING" in out.upper() or "QUOTA" in out.upper():
            return ""
        return out

    # ---------------- LLM ----------------
    def _via_llm(self, text: str, src: str, dst: str) -> str:
        base = (self._get("translate.llm.base_url", "") or "").rstrip("/")
        model = self._get("translate.llm.model", "")
        key = self._get("translate.llm.api_key", "")
        if not base or not model:
            return ""
        url = base + "/chat/completions"
        lang_name = {"en": "英文", "zh": "中文"}.get(dst.split("-")[0], dst)
        payload = {
            "model": model,
            "temperature": 0.1,
            "max_tokens": 256,
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": f"翻译成{lang_name}：{text}"},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        r = self._session.post(url, data=json.dumps(payload), headers=headers,
                               timeout=float(self._get("translate.llm.timeout", 10)))
        r.raise_for_status()
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip().strip('"“”')


def _short(exc: Exception) -> str:
    s = str(exc)
    return s if len(s) < 90 else s[:90] + "…"