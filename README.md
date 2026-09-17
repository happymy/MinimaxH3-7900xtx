# MinimaxH3-7900xtx

**Win11 + 32GB RAM + AMD RX 7900 XTX (24GB ROCm)：使用 ComfyUI 本地运行 MiniMax H3 视频生成（T2V / I2V / R2V）的极致优化部署方案。**

> 本仓库仅记录 MiniMax H3 相关。所有内容源自 `D:\localAI\ComfyUI-last\ComfyUI_windows_portable`（最终优化版）与
> `D:\localAI\ComfyUI_windows_portable`（原版未初始化）的实机对比 + `plan\` 下实测文档。目的：**快速换机后一键照此重部署**。

---

## 一、成果基线（已实测收敛，勿再折腾）

| 项 | 结论 |
|---|---|
| 分辨率 | **480P（864×480）**，0.4MP 档 |
| 时长 | **5s（124 帧）= 绝对甜点档**（日常主力）；10s 仅备用（显存逼近红线、耗时 ≈ 40–45min vs 5s ≈ 10min） |
| steps | **10 或 12**（官方模板默认 12；10 步与 20 步肉眼几乎无差） |
| cfg | **1.0**（H3 是蒸馏模型，cfgd >1.0 可能直接中止） |
| sampler / scheduler | `res_multistep` / `simple` |
| 速度参考 | 5s 一轮 ≈ 9.5min（采样 ~26.6s/it 恒定 + 解码 ~30s）；480P/10s/20 步长提示词 40–45min，比最初同条件快近一倍 |
| 显存纪律 | **任意时刻只驻留一个「大件」**（编码器 / 扩散模型 / VAE），靠顺序执行自动卸载，全程不触发 swap |

---

## 二、环境基线

- ComfyUI `ComfyUI_windows_portable`，**核心 v0.34.0**（随便携版自带，所有验证基于此版）
- 推理后端 `torch 2.9.1+rocm7.2.1` / HIP 7.2.53211，识别为 AMD RX 7900 XTX（ROCm）
- system RAM ≥ 31GB（本机 31.9GB 验证），config 页文件保余量

---

## 三、架构决策（为什么能跑）

MiniMax H3 官方用 Qwen3-VL-**32B** 编码器，官方 safetensors 为 **NVFP4/AWQ（Blackwell 专属，AMD 不可用）**，且 24GB 下与扩散模型同驻必溢出 → **排除 32B 路线**。

**采用 ClipProj 路线**：4B 编码器 + 学习好的线性投影，映射到 32B 条件空间：

```
cond = ((h - mean_in) / std_in) @ W * std_out + mean_out
```

- 编码器：`qwen3-vl-4b-heretic-Q4_K_M.gguf`（文本塔）+ 同名 mmproj（视觉塔）
- 投影矩阵：`mmh3-4b-ClipProj-v3.1.safetensors`（25MB，4B/2560 维）
- 实现：**CCTech `CCTechClipProjLoader` 单节点** = 加载 GGUF 文本塔 + 应用投影，输出标准 `CLIP`，下游 H3 节点连线不动
- 三段驻留（顺序执行即自动清场，详见 plan 文档 §5）：编码器 → 采样模型 → video+audio VAE，每次加载新大件时 ComfyUI 自动踢出最旧的那个

---

## 四、从原版 → 优化版的全部修改（换机照抄）

> 原版 = 官方 portable 同版本（**core v0.34.0 / 92 个 pip 包 / 无 custom_nodes**）。优化版 = core v0.34.0 / 146 个包。逐项差异如下。

### 4.1 启动脚本（portable 根目录）

**`run_amd_gpu.bat`**（日常启动，旁边保留原版 `.bak`）：
```bat
@echo off
set PYTHON=.\python_embeded\python.exe
set TARGET=ComfyUI\main.py
%PYTHON% -s %TARGET% --windows-standalone-build --disable-pinned-memory --fp16-intermediates
pause
```

**`run_amd_gpu_enable_dynamic_vram.bat`**（实验变体，ROCm 支持未验证，一次一测）：
```bat
%PYTHON% -s %TARGET% --windows-standalone-build --enable-dynamic-vram --disable-pinned-memory --fp16-intermediates
```

两条关键参数的实测意义：
- `--disable-pinned-memory`：Windows 默认锁 40% 系统 RAM（31.9GB→12.8GB）供 offload DMA，禁用后归还 → **10s 不再爆显存**（仅降低内存消耗，**内存耗尽仍会崩溃**，非根治）
- `--fp16-intermediates`：中间张量用 fp16，降内存压力
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

- 相对原版（同 v0.34.0）新增 **53 个包**，来源即：CCTech 依赖（`gguf`、`sentencepiece`、`protobuf`、`qwen-tts`、`timm`、`opencv-python-headless`）+ ComfyUI-Manager 全套（fastapi、uvicorn、GitPython、PyGithub、PyJWT、PyNaCl、orjson、gradio 等）+ Qwen3-TTS 系（accelerate、soundfile、sox、librosa、numba、onnxruntime、pandas、scikit-learn 等）。部署时 `pip install` 上面列的必需项即可，其余随 CCTech requirements 与 Manager 装齐
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

三套改编自 CCTech（Molbal）官方模板，**全部 core 节点，仅两处替换**：

| 工作流 | 扩散模型 | 用途 |
|---|---|---|
| `minimax_h3_t2v-gguf.json` | fl2va | 文本→视频 |
| `minimax_h3_i2v-gguf.json` | fl2va | 文本+首/末帧→视频 |
| `minimax_h3_ref2v-gguf.json` | ref2va | 参考图/视频/音频→视频 |

两处替换（模板 `UnetLoaderGGUFDynamicVRAM`/`CLIPLoader` → CCTech）：
1. `UnetLoaderGGUF`：`unet_name=minimax_h3_fl2va_pruned-Q4_K_M.gguf`（ref2v 用 ref2va）
2. `CCTechClipProjLoader`：`[qwen3-vl-4b-heretic-Q4_K_M.gguf, type=krea2, mmh3-4b-ClipProj-v3.1.safetensors]`

自带卸载节点 `ForceUnloadBeforeDecode` x2（采样前 136/146/158 + 解码前 135/145/157）。实测：**解码前卸载有效**（卸掉 DiT 后 VAE 独享显存，解码 ~30s）；**采样前卸载收益≈0**（采样是计算受限不是显存受限）——保留无害。

需替换素材：i2v 的 `LoadImage` x2（首/末帧）、ref2v 的 `LoadImage`+`LoadVideo`+`LoadAudio`，换自有文件。

---

## 六、Python 脚本（plan/）

| 脚本 | 用途 |
|---|---|
| `gen_video_ask.py` / `.bat` | 交互式 T2V 生成（提示词/尺寸/时长/Turbo LoRA，回车默认 480P 5s），走 ComfyUI API |
| `gen_h3_multisegment.py` / `.bat` | **多段视频拼接**：段 0 走 t2v，后续段取上段末帧作 first_frame 续接（fl2va），最后 ffmpeg concat 去重首帧；交互模式优先读同目录 `prompt.txt`（另有 `--prompt-file`，UTF-8/GBK 自动识别；`--prompt` 为单条、全部段复用） |
| `gen_video.py`（依赖，见脚本注释引用） | 核心 API 逻辑 |
| `prompt.txt` | `gen_h3_multisegment` 交互模式的提示词模板（整文件作为一条提示词，回车确认或 n 改输） |

依赖：ComfyUI 运行在 `http://127.0.0.1:8188`；ffmpeg（脚本内已写死本机 WinGet 版路径，换机需改 `FFMPEG` 常量）。`gen_h3_multisegment` 输出文件重名时自动追加 `_1/_2` 后缀防覆盖。

