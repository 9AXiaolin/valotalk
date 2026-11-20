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
| 语音聊天输入设备 | **变音麦克风 (VB-Audio Virtual Cable)** |
| 语音聊天输出设备 | **你的耳机/扬声器**（**不要**选 Cable） |
| 语音聊天模式 | 见下 |

> ⚠️ 中文系统里 VB-Audio Cable 的两个端点名字是反的，别选错：
>
> - `变声器输出 (VB-Audio Virtual Cable)` = **播放端**，ValoTalk 往这里灌英文（面板上的「TTS 输出」）
> - `变音麦克风 (VB-Audio Virtual Cable)` = **录音端**，游戏从这取麦克风（游戏里的「语音输入」）

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

| 默认键 | 作用 |
|---|---|
| **按住 F2** | 说中文 → 队友听到英文（松开就翻译） |
| **F3** | 字幕窗在「穿透鼠标 / 可拖动」之间切换 |
| **F4** | 清空字幕 |
| **F5** | 临时静音英文输出（不想让队友听到时） |

**改键不用碰配置文件**：控制面板中间有「快捷键」一栏，四个下拉框选完立刻生效（会写回 `config.json`）。重复绑定、占用游戏开麦键 V 都会被拦下来并在日志里提示。

可选键位（23 个）：

