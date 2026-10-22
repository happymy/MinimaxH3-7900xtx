# Toonflow 接入本地 ComfyUI 计划

> 目标：把本机 ComfyUI 的 6 个 API 工作流接入 Toonflow，并解决「生图/生视频需切换 ComfyUI 启动参数」与「LLM 与 ComfyUI 因硬件限制互斥」两个问题。
> 状态：**待确认后实施**（本文档为方案约定，未写任何业务代码）
>
> ⚠️ **2026-10-22 对齐注记**：comfy-kitchen 0.2.37 已修复 Qwen-Image 侧 CK 回归（见 `CK注意力回归问题调查报告.md` §1 定案 + `ck_ab_qwen_20261022\`），**生图不再需要单独的 no_ck 脚本**。因此 §1.2「两个脚本只差一个 ck 参数」与阶段 2「靠 `--use-ck-attention` 判定 image/video 模式」的前提**已失效**：两用途共用同一脚本，模式切换只剩「LLM 与 ComfyUI 互斥」一条（阶段 3）。下文原文保留作历史记录，实施前需按此修正。

---

## 一、背景与硬约束

### 1.1 硬件与运行约束

| 项 | 事实 |
| --- | --- |
| GPU | AMD 7900XTX（Vulkan，`GGML_VK_VISIBLE_DEVICES=0`） |
| 显存 | 24GB，**LLM 与 ComfyUI 不能同时驻留** |
| LLM | 本地 llama.cpp router：`D:\localAI\ollama\start-multi.bat` → `llama-server.exe`，监听 **0.0.0.0:1234**，`--models-max 1`（按需加载，同时只驻留 1 个模型） |
| 生图/生视频 | ~~两个启动脚本**只差一个参数** `--use-ck-attention`~~ → **2026-10-22 起共用 `run_amd_gpu_enable_dynamic_vram.bat`**（CK 修复后生图不再禁用 ck） |

### 1.2 ComfyUI 启动脚本（关键事实）

| 用途 | 脚本 | 差异 |
| --- | --- | --- |
| **生视频** | `run_amd_gpu_enable_dynamic_vram.bat` | 含 `--use-ck-attention` |
| **生图** | ~~`run_amd_gpu_no_ck_attention.bat`~~ → **同上主力脚本** | 2026-10-22 起不再需要 no_ck；该脚本降为**回退/对照**（CK 出脏图时用） |

其余公共参数：`--enable-dynamic-vram --disable-pinned-memory --disable-smart-memory --reserve-vram 6 --cache-none --fp16-intermediates`，端口 `8188`。

> ~~结论：**模式判定 = 查 8188 的 python 进程命令行是否含 `--use-ck-attention`**；**切换 = 杀进程 → 起对应 bat → 轮询 `/system_stats` 就绪**。~~
> **2026-10-22 修正**：两用途共用同一脚本后，ck 参数无法再区分 image/video，`detectMode()` 这一层**整段作废**；只剩下「起/停 ComfyUI + 轮询 `/system_stats`」与「LLM 互斥」（阶段 3）需要保留。

### 1.3 待接入的工作流（`D:\localAI\ComfyUI-last\plan\API_workflows\RAW\`）

| 文件 | 类型 | 需注入的输入 |
| --- | --- | --- |
| `minimax_h3_t2v-gguf-8b-heretic-op.json` | 文生视频 | prompt、分辨率、时长 |
| `minimax_h3_i2v-gguf-8b-heretic-op.json` | 图生视频 | 首帧图、prompt、分辨率、时长 |
| `minimax_h3_ref2v-gguf-8b-heretic-op.json` | 参考生视频 | 参考图/视频/音频、prompt、分辨率、时长 |
| `qwen_image_2_1_t2i-Q8_0_gguf.json` | 文生图 | prompt、分辨率、seed |
| `qwen_image_2_1_image_edit-Q8_0_gguf.json` | 图片编辑 | 原图 + 参考图、prompt、分辨率 |
| `qwen_image_2_1_background_removal-Q8_0_gguf.json` | 抠图 | 输入图、prompt、分辨率 |

均为 **ComfyUI API 格式**（节点 id 为键，含 `inputs` / `class_type` / `_meta.title`），可直接 `POST /prompt`。

---

## 二、Toonflow 现有架构（事实调查）

### 2.1 调用链（server 端）

```
画布节点 / Agent 工具
  → ai.generateVideo / generateImage            (节点侧)
  → generateMedia(cwd, mediaType, request)      apps/server/src/utils/media/generation.ts:131
    → getMediaProvider(providerId)              取 provider 元信息
    → loadMediaProviderSource(source, config)   apps/server/src/utils/media/provider.ts:382  动态加载插件
      → provider.generateVideo(request)         插件内部实现
  → 结果落盘到工作区 assets/
