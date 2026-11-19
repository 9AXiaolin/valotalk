# ValoTalk —— 无畏契约国际服实时翻译

打国际服听不懂队友、自己不会用英文喊话、看不懂左下角聊天？这个工具一次解决：

| 链路 | 方向 | 结果 |
|---|---|---|
| **① 队友语音** | 游戏声音 → 语音识别 → 翻译 | **中文字幕出现在屏幕下方** |
| **② 我说话** | 按住 F2 说中文 → 翻译成英文 → TTS 念出来 | 声音通过 VB-Audio Cable 送进游戏麦克风，**队友能听见英文** |
| **③ 左下角聊天** | 截屏 → OCR → 翻译 | 同一块字幕里显示中文 |

识别用本地 faster-whisper（不传云端），翻译走 Bing / Google / 你的 LLM，全离线也能跑（SAPI 兜底 TTS）。

---

## 1. 装

需要 Python 3.10+ 和 **VB-Audio Virtual Cable**（把 TTS 音频送进游戏麦克风的关键，免费）。

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

脚本会：装依赖（阿里云镜像）→ 预下载 whisper 模型（hf-mirror）→ 跑环境自检。

启动：**双击 `run.bat`**。

---

## 2. 游戏内设置（这一步不做，英文送不进游戏）

### 2.1 麦克风指向虚拟线缆

游戏 → 设置 → 音频 → 语音聊天：

| 项 | 设成 |
|---|---|
| 语音聊天输入设备 | **麦克风 (VB-Audio Virtual Cable)** |
| 语音聊天输出设备 | **你的耳机/扬声器**（**不要**选 Cable） |
| 语音聊天模式 | 见下 |

> ⚠️ 中文系统里 VB-Audio Cable 的两个端点名字是反的，别选错：
>
> - `输出 (VB-Audio Virtual Cable)` = **播放端**，ValoTalk 往这里灌英文（面板上的「TTS 输出」）
> - `麦克风 (VB-Audio Virtual Cable)` = **录音端**，游戏从这取麦克风（游戏里的「语音输入」）

**关于 Push to Talk：** 两种都行。

- **开放式麦克风（Open Mic）** —— 最省事，ValoTalk 一播就直接出去。
- **按键说话（Push to Talk）** —— 把键位绑到 `V`，ValoTalk 会在播放前自动按住 V、播完再松手（配置项 `tts.game_ptt_enabled` / `tts.game_ptt_key`）。

> 队友语音能被采集，靠的是扬声器回环（WASAPI loopback）。所以**游戏的语音输出必须是耳机**，一旦也设成 Cable，就会自己听自己。

### 2.2 显示模式必须是窗口化

游戏 → 设置 → 视频 → 显示模式：**窗口化全屏** 或 **无边框**。

独占全屏（Exclusive Fullscreen）下，任何浮层都画不上去，字幕会看不见。

### 2.3 建议把音效调小

队友语音和枪声、脚步混在同一条输出里。音乐/音效音量降到 40% 左右，识别率明显更好。

---

## 3. 用

双击 `run.bat`，出现控制面板：

1. **设备**三行会自动识别好，不对就手动选：
   - 游戏输出（采队友语音）→ 你的耳机
   - 我的麦克风 → 你的真实麦克风
   - TTS 输出 → **CABLE Input (VB-Audio Virtual Cable)**
2. 点 **测试 TTS→游戏**，进游戏按一下语音键，能听见英文就通了。
3. 点 **框选左下角聊天**，拖一个框把聊天框圈住（Esc 取消）。
4. 顶部 **▶ 开始**（启动时会自动开始一次）。

### 快捷键（全局，游戏里也生效）

| 键 | 作用 |
|---|---|
| **按住 F2** | 说中文 → 队友听到英文（松开就翻译） |
| **F3** | 字幕窗在「穿透鼠标 / 可拖动」之间切换 |
| **F4** | 清空字幕 |
| **F5** | 临时静音英文输出（不想让队友听到时） |

字幕默认贴在**屏幕下方居中**，点面板上的「字幕贴回屏幕下方」可复位；关掉穿透后可以直接拖动它。

---

## 4. 翻译质量怎么调

默认顺序：**LLM（若配置）→ Bing → Google → MyMemory**。Bing 通道国内可直连，单条约 0.6–1.2s。

### 想明显更准 → 配个 LLM

面板上填三格点保存（任何 OpenAI 兼容服务都行）：

