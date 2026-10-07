# MinimaxH3-7900xtx

**Win11 + 32GB RAM + AMD RX 7900 XTX (24GB ROCm)：使用 ComfyUI 本地运行 MiniMax H3 视频生成（T2V / I2V / R2V）的极致优化部署方案。**

> 本仓库仅记录 MiniMax H3 相关。所有内容源自 `D:\localAI\ComfyUI-last\ComfyUI_windows_portable`（最终优化版）与
> `D:\localAI\ComfyUI_windows_portable`（原版未初始化）的实机对比 + `plan\` 下实测文档。目的：**快速换机后一键照此重部署**。

---

## 一、成果基线（已实测收敛，勿再折腾）

| 项 | 结论 |
|---|---|
| 分辨率 | **480P（864×480）**，0.4MP 档 x20步 |
| 时长 | **5s（124 帧）= 绝对甜点档**（日常主力）；10s 仅备用（显存逼近红线、耗时 ≈ 优化前40–45min vs 5s ≈ 10min） |
| steps | **20（对比实测档）；10 或 12 亦可**（官方模板默认 12；10 步与 20 步肉眼几乎无差） |
| cfg | **1.0**（H3 是蒸馏模型，cfgd >1.0 可能直接中止） |
| sampler / scheduler | `res_multistep` / `simple` |
| 速度参考 | 5s 一轮 ≈ 9.5min（采样 ~26.6s/it 恒定 + 解码 ~30s）；480P/10s/20 步长提示词 40–45min，比最初同条件快近一倍 |
| 显存纪律 | **任意时刻只驻留一个「大件」**（编码器 / 扩散模型 / VAE），靠顺序执行自动卸载，全程不触发 swap |

**8B 分辨率档位实测**（2026-09-30：8B stock 编码器 / 同一套长提示词 / 20 步 / 随机种子 / **全程不爆显存、不触发 swap**）：

| MP 档 | 分辨率 | 时长 | 实测耗时 |
|---|---|---|---|
| 0.4 | 864×480 | 5s（124 帧） | **450 s ≈ 7.5 min** |
| 0.6 | 1056×608 | 5s（124 帧） | **630 s ≈ 10.5 min** |
| 0.7 | 1152×640 | 5s（124 帧） | **771 s ≈ 12.9 min** |
| 0.9 | 1280×736 | 4s（107 帧 ⚠️ 低训练下限 124） | **846 s ≈ 14.1 min ★ 几乎极限** |

MP 档位 ↔ 16:9 分辨率对应（Plan §11.10.1）：0.98→1344×768 · 0.9→1280×736 · 0.8→1216×672 · 0.7→1152×640 · 0.6→1056×608 · 0.5→960×544 · 0.4→864×480。
**8B 上限经验值：0.9 MP × 4s ≈ 846s 已近边界，再高档位（0.98 / 1344×768）会触发 swap；日常建议 ≤ 0.7 MP × 5s。**

**为何不用 Turbo LoRA 加速（决策依据，2026-09-30）**：

- **≥0.7MP 档：显存就是硬门槛**。24GB 已接近极限（上表 0.9MP 档即近边界），Turbo LoRA 实测额外占用 **≈1.6GB VRAM**（AICU/ComfyPods 复测：1344×768 下 17,316 → 18,882 MiB，且「Turbo 用 VRAM 换速度，不省内存」）→ 本机 8B + 高分辨率下**必触发 swap**，数据交换开销 > 步数缩短收益（20→4 步），**得不偿失**。
- **0.4MP 档：显存允许，但仍不值得**。8B 编码期峰值仅 ~11–12GB，+1.6GB 不触发 swap——显存上完全放得下；否决理由与显存无关：① Turbo 的质量劣化**不挑分辨率**（细节合并成大色块、运动需额外调 Shift 才保持锐利、issue #16382 伪影）在 0.4MP 一样发生；② 本机已实测 **10/12 步与 20 步肉眼几乎无差**，10 步近乎无损省一半时间（450s→~270s），Turbo 4 步仅再多省 **~2 分钟**——为省 2 分钟牺牲动作/细节质量，**这笔账不划算**。

结论：**本机（24GB）不用 LoRA 加速，以「不爆显存、不 swap、保质量」为第一优先**。若换机为 48GB+ 高档卡，可重新评估（Turbo 定位是试错草稿，成品仍建议标准 20 步）。

---

## 二、环境基线

- ComfyUI `ComfyUI_windows_portable`，**核心已升级至 v0.38.0**（commit `fb2315f1`，2026-09-29）。⚠️ 早期所有验证基于 v0.34.0，实机现已前移，H3 结论需在 0.38.0 上复核
- 注意力内核 `comfy-kitchen 0.2.36`（HIP int8 backend，**有回归 bug，见 §4.1 / §8**）
- 推理后端 `torch 2.9.1+rocm7.2.1` / HIP 7.2.53211，识别为 AMD RX 7900 XTX（ROCm）
- system RAM ≥ 31GB（本机 31.9GB 验证），config 页文件保余量

---

## 三、架构决策（为什么能跑）

MiniMax H3 官方用 Qwen3-VL-**32B** 编码器，官方 safetensors 为 **NVFP4/AWQ（Blackwell 专属，AMD 不可用）**，且 24GB 下与扩散模型同驻必溢出 → **排除 32B 路线**。

**采用 ClipProj 路线**：编码器 + 学习好的线性投影，映射到 32B 条件空间：

```
cond = ((h - mean_in) / std_in) @ W * std_out + mean_out
```

**双档文本编码器**（2026-09-30 起 I2V/R2V 主力已切 8B；4B 保留作 T2V 快档），均由 CCTech `CCTechClipProjLoader` 单节点加载 + 投影，输出标准 `CLIP`，下游 H3 节点连线不动：

| 档 | 用途 | 文本编码器 | 投影矩阵 | type | 磁盘 |
|---|---|---|---|---|---|
| **T1 4B** | T2V 快档 | `qwen3-vl-4b-heretic-Q4_K_M.gguf` + 同名 mmproj（视觉塔） | `mmh3-4b-ClipProj-v3.1.safetensors`（25MB） | `krea2` | 3.1GB |
| **T2 8B** | **I2V / R2V 主力**（同跑 T2V） | `qwen3vl_8b_fp8_scaled.safetensors`（Comfy-Org stock，**自带视觉塔，无需 mmproj**） | `mmh3-8b-ClipProj-v3.1.safetensors` | `boogu` | 10.6GB |
| **T2b 8B 破限** | T2V 破限备选 | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`（DreamFast v1.3.0，视觉塔降 F8_E4M3） | 同 T2 | `boogu` | 9.33GB |