```
F1 – F12
CapsLock、Tab、Insert、Home、End、Delete、PgUp、PgDn、`
MOUSE4、MOUSE5      ← 鼠标侧键（后退 / 前进）
```

两个约定：

- **字母键故意没开放** —— 打字、聊天时太容易误触
- **左右中键也没开放** —— 会干扰正常点击。只放鼠标侧键，因为 `GetAsyncKeyState` 能直接读到 `XBUTTON1/2`，当热键用是安全的

> 用鼠标侧键当触发键前，先看一眼游戏里这两个键有没有绑技能，避免按一下同时触发两件事。

字幕默认贴在**屏幕下方居中**，点面板上的「字幕贴回屏幕下方」可复位；关掉穿透后可以直接拖动它。

### 为什么说中文用 F2，不用游戏的 V

很多人第一反应是「V 不就是开麦键吗，为什么还要单独一个 F2」。因为这两个键在干**完全相反**的事：

| 键 | 谁按 | 作用 |
|---|---|---|
| **V** | **程序自动按** | 打开游戏麦克风，把英文 TTS 送出去 |
| **F2** | **你自己按住** | 告诉程序「现在开始听我说中文」，松手就翻译 |

程序播放英文之前会先替你按住 V、播完再松开（`tts.game_ptt_enabled` + `tts.game_ptt_key`）。你不需要手动碰它。

三个不能合并成同一个键的原因：

**1. 会自己触发自己。** 程序用 `SendInput` 注入 V，而热键是靠 `GetAsyncKeyState` 轮询的 —— 注入的键会被自己读到。播放完英文 → 被当成你又按了一次 → 再识别一遍 → 再播放，死循环。

**2. 游戏的开麦动作会插进来。** 你按 V 的瞬间游戏也在开麦，两条链路的状态互相打架。

**3. 语义相反。** V 是「我往外送声音」，F2 是「程序往里听我说话」。一个出、一个入。

#### 更省事的选择：用开放式麦克风

如果游戏语音模式设成 **开放式麦克风（Open Mic）**，就不用模拟按键了：

```jsonc
"tts": { "game_ptt_enabled": false }
```

麦克风一直开着，程序往 Cable 里播，游戏自动收走。**推荐这个** —— 没有按键时序问题，也不会偶尔和游戏抢键。

#### 想换触发键

**面板上直接改**：中间「快捷键」一栏，把「说中文」的下拉框选成 `CapsLock` 或别的，立刻生效，不用重启。

改完写回 `config.json` 的 `hotkeys.ptt`，想批量改也可以直接编辑文件：

```jsonc
"hotkeys": {
  "ptt": "capslock",
  "toggle_click_through": "f3",
  "clear_overlay": "f4",
  "toggle_mute_outgoing": "f6"       // 挪开，别和 ptt 撞
}
```

**只要别用 V**（那是游戏的），也别让四个键互相重复。

---

## 4. 模型怎么选（要不要 API key）

界面上有两处都叫「模型」，用途完全不同，先分清：

| | 开始按钮旁边的「模型」 | 翻译后端里的 `model` 输入框 |
|---|---|---|
| 是什么 | **本地语音识别**（Whisper） | **云端翻译**（qwen-plus / deepseek-chat 等） |
| 干什么 | 把队友的英文语音转成文字 | 把文字翻译成中文 |
| 跑在哪 | **你自己的电脑** | 阿里 / DeepSeek 的服务器 |
| **需要 key 吗** | **完全不需要** | **需要**（可选，不填也能用） |
| 花钱吗 | 免费 | 按 token 计费，约每万句几毛钱 |
| 体积 | 75 MB ～ 1.5 GB（首次下载，缓存在 `models/`） | 0，就是一次网络请求 |

**一句话：语音识别 0 个 key，纯本地离线跑；翻译可以配 LLM，不配也能用免费的 Bing。**

### 4.1 语音识别模型（Whisper，不需要任何 key）

| 模型 | 下载大小 | 显存占用 | 单句识别（GPU） | 单句识别（CPU） | 英文准确率 | 定位 |
|---|---|---|---|---|---|---|
| `tiny` | 75 MB | ~150 MB | 约 0.06s | ~0.5s | ~65% | 极限轻量，能听个大概 |
| `base` | 140 MB | ~250 MB | 约 0.12s | ~1.1s | ~78% | 轻量，偶尔错词 |
| **`small`（默认）** | **480 MB** | **~650 MB** | **0.25s（实测）** | 4.6s | ~87% | **平衡点，推荐** |
| `medium` | 1.5 GB | ~1.5 GB | 约 0.6s | ~14s | ~92% | 准，但吃显存、延迟高 |

> 「单句识别」指 3 秒左右的语音片段。`small` 的 GPU/CPU 数字是实测值，其余按模型规模推算。

**怎么选：**

| 遇到什么 | 改成 |
|---|---|
| 保持默认 | `small` |
| 字幕延迟明显（超过 2 秒） | `base` |
| 识别经常错字、影响理解 | `medium` |
| 游戏掉帧（显存不够） | `base` 或 `tiny` |
| 勾了「识别用 CPU」 | 必须 `tiny` 或 `base`（CPU 跑 `small` 比说话还慢） |

`tiny`/`base`/`small`/`medium` 都是多语言版。Whisper 还有英语专用版（`tiny.en`/`base.en`/`small.en`），同样大小但英文更准、快 10~20% —— 如果只用来听英文队友，换成 `.en` 版更划算，把 `config.json` 的 `asr.model` 改成 `small.en` 即可。

### 4.2 翻译模型（可选 key，不配也能用）

走四级降级：**LLM（若配置）→ Bing → Google → MyMemory**。

**免费通道（不需要任何 key）**

| 通道 | 需要什么 | 延迟 | 质量 | 说明 |
|---|---|---|---|---|
| **Bing** | 无 | 0.6–1.2s | 中 | **国内直连，默认首选** |
| Google | 需要梯子（填 `translate.proxy`） | 快 | 中上 | 有代理时质量比 Bing 略好 |
| MyMemory | 无 | 8–12s | 差 | 最后兜底，慢到影响体验 |

**云端 LLM（需要 key，质量最好）**

| 服务 | base_url | model | 延迟 | 备注 |
|---|---|---|---|---|
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | 0.7s | **实测推荐**，语境最自然 |
| 通义千问（更快） | 同上 | `qwen-turbo` | 0.4s | 快一点，质量略降 |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | 0.5–1s | 便宜，质量好 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` | 快 | 免费额度多 |

**本地 LLM（不需要 key，文字不出本机）**

