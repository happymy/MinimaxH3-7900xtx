# MiniMax H3 提示词书写规则

> 依据官方两份写作指南（本机官方 skill `h3-prompt-writing` 的 `references/base-en.txt`、`references/ref-en.txt`）、ComfyUI 官方提示词页、本机节点源码 `minimax_h3_prompt.py`。
> **核心原则：长结构化时间线，三字段缺一不可。**

---

## 1. 四种模式的信封结构

提示词本体写英文。**除 `<d>` 内的对白/歌词、以及画面上可见文字外，全部用英文。**

### 1.1 指令行（第一段，空一行隔开三字段）

| 模式 | 指令行（逐字照写） |
|---|---|
| **T2VA** | 无指令行，直接从三字段开始 |
| **I2VA** | `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` |
| **FL2VA** | `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` |
| **L2VA** | `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` |

`S.SS` = 实际时长，**必须两位小数**（如 `5.17`）。`N` = 该图实际所属的分镜号。

### 1.2 三字段（顺序固定，不可调换、不可省略）

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

| 字段 | 写什么 | 长度 |
|---|---|---|
| `integrated_multimodal_description` | 视觉风格、构图、主体外观位置、场景道具、动作反应、切镜、说话人、对白/唱歌、**同步的画内音效** | 主体，无硬性上限 |
| `overall_soundscape` | 全片的环境声、物理动作声、非语言人声（呼吸/笑声/喘息） | 1–4 句 |
| `non_diegetic_music` | 只有观众听得到、角色听不到的配乐：乐器、速度、节奏、动态变化 | 1–3 句 |

> ⚠️ **最常见的严重踩坑：漏掉后两个字段。** 三字段缺失会显著掉质量。
> 没有音景时写 `overall_soundscape: N/A`；没有配乐时写 `non_diegetic_music: N/A`——**写 `N/A`，不要整段删掉**。

### 1.3 两个音景字段的边界

- **对白、唱歌、画内音乐** → 属于 `integrated_multimodal_description`，**不要在音景字段里重复**。
- 收音机/电视/手机里角色能听到的音乐 → 属于**画内事件**，写进 `integrated_multimodal_description`，不是 `non_diegetic_music`。
- `non_diegetic_music` **不要写情绪词、不解释配乐的作用**，只写乐器/速度/节奏/强弱变化。

```text
overall_soundscape: Steady rain taps against the café windows while low room ambience continues underneath. The entrance bell rings once, followed by wet footsteps and the soft scrape of a chair.

non_diegetic_music: Sparse piano notes at a slow tempo, joined by sustained low strings that gradually increase in volume before fading out.
```

---

## 2. `integrated_multimodal_description` 写法

### 2.1 开头：风格 + 初始构图

`[Shot 1]` 之后立刻给整体风格和初始构图。风格词：`Cinematic` / `live-action` / `2D-animated` / `3D CG` / `claymation` / `watercolor` / `vintage film`。

```text
[Shot 1] Live-action, cinematic, a medium-wide shot frames a baker opening the shutters of a small street bakery before sunrise.
```

### 2.2 分镜与切点

- `[Shot 1]` **不带时间戳**。
- 后续分镜用**严格递增**的切点时间，落在片长之内，格式 `[Shot N] At MM:SS.mmm, ...`：

```text
[Shot 2] At 00:03.500, the camera cuts to a close-up of steam rising from the sliced bread.
```

- 普通切换词：`the camera cuts to` / `the shot cuts to` / `the shot transitions to` / `the shot changes to` / `the shot switches to`。用户明确要求时才用 cross-dissolve / fade / wipe。
- **切镜必须带来新信息**（主体、空间、状态、视角、时间）。如果只是距离或角度微调，**改用摄影机运动，不要切**。

### 2.3 摄影机运动：类型 + 幅度 + 速度

三个维度，**幅度和速度只在有意义时写**（中幅度、正常速度通常省略）。

