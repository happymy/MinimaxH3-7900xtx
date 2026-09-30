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
>   卸载节点，采样前/解码前两段手动清场（详见 §10.4）。
>
> **2026-09-30 路线更新（新增 I2V / R2V 用途后的文本编码器选型，详见 §11）**：
> - **采纳 `--use-ck-attention`**（comfy_kitchen INT8 attention）：端到端实测采样 **2.70x** 加速、峰值显存反降 0.40 GiB、全帧画质无实质损失（相关系数 0.99786）。已写入 `run_amd_gpu_enable_dynamic_vram.bat`。
> - **文本编码器：4B 保留为 T2V 快档，8B 作 I2V/R2V 主力档；32B 明确不上。**
>   决定性依据：Qwen3-VL 的**视觉塔在 8B 与 32B 之间逐项相同**（depth 27 / hidden 1152 / ff 4304 / deepstack [8,16,24]），
>   32B 在图像侧零增益，却要 24.55 GiB 体积 + ≈24.7 GiB 峰值显存（本卡 24 GB）。
> - **「无道德约束」对条件编码器是伪需求（机制层面）**：TE 只出 embedding 不生成文本，无「拒绝」行为；abliterated 对 conditioning 余弦影响仅 **0.0023**。
>   本机 4B heretic 本身即去审查版，保持不动。
>   **⚠️ 2026-09-30 13:00 更新**：另下载了 8B 破限备选 `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`（DreamFast Heretic v1.3.0，9.33 GB）并跑通端到端。
>   A/B 实测（§11.11）：**破限版不是 no-op** —— 124 帧**全部改变**（0/124 逐字节一致，SSIM 0.8264）；但**耗时无差异**（442.0 s vs 443.8/451.0 s）。
>   **默认仍用 stock 8B**：破限版视觉塔从 BF16 降到 F8_E4M3（I2V/R2V 有精度代价），且 staged 显存 16,721 MB > 可用 14,542 MB（stock 为 10,097 MB，可完全驻留）。
> - **最大收益项是零成本的**：prompt 必须改为官方三段格式（`integrated_multimodal_description` / `overall_soundscape` /
>   `non_diegetic_music`），并删除负向约束块（本工作流无 negative conditioning 入口，负向文本无处可去）。
> - 所有新增文件**只增不改**，4B 全套保留为回滚锚点，切换靠节点 #131 的三个下拉框。

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

`plan\molbal_workflows\final\4b\` 改编自 Molbal 官方 workflows：
`github.com/molbal/ComfyUI-GGUF/tree/main/workflows`（该仓库现改名
`ChrisColeTech/ComfyUI-GGUF-Loader`）的 t2v/i2v/ref2v 模板。
**节点已逐一定位，0.34 全部内置**——仅两处替换（见下方各节），其余节点
（`MiniMaxH3ImageToVideo`/`MiniMaxH3ReferenceToVideo`、`ResolutionSelector`、
`ComfyMathExpression`(=core `MathExpressionNode`, nodes_math.py:70)、`VAELoader`×2、
`KSamplerSelect`/`BasicScheduler`/`BasicGuider`/`SamplerCustomAdvanced`/`RandomNoise`、
`VAEDecode`/`VAEDecodeAudio`、`CreateVideo`/`SaveVideo`、`MarkdownNote`）一律不动。

> **`plan\molbal_workflows\` 目录结构（2026-09-30 用户整理后）**
>
> ```
> molbal_workflows\
> ├ bak RAW\ / bak noerror 0,1,2\   ← 历史版本，一字不动，仅作回滚锚点
> └ final\                          ← 交付集合层（唯一有效入口）
>    ├ 4b\                          ← 4B 基底：根 3 份旧提示词 + op\ 子目录 3 份官方提示词
>    ├ 8b\                          ← 8B stock，旧提示词
>    ├ op-8b\                       ← 8B stock + 官方提示词（主力档）
>    ├ op-8b-heretic\               ← 8B 破限 + 官方提示词
>    ├ qwen_image_2_1_*.json ×3     ← Qwen-Image 工作流（与 H3 无关）
>    └ 提示词模板-视频.txt / -照片.txt
> ```
>
> `final\` 是集合根，**不直接放工作流**。`plan\API_workflows\` 未加这层，仍平铺
> （`8b\` / `op\` / `op-8b\` / `op-8b-heretic\` / `omy\` 五个目录 + `H3工作流适配计划.md`）。

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
- `plan\molbal_workflows\final\4b\minimax_h3_t2v-gguf.json`：仅改两处——
  `UnetLoaderGGUFDynamicVRAM` → CCTech `UnetLoaderGGUF`，`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`；
  `CLIPLoader` → CCTech `CCTechClipProjLoader`，`[qwen3-vl-4b-heretic-Q4_K_M.gguf, krea2, mmh3-4b-ClipProj-v3.1.safetensors]`。
- cfg：H3 是蒸馏模型，**cfg=1.0 附近**（>1.0 可能直接中止，勿改大）。
- 纯文本 prompt（或 Molbal 模板自带三段式结构化 H3 prompt）。

### 5.2 I2V（用 fl2va + 首帧）
- `plan\molbal_workflows\final\4b\minimax_h3_i2v-gguf.json`：同 §5.1 两处替换；`LoadImage`×2（图 114/141）默认
  `bg-cerritos-exterior-01.jpg` → 换自己的首/末帧图。
- fl2va 变体支持「文本 + 零/一/两帧」；`ResizeImageMaskNode`（core）自动缩到模型输入尺寸。
- **注意**：GGUF 编码器走 vision tower 需要 mmproj（**已安装**，见 §10.3）；官方 workflow 的 I2V 模板用的是
  官方 32B safetensors 编码器（自带 vision），换成 GGUF 4B 后引用图路径由 mmproj 视觉塔提供（见 R4）。

### 5.3 R2V（用 ref2va + 引用图/视频/音频）
- `plan\molbal_workflows\final\4b\minimax_h3_ref2v-gguf.json`：同 §5.1 两处替换（unet 用 `ref2va_pruned-Q4_K_M.gguf`）；
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
- [x] 三套 Molbal 工作流改编完成 → `plan\molbal_workflows\final\4b\`，JSON 已校验。
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
| R6 | ~~32B 路线被整体排除~~ → **2026-09-30 升级为「有据否决」**（详见 §11.2）：Qwen3-VL 的**视觉塔在 8B 与 32B 之间逐项相同**（depth 27 / hidden 1152 / ff 4304 / deepstack [8,16,24]），32B 在 I2V/R2V 图像侧**零增益**，却要 24.55 GiB 体积 + 24.7 GiB 峰值显存（本卡 24 GB），且 ConvRot 权重存为 `weight_g` 可能过不了 `detect_te_model` 的字面 key 检测 | 仅剩语言容量（5120d/64L vs 4096d/36L） | **不上 32B**。改上 8B（拿满 32B 级视觉塔，10.6 GB）。见 §11.4 |
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
  - `--use-sage-attention`：**三重否决**——(1) 本机无 triton，ROCm 下装不了；(2) **AMD 官方实测 Navi31（RDNA3）上 sage 比 PyTorch SDPA 慢 30–34%**，它根本不是 AMD 上的提速项；(3) issue #15263 证实 H3 用全局 sage 产生**纯噪声**（需模型内低精度开关，本机 GGUF 路径无此开关）。
  - ✅ **替代方案已采纳：`--use-ck-attention`**（ComfyUI 自带 comfy_kitchen INT8 attention）。本机端到端 A/B 实测（同 seed 1234、8 步、1280×736×107f）：采样 **106.0 → 39.26 s/it（2.70x）**；总耗时 1005s → 498s（2.02x）；峰值专用显存 **21.37 → 20.97 GiB（反降 0.40）**；共享显存 567 → 743 MB，从未触发分页。全 107 帧逐帧比对：相关系数 0.99786、平均像素差 2.33/255、锐度 +4.05%、平坦区噪声 −5% → 差异集中在细节而非加噪。已追加到 `run_amd_gpu_enable_dynamic_vram.bat` 末尾。
  - Optimization Suite（NVFP4 Fused MLP / Low-Memory Sage2）：**Blackwell/NV 专属**，AMD 无效。
  - CAB Sampler（低步数 solver）：面向原生 ComfyUI 节点，GGUF 路径接入存疑，且非官方，优先级低。
  - **Tiled VAE 对 H3 无效**：tonyd2wild 实证 `vae.decode_tiled` 直接落到 `self.decode`，H3 VAE 已内建 tile（256px 空间 / 17 帧时间），别浪费时间。
  - pepikir latent 磁盘缓存：面向「TE 放不下」的 32B TE 场景；本机 TE 仅 4B heretic（~3.6GB），收益有限。
  - **ComfyUI-MiniMaxH3-Cache：雷，勿装**——全局 monkey-patch 会破坏 H3 生成（lihaoyun6/ComfyUI-MiniMaxH3-Cache#4）。
- **若不换链：维持 §10.5 结论（Q4_K_M 12–20 步、5s 甜点）；若想解 10s/15s：先加两条启动参数实测，5 分钟见分晓。**
- **🏁 最终基准（2026-09-09 用户实测，优化已到极致）**：同样条件（**480P / 10s / 20 步 / 长提示词**）下生成时间 **40–45 分钟**，比最初同条件**几乎短了一半**；480p **5s 为绝对甜点**（速度/稳定性/显存余量综合最优，日常主力档）；**10 步与 20 步输出区别不明显**（差异与提示词相关，随提示词复杂程度浮动）——故可长期用 10/12 步省时间，需要更高运动质量时再回到 20 步。10s 为「能跑但极限」的备用档（显存逼近红线、耗时 ~3x）。文档至此收敛，不再追加优化动作。

---

## 11. 文本编码器档位选型（2026-09-30 定案：**升 8B，不升 32B**）

> **结论**：现有 4B **保留**为 T2V 快档；**新增 8B** 作为 I2V / R2V 主力档；**32B 明确不上**。
> 决策依据不是「模型越大越好」，而是 **Qwen3-VL 的视觉塔在 8B 与 32B 之间逐项相同**——32B 买不到任何图像侧收益，却要付 2.3 倍体积和超过本卡 24 GB 的峰值显存。
> 另附两条独立结论：**「无道德约束」对条件编码器是伪需求**（§11.3）；**prompt 三段格式是零成本最大收益项**（§11.6）。

### 11.1 决定性证据：视觉塔三档规格

`Qwen/Qwen3-VL-{4B,8B,32B}-Instruct` 的 `config.json → vision_config`（2026-09-30 在线核实）：

| 视觉塔参数 | 4B | 8B | 32B | 读法 |
|---|---:|---:|---:|---|
| `depth` | 24 | **27** | **27** | 4B→8B +12.5%；**8B = 32B** |
| `hidden_size` | 1024 | **1152** | **1152** | 同上 |
| `intermediate_size` | 4096 | **4304** | **4304** | 同上 |
| `num_heads` | 16 | 16 | 16 | 全同 |
| `patch_size` / `spatial_merge_size` | 16 / 2 | 16 / 2 | 16 / 2 | 全同 |
| `deepstack_visual_indexes` | [5,11,17] | **[8,16,24]** | **[8,16,24]** | 4B 的注入层更浅 |
| `out_hidden_size` | 2560 | 4096 | 5120 | 投影进各自 LM 宽度 |

**这张表决定了整个选型：**

- **4B → 8B 是图像侧的实质升级**：视觉塔深度 +12.5%、宽度 +12.5%、deepstack 注入点从 [5,11,17] 前移到 [8,16,24]（更靠近语义层）。本机此前 T2V 实测中该视觉塔**从未执行**（`#129 first_frame` / `last_frame` 均为空、全流程零 LoadImage 节点），一旦转 I2V/R2V 它立刻成为主路径——这正是本轮新增需求带来的变化。
- **8B → 32B 在图像侧收益为零**：两者视觉塔逐项相同。32B 只多给语言容量（hidden 5120 vs 4096、64 层 vs 36 层）。

