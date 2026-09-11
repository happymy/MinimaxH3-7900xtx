# ComfyUI MiniMax-H3 从零搭建手册（AMD RX 7900 XTX / 24GB / Windows）

> 基于本机（2026-09-09）完整验证过的配置与结论编写。照此执行即可复现一套可用的
> T2V / I2V / R2V 迷你视频生成环境。所有 URL 为已可直接访问的镜像地址。
> 未验证项均有明确标注（⚠️需实测）。

---

## 0. 前提与预期

| 项 | 要求 |
|---|---|
| GPU | AMD RX 7900 XTX 24GB（或等效 24GB ROCm 卡） |
| 系统 RAM | ≥ 31GB（本机 31.9GB 验证） |
| OS | Windows（便携版 + ROCm torch 栈） |
| 产出规格 | 480p 视频 + 音频；**5s（124 帧）为绝对甜点档** |
| 性能预期 | 480P / 10s / 20 步 / 长提示词 ≈ 40–45 分钟；相同条件比最初快一倍 |
| 显存纪律 | 任意时刻只驻留一个「大件」（编码器 / 扩散模型 / VAE），严格防 swap |

**最终参数定稿（已实测，直接用）**
- 分辨率：480p（864×480）
- 时长：**5s 日常主力**；10s 备用（显存逼近红线，耗时 ~3x，仅需长时长时用）
- steps：**10 或 12**（官方模板默认 12；10 步 vs 20 步肉眼几乎无差，差异仅与提示词复杂程度相关）
- cfg：**1.0**（H3 是蒸馏模型，>1.0 可能直接中止，勿改大）
- sampler：`res_multistep`，scheduler：`simple`

---

## 1. 架构决策（为什么是这个组合）

MiniMax H3 官方用 Qwen3-VL-**32B** 做文本编码器，官方 safetensors 是 **NVFP4/AWQ（Blackwell 专属，AMD 不可用）**，
且 32B 与扩散模型在 24GB 下同驻必溢出。因此：

**采用 ClipProj 路线 = 4B 编码器 + 学习好的线性投影，把 4B 条件映射到 32B 条件空间：**
```
cond = ((h - mean_in) / std_in) @ W * std_out + mean_out
```

- 编码器：`qwen3-vl-4b-heretic-Q4_K_M.gguf`（文本塔）+ 配套 mmproj（视觉塔）
- 投影矩阵：`mmh3-4b-ClipProj-v3.1.safetensors`
- 实现：CCTech Suite 内置 `ClipProjLoader` 单节点（一个节点 = 加载 GGUF 文本塔 + 应用投影，输出标准 `CLIP`）
- 32B 路线整体排除（提示词若需更长/更复杂语义再考虑，见排雷 R6，但 24GB 余量很小）

---

## 2. 安装 ComfyUI（便携版）

1. 下载官方 ComfyUI Windows 便携版并解压（目标目录如 `D:\localAI\ComfyUI-last`）。
2. **ROCm 后端**（本机验证：`torch 2.9.1+rocm7.2.1` / HIP 7.2.53211，识别为 AMD RX 7900 XTX）：
   ```
   python_embeded\python.exe -m pip install torch==2.9.1+rocm7.2.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm7.2.1 py-torch-extra-index-url ...
   ```
   ⚠️ **安装命令未以文档形式留存，重装时以 PyTorch 官网 ROCm 安装页为准**（本机为已装状态）。
3. 校验：启动一次，日志确认 `Recognized AMD device ... RX 7900 XTX ... ROCm`。

---

## 3. 自定义节点：CCTech Suite（必需）