| 服务 | base_url | model |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| 本地 Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |
| 通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

配上之后游戏语境会好非常多（机翻会把「开大」翻成奇怪的俚语，LLM 不会）。

### 有梯子

`config.json` → `translate.proxy` 填 `http://127.0.0.1:7890`，Google 通道就通了，质量比 Bing 略好。

### 中→英喊话表

`translate.py` 里的 `VOICE_LINES` 是一张整句直出表（`我开大了` → `Using my ultimate now.`、`掩护我` → `Cover me.`…）。游戏里 90% 的话是固定短句，命中表就绕过机翻，又快又准。想加自己的口头禅直接往里添。

---

## 5. 性能（本机实测，RTX 4060）

| 配置 | 单句识别 | RTF | 能不能用 |
|---|---|---|---|
| **small + GPU（当前默认）** | **0.23–0.31s** | **0.10** | ✅ 实时 |
| small + CPU | 4.6s | 1.76 | ❌ 比说话还慢 |
| base + GPU | ~0.12s | ~0.05 | ✅ 更快，准确率略降 |
| tiny + GPU | ~0.07s | ~0.03 | 抢答用，错字多 |

> GPU 加速要求 `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`（已装好，约 1.2GB）。
> ValoTalk 启动时会自动把它们的 `bin` 目录注入 DLL 搜索路径；缺库会自动退回 CPU 并在日志写明，
> 失败的设备会被记住 7 天，不会每次都白等一遍。

**端到端延迟**（队友说完 → 屏幕出现中文）：

```
VAD 收尾 0.4s  +  识别 0.25s  +  翻译 0.7s  ≈ 1.4s
```

想更快：`audio.vad.silero_end_gap_ms` 降到 250、把翻译换成便宜的本地 LLM。

模型面板右上角可直接切换（tiny/base/small/medium），换完自动重载。

### 资源占用（影响游戏帧数，已优化）

| | 优化前 | 优化后 |
|---|---|---|
| CPU（单核当量） | **1236%** | **107%** |
| 整机 CPU（24 线程） | 51.5% | **4.5%** |
| 内存 | 813 MB | 800 MB |
| GPU 显存 | ~0.5 GB | ~0.5 GB |

元凶是 **onnxruntime 默认 `intra_op_num_threads=0`＝有多少核用多少核**：一次 OCR 墙钟只有 178ms，却吃掉 2822ms CPU（16 个核一起上），每 0.6 秒来一次就是 4.7 个核常驻。

现在的做法：

- onnxruntime 强制 `intra_op_num_threads=2`、`inter_op=1`、`ORT_SEQUENTIAL`
- whisper `cpu_threads=2`
- 聊天 OCR 间隔 600ms → **1200ms**
- Silero 分析窗口 12s → **8s**
- 进程优先级降到 **Below Normal**，游戏永远优先拿到时间片

想再省一点：把「左下角聊天翻译」开关关掉，OCR 是剩下的大头；或者 `asr.compute_type` 改 `int8_float16` 省显存。

---

## 6. 配置速查（`config.json`）

```jsonc
{
  "asr":     { "model": "small", "device": "auto", "lang_teammates": "en", "lang_me": "zh" },
  "audio":   { "game_output_device": "...", "mic_device": "...", "tts_output_device": "CABLE Input..." ,
               "vad": { "silence_ms": 420, "max_utterance_ms": 12000 } },
  "translate": { "backend": "auto", "proxy": "", "llm": { "base_url": "", "model": "", "api_key": "" } },
  "ocr":     { "region": [x1,y1,x2,y2], "interval_ms": 600, "min_confidence": 0.5 },
  "tts":     { "voice": "en-US-GuyNeural", "rate": "+10%", "game_ptt_enabled": true, "game_ptt_key": "v" },
  "overlay": { "font_size": 19, "backdrop": false, "outline": true,
               "ttl_seconds": 30, "click_through": true, "show_original": true }
}
```

字幕样式：

- `font_size` 字号（像素），觉得小就调大，19 是当前值
- `backdrop` 黑色底板，默认 **关**；关掉后靠 `outline`（8 向描边）保证在亮背景上也看得清
- `show_original` 是否在译文下面显示英文原文（小一号灰字）
- 想让字幕更高或更宽，改 `height` / `width`，内容永远从底部往上堆

改完重启 `run.bat`。面板上改的项会立刻存盘。

---

## 7. 排障

先跑：

