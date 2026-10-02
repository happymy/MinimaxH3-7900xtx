# plan 目录索引

MiniMax H3 本机部署与实测的**全部资产地图**。199 个文件 / 45.67 MB（2026-10-02 整理后）。
本文件是导航层；整理动作只做了归档、删字节码、修注释、补交付层、建显存估算模型，详见 §6。

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

> ### ⚠️ 本文件描述的是**实机目录全貌**，仓库是它的「文档 + 脚本 + 工作流」子集
>
> 实机根目录：`D:\localAI\ComfyUI-last\plan\`。**仓库 `plan\` 不含**下列资产（2026-10-02 裁决）：
>
> | 未入库 | 原因 | 在哪 |
> |---|---|---|
> | `API_workflows\`（全部，含 `final\` 交付层 15 份 + `H3工作流适配计划.md`） | API 格式工作流只在本机脚本链里用，随本机使用不随仓库分发 | 实机 `plan\API_workflows\` |
> | `归档\日志\*.log`（12 份）、`bat\_run_*.log` | 实测运行日志，体积大且可重生成；路径对照见 `归档\日志\来源清单.md` | 实机同名路径 |
> | `bat\分段归档\*.mp4` / `*.png`、`bat\<族>\h3_*.mp4` | 生成产物（约 35 MB，占实机目录 77%），应由 `ComfyUI\output\` 承接 | 实机同名路径 |
> | `bat\<族>\img\`、`bat\测试素材\` | 本机测试素材 | 实机同名路径 |
> | `molbal_workflows\bak *`、`API_workflows\{Calliope,go,omy}\bak *` | 调试期快照，随对应目录一并留在实机 | 实机同名路径 |
>
> **回滚锚点例外**：仓库**保留** `bak\`（5 份退场脚本）、`molbal_workflows\final\*.pre-q8fix.bak`（3 份）——体积小且是 §2.1 列的回滚锚点。

---

## 2. 文档（先读这 6 份）

| 文件 | 内容 |
|---|---|
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md` (约 91 KB / 1061 行) | **主计划**。**§3 显存预算模型**（预算双界 / staged 系数 / 装载判据 / 卸载纪律）、§5 目录结构图、§10 性能与显存、§11 分模型实测（11.8 8B 变体 / 11.9 op 系列 / 11.10 分辨率矩阵 / 11.11 破限专章） |
| `T2V_4B_vs_8B_对比报告.md` (约 30 KB / 433 行) | 4B vs 8B 主报告。§3.1 混淆变量、§9 0.60 MP 补测、§10 破限 A/B |
| `ComfyUI_MiniMaxH3_From_Scratch.md` (约 12 KB / 212 行) | 从零构建说明（模型清单、目录、启动参数） |
| `vision_qc_识图结论.md` (约 10 KB / 152 行) | 识图判定结论（0.40 MP 不糊 / 几何细节提升真实 / 4B-8B 无法排名） |
| `API_workflows\H3工作流适配计划.md` (约 9 KB / 157 行) | API 格式工作流适配方案 |
| `bat\提示词模板\MiniMax-H3-提示词书写规则.md` (约 19 KB / 330 行) | **提示词书写规则**（三字段信封 / `[Shot N]` 时间线 / 摄影机运动词表 / 帧栅格 / R2V 六段） |
| `API_workflows\final\README.md` | API 交付层的来源与三套 TE 对照 |
| `归档\日志\来源清单.md` | 12 个 `*.log` 归档前后的路径对照 |

> 体积写近似值（文档会持续修订，精确字节会自我失效）；**行数为审计时的精确值**。