### 11.2 为什么不上 32B（四条独立理由）

| # | 理由 | 证据 |
|---|---|---|
| 1 | **图像侧零收益** | 见 §11.1，8B 与 32B 视觉塔逐项相同 |
| 2 | **显存放不下** | `ethanfel` 的 32B INT8 ConvRot 实测 TE 峰值 **≈24.7 GiB**（RTX 5090 32GB 实测），本机 `Total VRAM 24560 MB`；官方 32B NVFP4 峰值亦有 **16.04 GiB**，与 DiT 争抢余量极小 |
| 3 | **落地检测有风险** | ComfyUI `detect_te_model`（`comfy/sd.py:1674`）用**字面 key** `model.layers.49.self_attn.q_proj.weight` 判定 H3 编码器，而 ConvRot 权重实际存为 `weight_g`（同一文件 `sd.py:522` 就有 `.weight_g` 分支）→ **可能直接检测失败**。为不存在的画质收益背这个风险不值 |
| 4 | **同门实测也不支持** | 见下方三条补充证据 |

**补充证据（全部指向「别上 32B」）：**

- `SearchingMan/MiniMax-H3-Text-Encoders` 的 `recovered_8b_int8_convrot` 峰值仅 **6.18 GiB**（很诱人），但作者 README 末尾明确：*"validated for text-only T2V. **Do not use them for image, first-frame, last-frame, or reference inputs.**"* → 本用途被作者**明确排除**。
- `NicoLab28/ClipProj-MiniMax-H3` v3.1 基准（**297 次语音渲染 + 405 次图像渲染**，三 seed）：归一化到「换 seed 的自然波动」后，**4B 与 8B 分不开**，ridge 与 residual 也分不开；而 32B 自身「只换 seed，75 个音素里就有 5.8 个发音不同」。测试余弦：`mmh3-8b-ClipProj-celeb-mlp` 0.8037 / `mmh3-8b-ClipProj-mlp` 0.7970 / `mmh3-4b-ClipProj-mlp` 0.7944 / `mmh3-4b-ClipProj` 0.7169。
- 同一份 benchmark：H3 在 **3s / 7s 硬切点**的要求下，**三种编码器（含官方 32B）全部未通过**（`evidence/cut_diagnostics.json`）。→ 「精确时间轴」不是编码器能解决的问题，见 §11.6。

### 11.3 「无道德约束」对条件编码器：机制上是伪需求，但确有 ComfyUI 单文件版

文本编码器**只产出 embedding，从不向用户生成文本**，因此不存在「拒绝」这一行为。ClipProj README 实测：把 bf16 校准的矩阵套用到 **abliterated（去审查）fp8 编码器**上，conditioning 余弦差仅 **0.0023** —— 去审查对条件化的**数值**影响可忽略。

- 本机现有 `qwen3-vl-4b-heretic-*.gguf` **本身就是 abliterated 版**（§4.3 / §10.3 链路已确认），**T2V 快档的「无道德约束」已满足，保持不动**。
- 去审查只在**会生成文本**的场景才要紧 —— 即 32B 的 prompt-enhancer tail（layers 50–63 + LM head）。不上 32B 就不涉及。
- **⚠️ 2026-09-30 修正**：本节原写「`heretic-org/Qwen-3-VL-8B-Instruct-heretic` 是 transformers 分片格式，目前无人发布其 ComfyUI 单文件版」——**此判断已被推翻**。`DreamFast/Qwen3-VL-8B-Heretic-1.3.0` 发布了 ComfyUI 单文件 safetensors（含 `comfyui/` 子目录三档量化），已下载并跑通，详见 **§11.11**。
- 但「余弦差 0.0023」不等于「输出不变」。**§11.11 的本机 A/B 实测证明：换成破限版后 124 帧全部改变（0/124 一致，SSIM 0.8264）**。所以正确表述是「去审查**不改变 TE 的角色与可用性**」，而不是「换不换都一样」。

### 11.3.1 三条容易混淆的结论

| 说法 | 是否成立 | 依据 |
|---|---|---|
| TE 不生成文本，所以不会被审查拦截 | ✅ 成立 | 架构事实；ClipProj README 余弦 0.0023 |
| 换破限 TE 后输出**逐字节不变** | ❌ **不成立** | §11.11：0/124 帧一致，SSIM 0.8264 |
| 换破限 TE 后输出**质量不变** | ❓ **本机无法判定** | 相似度指标只能测「差多少」，不能测「谁更好」；需多 seed 盲评或拒答率测试 |

### 11.4 三档配置（物理并存，靠下拉框切换）

