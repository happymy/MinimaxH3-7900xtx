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
| `bat\gen_sulphur.py` | API 直连生成脚本（从 `plan\bat\multisegment\` 改造，只换模型常量与 ClipProj 节点） |
| `bat\run_sulphur.bat` | 启动器（4 段 × 5 s / 864×480 / 20 步） |
| `bat\prompt.txt` | 提示词（从 plan1 复制） |

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
- [ ] 用 **Comfy Desktop** 启动 + 首测（480P / 124 帧 / 20 步）

## 5. 重要边界

- **预览**：新版 `--preview-method auto` 是 latent2rgb 缩略图，不占权重显存；
  plan1 的 `preview_watch` 补丁（预览 + step0 卸 DiT）**未移植**，
  本环境也没有它的触发条件。要长片防爆显存，需在实测后单独评估。
- **帧数**：`17k+5` 网格，20 s → 481 帧（20.04 s）。官方训练范围 124–362 帧，
  481 帧属分布外，能跑但需重测耗时。
- **步数**：20 / cfg 1.0 / simple / euler（或 res_multistep，plan1 基线用后者）。
- **许可**：MiniMax H3 Community License（含区域与用途限制），商用前自行核对。
