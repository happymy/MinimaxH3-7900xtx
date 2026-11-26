# Sulphur 3 省显存部署总结（plan4）

## 1. 目标

在独立的 `C:\plan4` 环境部署 **SulphurAI/Sulphur-3**，尽量压低 24 GB 卡（7900XTX）的显存占用，
并保留 plan1 已验证的 20 步采样链。

## 2. 关键判断：为什么不是 plan3 那套

| 事实 | 依据 |
|---|---|
| Sulphur 3 是 MiniMax H3 的 full fine-tune，标准非 Turbo | `SulphurAI/Sulphur-3` model card：「run it like any regular MiniMax H3 model」 |
| plan3 的 4 条 H3 工作流锁死 `HyperFlowSigmas=6 / euler / CFG 1` | `plan3\HyperFlow-H3-Flash-GGUF-部署总结.md` §4.4 |
| 套 HyperFlow schedule 到 Sulphur 上是「不报错，白跑 5 分钟」 | 同上，「改了不报错，只是白跑」 |
| plan1 的 20 步链与 Sulphur 逐项吻合 | `plan\bat\multisegment\gen_h3_multisegment.py` L59-77 |

结论：**模型与工作流走 plan1 形态，环境用 plan3 内核**。HyperFlow 快档继续留在 plan3，两者互补。

## 3. 环境（`C:\plan4\plan4`）

来自 `D:\localAI\plan3\Comfy-Desktop\ComfyUI-Installs\ComfyUI` 的独立副本，
`manifest.json` 基线 `v0.42.1-env1`：

| 项 | 值 |
|---|---|
| Python | 3.13.12（`.venv`） |
| torch | 2.12.0+rocm7.14.0 |
| torchvision / torchaudio | 0.27.0 / 2.11.0+rocm7.14.0 |
| 内核基线 | manifest 声明 v0.42.1（`63be2f9b`），实机 `comfyui_version.py` = **0.46.3** |
| comfy-kitchen / comfy-aimdo | 0.2.41 / 0.6.0（`.launcher\snapshots` 实机记录；manifest 基线为 0.2.39 / 0.5.6） |
| 模型根目录 | `C:\plan4\plan4\ComfyUI\models`（原生，不用 Desktop 的 Shared yaml） |

**用 Comfy Desktop 启动器启动**（不是命令行直跑 `main.py`），在 Desktop 的启动参数框填：

```
--enable-manager --use-ck-attention --preview-method auto \
--disable-smart-memory --cache-none --fp16-intermediates
```

Desktop 实际用 `ComfyUI\.venv\Scripts\python.exe` 跑内核（启动日志已确认）。
`ComfyUI-GGUF` 依赖的 `gguf` 包原先缺失，已装进该 `.venv`：**gguf 0.19.0**
（清华镜像 403，改用阿里云镜像 `https://mirrors.aliyun.com/pypi/simple/`）。

- **不加** `--enable-dynamic-vram`：ROCm 7.14+ 已默认开启（plan3 §3 实测）。
- **不加** `--fast-disk` / `--reserve-vram` / `--disable-pinned-memory`：plan3 实测后两条会把
  usable 从 15,299 MB 压到 9,634 MB。
- `--preview-method auto` 落到 latent2rgb 缩略图，对 latent 做小矩阵乘，不占权重显存。

## 4. 模型清单（全部落在 `models\` 对应子目录）