---

## 七、换机一键部署清单

1. 下载官方 `ComfyUI_windows_portable`（core 版本若是 v0.34.0 直接用；更高版本先 `git checkout v0.34.0`，优化全部基于 0.34 验证）
2. ROCm 环境（`torch 2.9.1+rocm7.2.1`），启动一次确认 `Recognized AMD device ... RX 7900 XTX ... ROCm`
3. clone CCTech `ComfyUI-GGUF-Loader` v2.16.7（镜像加速）
4. 复制 `ComfyUI-ForceUnloadBeforeDecode`（自建节点，单文件）
5. `pip install gguf sentencepiece protobuf qwen-tts timm opencv-python-headless ...`，**transformers 锁 4.57.3**
6. 按 §4.4 表放齐 7 个模型文件（hf-mirror，走 Aria2UI 多线程）
7. 部署两个 bat（§4.1）并启动，日志见 73 节点注册
8. 导入三套工作流（§五）替换素材 → 按 §一参数跑 T2V 冒烟，再 I2V / R2V

---

## 八、已知排雷（详见 plan 文档 §8）

- ❌ 独立 nicolab28 `ComfyUI-ClipProj`（CCTech 内置同源，避免同名冲突）
- ❌ `ComfyUI-MiniMaxH3-Cache`（全局 monkey-patch 破坏 H3 生成）
- ❌ Optimization Suite / SageAttention / Tiled VAE（NV 专属或对 H3 无效）
- GGUF mmap 崩溃 `0xC0000005`（Windows）：第二个不兼容模型叠在第一个上加载导致 → 靠 §三 顺序驻留规避
- 若 I2V/R2V 引用图/视频失败：换官方 bf16 编码器 `qwen3vl_4b_fp8_scaled.safetensors` 或 heretic bf16（8.3GB）