| 服务 | base_url | model | 备注 |
|---|---|---|---|
| Ollama | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` | 完全不联网，吃本机显存/内存 |

**质量差距有多大**（同一句实测）：

```
LLM:   A点敌人一枪头，小心侧翼！
Bing:  敌人一次击杀在A点，小心侧翼。（one tap=一枪头，flank=绕后）
```

机翻需要用术语表注释来救场，LLM 本身就译对了。

### 4.3 隐私去向

| 数据 | 去哪 |
|---|---|
| 你的语音、队友语音 | **只在本机**（Whisper 本地推理），不上传 |
| 识别出的文字 | 发给翻译服务（Bing 或通义） |
| 翻译结果 | 传回来显示 |

在意的话两个选择：只填空 LLM 三格（走 Bing），或者指向本地 Ollama（连文字都不出本机）。

### 4.4 有梯子

`config.json` → `translate.proxy` 填 `http://127.0.0.1:7890`，Google 通道就通了，质量比 Bing 略好。

### 4.5 中→英喊话表

`translate.py` 里的 `VOICE_LINES` 是一张整句直出表（`我开大了` → `Using my ultimate now.`、`掩护我` → `Cover me.`…）。游戏里 90% 的话是固定短句，命中表就绕过机翻，又快又准。想加自己的口头禅直接往里添。

### 4.6 英文缩写直出表

反方向由 `_DIRECT_EN_ZH` 处理。队友打的这些缩写，机翻要么原样吐回来、要么译成别的意思，所以直接给答案，**零延迟、不联网**：

| 原文 | 译文 |
|---|---|
| `+4` | 在家挂机 |
| `afk` | 挂机中 |
| `brb` | 马上回来 |
| `omw` | 在路上了 |
| `+1` | 同意 |
| `nt` / `gj` / `wp` / `gg` / `ns` / `ez` | 可惜 / 干得漂亮 / 漂亮 / 打得好 / 好枪 / 轻松 |

匹配时会忽略空格和大小写，`+ 4`、`AFK` 一样能命中。带上下文的句子（比如 `+4 guys, going afk now`）仍然走机翻。

---

## 5. 性能（本机实测，RTX 4060）

各模型的速度、准确率、显存占用完整对比见上面 **4.1 语音识别模型**。这里只列关键的 RTF 指标：

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

### 帧率影响（60–200 横跳怎么解决的）

实测排除了两个常见嫌疑：

| 嫌疑 | 实测 | 结论 |
|---|---|---|
| mss 截屏读回显存 | 30 次抓取，中位 5.6ms，最大 11.4ms，无一次超 20ms | 不是它 |
| whisper 抢占 GPU | 单次推理 GPU 峰值 51%；连续 6 次里 **0% 的时间显卡被占满** | 不是它 |

真凶是**字幕窗口本身在打断全屏合成**：分层透明窗口每 500ms 调一次 `SetWindowPos` 置顶，会破坏全屏游戏与显示器可变刷新率的同步，帧率就在刷新率上限和 60 之间反复跳。

| 改动 | 之前 | 现在 |
|---|---|---|
| 置顶检查间隔 | 500ms | **3s**（且只在有新字幕时额外置顶一次） |
| 描边层数 | 8 层 | **4 层** |
| canvas 元素数 | 90 个（9 条 × 10） | **35 个**（6 条 × 6） |
| 字幕窗口高度 | 380 | **300** |
| 聊天 OCR 间隔 | 1200ms | **2000ms** |
| 面板电平刷新 | 40ms（每秒重排 25 次） | **200ms**（每秒 5 次） |

还加了个彻底的开关：**「识别用 CPU（不抢显卡，稍慢）」**。勾上之后识别完全退出显卡，游戏独占 GPU。注意 CPU 上 `small` 很慢（RTF≈1.8），勾了要同时把模型换成 `base` 或 `tiny`。

如果还掉帧，按这个顺序排查：

1. 关掉「左下角聊天翻译」→ 还卡说明不是抓屏
2. 勾上「识别用 CPU」→ 还卡说明不是显卡
3. 把 `overlay.max_lines` 调成 3、`outline` 设 `false` → 还卡说明不是字幕窗口，检查是不是游戏本身或驱动
4. `overlay.backdrop` 设 `true` 换回黑底（不透明窗口的合成开销远小于分层透明）

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