| 档 | 用途 | 文本编码器 | 投影矩阵 | node #131 `type` | 磁盘 | TE 显存 |
|---|---|---|---|---|---:|---:|
| **T1 现状** | T2V 快档 | `qwen3-vl-4b-heretic-Q4_K_M.gguf` + `qwen3-vl-4b-heretic.mmproj-f16.gguf` | `mmh3-4b-ClipProj-v3.1.safetensors` | `krea2` | 3.11 GB | ~3.6 GB（实测） |
| **T2** | **I2V / R2V 主力** | `qwen3vl_8b_fp8_scaled.safetensors`（**Comfy-Org stock，视觉塔全 BF16 零量化**，自带视觉塔不需要 mmproj） | `mmh3-8b-ClipProj-v3.1.safetensors` | `boogu` | 10.6 GB | staged **10,097 MB**（实测） |
| **T2b** | 8B 破限备选（2026-09-30 新增，见 §11.11） | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`（**DreamFast Heretic v1.3.0**，语言塔同 T2，但**视觉塔 116 个张量被降到 F8_E4M3**） | `mmh3-8b-ClipProj-v3.1.safetensors` | `boogu` | 9.33 GB | staged **16,721 MB**（实测，⚠️ 超出可用显存） |
| ~~T3~~ | — | ~~32B~~ | — | — | — | **不上（§11.2）** |

> ⚠️ **T1 现状的 TE 文件名标 `Q4_K_M`，实测 `general.file_type=15` = **MOSTLY_Q3_K_M**，**70.8% 字节是 3-bit**（Q3_K_M 1.644 GiB + Q4_K_S 0.676 GiB）。RMSNorm 全保 F32（结构正确），但 attn 的 q/k/v/o 有 126/144 是 3-bit、ffn 90/108 是 3-bit。**升 8B fp8 顺带消除这个隐患。**
>
> ⚠️ **T2 与 T2b 不可互换视作等价**：T2b 视觉塔从 BF16 降到 F8_E4M3，**图像路径有精度损失**，这对 T2V（纯文本）无影响，但**对 I2V / R2V 是真实代价**。选型见 §11.11.4。

**T2 可落地性已逐条核实（全部来自本机代码）：**

| 检查项 | 结论 | 依据 |
|---|---|---|
| 加载器接受 safetensors？ | ✅ | `custom_nodes/ComfyUI-GGUF-Loader/nodes/extra.py:74` `ClipProjLoader(CLIPLoaderGGUF)`，tooltip 明示接受 `.gguf` 或 `.safetensors` |
| 认得 Comfy-Org 的键名？ | ✅ | `vendor/clipproj.py:75` `_MERGER_KEYS` 同时含 `model.visual.merger.linear_fc2.weight` 与 `visual.merger.linear_fc2.weight` |
| 能自动判出 8B？ | ✅ | `vendor/clipproj.py:73` `_ARCH_BY_DIM = {2560:(krea2,4B), 4096:(boogu,8B), …}`；8B 的 `out_hidden_size=4096` → `boogu` |
| fp8 受支持？ | ✅ | `detect_arch` docstring 明示「Quantised variants (fp8, nvfp4, int8_convrot) declare it just the same」 |
| 矩阵宽度匹配？ | ✅ | 8B 矩阵 `W[4096→5120]`；节点校验宽度，**4096 与 4B 的 2560 不可互换**（配错会拒绝，不会静默出错） |

**T2 已下载完成并通过运行期验证（2026-09-30）：**

> ⚠️ 本表所有结论均针对 **T2 = `qwen3vl_8b_fp8_scaled.safetensors`（Comfy-Org stock）**。T2b 破限版的对照实测见 **§11.11.2**，两者**不共用**本表数据。

| 验证项 | 结果 |
|---|---|
| **文件名** | `qwen3vl_8b_fp8_scaled.safetensors` |
| **来源** | `Comfy-Org/Qwen3-VL` → `text_encoders/` |
| 8B 编码器字节数 | `10,588,637,512` —— 与 HF API 声明值**逐字节一致** |
| 三个矩阵字节数 | `40,003,392` / `576,068,864` / 4B 现有 `26,256,128` —— 全部一致 |
| 矩阵张量形状 | `8b-v3.1` = ridge `W[4096,5120]`（6 张量，含 `sink_out`）；`8b-v3.1-mlp` = **纯 MLP 无 `W`**，`mlp.0[32768,4096]`→`mlp.2[5120,32768]`（8 张量，**无 `sink_out`**） |
| **真实文件跑 `detect_arch`** | 从 `vendor/clipproj.py` 源码抽出 `_MERGER_KEYS=['model.visual.merger.linear_fc2.weight','visual.merger.linear_fc2.weight']`、`_ARCH_BY_DIM={2560:('krea2','4B'),4096:('boogu','8B'),5120:('minimax','32B')}`，喂真实 10.59 GB 文件头 → **命中 `model.visual.merger.linear_fc2.weight` shape=[4096,4608] → 返回 `('boogu','8B')` ✅** |
| ComfyUI 原生路径也能识别 | 文件键名是 `model.layers.*` + `model.visual.*`；`comfy/sd.py:1919` 的 `state_dict_prefix_replace` 把 `model.visual.`→`visual.`，`model.language_model.` 无匹配（本来就没有）→ 两条路径都指向 `QWEN3VL_8B` |
| 视觉塔规格（**从文件实测，非查文档**） | `blocks` 索引 0..26 → **depth 27**；`attn.qkv.bias[3456]`=1152×3 → **hidden 1152**；`mlp.linear_fc1[4304,1152]` → **ffn 4304**；`pos_embed[2304,1152]`；`deepstack_merger_list[0,1,2]` → 对应注入层 **[8,16,24]**。**七项全部命中 §11.1 的预测** |
| **视觉塔量化状态（T2 stock）** | **全部 BF16，零量化**（`blocks.*` / `pos_embed` / `deepstack_merger_list.*` 全 BF16，共 351 个视觉张量）。语言侧 `F8_E4M3×252 + U8 scale×252 + fp32 weight_scale×252` → 252÷7 = **36 层**，即 LM 走 FP8 |
| 张量总数 / dtype 分布 | 1,254 个：`BF16×498 + F32×252 + F8_E4M3×252 + U8×252`（`fp8_scaled` = U8 载荷 + 独立 fp32 `weight_scale`，故张量数是裸 fp8 的 1.67 倍） |
| 工作流变体 | `minimax_h3_t2v-gguf-api-te8b.json`、`minimax_h3_i2v-gguf-api-te8b.json` 已生成并回读校验（节点/连线数与原版一致）。注意 I2V 的加载器节点 id 是 **137**、T2V 是 **131** |
| **运行期 staged 显存** | `Model BooguTEModel_ prepared ... 10097MB Staged` → `loaded completely; 14753.38 MB usable, 11186.65 MB loaded, full load: True`。**staged < usable，可完全驻留显存** |

> 💡 **对 I2V/R2V 而言这是最优配置**：图像路径（视觉塔）**满精度零损失**，而语言路径从现状的 **3-bit 升到 FP8**。§11.1 论证的是视觉塔**架构**升级（depth 24→27 / hidden 1024→1152 / deepstack [5,11,17]→[8,16,24]），本条补证的是**两档视觉塔精度相同（都满精度）**，所以收益是纯架构收益，不含精度掺杂。

**显存账（24 GB 卡）**：T2 的 ~11–12 GB 峰值出现在**编码阶段**，此时 DiT 尚未驻留。工作流已有的 `ForceUnloadBeforeDecode` **#136** 在 conditioning 之后 / 采样之前清场、**#135** 在解码前再清一次，故 T2 不与 DiT 抢显存。代价是 USB 3.0 每次加载多约 30–50 s。`context_length=262144`，长 prompt 不会截断（T1 实测）。

### 11.5 备份与回滚（不动任何现有文件）

**原则：只增不改、不删、不移、不改名。** 新旧各档物理并存，切换 = 改节点 #131 的三个下拉框。

**新增文件（3 个模型）**
```
models/text_encoders/qwen3vl_8b_fp8_scaled.safetensors                        ← T2  stock，10,588,637,512 B
models/text_encoders/qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors        ← T2b 破限，10,017,064,632 B（9.33 GiB）
models/clip_projections/mmh3-8b-ClipProj-v3.1.safetensors                    ← 新增 ~30 MB（T2/T2b 共用）
```

**保持原样（回滚锚点，一个字节都不动）**
```
models/text_encoders/qwen3-vl-4b-heretic-Q4_K_M.gguf         2.33 GB
models/text_encoders/qwen3-vl-4b-heretic.mmproj-f16.gguf     0.78 GB
models/clip_projections/mmh3-4b-ClipProj-v3.1.safetensors    25 MB
user/default/workflows/minimax_h3_t2v-gguf-api.json         SHA256:A1F080CB2C489B41
user/default/workflows/minimax_h3_i2v-gguf-api.json         SHA256:3D740DBB8E6386BE
user/default/workflows/minimax_h3_t2v-gguf.json              SHA256:05F4ECB1C544301B
```

**回滚（30 秒，零卸载、零删除）**：节点 #131 三个下拉框改回
`clip_name = qwen3-vl-4b-heretic-Q4_K_M.gguf` / `type = krea2` / `projection = mmh3-4b-ClipProj-v3.1.safetensors`，重启 ComfyUI 即回到现状。
8B 三档之间互切同理，只改 `clip_name` 与 `type`（`boogu` 三档共用），`projection` 固定 `mmh3-8b-ClipProj-v3.1.safetensors`。

**工作流变体**：新增文件后另存两份，**与现有 3 份并存**（不覆盖）：
```
user/default/workflows/minimax_h3_t2v-gguf-api-te8b.json
user/default/workflows/minimax_h3_i2v-gguf-api-te8b.json
```

**磁盘**：D:（USB 3.0 外接盘，模型所在盘）下载前实测可用 **255.8 GB**。T2（10.6 GB）+ T2b（9.33 GB）合计 19.9 GB，无压力。计划书已备份为 `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md.20260930.bak`。

### 11.6 官方三段 prompt 格式（T2VA / I2VA / FL2VA / L2VA）

> 规范来源：官方 `skills/h3-prompt-writing/references/base-en.txt`（本机已装同款 skill `h3-prompt-writing`）。
> **这是零成本、收益最大的一项，与换不换编码器无关。** 官方原话：「H3-Context-IR is critical to the quality of the final output」。

**必须写成三段，且字段标签不可省：**
```text
integrated_multimodal_description: [Shot 1] ... [Shot 2] At 00:03.500, the camera cuts to ...

overall_soundscape: ...