- 仓库：`github.com/molbal/ComfyUI-GGUF` → 放入 `ComfyUI\custom_nodes\ComfyUI-GGUF-Loader\`
- 提供：`UnetLoaderGGUF`（扩散模型）、`CLIPLoaderGGUF`、**`ClipProjLoader`**（`nodes/extra.py:74`，=
  `CLIPLoaderGGUF` 子类，一次性「加载 GGUF 文本塔 + 应用投影矩阵」，内置 MiniMax H3 支持）、`models\` 下
  Molbal 官方 t2v/i2v/ref2v 工作流模板。
- 纯 torch + `gguf` 包解包（**无 llama.cpp**）。

### ⚠️ 安装后必做修复（否则整包被 ComfyUI 静默跳过）
CCTech import 链 `krea2.py → vendor/depth_anything_v2.py` 硬依赖 `cv2`，缺失时整个包被跳过，
前端报「缺失节点包 ComfyUI-GGUF」。修复：
```
python_embeded\python.exe -m pip install opencv-python-headless -i https://mirrors.aliyun.com/pypi/simple/
```
> 清华源对该 wheel 返回 403，必须用阿里云源。装完重启，日志应见 `[CCTech Suite]: Activated 73 GGUF loader nodes`。

### 不要装的东西
- ❌ 独立 `ComfyUI-ClipProj`（nicolab28）：与 CCTech 内置 `ClipProjLoader` 同名冲突，CCTech 已内置同源实现
- ❌ `ComfyUI-MiniMaxH3-Cache`：全局 monkey-patch 会破坏 H3 生成，官方 Wiki 亦警告
- ❌ Optimization Suite 类 NV 优化节点：Blackwell 专属，AMD 无效

---

## 4. 模型下载清单（全部就位后无需再补）

镜像规则：HuggingFace 一律 `hf-mirror.com`，下载走 Aria2UI 多线程。

| 文件 | 大小 | 目标目录 | 来源 |
|---|---|---|---|
| `minimax_h3_fl2va_pruned-Q4_K_M.gguf` | 10.64GB | `models\diffusion_models\` | `hf-mirror.com/molbal/MiniMax-H3-GGUF`（旧版命名；官方现名 fp8_Q4_0，见排雷 R7） |
| `ref2va_pruned-Q4_K_M.gguf` | ~10.6GB | `models\diffusion_models\` | 同上 |
| `qwen3-vl-4b-heretic-Q4_K_M.gguf` | ~2.3GB | `models\text_encoders\` | `hf-mirror.com/matrixportalx/Qwen3-VL-4B-Instruct-heretic-Q4_K_M-GGUF` |
| `qwen3-vl-4b-heretic.mmproj-f16.gguf` | 836MB | `models\text_encoders\` | `hf-mirror.com/mradermacher/Qwen3-VL-4B-Instruct-heretic-GGUF`（matrixportalx 版无 mmproj，**必须 mradermacher**） |
| `mmh3-4b-ClipProj-v3.1.safetensors` | 25.0MB | `models\clip_projections\` | `hf-mirror.com/NicoLab28/ClipProj-MiniMax-H3` |
| `minimax_h3_video_vae_fp16.safetensors` | 5.2GB | `models\vae\` | `hf-mirror.com/molbal/MiniMax-H3-GGUF`（或 H3 官方） |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.6GB | `models\vae\` | 同上 |

关键说明：
- **mmproj 命名必须满足 loader 合并规则**：文本塔 stem（去量化后缀）`qwen3-vl-4b-heretic` 的 squash 名
  `qwen3vl4bheretic` 必须被 mmproj 文件名 squash 包含 → mmproj 命名为
  `qwen3-vl-4b-heretic.mmproj-f16.gguf` ✓。否则节点 131 报
  `loaded as Qwen3_4B, not as a Qwen3-VL text encoder`。
- 若 `UnetLoaderGGUF` 读不到 `diffusion_models\` 的 gguf → 复制一份到 `models\unet\`。
- `.pt` 投影文件一律不用（pickle 可执行代码风险）；备选投影矩阵（v3-mlp / celeb 人名）见排雷 R7。
- 扩散模型可备 `fl2va_pruned_fp8_Q4_0`（官方现版，10.60GB）：实测与 Q4_K_M 速度几乎相同，**VRAM 反而略高**，仅留档。

---

## 5. 工作流（Molbal 模板改编，共两处替换）

### 选用模板
`custom_nodes\ComfyUI-GGUF-Loader\models\`（= `github.com/molbal/ComfyUI-GGUF/workflows`）的
t2v / i2v / ref2v 模板。**0.34 全部节点内置**，只需替换两处，其余节点
（`MiniMaxH3ImageToVideo`/`MiniMaxH3ReferenceToVideo`、`ResolutionSelector`、
`ComfyMathExpression`、`KSamplerSelect`/`BasicScheduler`/`BasicGuider`/`SamplerCustomAdvanced`/`RandomNoise`、
`VAEDecode`/`VAEDecodeAudio`、`CreateVideo`/`SaveVideo`）一律不动。

### 两处替换（三套工作流通用）
| 原节点 | 替换为 |
|---|---|
| `UnetLoaderGGUFDynamicVRAM` / `CLIPLoader` | CCTech `UnetLoaderGGUF`，`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`（R2V 用 ref2va） |
| `CLIPLoader` | CCTech `ClipProjLoader`：`[qwen3-vl-4b-heretic-Q4_K_M.gguf, type=krea2, mmh3-4b-ClipProj-v3.1.safetensors]` |

`type=krea2` = 4B/2560 维。输出标准 `CLIP`，下游连线不动。

### 三段卸载骨架（顺序执行即自动清场，无需手动卸载节点）
```
[编码段]  ClipProjLoader → MiniMaxH3*ToVideo(clip 输入)
          ↓ 加载采样模型时 ComfyUI free_memory 自动踢掉最旧的编码器
[采样段]  UnetLoaderGGUF → latent 采样（模型 + 图像/音频 latent）
          ↓ 加载 VAE 时自动踢掉扩散模型
[解码段]  video VAE + audio VAE → VAEDecode / VAEDecodeAudio
```

### 素材节点（须换成自有文件）
- i2v：`LoadImage` ×2（首/末帧图），模板默认示例图不存在
- ref2v：`LoadImage` + `LoadVideo` + `LoadAudio`（参考图/视频/音频）

---

## 6. 启动脚本（含两条关键参数）

`run_amd_gpu.bat`（已备份为 `run_amd_gpu.bat.bak`）：

```bat
@echo off

