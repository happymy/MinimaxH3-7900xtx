# plan 目录索引

MiniMax H3 本机部署与实测的**全部资产地图**。**329 个文件 / 33.41 MB**（2026-10-06 重数；口径 = `Get-ChildItem -Recurse -File` 全量递归）。
本文件是导航层；整理动作只做了归档、删字节码、修注释、补交付层、建显存估算模型，详见 §6。

> **姊妹目录**：Qwen-Image 2.1（生图）那条线的全部资产在 **`plan2\`**，不在本目录。见 `plan2\README.md`。
> 两侧唯一的交集是 `CK注意力回归问题调查报告.md`（Qwen 侧崩坏 + H3 侧安全），权威版在本目录 `plan\`，`plan2\` 那份是副本。

---

## 1. 顶层五区语义

| 目录 | 语义 | 格式 | 用途 |
|---|---|---|---|
| *(根)* | **文档 + 实测证据 + 生成产物** | md / json / csv / mp4 | 主报告在此；实测原始数据也落在根目录 |
| `bat\` | **可执行脚本族 + 提示词模板** | py / bat / txt / md | 日常入口全部在这里 |
| `API_workflows\` | **API 格式工作流**（走 `/prompt` 提交） | json | 含 `final\` 交付层；参数覆盖只在内存中，不落盘 |
| `molbal_workflows\` | **UI 格式工作流**（ComfyUI 画布直接拖入） | json | 含 `final\` 交付层 |
| `归档\` | **运行日志归档** | log / md | 2026-10-02 从全目录收拢的 12 个 `*.log`，见 `归档\日志\来源清单.md` |
| `bak\` | 早期脚本退场副本 | py / bat | 与 `bat\` 内同名脚本易混，**不要从这里取用** |

> ### ⚠️ 本文件描述的是**实机目录全貌**，仓库是它的「文档 + 脚本 + 工作流 + 锚点」子集
>
> 实机根目录：`D:\localAI\ComfyUI-last\plan\`。**2026-10-06 裁决调整**（上一轮把 `API_workflows\` 整棵排除在外，本轮改判入库 —— 它是交付层，换机必需）：
>
> | 未入库 | 原因 | 在哪 |
> |---|---|---|
> | `bat\分段归档\*.mp4` / `*.png`、`bat\<族>\h3_*.mp4` | 生成产物（22.26 MB），应由 `ComfyUI\output\` 承接 | 实机同名路径 |
> | `bat\<族>\img\`、`bat\测试素材\` | 本机测试素材（7.7 MB） | 实机同名路径 |
> | `bat\preview_watch - 副本\` | **旧版脚本快照**（`watch_h3_preview.py` 10,440 B，比现行 12,732 B 少 2 KB + 一份 `.pyc`），历史备份不入库 | 实机同名路径 |
> | `ck_ab_20261002\` 的可视化 PNG / mp4 | 对照图与自检样本（6.44 MB）；**指标 json 与脚本已入库** | 实机同名路径 |
> | `bat\_run_4b.log`、`*.err.log`（全目录） | 运行 stderr / 驱动日志，可重生成 | 实机同名路径 |
> | `__pycache__\`、全部 `*.pyc` | 字节码，已被 `.gitignore` 排除 | — |
>
> **本轮已入库**（相对上一轮新增 194 文件 / 2.72 MB）：
>
> | 内容 | 文件 | 说明 |
> |---|---|---|
> | `API_workflows\` 全树 | 103 | 交付层 + 调试线 + `_audit\` 工具脚本，**换机必需** |
> | `归档\日志\` | 13 | 含 `aria2.log`（407 KB）等运行留痕，路径对照见 `来源清单.md` |
> | `molbal_workflows\bak noerror 0/1/2`、`bak RAW` | 15 | §2.1 登记的回滚锚点，此前一直漏登 |
> | plan 根 8 份实测数据 | 8 | `ab_8b_heretic_*`、`op_gpu_mem.csv`、`op_matrix_results.jsonl`、`t2v_*_results.json` |
> | `*.pre-ck-ab-20261002.bak` | 3 | 上一轮留的锚点，此前未入库 |
>
> **死文件已清**（实机确无，仓库曾有 6 个）：`bak\gen_video.py`、`molbal_workflows\final\*.pre-q8fix.bak`（3 份）、`molbal_workflows\final\提示词模板-照片.txt`（`bat\提示词模板\` 下有逐字节相同副本）。
> 另 `molbal_workflows\final\提示词模板-视频.txt` 改名保留为 `提示词模板-视频.txt.pre-trim-20261001.bak`（实机 10-01 版比仓库 09-30 版少 12 行「完整操作顺序」，属内容差异不是重复件，详见 §2.1）。

---

## 2. 文档（先读这 6 份）

| 文件 | 内容 |
|---|---|
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md` (约 91 KB / 1061 行) | **主计划**。**§3 显存预算模型**（预算双界 / staged 系数 / 装载判据 / 卸载纪律）、§5 目录结构图、§10 性能与显存、§11 分模型实测（11.8 8B 变体 / 11.9 op 系列 / 11.10 分辨率矩阵 / 11.11 破限专章） |
| `T2V_4B_vs_8B_对比报告.md` (约 30 KB / 433 行) | 4B vs 8B 主报告。§3.1 混淆变量、§9 0.60 MP 补测、§10 破限 A/B |
| `ComfyUI_MiniMaxH3_From_Scratch.md` (约 12 KB / 212 行) | 从零构建说明（模型清单、目录、启动参数） |
| `vision_qc_识图结论.md` (约 10 KB / 152 行) | 识图判定结论（0.40 MP 不糊 / 几何细节提升真实 / 4B-8B 无法排名） |
| `CK注意力回归问题调查报告.md` (350 行) | ⚠️ `--use-ck-attention` 回归证据链（**Qwen-Image 侧**：5 组 flag 对照 / token 64 边界二分 / 源码定位 / 版本溯源），对应 `Plan.md §12`。§7.3 已于 2026-10-02 由 A/B 关闭（H3 DiT 侧安全）。**`plan2\qwen21-tools\` 下有同名副本**，权威版是本目录这份 |
| `ck_ab_20261002\` (入库 16 文件 / 171 KB) | ✅ **H3 侧 ck / 非-ck 受控 A/B**（2026-10-02）。结论：**H3 DiT 走 ck 安全**，端到端 1.54x。入库内容 = 本目录 `README.md` + 主报告 + 2 个脚本 + 10 份 json（2 份运行清单组共 5 份 + 5 份指标）。**实机另有 32 文件 / 6.61 MB**，多出的是可视化 PNG / mp4 / 启动日志，不入库。对应 `Plan.md §12.3` / `§12.6` 待办 1（已关闭） |
| `API_workflows\H3工作流适配计划.md` (约 9 KB / 157 行) | API 格式工作流适配方案 |
| `API_workflows\未测试\final\README.md` | **API 格式交付层**（15 份）的来源与三套 TE 对照。见 §2.2 |
| `bat\提示词模板\MiniMax-H3-提示词书写规则.md` (约 19 KB / 330 行) | **提示词书写规则**（三字段信封 / `[Shot N]` 时间线 / 摄影机运动词表 / 帧栅格 / R2V 六段） |
| `归档\日志\来源清单.md` | 12 个 `*.log` 归档前后的路径对照 |
| `plan2\README.md`（姊妹目录） | **Qwen-Image 2.1 生图线**的全部资产索引。工具链 17 份脚本、上游 issue #226 材料、实验留痕 |

> 体积写近似值（文档会持续修订，精确字节会自我失效）；**行数为审计时的精确值**。

> `bat\提示词模板\` 另有 4 份模板：`提示词模板-视频.txt`、`提示词模板-视频 - 静止.txt`、`提示词模板-照片.txt`（模块 A/B/C 的「隐形排除」正向写法出处）。

### 2.1 文档回滚锚点（勿删）

| 文件 | 说明 |
|---|---|
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md.20260930.bak` | 目录重组前快照 |
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md.old` | 更早快照 |
| `ComfyUI_MiniMaxH3_From_Scratch.md.old` | 更早快照 |
| `molbal_workflows\bak noerror 0/1/2`、`bak RAW` | 4 套调试期快照（15 个文件）。**2026-10-06 首次入库**，此前一直只登记未入库 |
| `API_workflows\{Calliope,go,omy}\bak *` | API 格式调试期快照（31 个文件）。⚠️ `omy\` 的主目录内容已进交付层 `API_workflows\未测试\final\4b\`，但 `bak 01\` 仍原样保留 |
| `*.pre-ck-ab-20261002.bak`（3 份） | ck A/B 结论回写**之前**的实机文档快照：`ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md` / `ComfyUI_MiniMaxH3_From_Scratch.md` / `README.md`。同批把 `CK注意力回归问题调查报告.md` 首次补进实机（此前只在仓库） |
| `molbal_workflows\final\提示词模板-视频.txt.pre-trim-20261001.bak` (4570 B) | **仓库独有**（实机 10-01 已删此路径）。实机 `bat\提示词模板\提示词模板-视频.txt` 是 10-01 修订版（4053 B / 67 行），比本锚点（09-30 版 / 79 行）**少 12 行**「✅ 完整操作顺序」——分辨率下限、关闭 Turbo/SageAttention、删 soft/dreamy/blur 类词、种子固定。**不是重复件，是内容有差异**，故保留而不删 |
| `plan2\qwen21-tools\CK注意力回归问题调查报告.md.pre-ab-20261002.bak` (336 行) | H3 侧 A/B 之前的旧版 CK 报告快照，§7.3 当时仍写「H3 DiT 未验证」。`plan2\` 那份正文已于 2026-10-06 同步为定稿版 |

### 2.2 API 格式交付层在哪（2026-10-06 路径勘误）

交付层 README 里原写 `API_workflows\final\4b\`，**该路径不存在**。实际位置：

```
plan\API_workflows\未测试\final\
├── 4b\            3 份（拷贝自 API_workflows\omy\）
├── 4b\op\         3 份（拷贝自 API_workflows\未测试\op\）
├── 8b\            3 份（拷贝自 API_workflows\未测试\8b\）
├── op-8b\         3 份（拷贝自 API_workflows\未测试\op-8b\）
└── op-8b-heretic\ 3 份（拷贝自 API_workflows\未测试\op-8b-heretic\）
```

即**除 `omy\` 在顶层外，其余 4 个源目录都在 `未测试\` 下**。`API_workflows\未测试\final\README.md` 的 9 处路径引用已于 2026-10-06 全部改正。
> 目录名 `未测试` 是历史遗留 —— 用户 2026-10-06 确认**所有工作流均已实战跑通**，但按 D 盘硬规矩（工作流与脚本只增不改不删不移）**不改名**，仅在此说明。

---

## 3. 实测证据（被上面两份报告逐条引用，**不能移位**）

| 文件 | 内容 |
|---|---|
| `t2v_4b_vs_8b_results.json` | 0.40 MP 两组完整实测（含 ffprobe 字段） |
| `t2v_8b_060_4s_result.json` | 0.60 MP / 4 秒补测（★107 帧越界） |
| `ab_8b_heretic_metrics.json` | **破限 A/B 三组逐帧 sha256 / SSIM / PSNR，以此为准** |
| `ab_8b_heretic_full.json` / `ab_8b_heretic_compare.json` | 生成 + 比对原始记录 |
| `ab_8b_heretic_results.jsonl` | 生成过程记录 |
| `op_gpu_mem.csv` | 显存采样（3 秒间隔，**308 数据行**，11:55:56→12:11:25，峰值 21,473 MB） |
| `op_matrix_results.jsonl` | 测试进程记录（每次开跑前清空） |
| **`vram_model.py`** | **显存估算模型复算脚本**（纯标准库）。输出 `Plan.md` §3 全部表格；改常量即重算 |
| `ck_ab_20261002\*_metrics.json`（5 份） | ck A/B 逐帧原始指标（Pearson / SSIM / mad / 锐度），`Plan.md §12.3` 五路判据的数据源 |

> 报告正文按 `plan\xxx.json` 的**精确相对路径**引用以上文件。移动它们必须同步改文档，收益为零风险不等。

### 3.1 `API_workflows\` 树登记（2026-10-06 首次入库）

103 个文件 / 0.77 MB，7 个子目录：

| 子目录 | 文件 | 性质 | 说明 |
|---|---:|---|---|
| `未测试\` | 28 | **交付层 + 源目录** | `final\{4b,4b\op,8b,op-8b,op-8b-heretic}\` 共 15 份是 API 格式交付层（路径勘误见 §2.2）；同级的 `op\` `8b\` `op-8b\` `op-8b-heretic\` 是它的拷贝源，各 3 份 |
| `Calliope\` | 22 | 调试线 | Krea2 T2I 调试，5 套 `bak` 命名不统一（`bak 04  OK` 双空格 / `bak 05 OK` / `bak 04` 混用，见 §7.2） |
| `go\` | 15 | 调试线 | 同上，4 套 `bak` |
| `infinite-creation\` | 12 | **官方模板交付** | `Final\` 8 份 + `infinite-creation-originals\` 4 份原始模板。`Final\` 里 4 份与 originals 逐字节相同（未改），4 份是本机适配产物 |
| `omy\` | 8 | 已验证源 | 3 份 H3 API 工作流（= 交付层 `final\4b\` 的拷贝源）+ `bak 01\` 5 份调试快照 |
| `RAW\` | 10 | 原始快照 | 含 `bak\009/010-*-NOAV*` 6 份（去 audio 的对照版）+ 4 份 Qwen-Image 2.1 Q8_0 |
| `_audit\` | 7 | 工具脚本 | `adapt_raw_to_test.py` / `verify_adapted.py` / `probe_raw.py` / `probe_tagged.py` / `probe_user_wf.py` / `dump_raw.py` / `export_imported_to_bak.py`，校验 RAW → 交付层的适配链路 |

---

## 4. `bat\` 脚本族矩阵

**4 个生成族 × 3 个文本编码器变体 = 12 个目录**，加 4 个工具目录（工具无变体），`bat\` 下共 16 个脚本目录。

变体唯一差别是 `CCTechClipProjLoader` 节点的 `clip_name` / `type` / `projection` 三元组
（`gen_*.py` docstring 里逐条列明，实测取自工作流 JSON 的 `widgets_values`）：

| 后缀 | clip_name（文件） | type（**下拉值，非文件名**） | projection（文件） |
|---|---|---|---|
| *(无后缀)* | `qwen3-vl-4b-heretic-Q4_K_M.gguf` | `krea2` | `mmh3-4b-ClipProj-v3.1.safetensors` |
| `_8b` | `qwen3vl_8b_fp8_scaled.safetensors` | `boogu` | `mmh3-8b-ClipProj-v3.1.safetensors` |
| `_8b_heretic` | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | `boogu` | 同上 |

> ⚠️ `krea2` / `boogu` 是节点 `type` 字段的枚举值，不是模型文件，`models\` 下没有同名文件。

| 族 | 变体数 | 做什么 | 关键差异 |
|---|---:|---|---|
| `multisegment` | 3 | 多段视频生成（**首尾帧拼接**） | 所有段共用一条提示词 |
| `scenes` | 3 | 分镜多段（每段独立提示词/时长 + **首帧续接**） | 纯文本提示词 |
| `scenes_ref` | 3 | 分镜多段 + **多图 + 视频参考** | 支持图片/视频参考 |
| `ref2va` | 3 | 参考图生成视频 + ffmpeg 拼接 | 多段参考图 |
| `extract_frames` | 1 | 工具：抽首/中/末帧 → PNG | 供 ref2va 造参考图 |
| `qc_frames` | 1 | 工具：质检抽帧 + contact sheet | 配合 `vision-deepseek` 识图 |
| `free_vram` | 1 | 工具：调 ComfyUI `/free` 卸载模型、释放 Dynamic VRAM 残留 | 无 TE 变体；`--status` / `--interval N` / `--no-verify` |
| `preview_watch` | 1 | 工具：H3 生成中**实时预览帧监视器**（纯旁观，不干预生成）；`step 1` 首批预览**顺带把 DiT 卸到低水位** | 无 TE 变体；**需先给 ComfyUI 内核打补丁**，见 §6.7 |

每个生成/工具目录都含 `gen_*.py` + `gen_*.bat`（Windows 入口），**例外 `free_vram\` 是 `free_vram.py` + `free_vram.bat`、`preview_watch\` 是 `watch_h3_preview.py` + `watch_h3_preview.bat`**（都不走 `gen_` 前缀，前者不生成内容，后者不是生成器）。
其中 **8 个有 `prompt.txt`**（`multisegment*` 3 个、`ref2va*` 3 个、`scenes`、`scenes_ref`）；
**8 个没有**（`extract_frames`、`qc_frames`、`free_vram`、`preview_watch`、`scenes_8b`、`scenes_8b_heretic`、`scenes_ref_8b`、`scenes_ref_8b_heretic`）。

> 2026-10-07 起，12 份 `gen_*.py`、`free_vram.py` 与 `preview_watch\watch_h3_preview.py` 全部改用模块级 `OPENER` 直连本地 API，`urllib.request.urlopen` 在 `bat\` 下已清零 —— 系统代理导致的 404 排查见 §6.6。

`bat\归档\` 存官方三份 op 提示词（`prompt_t2v_op.txt` / `prompt_fl2va_op.txt` / `prompt_ref2va_op.txt`）+ 种子记录。
（原 `dl_8b_heretic.log` 已于 2026-10-02 移入 `plan\归档\日志\`。）

---

## 5. 工作流矩阵

### 5.1 `molbal_workflows\`（UI 格式）

```
final\                        ← 交付层
  ├ 4b\      minimax_h3_{t2v,i2v,ref2v}-gguf.json                 4B stock
  │  └ op\   minimax_h3_{t2v,i2v,ref2v}-gguf-op.json              4B + 官方 prompt
  ├ 8b\      minimax_h3_{t2v,i2v,ref2v}-gguf-8b.json              8B stock
  ├ op-8b\  minimax_h3_{t2v,i2v,ref2v}-gguf-8b-op.json            8B + 官方 prompt
  ├ op-8b-heretic\  ...-gguf-8b-heretic-op.json                   8B 破限 + 官方 prompt
  └ qwen_image_2_1_{t2i,image_edit,background_removal}[-Q8_0]_gguf.json  Qwen 附带件（含 .bak）