non_diegetic_music: ...
```

| 规则 | 说明 |
|---|---|
| 首镜不加时间戳 | `[Shot 1] Live-action, cinematic, ...` |
| 后续镜用**绝对切点** | `[Shot 2] At 00:03.500, ...`，格式 `MM:SS.mmm`，严格递增且落在时长内 |
| ❌ **禁用区间记法** | `[0s-1s]` `[1s-2.5s]` 在 H3 训练分布里不存在；H3 生成固定帧数 latent，不做区间推理 |
| 运镜三维度 | 类型（`Push In`/`Pull Out`/`Pan Left`/`Arc Shot`/`Tracking Shot`/`Static Shot`…）+ `with small\|large amplitude` + `at slow\|fast speed`，写成自然英文句子，不要堆标签 |
| 屏幕文字用英文双引号 | `a red neon sign reading "营业中"`，原文照抄不翻译 |
| 说话人 ID | `(S1)` 首次出现时在 `<d>` 外交代身份/音色/语速；`<d>` 内**只放语言标签 + 用户原话**，一字不改 |
| 音景**必须拆两段** | 现场/环境音 → `overall_soundscape`（1–4 句）；角色听不到的配乐 → `non_diegetic_music`（1–3 句，只写配器/速度/节奏/动态，不用「悲伤」这类情绪词） |

**负向约束不要写。** 本机三套工作流唯一的条件入口是 `#126 BasicGuider.conditioning <- #129`，**没有第二个输入口**（无 negative conditioning 节点）——负向文本无处可去，纯烧 token 且误导模型。

**I2V / FL2VA / L2VA 的首行指令**（节点自动做视觉拼接，prompt 里**不要**自己写 `<Picture 1>` 标签）：
```text
I2VA:   For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
FL2VA:  How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
L2VA:   How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```
`S.SS` = 实际时长，保留两位小数。节点内部按 `comfy/text_encoders/minimax.py` 的规则拼 `"<Picture 1>: " <vision block> … <prompt>`，并把 vision 位置打 adaLN **tag 0**、文本位置打 **tag 1**。

**模型能力天花板（换任何编码器都救不了，出片时别期待）**：
- 画面内渲染清晰英文（如 `"DIRECTED BY COMFYUI"`）→ 视频扩散模型通病
- 计数类要求（如 `each shown exactly once`）→ 扩散模型不会数
- 精确硬切时间点 → 见 §11.2 末条，**连官方 32B 都不达标**

### 11.7 执行清单

- [ ] **P0（零成本，先做）**：按 §11.6 把三套工作流的 prompt 重写为官方三段格式；删掉全部负向约束块。
- [ ] **P0**：把 `ResolutionSelector`（节点 115）的 `megapixels` 从 **1.0 改到 0.98**。
  - Comfy-Org 官方文档原文（`comfy-org/docs` → `tutorials/video/minimax/minimax-h3.mdx`）：
    *"set the Resolution Selector's Megapixels to **0.98** for H3's native canvas (a 768px short edge, 1344x768 at 16:9) ... **Skip the 1.0 Megapixel step: it yields 1376x768, above the model's 768x1344 pixel area cap**"*
  - 本机 `comfy_extras/nodes_resolution.py` 的 `ResolutionSelector.execute` 换算结果（`multiple=32`）：

    | megapixels | 输出 | 面积 | vs 上限 1,032,192 |
    |---|---|---|---|
    | **1.0（T2V 工作流当前值）** | **1376×768** | 1,056,768 | **超 24,576 px** |
    | **0.98（正解）** | **1344×768** | 1,032,192 | 正好等于上限 = 原生画布 |
    | 0.9 | 1280×736 | 942,080 | 合法但非原生 |
    | 0.5（I2V 工作流当前值） | 960×544 | 522,240 | 合法 |

  - ⚠️ **这不是代码硬限制**：`MiniMaxH3ImageToVideo` 的 `width/height` 上限是通用的 `nodes.MAX_RESOLUTION`，`_empty_av_latent` 也只要求 `//16` 整除（768/16=48、1376/16=86 都过）。**超限不会报错，只会静默出训分布外的画质**——正是最难排查的那类问题。
  - 注：T2V 工作流当前是 1.0 MP（= 被官方点名跳过的那档），I2V 工作流是 0.5 MP。两套都要按各自目标改。
  - ✅ **已逐行核查源码并补测**（2026-09-30 12:06）：目标画布**确实无任何钳制**——`MAX_PIXELS` 只在 `adapt_canvas` 内用于**参考视频帧**归一化，三个 H3 节点都把 `width/height` 原样交给 `_empty_av_latent`。完整换算表（0.1~1.2 全部档位）与源码行号见 **§11.10.1 / §11.10.2**。