```powershell
python -X utf8 tools\probe_env.py
```

| 现象 | 原因 / 处理 |
|---|---|
| 队友说话没字幕 | 面板里「游戏输出」选错；或游戏语音输出走了 CABLE。先看日志有没有 `采集队友语音`，再看有没有 `队友：... → ...` |
| 字幕不出现但日志有内容 | 游戏是独占全屏；或字幕窗跑到屏幕外——点「字幕贴回屏幕下方」 |
| 说中文没反应 | 麦克风选错；F2 被游戏占用（改 `hotkeys.ptt`）；模型还在加载（看日志「模型」行） |
| 队友听不到英文 | TTS 输出不是 `CABLE Input`；游戏麦克风没指向 `CABLE Output`；PTT 键位和 `tts.game_ptt_key` 不一致 |
| 英文念得断断续续 | 把 `audio.capture_samplerate` 改 44100 试试；或换 `tts.engine: "sapi"` 走离线 |
| 翻译失败 | 日志里 `translate` 那行；Bing 偶尔限流，配 LLM 最稳 |
| 识别全是乱七八糟 | 音乐音效太大；换 `small` 以上模型 |
| 播报自己又被识别 | 游戏语音输出别设 CABLE；或用 F5 暂时静音 |

其他：`asr.device` 写 `"cuda"` 但没装对 CUDA，会自动回落到 CPU（日志里能看到 `cpu / int8`）。

---

## 8. 自测脚本（不用打游戏也能查）

```powershell
$py = "python"
& $py -X utf8 tools\probe_env.py          # 全套自检：依赖/设备/翻译/OCR/TTS
& $py -X utf8 tools\selftest.py           # 离线冒烟：重采样/VAD/去重/翻译
& $py -X utf8 tools\boot_test.py          # 真启动 40 秒，看模型和采集是否就绪
& $py -X utf8 tools\capture_stability.py  # 采集稳定性（应 100%）
& $py -X utf8 tools\uitest.py             # 字幕排版（存 cache/ui_shot.png）
& $py -X utf8 tools\quality_test.py       # 音质对比：均值/左/右声道谁识别得准
```

`boot_test.py` 里 `采集源` 那行最有用：`running=True` + `peak` 会随声音跳动，说明麦克风和游戏音频都收进来了。

## 9. 已知行为

- **启动时会有一次采集异常**（`'bytes' object has no attribute 'size'`），设备刚打开时的瞬时问题，之后 12 秒压测 100% 稳定，可以忽略。
- **字幕延迟 ≈ 1.4s**，主要花在「等你说完」的 0.42s 静音判定上，调小 `vad.silence_ms` 能更快但容易把一句话切断。
- **7.1 虚拟声卡**（7.1 耳机/虚拟声卡很常见）采集时只取 L/R，直接对 8 声道取均值会把前场人声衰减 4 倍。
- **首句识别会慢**：模型第一次加载约 30s（含 GPU 转换），之后就绪了。面板右上角切模型会自动重载。
- **聊天只翻玩家说的话**：必须带「名字: 内容」前缀才算聊天。`Spike has been planted`、`Round 5`、`Enemy remaining: 2`、`XXX joined the party` 这类系统广播整行丢掉，不占字幕位。
- **字幕无黑底**，改用文字描边（8 向 1px）。如果觉得在深色场景下不够清楚，把 `overlay.backdrop` 设 `true` 换回黑底。
- **翻译失败时字幕只显示英文原文**，不会静默丢掉。

---

## 10. 结构

```
valotalk/
├─ run.bat                启动
├─ setup.ps1              一键装依赖 + 下模型
├─ config.json            配置（首次启动生成）
├─ models/                whisper 权重
├─ valotalk/
│  ├─ app.py              编排 + 主面板
│  ├─ capture.py          WASAPI 回环/麦克风采集 + VAD 断句 + 按设备播放
│  ├─ asr.py              faster-whisper 封装（懒加载、幻觉过滤）
│  ├─ translate.py        多通道翻译 + 术语表 + 喊话直出
│  ├─ tts.py              edge-tts / SAPI → VB-Cable
│  ├─ ocr.py              截图 OCR + 新增行 diff
│  ├─ overlay.py          屏幕下方悬浮字幕
│  └─ winapi.py           全局热键轮询、按键注入、点击穿透
└─ tools/
   ├─ probe_env.py        环境自检
   └─ selftest.py         离线冒烟测试
```