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

- ComfyUI `ComfyUI_windows_portable`，**核心 v0.34.0**（随便携版自带，所有验证基于此版）
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

**`run_amd_gpu_enable_dynamic_vram.bat`**（**日常启动 / 主力**；`--enable-dynamic-vram` 在 ROCm <7.14 需手动开启，官方 7.14+ 才默认启用，本机 ROCm 7.2.1 必须加）：
```bat
%PYTHON% -s %TARGET% --windows-standalone-build --enable-dynamic-vram --disable-pinned-memory --fp16-intermediates --disable-smart-memory --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
```

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
- `--use-ck-attention`：启用 **Comfy Kitchen attention**（int8 内核，`comfy_kitchen` 0.2.36，本机 HIP 后端实测可用）。⚠️ 该参数**不是 fallback**：`comfy_kitchen` 缺失或 kernel 不支持时会打印错误并**直接退出**（`attention.py:918 exit(-1)`），本机已验证 `hip int8 avail: True` 才放心启用
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
| 根目录 | `提示词模板-视频.txt` / `提示词模板-照片.txt`；`qwen_image_2_1_*_gguf.json` ×3 | prompt 模板；Qwen-Image 2.1 工作流（与 H3 无关） |

替换两处（模板 `UnetLoaderGGUFDynamicVRAM`/`CLIPLoader` → CCTech）：
1. `UnetLoaderGGUF`：`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`（ref2v 用 ref2va）
2. `CCTechClipProjLoader` TE 三件套：4B=`[qwen3-vl-4b-heretic-Q4_K_M.gguf, krea2, mmh3-4b-ClipProj-v3.1.safetensors]`；8B=`[qwen3vl_8b_fp8_scaled.safetensors, boogu, mmh3-8b-ClipProj-v3.1.safetensors]`（破限换 `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`）

自带卸载节点 `ForceUnloadBeforeDecode` x2（采样前 + 解码前）。实测：**解码前卸载有效**（卸掉 DiT 后 VAE 独享显存，解码 ~30s）；**采样前卸载收益≈0**（采样是计算受限不是显存受限）——保留无害。8B 编码器更重（编码期峰值 ≈11–12GB vs 4B ≈3.6GB），**卸载是必需而非优化**。

op 系列（官方 prompt 合规版，§11.9）：T2V/I2V 的 `length` 已从 73 提到 **124≈5s**（官方训练范围下限）；模板 txt（`plan\bat\prompt_{t2v,fl2va,ref2va}_op.txt`）与工作流内嵌 prompt **逐字一致**，脚本 `--prompt-file` 可直接复用。

需替换素材：i2v 的 `LoadImage` x2（首/末帧）、ref2v 的 `LoadImage`+`LoadVideo`+`LoadAudio`，换自有文件。

---

## 六、Python 脚本（plan/bat/，2026-09-30 由 plan/ 迁入）

| 脚本 | 用途 |
|---|---|
| `gen_video_ask.py` / `.bat` | 交互式 T2V 生成（提示词/尺寸/时长/Turbo LoRA，回车默认 480P 5s），走 ComfyUI API |
| `gen_h3_multisegment.py` / `.bat` | **多段视频拼接（4B base）**：段 0 走 t2v，后续段取上段末帧作 first_frame 续接（fl2va），最后 ffmpeg concat 去重首帧；交互模式优先读同目录 `prompt.txt`（另有 `--prompt-file`，UTF-8/GBK 自动识别；`--prompt` 为单条、全部段复用） |
| `gen_h3_multisegment-8b.py` / `.bat` | 同上，8B stock（`qwen3vl_8b_fp8_scaled`） |
| `gen_h3_multisegment-8b-heretic.py` / `.bat` | 同上，8B 破限（`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn`） |
| `gen_h3_ref2va.py` / `.bat` | **ref2va 参考图多段生成（4B）**：段 0 用参考图 ref2va（er_sde），后续段 fl2va 首帧续接；`--ref` 多图/目录、`<Picture N>` 引用，全部段共用种子与配置；输出 `h3_ref2va_<seed>.mp4` 防覆盖 |
| `gen_h3_ref2va-8b.py` / `.bat` | 同上，8B stock |
| `gen_h3_ref2va-8b-heretic.py` / `.bat` | 同上，8B 破限 |
| `gen_extract_frames.py` / `.bat` | **抽帧工具**：从视频抽 **首/中/末** 三帧 PNG（ffprobe 读时长，`--mid` 调中间帧位置，防覆盖） |
| `gen_h3_qc_frames.py` / `.bat` | **QC 抽帧**：ffmpeg 按时间轴抽 8 帧 + tile 拼图，供识图质检（vision-deepseek，见 `vision_qc_识图结论.md`） |
| `gen_video.py`（依赖，见脚本注释引用） | 核心 API 逻辑 |
| `prompt.txt` | `gen_h3_multisegment`/`gen_h3_ref2va` 交互模式的提示词模板（整文件作为一条提示词，回车确认或 n 改输） |
| `prompt_{t2v,fl2va,ref2va}_op.txt` | 官方 prompt 模板（T2VA 三段式 / FL2VA 首行对齐 + 三段式 / ref2va 六段式），供脚本 `--prompt-file` 复用，与 op 工作流内嵌逐字一致 |

