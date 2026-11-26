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
| `Sulphur3-省显存部署总结.md` | **主文档**。环境、选型、模型清单、节点、启动参数、省显存决策、未验证项 |
| `API_workflows\` | **12 条 API payload**：4 任务 × 3 编码器档（4B / 8B / 8B-heretic） |
| `workflows\` | **12 张 UI 工作流**：同名 JSON，可拖进 Desktop 界面编辑 |
| `tools\make_workflows.py` | 从 API graph 生成上述 24 个 JSON（需 ComfyUI 在线读 `/object_info`） |
| `tools\migrate_8b.py` | 从 plan1 移植 8B / 8B-heretic 脚本族的一次性工具 |
| `bat\gen_sulphur.py` | 多段生成（t2v / 首帧续接），首测脚本 |
| `bat\gen_h3_{multisegment,ref2va,scenes,scenes_ref}-8b*.py` | plan1 的 8 个 8B / 8B-heretic 脚本，模型常量已换 Sulphur |
| `bat\run_workflow.py` | 通用提交器，读任意 `API_workflows` 图，支持 12 种组合 |
| `bat\run_sulphur.bat` | 启动器（4 段 × 5 s / 864×480 / 20 步） |
| `bat\prompt.txt` | 提示词（从 plan1 复制） |
| `bat\gen_extract_frames.py` | 抽帧工具（ffmpeg 路径已修为 9.1） |
| `bat\gen_h3_qc_frames.py` | 帧质检工具（ffmpeg 路径已修为 9.1） |
| `bat\free_vram.py` | `/free` 显存释放工具 |
| `bat\step0_free.py` | step 0 卸 DiT 钩子（plan3 无预览版移植，支持 `--install/--revert`） |

**4 条工作流与原生节点**：

| 任务 | 关键节点 | 输入 |
|---|---|---|
| t2v | `MiniMaxH3ImageToVideo` | 纯提示词 |
| i2v | + `LoadImage → first_frame` | 首帧图 |
| flf2v | + `LoadImage ×2 → first_frame / last_frame` | 首尾帧 |
| ref2v | + `MiniMaxH3AddGuide(frame_idx=0, vae, image)` | 参考图 |

四条任务 × 三档编码器：4B 走 `CLIPLoaderGGUF`（GGUF，三段最省显存），
8B / 8B-heretic 走 `CLIPLoader`（safetensors，`boogu`）→ `ClipProjApply`。
全部共用 `UnetLoaderGGUF` → 双 VAE → 20 步 `simple` / `res_multistep` / cfg 1.0。

**8B 编码器选了 plan3 的 int8_convrot 版**，不是 plan1 的 fp8 版：

| 档 | 文件 | 磁盘 | staged 显存 |
|---|---|---:|---:|
| 8B stock | `qwen3vl_8b_int8_convrot.safetensors` | 9.35 GB | ~9.35 GB |
| 8B heretic | `qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors` | 10.98 GB | ~8.47 GB（plan3 §7.7 实测） |

plan1 的 fp8 heretic 实测 staged **16,721 MB**，超出可用显存；int8 版是 plan3 跑通后的选择。

Sulphur 没有 ref2va 专用权重（官方 `s3_ref2va` 标注 not trained），ref2va 脚本的两个 DiT 常量都指向主权重。

## 2. 一句话结论

Sulphur 3 是**标准非 Turbo 的 H3 fine-tune**，采样范式与 plan1 的 20 步链一致，
与 plan3 的 HyperFlow 6 步蒸馏线不兼容。因此模型与工作流走 plan1 形态，
环境用 plan3 的较新内核（实机 0.46.3 / torch 2.12+ROCm 7.14），
**不混 HyperFlow 的节点与 schedule**。

## 3. 省显存三件事

1. **DiT**：`Sulphur-3-Q4_K_M.gguf`（11.6 GB）。不用 Q5（14.1 GB）；Q3_K_M（8.9 GB）是撞墙退路。
2. **文本编码器**：4B heretic Q4_K_M（2.5 GB）+ 4B ClipProj 矩阵（25 MB），
   比 plan3 的 8B int8（8.47 GB）省约 6 GB。
3. **视频 VAE**：int8_convrot（2.81 GB），比 fp16（5.2 GB）省 2.4 GB。音频 VAE 必需 fp32（605 MB）。

## 4. 当前状态

- [x] git 分支 `plan4`、仓库目录 `plan4/`
- [x] 环境副本 `C:\plan4\plan4`（来自 `D:\localAI\plan3\Comfy-Desktop\ComfyUI-Installs\ComfyUI`）
- [x] 节点：`ComfyUI-GGUF`、`ComfyUI-ClipProj`、`ComfyUI-ForceUnloadBeforeDecode`
- [x] 小模型：4B TE + mmproj + 4B 矩阵 + 音频 VAE（从 plan1 复制）
- [x] 大模型：Sulphur Q4_K_M（11,564,180,576 B）、视频 VAE int8（2,811,065,184 B）
- [x] `gguf` 包已装进 `.venv`（0.19.0，阿里云镜像；ComfyUI-GGUF 节点依赖）
- [x] Desktop 启动参数已生效（`/system_stats` argv 已确认 5 条全在）
- [x] 首测通过：864×480 / 124 帧 / 20 步 / seed `3538674239439636468` = **315.3 s**，产物正常
- [x] 首测发现并修复：`ClipProjLoader` 看不到 GGUF → 改 `CLIPLoaderGGUF` + `ClipProjApply`；
      4B `Qwen3_4B` 缺 `preprocess_embed` → `install_video_blocks` 加 `getattr` 跳过；ffmpeg 9.0.2 → 9.1
- [x] 12 条 API + 12 张 UI 工作流已生成，通用提交器与 3 个工具脚本已就位
- [x] 8B / 8B-heretic 脚本族 8 个已移植（int8 编码器 + Sulphur 权重 + int8 VAE）
- [x] step0 卸载 A/B：同 seed 315.3 s → 330.5 s（+4.8%），显存确实释放；短片净亏，长片才值
- [x] 当前钩子状态：已装（`step0_free.py --revert` 可恢复快档）

## 5. 重要边界

- **预览**：新版 `--preview-method auto` 是 latent2rgb 缩略图，不占权重显存；
  plan1 的 `preview_watch` 补丁（预览 + step0 卸 DiT）**未移植**，
  本环境也没有它的触发条件。要长片防爆显存，需在实测后单独评估。
- **帧数**：`17k+5` 网格，20 s → 481 帧（20.04 s）。官方训练范围 124–362 帧，
  481 帧属分布外，能跑但需重测耗时。
- **步数**：20 / cfg 1.0 / simple / euler（或 res_multistep，plan1 基线用后者）。
- **许可**：MiniMax H3 Community License（含区域与用途限制），商用前自行核对。
