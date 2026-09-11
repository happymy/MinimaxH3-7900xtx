# ComfyUI MiniMax H3 优化方案（AMD RX 7900 XTX / 24GB）

> 状态：**已收敛、优化到本机极致（模型全齐、工作流已改编、三套跑通、防抖动两段卸载已并入）**。目标：三套工作流（T2V / I2V / R2V）在本机跑通，
> 严格不触发系统 swap，模型「用后即卸载」。全部结论基于已核实的本地环境 + 官方/社区文档。
>
> **最终结论（2026-09-09 用户实测）**：480p 下 **5s 为绝对甜点档位**；同样条件（480P / 10s / 20 步 / 长提示词）下当前生成时间 **40–45 分钟，比最初同条件几乎短了一半**；10 步与 20 步输出区别不明显（与提示词相关）。10s 可跑但显存极限，仅偶发需要时长时使用。**
>
> 2026-09 路线变更（本次更新）：
> - **弃用** leejet 仓库 + nicolab28 独立 `ComfyUI-ClipProj` 节点；
> - **改用** GGUF 三件套（模型来自 `molbal/MiniMax-H3-GGUF`，工作流模板来自 Molbal `ComfyUI-GGUF` = 现 CCTech `ComfyUI-GGUF-Loader`）+ CCTech 内置 `CCTechClipProjLoader`；
> - 32B NVFP4/AWQ safetensors CLIP（Blackwell 格式，AMD 不可用）换成 4B GGUF + 投影矩阵。
> - **2026-09-09 新增**：co-residency 抖动根因确认（issue Comfy-Org/ComfyUI#15484 / #15453）+ 自建 `ForceUnloadBeforeDecode`
>   卸载节点，采样前/解码前两段手动清场（详见 §9 与 §10.4）。

---

## 1. 环境现状（已核实）