- [x] **P1**：下载 **`qwen3vl_8b_fp8_scaled.safetensors`**（`Comfy-Org/Qwen3-VL` → `text_encoders/`）到 `models\text_encoders\` —— **2026-09-30 完成**，10,588,637,512 字节逐字节一致
- [x] **P1b（2026-09-30 13:00 新增）**：下载 **破限备选 `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`**（`DreamFast/Qwen3-VL-8B-Heretic-1.3.0` → `comfyui/`，经 hf-mirror）到 `models\text_encoders\` —— **完成**，aria2 16 线程，10,017,064,632 字节逐字节一致，safetensors header 可解析（750 张量），ComfyUI 下拉项已列出，跑通 T2V 端到端。详见 **§11.11**
- [x] **P1**：下载 `mmh3-8b-ClipProj-v3.1.safetensors`（`NicoLab28/ClipProj-MiniMax-H3`）到 `models\clip_projections\` —— **2026-09-30 完成**，另加送 `mmh3-8b-ClipProj-v3.1-mlp.safetensors`（576 MB）作为矩阵 A/B 备选
- [x] **P1**：另存两份 `-te8b` 工作流变体；**不动**现有 3 份 —— **2026-09-30 完成**并回读校验
- [x] **P1.5**：**首跑 8B 冒烟测试** —— **2026-09-30 完成**。stock 8B（`MiniMax_H3_00166_.mp4` 443.8 s）与破限 8B（`MiniMax_H3_00169_.mp4` 442.0 s）均 success 出片，`detect_arch` 文件级验证（§11.4）+ 实际 encode + 采样 + 解码全链路打通
- [x] **P2**：同 seed A/B **4B vs 8B**，两侧同一段合规三段 prompt —— **2026-09-30 完成**，见 `plan\T2V_4B_vs_8B_对比报告.md`。**结论：耗时 4B 440.2 s vs 8B 443.8 s（+0.8%，8B 几乎免费）；画质优劣仍无法排名**
  - 变体已就绪：`minimax_h3_t2v-gguf-api-op.json`（4B）vs `minimax_h3_t2v-gguf-api-8b-op.json`（8B），仅节点 131 三个下拉框不同
  - ✅ 已证明 prompt 逐字一致（sha256[:16] 同为 `2551bea3eb4a291f`，各 1449 字符）
  - ✅ 已证明生成**位级确定**：同 seed 同参数复跑，124/124 帧逐字节一致、SSIM=1.000000(inf)、PSNR=inf
  - ⏳ 未做：同 seed A/B 矩阵 ridge vs mlp（工作流不变，只切 `projection` 下拉框）
- [ ] **P2（独立议题）**：Turbo LoRA（4–8 步达 base ~20 步画质）。本地目前**无** H3 turbo LoRA。注意 `larryvrh/ComfyUI-MiniMax-H3-Turbo` 称 4 步替代 ~20 步，且「6–8 步明显好于 4 步，**超过 8 步不再变好反而开始过锐**」
- [x] ~~**待定（可不做）**：8B 去审查版自建（§11.3 末条）~~ —— **2026-09-30 取消自建，改用现成 `DreamFast/Qwen3-VL-8B-Heretic-1.3.0`**，见 §11.11

---

### 11.8 8B 变体文件集（2026-09-30 新建完成，只增不改、不覆盖）

> **设计原则**：8B 变体**只改 TE 三件套**（clip_name / type / projection），prompt、分辨率（T2V 0.98、I2V/R2V 0.5）、步数（20）、采样器、seed、卸载拓扑全部与 4B 逐字节一致——**刻意不做 P0 prompt / 0.98 修正**，保证 4B vs 8B 是严格单变量对照（覆盖此前"P0 修正打入 8B 文件"的旧意向；P0 修正如需，可在**下一轮**另建「合规 8B」变体）。
>
> **卸载设计全部保留**：每份工作流含 `ForceUnloadBeforeDecode` ×2（采样前卸 TE、解码前卸 DiT）；多段脚本每段前 `POST /free`。8B 编码器更重（编码期峰值 ≈11–12 GB，4B ≈3.6 GB），卸载是必需而非优化。

#### 11.8.1 UI/litegraph 工作流（ComfyUI UI 直接加载）→ `plan\molbal_workflows\final\8b\`

| 文件 | 节点/连线 | TE 节点 | 卸载节点 |
|---|---|---|---|
| `minimax_h3_t2v-gguf-8b.json` | 22 / 23 | #131 | #135 #136 |
| `minimax_h3_i2v-gguf-8b.json` | 26 / 31 | #137 | #145 #146 |
| `minimax_h3_ref2v-gguf-8b.json` | 27 / 29 | #137 | #157 #158 |

TE 三件套：`qwen3vl_8b_fp8_scaled.safetensors`（clip_name，**Comfy-Org stock**）/ `boogu`（type）/ `mmh3-8b-ClipProj-v3.1.safetensors`（projection）。除三下拉框 + loader 节点 title（"Text Encoder 8B (boogu)"）外，节点/连线/widgets 值与 4B 版逐字节一致（转换脚本断言拓扑）。

#### 11.8.2 API 格式工作流（/prompt 提交参考）→ `plan\API_workflows\8b\`

| 文件 | 节点数 | TE 节点 | 卸载节点 |
|---|---|---|---|
| `minimax_h3_t2v-gguf-api-8b.json` | 20 | #131 | #135 #136 |
| `minimax_h3_i2v-gguf-api-8b.json` | 24 | #137 | #145 #146 |
| `minimax_h3_ref2v-gguf-api-8b.json` | 24 | #137 | #157 #158 |

#### 11.8.3 脚本与启动器 → `plan\bat\`

| 文件 | 对应 4B | 差异 |
|---|---|---|
| `gen_h3_multisegment-8b.py` | `gen_h3_multisegment.py` | 去 docstring / 去 CLIP 三常量 / 归一模型注释后逐字节一致 ✓ |
| `gen_h3_multisegment-8b.bat` | `gen_h3_multisegment.bat` | 仅调用 `-8b.py`；UTF-8 无 BOM + CRLF + `chcp 65001` |
| `gen_h3_ref2va-8b.py` | `gen_h3_ref2va.py` | 同上 ✓ |
| `gen_h3_ref2va-8b.bat` | `gen_h3_ref2va.bat` | 仅调用 `-8b.py` |

脚本内嵌 API 图与 4B 版一致：两处 `ForceUnloadBeforeDecode` 节点 + `free_vram()`（每段前 POST /free）原样保留；docstring 注明 8B 显存含义（采样前卸 TE、解码前卸 DiT）。

#### 11.8.4 校验证据（2026-09-30）

- `py_compile` 通过（两份 `-8b.py`）
- 核心代码 diff：去 docstring / 去常量 / 归一注释后**逐字节一致**（difflib 精确比对）
- 8B 三常量就位；主体无 4B 常量残留
- 工作流转换脚本断言：非 TE 节点逐字节相等，TE 节点除三件套外其余输入相等
- bat：首字节 0x40（无 BOM）、纯 CRLF 无 LF-only、调用对应 `-8b.py`、含 `chcp 65001`
- 模型文件级验证（§11.7 已勾）：**`qwen3vl_8b_fp8_scaled.safetensors`** 10,588,637,512 B、`mmh3-8b-ClipProj-v3.1.safetensors` 41,990,896 B（+ `-mlp` 604,093,248 B），ComfyUI 下拉项已含 8B 三件套

#### 11.8.5 首次 8B 运行注意

- 编码期峰值 ≈11–12 GB（4B ≈3.6 GB），卡 24 GB；此前实测 GPU 另有 ≈7,246 MB 驻留未卸净 → **首跑前关掉其它 GPU 程序**，防分页
- ✅ 冒烟已完成（§11.7 P1.5）：`MiniMax_H3_00166_.mp4`（stock）/ `00168_`（stock 复跑）/ `00169_`（破限）三支均 success，864×480 / 124 帧 / aac 双声道
- Turbo LoRA（≈11.4 GB）是否下载：待用户拍板（§11.7 P2 独立议题）

---

### 11.9 官方 Prompt 合规版（op 系列，2026-09-30 新建完成，只增不改、不覆盖）

> **本轮定案（用户指示「用官方提示词」+「不覆盖旧文件」，方案自定）**：
> 1. 按官方 skill（`h3-prompt-writing` → `base-en.txt` 三段式 / `ref-en.txt` 六段式，本机 `~/.agents/skills/`）重写三套 prompt，删全部负向约束块、区间记法、计数类要求；
> 2. **修正时长硬伤**：UI T2V/I2V 原 `length=73`（≈3s @24fps）低于官方训练范围（124–362 帧 = 5–15s），且旧 prompt 时间线写 5s 与实际帧数不匹配 → 统一提到 **124≈5s**（官方默认值）。API 版经 `ComfyMathExpression(5s)` 本来就是 124，未动；
> 3. 生成 **4B-op（对照组）与 8B-op（主力档）两套**，同一段官方 prompt，仅 TE 三件套不同 → P2 A/B 直达（变量只有编码器）；
> 4. UI 与 API 各 6 份共 12 份新文件；脚本**不新建变体**（prompt 是运行时参数），另生成 3 份官方 prompt 模板 txt 供脚本 `--prompt-file` 复用。

| 档位 | UI（litegraph，ComfyUI 直接加载） | API（/prompt 提交参考） |
|---|---|---|
| 4B-op | `plan\molbal_workflows\final\4b\op\minimax_h3_{t2v,i2v,ref2v}-gguf-op.json` | `plan\API_workflows\op\minimax_h3_{t2v,i2v,ref2v}-gguf-api-op.json` |
| 8B-op（stock，主力） | `plan\molbal_workflows\final\op-8b\minimax_h3_{t2v,i2v,ref2v}-gguf-8b-op.json` | `plan\API_workflows\op-8b\minimax_h3_{t2v,i2v,ref2v}-gguf-api-8b-op.json` |
| **8B-op-heretic（破限备选）** | `plan\molbal_workflows\final\op-8b-heretic\minimax_h3_{t2v,i2v,ref2v}-gguf-8b-heretic-op.json` | `plan\API_workflows\op-8b-heretic\minimax_h3_{t2v,i2v,ref2v}-gguf-api-8b-heretic-op.json` |
| prompt 模板（txt） | `plan\bat\prompt_t2v_op.txt`（T2VA）· `prompt_fl2va_op.txt`（FL2VA）· `prompt_ref2va_op.txt`（ref2va 六段式） | 同左 |

**Prompt 对应关系**：T2V → T2VA 三段式（`integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music`）；I2V（fl2va 首/末帧）→ FL2VA 首行对齐指令 + 三段式；R2V（ref2va）→ 六段式（`subject_definitions` / `summary` / `retention_analysis` / `detailed_description` / `overall_soundscape` / `non_diegetic_music`）。

**校验证据（2026-09-30，difflib/脚本断言）**：
- UI 12 份（op ×3 + op-8b ×3）：节点/连线数与 4B/8B 基底一致（t2v 22/23、i2v 26/31、ref2v 27/29）；`ForceUnloadBeforeDecode` ×2 全部保留（#135#136 / #145#146 / #157#158）；T2V/I2V length 已 73→124
- 与基底 diff 仅白名单字段：生成节点 `widgets_values[0]`（prompt）+ T2V/I2V `widgets_values[3]`（length）；其余节点/连线/参数**逐字节一致**
- 8B TE 三件套抽查通过：**`qwen3vl_8b_fp8_scaled.safetensors / boogu / mmh3-8b-ClipProj-v3.1.safetensors`**
- 模板 txt 与工作流内嵌 prompt **逐字一致**（6 对全 True）
- 4B-op 与 8B-op 同一段 prompt（1449 / 1244 / 2748 字符），A/B 单变量成立

**用法**：日常跑 T2V → UI 加载 `op-8b\minimax_h3_t2v-gguf-8b-op.json`（或脚本 `--prompt-file plan\bat\prompt_t2v_op.txt`）；对照 4B-op 同一 prompt 验证收益。要破限版就换成 `op-8b-heretic\` 同名文件，脚本用 `gen_h3_multisegment-8b-heretic.bat` / `gen_h3_ref2va-8b-heretic.bat`。**破限版对 I2V/R2V 有视觉塔精度代价，默认仍用 stock（§11.11.4）。**

---

### 11.10 分辨率换算与耗时实测（2026-09-30 12:06 补测）

> **本节全部为本机实测**，来源：`plan\t2v_8b_060_4s_result.json`（本节 11.10.4/5）、`plan\t2v_4b_vs_8b_results.json`（0.4 MP 两支）、`plan\op_gpu_mem.csv`（300 点，3 秒间隔）。未修改任何已交付工作流，参数覆盖只在内存中进行。

#### 11.10.1 megapixels → 实际分辨率换算表

`comfy_extras/nodes_resolution.py` 的 `ResolutionSelector.execute`（L76-82）换算式：

```python
total_pixels = megapixels * 1024 * 1024      # 1024 基准，不是 10^6
scale  = math.sqrt(total_pixels / (w_ratio * h_ratio))
width  = round(w_ratio  * scale / multiple) * multiple
height = round(h_ratio * scale / multiple) * multiple
```

- `megapixels` 是 **0.1 ~ 16.0、步进 0.1 的浮点滑块**，不是枚举下拉
- `multiple` 本项目工作流统一设 **32**（节点默认 8）
- 取整到 32 倍数会引入漂移：**「0.5」实际是 0.522 MP，「0.9」实际是 0.942 MP**。要精确值只能看实际分辨率，反推不出来

**16:9（Widescreen）—— T2V / I2V 用**

| megapixels | 输出 | 实际像素 | 实际 MP | 备注 |
|---|---|---|---|---|
| 0.1 | 416×256 | 106,496 | 0.106 | |
| 0.2 | 608×352 | 214,016 | 0.214 | |
| 0.3 | 736×416 | 306,176 | 0.306 | |
| **0.4** | **864×480** | **414,720** | **0.415** | 本项目 4B/8B 对比实测档 |
| 0.5 | 960×544 | 522,240 | 0.522 | |
| **0.6** | **1056×608** | **642,048** | **0.642** | 本节补测档 |
| 0.7 | 1152×640 | 737,280 | 0.737 | |
| 0.8 | 1216×672 | 817,152 | 0.817 | |
| 0.9 | 1280×736 | 942,080 | 0.942 | |
| **0.98** | **1344×768** | **1,032,192** | **1.032** | 官方原生画布（= `MAX_PIXELS`） |
| 1.0 | 1376×768 | 1,056,768 | 1.057 | 官方文档点名跳过 |
| 1.2 | 1504×832 | 1,251,328 | 1.251 | 训练分布外 |

**9:16（Portrait）—— Ref2V 用**（0.1~0.9 与上表像素数完全相同，仅宽高互换）

| megapixels | 输出 | megapixels | 输出 |
|---|---|---|---|
| 0.4 | 480×864 | 0.8 | 672×1216 |
| 0.6 | 608×1056 | 0.9 | 736×1280 |
| 0.7 | 640×1152 | 0.98 | 768×1344 |

**其余 6 个宽高比 @ 0.4**：1:1→640×640、2:3→544×800、3:2→800×544、3:4→576×736、4:3→736×576、21:9→992×416

#### 11.10.2 修正：目标画布**没有任何上限钳制**

§11.7 P0 那张表的表头写「vs 上限 1,032,192」，容易被误读成代码里有硬钳制。**逐行核查源码后确认：没有。**

| 核查项 | 源码位置 | 结论 |
|---|---|---|
| `MAX_PIXELS = 768 * 1344` 出现次数 | `nodes_minimax_h3.py` L28（定义）、L57-58（`adapt_canvas` 内部） | 全文件仅此 3 处 |
| `adapt_canvas` 调用点 | 仅 **L316**，位于 `for name, video_frames in (ref_videos or {})` 循环内 | 只对**参考视频帧**归一化，与目标画布无关 |
| `EmptyMiniMaxH3LatentAV` | L108 `_empty_av_latent(width, height, length)` | `width/height` **原样**传递 |
| `MiniMaxH3ImageToVideo`（T2V/I2V） | L137 同上 | 同上 |
| `MiniMaxH3ReferenceToVideo`（R2V） | L288 同上 | 同上 |
| `_empty_av_latent` 内部 | L81-88，只做 `height // 16` / `width // 16` | **不校验面积** |

