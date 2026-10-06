# plan2 — Qwen-Image 2.1 (GGUF) 工作区

> 本目录是 **`plan\` 的姊妹目录**，不是它的子目录。
> `plan\` 放 MiniMax H3 生视频的全部资产；`plan2\` 只放 **Qwen-Image 2.1 生图**这条线。
> 两者共同构成 `D:\localAI\ComfyUI-last\` 下的实测资产，仓库侧对应 `plan2/`。

---

## 1. 顶层构成

| 文件 / 目录 | 内容 | 规模 |
|---|---|---|
| `Qwen-Image-2.1-GGUF-部署总结.md` | **主文档**。目标 / 结论 / 环境 / 模型 / 适配做了什么 / 7 类节点依赖 / 实测结果 / 9 节踩坑 / 官方 skill 调查结论 | 12 节 |
| `qwen21-tools\` | 工作流工具链 + flag 实测脚本 + 上游 issue 材料 | 73 文件 / 4.06 MB |

---

## 2. `qwen21-tools\` 分三层

### 2.1 工具脚本（17 份 `.py`）

| 脚本 | 作用 |
|---|---|
| `check_workflows.py` | 静态校验：悬空 link、`UnetLoaderGGUF` 数量、引用的模型是否真在磁盘上 |
| `fetch_schema.py` | 从运行中的 ComfyUI `/object_info` 抓 `node_schema.json`（转换器依赖它） |
| `ui2api.py` | 前端 UI 格式 → API prompt 格式（含子图展开、autogrow 扁平 key、widget 位置映射） |
| `run_api.py` | 把 API 图丢给 `/prompt` 并轮询到出结果 |
| `adapt_workflows.py` | 从**已安装的** `comfyui-workflow-templates` 官方模板重新生成 GGUF 工作流，Comfy-Org 出新模板时用它 |
| `add_shift_all.py` | 给每个工作流插入 `ModelSamplingAuraFlow(shift=3.1)`，位置对齐官方 blueprint |
| `make_q8_set.py` | 由 Q4_K_M 版派生 Q8_0 版，只换 `UnetLoaderGGUF` 的模型引用 |
| `fix_q8_instance.py` | 修 Q8_0 工作流：参数序列化两份，**子图 INSTANCE 的 `widgets_values` 里也内联了 unet**，必须同步改 |
| `bisect.py` / `len_bisect.py` | 提示词留一法二分 / 长度-内容解耦（`T*` 精确 token 数截断） |
| `probe_tokens.py` | 走真实 tokenizer，并重放 `QwenImage21TEModel.encode_token_weights` 的 keep-mask，算出到底哪些文本进了 DiT |
| `shift_ab.py` / `cfg_ab.py` / `attn_ab.py` | 单变量 A/B：shift 节点 / cfg / attention 后端 |
| `flag_sweep.py` | 扫 ComfyUI 启动 flag，每组跑 T82 探针 |
| `accept_full.py` | 验收：用用户原始完整提示词（95 字符 / 101 token，远超原 74 字符崩坏点）在修正 flag 下重跑 |
| `sheet.py` | 把 BISECT_* 输出拼成带标签的对照图 |

### 2.2 上游 issue 材料（提交给 comfy-kitchen）

| 文件 | 内容 |
|---|---|
| `PR_submission_CN.md` / `PR_submission_EN.md` | 提交到 [comfy-kitchen issue #226](https://github.com/Comfy-Org/comfy-kitchen/issues/226) 的补充材料。**关键发现：token 长度边界精确落在 64**（注意力核 tile 宽度），78 token→64 存活正常，82 token→68 存活即损坏。已定位到 `comfy_kitchen/sage_attention.py` 的硬编码阈值 |
| `report_en.md` | 英文版报告 |
| `CK注意力回归问题调查报告.md` | **本文件是 `plan\CK注意力回归问题调查报告.md` 的副本**（2026-10-06 同步，权威版在 `plan\`）。同名 `.pre-ab-20261002.bak` 是 A/B 之前的旧版快照，§7.3 当时仍写「H3 DiT 未验证」 |

### 2.3 实验留痕

| 类别 | 数量 | 说明 |
|---|---|---|
| `api_*.json` | 22 | 各阶段实际提交给 `/prompt` 的 API 图，按实验分组命名（`V0~V6` 消融、`SHIFT_T*`、`CFG4_T*`、`ATTN_T*`、`ACCEPT_*`） |
| `*_manifest.json` | 6 | 每组实验的清单：tag / 源 PNG / 字符数 / prompt 原文 / 产出文件名。**prompt 是从已生成的 PNG 里读回来的，保证逐字节一致** |
| `comfy_run_*.log` | 5 | 5 组启动 flag 下的 ComfyUI 启动日志（ck / fp16 upcast / default attention / dynamic vram / fp16 mid only） |
| `*.err.log` | 6 | 配套 stderr，多数为 0 字节（无报错） |
| `对照图.png` / `flag_sweep_sheet.png` | 2 | 视觉对照图，**不入库**（2.94 MB，仓库侧不含） |
| `node_schema.json` | 1 | `/object_info` 缓存，`ui2api.py` 的依赖。**入库**，ComfyUI 升级后跑 `fetch_schema.py` 刷新 |

---

## 3. 启动脚本（⚠️ 与 `plan\` 的 H3 不同，勿混用）

| 用途 | 启动脚本 | `--use-ck-attention` |
|------|----------|:---:|
| **Qwen 生图**（本目录全部工作流） | `run_amd_gpu_no_ck_attention.bat` | ❌ 关 |
| **H3 生视频**（`plan\`） | `run_amd_gpu_enable_dynamic_vram.bat` | ✅ 开 |

两个脚本**都带 `--enable-dynamic-vram`** —— 动态显存是 OOM 的关键，这条不变；
区别只在 ck 开关，所以别认错脚本。

**⚠️ 口径变更（2026-10-03 用户实测）**：本目录两份文档原先都写「只能用
`run_amd_gpu_enable_dynamic_vram.bat`」，那条结论只验了动态显存、没拆开 ck 变量。
后续实测 ck 对生图是负向的：图片会「脏」、与提示词不符，且**超过一定长度的提示词会丢失**。
故生图一律关 ck。详见 `Qwen-Image-2.1-GGUF-部署总结.md` §3。

---

## 4. 硬编码路径（跨机必改）

| 文件 | 常量 | 现值 |
|---|---|---|
| `check_workflows.py` | `WF` / `MODELS` | `…\ComfyUI_windows_portable\ComfyUI\user\default\workflows` / `…\ComfyUI\models` |
| `adapt_workflows.py` | `TPL` | `…\python_embeded\Lib\site-packages\comfyui_workflow_templates_json\templates` |
| `run_api.py` | `BASE` | `http://127.0.0.1:8188` |
| `fetch_schema.py` | — | 同上，走 `/object_info` |