依赖：ComfyUI 运行在 `http://127.0.0.1:8188`；ffmpeg（脚本内已写死本机 WinGet 版路径，换机需改 `FFMPEG` 常量）。`gen_h3_multisegment` 输出文件重名时自动追加 `_1/_2` 后缀防覆盖。`-8b` / `-8b-heretic` 变体与对应 4B 版归一后逐字节一致（§11.8.4）。

---

## 七、换机一键部署清单

1. 下载官方 `ComfyUI_windows_portable`（core 版本若是 v0.34.0 直接用；更高版本先 `git checkout v0.34.0`，优化全部基于 0.34 验证）
2. ROCm 环境（`torch 2.9.1+rocm7.2.1`），启动一次确认 `Recognized AMD device ... RX 7900 XTX ... ROCm`
3. clone CCTech `ComfyUI-GGUF-Loader` v2.16.7（镜像加速）
4. 复制 `ComfyUI-ForceUnloadBeforeDecode`（自建节点，单文件）
5. `pip install gguf sentencepiece protobuf qwen-tts timm opencv-python-headless ...`，**transformers 锁 4.57.3**
6. 按 §4.4 表放齐 **10 个模型文件**（hf-mirror，走 Aria2UI 多线程；8B 三件套见 §三 T2/T2b）
7. 部署两个 bat（§4.1）并启动，日志见 73 节点注册
8. 导入工作流（§五，按档位选 `4b\` / `op-8b\` 等）替换素材 → 按 §一参数跑 T2V 冒烟，再 I2V / R2V

---

## 八、已知排雷（详见 plan 文档 §8）

- ❌ 独立 nicolab28 `ComfyUI-ClipProj`（CCTech 内置同源，避免同名冲突）
- ❌ `ComfyUI-MiniMaxH3-Cache`（全局 monkey-patch 破坏 H3 生成）
- ❌ Optimization Suite / SageAttention / Tiled VAE（NV 专属或对 H3 无效）
- GGUF mmap 崩溃 `0xC0000005`（Windows）：第二个不兼容模型叠在第一个上加载导致 → 靠 §三 顺序驻留规避
- 若 I2V/R2V 引用图/视频失败：换官方 bf16 编码器 `qwen3vl_4b_fp8_scaled.safetensors` 或 heretic bf16（8.3GB）
- ❌ 8B 破限（T2b）**不要用于 I2V/R2V**：视觉塔 116 个张量降 F8_E4M3，图像路径有真实精度损失（§11.11.4）；破限只做 T2V 备选
- 8B 首跑前**关掉其它 GPU 程序**：编码期峰值 ≈11–12GB（4B ≈3.6GB），T2b staged 16,721MB 超出可用显存需分页（§11.8.5）

---

## 九、相关文档（plan/）

| 文档 | 内容 |
|---|---|
| `ComfyUI_MiniMaxH3_AMD_7900XTX_Plan.md` | 主计划：全部实测决策、§11 8B 路线 / 分辨率换算表 / 耗时模型 |
| `ComfyUI_MiniMaxH3_From_Scratch.md` | 从零重建全流程（干净 portable → 可跑） |
| `T2V_4B_vs_8B_对比报告.md` | 4B vs 8B 单变量对比（耗时/显存/逐帧指标），含 0.6MP 补测与破限 A/B（2026-09-30） |
| `vision_qc_识图结论.md` | H3 产物画质识图结论（vision-deepseek 通道，抽帧 QC） |
| `bat\`（脚本） | 全部 Python 脚本 + bat 启动器 + prompt 模板（§六） |
| `molbal_workflows\final\` | 工作流全集（§五） |