| 项 | 值 |
|---|---|
| ComfyUI | 0.34.0（`ComfyUI_windows_portable`） |
| 推理后端 | `torch 2.9.1+rocm7.2.1` / HIP 7.2.53211，识别为 AMD RX 7900 XTX（ROCm，非 CUDA） |
| 启动脚本 | `run_amd_gpu.bat`、`run_amd_gpu_enable_dynamic_vram.bat`（均存在） |
| GGUF 加载器 | **CCTech Suite**（`ComfyUI-GGUF-Loader` v2.16.7）已装，注册 `UnetLoaderGGUF` / `CLIPLoaderGGUF` / **`CCTechClipProjLoader`**（`nodes/extra.py:74`，CLIPLoaderGGUF 子类，可一次性「加载 GGUF 文本塔 + 应用投影矩阵」，输出 CLIP），纯 torch+`gguf` 包解包（无 llama.cpp），内置 MiniMax H3 支持。⚠️ **已修复**：import 链上的 `krea2.py→vendor/depth_anything_v2.py` 缺 `cv2` 曾导致整包被 ComfyUI 跳过，已向 `python_embeded` 装 `opencv-python-headless`（阿里云源），现 73 节点正常注册 |
| 编码器 | `text_encoders/qwen3-vl-4b-heretic-Q4_K_M.gguf`（~2.3GB 文本塔）+ 配套 `text_encoders/qwen3-vl-4b-heretic.mmproj-f16.gguf`（836MB 视觉塔，CCTech loader 自动合并，详见 §10.3） |
| 扩散模型 | `diffusion_models/minimax_h3_fl2va_pruned-Q4_K_M.gguf`、`ref2va_pruned-Q4_K_M.gguf`（均已在 `diffusion_models\`，共 ~22.8GB 十进制；**实测 `UnetLoaderGGUF` 直接读得到，无需复制到 `models\unet\`**） |
| 投影矩阵 | `clip_projections/mmh3-4b-ClipProj-v3.1.safetensors`（25.0MB） |
| VAE | `vae/minimax_h3_video_vae_fp16.safetensors`（5.2GB）、`vae/minimax_h3_audio_vae_fp32.safetensors`（0.6GB） |

**三套工作流模型/VAE/矩阵全部就位，无需再补任何下载。**

---

## 2. 核心架构决策（关键）

MiniMax H3 官方用 **Qwen3-VL-32B** 做文本编码器（官方 safetensors 为 NVFP4/AWQ 量化，
Blackwell 专属格式，**AMD/ROCm 不可用**）。本机 24GB 下与扩散模型同驻必溢出 → **不用 32B 路线。**

**采用社区已验证的 ClipProj 路线**：用已有 4B 编码器 + 学习好的线性投影映射到 32B 条件空间：

```
cond = ((h - mean_in) / std_in) @ W * std_out + mean_out
```

- 手头 `qwen3-vl-4b-heretic-Q4_K_M.gguf` 正好作 4B 编码器（同 tokenizer，位置一一对应）。
- **投影矩阵**：`clip_projections/mmh3-4b-ClipProj-v3.1.safetensors`（25MB，4B=2560 维与 v3.1 矩阵吻合）。
- **实现载体 = CCTech `CCTechClipProjLoader` 单节点**（官方 32B 三参数 `[clip, type, device]` 替换为
  `[clip_name, type, projection]`，`type=krea2` 表示 4B/2560 维）：一个节点完成「加载 GGUF 文本塔 +
  应用投影」，输出仍是标准 `CLIP` 对象，下游 H3 节点连接完全不动。
- **不使用 nicolab28 独立 `ComfyUI-ClipProj`**：CCTech 已内置等价实现（`vendor/clipproj.py`，从
  nicolab28 移植）。本机该目录仍在（含调试脚本），三套工作流全部走 CCTech `CCTechClipProjLoader`，无命名冲突。
- 编码阶段结束后把 4B 编码器卸载回 RAM，采样阶段整张卡给扩散模型。
- 投影矩阵对编码器量化鲁棒：校准于 bf16，可直接用于 abliterated/fp8/int8 变体（GGUF Q4 未由作者实测，列为风险 R4）。

---

## 3. 显存预算（分阶段，各自峰值 ≤ 24GB）

| 阶段 | 驻留 | 峰值估算 | 达标 |
|---|---|---|---|
| ① prompt 编码（T2V） | 4B 编码器 ~2.5GB + 激活 | ≤ 4GB | ✅ |
| ② 采样（T2V/I2V） | fl2va 11.4GB + 图像/音频激活 | ~14–16GB | ✅ |
| ② 采样（R2V） | ref2va 11.4GB + 引用 tokens 激活 | ~15–17GB | ✅ |
| ③ VAE decode | video VAE 5.2GB + audio VAE 0.6GB（卸载 UNet 后） | ≤ 10GB | ✅ |

关键纪律：**同一时刻只驻留一个「大件」**（编码器 / 扩散模型 / VAE）。核心 ComfyUI **没有** `Unload Model` 节点（已核实 execution.py / model_management.py），实际卸载靠两种内置机制：

1. **默认（NORMAL_VRAM）被动卸载**：每次 `load_models_gpu()` 前 `free_memory()` 按整张图所需显存检查，装不下时按 LRU 卸载最旧的模型。三阶段顺序执行时，加载采样模型会自动踢掉编码器、加载 VAE 会自动踢掉扩散模型——只要顺序跑就有保证。
2. **`--disable-smart-memory` 主动卸载**：该标志下每次 prompt 执行完毕调用 `unload_all_models()`（execution.py:836）清空全部驻留。代价：每次生成结束模型全部卸载、下次重新加载慢一点；适合「跑一把歇一把」的用法。

任何阶段之间不叠加即不会 OOM，也不会触底到 swap。

---

## 4. 需要补充的下载（共 2 项，已完成 ✅）

> 全部走 `hf-mirror.com` / GitHub 加速镜像 + Aria2UI 多线程，见全局加速规则。

### 4.1 fl2va 扩散模型（T2V/I2V 必需）— ✅ 已下载
- 仓库：`molbal/MiniMax-H3-GGUF`（GGUF 制作者本人，与 ref2va 同源同量化风格，pruned Q4_K_M，20B 参数下 Q4_K_M ≈ 11GB）
- 文件：`minimax_h3_fl2va_pruned-Q4_K_M.gguf`（+ `ref2va_pruned-Q4_K_M.gguf` 同批次下载）
- 已保存到：`ComfyUI_windows_portable\ComfyUI\models\diffusion_models\`
- ⚠️ 两个 gguf 目前在 `diffusion_models\`（= `unet\` 别称）。若 `UnetLoaderGGUF` 报找不到文件，复制一份到 `models\unet\` 即可。

### 4.2 投影矩阵（→ models\clip_projections\）— ✅ 已下载
- `mmh3-4b-ClipProj-v3.1.safetensors`（**25.0 MB**，ridge 线性，多语言语音更好）
  - `https://hf-mirror.com/NicoLab28/ClipProj-MiniMax-H3/resolve/main/mmh3-4b-ClipProj-v3.1.safetensors`
- 备选（质量数字更高，纯测量可辨，屏幕看不出）：`mmh3-4b-ClipProj-v3-mlp.safetensors`（带残差网络）
- 需要人物名渲染时再用 `mmh3-4b-ClipProj-celeb` 系列。
- `.pt` 旧文件一律不用（pickle 可执行代码）。

### ~~4.3 ClipProj 自定义节点~~ — 不再需要
- ~~git clone nicolab28/ComfyUI-ClipProj~~ → **改用 CCTech 内置 `CCTechClipProjLoader`**（`nodes/extra.py:74`），三套工作流均走它。
- CCTech `vendor/clipproj.py` 是从 nicolab28 仓库移植的同源实现。

