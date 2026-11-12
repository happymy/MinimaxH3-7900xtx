# MinimaxH3-7900xtx

**Win11 + 32GB RAM + AMD RX 7900 XTX (24GB, gfx1100)：本地跑 MiniMax H3 视频生成（T2V / I2V / FLF2V / 参考图生视频）的部署与实测记录。**

> **现状（2026-11-12 起重写）**：整条线已从「旧 portable 环境」换成 **Comfy Desktop 新环境 +
> HyperFlow H3 Flash（14B 蒸馏加速版，GGUF）+ Qwen3-VL-8B + ClipProj**。
> 现行文档只有 **`plan3/`**；`plan/`、`plan2/` 是旧 portable 环境的资产，**已废弃**，只留作历史对照。

| 目录 | 内容 | 状态 |
|---|---|---|
| **`plan3/`** | **现行**。新环境（ComfyUI 0.45.2 / ROCm 7.14）的 H3 全部资产：部署总结、工作流工具、API 工作流、bat 脚本族、提示词规则 | ✅ 唯一现行 |
| `plan2/` | Qwen-Image 2.1 生图线（与 H3 无关，同机另一条线） | 旧环境，已废弃 |
| `plan/` | 旧 portable 环境（0.39.x，原生 H3 20 步）全部资产；根目录旧版 README 已归档到 `plan/归档/README-portable-0.39-旧版.md` | 旧环境，已废弃 |
| `src/` | infinite-creation 等下游接入配置 | 未变 |

---

## 一、新基线（实测，勿再按旧数字）

| 项 | 旧 portable（`plan/`） | **新 Comfy Desktop（`plan3/`）** |
|---|---|---|
| 模型 | MiniMax H3 14B，20 步 | **HyperFlow H3 Flash 14B GGUF Q4_K_M，6 步** |
| 文本编码器 | Qwen3-VL-4B/8B + ClipProj（单节点 CCTech loader） | **Qwen3-VL-8B Heretic fp8 + `mmh3-8b-ClipProj-v3.1-mlp`（两段式 `Load CLIP` + `ClipProj Apply`）** |
| 成片 | 480P（864×480）/ 5 s ≈ 9.5 min | **1344×768 / 124 帧 / 5.17 s，带音轨，≈ 278–294 s** |
| 采样 | 20 步 | **6 步，38 s/it ≈ 230 s**（4 快 / 8 细） |
| 显存 | 靠顺序卸载 | **加载时可用 15,299 MB，DiT 载入 8,937 MB —— 已在极限** |
| 前置纪律 | 关闭其它占显存程序 | **每次点 Queue 前必须先 `/free`**（上一轮残留 14.5 GB，第二次必爆） |

**结论：同卡同内存下，画面上到 720P、单条耗时降到旧基线的 1/2。** 详细证据链见
`plan3/HyperFlow-H3-Flash-GGUF-部署总结.md`。

显存档位（token 公式 `(length/4)×(width/32)×(height/32)`，本卡上限约 33.5k token）：

| 分辨率 | 帧数 | 秒 | token | 实测 |
|---|---|---|---|---|
| 1344×768 | 124 | 5.2 | 31,248 | ≈ 294 s，不爆 |
| 832×480 | 345 | 14.4 | 33,540 | 324 s，不爆 |
| 832×480 | 362 | 15.1 | 35,100 | **爆显存，慢 3–4 倍**，不要试 |

要更长就分段生成再拼（`plan3/bat/multisegment_8b_heretic` / `scenes_8b_heretic`）。

---

## 二、快速开始（每天用的流程）

```powershell
$py = "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"

# 1. 启动 Comfy Desktop，启动参数（installations.json -> launchArgs）：
#    --enable-manager --use-ck-attention --preview-method auto
#    --disable-smart-memory --cache-none --fp16-intermediates
#    （--fast-disk 本机按磁盘类型自动为 True，--enable-dynamic-vram 已是默认）

# 2. 关掉所有占显存的程序（浏览器硬件加速 / 其它 ComfyUI / 游戏）

# 3. 每次点 Queue 之前卸一次，等到 total - 1.5 GB 才返回（连续生成必做）
& $py "D:\localAI\ComfyUI-last\plan3\t2v\step0_free.py"

# 4. 点 Queue，或在工作流列表里选 hyperflow_<family>_clipproj_8b.json
```

`step0_free.py` 打印 `ok : 23.5x GB free` 才可以点 Queue；打印 `FAILED` 说明还有进程占着显存。

**四条工作流**（UI，`ComfyUI\user\default\workflows\`）：

| 文件 | DiT | 额外输入 |
|---|---|---|
| `hyperflow_t2v_clipproj_8b.json` | `fl2va` | — |
| `hyperflow_i2v_clipproj_8b.json` | `fl2va` | 首帧 |
| `hyperflow_flf2v_clipproj_8b.json` | `fl2va` | 首帧 + 末帧 |
| `hyperflow_ref2v_clipproj_8b.json` | `ref2va` | 参考图 ×1–9 |

**四条 API 工作流**（`/prompt` 直连，`plan3/API_workflows/`）：同样的四个 family，文件名
`hyperflow_<family>_clipproj_8b_api.json`，提交前同样要先跑 `step0_free.py`。

---

## 三、三条不能动的硬约束

1. **采样参数**：`HyperFlowSigmas` 只取 4/6/8，`euler`，CFG 1（`BasicGuider`，无负向提示词）。
   改了不报错，只是白跑几分钟。
2. **每次提交前 `/free`**：图内挂卸载节点不够（缺 `gc.collect()` 和 `e.reset()`），必须走 `/free`。
   同一提示词 + 固定 seed 第二次会命中图缓存（`Prompt executed in < 1 s`），那次实验作废。
3. **提示词**按 `plan3/bat/提示词模板/MiniMax-H3-提示词书写规则.md` 写：三字段缺一不可（没内容写 `N/A`），
   风格句放 `[Shot 1]` 后第一句，**不要写禁令** —— CFG 锁死 1，`no anime` 里的词照样进条件向量。

---

## 四、换机 / 重装

照 `plan3/HyperFlow-H3-Flash-GGUF-部署总结.md`：

- §5 安装清单（3 个自定义节点、`gguf` pip 包、6 个模型文件的落点）
- §6 工作流改了什么（`plan3/tools/make_workflow.py` 一次生成 UI + API 两套）
- §10 复现步骤（含三条静态自检）
- 硬编码路径清单见 `plan3/README.md` §5

---

## 五、历史（已废弃，仅在需要对照旧结论时看）

- `plan/`：旧 portable 环境（ComfyUI 0.39.x、torch 2.13+ROCm10.1）的原生 H3 20 步方案，
  含 448 个文件的资产地图、4B/8B 对比报告、CK 回归调查报告、15 个 bat 脚本族、预览内核补丁。
- `plan2/`：Qwen-Image 2.1 GGUF 生图线，与 H3 无关，未随本次切换。
