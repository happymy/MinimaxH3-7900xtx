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
| DiT | `diffusion_models/Sulphur-3-Q4_K_M.gguf` | 11,564,180,576 | `Abiray/Sulphur-3-GGUF`（hf-mirror） | Aria2 下载中 |
| TE | `text_encoders/qwen3-vl-4b-heretic-Q4_K_M.gguf` | 2,497,281,696 | plan1 复制 | 已就位 |
| 视觉塔 | `text_encoders/qwen3-vl-4b-heretic.mmproj-f16.gguf` | 836,180,704 | plan1 复制 | 已就位 |
| 投影矩阵 | `clip_projections/mmh3-4b-ClipProj-v3.1.safetensors` | 26,256,128 | plan1 复制 | 已就位 |
| 视频 VAE | `vae/minimax_h3_video_vae_int8_convrot.safetensors` | ~2.81 GB | `Comfy-Org/MiniMax-H3`（hf-mirror） | Aria2 下载中 |
| 音频 VAE | `vae/minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | plan1 复制 | 已就位 |

**为什么不去 32B**：Sulphur 官方推荐 Qwen3-VL-32B（Q4 GGUF 14.6 GB / NVFP4 15.7 GB / INT8 27.1 GB），
24 GB 卡同时装 32B TE + 11.6 GB DiT 不可能。ClipProj 的 4B/8B 投影是本机唯一可行路径；
ClipProj v3.1 基准（297 次语音 + 405 次图像渲染）中 4B 与 8B 归一化后「分不开」。

## 5. 自定义节点

| 节点 | 来源 | 用途 |
|---|---|---|
| `ComfyUI-GGUF` | plan3（city96 原版，`6ea2651`） | `UnetLoaderGGUF`，读 Abiray 的 city96 格式 GGUF |
| `ComfyUI-ClipProj` | plan3（从旧环境复制，`c01ba8f` v0.1.4） | `ClipProjLoader`，4B TE + 矩阵投影到 32B 条件空间 |
| `ComfyUI-ForceUnloadBeforeDecode` | plan1 复制 | 采样后 / 解码前两段清场 |

`ClipProjLoader` 新增的两个输入：`device='cuda:0'`（`gpu_devices()` 在 ROCm 下返回 `cuda:0`）、
`mode='dynamic'`（省显存档，可选 `resident` / `streaming`）。

## 6. 脚本改动（`bat\gen_sulphur.py`）

从 `plan\bat\multisegment\gen_h3_multisegment.py` 复制，只改 3 处，其余逻辑（分段、
首帧续接、seed、`/free`）原样保留：

| 位置 | 原值 | 新值 |
|---|---|---|
| `GGUF_UNET` | `minimax_h3_fl2va_pruned-Q4_K_M.gguf` | `Sulphur-3-Q4_K_M.gguf` |
| `VIDEO_VAE` | `minimax_h3_video_vae_fp16.safetensors` | `minimax_h3_video_vae_int8_convrot.safetensors` |
| 节点 2 | `CCTechClipProjLoader`（3 输入） | `ClipProjLoader`（5 输入，加 `device` / `mode`） |

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

1. **step0 卸载未移植**。新版 `--preview-method auto` 是 latent2rgb，不调用 `vae.decode()`，
   不会触发 plan1 那种 `free_memory` → 卸 DiT。plan3 §7.5 实测该钩子在静态 GGUF 上会让下一步跑 CPU
   （80 s 不走一步），所以不盲目移植。长片防爆显存需单独评估。
2. **Sulphur + Turbo LoRA 的二次蒸馏损失**未测。官方支持，但 Sulphur 团队自述
   「retraining a finished, CFG-distilled model was significantly harder」。
3. **city96 GGUF 加载器 + 0.46.3 内核 + Sulphur 权重**未用 Desktop 实跑。
   命令行启动曾确认三个节点中 `ComfyUI-GGUF` 因缺 `gguf` 包导入失败，已装 0.19.0 修复；
   但尚未在 Desktop 下复验，也未提交过 `/prompt`。
4. **20 s = 481 帧**在官方训练范围（124–362）之外；plan1 历史值 2391 s 是旧栈数据。
5. comfy-kitchen / comfy-aimdo 实际版本以启动日志为准，manifest 是基线声明。