### 4.4 （可选，未下载）官方 4B 编码器 safetensors
若后期发现 GGUF 编码器的 vision 引用图失败（风险 R4），补下 `fp8_scaled` 版：
- `https://hf-mirror.com/Comfy-Org/Krea-2/resolve/main/text_encoders/qwen3vl_4b_fp8_scaled.safetensors`（4.9GB，amd 的 fp8 需 ROCm 验证）
- 或 DreamFast heretic 的 `qwen3-vl-4b-heretic_int8.safetensors`（4.6GB）/ bf16（8.3GB，最稳）

---

## 5. 三套工作流（节点构成 + 加载卸载时序）

> 前置事实（ComfyUI 0.34 原生 H3）：扩散模型走 CCTech `UnetLoaderGGUF`；
> **编码器走 CCTech `CCTechClipProjLoader` 单节点**（= 加载 GGUF 文本塔 + 应用投影矩阵）；
> 引用图是编码器 vision 输出，混入 prompt 序列后一次性进入 DiT。

### 采用的模板：Molbal 官方三件套（已验证全 core）

`plan\molbal_workflows\final\` 改编自 Molbal 官方 workflows：
`github.com/molbal/ComfyUI-GGUF/tree/main/workflows`（该仓库现改名
`ChrisColeTech/ComfyUI-GGUF-Loader`）的 t2v/i2v/ref2v 模板。
**节点已逐一定位，0.34 全部内置**——仅两处替换（见下方各节），其余节点
（`MiniMaxH3ImageToVideo`/`MiniMaxH3ReferenceToVideo`、`ResolutionSelector`、
`ComfyMathExpression`(=core `MathExpressionNode`, nodes_math.py:70)、`VAELoader`×2、
`KSamplerSelect`/`BasicScheduler`/`BasicGuider`/`SamplerCustomAdvanced`/`RandomNoise`、
`VAEDecode`/`VAEDecodeAudio`、`CreateVideo`/`SaveVideo`、`MarkdownNote`）一律不动。

### 通用骨架（三段，逐段卸载）

```
[编码段]
  CCTechClipProjLoader(clip_name=heretic-4B.gguf, type=krea2, projection=mmh3-4b-ClipProj-v3.1.safetensors)
      └─> CLIP → MiniMaxH3ImageToVideo / MiniMaxH3ReferenceToVideo(的 clip 输入)
      （替代官方 qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors + CLIPLoader[minimax]，输出类型同为 CLIP，连线不动）
  ← 编码完成后不显式卸载：后续加载采样模型时，ComfyUI 的 free_memory 会自动把
    最旧的 4B 编码器踢出显存（顺序执行即有保证；无需也**没有**手动卸载节点）

[采样段]
  UnetLoaderGGUF(fl2va 或 ref2va .gguf)  → model
  MiniMax H3 联合 latent（图像 latent + 音频 latent，见下）+ cfg/step 采样 → latent_out
  ← 采样结束不手动卸载：下一步加载 VAE 时 free_memory 自动踢掉扩散模型

[解码段]
  VAELoader(video_vae_fp16) + VAELoader(audio_vae_fp32)
  → VAE Decode / Audio VAE Decode → 视频+立体声 输出
  全程只驻留 VAE，峰值 ≤ 10GB