三档互切只改三个下拉框（`clip_name` / `type` / `projection`，详见 plan 文档 §11.4）。⚠️ T2b 视觉塔 116 个张量被降到 F8_E4M3，对 I2V/R2V 是真实精度代价 → **破限只用于 T2V，I2V/R2V 默认 T2 stock**（实测 §11.11）。

三段驻留（顺序执行即自动清场，详见 plan 文档 §5）：编码器 → 采样模型 → video+audio VAE，每次加载新大件时 ComfyUI 自动踢出最旧的那个

---

## 四、从原版 → 优化版的全部修改（换机照抄）

> 原版 = 官方 portable 同版本（**core v0.34.0 / 92 个 pip 包 / 无 custom_nodes**）。优化版 = core v0.34.0 / 146 个包。逐项差异如下。

### 4.1 启动脚本（portable 根目录）

> **⚠️ 硬规则：只能同时开一个 ComfyUI。** 同时开两个会内存爆掉、系统直接卡死。
> 切换用途（生图 ↔ 生视频）必须**先完全关掉旧实例**（`Get-Process python | Stop-Process -Force`），
> 确认 8188 不再监听，再起新的。启动前先探：
> ```powershell
> if ((Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue) -or (Test-NetConnection 127.0.0.1 -Port 8188 -InformationLevel Quiet)) { "已在运行，别再起" } else { 启动对应脚本 }
> ```

| 用途 | 启动脚本 | `--use-ck-attention` |
|---|---|:---:|
| **MiniMax H3 生视频**（t2v / i2v / ref2v） | `run_amd_gpu_enable_dynamic_vram.bat` | ✅ 开 |
| **Qwen-Image 2.1 生图**（t2i / edit / 抠图） | `run_amd_gpu_no_ck_attention.bat` | ❌ 关 |

**两个脚本都带 `--enable-dynamic-vram`** —— 动态显存是 OOM 的关键，这条不变；区别**只在 ck 开关**，所以别认错脚本。

**`run_amd_gpu_enable_dynamic_vram.bat`**（**H3 生视频主力**；`--enable-dynamic-vram` 在 ROCm <7.14 需手动开启，官方 7.14+ 才默认启用，本机 ROCm 7.2.1 必须加）：
```bat
%PYTHON% -s %TARGET% --windows-standalone-build --enable-dynamic-vram --disable-pinned-memory --fp16-intermediates --disable-smart-memory --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
```

**`run_amd_gpu_no_ck_attention.bat`**（**Qwen-Image 2.1 生图**——去掉 `--use-ck-attention`，其余逐字与主力一致，保证 A/B 可比。⚠️ 必须用它跑 Qwen-Image，理由见参数表 `--use-ck-attention` 行与 §8）：
```bat
%PYTHON% -s %TARGET% --windows-standalone-build --enable-dynamic-vram --disable-pinned-memory --disable-smart-memory --reserve-vram 6 --disable-api-nodes --cache-none --fp16-intermediates
```

**常驻进程的启动方式**（裸挂管道会卡死 opencode 会话，必须重定向输出）：
```powershell
Start-Process -FilePath "cmd.exe" -ArgumentList "/c","run_amd_gpu_enable_dynamic_vram.bat" `
  -WorkingDirectory "D:\localAI\ComfyUI-last\ComfyUI_windows_portable" `
  -RedirectStandardOutput "C:\Users\GAME\AppData\Local\Temp\opencode\comfyui.log" `
  -RedirectStandardError  "C:\Users\GAME\AppData\Local\Temp\opencode\comfyui.err.log" -PassThru -WindowStyle Hidden
```
（用 `/c` 不是 `/k`：脚本末尾有 `pause`，`/k` 会留下一个挂着的窗口。）启动后轮询 `http://127.0.0.1:8188/system_stats` 直到 200，首次启动要加载模型通常 1–2 分钟。

**`run_amd_gpu.bat`**（**已弃用**，仅保留原版 `.bak` 作对照，勿再日常使用）：
```bat
@echo off
set PYTHON=.\python_embeded\python.exe
set TARGET=ComfyUI\main.py
%PYTHON% -s %TARGET% --windows-standalone-build --disable-pinned-memory --fp16-intermediates
pause
```