| 用途 | 文件 | 字节数 | 来源 | 状态 |
|---|---|---:|---|---|
| DiT | `diffusion_models/Sulphur-3-Q4_K_M.gguf` | 11,564,180,576 | `Abiray/Sulphur-3-GGUF`（hf-mirror） | 已就位 |
| TE | `text_encoders/qwen3-vl-4b-heretic-Q4_K_M.gguf` | 2,497,281,696 | plan1 复制 | 已就位 |
| 视觉塔 | `text_encoders/qwen3-vl-4b-heretic.mmproj-f16.gguf` | 836,180,704 | plan1 复制 | 已就位 |
| 投影矩阵 | `clip_projections/mmh3-4b-ClipProj-v3.1.safetensors` | 26,256,128 | plan1 复制 | 已就位 |
| 视频 VAE | `vae/minimax_h3_video_vae_int8_convrot.safetensors` | 2,811,065,184 | `Comfy-Org/MiniMax-H3`（hf-mirror） | 已就位 |
| 音频 VAE | `vae/minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | plan1 复制 | 已就位 |
| 8B TE | `text_encoders/qwen3vl_8b_int8_convrot.safetensors` | 9,350,798,360 | plan3 复制 | 已就位 |
| 8B heretic TE | `text_encoders/qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors` | 10,979,853,342 | plan3 复制 | 已就位 |
| 8B 投影 | `clip_projections/mmh3-8b-ClipProj-v3.1.safetensors` | 41,990,896 | plan1 复制 | 已就位 |

**为什么不去 32B**：Sulphur 官方推荐 Qwen3-VL-32B（Q4 GGUF 14.6 GB / NVFP4 15.7 GB / INT8 27.1 GB），
24 GB 卡同时装 32B TE + 11.6 GB DiT 不可能。ClipProj 的 4B/8B 投影是本机唯一可行路径；
ClipProj v3.1 基准（297 次语音 + 405 次图像渲染）中 4B 与 8B 归一化后「分不开」。

## 5. 自定义节点

| 节点 | 来源 | 用途 |
|---|---|---|
| `ComfyUI-GGUF` | plan3（city96 原版，`6ea2651`） | `UnetLoaderGGUF`，读 Abiray 的 city96 格式 GGUF |
| `ComfyUI-ClipProj` | plan3（从旧环境复制，`c01ba8f` v0.1.4） | `ClipProjLoader`，4B TE + 矩阵投影到 32B 条件空间 |
| `ComfyUI-ForceUnloadBeforeDecode` | plan1 复制 | 采样后 / 解码前两段清场 |

**4B GGUF 必须拆成两段加载**：`ClipProjLoader` 用的是原生 `folder_paths`，看不到 `.gguf`
（API 实测 `clip_name` 列表为空）。脚本已改成 `CLIPLoaderGGUF`（读 4B GGUF）→ `ClipProjApply`（套 4B 矩阵）。

**已修的节点 bug**：4B 编码器走 `Qwen3_4B` 类（`llama.py`），没有 `preprocess_embed`；
`clipproj_nodes.py:202` 的 `install_video_blocks` 原先直接取该属性，T2V 首测报
`AttributeError: 'Qwen3_4B' object has no attribute 'preprocess_embed'`。
已改为 `getattr(tr, "preprocess_embed", None)`，缺失时跳过视频块 patch。
`shortcut: 4B 纯 T2V 不产生 image embed；I2V/R2V 需换 8B (boogu) 编码器`。

## 6. 脚本改动（`bat\gen_sulphur.py`）

从 `plan\bat\multisegment\gen_h3_multisegment.py` 复制，只改 3 处，其余逻辑（分段、
首帧续接、seed、`/free`）原样保留：

| 位置 | 原值 | 新值 |
|---|---|---|
| `GGUF_UNET` | `minimax_h3_fl2va_pruned-Q4_K_M.gguf` | `Sulphur-3-Q4_K_M.gguf` |
| `VIDEO_VAE` | `minimax_h3_video_vae_fp16.safetensors` | `minimax_h3_video_vae_int8_convrot.safetensors` |
| 节点 2 | `CCTechClipProjLoader`（3 输入） | `CLIPLoaderGGUF` + `ClipProjApply`（两段，见 §5） |

采样参数不变：`simple` / 20 步 / `res_multistep` / cfg 1.0（BasicGuider 隐含）。
帧数 `max(5, round(秒×24))` 后对齐 `17k+5`，20 s → 481 帧（静默吸附，不报错）。

## 7. 省显存账

| 阶段 | 占用 | 依据 |
|---|---|---|
| 编码 | 4B TE ~3.6 GB + 矩阵 25 MB | plan1 §11.4 T1 实测 |
| 采样 | DiT Q4_K_M ~11.1 GB + 激活 | plan1 §11.10.7：`11186.65 MB loaded` |
| 解码 | 视频 VAE int8 2.81 GB + 音频 605 MB | 官方文件大小；`ForceUnloadBeforeDecode` 在解码前卸 DiT |

plan1 在 11.42 GB DiT 上跑通 480P/124 帧/20 步（370.6 s），Sulphur Q4_K_M 只多 0.18 GB，
可把 plan1 的显存与耗时实测当基线。

## 8. 未验证 / 风险

1. **step0 卸载已测（见 §9）**：显存确实释放，但 124 帧档净亏 15.2 s；只在接近显存墙的长片才值。
2. **Sulphur + Turbo LoRA 的二次蒸馏损失**未测。官方支持，但 Sulphur 团队自述
   「retraining a finished, CFG-distilled model was significantly harder」。
3. **20 s = 481 帧**在官方训练范围（124–362）之外；plan1 历史值 2391 s 是旧栈数据。
4. **720P 与 ≥209 帧**未实测；表里的耗时全是外推（见 §9）。
5. **4 张 UI 工作流**由 `make_workflows.py` 生成，结构已本地校验，但尚未逐张拖进 Desktop 实点。

---

## 9. 首测、step0 A/B 与工作流资产（2026-11-26）

### 9.1 首测

| 项 | 值 |
|---|---|
| 配置 | 864×480 / 124 帧 / 20 步 / `simple` / `res_multistep` / cfg 1.0 / seed `3538674239439636468` |
| 耗时 | **315.3 s**（plan1 同参数 370.6 s，快 15%） |
| 产物 | `h3_multisegment_3538674239439636468.mp4`，用户目视确认正常 |
| 环境 | Comfy Desktop 0.46.3，argv 已确认 5 条启动参数全在 |

首测前修了三处：`CLIPLoaderGGUF` + `ClipProjApply`（4B GGUF 绕路）、
`install_video_blocks` 的 `getattr` 兜底（4B 无 `preprocess_embed`）、ffmpeg 9.0.2 → 9.1。

### 9.2 step0 卸 DiT 的 A/B

钩子来自 plan3 的无预览版 `step0_free.py`（只 hook `unload_all_models` + `soft_empty_cache`）。

| 组 | 钩子 | 同 seed 耗时 | 现象 |
|---|---|---:|---|
| A | 无 | 315.3 s | 基线 |
| B | 装 | 330.5 s | 日志 `step0-free: unloaded models before step 1`，显存确实释放，慢 15.2 s（4.8%） |

**结论**：plan4 的 DiT 能卸载后搬回（city96 加载器不传 `disable_dynamic`，走默认 dynamic），
所以不像 plan3 那样卡死；但 124 帧档 headroom 本就够，卸载净亏 15 s。
它的价值只在接近显存墙的长片——不卸会掉进每步重搬权重的慢车道（×3 起步）。
钩子当前已装，`step0_free.py --revert` 可回快档。

### 9.3 工作流与脚本资产

| 目录 | 内容 |
|---|---|
| `API_workflows/` | 12 条 `/prompt` inner graph：4 任务 × 3 编码器档 |
| `workflows/` | 同名 12 张 UI 图，可拖进 Desktop |
| `tools/make_workflows.py` | 读 `/object_info` 生成上述 24 个 JSON（需 ComfyUI 在线） |
| `tools/migrate_8b.py` | 从 plan1 移植 8 个 8B 脚本的一次性工具 |
| `bat/run_workflow.py` | 通用提交器，读任一 API 图，支持 12 种组合 |
| `bat/gen_sulphur.py` | 多段生成（首测脚本，4B 档） |
| `bat/gen_h3_{multisegment,ref2va,scenes,scenes_ref}-8b*.py` | 8 个 8B / 8B-heretic 脚本 |
| `bat/gen_extract_frames.py` / `gen_h3_qc_frames.py` / `free_vram.py` | 从 plan1 复制，ffmpeg 路径已修 9.1 |

4 条任务与原生节点：t2v 纯提示词；i2v 挂 `LoadImage → first_frame`；
flf2v 挂首尾两帧；ref2v 挂 `MiniMaxH3AddGuide(frame_idx=0, vae, image)`。
三档编码器：4B 用 `CLIPLoaderGGUF`（GGUF），8B / 8B-heretic 用 `CLIPLoader`（int8 safetensors, boogu），
都接 `ClipProjApply`。8B 选 plan3 的 int8_convrot 版而非 plan1 的 fp8 版——后者 staged 16,721 MB 超显存。
ref2va 脚本的两个 DiT 常量都指向主权重：官方 `s3_ref2va` 标注 not trained。

### 9.4 时长与耗时外推（除 124 帧外均为预测）

依据：plan4 的 315.3 s 基准、帧数指数 c≈1.484（plan1 §11.10.5）、
像素指数 b≈1.144（下界）、plan3 §7.8 的显存墙实测（plan4 DiT 比 HyperFlow 大 2.2 GB，墙只会更早）。

| 分辨率 | 帧数 | 视频时长 | 预计墙钟 | 判断 |
|---|---:|---:|---:|---|
| 864×480 | 124 | 5.17 s | 5.3 min（实测） | 稳 |
| 864×480 | 209 | 8.70 s | ~11 min | 推算稳 |
| 864×480 | 294 | 12.25 s | ~18 min | 上限候选 |
| 864×480 | 345 | 14.38 s | ~23 min | 大概率跨墙 |
| 1280×720 | 124 | 5.17 s | ~13 min | 稳 |
| 1280×720 | 158 | 6.58 s | ~19 min | 边界 |
| 1280×720 | 243 | 10.13 s | ~28 min+ | 跨墙 |

跨墙判据是 s/it 与 `Model Initializing` 耗时（×3 起步），不是 `vram_free`（plan3 那档还剩 8.84 GB）。
要 20 s 走脚本的 4×5 s 分段（约 21 min），别单段 481 帧。