```

> 素材节点（`LoadImage`/`LoadVideo`/`LoadAudio`）引用的是 Molbal 自带示例文件，本机无 →
> 需换自己的素材文件（i2v：首/末帧图×2；ref2v：参考图+参考视频+参考音频）。

### 5.1 T2V（用 fl2va）
- `plan\molbal_workflows\final\minimax_h3_t2v-gguf.json`：仅改两处——
  `UnetLoaderGGUFDynamicVRAM` → CCTech `UnetLoaderGGUF`，`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`；
  `CLIPLoader` → CCTech `CCTechClipProjLoader`，`[qwen3-vl-4b-heretic-Q4_K_M.gguf, krea2, mmh3-4b-ClipProj-v3.1.safetensors]`。
- cfg：H3 是蒸馏模型，**cfg=1.0 附近**（>1.0 可能直接中止，勿改大）。
- 纯文本 prompt（或 Molbal 模板自带三段式结构化 H3 prompt）。

### 5.2 I2V（用 fl2va + 首帧）
- `plan\molbal_workflows\final\minimax_h3_i2v-gguf.json`：同 §5.1 两处替换；`LoadImage`×2（图 114/141）默认
  `bg-cerritos-exterior-01.jpg` → 换自己的首/末帧图。
- fl2va 变体支持「文本 + 零/一/两帧」；`ResizeImageMaskNode`（core）自动缩到模型输入尺寸。
- **注意**：GGUF 编码器走 vision tower 需要 mmproj（**已安装**，见 §10.3）；官方 workflow 的 I2V 模板用的是
  官方 32B safetensors 编码器（自带 vision），换成 GGUF 4B 后引用图路径由 mmproj 视觉塔提供（见 R4）。

### 5.3 R2V（用 ref2va + 引用图/视频/音频）
- `plan\molbal_workflows\final\minimax_h3_ref2v-gguf.json`：同 §5.1 两处替换（unet 用 `ref2va_pruned-Q4_K_M.gguf`）；
  `LoadImage`〔149〕/`LoadVideo`〔156〕/`LoadAudio`〔153〕默认素材 → 换自己的。
- 引用路径同样依赖编码器 vision；GGUF 编码器下与 I2V 相同的失败退路。

---

## 6. 启动与防 swap

- 启动用现有 `run_amd_gpu.bat`（`--amdgpu` 或等效后端参数已在脚本内）。**不要**为提速上 `--lowvram/--novram`（会主动把权重卸载到系统内存，无谓增加 RAM 压力；本方案按阶段控制驻留已够）。若 ComfyUI 官方 0.34 在 ROCm 上 `--enable-dynamic-vram` 可用，则作为可选项实验（§8 R1）。
- **swap 红线**：Windows 页面文件仅在系统物理 RAM 耗尽时才触发。本方案峰值显存 ~17GB < 24GB，正常不会触底；避免同时开多浏览器/大程序占用 RAM，Ubuntu 说法不适用，本机主要防：ComfyUI 误把 VAE 留在显存 + 下一个大件叠加（靠 §5 的顺序执行 + free_memory 自动踢旧），以及系统整体 RAM 保持余量。
- **Windows 专属崩溃源**（ComfyUI-MiniMaxH3-Director 文档实证）：GGUF 权重是内存映射，**第二个不兼容模型直接叠在第一个上加载会崩 `0xC0000005`（访问冲突），而非干净的 OOM**。规避靠强制先后顺序（加载采样模型时编码器已被 free_memory 踢出、加载 VAE 时扩散模型已被踢出），绝不允许两个大件同时驻留触发叠加。

---

## 7. 执行清单（验收顺序）

- [x] 下载 §4.1 fl2va/ref2va + §4.3 矩阵（已完成，均已在本地）。
- [x] ClipProj 实现确认（改用 CCTech 内置 `CCTechClipProjLoader`，未用 nicolab28）。
- [x] 三套 Molbal 工作流改编完成 → `plan\molbal_workflows\final\`，JSON 已校验。
- [x] CCTech 包加载修复（缺 `cv2` → 装 `opencv-python-headless`）：T2V 导入无报错，节点 73/73 注册。
- [x] 编码器配套 mmproj 视觉塔安装（`qwen3-vl-4b-heretic.mmproj-f16.gguf` 入 `models\text_encoders\`，解决节点 131 报错，见 §10.3）。
- [x] 素材替换：i2v 首/末帧图、ref2v 参考图/视频/音频 → 已换自有文件。
- [x] 无需处理：`UnetLoaderGGUF` 实测直接读到 `diffusion_models\` 的 gguf。
- [x] **T2V 冒烟通过**：fl2va + 480P + cfg≈1.0 跑通；实测 480p 下 5s（124 帧）为甜点档。
- [x] I2V 跑通：首帧 + mmproj vision 路径正常。
- [x] R2V 跑通：ref2va + 引用图/视频。
- [x] 全程任务管理器观察：GPU 显存峰值曲线三段低峰，系统「已提交内存」不趋近上限（无 swap 迹象）。

---

## 8. 风险与备选

> ⚠️ 本方案沿用 4B+投影，点不开 §7「T2V/I2V/R2V」验收前的**对照组**（`<control:zero>` / `<control:identity>`）——Molbal 官方 workflow 没有这套控制条目的接线，且 CCTech `CCTechClipProjLoader` 的 `projection` 只能选本地矩阵文件、无内置 control 条目。改用 CCTech 后对照组不再可跑，有问题时直接以各任务冒烟为准。

| # | 风险 | 影响 | 处置 |
|---|---|---|---|
| R1 | `--enable-dynamic-vram` 在 ROCm/0.34 的支持状态未验证 | 可选项不可用 | 不影响主方案；仅作实验，一次一测 |
| R2 | 4B+投影路线（ClipProj 内核来自 nicolab28，作者仅实测 NVIDIA+Windows11）AMD/ROCm 未测 | 可能个别算子行为差异 | 先 T2V 冒烟；出问题抓堆栈回报 issue |
| R3 | `qwen3-vl-4b-heretic` 是 abliterated 版，作者实测对语料域宽有 -0.026~-0.034 的微小偏离（不是提升） | 可忽略 | 无需换回对齐版；仅说明它「不更好但不更差」 |
| R4 | **GGUF 编码器的 vision 路径曾被 ClipProj 未实测**；视觉塔已通过配套 mmproj 补齐（同样需要投影匹配，见 §10.3）。社区有「GGUF 编码器下引用**视频**失败、文本正常」的未证实报告（疑在 vision 塔而非投影）。引用**图**在 fl2va/ref2va 实测可用，但 W 仅校准文本位置，vision 位置被投出训练分布（README 明示） | I2V/R2V 引用图/视频可能异常 | 失败即切 §4.4 官方 fp8/bf16 编码器（Comfy 原生 CLIPLoader 路径）。R2V 若用 int8 编码器须 `resident` 模式 |
| R5 | fp8 在 ROCm 上的 matmul 速度/正确性未验证 | fp8 编码器效率未知 | 保守用 bf16（8.3GB，校准基准，最稳）；fp8 仅作提速实验 |
| R6 | 32B 路线被整体排除 | 长 prompt/复杂语义略弱于 32B | 如质量不达标再考虑 32B GGUF Q3 + 严格的编码-卸载-采样分离（24GB 可行但余量小） |
| R7 | **Molbal 官方 workflow 的 unet 是 fp8_Q8_CR（8bit，24GB 显存专用）**，本机改用 Q4_K_M 4bit | 纹理细节/长提示词质量略降；但 4bit 显存占用更低、24GB 卡跑更长时长反而更稳 | 优先本地已有 Q4_K_M；质量不达预期再下载 Molbal 的 fp8_Q8_CR 版 |

---

## 10. 故障排查记录

### 10.1 CCTech 包被跳过（前端报「缺失节点包 ComfyUI-GGUF」+「未知节点 CCTechClipProjLoader」）
- **现象**：T2V 工作流导入后前端提示缺失节点/缺失模型，而 CCTech 包明明装了。
- **根因**：`nodes/__init__.py` 的 import 链 `krea2.py → vendor/depth_anything_v2.py` 处
  `ModuleNotFoundError: No module named 'cv2'` → 整个包被 ComfyUI 静默跳过（只在日志留错误），
  前端因此看不到 `CCTechClipProjLoader`/`UnetLoaderGGUF` 等任何注册键。
- **修复**：`python_embeded\python.exe -m pip install opencv-python-headless -i https://mirrors.aliyun.com/pypi/simple/`（清华源对该 wheel 403，改阿里云）。
- **验证**：重启后日志 `[CCTech Suite]: Activated 73 GGUF loader nodes`，工作流加载无错。
- **教训**：CCTech 包 import 依赖链粗（深度模型/音频/音乐等一批 `nodes_*` 子模块硬 import），
  装不上任意传递依赖就会整包报废。