| 维度 | 可选表达 |
|---|---|
| 运动类型 | `Zoom In / Zoom Out`（机身不动，变焦）<br>`Push In / Pull Out`（机身前后移动）<br>`Pan Left / Pan Right`（机身不动，水平摇）<br>`Truck Left / Truck Right`（机身水平平移）<br>`Tilt Up / Tilt Down`（机身不动，俯仰）<br>`Pedestal Up / Pedestal Down`（整机升降）<br>`Arc Shot`（绕主体弧线移动）<br>`Tracking Shot`（跟随运动主体）<br>`Static Shot`（机位与镜头均不动）<br>`Shake Slightly / Shake Strongly`<br>`POV`（视点视角）<br>`Roll Clockwise / Roll Counterclockwise` |
| 幅度 | `with small amplitude` / `with large amplitude` |
| 速度 | `at slow speed` / `at fast speed` |

**必须写成句子里自然的英文动作，不要在句尾堆标签。**

```text
The camera pushes in with small amplitude at slow speed toward the folded letter in her hands.
The camera pans right with large amplitude at fast speed, revealing the open doorway.
The camera holds a static shot as the runner exits the frame.
```

### 2.4 说话人、对白、唱歌

发声主体（说话、唱歌、画外人声）用稳定 ID：`(S1)`、`(S2)`；多人同时发声用复合 ID `(S1,S2)`。

- **一个角色跨分镜保持同一个 ID**。全程不发声的角色**不给 ID**。
- 说话人**首次出现**时给足身份信息（角色类型、年龄、性别、是否在画面内、音高、音色、语速、口音），且**这些描述短语、ID、动作、语气全部写在 `<d>` 之外**。

```text
The young woman with a quiet, breathy voice (S1) says: <d>[English] I get off at the next station.</d>
The two children (S1,S2) shout together, <d>[English] Wait for us!</d>
```

**`<d>` 内部只放语言标签和台词本身**，逐字保留原文的每一个词和标点，**不翻译、不改写**。

画外音用固定短语 `says in an off-screen voiceover`，且**紧跟 `<d>` 之后说明画面角色嘴部保持闭合**：

```text
The man (S1) says in an off-screen voiceover: <d>[English] I still remember that road.</d> while his lips remain completely closed.
```

台词/歌词跨切点时，在**两段**里都用 `<scenetrans>` 标出接续处，并明说音频连续；被片尾截断用 `<cutoff>`。可用措辞：`continues seamlessly across the cut` / `continues uninterrupted into the next shot` / `carries over from the previous shot` / `remains audible across the transition`。

```text
[Shot 2] At 00:05.000, the camera cuts to a close-up of steam rising from the sliced bread while the baker's final words carry over from the previous shot.
```

### 2.5 画面可见文字

招牌、标牌、字幕、霓虹等**实际出现在画面里的文字**，用**英文双引号**括起，**保留原文逐字照写，不翻译**。

```text
A red neon sign reading "营业中" glows above the doorway.
```

> ⚠️ **`<d>` 和引号是两回事**：`<d>` = 说出来/唱出来的声音；`"..."` = 画面上看得见的字。

---

## 3. 各模式正文的组织顺序

| 模式 | 推荐顺序 |
|---|---|
| **T2VA** | 从文本直接构建完整时间线，可补充与用户意图一致的场景/角色/动作/声音细节 |
| **I2VA** | 以 `<Picture 1>` 的人物、构图、场景作为 Shot 1 的起点，再描述画面如何继续发展 → **首帧锚点 → 动作起势 → 连续发展 → 结果/反应** |
| **FL2VA** | Picture 1 是开头，Picture 2 是结尾。正文**不要重复两幅静态图描述**，要写连接两者的运动路径 → **首帧状态 → 可观察的中间变化 → 差异逐步收窄 → 末帧状态**。FL2VA 一般用**单镜头**让模型连续插值；末帧必须由最后一个 `[Shot N]` 抵达 |
| **L2VA** | `<Picture 1>` 是**末帧**，属于最后一个 `[Shot N]`，不属于 Shot 1。先推断合理的前置状态 → **合理的前置状态 → 明确的动作与过渡 → 末镜逐渐收敛 → 落到末帧** |

---

## 4. 必须避免的踩坑