**结论**：填 1.0 就真的跑 1376×768，**不报错也不裁剪**。所以「超上限」的准确含义是「落在训练分布外」（官方文档的意思），**不是**「被静默降质」。0.98 之所以正好等于 1344×768，是 32 倍数取整恰好落回 768 短边，与钳制无关。

⚠️ 顺带纠正一条早期笔记误记：「1.0 MP 超限 24,576 px 会静默画质损失不报错」——**「静默画质损失」不成立**，ComfyUI 侧无此行为；风险是模型侧的分布外劣化，属未定义行为。

#### 11.10.3 时长 → 帧数：17k+5 网格，向上取整且静默

工作流里的官方表达式：先 `max(5, round(秒 × 24))`，再对齐到 `17k+5`（`n + (5 - n % 17) % 17`）。

| 输入秒数 | 帧数 | 实际时长 | 是否在训练范围 124–362 帧 |
|---|---|---|---|
| 3 | 73 | 3.042 s | ★越界 |
| **4** | **107** | **4.458 s** | **★越界（低于下限 124）** |
| **4.5** | **124** | **5.167 s** | 范围内 —— **要留在范围内的最小输入** |
| 5 | 124 | 5.167 s | 范围内（官方默认） |
| 6 | 158 | 6.583 s | 范围内 |
| 8 | 192 | 8.000 s | 范围内 |

- 训练下限 **124 帧 = 5.167 s**（`nodes_minimax_h3.py` L30 `FPS=24` + L34-37 `align_frame_count`，tooltip 见 L101/L127/L262）
- **要 5 秒以下的视频，最低只能传 4.5 秒**；传 4 秒会被拉到 4.458 秒且越界
- 合法网格共 15 个点（124~362 帧 = 5.167~15.083 s）；124 之下另有 7 个「合法但越界」点：5 / 22 / 39 / 56 / 73 / 90 / 107
- 坑：输入 110 或 120 都会被拉到 124 帧；输入 200 → 209 帧（8.708 s）。**取整是静默的，不报错、不告警**

#### 11.10.4 补测：T2V 8B @ 0.60 MP / 4 秒 = **588.0 秒（9 分 48 秒）**

| 指标 | 值 |
|---|---|
| 配置 | T2V / 8B-op / op 官方 prompt（1449 字符，sha256 `2551bea3eb4a291f`）/ seed 1104405517180391 / 20 步 / UNet `minimax_h3_fl2va_pruned-Q4_K_M.gguf` |
| 内存内覆盖 | 节点 115 `megapixels` = 0.6；节点 134 秒数 = 4 |
| **耗时** | **588.0 s = 9 分 48 秒** |
| 时间窗 | 11:56:25 → 12:06:14 |
| 分辨率 | **1056×608 = 642,048 px = 0.642 MP** |
| 帧数 / 时长 | **107 帧** / 24 fps / **4.458 s**（★越界） |
| 编码 | h264 / yuv420p + **aac 2ch 32000 Hz 4.450 s** |
| 文件大小 | 0.91 MB（`ComfyUI\output\video\MiniMax_H3_00167_.mp4`） |
| 显存峰值（WMI 口径，见 T2V 报告 §5.2 警告） | 21,473 MB |
| 启动前基线 | 7,355 MB（ComfyUI **未**重启，残留上一轮状态；对比 0.4 MP 那轮的干净基线 3,815 MB） |

**预算核对**：0.60 MP + 4.458 s = 9 分 48 秒 < 20 分钟，**达标**（余量 10 分钟）。

⚠️ **这条越界**：107 帧 < 训练下限 124 帧。**时长数据有效，但画质不代表正常水平**，不能与 0.4 MP 的 124 帧产物做画质对比。

#### 11.10.5 耗时模型：帧数比像素更吃时间

三个实测点：

| 配置 | 像素 | 帧数 | 耗时 |
|---|---|---|---|
| 4B @ 0.4 MP | 414,720 | 124 | 440.2 s（7.3 分） |
| 8B @ 0.4 MP | 414,720 | 124 | 443.8 s（7.4 分） |
| **8B @ 0.6 MP** | **642,048** | **107** | **588.0 s（9.8 分）** |
| 4B @ 0.98 MP | 1,032,192 | 124 | > 1,260 s（21.0 分，**未完成，取下界**） |

按 `t = a · 像素^b · 帧数^c` 反解：

- 像素指数 **b = 1.144**（同 124 帧，0.4 vs 0.98；因 0.98 那条是下界，**b 也是下界**）
- 帧数指数 **c = 1.484**

**这修正了此前只按像素拟合的结论**。0.6 MP 配 4.458 秒只要 9.8 分钟并不矛盾 —— 帧数同时从 124 掉到 107，两者部分抵消。

**按修正后模型预测（5.167 s = 124 帧）**：

| megapixels | 分辨率 | 预测耗时 | 占 20 min 预算 |
|---|---|---|---|
| 0.4 | 864×480 | 7.4 分 | 37% |
| 0.5 | 960×544 | 9.6 分 | 48% |
| 0.6 | 1056×608 | 12.2 分 | 61% |
| 0.7 | 1152×640 | 14.3 分 | 71% |
| 0.8 | 1216×672 | 16.1 分 | 80% |
| 0.98 | 1344×768 | 21.0 分 | 105%（超预算） |

⚠️ **c 不可信**：b 与 c 是从同一组数据里硬拆出来的，误差会放大。**要拿干净曲线，就固定 124 帧只扫分辨率**（0.6 和 0.8 各一条，预计 12.2 / 16.1 分钟，共约 28 分钟）—— 这样 b 有两个同帧数实测点，不需要靠越界数据反解。

#### 11.10.6 画质（已由 vision-deepseek 判定，2026-09-30 12:31~12:37）

完整记录见 **`plan\vision_qc_识图结论.md`**。抽帧用 `plan\bat\gen_h3_qc_frames.py`（ffmpeg），识别走 `vision-deepseek`。

