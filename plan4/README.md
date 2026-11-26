# plan4 — Sulphur 3 省显存部署（独立环境）

> 分支 `plan4`，环境根目录 `C:\plan4`。本目录是仓库侧文档与脚本副本；
> 实机环境在 `C:\plan4\plan4`（Comfy Desktop 内核副本），模型按 ComfyUI 原生
> `models\` 目录摆放，不依赖 Desktop 的 `instance-model-paths` yaml。
>
> `plan\`、`plan2\`、`plan3\` 均不改动、不移、不删。plan3 的 Comfy Desktop 已由
> 用户移到 `D:\localAI\plan3\Comfy-Desktop`，本环境是它的独立副本，两者互不影响。

---

## 1. 顶层构成

| 文件 / 目录 | 内容 |
|---|---|
| `Sulphur3-省显存部署总结.md` | **主文档**。环境、选型、模型清单、节点、启动参数、省显存决策、实测与未验证项 |
| `API_workflows\` | **12 条 API payload**：4 任务 × 3 编码器档（4B / 8B / 8B-heretic） |
| `workflows\` | **12 张 UI 工作流**：同名 JSON，可拖进 Desktop 界面编辑 |
| `tools\make_workflows.py` | 从 API graph 生成上述 24 个 JSON（需 ComfyUI 在线读 `/object_info`） |
| `tools\migrate_8b.py` | 从 plan1 移植 8B / 8B-heretic 脚本族的一次性工具 |
| `tools\apply_s3_params.py` | 套用 S3 官方采样参数（SigmaShift + Euler），幂等且防自引用 |
| `bat\gen_sulphur.py` | 多段生成（t2v / 首帧续接），首测脚本 |
| `bat\gen_h3_{multisegment,ref2va,scenes,scenes_ref}-8b*.py` | plan1 的 8 个 8B / 8B-heretic 脚本，模型常量已换 Sulphur |
| `bat\run_workflow.py` | 通用提交器，读任意 `API_workflows` 图，支持 12 种组合 |
| `bat\run_sulphur.bat` | 启动器（4 段 × 5 s / 864×480 / 20 步） |
| `bat\prompt.txt` | 原 H3 三段式提示词（integrated_multimodal_description 等） |
| `bat\prompt_s3.json` | **S3 官方结构化 JSON 提示词**（推荐，见 §5） |
| `bat\gen_extract_frames.py` | 抽帧工具（ffmpeg 路径已修为 9.1） |
| `bat\gen_h3_qc_frames.py` | 帧质检工具（ffmpeg 路径已修为 9.1） |
| `bat\free_vram.py` | `/free` 显存释放工具 |
| `bat\step0_free.py` | step 0 卸 DiT 钩子（plan3 无预览版移植，支持 `--install/--revert`） |

**4 条任务与原生节点**：

| 任务 | 关键节点 | 输入 |
|---|---|---|
| t2v | `MiniMaxH3ImageToVideo` | 纯提示词 |
| i2v | + `LoadImage → first_frame` | 首帧图 |
| flf2v | + `LoadImage ×2 → first_frame / last_frame` | 首尾帧 |
| ref2v | + `MiniMaxH3AddGuide(frame_idx=0, vae, image)` | 参考图 |

四条任务 × 三档编码器：4B 走 `CLIPLoaderGGUF`（GGUF，最省显存），
8B / 8B-heretic 走 `CLIPLoader`（safetensors，`boogu`）→ `ClipProjApply`。
全部共用 `UnetLoaderGGUF` → `MiniMaxH3SigmaShift(12, 3)` → 双 VAE →
20 步 `simple` / **`euler`** / cfg 1.0 —— 这是 S3 官方参数（见 §5），不是 plan1 的 `res_multistep`。

**8B 编码器选了 plan3 的 int8_convrot 版**，不是 plan1 的 fp8 版：

| 档 | 文件 | 磁盘 | staged 显存 |
|---|---|---:|---:|
| 8B stock | `qwen3vl_8b_int8_convrot.safetensors` | 9.35 GB | ~9.35 GB |
| 8B heretic | `qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors` | 10.98 GB | ~8.47 GB（plan3 §7.7 实测） |

plan1 的 fp8 heretic 实测 staged **16,721 MB**，超出可用显存；int8 版是 plan3 跑通后的选择。

Sulphur 没有 ref2va 专用权重（官方 `s3_ref2va` 标注 not trained），ref2va 脚本的两个 DiT 常量都指向主权重。

## 2. 一句话结论

Sulphur 3 是**标准非 Turbo 的 H3 fine-tune**，20 步采样范式与 plan1 一致，
与 plan3 的 HyperFlow 6 步蒸馏线不兼容。因此模型与工作流走 plan1 形态，
环境用 plan3 的较新内核（实机 0.46.3 / torch 2.12+ROCm 7.14），
**不混 HyperFlow 的节点与 schedule**；采样参数按 S3 官方修正为 euler + shift 12/3。

## 3. 省显存三件事

1. **DiT**：`Sulphur-3-Q4_K_M.gguf`（11.6 GB）。不用 Q5（14.1 GB）；Q3_K_M（8.9 GB）是撞墙退路。
2. **文本编码器**：4B heretic Q4_K_M（2.5 GB）+ 4B ClipProj 矩阵（25 MB），
   比 8B int8（8.47 GB staged）省约 5 GB；8B 档作为质量路线并存。
3. **视频 VAE**：int8_convrot（2.81 GB），比 fp16（5.2 GB）省 2.4 GB。音频 VAE 必需 fp32（605 MB）。

## 4. 当前状态（2026-11-26）

- [x] git 分支 `plan4`、仓库目录 `plan4/`；已提交 `d5e33c7` / `803f3e4` / `0736150` / `35f1100` / `be32068`
- [x] 环境副本 `C:\plan4\plan4`（来自 `D:\localAI\plan3\Comfy-Desktop\ComfyUI-Installs\ComfyUI`）
- [x] 节点：`ComfyUI-GGUF`、`ComfyUI-ClipProj`、`ComfyUI-ForceUnloadBeforeDecode`
- [x] 模型：4B TE + mmproj + 4B 矩阵；8B / 8B-heretic int8 TE + 8B 矩阵；
      Sulphur Q4_K_M（11,564,180,576 B）；视频 VAE int8（2,811,065,184 B）；音频 VAE fp32
- [x] `gguf` 包已装进 `.venv`（0.19.0，阿里云镜像；ComfyUI-GGUF 节点依赖）
- [x] Desktop 启动参数已生效（`/system_stats` argv 已确认 5 条全在）
- [x] 首测通过：864×480 / 124 帧 / 20 步 / seed `3538674239439636468` = **315.3 s**，产物正常
      （**旧参数** `res_multistep`、无 SigmaShift；现资产已改 euler + shift，**需重测**）
- [x] 首测发现并修复：`ClipProjLoader` 看不到 GGUF → `CLIPLoaderGGUF` + `ClipProjApply`；
      4B `Qwen3_4B` 缺 `preprocess_embed` → `install_video_blocks` 加 `getattr` 跳过；ffmpeg 9.0.2 → 9.1
- [x] 12 条 API + 12 张 UI 工作流已生成并同步到 `C:\plan4`；通用提交器与工具脚本已就位
- [x] 8B / 8B-heretic 脚本族 8 个已移植（Sulphur 权重 + int8 VAE + int8 编码器）
- [x] 用户实测 `workflows/sulphur_t2v_8b_heretic.json` 拖进 Desktop **可跑**（2026-11-26）
- [x] 新实测（step 0 卸 DiT + 长提示词 + 8B heretic + euler/shift/JSON）：
      **480P × 5 s = 320 s、10 s = 723 s；720P × 5 s = 900 s**（主文档 §9.6 / §9.7）
- [x] 甜点预测：480P **8–10 s**、720P **5 s**；20 s 走 4×5 s 分段（主文档 §9.7）
- [x] step0 卸载 A/B：同 seed 315.3 s → 330.5 s（+4.8%），显存确实释放；短片净亏，长片才值
      （同为旧参数下的对照）
- [x] 当前钩子状态：**已装**（`step0_free.py --revert` 可恢复快档）

## 5. S3 官方参数与提示词（2026-11-26 核实）

官方 `S3_ComfyUI.zip/example_workflow.json` 的说明：

| 项 | S3 官方 | 此前 plan4（错） | 现资产 |
|---|---|---|---|
| sampler | **euler** | res_multistep / er_sde | euler ✓ |
| shift | **video 12 / audio 3** | 无 SigmaShift | `MiniMaxH3SigmaShift(12,3)` ✓ |
| schedule | simple | simple | simple ✓ |
| CFG | 1（guidance-distilled，negative prompt 被忽略） | 1 | 1 ✓ |
| 提示词 | **结构化 JSON captions** | H3 三段式 | `prompt_s3.json` ✓ |

已修正所有脚本与 12 条工作流；`tools\apply_s3_params.py` 是幂等补丁且修复了 SigmaShift 自引用问题。

**Corrector 暂不装**：`s3_corrector.safetensors` 7.44 GB，fp32 常驻约 8 GB；
24 GB 卡上 DiT 11.6 + 8B TE 9~11 + 双 VAE 5.8 + corrector 8 会爆。官方也明确它是可选项。

## 6. 重要边界

- **预览**：新版 `--preview-method auto` 是 latent2rgb 缩略图，不占权重显存；
  plan1 的 `preview_watch` 补丁未移植（不需要，新版自带预览）。
  step0 卸 DiT 已用无预览版 `step0_free.py` 单独装上并 A/B 过（主文档 §9.2），当前已装。
- **帧数**：`17k+5` 网格，20 s → 481 帧（20.04 s）。官方训练范围 124–362 帧，
  481 帧属分布外，能跑但需重测耗时。
- **采样**：20 步 / `simple` / `euler` / `MiniMaxH3SigmaShift(video 12, audio 3)` / cfg 1.0。
- **时长**：480P 5 s / 10 s、720P 5 s 已实测；720P × 10 s 与 ≥294 帧未实测（§9.7 为外推）。
  甜点预测：480P 8–10 s、720P 5 s。要 20 s 走 4×5 s 分段。
- **许可**：MiniMax H3 Community License（含区域与用途限制），商用前自行核对。