```

### 2.2 Provider 插件契约

- 结构见 `packages/providers/types.d.ts:194`（`ProviderDefinition`）：`id` / `label` / `icon` / `version` / `rules`（配置表单）/ `models`（模型能力）/ `generateImage` / `generateVideo` / `generateAudio`。
- 模型能力字段：`mode`、`durationResolutionMap`（时长↔分辨率）、`imageSizes`、`imageRatios`、`audio`、`voices`。
- 参考实现：`packages/providers/src/media/tfRouter.ts`（326 行，含 `generateTask` 轮询范式）。
- 注册：`apps/server/src/app.ts:15` 的 `autoInstallProviders` 数组 + `initializePlugins(...)`；源码位于 `packages/providers/src/media/*.ts`。

### 2.3 ⚠️ 沙箱约束（决定架构）

`provider.ts:385-397`：插件源码在 **node:vm `SourceTextModule`** 中执行：

- 仅注入白名单全局：`Buffer / URL / URLSearchParams / TextEncoder / TextDecoder / Blob / AbortController / AbortSignal / setTimeout / clearTimeout`
- **禁止 import 任何模块**（`rejectImport`）、无 `codeGeneration`
- **没有 `child_process` / `fs` / `process`**

> **因此：能进 provider 的只有 HTTP；凡是「启停进程、读写文件、切换模式」只能在 server 层做。**

### 2.4 节点侧参数（前端）

- 视频生成节点：`packages/nodes/videoGenerationNode/src/index.vue`，设置面板 `components/generationSettings.vue`，字段 `duration` / `resolution` / `ratio` / `mode` / `generateAudio`。
- 分辨率选项 = `durationResolutionMap` 中「当前时长」对应的档位。
- 图片生成节点同理，字段 `size` / `ratio`。

---

## 三、总体方案

```
┌─────────────────────────── server 进程（可读写文件/进程）───────────────────────────┐
│                                                                                    │
│  generation.ts: generateMedia()                                                    │
│        │                                                                           │
│        ├──(新增) ComfyUI 调度器  apps/server/src/utils/comfyui/                     │
│        │     • ensureMode("image" | "video")   检测 8188 + CK 参数，必要时切换      │
│        │     • releaseLlm() / ensureLlm()      LLM(llama-server) 互斥调度           │
│        │                                                                           │
│        └── loadMediaProviderSource("comfyui")  → 受限 VM 沙箱                  │
│                 └── comfyui.ts  仅做 HTTP：                                    │
│                       POST /upload/image → POST /prompt → 轮询 /history → /view     │
└────────────────────────────────────────────────────────────────────────────────────┘
                                        │ HTTP 127.0.0.1:8188
                                        ▼
                         ComfyUI（生图实例 / 生视频实例，二选一）
```

**设计要点**

1. 工作流模板内联进 provider 源码（受沙箱限制，插件不能读盘），每个模型一份模板 + 占位符注入表。
2. ComfyUI 生命周期与 LLM 互斥放在 server 层（`utils/comfyui/`），通过 `utils.ts` 统一出口暴露。
3. 调度器接入点在 `generateMedia` 调 provider 之前，按 `mediaType` 决定目标模式；provider 不感知进程。
4. 配置项（ComfyUI 地址、脚本路径、模式判定方式）走 provider 的 `rules` 表单，便于调整。

---

## 四、分阶段实施

### 阶段 1：ComfyUI Provider 接入（核心，先做）

**新增** `packages/providers/src/media/comfyui.ts`

1. 内联 6 个工作流模板（从 RAW 目录复制为 JS 常量）。
2. `rules`：`apiUrl`（默认 `http://127.0.0.1:8188`）+ 可选超时。
3. `models`：6 条，`type` 分别为 `video`/`image`，并声明能力：
   - 视频：`mode`（text / singleImage / 参考数组）、`durationResolutionMap`、`audio`
   - 图片：`mode`（text / singleImage / multiReference）、`imageSizes`、`imageRatios`
4. 通用函数（仅用 `this.tool.fetch`）：
   - `uploadImage(input)` → `POST /upload/image`（multipart）→ 返回 ComfyUI 内部文件名
   - `queue(workflow)` → `POST /prompt` → 拿 `prompt_id`
   - `poll(promptId, signal)` → `GET /history/{id}` 直到完成/失败
   - `fetchOutput(nodeOutput)` → `GET /view?filename=...&subfolder=...&type=output` → 返回 `{ type: "binary", data, mimeType }`
5. 占位符注入表（每模型一套，标注节点 id）：

   | 工作流 | prompt | 图片 | 分辨率 | 时长/帧 | seed | 输出节点 |
   | --- | --- | --- | --- | --- | --- | --- |
   | t2v | `169.prompt` | — | `20.aspect_ratio` / `20.megapixels` | `134.value`(秒)→`133` 帧换算 | `RandomNoise` | `4` |
   | i2v | `187` | `20`(首帧) | `29` | `196`/`PrimitiveFloat` | — | `SaveVideo` |
   | ref2v | `220` | `270` 等 | `115` | `229` | — | `92` |
   | t2i | `459:474.on_false` | — | `13` | — | `459:458.seed` | `461` |
   | image_edit | `280`（+`177`/`269`） | `20`/`51` | `89`/`90` | — | — | `SaveImageAdvanced` |
   | bg_removal | `168` | `20` | `80`/`81` | — | — | `SaveImageAdvanced` |

   > 具体节点 id 与字段需在实施时**逐一对照实际 JSON 复核**（本表为初查结果）。
6. **内置 LLM 改写节点处理**：`qwen t2i` 含 `TextGenerate`（qwen3.5 本地模型改写提示词）+ `ComfySwitchNode`。接入时应 **`switch=false`，直接把 Toonflow/Agent 传来的 prompt 写入 `on_false`**，避免 ComfyUI 内再跑一次 LLM（既省显存又避免与 Agent 重复改写）。
7. 注册：加入 `app.ts` 的 `autoInstallProviders`。

**验收**：Toonflow 节点里能选到 6 个本地模型；文生图、文生视频能出结果并落在工作区。

---

### 阶段 2：ComfyUI 双模式自动切换（server 层）

**新增** `apps/server/src/utils/comfyui/`（+ 在 `utils.ts` 暴露）

1. ~~`detectMode()`：查 8188 监听进程 → 读 python 进程命令行 → 含 `--use-ck-attention` 即 `video`，否则 `image`；未运行返回 `null`。~~ → **2026-10-22 作废**：两用途同脚本，无需也无法按 ck 参数区分；只需 `isRunning()`（8188 是否监听 + `/system_stats` 是否 200）。
2. `ensureMode(mode)`：
   - 已运行且模式正确 → 直接返回
   - 已运行但模式不符 → 杀 8188 进程 → 确认端口释放
   - 未运行 → 启动目标 bat（`Start-Process` 后台 + 日志重定向，遵守 cmd 常驻进程规范）
   - 轮询 `GET /system_stats` 直到 200（含首次模型加载耗时）
3. **接入点**：`generateMedia`（generation.ts）在调用 provider 前，若 `providerId === "comfyui"`，按 `mediaType` 调 `ensureMode`。
4. 若「当前没有 LLM 在跑」是前提，则本阶段即可独立工作（不涉及阶段 3）。

**验收**：~~先跑生图 → 再点生视频，能自动重启 ComfyUI 到 CK 模式；反之亦然。~~ → **2026-10-22 修正**：生图与生视频共用同一 CK 脚本后**无需在两者间重启**，验收改为「ComfyUI 未运行时能自动拉起并等到 `/system_stats` 就绪；LLM 占用显存时能按阶段 3 规则先卸 LLM」。

---

### 阶段 3：分级使用（LLM 阶段 / ComfyUI 阶段）—— 已选定路线

**结论：能，而且 Toonflow 的 workflow 本身就是分层的、带「生成闸门」的。**

#### 3.1 Toonflow 天然的切点（依据）

| 证据 | 位置 | 含义 |
| --- | --- | --- |
| workflow 是**分阶段**制作主流程 | `packages/skills/workflow/SKILL.md:15`「从哪里开始」 | 剧本 → 资产 → 视频提示词 → 生成，逐层推进 |
| 提示词准备与实际生成**分开登记** | `references/assets.md:86` | 「提示词准备完成与实际生成分开登记」——文本与媒体的边界是官方设计 |
| 生成前必须**先给方案、取得授权** | `apps/server/src/agent/runtime/prompt.ts:34-36` | 「图片或视频生成前，先给可审阅的具体方案…用 askUser 取得明确同意」 |
| 生成是独立的一步 | `references/canvasExecution.md:73-80` | 「生成前准备」：读配置 → 写提示词 → 展示方案 → 授权 → 复核 → 才 `node:generateImage/generateVideo` |
| 同一批可不依赖地批量启动 | `references/canvasExecution.md:86` | 「同一已授权批次中，其他节点若不依赖待生成结果，可继续核对并启动」 |
| 生成中 Agent 结束本轮 | `references/canvasExecution.md:88` | 「没有状态/等待能力时结束本轮」——生成期间 Agent 不在推理 |

**关键结论**：Toonflow 的「一轮对话」天然就是分级单位——

1. 一轮内：Agent 用 **LLM** 写剧本 / 资产清单 / 提示词 / 生成方案；
2. 到「生成前授权」闸门时用 `askUser` 提问——**此刻 Agent 空闲**；
3. 用户批准 → 由 `node:generateImage/generateVideo` 调 **ComfyUI**，生成期间 Agent 已结束本轮；
4. 用户下次回复 → Agent 用 **LLM** 回读结果、验收。

> 即：**LLM 与 ComfyUI 被「授权闸门」和「对话轮次」天然隔开**，不必在连续推理中来回抢显存。

#### 3.2 落地方案（由易到难）

| 方案 | 改动 | 说明 |
| --- | --- | --- |
| **S1 手动分级**（零代码，立即可用） | 无 | 你控制「何时批准生成」：批准前让 Agent 只用 LLM 把剧本 + 全部提示词做完，**先不批准生成**；此时手动关 LLM、起 ComfyUI；回来批准生成；生成完再手动切回 LLM 验收。 |
| **S2 半自动门控**（推荐） | server 层 | `generateMedia` 入口按 `mediaType` 自动 `ensureMode`（阶段 2）；并在 Agent 进入「生成前授权」等待 / 结束本轮时自动释放 LLM（停 `llama-server.exe` 或卸模），LLM 需要时自动拉起。 |
| **S3 全自动互斥** | server 层 + 运行时协调 | 在 pi-ai 的 LLM 调用与媒体调用两侧都加锁。**风险高**：Agent 边想边生成时会颠簸，不建议。 |

#### 3.3 现实折扣（必须知道）

- **验收回路**：资产/视频阶段是「LLM 出提示词 → 生成 → 看结果 → 可能改词重做」，不是绝对的一次性单向分级；回路本身仍要 LLM 与 ComfyUI 交替。
- **批量合并**：靠 `canvasExecution.md:86` 的「同批不依赖可并发生成」，把同一批资产/片段一次跑完，减少切换次数。
- **ComfyUI 内的 LLM**：`qwen t2i` 内置 `TextGenerate`（本地 LLM 改写）——接入时必须 `switch=false`，否则 ComfyUI 内又跑一个 LLM，同样抢显存。
- **"Ollama" 实为 llama.cpp router**（`--models-max 1`）：空闲是否自动卸载模型需实测；必要时直接停 `llama-server.exe` 进程以彻底让出显存。

#### 3.4 推荐

先做 **S1（手动分级）** 跑通全流程，确认 LLM / ComfyUI 不抢显存；再升级 **S2（半自动门控）**。

**验收**：同一台机器上能可靠地「LLM 阶段」与「ComfyUI 阶段」各自独占显存、不崩溃；跨阶段切换有明确触发点。

---

## 五、文件清单（预计）

### 新增
| 文件 | 用途 |
| --- | --- |
| `packages/providers/src/media/comfyui.ts` | ComfyUI provider（内联工作流 + HTTP 调用） |
| `apps/server/src/utils/comfyui/index.ts` | 模式检测 / 启动 / 切换 |
| `apps/server/src/utils/comfyui/llm.ts`（阶段 3） | llama-server 启停与互斥 |

### 修改
| 文件 | 改动 |
| --- | --- |
| `apps/server/src/app.ts:15` | `autoInstallProviders` 加入 `comfyui.ts` |
| `apps/server/src/utils.ts` | 暴露 `comfyui` 工具 |
| `apps/server/src/utils/media/generation.ts` | 调 provider 前 `ensureMode(mediaType)`（阶段 2/3） |

> 注：`packages/providers/src/media/*` 的改动需按仓库规范（双引号、分号、两空格缩进、小驼峰命名）编写；server 目录遵守其「一个接口一个文件」等既有约定。

---

## 六、风险与待确认

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | **沙箱限制** | 已确认 provider 不能 spawn/读盘 → 生命周期必须放 server 层（方案已据此设计） |
| 2 | 工作流节点 id | 6 个模板的注入点需逐一对照实际 JSON 复核，避免写错字段 |
| 3 | 内置 LLM 节点 | t2i 的 `TextGenerate` 需确认关闭方式（`switch=false`）|
| 4 | 时长↔帧数换算 | 视频工作流用 `ComfyMathExpression` 把「秒」换算成帧数（如 `max(5, round(a*24))+...`），需按实际公式注入 |
| 5 | 图片上传 | ComfyUI `/upload/image` 的 multipart 形式需实测（沙箱内仅 `fetch`，`FormData` 未在注入白名单 → **可能需要用固定 boundary 手工拼 multipart body**）⚠️ |
| 6 | 参考文献/音频 | ref2v 的参考视频、音频注入点未逐一确认 |
| 7 | 切换耗时 | ComfyUI 重启 + 模型加载约数十秒~2 分钟，交互体验需接受 |
| 8 | LLM 互斥路线 | 已选「分级使用」：靠「生成闸门 + 对话轮次」隔开 LLM 与 ComfyUI（见阶段 3），S1 手动即可用 |
| 9 | 端口/进程判定 | Windows 下取进程命令行需 `Get-CimInstance Win32_Process` 等价能力（Node 侧用 `wmic`/PowerShell 或 `tasklist /v`）|

> 第 5 条是**阶段 1 的主要技术风险**：VM 沙箱未注入 `FormData`/`Blob` 之外的 Web API，图片上传方式需先验证；若不可行，可改为「先由 server 层上传图片，provider 只拿文件名」，或改用 base64 写节点输入。

---

## 七、建议实施顺序

1. **先做阶段 1 的「文生图」单链路**（t2i），跑通「节点 → provider → ComfyUI → 出图 → 落工作区」最小闭环，同时验证风险 #5（图片上传）与沙箱能力。
2. 打通后再补 5 个工作流。
3. 阶段 2（双模式自动切换）。
4. 阶段 3 用 **S1 手动分级**跑通，确认不抢显存后，再升级 **S2 半自动门控**。

---

## 八、实施记录（2026-10-11）

### 实际交付

- **提交** `3620694 新增本地 ComfyUI 媒体供应商`：`packages/providers/src/media/comfyui.ts` + `apps/server/src/app.ts`（`autoInstallProviders` 加入 `"comfyui.ts"`）。
- **provider**：id `comfyui`，label「本地 ComfyUI」，v2.0.0；`rules` 提供 `baseUrl`（默认 `http://127.0.0.1:8188`）；结果资产为 `{ type: "url", url: "/view?..." }`。
- **命名说明**：计划初稿命名为 `comfyuiLocal.ts`（id `comfyuiLocal`），实施时调整为 `comfyui.ts`（id `comfyui`）——对齐仓库 AGENTS.md（小驼峰、零全大写常量）；原备选实现已移出运行时目录（保留于备份/隔离区）。

### 实际节点映射（已逐一对照 RAW JSON 复核）

| 工作流 | prompt | 参考图/视频/音频 | 分辨率 | 时长/帧 | seed | 输出 |
| --- | --- | --- | --- | --- | --- | --- |
| qwen t2i | `459:474.on_false`（`switch=false` 内联） | — | `13.aspect_ratio` / `13.megapixels` | — | `459:458.seed` | `461` |
| qwen edit | `459:484.on_false` | `470` / `475`（可扩到 16 张） | — | — | `459:458.seed` | `461` |
| qwen bg_removal | `459:474.prompt` | `470` | — | — | `459:458.seed` | `461` |
| h3 t2v | `129.prompt` | — | `115.aspect_ratio` / `115.megapixels` | `134.value`(秒) → `133` 帧换算 | `127.noise_seed` | `92` |
| h3 i2v | `133.prompt` | 首帧 `114` / 尾帧 `141` | `115` | `135.value`(秒) → `133` 帧换算 | `131.noise_seed` | `92` |
| h3 ref2v | `145.prompt` | 图 `149` / 视频 `156` / 音频 `153` | `115` | `135.value`(秒) → `133` 帧换算 | `131.noise_seed` | `92` |

- 视频时长换算表达式：`max(5, round(a*24)) + (5 - (max(5, round(a*24)) % 17)) % 17`（24fps、下限 5 帧、帧数 ≡5 mod 17）。
- `generateAudio === false` 时删除 CreateVideo 的 `audio` 输入（`dropAudio`，对应音频 VAE/`VAEDecodeAudio` 分支随之剪除）。
- 参考素材经手工拼 multipart `POST /upload/image`（或 `upload` 通用入口）上传到 `input/toonflow`，风险 #5 已验证可行。

### 测试结论（`POST /api/providers/debug/run`，source=comfyui.ts，快速参数）

6/6 全部通过（`result=1`、`error=0`、输出为 `/view?` URL 资产）：

| 工作流 | 产出文件 | 耗时 |
| --- | --- | --- |
| t2i | `Qwen_image_2.1_00128/00129.png` | 122.7s |
| image edit | `Qwen_image_2.1_00130.png` | 215.4s |
| bg removal | `Qwen_image_2.1_00131.png` | 211.6s |
| t2v | `MiniMax_H3_00250_.mp4` | 192.4s |
| i2v | `MiniMax_H3_00251_.mp4` | 214.0s |
| ref2v | `MiniMax_H3_00252_.mp4` | 212.9s |

**未实测分支**：多参考图（edit >1 张）；i2v 首尾帧同时；ref2v 视频/音频参考。UI 画布端到端未验证（止于 provider 层）。

**补充（2026-10-11）**：带音频 t2v 已实测通过——`generateAudio` 默认（不传时保留音频分支 `audio_vae → VAEDecodeAudio → CreateVideo.audio`），产出 `MiniMax_H3_00253_.mp4`（h264 + **aac 音轨**，ffprobe 确认）。注意：本次测试中 Toonflow server（`bun --watch`）在生成中途自行退出（`Exited with code 1`，已知问题）导致 debug 流中断，但 ComfyUI 侧任务正常完成；重启 server 后 `/view` 资产可访问。

---

*文档位置：`D:\localAI\ComfyUI-last\plan\Toonflow接入本地ComfyUI计划.md`*