bak noerror 0/1/2, bak RAW    ← 调试期快照
```

### 5.2 `API_workflows\`（API 格式，走 `/prompt`）

| 目录 | 内容 |
|---|---|
| `op\` / `op-8b\` / `op-8b-heretic\` | H3 三件套（t2v / i2v / ref2v）+ 官方 prompt，3 个 TE 变体 |
| `8b\` | 8B stock，无 op prompt |
| `omy\` | 4B stock，无 op prompt（目录名是历史遗留，内容是纯 H3 三件套，无 Krea2 节点） |
| `Calliope\` `go\` | Krea2 T2I 调试线（5 套 `bak`，命名不统一） |
| **`final\`** | **交付层（2026-10-02 补齐）**，见下 |

> **交付层已对齐**：`API_workflows\final\` 与 `molbal_workflows\final\` 逐层同名对齐
> （`4b\` / `4b\op\` / `8b\` / `op-8b\` / `op-8b-heretic\`，各 3 份，共 15 份）。
> 是各历史目录的**纯拷贝**（sha256 逐份一致），原目录零改动，报告里的精确路径引用继续有效。
> 取哪一版交付只看这一层。详见 `API_workflows\final\README.md`。

### 5.3 命名语义

| 记号 | 含义 |
|---|---|
| `op` | 用**官方原始 prompt**（`bat\归档\prompt_*_op.txt`），不是自己写的 |
| `8b` | 8B stock 文本编码器 |
| `heretic` | 破限文本编码器（`fp8_e4m3fn`，仅 116 个视觉塔张量降到 F8_E4M3） |
| `final` | 交付集合层，只放验证通过的 |

---

## 6. 整理执行记录（6.1–6.5 于 2026-10-02，6.6–6.7 于 2026-10-07）

### 6.1 已归档运行残渣

| 项 | 动作 |
|---|---|
| 12 个 `*.log`（466 KB，含 4 个 0 字节空文件） | **移入 `归档\日志\`**，内容与时间戳未改；原路径清单见 `归档\日志\来源清单.md` |
| 7 个 `__pycache__\`（249.7 KB） | **删除**，零信息量，Python 自动重建 |

两份报告的日志引用已同步改到新路径（`Plan.md` §文件索引、`对比报告.md` §原始文件表）。
顺带纠正两处**归档前就已失效**的引用：报告写 `bat\dl_8b_heretic.log`，实际当时在 `bat\归档\`。

### 6.2 已修过期注释

`bat\multisegment_8b\gen_h3_multisegment-8b.py:51` 与
`bat\multisegment_8b_heretic\gen_h3_multisegment-8b-heretic.py:51`：
`molbal_workflows/8b` → `molbal_workflows/final/8b`（前者不存在，实测 `Test-Path` = False）。
字节各 +6，UTF-8 无 BOM / 纯 LF / 359 行不变，`ast.parse` 通过。

### 6.3 已补 API 交付层

`API_workflows\final\`（15 份 + README），逐层对齐 `molbal_workflows\final\`，sha256 全部一致。

### 6.4 已建显存估算模型（`Plan.md` §3 重写 + `vram_model.py`）

| 项 | 内容 |
|---|---|
| 触发 | 统一 GB/GiB 单位时发现文档的显存估算全是实测前粗估，无法回答「换个 TE 要不要重启」 |
| 推导源 | `--reserve-vram 6` 双重作用（`EXTRA_RESERVED_VRAM` + `set_simple_vram_headroom`）、`minimum_inference_memory()` = 0.8 GiB + 6 GiB、`load_models_gpu` 准入式、`unload_all_models()` @ `execution.py:836` |
| 三个新结论 | ① 装载判据 **15,493 MiB**；② staged 系数 T2b **1.750×**（磁盘比 T2 小 545 MiB 却多占 6,624 MiB 显存）；③ **WMI 峰值度量「拿走了多少」而非「需要多少」**——谷值最低的 4B 反而峰值最高，分辨率最高点不是最高点 |
| 验证 | 判据算术复现了 §11.4 已标注的「T2b 超出可用显存」（超 1,228 MiB） |
| 已声明局限 | 分辨率斜率 3,132 MiB/MP 含混淆变量（分辨率与帧数同变）**不可外推**；`B_adapter` 是快照；采样阶段流式窗口无直接测量 |

### 6.5 已统一单位

`Plan.md` §11.4 磁盘列改用 **MiB / GiB（二进制）**，与显存列口径一致。
T1 `3.11 GB`→`3,179 MiB / 3.10 GiB`、T2 `10.6 GB`→`10,098 MiB / 9.86 GiB`、T2b `9.33 GB`→`9,553 MiB / 9.33 GiB`。

### 6.6 已加固本地 API 直连（2026-10-07）

**22 份脚本 / 68 处** `urllib.request.urlopen` 统一改为模块级 opener 直连：

```python
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# ……调用处
OPENER.open(req, timeout=15)
```

| 范围 | 份数 | 替换处数 |
|---|---:|---:|
| `bat\` 12 个生成族 `gen_h3_*.py` | 12 | 48 |
| `bat\free_vram\free_vram.py` | 1 | 1（另加 docstring 第 6 条限制说明） |
| `plan2\qwen21-tools\`（`run_api` / `fetch_schema` / `accept_full` / `attn_ab` / `cfg_ab` / `flag_sweep` / `len_bisect` / `shift_ab` / `bisect`） | 9 | 19 |
| **合计** | **22** | **68** |

**根因（四要素，缺一不可复现）**：

1. 本机系统代理 `127.0.0.1:26561`，其 `ProxyOverride` **不含 `127.0.0.1`**
2. 双击 `*.bat` 启动的环境里**没有 `no_proxy` 变量**
3. `urllib.getproxies()` 会读**注册表**代理（不只是环境变量），把 `127.0.0.1:8188` 也发给代理 → 代理对本地端口回 **404**
4. ⚠️ **opencode shell 里恰好有 `NO_PROXY`，会掩盖这个坑** —— 在会话里测「没坏」不能作为证据，必须用双击 bat 的环境验

**症状与排查口诀**：脚本报 `404` / `Not Found` 但浏览器打开 `127.0.0.1:8188` 明明正常 → **先查系统代理，别怀疑 ComfyUI**。空 `ProxyHandler` 同时绕过环境变量与注册表两种来源，不依赖调用方环境，所以比设 `no_proxy` 更稳。

**未覆盖残留（2026-10-07 拍板保留，共 2 份 8 处）**：

| 文件 | 处数 | 保留理由 | 将来怎么用 |
|---|---:|---|---|
| `ck_ab_20261002\gen_h3_ck_ab.py` | 4 | §3 登记的实测证据锚点，A/B 已跑完不复跑 | **重跑前必须先加 `OPENER`**，否则 404 |
| `bak\gen_h3_multisegment.py` | 4 | §8 硬规矩「退场副本，不要取用」 | 不取用即可 |

**回滚锚点**：22 份的改前字节全在 commit `8278ce9`，`git show 8278ce9:<path>` 可逐字节取回；D 盘与仓库 sha256 一致，仓库即锚点，故未留 `.bak`。

### 6.7 已入库 `preview_watch\` 帧预览监视器（2026-10-07）

`bat\preview_watch\` 是「视频生成中实时看预览帧」的旁观工具，本轮 4 文件入库：

| 文件 | 大小 | 作用 |
|---|---:|---|
| `watch_h3_preview.py` | 12,732 B | 主脚本：轮询 `GET /queue` 判任务起止，再轮询 `%TEMP%\iw-preview-*` 打印内核落盘的真实预览帧（成片分辨率，非 34×60 小图）。**零侵入**，不干预生成、不重复解码、不改工作流 |
| `watch_h3_preview.bat` | 80 B | Windows 入口（`chcp 65001` → `python watch_h3_preview.py %*`） |
| `frame_preview_kernel.patch` | 8,271 B | **帧预览功能的本地改动权威版**，3 个文件 |
| `official-0.38.0-to-current.patch` | 63,330 B | 官方 `0.38.0` tag → 当前内核的完整复刻 = 帧预览 3 文件 + 11 个 2026-09-30 之后的官方上游提交（14 文件） |

> 不入库：`bat\preview_watch - 副本\`（旧版快照 10,440 B + `.pyc`，见 §1 未入库表）、`bat\测试素材\`。

**⚠️ 用它必须先给 ComfyUI 内核打补丁** —— 预览帧由内核负责生成并落盘，本脚本只是在旁边盯着。内核侧改动清单（相对 `ComfyUI_windows_portable\`，均为 UTF-8）：

1. `ComfyUI\latent_preview.py` —— 帧预览主战场：模块级状态、`_save_frame_preview()` 解码中途写盘
2. `ComfyUI\comfy_extras\nodes_minimax_h3.py` —— H3 节点接上 `latent_preview` 回调
3. `ComfyUI\execution.py` —— 任务起止与 `extra_data.preview_file` 传递

实机权威确认（2026-10-07 `git status`，本机 ComfyUI 是 git 仓库）：**本地改动恰好只有这 3 个文件**，与 `frame_preview_kernel.patch` 的 `diff --git` 清单逐一对齐。

覆盖范围：`plan\molbal_workflows\final\` 的 15 个视频工作流（i2v/t2v 共用 `MiniMaxH3ImageToVideo`，ref2v 走 `ReferenceToVideo`），**未改动任何工作流文件**。链路需 `extra_data.preview_file=true`（项目侧默认 true；手动 `POST /prompt` 不传则 ComfyUI 默认 true）。

#### 隐藏的附加效果：step 1 首批预览 = 顺手卸载 DiT（2026-10-07 补记）

链路：`step 1` 触发第一批预览 → `video VAE decode` → ComfyUI 自带的 `free_memory` → **动态 DiT 在采样最早期就被卸载、压到低水位** → 后续采样按需换回。补丁里对应的注释就在 `latent_preview.py` 的采样 callback 上：

```python
# step 1 额外触发第一批预览：借此把 VAE decode 自带的 free_memory 提前到采样初期，
# 让动态 DiT 以低水位按需运行（--enable-dynamic-vram 下反复加载 ≪ 内存 swap）。
```

为什么值得这么做（**实机经验，非推测**）：

- **反复加载模型的耗时 ≪ 爆显存的代价**。显存一旦被顶爆，`--enable-dynamic-vram` **不会崩进程**，而是把数据退到系统内存（页面文件 / swap）走，那一段渲染**非常慢** —— 宁可让 DiT 反复进出，也不让它把显存顶满
- **长提示词、长视频时长时最明显**：这两类任务采样期显存占用最高（文本张量大 / 帧多 latent 大），提前卸载的收益最大
- **真正的风险是整机卡死，不是报错**：`--enable-dynamic-vram` 下「显存爆了」不等于出错，只有内存也被耗尽时操作系统才卡死 → 提前卸载是**防卡死**，不是防报错

本脚本对此**零贡献也零破坏**：卸载由内核 `VAE decode` 触发，`watch_h3_preview.py` 不发任何卸载请求，零侵入性质不变。同一份说明已写进脚本 docstring 的「【step 1 首批预览的附加效果：提前卸载 DiT】」小节。

**换机部署顺序**：装好官方 `0.38.0` → `git apply` 补丁（或按 `official-0.38.0-to-current.patch` 复刻基线后再打）→ **重启 ComfyUI 生效** → 再跑 `watch_h3_preview.bat`。内核没打补丁时脚本仍能跑，只是永远等不到 `iw-preview-*` 目录。

脚本自带 `OPENER` 直连（§6.6 同源），不依赖 `no_proxy`。

---

## 7. 仍未处理（待拍板）

> 全部**未动**，仅登记。需要动时先确认，因为工作流与脚本的字节和时间戳是回滚锚点。

### 7.1 体积大头：生成产物落在 plan 内（现状 19 个 mp4 = 8.22 MB，占全目录 23.6%）

> ⚠️ 本节原表所列 `h3_multisegment_2_3456x1920.mp4`（21.0 MB）等 4 个大文件**已在 §6.1 归档时移出 plan，现已不存在**，整表于 2026-10-02 按实测重记。

| 位置 | 数量 / 体积 | 说明 |
|---|---|---|
| `bat\分段归档\{multisegment,ref2va,scenes,scenes_ref}\` | 12 个 / 3.80 MB | 分段中间产物，每族 3 个（含 `seg0.mp4`） |
| `bat\{multisegment,scenes,scenes_ref,ref2va,scenes_ref_8b_heretic}\` | 5 个 / 3.97 MB | 各脚本目录里的单段成品 |
| `ck_ab_20261002\` | 2 个 / 0.46 MB | `selftest_same.mp4` / `selftest_perturbed.mp4`（比对工具的自检样本） |
| **合计** | **19 个 / 8.22 MB** | 占 plan 全目录 **25.0%**（plan 总计 329 文件 / 33.41 MB） |

`plan\` 根目录**已无散落 mp4**（§6.1 归档后状态），产物只存在于上述三个脚本族目录内。

> 另有非 mp4 的生成产物同样不入库：`bat\分段归档\*\{first,last}_frame.png`（18 张 / 1.9 MB）、`bat\<族>\img\` 与 `bat\测试素材\`（10 张 PNG / 7.7 MB）、`ck_ab_20261002\` 的对照图与自检样本（15 文件 / 6.44 MB）、`plan2` 的两张对照图（2.94 MB）。

### 7.2 结构不一致

| 项 | 问题 |
|---|---|
| `bak\`（plan 根） | `gen_h3_multisegment.py` 与 `bat\multisegment\gen_h3_multisegment.py` 同名不同版（13.4 KB vs 15.6 KB），易误用；`gen_video_ask.*` 已无对应目录（现已退场归入本目录，勿取用，见 §8 硬规矩） |
| `API_workflows\{Calliope,go,omy}\bak *` | 命名不统一：`bak 04  OK`（双空格）/ `bak 05 OK` / `bak 04`；`bak 04` 与 `bak 05 OK` 文件重叠。另 `omy\` 只有 `bak 01`，与另两族步数不齐 |
| `molbal_workflows\final\4b\op\` | 比同级的 `final\op-8b\` 深一层。⚠️ `API_workflows\未测试\final\` **刻意沿用了同样的深一层**，以保证两种格式层级可对照 |
| `final\提示词模板在bat里.txt` | 0 字节占位指针（仍存在） |
| ~~`提示词模板-视频.txt` 在 `bat\` 与 `final\` 双份~~ | ✅ **已解决**：唯一实体已归 `bat\提示词模板\提示词模板-视频.txt`（4053 B / 67 行，10-01 修订版），`final\` 侧只剩 0 字节指针 `提示词模板在bat里.txt`。仓库另存删减前版本为 `final\提示词模板-视频.txt.pre-trim-20261001.bak`（§2.1） |
| `API_workflows\未测试\` 目录名 | ⚠️ **语义与内容矛盾**：名字叫「未测试」，但用户 2026-10-06 确认所有工作流均已实战跑通，且该目录内还套着 `final\` 交付层（15 份）。按 §8 硬规矩**不改名**，仅记录 |
| 仍指向 `molbal_workflows/test` 的脚本 **5 份** | §6.2 只修了点名的 2 份 8B 脚本。仍为失效路径（正确应为 `final\4b\` / `final\4b\op\`）的 5 份：`bak\gen_h3_multisegment.py`、`bat\multisegment\gen_h3_multisegment.py`、`bat\scenes\gen_h3_scenes.py`、`bat\scenes_8b\gen_h3_scenes-8b.py`、`bat\scenes_8b_heretic\gen_h3_scenes-8b-heretic.py`。**仅注释，不影响运行**；按 §8 硬规矩未授权故未动 |
| ~~`infinite-creation\Final\qwen3_tts_voice_design_GUFF.json`~~ | ✅ **已解决**（2026-10-06）：`GUFF` → `GGUF` 已由用户改名（覆盖 §8 不改名硬规矩），**改名后实测跑通**；D 盘与仓库同步，字节未变（sha256 `A4B50744…17233C21`）。事实备注（非遗留问题）：内容仍走 `QwenTTSModelsLoader` 从 HuggingFace 拉 `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`、`precision: bf16`（非 GGUF 量化），且是 UI 格式 → API 格式的适配版（原版 `qwen3_tts_voice_design.json` 用 `Qwen3TTSModelLoader` + `Qwen3TTSVoiceDesign`，API 版换成 `⚡` 后缀的 `QwenTTSModelsLoader` + `QwenTTSVoiceDesignGenerate` + `SaveAudio`），同目录其它 API 版文件无后缀 |

---

## 7.3 命名瑕疵汇总（默认按 §8 硬规矩不改名，仅记录；唯一例外见表内标注）

| 位置 | 瑕疵 | 处置 |
|---|---|---|
| `API_workflows\未测试\` | 目录名暗示未验证，实际全部跑通，且内含 `final\` 交付层 | 记录。取交付层看 `未测试\final\` |
| `API_workflows\未测试\final\README.md` | 原文 9 处路径引用写作 `API_workflows\final\`，该路径不存在 | **已改正**（2026-10-06，文档非工作流，可改） |
| ~~`…\Final\qwen3_tts_voice_design_GUFF.json`~~ | ✅ **已解决**：`GUFF` 拼错 → 2026-10-06 改名 `GGUF` 并实测跑通（本表唯一改名例外，用户授权覆盖 §8）；内容事实见 §7.2 | 已闭环 |
| `API_workflows\{Calliope,go}\bak 04  OK` | 双空格 | 记录 |

---

## 8. 修改本目录的硬规矩

1. **工作流与脚本只增不改、不删、不移、不改名** —— 字节与时间戳是回滚锚点。
2. 参数覆盖只在**内存**中进行，不写回 JSON。
3. 新增变体一律**新建目录**（如 `_8b_heretic`），不改动原目录内任何文件。
4. 新增脚本族遵循 `bat\<族名>[_<TE变体>]\` + `gen_<族名>[-<变体>].py|bat` + `prompt.txt`。
5. 实测产物（json / jsonl / csv / log / mp4）落在 `plan\` 根，报告按精确相对路径引用。