关键参数的实测意义：
- `--disable-pinned-memory`：Windows 默认锁 40% 系统 RAM（31.9GB→12.8GB）供 offload DMA，禁用后归还 → **10s 不再爆显存**（仅降低内存消耗，**内存耗尽仍会崩溃**，非根治）
- `--fp16-intermediates`：中间张量用 fp16，降内存压力
- `--enable-dynamic-vram`：dynamic VRAM 在 ROCm 7.14+ 才默认开启，本机 7.2.1 需手动加参启用
- `--disable-smart-memory`：强制激进卸载到系统内存（不尽量驻留显存），配合 dynamic-vram 进一步压低驻留
- `--reserve-vram 6`：预留 6GB 显存给 OS/桌面软件，避免生成期间切桌面卡顿/驱动超时
- `--disable-api-nodes`：不加载 API 节点 + 前端不联网；`/prompt` 提交不受影响，plan 脚本照常可用
- `--cache-none`：不缓存节点执行结果（每次运行全部节点重算），降 RAM/VRAM 占用，代价是重复执行
- `--use-ck-attention`：启用 **Comfy Kitchen attention**（int8 内核，`comfy_kitchen` 0.2.36，本机 HIP 后端实测可用）。⚠️ **双重风险**：(1) 该参数**不是 fallback**——`comfy_kitchen` 缺失或 kernel 不支持时会打印错误并**直接退出**（`attention.py:918 exit(-1)`），本机已验证 `hip int8 avail: True`；(2) ⚠️⚠️ **0.2.36 有正确性回归**——token 数跨过 **64**（HIP 核 tile 宽度）时输出崩坏，**Qwen-Image 2.1 已确认**（绿/紫伪影、无异常抛出）。**Qwen-Image 请用 `run_amd_gpu_no_ck_attention.bat`**；**MiniMax H3 已实测确认安全**（2026-10-02 受控 A/B：124 帧 SSIM 0.98849、平均像素差 0.9125/255、锐度 +5.50%、端到端 1.54x，四路判据全排除崩坏；H3 文本编码器另经源码核实不受影响）。完整证据链见 `plan\CK注意力回归问题调查报告.md` + `plan\ck_ab_20261002\` + `Plan.md §12`
- ⚠️ **不要上 `--lowvram/--novram`**（把权重卸到系统内存徒增 swap）；**不要 `--use-sage-attention`**（AMD 无支持 + H3 全局 sage 出纯噪声，issue #15263）

### 4.2 自定义节点（custom_nodes/）

| 节点 | 来源 / 版本 | 必需? | 用途 |
|---|---|---|---|
| **ComfyUI-GGUF-Loader** | `github.com/ChrisColeTech/ComfyUI-GGUF-Loader` **v2.16.7** | ✅ | `UnetLoaderGGUF`（扩散模型 GGUF）、**`CCTechClipProjLoader`**（编码器+投影，`nodes/extra.py`） |
| **ComfyUI-ForceUnloadBeforeDecode** | 自建单文件节点 | ✅ | 解码前 `unload_all_models()`，治 #15484 co-residency 抖动，解码提速关键 |
| ComfyUI-KJNodes | `github.com/kijai/ComfyUI-KJNodes`（5710537，含 minimax 音频预览） | 可选 | 三套工作流未直接引用，装上无害 |
| ComfyUI-ClipProj | nicolab28（c01ba8f） | ❌ | 已装但工作流用 CCTech 内置；按文档建议可不装 |

克隆走镜像：`git clone https://v4.gh-proxy.org/https://github.com/ChrisColeTech/ComfyUI-GGUF-Loader.git`

**ComfyUI-GGUF-Loader 依赖（python_embeded）**：
```bat
python_embeded\python.exe -m pip install gguf==0.19.0 sentencepiece protobuf qwen-tts timm -i https://mirrors.aliyun.com/pypi/simple/
```

**⚠️ 安装后必做修复（否则整包被 ComfyUI 静默跳过）**：
CCTech import 链 `krea2.py → vendor/depth_anything_v2.py` 硬依赖 `cv2`。缺失时整个包被跳过，前端报「缺失节点包 ComfyUI-GGUF」。
```bat
python_embeded\python.exe -m pip install opencv-python-headless -i https://mirrors.aliyun.com/pypi/simple/
```
> 清华源对该 wheel 返回 403，**必须阿里云源**。装完重启，日志应见 `[CCTech Suite]: Activated 73 GGUF loader nodes`。

### 4.3 python 环境（pip 差异摘要）

- 相对原版（同 v0.34.0）新增 **53 个包**，来源即：CCTech 依赖（`gguf`、`sentencepiece`、`protobuf`、`qwen-tts`、`timm`、`opencv-python-headless`）+ ComfyUI-Manager 全套（fastapi、uvicorn、GitPython、PyGithub、PyJWT、PyNaCl、orjson、gradio 等）+ Qwen3-TTS 系（accelerate、soundfile、sox、librosa、numba、onnxruntime、pandas、scikit-learn 等）+ **`comfy-kitchen` 0.2.36**（`--use-ck-attention` int8 内核，见 §4.1）。部署时 `pip install` 上面列的必需项即可，其余随 CCTech requirements 与 Manager 装齐
- **transformers 降级 5.15.1 → 4.57.3**、**huggingface_hub 降级 1.28.0 → 0.36.2**（qwen-tts 需要旧版 transformers，连带 hub 版本配套），装 qwen-tts 时注意强制覆盖
- 已装 ComfyUI-Manager 4.2.2，但启动脚本未加 `--enable-manager`（未激活，只做节点管理备用）

### 4.4 模型文件（models/，MiniMax H3 部分）