| 结论 | 置信度 |
|---|---|
| **0.40 MP 不糊** —— 文字可读且拼写全对，雕塑/棕榈树可辨。属"能看"，不是"高清" | 高 |
| **三支都完整生成 4 个分镜，提示词跟随度不是瓶颈** —— 末帧逐字母核对 `D-I-R-E-C-T-E-D B-Y C-O-M-F-Y-U-I` 全对 | 高 |
| **0.60 MP 的几何细节提升真实** —— 卷发纹理、五官轮廓、棕榈叶线条明显增多，剥离 RGB 风格因素后仍成立 | 中高 |
| **4B vs 8B 优劣方向不一致，仍无法排名** —— 中段帧判 8B 领先，末帧判 4B 色散更轻 | — |
| **瓶颈在扩散模型对文字的空间控制力**，不在分辨率、也不在文本编码器容量 | 中 |

**方法论教训（两条，都已踩过）**：

1. **稀疏抽帧拼图不能判定分镜完整性。** 第一轮 6 帧拼图误判「0.60 MP 那支缺少结尾分镜」，第二轮改用 `-sseof -0.1` 抽末帧单图验证，推翻该结论。拼图只适合判清晰度和整体风格；分镜/时间轴问题必须定点单帧。
2. **提示词明确要求的视觉效果不能当缺陷评分。** op prompt 明确写了 `RGB chromatic aberration` / `RGB split` / `VHS tracking artifacts`，所以 RGB 分离是**风格不是缺陷**。两轮识图都没区分开——第一轮把 RGB 分离当压缩伪影批评，第二轮把"少了 RGB 分离"当质量最高。做画质排序必须先剥离这一项。

**顺带得到一条甜点判据**：Shot 4 从 00:04.000 开始，124 帧给它 **1.167 s = 28 帧**，107 帧只给 **0.458 s = 11 帧**。**甜点必须按 124 帧固定扫分辨率，不要靠缩短时长换分辨率** —— 否则分镜会被压变形。

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
- CCTech Suite 本地代码：`nodes/extra.py`（CCTechClipProjLoader:74）、`nodes/gguf.py`（UnetLoaderGGUF:317）、`vendor/clipproj.py`（`detect_arch`、`_ARCH_BY_DIM`:73、`_MERGER_KEYS`:75）

---

### 11.11 破限 8B 文本编码器（Heretic v1.3.0）落地与 A/B 实测（2026-09-30 13:00~13:20）

> **本节全部为本机实测 + 一手仓库核实**。原始数据：`plan\ab_8b_heretic_results.jsonl`（生成记录）、`plan\ab_8b_heretic_full.json`（含比对）、`plan\ab_8b_heretic_metrics.json`（三组客观指标）。

#### 11.11.1 起因：原判断被推翻

§11.3 原写「去审查 8B **无人发布其 ComfyUI 单文件版**，需自行合并重打包，列为可选非必需」。**联网复查后此判断作废**：

`DreamFast/Qwen3-VL-8B-Heretic-1.3.0` 提供 `comfyui/` 子目录三档量化，**均为 ComfyUI 单文件 safetensors、自带视觉塔**：

| 文件 | 字节数 | 折合 | 说明 |
|---|---:|---:|---|
| `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | 10,017,064,632 | 9.33 GiB | **本机采用**（`fp8_e4m3fn` 裸 float8） |
| `qwen3-vl-8b-heretic-1.3.0.safetensors` | 17,534,334,584 | 16.33 GiB | 纯 bf16 |
| `qwen3-vl-8b-heretic-1.3.0_nvfp4.safetensors` | 6,728,389,136 | 6.27 GiB | nvfp4（AMD 需验证） |

同仓库 **GGUF 版会剥离视觉塔**，8B 侧**没有 mmproj 供应** → 只能走 safetensors，否则 I2V/R2V 不可用。

#### 11.11.2 两个 8B 文件的结构对拍（直接读 safetensors header，非查文档）

| 项 | T2 `qwen3vl_8b_fp8_scaled` | T2b `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn` |
|---|---|---|
| 字节数 | 10,588,637,512 | 10,017,064,632 |
| 张量总数 | **1,254** | **750** |
| dtype 分布 | BF16×498 + F32×252 + F8_E4M3×252 + U8×252 | BF16×382 + **F8_E4M3×368** |
| 量化封装 | `fp8_scaled` = U8 载荷 + 独立 fp32 `weight_scale`（故张量数是裸 fp8 的 1.67 倍） | 裸 `fp8_e4m3fn`，无 `weight_scale` |
| 语言塔层数 | 36（`model.layers.0..35`，每层 11 个张量） | 36（同） |
| 语言塔 dtype | F8_E4M3×252 + BF16×144 | **完全相同** |
| 视觉塔张量数 | 351 | **351（未被剥离 ✅）** |
| **视觉塔 dtype** | **BF16×351（全满精度）** | **BF16×235 + F8_E4M3×116** |
| 被降精度的具体张量 | — | `attn.qkv.weight` / `attn.proj.weight` / `mlp.linear_fc1.weight` / `mlp.linear_fc2.weight`（27 blocks）+ `merger.linear_fc1/fc2` + `deepstack_merger_list.{0,1,2}.linear_fc1/fc2` |
| `embed_tokens` / `lm_head` / `norm` | BF16 | BF16（相同） |
| 名称集合差异 | 多 504 个 `*.weight_scale`（量化元数据） | — |
| 同名张量 shape | — | **116 个仅 dtype 不同，shape 全部相同** |

**结论**：
1. **语言塔（真正产出文本 conditioning 的部分）两者格式等价** —— 7 个线性投影 × 36 层 = 252 个 F8_E4M3 相同，其余 BF16 归一化相同。
2. **视觉塔有真实精度代价** —— 破限版把 27 个 block 的 qkv/proj/fc1/fc2 全降到 fp8。这对 **T2V 无影响**（视觉塔不参与），对 **I2V/R2V 是实打实的图像条件编码精度损失**。
3. 作者自述「abliterated TE 单独使用不显著改变输出质量」指的是**语义质量**，与下面的像素级实测不矛盾。

#### 11.11.3 A/B 实测：单变量、含噪声地板对照

**设计**：同 seed `1104405517180391`、同 prompt（sha256[:16] = `2551bea3eb4a291f`，1449 字符）、同 0.40 MP / 5 s / 20 步 / 同 UNet，**唯一变量 = 节点 131 的 `clip_name`**（两工作流逐节点 diff 只差节点 131，已校验）。ComfyUI 重启后跑，队列排空再开跑。

| 组 | TE | 产物 | 耗时 | 帧数/规格 |
|---|---|---|---:|---|
| 历史组（上一轮） | `qwen3vl_8b_fp8_scaled` | `MiniMax_H3_00166_.mp4` | 443.8 s | 864×480 / 124 帧 / 5.167 s / 834,346 B |
| **AB-CTRL（对照组）** | `qwen3vl_8b_fp8_scaled` | `MiniMax_H3_00168_.mp4` | **451.0 s** | 同上 / 834,346 B |
| **AB-TEST（破限）** | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn` | `MiniMax_H3_00169_.mp4` | **442.0 s** | 同上 / 808,203 B |

**三组客观指标**（逐帧 sha256 + ffmpeg SSIM/PSNR）：

| 对比 | 逐帧一致 | SSIM (All) | PSNR (avg) | 说明 |
|---|---|---|---|---|
| **噪声地板**：00166 vs 00168（同 TE 复跑） | **124/124 = 100%** | **1.000000 (inf)** | **inf** | ✅ **证明生成位级确定，运行间噪声为零**，后续差异全部是真实效应 |
| **TE 效应**：00168 stock vs 00169 破限 | **0/124 = 0%** | **0.826398** | **21.879 dB** | 逐帧 SSIM min 0.4326（第 1 帧）/ max 0.9268 / mean 0.8264；逐帧 PSNR min 12.58（第 106 帧）/ max 28.39 / mean 23.76 |
| 交叉验证：00166 vs 00169 | 0/124 | 0.826398 | 21.879 dB | 与上行**数值完全相同** —— 因 00166≡00168，进一步佐证测量无噪声 |

**这组数据能证明什么、不能证明什么**：

| 结论 | 判定 |
|---|---|
| 破限 TE **不是** no-op，**每一帧都变了** | ✅ **确定**。0/124 一致，SSIM 0.826 远低于「同画面不同编码」的 0.95+ 区间 |
| 破限版**不引入运行抖动** | ✅ **确定**。位级确定，耗时 442.0 s 落在 stock 区间 {443.8, 451.0} 内或更低 |
| 破限版**画质更好/更差** | ❌ **无法判定**。SSIM/PSNR 是「两张不同的图有多像」，**不是「哪张更好」**；两者都不是 ground truth，分数高低无意义 |
| 破限版在**边界 prompt** 上不拒答 | ⚠️ **未测**。当前用的是完全良性的官方 prompt，两版都不可能拒答。要证明价值需构造会触发过滤的 prompt 对比拒答率 |
| 破限版对 **I2V/R2V** 无损 | ❌ **已证伪**。视觉塔 116 个张量降到 F8_E4M3（§11.11.2） |

> ⚠️ **撤回一条此前的错误结论**：13:20 我曾口头汇报「破限版显存峰值 7,462 MB，比 stock 20,614 MB 下降 63.8%」。**该数字无效** —— 采样线程因首轮结束时未复位 `_stop` 而从未启动（记录中 `gpu_mem_samples=0`，峰值恰好等于地板值 7,462 MB）。**显存排名仍需在 ComfyUI 进程内用 `torch.cuda.max_memory_allocated()` 打点**（与 §5.2 的 WMI 口径问题同源）。