### 10.2 其余启动警告（均无害，不处理）
- `offload-arch failed`：安装目录残留 CI 打包机路径 `D:\a\ComfyUI\...` 导致该 exe 启动失败，纯历史残留。
- `SoX could not be found!`：系统缺 sox。仅音频/TTS 系节点（qwen_tts、music 等）需要，T2V/I2V/R2V 不含音频节点 → **不装**。
- `flash-attn is not installed`：已自动回退 PyTorch 手动 attention；ROCm 下官方 flash-attn 通常不可装，不处理。
- `triton not found`：Triton 后端不可用；`comfy_kitchen` 已回退 eager/HIP 后端。
- `matrix-nio missing`：ComfyUI-Manager 矩阵共享功能关闭，无关推理。

### 10.3 节点 131 `CCTechClipProjLoader` 报错 `loaded as Qwen3_4B, not as a Qwen3-VL text encoder`
- **现象**：T2V 工作流节点 131 报
  `qwen3-vl-4b-heretic-Q4_K_M.gguf loaded as Qwen3_4B, not as a Qwen3-VL text encoder, so the projection has nothing to read.`（`nodes/extra.py:193` guard — 报错源于外部投影矩阵，即「剪辑投影」）：
  CLIP 被识为 **Qwen3_4B**（`preprocess_embed` 缺失），krea2 投影矩阵无从附加。
- **根因**：`qwen3-vl-4b-heretic-Q4_K_M.gguf` 是纯文本塔 GGUF，`detect_arch`（`vendor/clipproj.py:232`）只读
  `token_embd.weight` 宽度查 `_ARCH_BY_DIM`，得 4B 却**无配套 mmproj** → 缺少 `model.visual.*` 视觉键 →
  comfy `detect_te_model` 归为 `Qwen3_4B`。CCTech guard（extra.py:189-197）检查的是「加载后模型类型」，不看工作流是否只用文本。