| 坑 | 说明 | 正确做法 |
|---|---|---|
| **漏写音景字段** | 最严重。三个字段是信封，缺字段显著掉质量 | 必写三项，没内容就写 `N/A` |
| **三字段顺序调换 / 标签写错** | 标签拼写或顺序错了，解析直接失效 | 逐字照抄 `integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music` |
| **`Shot 1` 加时间戳** | 首镜禁止带时间戳 | 后续分镜才写 `At MM:SS.mmm` |
| **切点时间不递增或越界** | 必须严格递增且落在片长内 | 写之前先按分镜数分配时间 |
| **为微调角度而切镜** | 切镜必须带来新信息，否则画面碎 | 改用摄影机运动 |
| **摄影机运动堆在句尾成标签** | 写成自然英文动作句 | 见 §2.3 |
| **`<d>` 里做翻译或改写** | 台词必须逐字保留原文与标点 | `<d>` 只放 `[语言] 原文` |
| **把台词重复进音景字段** | 对白/唱歌只在正文里 | 音景只写环境声与物理声 |
| **翻译画面可见文字** | 屏幕文字保留原文，用英文双引号括起 | `A sign reading "营业中"` |
| **在 `non_diegetic_music` 写情绪词** | 只写乐器/速度/节奏/动态 | `Sparse piano notes at a slow tempo` |
| **用摄影器材参数代替光线描述** | `85mm` / `f/1.8` / `ARRI Alexa 65` 属于元信息 | 用具体方向描述：`Broad diffused illumination from a large source` |
| **堆砌画质词** | `8K UHD` / `hyper detailed` / `masterpiece` 稀释实际描述 | 删除，靠 §2.1–2.3 的具体描述提质 |

### 4.1 长度：`length` 是帧数，且**取整是静默的**

- `length` 传的是**帧数**（24 fps）。默认 124 帧 ≈ 5.17 s。
- 帧数会**向上吸附**到 `17k + 5` 栅格。常用档：

| 帧数 | 时长 |
|---|---|
| 124 | 5.17 s |
| **192** | **8.00 s（整秒，唯一整秒档）** |
| 243 | 10.13 s |
| 362 | 15.08 s |
| 481 | 20.04 s |

- 合法范围 **124–481 帧**；**124 帧是训练下限**。
- ⚠️ **静默取整**：传 110 或 120 都会被拉到 124；传 200 会变成 209。**不报错、不告警**。写分镜时间点前先确认实际帧数，否则末尾分镜会被压扁。

### 4.2 原生画布

官方原生短边 **768 px**（16:9 → `1344×768`），尺寸按 32 对齐。低于原生尺寸可以跑，画质会掉但不会崩。

---

## 5. 风格嵌入（可选）

`Comfy-Org/MiniMax-H3` 仓库的 `embeddings/` 提供 10 个风格嵌入，**文件名去掉 `.safetensors` 即触发词**，放进 `models/embeddings/` 后在提示词里写 `embedding:minimaxh3_*`：

| 触发词 | 触发词 | 触发词 |
|---|---|---|
| `embedding:minimaxh3_art_is_explosion` | `embedding:minimaxh3_dark_magic` | `embedding:minimaxh3_kiss_camera` |
| `embedding:minimaxh3_blooming_flowers` | `embedding:minimaxh3_fire_breath` | `embedding:minimaxh3_spiral_ascent` |
| `embedding:minimaxh3_bullet_time` | `embedding:minimaxh3_four_seasons` | `embedding:minimaxh3_storm_magic` |
| | | `embedding:minimaxh3_truman_show` |

> ⚠️ **本机尚未安装这 10 个嵌入**（`models/embeddings/` 为空）。未安装时写入触发词 = 普通文本词，不会报错但也没有效果。

---

## 6. R2V（全参考 / 多素材改写）六段结构

当任务需要引用外部素材（人物、场景、视频、音频）时，改写输出是**六段**，不是三字段：

| 段 | 作用 |
|---|---|
| `subject_definitions` | 定义被引用内容及其引用标签 |
| `summary` | 任务类型 + 目标视频 + 主要引用关系 |
| `retention_analysis` | 被引用内容如何被保留/迁移/复用 |
| `detailed_description` | **按播放顺序**写视觉、动作、分镜、声音、对白 |
| `overall_soundscape` | 同基础模式 |
| `non_diegetic_music` | 同基础模式 |