| 文件 | 大小 | 目录 | 来源（hf-mirror） |
|---|---|---|---|
| `minimax_h3_fl2va_pruned-Q4_K_M.gguf` | 10.64GB | diffusion_models | `molbal/MiniMax-H3-GGUF` |
| `minimax_h3_ref2va_pruned-Q4_K_M.gguf` | ~10.6GB | diffusion_models | `molbal/MiniMax-H3-GGUF` |
| `qwen3-vl-4b-heretic-Q4_K_M.gguf` | ~2.3GB | text_encoders | `matrixportalx/Qwen3-VL-4B-Instruct-heretic-Q4_K_M-GGUF` |
| `qwen3-vl-4b-heretic.mmproj-f16.gguf` | 836MB | text_encoders | `mradermacher/Qwen3-VL-4B-Instruct-heretic-GGUF` 的 `Qwen3-VL-4B-Instruct-heretic.mmproj-f16.gguf`（**matrixportalx 版无 mmproj，必须 mradermacher**） |
| `mmh3-4b-ClipProj-v3.1.safetensors` | 25MB | clip_projections | `NicoLab28/ClipProj-MiniMax-H3` |
| `qwen3vl_8b_fp8_scaled.safetensors` | 10.6GB | text_encoders | `Comfy-Org/Qwen3-VL`（8B stock，自带视觉塔） |
| `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | 9.33GB | text_encoders | `DreamFast/Qwen3-VL-8B-Heretic-1.3.0` → `comfyui/`（8B 破限备选） |
| `mmh3-8b-ClipProj-v3.1.safetensors` | ~30MB | clip_projections | `NicoLab28/ClipProj-MiniMax-H3`（8B 两档共用；另加送 `-mlp` 576MB 做矩阵 A/B） |
| `minimax_h3_video_vae_fp16.safetensors` | 5.2GB | vae | `Comfy-Org/MiniMax-H3` |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.6GB | vae | `Comfy-Org/MiniMax-H3` |

关键坑：
- **mmproj 命名必须满足 GGUF loader 合并规则**：文本塔 squash 名 `qwen3vl4bheretic` 必须被 mmproj 文件名包含 → mmproj 固定命名为 `qwen3-vl-4b-heretic.mmproj-f16.gguf`。否则 `CCTechClipProjLoader` 报 `loaded as Qwen3_4B, not as a Qwen3-VL text encoder`
- 若 `UnetLoaderGGUF` 读不到 `diffusion_models\` 下的 gguf → 复制一份到 `models\unet\`
- 投影只用 `.safetensors`，**`.pt` 一律不用**（pickle 可执行代码）
- `minimax_h3_fl2va_pruned_fp8_Q4_0.gguf`（官方现版 10.6GB）曾下载实测：与 Q4_K_M 速度几乎相同、VRAM 略高；对比结束后已删除，不保留，**主力就是 Q4_K_M**

### 4.5 不影响部署的运行时产物（对比时忽略）

`ComfyUI\__pycache__`、`ComfyUI\temp`、`ComfyUI\user`（Manager 数据库 comfyui.db、运行日志）。

### 4.6 ComfyUI 内核改动：帧预览（2026-10-07）

> ⚠️ 这是**唯一动过 ComfyUI 源码的改动**，换机必须显式打上，否则 `plan\bat\preview_watch\` 永远等不到预览帧。补丁与说明见 `plan\bat\preview_watch\`、`plan\README.md §6.7`。

| 改动文件（相对 `ComfyUI_windows_portable\`） | 干什么 |
|---|---|
| `ComfyUI\latent_preview.py` | **帧预览主战场**：模块级状态 + 采样 callback 里用工作流的 video VAE 解码 latent → 写 `%TEMP%\iw-preview-{MMddHHmmss}-{pid%100000}\`；首批 `step 0` 触发（顺带把 DiT 提前卸到低水位），之后每 `total_steps//4` 步一批 |
| `ComfyUI\comfy_extras\nodes_minimax_h3.py` | H3 节点接上 `latent_preview` 回调（`import latent_preview`），i2v/t2v/ref2v 三套共用 |
| `ComfyUI\execution.py` | 任务起止通知与 `extra_data.preview_file` 传递 |

**两个补丁文件**（同目录，均为权威版）：

| 补丁 | 覆盖 | 用途 |
|---|---|---|
| `frame_preview_kernel.patch` | 8,271 B / 3 文件 | **帧预览功能本体**，就是上表 3 个文件的改动 |
| `official-0.38.0-to-current.patch` | 63,330 B / 14 文件 | 官方 `0.38.0` tag → 本机当前内核的完整复刻 = 帧预览 3 文件 + 11 个 2026-09-30 之后的官方上游提交。**换机复现本机内核状态用它**，之后 `frame_preview_kernel.patch` 已包含在内 |

**打补丁步骤**：`cd ComfyUI_windows_portable\ComfyUI` → `git apply frame_preview_kernel.patch`（在 0.38.0 源码树上已 `--check` 验证）→ **重启 ComfyUI 生效**。

**实机状态可验证**（本机 ComfyUI 是 git 仓库，2026-10-07 `git status`）：本地改动**恰好只有上表 3 个文件**，与补丁的 `diff --git` 清单一一对应，无其它漂移。换机后同样跑一次 `git status` 对表即可。