- **修复**：为文本塔 GGUF 配齐同源 mmproj（视觉塔），文件命名须满足 loader 自动合并规则
  （`gguf_mmproj_loader`，`squash_name(文本塔 stem) in squash_name(mmproj 文件名)`）：
  - 文本塔 stem（去量化后缀）= `qwen3-vl-4b-heretic` → squash=`qwen3vl4bheretic`；
  - 故 mmproj 重命名为 `qwen3-vl-4b-heretic.mmproj-f16.gguf`（squash=`qwen3vl4bhereticmmprojf16`，包含前者）✓。
  - 来源：`https://hf-mirror.com/mradermacher/Qwen3-VL-4B-Instruct-heretic-GGUF/tree/main`
    （文件 `Qwen3-VL-4B-Instruct-heretic.mmproj-f16.gguf`，字节数 836,180,704；`-Q8_0` 版为 453,974,752 B。
    matrixportalx 版无 mmproj，故从 mradermacher 取）。
  - 放入 `models\text_encoders\` 后重启 ComfyUI；日志应出现
    `Using mmproj '...mmproj-f16.gguf' for text encoder '...'...` 即合并成功。
- **结果**：编码器带视觉键 → comfy 归为 `QWEN3VL_4B` → guard 通过，节点 131 不再报错。

### 10.4 两轮 480p 实测：时长是采样瓶颈，卸载不是
- **背景**：`ComfyUI-ForceUnloadBeforeDecode` 节点（latent 透传 + `unload_all_models()`）已并入三套工作流，
  每阶段边界各一个（采样前 136/146/158 + 解码前 135/145/157）。同一份复杂 prompt，480p 两轮实测对比：
  - **① 10s（243 帧）**：采样被中断（>21 分钟没跑完 20 步）。H3 加载时 `usable 17087.92 MB`。
  - **② 5s（124 帧）**：**20/20 步 8:47 = 26.60s/it 全程恒定**，采样后全部 46.7s 收工（解码 ~30s）。
    总耗时 573.67s，H3 加载时 `usable 20106.19 MB`。
- **结论一（采纳）**：**解码前卸载非常有效**。卸掉 DiT（11185.54MB）后 VideoVAE（4966MB）+ AudioVAE（577MB）
  独享显存，解码 ~30s 快收——此前 DiT + 两 VAE 共驻即 issue #15484 co-residency 抖动。
- **结论二（否决采样前卸载的预期）**：**采样前卸载几乎无效**。采样是**计算受限**（20B Q4 + ROCm 无
  flash-attn，26.6s/it 即物理上限，进度条无抖动），不是显存受限；5s 时 headroom ~9GB 本就不缺，
  TE 只占 3613.93MB，卸不卸无感。10s 慢的真正原因 = latent tokens ~2x（176k vs 89k）→ 激活也 ~2x，
  直接吃光 headroom（`usable` 17087 vs 20106 差 3GB）→ 换成页。卸载 3.6GB 填不上 2x 激活的缺口。
- **GPU 占用忽高忽低 ≠ 内存故障**：`async weight offloading with 2 streams` 常开（19:08:15），5s 一轮
  占用也在低频波动——那是异步卸载流 + 进度条固有节奏；真换页是 10s 那种"步数走不动"。
- **对策**：长视频按 7s 起测（官方已验证 124–362 帧区间更稳的短半段），或接受 10s 的 ~2x 算力成本；
  显存/换页问题已到底，不再依赖卸载节点解决。

### 10.5 联网核查后覆盖：480p 更长时长的正解是降步数，不是换显存
> 结论：**480p 甜点仍是 5s，10s 是显存硬墙（两个模型实测都爆）；降步数是唯一有官方背书的时间杠杆（官方模板默认仅 12 步）；两模型速度几乎无差、Q4_K_M VRAM 略低，维持 Q4_K_M 不换模型。**

- **模型/仓库现状（molbal/MiniMax-H3-GGUF README + 文件树，2026-09-09 在线核实）**：
  - 官方现提供 `fl2va_pruned_fp8_Q4_0`（11.4GB）/ `Q8_0`（20.2GB）/ `Q8_CR`（20.2GB）/ `U16G`（15.0GB），**无 Q4_K_M fl2va**；本地 `minimax_h3_fl2va_pruned-Q4_K_M.gguf`（10.64GB）为旧版命名。fp8_Q4_0 曾下载至 `models/diffusion_models/`（10.60GB）并接入 `minimax_h3_t2v-fp8-gguf.json`，数据对比结束后二者均已删除（见下文采纳建议 2）。
  - **输出时长官方支持 4–15 秒**（README「Output duration: 4–15 seconds」）；10s 在模型能力范围内，瓶颈纯在显存。
  - **U16G（混合 INT8+Q4，15GB）README 称 16GB+ 卡上比 Q4_0 快**，但 15GB 权重对 24GB 卡太挤（10s 已爆），已否决不下载。
  - ⚠️ **K-quant 在 H3 架构属非常规**：ComfyUI-GGUF README 明确 `_K` 量化仅用于文本编码器，扩散模型「可能加载但推理速度极慢」；joeygambino 模型卡称 H3 隐藏宽 2688 不整除 K-quant 的 256 行要求（「architecturally impossible for this model」）。**但本机实测 fp8_Q4_0 与 Q4_K_M 速度几乎相同**——反量化路径正常，该警告未显现，故不为理论风险换模型。
- **官方步数档位（联网三处交叉印证）**：
  - **本地官方 ClipProj 模板（CCTech 示例工作流，最权威）**：`BasicScheduler` 默认 **12 steps**（`simple,12,1`），sampler `res_multistep`。
  - **Comfy Cloud MiniMax-H3 云端 workflow**：**20 steps**（864×480×124 帧，issue #15760）。
  - **issue #15453 官方典型配置**：**10 steps**（864×480@243 帧，采样 ~3:40 并完成解码）。
  - → 官方默认区间 10–20，本地模板取中 **12**；社区配 SageAttention 6 步亦可跑。**降步数有官方背书，是安全时间杠杆。**
- **✅ 实测结论（2026-09-09 双模型 A/B，用户实跑）**：
  - **fp8_Q4_0 vs Q4_K_M：采样速度几乎相同**；**Q4_K_M VRAM 占用略低一点点**（不是 fp8 更低）。
  - **两模型在 10s 均爆显存** → 10s 是 480p 换页硬墙，与量化无关，**不再试其它量化/U16G**。
  - **两模型之间的质量差距：未做对比**（用户仅对比速度/VRAM；全网亦无公开同模型 Q4_K_M vs fp8_Q4_0 的 benchmark）。理论层面 fp8 精度更接近 source，但对观感是不可感级差异；实证上二者之别只剩 VRAM。
  - **10 步 vs 20 步（同模型）：肉眼质量基本一致**（用户实测）；且官方模板默认仅 12 步自我印证了该结论。
- **采纳建议**：
  1. 三套工作流的 `BasicGuider`（t2v 124 / i2v / ref2v 同构节点）steps 由用户自行从 20 下调至 **10 或 12**（官方模板即 12），cfg 保持 1.0，采样时间约减半。
  2. **模型维持 Q4_K_M 不用换**——fp8 无速度收益、VRAM 反而略高，K-quant 警告在本机未显现；已下载的 fp8_Q4_0（及改名的 t2v-fp8-gguf.json）在对比完成后已删除，不保留。
  3. 解码前卸载节点（135/145/157）**保留**——治 #15484 co-residency 抖动，是解码快的来源。
  4. 采样前卸载节点（136/146/158）**保留但别指望收益**——t2v 下只卸 TE 3.6GB。
  5. **时长天花板已定：480p = 5s 甜点**；想要更长 = 放弃解锁（接受换页）或上更大显存。
- **风险**：10 步质量实测与 20 步同级、且官方模板默认 12 步，但仍是主观判断；正式出片如需极高质量可保留 12–20 步选项。

---

### 10.6 联网续查优化手段（2026-09-09，含本机实测结论）：5s 仍是甜点，10s 是「能跑但极限」
> 结论：**两条启动参数（`--disable-pinned-memory --fp16-intermediates`）已加入 `run_amd_gpu.bat`（.bak 已备份）。本机实测：RAM 占用确实下降（幅度不大）、10s 不再爆显存——但 10s 已非常极限，不安全，且耗时是 5s 的 3 倍多；**内存耗尽时仍会崩溃**（更正：只降低了单次内存消耗、不容易触发，并非消除 OOM 崩溃）。最终维持 5s 为甜点档位。**

- **原稿否定回顾**：§10.5 曾把「10s 爆显存」定为换页硬墙、不再试。该判断建立在缺启动参数的前提下，需降级为「未验证的可解瓶颈」。
- **已验证同款硬件的正解（tonyd2wild/MiniMax-H3-Local，3090+31GB RAM）**：
  - `--disable-pinned-memory`（关掉 ComfyUI 默认锁定系统 RAM 的缓冲，Windows 上默认锁 ~40%）：OOM-kill → 完整 15s，仅此一条 flag 之差。
  - `--fp16-intermediates`（配合前者，压中间激活内存）。
  - 本机要测：`python main.py --listen 0.0.0.0 --port 8188 --disable-pinned-memory --fp16-intermediates ...`，配已有的 `--enable-dynamic-vram` 变体。
- **官方提速手段（ComfyUI docs minimax-h3）**：
  - **官方 turbo LoRA**：`minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16`，LoRA 8 步生成，速度快、质量略降——但**面向原生原生 checkpoint，是否适用于 GGUF 路径未验证**，需自行试（UnetLoaderGGUF + LoRA 兼容性未知）。
  - 官方默认 20 步；步数 20→25 提高运动质量——与本地 12 步模板、10 步实测结论并存，属步数档位选择。
  - `884×480` 档位已是减负常见选择；官方原生 canvas 是 1344×768。
- **不适用于本机的提速项（已排查排除）**：
  - `--use-sage-attention`：其一 AMD 无 SageAttention 支持；其二 issue #15263 证实 H3 用全局 sage 产生**纯噪声**（需模型内低精度开关，本机 LGUF 路径无此开关）。
  - Optimization Suite（NVFP4 Fused MLP / Low-Memory Sage2）：**Blackwell/NV 专属**，AMD 无效。
  - CAB Sampler（低步数 solver）：面向原生 ComfyUI 节点，GGUF 路径接入存疑，且非官方，优先级低。
  - **Tiled VAE 对 H3 无效**：tonyd2wild 实证 `vae.decode_tiled` 直接落到 `self.decode`，H3 VAE 已内建 tile（256px 空间 / 17 帧时间），别浪费时间。
  - pepikir latent 磁盘缓存：面向「TE 放不下」的 32B TE 场景；本机 TE 仅 4B heretic（~3.6GB），收益有限。
  - **ComfyUI-MiniMaxH3-Cache：雷，勿装**——全局 monkey-patch 会破坏 H3 生成（lihaoyun6/ComfyUI-MiniMaxH3-Cache#4）。
- **若不换链：维持 §10.5 结论（Q4_K_M 12–20 步、5s 甜点）；若想解 10s/15s：先加两条启动参数实测，5 分钟见分晓。**
- **🏁 最终基准（2026-09-09 用户实测，优化已到极致）**：同样条件（**480P / 10s / 20 步 / 长提示词**）下生成时间 **40–45 分钟**，比最初同条件**几乎短了一半**；480p **5s 为绝对甜点**（速度/稳定性/显存余量综合最优，日常主力档）；**10 步与 20 步输出区别不明显**（差异与提示词相关，随提示词复杂程度浮动）——故可长期用 10/12 步省时间，需要更高运动质量时再回到 20 步。10s 为「能跑但极限」的备用档（显存逼近红线、耗时 ~3x）。文档至此收敛，不再追加优化动作。

---

- Molbal 官方 GGUF 三件套 workflows：`github.com/molbal/ComfyUI-GGUF`（workflows 目录，t2v/i2v/ref2v 模板；该仓库现改名 `github.com/ChrisColeTech/ComfyUI-GGUF-Loader`）；GGUF 模型：`huggingface.co/molbal/MiniMax-H3-GGUF`
- ClipProj 投影矩阵库：`huggingface.co/NicoLab28/ClipProj-MiniMax-H3`（mmh3-4b-ClipProj-v3.1.safetensors）；内核源自 `github.com/nicolab28/ComfyUI-ClipProj`
- qwen3vl 4B heretic：`matrixportalx/Qwen3-VL-4B-Instruct-heretic-Q4_K_M-GGUF`（由 `coder3101/Qwen3-VL-4B-Instruct-heretic` 转换）、`huggingface.co/DreamFast/Qwen3-VL-4b-Heretic-ComfyUI`
- qwen3vl 4B heretic **mmproj**（视觉塔，节点 131 修复）：`hf-mirror.com/mradermacher/Qwen3-VL-4B-Instruct-heretic-GGUF`（`Qwen3-VL-4B-Instruct-heretic.mmproj-f16.gguf`，836MB；matrixportalx 版无 mmproj）
- unsloth GGUF 家族：`huggingface.co/unsloth/MiniMax-H3-GGUF`（fl2va/ref2va 区分 + `--backend te=cpu` 佐证 TE 可卸载）
- joeygambino/MiniMax-H3-GGUF（K-quant 在 H3 架构不可行的依据 + VRAM/Q4_0 测算）：`huggingface.co/joeygambino/MiniMax-H3-GGUF`
- 本地官方 ClipProj 模板（12 steps 默认值）：`ComfyUI_windows_portable/ComfyUI/custom_nodes/ComfyUI-ClipProj/example_workflows/minimax_h3_clipproj.json`
- 15s@24GB 硬配置正解（--disable-pinned-memory + --fp16-intermediates）：`github.com/tonyd2wild/MiniMax-H3-Local`（docs/3090-comfyui.md：OOM-kill → 完整 15s，仅一条 flag 之差；`vae.decode_tiled` 对 H3 无效果）
- 官方 turbo LoRA（8 步提速，质量略降）：`docs.comfy.org/tutorials/video/minimax/minimax-h3`（工作流默认 20 步、turbo_mode 8 步 + Lightning LoRA）；官方原生 canvas 1344×768
- AMD 不可用的 NV 专属优化（Blackwell）：`github.com/ByronLeeeee/ComfyUI-MiniMax-H3-Optimization-Suite`（NVFP4 Fused MLP / Low-Memory Sage2 / CAB Sampler）
- `--use-sage-attention` 对 H3 出纯噪声：`github.com/Comfy-Org/ComfyUI/issues/15263`
- 勿装的雷：`github.com/lihaoyun6/ComfyUI-MiniMaxH3-Cache#4`（全局 monkey-patch 破坏 H3 生成，ComfyUI Wiki 亦警告）
- Windows 崩溃 0xC0000005（GGUF mmap 叠加）与卸载纪律：`Thefrizzy1/ComfyUI-MiniMaxH3-Director` node_docs
- ComfyUI 0.34 原生 H3 支持：`comfy/ldm/minimax`、`text_encoders/minimax.py`、`comfy/sd.py`（MINIMAX=35、QWEN3VL_32B 检测）、`comfy_extras/nodes_minimax_h3.py`、`nodes_math.py`（MathExpressionNode / ComfyMathExpression）
- CCTech Suite 本地代码：`nodes/extra.py`（CCTechClipProjLoader:74）、`nodes/gguf.py`（UnetLoaderGGUF:317）、`vendor/clipproj.py`