### 6.1 四类引用标签

| 标签 | 含义 |
|---|---|
| `<Subject N>` | 从参考素材中抽象出的、会被复用或修改的**可见内容**（人物/动物/物体、场景、服装道具、风格、动作表情） |
| `<Picture N>` | 作为**具体目标帧**或分镜规划锚点的参考图 |
| `<Video N>` | 提供剪辑源、续写起点或整片时间结构的参考视频 |
| `<Audio N>` | 被复制或参考的音频信号 |

> 标签一旦分配，**在六段里含义保持不变**。`<Video N>` 与 `<Audio N>` **各自独立编号**，编号不含配对关系。

### 6.2 `summary` 的任务类型前缀

方括号前缀，多任务用 ` + ` 连接、不重复：

| 任务类型 | 何时用 |
|---|---|
| `keyframe completion` | 图作为首帧/关键帧/末帧/编辑后关键帧等具体帧锚点 |
| `reference generation` | 素材提供人物、场景、风格、动作、运镜、分镜等生成指导，但不作具体帧、也不是被剪辑/续写的源 |
| `video editing` | 直接修改已有源视频 |
| `video continuation` | 从已有源视频续写、延长、衔接 |
| `audio reuse` | 同一音频信号被完整或部分复用 |
| `audio reference` | 音频不直接复制，只参考音乐风格、音色、台词歌词、音效质感、节拍或连续性 |

```text
[video editing + audio reuse] ...
[video continuation + keyframe completion] ...
```

> 参考视频**只提供运镜/剪辑/节奏**时属于 `reference generation`，不属于 `video editing`。剪辑源视频且原声仍可闻时，**必须**加 `audio reuse`。

### 6.3 `retention_analysis` 关系标记词（固定值，逐字照写）

视觉（`<Subject N>` / `<Picture N>` / `<Video N>`）：

| 标记 | 含义 |
|---|---|
| `fully_preserved` | 定义的角色被完整保留 |
| `partially_preserved` | 仍被使用，但部分既定特征被改动或只部分保留 |
| `attribute_transfer` | 特征被迁移到另一个可识别的目标主体 |
| `weak_reference` | 只保留风格/类别/构图/氛围上的宽泛相似 |

音频（`<Audio N>`）：

| 标记 | 含义 |
|---|---|
| `fully_copy` | 完整源音频作为目标视频的完整最终音轨 |
| `partially_copy` | 只复制部分时间轴或部分音层，或复制后有增删替换 |
| `reference` | 不直接复制，只参考音色、节奏、音乐风格、台词内容或音效质感 |
| `weak_reference` | 只保留类别或氛围上的宽泛相似 |

```text
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - ...
<Picture 2> ([Shot 1] first frame): fully_preserved - ...
<Video 1> (cut and pacing structure): weak_reference - ...
<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.
```

> `retention_analysis` 里**不写 `(Sx)`**。目标视频里**新加**的动作、背景、情节事件**不算**引用保真度的损失，不要改标记词。

### 6.4 R2V 与基础模式的差异

| 维度 | 基础模式（T2VA/I2VA/FL2VA/L2VA） | 全参考模式 |
|---|---|---|
| 主体字段 | `integrated_multimodal_description` | `detailed_description` |
| 风格开场 | 写在 `[Shot 1]` 之后 | 在 `[Shot 1]` 之前用 1–2 句英文单独确立 |
| 引用信息 | 不用引用标签 | 在首次出现处及角色生效处插入 `<Subject N>` / `<Picture N>` / `<Video N>` / `<Audio N>` |
| 音频关系 | 描述目标视频自身声音 | 在对应分镜或音频段落引用 `<Audio N>`，并说明是复制还是参考 |