---

## 5. 与 `plan\` 的分工

| | `plan\` | `plan2\` |
|---|---|---|
| 模型 | MiniMax H3（8B / 4B，GGUF + fp8 TE） | Qwen-Image 2.1（abenzerps GGUF，Q4_K_M / Q8_0） |
| 产出 | 视频（含音频轨） | 静态图 |
| ck | ✅ 开（实测安全，见 `plan\ck_ab_20261002\`） | ❌ 关（生图会脏 + 丢长提示词） |
| 崩坏问题 | 无 | 有，token>64 即损坏，已提交上游 issue #226 |
| 工作流格式 | UI 格式（`molbal_workflows\`）+ API 格式（`API_workflows\`） | UI 格式交付在 `ComfyUI\user\default\workflows\`，API 图留痕在本目录 |

---

## 6. 复现前置

- ComfyUI **必须**先起来（8188），`run_api.py` / `fetch_schema.py` 依赖 HTTP 接口。
- 「所有工作流都已实战跑通」（用户 2026-10-06 确认），本目录**不需要重跑测试**即可作为交付依据。
- 但 `node_schema.json` 与 ComfyUI 版本绑定：升级 ComfyUI 后建议跑一次 `fetch_schema.py`，否则 `ui2api.py` 的 widget 位置映射可能对不上。