**唯一可信的显存口径是 ComfyUI 自己的 staged 日志**：

| TE | ComfyUI 日志 | 判读 |
|---|---|---|
| stock | `BooguTEModel_ prepared ... 10097MB Staged` → `loaded completely; 14753.38 MB usable, 11186.65 MB loaded, full load: True` | staged < usable → **可完全驻留显存** |
| 破限 | `BooguTEModel_ prepared ... 16721MB Staged` → `loaded completely; 14542.38 MB usable, 11186.65 MB loaded, full load: True` | **staged 16,721 MB > usable 14,542 MB** → **无法完全驻留，必须走系统内存分页** |

破限版 staged 反而**多 6,624 MB（+65.6%）**。一个**待验证的假设**：8B 参数 × 2 bytes ≈ 16 GB，与 16,721 MB 数量级吻合 —— ComfyUI 对裸 `fp8_e4m3fn` 可能没有原生反量化快路径，向上转到了 bf16；而 `fp8_scaled` 有 U8+scale 的原生路径故只需 10,097 MB。**此为假设，未验证**，但对 24 GB 卡是实打实的风险：I2V/R2V 场景下 TE 与 DiT 都要抢显存，分页会拖慢并可能 OOM。

#### 11.11.4 选型建议

| 场景 | 建议 | 理由 |
|---|---|---|
| **日常 T2V / I2V / R2V（默认）** | **stock `qwen3vl_8b_fp8_scaled`** | 视觉塔满精度；staged 10,097 MB 可完全驻留；已实测跑通（00166/00168） |
| **纯 T2V + 明确要用边界 prompt** | 可切破限版 | 视觉塔不参与，精度代价为零；耗时无差异 |
| **I2V / R2V** | **不要用破限版** | 视觉塔 fp8 化是真实损失，且 staged 超出可用显存需分页 |
| 想要更小体积 | `..._nvfp4.safetensors`（6.27 GiB） | **AMD/ROCm 需先验证**，未测 |

**切换方式**：节点 #131 只改 `clip_name`（`type` 三档都是 `boogu`，`projection` 共用），或直接加载 `op-8b-heretic\` 下的工作流。旧 `op-8b\` 全部原样保留为回滚锚点。

#### 11.11.5 新增文件清单（只增不改、不删、不移、不改名）

**模型**
```
models/text_encoders/qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors   10,017,064,632 B
```

**UI 工作流** → `plan\molbal_workflows\final\op-8b-heretic\`
```
minimax_h3_t2v-gguf-8b-heretic-op.json      33,528 B   22 nodes
minimax_h3_i2v-gguf-8b-heretic-op.json      40,121 B   26 nodes
minimax_h3_ref2v-gguf-8b-heretic-op.json    44,154 B   27 nodes
```

**API 工作流** → `plan\API_workflows\op-8b-heretic\`
```
minimax_h3_t2v-gguf-api-8b-heretic-op.json     7,966 B
minimax_h3_i2v-gguf-api-8b-heretic-op.json     9,563 B   TE 节点 #137
minimax_h3_ref2v-gguf-api-8b-heretic-op.json  10,776 B   TE 节点 #137
```

**脚本** → `plan\bat\`
```
gen_h3_multisegment-8b-heretic.py / .bat
gen_h3_ref2va-8b-heretic.py / .bat
```

**数据与日志** → `plan\`
```
ab_8b_heretic_results.jsonl      两条生成记录（含无效的显存字段，已在 §11.11.3 标注）
ab_8b_heretic_full.json          生成 + 比对原始记录
ab_8b_heretic_metrics.json       三组逐帧 sha256 / SSIM / PSNR（干净重算版，以此为准）
ab_8b_heretic_compare.json       逐帧哈希部分
ab_8b_heretic_run.log / .err.log A/B 运行日志
ab_metrics.log / .err.log        指标重算日志
comfyui_restart_heretic.log / .err.log   重启后 ComfyUI 日志（staged 行出处）
bat\dl_8b_heretic.log / .err.log          aria2 下载日志
```

**校验结论**：
- 6 份新工作流：旧 TE 名残留 **0**，新 TE 名出现 **1**；JSON 全部可解析
- 2 份新 `.py`：`py_compile` 通过
- 旧文件（`op-8b\*` 6 份 + `gen_h3_*8b.py` 2 份）：旧名 ≥1、新名 **0**，时间戳未变 → **回滚锚点完好**
- 新旧 T2V API 工作流逐节点 diff：**差异节点仅 131**

---

### §11 文本编码器选型引用（2026-09-30 联网核实）

- 官方 H3 仓库与架构说明（Qwen3-VL-32B 截断至 50 层 / H3-Context-IR 重要性）：`github.com/MiniMax-AI/MiniMax-H3`
- **官方三段 prompt 规范**（本机 skill 同源）：`~/.agents/skills/h3-prompt-writing/references/base-en.txt`、`ref-en.txt`；安装源 `npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --skill h3-prompt-writing`
- **视觉塔三档规格**（depth 24/27/27、hidden 1024/1152/1152、deepstack [5,11,17] vs [8,16,24]）：`huggingface.co/Qwen/Qwen3-VL-4B-Instruct/raw/main/config.json`、`…/Qwen3-VL-8B-Instruct/…`、`…/Qwen3-VL-32B-Instruct/…`
- **T2 编码器下载源**（fp8_scaled，ComfyUI 单文件，自带视觉塔）：`huggingface.co/Comfy-Org/Qwen3-VL` → `text_encoders/qwen3vl_8b_fp8_scaled.safetensors`（10,588,637,512 B）
- **T2b 破限编码器下载源**（fp8_e4m3fn，ComfyUI 单文件，自带视觉塔）：`huggingface.co/DreamFast/Qwen3-VL-8B-Heretic-1.3.0` → `comfyui/qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`（10,017,064,632 B）。同仓库另有 `16.33 GB` 纯 bf16 版与 `6.27 GB` nvfp4 版；**GGUF 版会剥离视觉塔，不可用**。详见 §11.11
- **8B 投影矩阵**：`huggingface.co/NicoLab28/ClipProj-MiniMax-H3` → `mmh3-8b-ClipProj-v3.1.safetensors`（另有 `-mlp` 残差版、`-celeb` 名人增强版；测试余弦表见其 README）
- **不升 32B 的证据 A**：32B Ultra-Heretic H3 ComfyUI INT8 ConvRot（24.55 GiB、峰值 ≈24.7 GiB、`weight_g` 键名风险）：`huggingface.co/ethanfel/Qwen3-VL-32B-Ultra-Heretic-H3-ComfyUI-INT8-ConvRot`（源自 `llmfan46/Qwen3-VL-32B-Instruct-ultra-uncensored-heretic`，Heretic v1.2.0，4/100 拒绝 vs 原版 99/100）
- **不升 32B 的证据 B**（作者明确禁止用于图像/首末帧/参考输入；recovered 8B INT8 峰值 6.18 GiB；三编码器 vs 官方 32B 的 teacher 余弦 0.9387）：`huggingface.co/SearchingMan/MiniMax-H3-Text-Encoders`
- **不升 32B 的证据 C**（297 次语音 + 405 次图像渲染；归一化到换 seed 波动后 4B 与 8B 分不开；3s/7s 硬切三编码器全未通过）：`huggingface.co/NicoLab28/ClipProj-MiniMax-H3` 的 `bench3.1/README.md`
- **「无道德约束」伪需求依据**（abliterated fp8 vs bf16 校准矩阵的 conditioning 余弦差仅 0.0023）：同上 ClipProj README
- **破限 8B 行为数据**（trial 98；原版拒答 100/100 → 6/100；拒答率 71.5% → 服从 99.0%；KL 0.0314；改 53/398 个张量；TruthfulQA −11.7%）：`huggingface.co/DreamFast/Qwen3-VL-8B-Heretic-1.3.0` README。其自述要点：abliterated TE **单独使用不显著改变输出质量**，完整用法需配 LoRA；GGUF 版剥离视觉塔
- 去审查 8B 其它上游（**transformers 分片，需自行合并重打包**）：`huggingface.co/heretic-org/Qwen-3-VL-8B-Instruct-heretic`、`huihui-ai/Qwen3-VL-8B-abliterated`（transformers 格式，**本机 ComfyUI 不可直用**）、`Kizzington/*`（同上）
- 8B GGUF 备选（含 `mmproj-Qwen3VL-8B-Instruct-F16.gguf`，官方非去审查）：`huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF`
- ComfyUI 原生 H3 编码器路径（无需自定义节点）：`comfy/sd.py:1674` `detect_te_model`、`:1924-1926` `QWEN3VL_32B → text_encoders.minimax.te`、`comfy/text_encoders/minimax.py`（三段拼接规则 / adaLN tag 0-1）
- AMD Navi31 上 sage 比 PyTorch SDPA 慢 30–34%（故 §10.6 否决 `--use-sage-attention`）：AMD ROCm / Ryzen AI 官方性能文档