- **生成任务**的 `detailed_description` 通常 **350–500 英文词**。台词密集的内容优先保证完整口语时间线，不机械凑词数。**单镜头不等于可以写短**。
- `<Subject N>` 标识被引用主体，`(Sx)` 标识实际发声者。主体发声时写 `<Subject N> (Sx)`。
- 复用 BGM/完整音轨里的**纯人声提示**（如歌词 cue）时，**不另造 `(Sx)`**，直接用 `<Audio N>` 作音源。
- 直接复用参考音频的台词/歌词时，逐字保留原文与语言；听不清的部分写 `[unclear]`，**不要猜或改写**。

---

## 7. 即用模板（T2VA）

```text
integrated_multimodal_description: [Shot 1] {Cinematic / live-action / 3D CG}, a {景别} frames {主体} {外观与服装} {在场景中的位置与正在做的事}. The camera {运动类型 with small amplitude at slow speed} as {可见的连续动作与状态变化}. {氛围与非语言人声细节}. {说话人身份描述 (S1)} {动作/语气}, <d>[English] {逐字台词}.</d> [Shot 2] At 00:0X.XXX, the camera cuts to {新信息：新主体/新空间/新状态/新视角} while {跨切点音频用 carries over from the previous shot 或 <scenetrans> 标明连续}.

overall_soundscape: {1–4 句：环境声 + 物理动作声 + 非语言人声}.

non_diegetic_music: {1–3 句：乐器、速度、节奏、动态变化} 或 N/A.
```

**实际示例：**

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, a medium-wide shot frames a baker opening the shutters of a small street bakery before sunrise. The camera pushes in with small amplitude at slow speed as the middle-aged baker with a calm, slightly raspy voice (S1) places a fresh loaf on the wooden counter and says: <d>[English] First batch of the morning.</d> [Shot 2] At 00:05.000, the camera cuts to a close-up of steam rising from the sliced bread while the baker's final words carry over from the previous shot.

overall_soundscape: Wooden shutters scrape open over a quiet street as trays clink softly inside the bakery. The doorbell rings once, followed by light footsteps and the crisp sound of bread being sliced.

non_diegetic_music: A soft acoustic-guitar pattern at a moderate tempo, joined by sparse upright-bass notes and a gentle fade at the end.
```

---

## 8. 一页速查清单

- [ ] **三个字段都在**，顺序是 `integrated_multimodal_description` → `overall_soundscape` → `non_diegetic_music`，标签逐字正确
- [ ] **没有内容也写 `N/A`**，没有整段删字段
- [ ] **提示词本体全英文**；只有 `<d>` 内台词和画面可见文字保留原语言
- [ ] **`[Shot 1]` 没有时间戳**；后续分镜用 `At MM:SS.mmm` 且严格递增、不越界
- [ ] **每个切镜都带来新信息**；微调角度改用摄影机运动
- [ ] **摄影机运动写成自然英文句**，不是句尾标签堆
- [ ] **发声主体有稳定 `(S1)`/`(S2)`**，跨分镜不变；不发声的角色没有 ID
- [ ] **`<d>` 内只有语言标签和逐字原文**，身份描述/ID/动作/语气都在 `<d>` 之外
- [ ] **画外音**用了 `says in an off-screen voiceover` + 嘴部闭合说明
- [ ] **跨切点台词**用了 `<scenetrans>` + 连续性措辞；被截断用 `<cutoff>`
- [ ] **画面可见文字**用英文双引号括起并逐字保留原文
- [ ] **对白/唱歌没有重复**进音景字段
- [ ] **`non_diegetic_music` 只写乐器/速度/节奏/动态**，没有情绪词、没有画内音乐
- [ ] **没有器材参数**（`85mm` / `f/1.8` / 机型名），光线用方向描述
- [ ] **没有画质堆砌词**（`8K` / `hyper detailed` / `masterpiece`）
- [ ] **帧数已核对**（124 / 192 / 243 / 362 / 481），分镜时间点按实际帧数分配
- [ ] **R2V 任务是六段**，不是三字段；`retention_analysis` 的标记词逐字照写，且没写 `(Sx)`

**核心铁律：H3 的提示词是「一份有时间轴的拍摄脚本」，不是「一段描述」。字段写全、时间线写准、音景不省，比任何画质词都有效。**
