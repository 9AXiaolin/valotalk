/* 手机页面交互逻辑测试（Node，无需浏览器）。
 *
 * 用最小 DOM 桩跑真实的页面脚本，验证：
 *   1) 按住模式：touchstart → /down，touchend → /up
 *   2) 点按模式：第一次点 → /down，第二次点 → /up（松手不发 /up）
 *   3) 按住期间每 400ms 发 /ping
 *   4) 电脑状态变化（另一个标签页松手/刷新）能同步回本页
 *
 * 跑：E:\Node\node.exe tools\remote_page_logic.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const PY = path.join(ROOT, 'valotalk', 'remote.py');

// ---- 从 remote.py 里抽出页面脚本（避免两处维护）----
const py = fs.readFileSync(PY, 'utf8');
const pageStart = py.indexOf('_PAGE = r"""');
const pageEnd = py.indexOf('"""', pageStart + 12);
if (pageStart < 0 || pageEnd < 0) {
  console.error('在 remote.py 里找不到 _PAGE 字符串');
  process.exit(1);
}
const page = py.slice(pageStart + 12, pageEnd);
const m = page.match(/<script>([\s\S]*?)<\/script>/);
if (!m) {
  console.error('页面里找不到 <script>');
  process.exit(1);
}
const script = m[1];

// ---- 最小 DOM ----
function makeEl(id) {
  const classes = new Set();
  return {
    id,
    textContent: '',
    dataset: {},
    listeners: {},
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
      contains: (c) => classes.has(c),
    },
    _classes: classes,
    addEventListener(type, fn) {
      (this.listeners[type] = this.listeners[type] || []).push(fn);
    },
    fire(type, ev) {
      for (const fn of this.listeners[type] || []) fn(ev || { preventDefault() {} });
    },
  };
}

const ids = ['btn', 'dot', 'big', 'sub', 'hint', 'bMute', 'bClear', 'mHold', 'mTap', 'ip'];
const els = {};
for (const id of ids) els[id] = makeEl(id);
els.mHold._classes.add('sel');

const calls = [];
let serverState = { ok: true, holding: false, running: true, muted: false, ip: '10.0.0.5' };

const store = {};
const ctx = {
  console,
  URLSearchParams,
  setInterval: (fn, ms) => {
    // 手动推进：把定时器收集起来，测试里显式触发
    const h = { fn, ms, cleared: false };
    (ctx.__timers = ctx.__timers || []).push(h);
    return h;
  },
  clearInterval: (h) => { if (h) h.cleared = true; },
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
  },
  document: {
    getElementById: (id) => els[id] || makeEl(id),
    addEventListener: (t, fn) => { (ctx.__docL = ctx.__docL || {})[t] = fn; },
    querySelector: () => null,
    hidden: false,
  },
  window: {
    addEventListener: (t, fn) => { (ctx.__winL = ctx.__winL || {})[t] = fn; },
  },
  navigator: { vibrate: () => {}, wakeLock: undefined },
  location: { search: '' },
  fetch: (url, opts) => {
    const p = String(url);
    const mth = (opts && opts.method) || 'GET';
    calls.push(mth + ' ' + p.replace(/\?.*$/, ''));
    if (p.indexOf('/state') >= 0) {
      return Promise.resolve({ json: () => Promise.resolve({ ...serverState }) });
    }
    if (p.indexOf('/down') >= 0) { serverState.holding = true; }
    if (p.indexOf('/up') >= 0) { serverState.holding = false; }
    if (p.indexOf('/mute') >= 0) { serverState.muted = !serverState.muted; }
    return Promise.resolve({ json: () => Promise.resolve({ ...serverState }) });
  },
};
ctx.window.document = ctx.document;
ctx.window.navigator = ctx.navigator;
ctx.window.localStorage = ctx.localStorage;
ctx.globalThis = ctx;
ctx.self = ctx;

vm.createContext(ctx);
vm.runInContext(script, ctx);

// 等首帧 tick 的 promise 落地
const flush = () => new Promise((r) => setImmediate(r));

function timersOf(ms) {
  return (ctx.__timers || []).filter((t) => t.ms === ms && !t.cleared);
}

let failed = 0;
function check(name, cond, extra) {
  if (cond) { console.log('  [PASS] ' + name); }
  else { console.log('  [FAIL] ' + name + (extra ? '  → ' + extra : '')); failed++; }
}

(async () => {
  await flush(); await flush();

  console.log('\n[1] 首屏');
  check('默认选中「按住」', els.mHold._classes.has('sel') && !els.mTap._classes.has('sel'));
  check('按钮文案是「按住说话」', els.big.textContent === '按住说话', els.big.textContent);
  check('拉过一次 /state', calls.some((c) => c === 'GET /state'));

  console.log('\n[2] 按住模式');
  calls.length = 0;
  els.btn.fire('touchstart');
  await flush();
  check('按下发 /down', calls[0] === 'POST /down', calls.join(','));
  check('按钮变绿(on)', els.btn._classes.has('on'));
  check('文案变「正在听…」', els.big.textContent === '正在听…', els.big.textContent);
  const pings = timersOf(400);
  check('起了 400ms 心跳', pings.length === 1);
  pings[0].fn(); await flush();
  check('心跳发 /ping', calls.includes('POST /ping'), calls.join(','));

  calls.length = 0;
  els.btn.fire('touchend');
  await flush();
  check('松手发 /up', calls[0] === 'POST /up', calls.join(','));
  check('按钮恢复(on 移除)', !els.btn._classes.has('on'));
  check('文案回到「按住说话」', els.big.textContent === '按住说话', els.big.textContent);
  check('心跳已停', timersOf(400).length === 0);

  console.log('\n[3] 点按模式');
  els.mTap.fire('click');
  await flush();
  check('切到「点按」', els.mTap._classes.has('sel') && !els.mHold._classes.has('sel'));
  check('文案变「点一下」', els.big.textContent === '点一下', els.big.textContent);
  check('模式存进 localStorage', store.vt_mode === 'tap', String(store.vt_mode));

  calls.length = 0;
  els.btn.fire('touchstart');
  await flush();
  check('第一次点 → /down', calls[0] === 'POST /down', calls.join(','));

  calls.length = 0;
  els.btn.fire('touchend');            // 点按模式下松手什么都不该发生
  await flush();
  check('松手不发 /up', calls.filter((c) => c.indexOf('/up') >= 0).length === 0, calls.join(','));
  check('仍在听(on 保留)', els.btn._classes.has('on'));

  // 心跳继续续命 —— 点按模式靠它保持按下态
  const t2 = timersOf(400);
  check('点按期间仍有心跳', t2.length === 1);
  t2[0].fn(); await flush();
  check('心跳发 /ping', calls.includes('POST /ping'), calls.join(','));

  calls.length = 0;
  els.btn.fire('touchstart');          // 再点一下 = 结束
  await flush();
  check('第二次点 → /up', calls[0] === 'POST /up', calls.join(','));
  check('按钮恢复', !els.btn._classes.has('on'));
  check('文案回到「点一下」', els.big.textContent === '点一下', els.big.textContent);

  console.log('\n[4] 页面切走自动结束');
  calls.length = 0;
  els.btn.fire('touchstart'); await flush();
  calls.length = 0;
  ctx.document.hidden = true;
  ctx.__docL.visibilitychange(); await flush();
  check('切后台发 /up', calls.includes('POST /up'), calls.join(','));
  ctx.document.hidden = false;

  console.log('\n[5] 电脑状态回流');
  // 电脑端被别人松手了：本页应该跟着恢复
  els.btn.fire('touchstart'); await flush();
  serverState.holding = false;
  calls.length = 0;
  // 手动触发一次 tick（1200ms 定时器）
  const st = timersOf(1200);
  check('有 1200ms 状态轮询', st.length === 1);
  st[0].fn(); await flush(); await flush();
  check('电脑已松手 → 本页恢复', !els.btn._classes.has('on'), '仍显示听');
  check('文案回到「点一下」', els.big.textContent === '点一下', els.big.textContent);

  console.log('\n[6] 静音按钮');
  calls.length = 0;
  els.bMute.fire('click'); await flush(); await flush();
  check('点静音发 /mute', calls.includes('POST /mute'), calls.join(','));
  check('按钮变「恢复」', els.bMute.textContent === '恢复', els.bMute.textContent);

  console.log('\n' + '='.repeat(46));
  console.log(failed === 0 ? '全部通过 ✅' : `失败 ${failed} 项 ❌`);
  console.log('='.repeat(46));
  process.exit(failed === 0 ? 0 : 1);
})();