set PYTHON=.\python_embeded\python.exe
set TARGET=ComfyUI\main.py

%PYTHON% -s %TARGET% --windows-standalone-build --enable-manager --disable-pinned-memory --fp16-intermediates
pause
```

两个参数的实测意义：
- `--disable-pinned-memory`：Windows 默认锁死 40% 系统 RAM（31.9GB→锁 12.8GB）供权重 offload DMA，
  禁用它把内存归还给系统调度 → **10s 不再爆显存**（⚠️ 注意：仅降低单次内存消耗、不易触发崩溃，
  **内存耗尽时仍会 OOM 崩溃**，非根治）。
- `--fp16-intermediates`：节点间中间张量用 fp16（Experimental），内存压力降低。

就记住：**只改这两个 + 默认参数；不要上 `--lowvram/--novram`**（会主动把权重卸到系统内存，徒增 swap 风险）。

可选 `--enable-dynamic-vram` 变体（`run_amd_gpu_enable_dynamic_vram.bat`）——ROCm 支持状态未验证，实验性质，一次一测。

---

## 7. 冒烟验收顺序

1. **T2V**：fl2va + 5s + 12 步 + cfg 1.0 + 480p，先跑通。预期全程恒定 ~26.6s/it，总耗时约 9–10 分钟。
2. **I2V**：加首帧，验证 GGUF 编码器 + mmproj 视觉路径（失败则换 bf16 编码器，见排雷 R6）。
3. **R2V**：ref2va + 参考图/视频/音频。
4. 全程任务管理器观察：GPU 显存三段低峰，系统「已提交内存」不趋近上限（无 swap 迹象）。
5. 参考基准：5s 一轮 ≈ 9.5 分钟（采样 8:47 + 解码 ~30s）；10s / 20 步 / 长提示词 ≈ 40–45 分钟。

---

## 8. 排雷清单（全部实测/核实过）

| # | 坑 | 处置 |
|---|---|---|
| 1 | CCTech 整包被跳过：`krea2.py→vendor/depth_anything_v2.py` 缺 `cv2` | 阿里云源装 `opencv-python-headless`（§3） |
| 2 | 节点 131 报 `loaded as Qwen3_4B` | 配齐同源 mmproj 并满足命名合并规则（§4） |
| 3 | 10s 爆显存（过去式） | 加 `--disable-pinned-memory --fp16-intermediates`（§6）；10s 仍极限，勿作日常 |
| 4 | 内存耗尽仍崩溃 | 两条参数只是降低消耗，防 swap 靠「单驻留纪律」+ 系统 RAM 保余量 |
| 5 | `--use-sage-attention` | AMD 无支持 + H3 全局 sage 出纯噪声（issue #15263），别试 |
| 6 | 引用图/视频 QA 失败（R2V） | 换官方 bf16 编码器 `qwen3vl_4b_fp8_scaled.safetensors`（ROCm 需验证）或 heretic bf16 8.3GB；fps8 保守用 bf16 |
| 7 | 量化选择 | Q4_K_M 与 fp8_Q4_0 速度几乎相同、Q4 VRAM 略低 → **留 Q4_K_M**；K-quant 警告（H3 隐藏宽 2688 不整除 256）本机未显现 |
| 8 | 解码抖动（DiT + 两 VAE 共驻，issue #15484） | 靠 §5 顺序卸载；前缀 `ForceUnloadBeforeDecode`（采样前/解码前各一个）可选，判解码前卸载有效、采样前卸载收益≈0 |
| 9 | U16G / 大体积量化 | 15GB 权重对 24GB 更挤，否决不试 |
| 10 | 投影 `.pt` 文件 | pickle 可执行代码，只用一个 `.safetensors` |

---

## 9. 备选/后续可挖（均未验证，勿优先投入）

- **官方 turbo LoRA**（`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16`，8 步提速）：面向原生 bf16
  checkpoint，GGUF 路径（`UnetLoaderGGUF` + LoRA）兼容性未验证。
- 分辨率档：「480p」已是减负常见选择；官方原生 canvas 为 1344×768，更大分辨率需换算显存预算。
- steps 25（官方建议「提高步数提升运动质量」）：与 10 步实测结论并存，属步数档位取舍。

---

## 10. 结论（本机定稿）

- **5s / 480p / 10–12 步 / cfg 1.0 是可长期使用的甜点档**。
- 10s 仅偶发需要时长时用（显存极限、耗时约 40–45 分钟 vs 5s 约 10 分钟）。
- 相比最初「480P 10s 20 步长提示词」配置，当前同条件生成时间**几乎减半**，已到本机优化极致。
- 想再突破 = 换更大显存 / 原生（非 GGUF）+ SageAttention / 32B 编码器，均超出本 24GB AMD 方案范围。
```