> `bat\提示词模板\` 另有 4 份模板：`提示词模板-视频.txt`、`提示词模板-视频 - 静止.txt`、`提示词模板-照片.txt`（模块 A/B/C 的「隐形排除」正向写法出处）。

### 2.1 文档回滚锚点（勿删）

| 文件 | 说明 |
|---|---|
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md.20260930.bak` | 目录重组前快照 |
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md.old` | 更早快照 |
| `ComfyUI_MiniMaxH3_From_Scratch.md.old` | 更早快照 |
| `molbal_workflows\final\*.json.pre-q8fix.bak` | 3 份 Q8_0 修复前快照 |
| `molbal_workflows\bak noerror 0/1/2`、`bak RAW` | 4 套调试期快照（15 个文件） |
| `API_workflows\{Calliope,go,omy}\bak *` | API 格式调试期快照（31 个文件）。⚠️ `omy\` 的主目录内容已进交付层 `API_workflows\final\4b\`，但 `bak 01\` 仍原样保留 |

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

> 报告正文按 `plan\xxx.json` 的**精确相对路径**引用以上文件。移动它们必须同步改文档，收益为零风险不等。

---

## 4. `bat\` 脚本族矩阵

**4 个生成族 × 3 个文本编码器变体 = 12 个目录**，加 2 个工具目录（工具无变体），`bat\` 下共 14 个脚本目录。

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

每个目录都含 `gen_*.py` + `gen_*.bat`（Windows 入口）。
其中 **8 个有 `prompt.txt`**（`multisegment*` 3 个、`ref2va*` 3 个、`scenes`、`scenes_ref`）；
**6 个没有**（`extract_frames`、`qc_frames`、`scenes_8b`、`scenes_8b_heretic`、`scenes_ref_8b`、`scenes_ref_8b_heretic`）。

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

## 6. 本次整理已执行（2026-10-02）

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

---

## 7. 仍未处理（待拍板）

> 全部**未动**，仅登记。需要动时先确认，因为工作流与脚本的字节和时间戳是回滚锚点。

### 7.1 体积大头：生成产物落在 plan 内（6 个 mp4 = 35.1 MB，占全目录 77%）

| 文件 | 大小 | 说明 |
|---|---|---|
| `h3_multisegment_2_3456x1920.mp4` | 21.0 MB | 应在 `ComfyUI\output\` |
| `h3_multisegment_2_1728x960.mp4` | 10.4 MB | 同上 |
| `h3_multisegment_1.mp4` / `h3_multisegment_2.mp4` | 1.8 MB each | 同上 |
| `seg0.mp4` | 568 KB | 分段中间产物 |
| `bat\scenes\h3_scenes_4745687172311705797.mp4` | 1.1 MB | 脚本目录里的产物 |

### 7.2 结构不一致

| 项 | 问题 |
|---|---|
| `bak\`（plan 根） | `gen_h3_multisegment.py` 与 `bat\multisegment\gen_h3_multisegment.py` 同名不同版（13.7 KB vs 16.0 KB），易误用；`gen_video_ask.*` 已无对应目录 |
| `API_workflows\{Calliope,go}\bak *` | 命名不统一：`bak 04  OK`（双空格）/ `bak 05 OK` / `bak 04`；`bak 04` 与 `bak 05 OK` 文件重叠 |
| `molbal_workflows\final\4b\op\` | 比同级的 `final\op-8b\` 深一层。⚠️ `API_workflows\final\` **刻意沿用了同样的深一层**，以保证两种格式层级可对照 |
| `final\提示词模板在bat里.txt` | 0 字节占位指针 |
| `提示词模板-视频.txt` | 在 `bat\` 与 `final\` 双份（`final\` 那份是 0 字节指针，非重复内容） |
| `gen_h3_{multisegment,scenes}*.py` **共 4 份** | 注释仍写 `molbal_workflows/test`，该目录**不存在**（正确为 `final\4b\` / `final\4b\op\`）。本次只修了点名的 2 份 8B 脚本，另 4 份未授权故未动 |

---

## 8. 修改本目录的硬规矩

1. **工作流与脚本只增不改、不删、不移、不改名** —— 字节与时间戳是回滚锚点。
2. 参数覆盖只在**内存**中进行，不写回 JSON。
3. 新增变体一律**新建目录**（如 `_8b_heretic`），不改动原目录内任何文件。
4. 新增脚本族遵循 `bat\<族名>[_<TE变体>]\` + `gen_<族名>[-<变体>].py|bat` + `prompt.txt`。
5. 实测产物（json / jsonl / csv / log / mp4）落在 `plan\` 根，报告按精确相对路径引用。