**影响范围**：`plan\molbal_workflows\final\` 的 15 个视频工作流（i2v/t2v 共用 `MiniMaxH3ImageToVideo`，ref2v 走 `ReferenceToVideo`），**工作流文件本身零改动**；请求侧需 `extra_data.preview_file=true`（项目侧默认 true，手动 `POST /prompt` 不传则 ComfyUI 默认 true）。Qwen-Image 线不受影响。

**附带收益：`step 0` 首批预览 = 顺手卸载 DiT**（2026-10-07 补记，实机经验）—— `step 0` 触发首批预览 → `video VAE decode` → ComfyUI 自带的 `free_memory` → **动态 DiT 在采样最早期就被卸载到低水位**，后续按需换回。逻辑依据：

- **反复加载模型的耗时 ≪ 爆显存的代价**：显存被顶爆时 `--enable-dynamic-vram` **不崩进程**，而是把数据退到系统内存（页面文件 / swap）走，那段渲染**非常慢** → 宁可让 DiT 反复进出，也不让它把显存顶满
- **长提示词、长视频时长时最明显**（采样期显存占用最高），收益最大
- **风险是整机卡死而非报错**：显存爆了不等于出错，只有内存也耗尽时操作系统才卡死 → 提前卸载是**防卡死**不是防报错

详见 `plan\README.md §6.7` 与 `watch_h3_preview.py` docstring；脚本本身零侵入，不发任何卸载请求。

> **2026-10-07 同日更新：触发点从 `step 1` 提前到 `step 0`** —— 内核条件由 `step > 0 and (step == 1 or step % every == 0)` 简化为 `step % every == 0`（`every = max(1, total_steps // 4)`，自然含 `step 0`），卸载时机再早一个采样步，**省显存效果更好**。两个补丁 `*.patch` 已同步重生成并过反向 apply 校验。

---

## 五、工作流（plan/molbal_workflows/final/）

全部改编自 CCTech（Molbal）官方模板，**全部 core 节点，仅替换 TE 节点**。按档位分目录（2026-09-30 重组）：

| 目录 | 文件 | 用途 |
|---|---|---|
| `4b\` | `minimax_h3_{t2v,i2v,ref2v}-gguf.json` | 4B heretic 三套基底 |
| `4b\op\` | `minimax_h3_*-gguf-op.json` | 4B + 官方 prompt（对照组） |
| `8b\` | `minimax_h3_*-gguf-8b.json` | 8B stock 三套基底 |
| `op-8b\`（主力） | `minimax_h3_*-gguf-8b-op.json` | 8B stock + 官方 prompt |
| `op-8b-heretic\` | `minimax_h3_*-gguf-8b-heretic-op.json` | 8B 破限 + 官方 prompt（T2V 用） |
| 根目录 | `qwen_image_2_1_{t2i,image_edit,background_removal}[-Q8_0]_gguf.json` ×6 | Qwen-Image 2.1（与 H3 无关，**跑它必须换 no_ck 启动脚本**，见 §八）；prompt 模板已迁至 `plan\bat\提示词模板\`，`提示词模板在bat里.txt` 是 0 字节指针 |

### 5.1 API 格式工作流（`plan/API_workflows/`，2026-10-06 入库）

UI 格式（`molbal_workflows\`）拖进画布用；**API 格式**走 `POST /prompt` 提交，由 `plan\bat\` 下的脚本链驱动，参数覆盖只在内存中、不落盘。103 文件 / 7 个子目录：

| 子目录 | 内容 |
|---|---|
| `未测试\final\{4b,4b\op,8b,op-8b,op-8b-heretic}\` | **API 格式交付层 15 份**，与 `molbal_workflows\final\` 层级刻意对齐。⚠️ 目录名 `未测试` 是历史遗留，全部工作流实际均已跑通 |
| `未测试\{op,8b,op-8b,op-8b-heretic}\` | 上述交付层的拷贝源，各 3 份 |
| `infinite-creation\Final\` | 官方 infinite-creation 模板交付（8 份，含 Qwen3-TTS Voice Design） |
| `RAW\` | 原始快照，含 `bak\009/010-*-NOAV*` 去音频对照版 |
| `omy\` / `Calliope\` / `go\` | 调试线与快照（`bak 04  OK` 等命名不统一，见 `plan\README.md §7.2`） |
| `_audit\` | 7 份工具脚本，校验 RAW → 交付层的适配链路 |

替换两处（模板 `UnetLoaderGGUFDynamicVRAM`/`CLIPLoader` → CCTech）：
1. `UnetLoaderGGUF`：`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`（ref2v 用 ref2va）
2. `CCTechClipProjLoader` TE 三件套：4B=`[qwen3-vl-4b-heretic-Q4_K_M.gguf, krea2, mmh3-4b-ClipProj-v3.1.safetensors]`；8B=`[qwen3vl_8b_fp8_scaled.safetensors, boogu, mmh3-8b-ClipProj-v3.1.safetensors]`（破限换 `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`）

自带卸载节点 `ForceUnloadBeforeDecode` x2（采样前 + 解码前）。实测：**解码前卸载有效**（卸掉 DiT 后 VAE 独享显存，解码 ~30s）；**采样前卸载收益≈0**（采样是计算受限不是显存受限）——保留无害。8B 编码器更重（编码期峰值 ≈11–12GB vs 4B ≈3.6GB），**卸载是必需而非优化**。

op 系列（官方 prompt 合规版，§11.9）：T2V/I2V 的 `length` 已从 73 提到 **124≈5s**（官方训练范围下限）；模板 txt（`plan\bat\归档\prompt_{t2v,fl2va,ref2va}_op.txt`）与工作流内嵌 prompt **逐字一致**，脚本 `--prompt-file` 可直接复用。

需替换素材：i2v 的 `LoadImage` x2（首/末帧）、ref2v 的 `LoadImage`+`LoadVideo`+`LoadAudio`，换自有文件。

---

## 六、Python 脚本（plan/bat/，2026-10-02 重构为「族 × TE 变体」矩阵）

**4 个生成族 × 3 个 TE 变体 = 12 个目录 + 4 个工具目录 + 提示词模板/归档/分段归档**。变体唯一差别是 `CCTechClipProjLoader` 的 `clip_name` / `type` / `projection` 三元组（`krea2` / `boogu` 是**节点 type 枚举值**，不是文件名）：

| 后缀 | clip_name | type | projection |
|---|---|---|---|
| *(无)* | `qwen3-vl-4b-heretic-Q4_K_M.gguf` | `krea2` | `mmh3-4b-ClipProj-v3.1.safetensors` |
| `_8b` | `qwen3vl_8b_fp8_scaled.safetensors` | `boogu` | `mmh3-8b-ClipProj-v3.1.safetensors` |
| `_8b_heretic` | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | `boogu` | 同上 |

| 族（目录） | 做什么 | 关键差异 |
|---|---|---|
| `multisegment[_8b\|_8b_heretic]\` | 多段视频生成（**首尾帧拼接**，fl2va） | 所有段共用一条提示词；`prompt.txt` 三份 |
| `scenes[_8b\|_8b_heretic]\` | **分镜多段**：每段独立提示词/时长 + **首帧续接** | 纯文本提示词 |
| `scenes_ref[_8b\|_8b_heretic]\` | **分镜多段 + 多图 / 视频参考** | 支持图片/视频参考 |
| `ref2va[_8b\|_8b_heretic]\` | 参考图生成视频（ref2va er_sde）+ ffmpeg 拼接 | 段 0 用参考图，后续段首帧续接 |
| `extract_frames\` | 工具：抽 **首/中/末** 三帧 PNG（`--mid` 调中间帧，防覆盖） | 无 TE 变体 |
| `qc_frames\` | 工具：QC 抽帧 + contact sheet（配 `vision-deepseek` 识图） | 无 TE 变体 |
| `free_vram\` | 工具：调 ComfyUI `/free` 卸载模型、释放 Dynamic VRAM 残留（§八） | 无 TE 变体 |
| `preview_watch\` | 工具：H3 生成中**实时预览帧监视器**，轮询 `/queue` + `%TEMP%\iw-preview-*` 打印内核落盘的真帧；`step 0` 首批预览**顺带把 DiT 卸到低水位**（§4.6） | 无 TE 变体；**需先给内核打补丁**，见 §4.6 |

每个目录含 `gen_*.py` + `gen_*.bat`（Windows 入口），**例外 `free_vram\` = `free_vram.py` + `free_vram.bat`、`preview_watch\` = `watch_h3_preview.py` + `watch_h3_preview.bat`**。`prompt.txt` 随目录（交互模式优先读同目录，另有 `--prompt-file`，UTF-8/GBK 自动识别；`--prompt` 为单条、全部段复用）。输出重名自动追加 `_1/_2` 防覆盖。

| 辅助目录 | 内容 |
|---|---|
| `提示词模板\` | `MiniMax-H3-提示词书写规则.md`（三字段信封 / `[Shot N]` 时间线 / 摄影机运动词表 / 帧栅格 / R2V 六段）+ `提示词模板-视频.txt` / `-视频 -静止.txt` / `-照片.txt` |
| `归档\` | 官方三份 op 提示词 `prompt_{t2v,fl2va,ref2va}_op.txt` + 种子记录 |
| `分段归档\` | 多段生成的分段产物（`seg<N>.mp4` + 首末帧 PNG + 归档说明），按族分子目录 |
| `prompt说明.txt` | 根级提示词文件用法说明 |
| `..\bak\` | ⚠️ **早期脚本退场副本，与 `bat\` 内同名文件易混，不要从这里取用** |

依赖：ComfyUI 运行在 `http://127.0.0.1:8188`，**本地 API 一律直连**（2026-10-07 起 14 份脚本统一 `OPENER = build_opener(ProxyHandler({}))`，绕过系统代理，§八 有排雷）；ffmpeg（脚本内已写死本机 WinGet 版路径，换机需改 `FFMPEG` 常量）。`-8b` / `-8b-heretic` 变体与对应 4B 版归一后逐字节一致（§11.8.4）。

---

## 七、换机一键部署清单

1. 下载官方 `ComfyUI_windows_portable`。⚠️ 早期优化全部基于 v0.34.0 验证，实机现已升级到 **v0.38.0**（`fb2315f1`）；要复现本仓库全部结论就 `git checkout` 到 0.34.0，要跟实机一致就用 0.38.0 并复核 H3 结论
2. ROCm 环境（`torch 2.9.1+rocm7.2.1`），启动一次确认 `Recognized AMD device ... RX 7900 XTX ... ROCm`
3. clone CCTech `ComfyUI-GGUF-Loader` v2.16.7（镜像加速）
4. 复制 `ComfyUI-ForceUnloadBeforeDecode`（自建节点，单文件）
5. `pip install gguf sentencepiece protobuf qwen-tts timm opencv-python-headless ...`，**transformers 锁 4.57.3**，**`comfy-kitchen` 必装**（`--use-ck-attention` 依赖，缺失即 `exit(-1)` 拒启）
6. 按 §4.4 表放齐 **10 个模型文件**（hf-mirror，走 Aria2UI 多线程；8B 三件套见 §三 T2/T2b）
7. 部署启动脚本（§4.1，H3 用 ck 版 / Qwen-Image 用 `no_ck` 版）并启动，日志见 73 节点注册
8. 导入工作流（§五，按档位选 `4b\` / `op-8b\` 等）替换素材 → 按 §一参数跑 T2V 冒烟，再 I2V / R2V
9. 改任何模型/分辨率组合前，先跑 `python plan\vram_model.py` 过判据（`Plan.md §3.6` 速查）
10. **（可选）打帧预览内核补丁**：`cd ComfyUI_windows_portable\ComfyUI && git apply <repo>\plan\bat\preview_watch\frame_preview_kernel.patch` → **重启 ComfyUI**（§4.6）。打完才能用 `plan\bat\preview_watch\watch_h3_preview.bat` 边跑边看预览帧；不打也不影响任何生成，只是没有预览

> **仓库仍不含的本机资产**（2026-10-06 调整）：上一轮把 `API_workflows\` 整棵排除在外（理由「只在本机脚本链里用」），**本轮改判入库** —— 它含 API 格式交付层 15 份，换机必需。净增 194 文件 / 2.72 MB，含完整 `API_workflows\`（103）、`归档\日志\`（13）、`molbal_workflows\bak noerror *` 与 `bak RAW`（15）、以及整个 `plan2\`（52，Qwen-Image 2.1 生图线）。
>
> 仍不入库的都是**可重生成的产物**（约 31.8 MB）：`bat\` 下的 mp4 与 PNG 帧（22.26 MB）、`ck_ab_20261002\` 对照图与自检样本（6.44 MB）、`plan2` 两张对照图（2.94 MB）、`bat\测试素材\`、全部 `*.pyc`。逐条清单见 `plan\README.md` 顶部说明块。
>
> **另入库 `src/infinite-creation/config.json`**（2026-10-06，651 B）：infinite-creation 编排器的本机配置 —— ComfyUI `127.0.0.1:8188`、本地 LLM `127.0.0.1:1234/v1`（`Huihui-Qwen3.8-27B-abliterated-GGUF`）、t2i/i2i/r2v/tts 四类工作流映射。实机源 `D:\localAI\ComfyUI-last\src\infinite-creation\`（该目录是独立 Next.js 项目，**仓库只收这一份配置**，其余 `vendor\`、`node_modules\` 等不入库）。

---

## 八、已知排雷（详见 plan 文档 §8）

- ❌ **同时开两个 ComfyUI**（内存爆掉、系统直接卡死）。切换生图 ↔ 生视频必须先 `Get-Process python | Stop-Process -Force`，确认 8188 不再监听再起
- ❌ 把「两个启动脚本都带 `--enable-dynamic-vram`」误认成「两个一样」——**区别只在 ck 开关**
- ⚠️ **`--enable-dynamic-vram` 的残留物理页会让同一条工作流越跑越慢**（十几分钟的活拖成几小时）。段间清理由多段脚本内置 `POST /free` 完成；段外与批跑用 `plan\bat\free_vram\free_vram.bat`（`--status` 看状态、`--interval 60` 挂旁边周期清、`--no-verify` 发完即走）。**`/free` 是异步 flag 端点**：HTTP 200 只代表 flag 已设，真正卸载在当前任务结束后的 worker 线程执行，所以必须用 `/system_stats` 的 `vram_free` 上升来验证；任务执行中调用安全（不会打断 prompt），但它**救不了单个任务内部变慢**，那种只能重启 ComfyUI
- ⚠️ **脚本报 `404` / `Not Found`，但浏览器开 `127.0.0.1:8188` 明明正常 → 先查系统代理，别怀疑 ComfyUI**：本机代理 `127.0.0.1:26561` 的 `ProxyOverride` **不放行 loopback**，双击 bat 的环境里又**没有 `no_proxy`**，`urllib.getproxies()` 会读**注册表**代理，把发往 `127.0.0.1:8188` 的请求也交给代理 → 代理回 404。**2026-10-07 已加固 22 份 / 68 处**（`plan\bat\` 13 份 + `plan2\qwen21-tools\` 9 份）统一 `OPENER = build_opener(ProxyHandler({}))` 直连，空 handler 同时绕过环境变量与注册表两种来源。⚠️ **opencode / 终端 shell 里往往自带 `NO_PROXY`，会掩盖这个坑** —— 别拿会话里「能跑」当证据，要用双击 bat 的环境验。残留 2 份 8 处按拍板保留（`ck_ab_20261002\gen_h3_ck_ab.py` 是实测锚点，**重跑前须先加 `OPENER`**；`bak\` 退场副本不取用），详见 `plan\README.md §6.6`
- 💡 **显存策略：宁可让 DiT 反复进出，也别让 `--enable-dynamic-vram` 把显存顶满**（实机经验）。显存爆了**不崩进程** —— 数据退到系统内存（页面文件 / swap）走，那一段渲染**非常慢**；只有内存也被耗尽时操作系统才卡死，所以真正的风险是**整机卡死**而非报错。**反复加载模型的耗时远小于爆显存的代价**，且**长提示词、长视频时长时最明显**（采样期显存占用最高）。`preview_watch` 的 `step 0` 首批预览正是利用这点：借 `VAE decode` 自带的 `free_memory` 在采样最早期就把 DiT 卸到低水位（§4.6、`plan\README.md §6.7`）
- ⚠️ **`watch_h3_preview.bat` 一直等不到预览帧 → 先查内核补丁打没打**：预览帧由**内核**生成并落盘到 `%TEMP%\iw-preview-*`，`preview_watch\` 脚本零侵入、只在旁边监视，所以内核没改就永远没有输出。补丁与打步骤见 §4.6、`plan\README.md §6.7`；**改完必须重启 ComfyUI**。本机权威状态：ComfyUI 仓库跑 `git status`，应只有 `latent_preview.py` / `comfy_extras/nodes_minimax_h3.py` / `execution.py` 三个 `M`
- ❌ 独立 nicolab28 `ComfyUI-ClipProj`（CCTech 内置同源，避免同名冲突）
- ❌ `ComfyUI-MiniMaxH3-Cache`（全局 monkey-patch 破坏 H3 生成）
- ❌ Optimization Suite / SageAttention / Tiled VAE（NV 专属或对 H3 无效）
- GGUF mmap 崩溃 `0xC0000005`（Windows）：第二个不兼容模型叠在第一个上加载导致 → 靠 §三 顺序驻留规避
- 若 I2V/R2V 引用图/视频失败：换官方 bf16 编码器 `qwen3vl_4b_fp8_scaled.safetensors` 或 heretic bf16（8.3GB）
- ❌ 8B 破限（T2b）**不要用于 I2V/R2V**：视觉塔 116 个张量降 F8_E4M3，图像路径有真实精度损失（§11.11.4）；破限只做 T2V 备选
- 8B 首跑前**关掉其它 GPU 程序**：编码期峰值 ≈11–12GB（4B ≈3.6GB），T2b staged 16,721MB 超出可用显存需分页（§11.8.5）
- ❌ **`--use-ck-attention` + Qwen-Image 2.1 = 输出崩坏**（2026-10-01 实测确认）：comfy-kitchen 0.2.36 的 masked attention 重写在**存活 token >64**（HIP 核 tile 宽度）时产出绿/紫伪影、纹理破碎，**且不抛任何异常**。**对策：Qwen-Image 改用 `run_amd_gpu_no_ck_attention.bat`。** 排查口诀：任何「提示词太长就崩」的症状，**先查启动 flag，别怀疑模型限制**。
- ✅ **同款 flag 对 MiniMax H3 已确认安全**（2026-10-02 受控 A/B，**不是同一个问题**）：H3 文本编码器不受影响（`small_input=True` 提前返回 `attention_basic`）；**H3 DiT 主干经 124 帧逐帧实测确认无损坏** —— SSIM 0.98849（全部帧 > 0.98）、平均像素差 0.9125/255、误差均匀弥散且高频为主、绿/紫伪影像素占比 **0.000%**、100% 裁切目视复核逐项无结构损坏、锐度 ck 侧 **+5.50%**（属「细节更清楚」而非假边缘）。差异性质是 **int8 量化导致的系统性微差**（落在另一个同样合法的采样结果上），**4 步 → 20 步差异收敛**（r 0.928 → 0.995）进一步排除崩坏。**H3 继续用带 ck 的 `run_amd_gpu_enable_dynamic_vram.bat`。** 详见 `plan\CK注意力回归问题调查报告.md`（Qwen 侧 5 组 flag 对照 + token 二分 + 源码定位）与 `plan\ck_ab_20261002\`（H3 侧 A/B 完整报告与原始数据）+ `Plan.md §12`

> **ck-attention 现状速查**：加速 2.70x（纯采样口径；总耗时 2.02x，甜点档端到端 1.54x）· H3 文本侧安全（源码核实）· Qwen-Image 2.1 崩坏（已确认）· **H3 DiT 安全（2026-10-02 实测确认）** · 上游 issue [comfy-kitchen#226](https://github.com/Comfy-Org/comfy-kitchen/issues/226) 无修复版本 · 升级 comfy-kitchen 后必须重测 64 token 边界**并重跑 `plan\ck_ab_20261002\` 的 A/B**

---

## 九、相关文档

### 9.1 H3 生视频线（`plan/`）

| 文档 | 内容 |
|---|---|
| `plan\README.md` | **先读这份**：H3 侧资产地图（五区语义 / 文档清单 / 脚本族矩阵 / 工作流矩阵 / API_workflows 树 / 整理记录 / 硬规矩） |
| `plan\ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md` | 主计划：全部实测决策、§11 8B 路线 / 分辨率换算表 / 耗时模型、§12 ck 回归专章、§13 资产分布 |
| `ComfyUI_MiniMaxH3_From_Scratch.md` | 从零重建全流程（干净 portable → 可跑） |
| `T2V_4B_vs_8B_对比报告.md` | 4B vs 8B 单变量对比（耗时/显存/逐帧指标），含 0.6MP 补测与破限 A/B（2026-09-30） |
| `vision_qc_识图结论.md` | H3 产物画质识图结论（vision-deepseek 通道，抽帧 QC） |
| `plan\bat\`（脚本） | 全部 Python 脚本 + bat 启动器 + prompt 模板（§六），**按族 × TE 变体分 16 个子目录** |
| `plan\bat\preview_watch\` | H3 生成中**实时预览帧监视器**（`watch_h3_preview.py/.bat` + 2 个内核补丁 `*.patch`）。**用它要先给内核打补丁**，见 §4.6 |
| `plan\molbal_workflows\final\` | 工作流全集（§五） |
| `plan\vram_model.py` | **显存估算模型**（纯标准库）：输出 `Plan.md §3` 全部表格，改常量即重算。改配置前先跑它算判据 |
| `plan\CK注意力回归问题调查报告.md` | ⚠️ `--use-ck-attention` 回归完整证据链（Qwen-Image 侧 5 组 flag 对照 / token 64 边界二分 / 源码定位 / 版本溯源），对应 `Plan.md §12`。**权威版在 `plan\`，`plan2\qwen21-tools\` 下是副本** |
| `plan\ck_ab_20261002\` | ✅ **H3 侧 ck / 非-ck 受控 A/B**（2026-10-02）：报告 + 探针与比对脚本 + 5 次运行清单 + 逐帧原始指标。结论「H3 DiT 走 ck 安全」，对应 `Plan.md §12.3` / `§12.6` 待办 1（已关闭） |
| `plan\API_workflows\H3工作流适配计划.md` | API 格式工作流适配方案 |
| `plan\API_workflows\未测试\final\README.md` | API 格式交付层（15 份）的来源与三套 TE 对照 |
| `plan\归档\日志\来源清单.md` | 12 个 `*.log` 归档前后路径对照 |

### 9.2 Qwen-Image 2.1 生图线（`plan2/`，2026-10-06 入库）

`plan2\` 是 `plan\` 的**姊妹目录**（并列，不是父子），实机在 `D:\localAI\ComfyUI-last\plan2\`。

| 文档 | 内容 |
|---|---|
| `plan2\README.md` | **先读这份**：Qwen 侧资产地图（工具脚本 17 份 / 上游 issue 材料 / 实验留痕 / 硬编码路径 / 与 `plan\` 的分工） |
| `plan2\Qwen-Image-2.1-GGUF-部署总结.md` | 主文档：目标 / 结论 / 环境 / 模型 / 适配做了什么 / 节点依赖 / 实测结果 / 9 节踩坑 |
| `plan2\qwen21-tools\` | 工具链（`ui2api.py` / `check_workflows.py` / `run_api.py` / `fetch_schema.py` 等）+ 22 份实验 API 图 + 上游 issue #226 材料 |
| `plan2\qwen21-tools\CK注意力回归问题调查报告.md` | `plan\CK注意力回归问题调查报告.md` 的副本（2026-10-06 同步，§7.3 已关闭） |