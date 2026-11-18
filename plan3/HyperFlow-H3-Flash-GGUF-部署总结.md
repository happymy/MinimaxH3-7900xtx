# HyperFlow H3 Flash（GGUF）Comfy Desktop 部署总结

> 落地目录：`D:\localAI\ComfyUI-last\plan3\`
> 新环境：`C:\Comfy-Desktop\`（ComfyUI 0.45.2 / ROCm 7.14 / RX 7900 XTX）
> 完成日期：2026-11-11（连续生成问题 2026-11-12 定位并解决）
> 状态：**已完成**。单次 3 连测通过（277.87 / 281.70 / 293.65 s）；连续第二次爆显存已定位为「上一轮没卸」，解法见 §7.5，实测通过；API 工作流 11 条全部实跑通过（§6.2）
>
> ### ✅ 强烈建议：就按本文这一套部署
>
> **换机 / 重装 / 想复现，一律照本文（`plan3\`）做** —— Comfy Desktop + HyperFlow H3 Flash GGUF +
> Qwen3-VL-8B heretic + `mmh3-8b-ClipProj-v3.1-mlp`。旧 portable 环境（`plan\`）那套原生 H3 20 步方案
> **已废弃**：同为 5 s 片，旧方案 480P ≈ 570 s，本方案 720P ≈ 280 s，画质与速度都是两倍差距。
> 不要再回头拼旧参数、旧模型清单或旧工作流。

---

## 1. 目标

在**新装的 Comfy Desktop 环境**里跑通 HyperFlow H3 Flash（MiniMax H3 14B 的加速蒸馏版），
输出带音轨的短片，并尽量复用旧 portable 环境（`plan\` / `plan2\`）已有的模型。

硬约束：

| 约束 | 值 | 后果 |
|---|---|---|
| 显卡 | RX 7900 XTX，gfx1100，24 GB | 无 Blackwell FP4、无 CUDA |
| 内存 | 32 GB | 放不下 32B 编码器 |
| 旧环境 | **不许改、不许升级** | 只能单向复制资产 |
| 前台 | 用户可能正在跑别的 ComfyUI 任务 | 安装/校验不得占 GPU |

---

## 2. 结论

| 项 | 结果 |
|---|---|
| 工作流 | **4 条 UI**（`hyperflow_{t2v,i2v,flf2v,ref2v}_clipproj_8b.json`）+ **11 条 API payload**（`plan3\API_workflows\`：4 条 H3 同名 + 6 条 qwen + 1 条 TTS，§6.2），均带音轨 |
| 应用侧 | API 工作流**已完成 [infinite-creation](https://github.com/SwotAtmk/infinite-creation) 适配**（§6.2；`plan3\README.md` §8.5） |
| 实测 | t2v 3 次成功，`Prompt executed in` 277.87 / 281.70 / 293.65 s；11 条 API payload 全部实跑通过 |
| 成片参数 | 1344×768 @ 24 fps，124 帧，5.167 s，H.264 + AAC 32 kHz 立体声 |
| 启动参数 | `--enable-manager --use-ck-attention --preview-method auto --disable-smart-memory --cache-none --fp16-intermediates`（6 条，逐条语义见 §3；`--fast-disk` 本机自动 True） |
| 显存 | **已在极限**（§7.3）——开跑前必须清空其它占显存的程序。同一个任务整卡实测 21.43 GB，torch 只报 13.54 GB，口径差 5.8 GB（§7.10） |
| 连续生成 | **每次提交前必须先 `/free`**（§7.5）：跑完一次会留 14.5 GB 驻留，第二次装编码器时必爆。4 s 拿回来，只多付 13 s 重载 |
| 静态校验 + 实跑 | 4 个 UI 图各自双向一致（link/node：t2v 18/16、i2v 19/17、flf2v 20/18、ref2v 21/18）；**11 条 API payload 引用全解析并全部实跑通过**（§6.2）；`bat\` 的 8 种 API 图节点名与输入名全解析（`check_graphs.py`）；GGUF 结构与 loader 预期逐项对上 |
| 提示词 | 按 `bat\提示词模板\MiniMax-H3-提示词书写规则.md` 写；**不能写禁令**（§9）：CFG 锁死 1、无负向分支，`no anime` 里的词照样进条件向量 |
| 遗留 | 8B 投影的语义保真度未逐项评估 |

---

## 3. 环境

| 项 | 旧（`plan\` / `plan2\`） | 新（本文件） |
|---|---|---|
| ComfyUI | 0.38.0 | **0.44.2** |
| Python | `python_embeded` | `.venv` **3.13.12** |
| torch | 2.9.1+rocm7.2.1 | **2.12.0+rocm7.14.0** |
| comfy-kitchen | 0.2.36 → 0.2.37 | **0.2.40** |
| comfy-aimdo | 0.5.5 | **0.6.0** |
| numpy | — | 2.5.4 |
| transformers | — | 5.20.2 |
| 前端 / 模板 | 1.53.6 / 0.11.70 | 1.57.6 / 0.11.103 |
| 模型根目录 | `ComfyUI\models\` | `C:\Comfy-Desktop\ComfyUI-Shared\models\`（Desktop 托管） |
| 启动方式 | `.bat` | Desktop 内置启动器 + 自定义参数 |

`manifest.json` 记的基线是 `v0.42.1-env1`，ComfyUI 已自行更新到 0.44.2
（`comfyui_version.py` 与启动日志一致）。

桌面版启动器**不能**在命令行里加参数，要改 Desktop 的启动参数框，实际等价于：

```
python -s ComfyUI\main.py --feature-flag show_signin_button=true --enable-assets --enable-manager \
  --extra-model-paths-config "...\Comfy Desktop\instance-model-paths\inst-1794395587998.yaml" \
  --input-directory  D:\Comfy-Desktop\ComfyUI-Shared\input \
  --output-directory D:\Comfy-Desktop\ComfyUI-Shared\output \
  --use-ck-attention --preview-method auto \
  --disable-smart-memory --cache-none --fp16-intermediates   # ← 这 5 条是我们加的
```

`--enable-manager` 是 Desktop 自带（Manager 要开，`custom_nodes` 里 qwen GGUF 那处修补靠它加载）。
**`--fast-disk` 不写** —— `comfy/storage.py:104-110` 按磁盘类型自动判定，本机 SSD 判为 True；
**`--reserve-vram` / `--disable-pinned-memory` 也不写** —— 两条都试过，实测把 usable 从 15,299 MB 压到 9,634 MB，
摘掉后 0.45.2 复测回到 15,299 MB、H3 6 步 37.98 s/it（`plan3\README.md` §1.3）。
2026-11-18 又单独试了一次 `--reserve-vram 6`：usable 压到 9,855 MB，但整卡物理峰值仍是 21.43 GB，
**一个字节没省**（§7.10）—— 这两个参数改的是装载预算，不是物理占用。

逐条语义（本机 `comfy\cli_args.py` 原文核对，2026-11-18）：

| flag | 源码原文 | 本机作用 |
|---|---|---|
| `--use-ck-attention` | comfy-kitchen attention | 采样快一个数量级；kernel 不支持时直接 `exit(-1)` 拒启 |
| `--preview-method auto` | `LatentPreviewMethod.Auto`，在 `latent_preview.py:102` **落到 `latent2rgb`** | 每步对 latent 做一次小矩阵乘出缩略图；不加载 TAESD 权重、几乎不吃显存，**不影响判爆与耗时基线** |
| `--disable-smart-memory` | 装不下就激进退回系统内存，而非尽量留在显存 | 编码器（8.47–14.54 GB）用完就退，不常驻抢 DiT 的位置 |
| `--cache-none` | `NullCache`，**每次运行所有节点全部重算** | 省 RAM/VRAM；代价是每次都要重新编码提示词，第二次跑同一图不会更快 |
| `--fp16-intermediates` | 节点间中间张量 fp16（Experimental） | 压采样激活，362 帧 4 窗口能站住的前提之一 |
| `--enable-manager` | 打开 Manager | 加载 `custom_nodes` |

§7.9 的耗时基线（874 s / 1,216 s / 1,066 s）和 `bat\` 脚本都在本机这套参数下跑出来的
（`--preview-method auto` 的缩略图开销已包含在内：latent2rgb 是对 latent 的小矩阵乘，不占权重显存）。

---

## 4. 选型：为什么是 GGUF + 8B + ClipProj

这一节是本次最贵的部分，**换方案前先读完**。

### 4.1 官方给了两套权重，只能用 GGUF 那套

HyperFlow 仓库同时发布 `fl2va_gguf/` 与 `fl2va_int8_convrot_comfyui/`。选 GGUF 的理由：

| 理由 | 证据 |
|---|---|
| 体积 | fl2va INT8 约 16.0 GB，GGUF Q4_K_M **9.05 GB** |
| 内核路线 | 官方 README：INT8 线性的计算走 ComfyUI 自带 INT8 kernel，**长片段还要走 comfy-kitchen 的 Triton kernel**（按行分块，规避 32 位偏移） |
| 本机无 triton | `.venv` 里 `importlib.util.find_spec("triton")` → `None`；`comfy/quant_ops.py:33-41` 在 import 失败时 `ck.registry.disable("triton")`，INT8 内核可用性**无法保证** |
| 模型卡偏好不适用 | 模型卡写「diffusion 首选 `int8_convrot`，前提是能用 cu130 的 pytorch」——那是 CUDA 的前提，ROCm 没有这条路径 |

结论：**GGUF 是唯一有把握的一条**。将来若要试 INT8，先跑 `comfy_kitchen.registry.list_backends()`
确认 triton/hip 后端是否真的拉起来了。

### 4.2 32B 文本编码器在这台机器上不可达

原版工作流用 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（15.7 GB）。它在 gfx1100 上跑不了，
**但原因不是「nvfp4 需要 Blackwell」**（模型卡明确说"The nvfp4 text encoder does not require
Blackwell GPU to use"）。真正的原因是 ComfyUI 的量化门控：

```python
# comfy/model_management.py:2057
def supports_nvfp4_compute(device=None):
    ...
    if not is_nvidia():
        return False

# comfy/ops.py:1872
def get_disabled_quant_formats(device=None):
    if not comfy.model_management.supports_nvfp4_compute(device):
        disabled.add("nvfp4")
```

AMD 上 nvfp4 被禁 → 编码器退回 `MixedPrecisionOps`（bf16）——启动日志里那句
`Using MixedPrecisionOps for text encoder` 就是这个意思。于是 32B 要按 **bf16 常驻**：
≈ 64 GB，24 GB 显存 + 32 GB 内存都装不下。

本地另有 `qwen3vl_32b_minimax_h3-Q4_K_M.gguf`（18.22 GB），这条路也堵死：
ComfyUI 认 32B 的判据在 `comfy/sd.py:1815`，要求
`visual.deepstack_merger_list.0.norm.weight`（**无 `model.` 前缀**）与 `model.layers.49.*` 同时存在。
GGUF 转换只打包 LLM，**不含 vision tower、也没有配套 mmproj**，判据不成立 → 继续往下走到通用分支，
按宽度 5120 认成 `MISTRAL3_24B`。**它不会报错，会静默走错编码器实现。**

> 另有隐性代价：没有 vision tower，ref2v（用参考图锁角色）这条路也一起废了。

### 4.3 所以走 8B + 校准投影

| | Qwen3-VL-8B | Qwen3-VL-32B |
|---|---|---|
| 隐藏宽度 | 4096 | 5120（＝ DiT 要的维度） |
| 层数 | 36 | 50（截断） |
| 到 DiT | 过一层学出来的矩阵 | 零转换 |
| 实测 cosine | 线性 0.9289 / `-mlp` **0.9449** | 1.0 |
| 体积 | 10.02 GB（heretic fp8，**显存占 16.33 GiB**，见 §7.7） | 15.7 GB nvfp4（本机要摊成 64 GB bf16） |

ClipProj 能这么做的原理：H3 只要**单个 5120 维隐藏态**（不像 Krea2 要 12 个 tap），
且 4B / 8B / 32B **共用同一 tokenizer**（151936），所以可以逐位置做闭式岭回归。

选型细节：

- **用 8B，不用 4B**：4B cosine 0.712，差得远。
- **用 `-mlp` 版**（`mmh3-8b-ClipProj-v3.1-mlp`），不用线性版：0.9449 vs 0.9289。
- **不用 heretic 版**：ClipProj 作者的对照实测里，abliterated 编码器反而更差（-0.026 / -0.034）。
  **但本环境用的是 heretic**（用户指定，`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn`）——
  差在语义保真度，**不影响画风**，画风问题看 §9。
- **不用 `ClipProjLoader`（all-in-one）**：作者明确写单卡上有害——它会把编码器钉在卡上白占 4–9 GB。
  正确接法是原生 `Load CLIP`（type `boogu`）+ `ClipProj Apply`。

### 4.4 三个不能换的采样参数

| 参数 | 值 | 换了会怎样 |
|---|---|---|
| `HyperFlowSigmas` | **6** | 4 更快但糙、8 更细但慢，都不是默认分布 |
| `KSamplerSelect` | **euler** | 不报错，出烂片 |
| `BasicGuider` | **CFG 1**（无负面提示词） | 不报错，出烂片 |

模型是蒸馏过的，按这套 schedule 训练。这三项是「改了不报错，只是白跑 5 分钟」的典型。

---

## 5. 安装清单

### 5.1 自定义节点

| 节点 | 来源 | commit | 备注 |
|---|---|---|---|
| `ComfyUI-GGUF` | `city96/ComfyUI-GGUF` | `6ea2651` | **必须是 city96 原版**（见 §8.4） |
| `ComfyUI-HyperFlow-Flash` | `Video-Rebirth/ComfyUI-HyperFlow-Flash` | `356649c`（v1.1.1） | 提供 4 个 loader 节点 |
| `ComfyUI-ClipProj` | 从旧环境整目录复制 | `c01ba8f`（v0.1.4） | 无 pip 依赖 |

ClipProj 的两个 hook 在 0.44.2 上签名仍然吻合，加载不会失败：
`execution.PromptExecutor.execute_async`（`execution.py:736`）、
`comfy.model_management.unload_all_models`（`model_management.py:2171`）。

git clone 一律走加速代理（大陆直连 GitHub 会断）：

```powershell
git clone --depth 1 https://v4.gh-proxy.org/https://github.com/city96/ComfyUI-GGUF <custom_nodes>\ComfyUI-GGUF
git clone --depth 1 https://v4.gh-proxy.org/https://github.com/Video-Rebirth/ComfyUI-HyperFlow-Flash <custom_nodes>\ComfyUI-HyperFlow-Flash
```

### 5.2 pip

只有一个包要装：

```powershell
<ComfyUI>\.venv\Scripts\python.exe -m pip install gguf -i https://mirrors.aliyun.com/pypi/simple/
```

- 实得 **gguf 0.19.0**，依赖 `numpy 2.5.4` / `pyyaml` / `requests` / `tqdm` 全部已满足。
- **清华源对这个包返回 403**（`pypi.tuna.tsinghua.edu.cn/.../gguf-0.19.0-...whl`），换阿里云即成功。
- `sentencepiece` / `protobuf` 是 ComfyUI-GGUF 的 optional，本例不需要。

### 5.3 模型（6 个文件，全部字节数与源一致）

| 角色 | 目录 | 文件 | 字节 | GB |
|---|---|---|---|---|
| DiT（GGUF） | `diffusion_models` | `minimax_h3_fl2va_hyperflow_flash_14b-Q4_K_M.gguf` | 9,053,456,480 | 9.05 |
| DiT（GGUF，ref2v 段 0） | `diffusion_models` | `minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf` | 9,220,352,512 | 9.22 |
| 文本编码器 | `text_encoders` | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | 10,017,064,632 | 10.02 |
| 文本编码器（**推荐替换**，见 §7.7） | `text_encoders` | `qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors` | 10,979,853,342 | 10.98 |
| 投影矩阵 | `clip_projections` | `mmh3-8b-ClipProj-v3.1-mlp.safetensors` | 604,093,248 | 0.60 |
| 视频 VAE | `vae` | `minimax_h3_video_vae_fp16.safetensors` | 5,207,808,496 | 5.21 |
| 音频 VAE | `vae` | `minimax_h3_audio_vae_fp32.safetensors` | 605,254,808 | 0.61 |

落点：

```
C:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models\    ← 两个 DiT（fl2va + ref2va）
C:\Comfy-Desktop\ComfyUI-Shared\models\text_encoders\       ← 8B heretic 编码器
C:\Comfy-Desktop\ComfyUI-Shared\models\vae\                 ← 两个 VAE
C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\clip_projections\   ← 投影矩阵（不在共享目录）
```

两个 VAE、投影矩阵、heretic 编码器都从旧环境 `robocopy` 直接复制（省掉 25 GB 下载）；
编码器复制到新环境的 `text_encoders` 时也是**复制**，不是硬链接（旧环境不许动）。
两个 DiT GGUF 是新下的：hf-mirror + Aria2 RPC（16 线程），约 15 MB/s，每个约 10 分钟。

### 5.4 Desktop 的模型路径机制（容易踩）

`C:\Users\<user>\AppData\Roaming\Comfy Desktop\instance-model-paths\inst-*.yaml`
由 Desktop 生成，给**两个** `base_path`（`C:\Comfy-Desktop\ComfyUI-Shared\models` 与
`D:\Comfy-Desktop\ComfyUI-Shared\models`），每个下面挂全套子目录名，**其中包含
`clip_projections`**。启动日志会逐行打印：

```
Adding extra search path diffusion_models C:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models
...
Adding extra search path clip_projections C:\Comfy-Desktop\ComfyUI-Shared\models\clip_projections
Adding extra search path clip_projections D:\Comfy-Desktop\ComfyUI-Shared\models\clip_projections
```

这些是**追加**在 ComfyUI 自身 `models\` 之后的，不是替换。在此基础上 ClipProj 又补一刀：

```python
# clipproj_projection.py:51  register_folder()
path = os.path.join(folder_paths.models_dir, "clip_projections")
existing = folder_paths.folder_names_and_paths.get(FOLDER)
if existing is None:
    folder_paths.folder_names_and_paths[FOLDER] = ([path], {".pt", ".safetensors"})
elif path not in existing[0]:
    existing[0].append(path)          # ← 已经存在时是 append，不是覆盖
```

所以 `clip_projections` 实际有**三个**候选位置：
两个共享目录（yaml 给的）+ `ComfyUI\models\clip_projections`（ClipProj 追加的）。
本次把矩阵放在第三个，实测被正确列出并加载。

### 5.5 绝对不要装的东西

**`ComfyUI-GGUF-Loader`（CCTech 分叉）**——旧环境 `plan2` 用的就是它（改过 `IMG_ARCH_LIST`）。
它和 city96 原版**注册同一个节点名 `UnetLoaderGGUF`**，按 custom_nodes 目录名排序，排在后面的会覆盖前面的。
HyperFlow 的 `GGUFBackend.find()` 会拿到分叉的实现，而分叉没有顶层 `dequant` 模块 → `KeyError`。

**`ComfyUI-UnloadModels`**（`UnloadCPUModels` / `UnloadAfterSampling`）—— 本机装了又删掉，见 §8.10。
它在 `--cache-none` 下没有可卸的东西，而真正要卸的是**上一轮**的残留，只能在下一次提交前调 `/free`。

顺带：`loader_nodes.py:117` 的 `supports_disk()` 要求 `GGUFModelPatcher` 具备
`mmap_released` 与 `pin_weight_to_device`；缺任何一个就退回内存模式，`--fast-disk` 白设。

---

## 6. 工作流改了什么

4 个文件，全部由 `tools\make_workflow.py` 从官方 `example_workflows\hyperflow_<family>.json`
生成（`tools\stock_<family>.json` 是快照），可随时重跑：

| 文件 | DiT | 额外输入 | 输出前缀 |
|---|---|---|---|
| `hyperflow_t2v_clipproj_8b.json` | `fl2va` | — | `hyperflow/t2v` |
| `hyperflow_i2v_clipproj_8b.json` | `fl2va` | `first_frame` | `hyperflow/i2v` |
| `hyperflow_flf2v_clipproj_8b.json` | `fl2va` | `first_frame` + `last_frame` | `hyperflow/flf2v` |
| `hyperflow_ref2v_clipproj_8b.json` | **`ref2va`** | 2 张参考图（`<Picture 1>`/`<Picture 2>`） | `hyperflow/ref2v` |

四个图的骨架相同，脚本按 `type` 找节点（不写死 id），每个 family 只做这三处改动：

| # | 改动 | 原 | 新 |
|---|---|---|---|
| 1 | `Load CLIP` 模型 + `type` | `qwen3vl_32b_minimax_h3_nvfp4_awq` / `minimax` | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn`（或 `_int8_convrot`，§7.7）/ **`boogu`**（走 `sd.py` 的 Qwen3-VL-8B + H3 分支） |
| 2 | 新增 `ClipProj Apply`，串进 clip 链 | CLIP → `MiniMaxH3*ToVideo.clip` | CLIP → **Apply**(`mmh3-8b-ClipProj-v3.1-mlp`) → `MiniMaxH3*ToVideo.clip` |
| 3 | `HyperFlowLoader.weights_in` | `auto` | **`disk`**（装不下的权重留在 GGUF 映射里流式读，不复制进 RAM） |

图内 MarkdownNote 一并重写成对应的 8B 清单。

**未改动**：两个 `VAELoader`、`MiniMaxH3*ToVideo`（1344×768×124）、
`RandomNoise`（seed 42 fixed）、`HyperFlowSigmas`（6）、`KSamplerSelect`（euler）、
`BasicGuider`（CFG 1）、`SamplerCustomAdvanced`、`VAEDecode` ×2、`CreateVideo`（24 fps）、
`SaveVideo`。

自检（`tools\check_workflow.py`，4 个图逐个跑）：

```
links: 18 nodes: 16                              # t2v；i2v 19/17、flf2v 20/18、ref2v 21/18
ok: 8B + ClipProj wiring as expected (MiniMaxH3ImageToVideo, weights_in=disk)
ok: every link agreed on both ends
```

`check_workflow.py` 从 `ClipProjApply` 反查两端，不再是写死 id 的断言，所以 4 个图共用一份检查。

### 6.1 `bat\` 脚本（API 直连，不经网页）

从 `plan\bat` 移植，只改 `build_graph()` 里的 4 处（loader / CLIP 链 / sigmas / sampler），
分段、末帧续接、ffmpeg 拼接逻辑原样复用：

| 目录 | 入口 | 作用 |
|---|---|---|
| `multisegment_8b_heretic\` | `gen_h3_multisegment-8b-heretic.bat` | 一条提示词、N 段等长，段间末帧续接 |
| `scenes_8b_heretic\` | `gen_h3_scenes-8b-heretic.bat` | 每段独立提示词 + 独立时长，超长自动拆 |
| `scenes_ref_8b_heretic\` | `gen_h3_scenes_ref-8b-heretic.bat` | 同上 + 参考图/视频（段 0 走 ref2va） |
| `ref2va_8b_heretic\` | `gen_h3_ref2va-8b-heretic.bat` | 参考图生视频，多段末帧续接 |
| `extract_frames\` | `gen_extract_frames.bat` | 抽首/中/末帧（与模型无关） |
| `qc_frames\` | `gen_h3_qc_frames.bat` | 均匀抽 N 帧 + contact sheet（与模型无关） |
| `free_vram\` | `free_vram.bat` | 通用 `/free`：`--status` / `--interval N` 挂机定时清 / `--no-verify` |
| `提示词模板\` | — | `MiniMax-H3-提示词书写规则.md`（19 KB，**写提示词前先看**）+ 视频 / 静帧 / 照片三个 `.txt` 示例。规则 md 与 `.txt` 冲突时以 md 为准（§9） |
| `测试素材\` | — | 两张示例参考图（`1_女孩.png` / `2_男孩.png`），与 `ref2va_8b_heretic\img\` 同内容 |

| 移植点 | 旧（`plan\bat`） | 新（`plan3\bat`） |
|---|---|---|
| DiT | `UnetLoaderGGUF` + `*_pruned-Q4_K_M` | `HyperFlowLoader(weights_in='disk')` + `*_hyperflow_flash_14b-Q4_K_M` |
| CLIP | `CCTechClipProjLoader`（判官版，单卡钉死） | `CLIPLoader(boogu)` → `ClipProjApply` |
| 投影 | `mmh3-8b-ClipProj-v3.1`（非 mlp） | `mmh3-8b-ClipProj-v3.1-mlp` |
| sigmas + sampler | `BasicScheduler simple` 20 步 + `res_multistep`/`er_sde` | `HyperFlowSigmas`（4/6/8）+ `euler`，CFG 1 |
| 采样后卸载 | `ForceUnloadBeforeDecode` ×2 | 删除，改由各脚本内的 `free_vram()`（POST `/free`）负责 |

`--steps` 只接受 `4/6/8`（`HyperFlowSigmas` 的硬约束），交互输入越界回退默认 6。

### 6.2 API 工作流（`plan3\API_workflows\`）

旧环境 `plan\API_workflows\` 是交付层。新环境这一步**由界面图离线转换得到**：源是
`user\default\workflows\` 的 11 份界面工作流，输出是 infinite-creation 直接 `POST /prompt` 的 API 格式；
input 名与 widget 顺序全部取自本机 ComfyUI 的 `object_info`，不手写猜测。转换规则、文件名映射与落地
细节见 `plan3\README.md` §8。

| 项 | 内容 |
|---|---|
| 起点 | `user\default\workflows\` 的界面工作流（`molbal_workflows\` 里有一份逐字节镜像） |
| 转换 | 离线 UI→API：子图展开、动态组合 / autogrow 输入展开、seed 类前端状态丢弃（§8.1） |
| 产物 | `plan3\API_workflows\` 11 条：4 条 H3（与 UI 同名）+ 6 条 qwen（`_api` 后缀）+ 1 条 TTS |
| 不进 workflows 目录 | API 格式拖进界面必报 `TypeError: e is not iterable`；直接 POST `/prompt` |

H3 四条相对官方 32B 模板的三处改动与 UI 图逐项一致，只是引用从 link id 换成 `[节点id, 输出槽]`：

| # | 改动 | API 里的形态 |
|---|---|---|
| 1 | 换 8B heretic 编码器 | `CLIPLoader.inputs`：`clip_name` = `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`（int8 副本用 `..._int8_convrot.safetensors`，见 §7.7），`type` = `boogu` |
| 2 | 插 `ClipProjApply` | 新增节点（t2v `16`、i2v `22`、flf2v `23`、ref2v `23`），`MiniMaxH3*.clip` 从 `["2",0]` 改指它 |
| 3 | 权重驻留策略 | `HyperFlowLoader.inputs.weights_in` = `disk`（可选输入，官方图没写，默认 `auto`） |

节点数：t2v 15 / i2v 16 / flf2v 17 / ref2v 18。i2v、flf2v、ref2v 各带 1–2 个 `LoadImage`（`20`/`21`），
模板里是占位文件名（`first_frame.png` / `ref_image_1.png`），提交前要换成 `ComfyUI\input\` 下真实存在的文件。
ref2v 另有转换后补的 **`115` `ResolutionSelector`**（宽高改由它出，供应用的 `resolution` / `aspect_ratio` 使用，
`plan3\README.md` §8.3），另外三条没有。

调参位置（全是 model input，没有 widget）：

| 参数 | 位置 |
|---|---|
| 提示词 / 宽 / 高 / 帧数 | `5.inputs.{prompt,width,height,length}`（ref2v 宽高 = `["115",0/1]`） |
| 步数（仅 4/6/8） | `6.inputs.steps` |
| 种子 | `8.inputs.noise_seed` |
| 输出前缀 | `14.inputs.filename_prefix` |
| 参考/首末帧图片 | `20`/`21` 号 `LoadImage.inputs.image` |

自检：`& $py check_workflow.py ..\API_workflows\*.json`。`check_workflow.py` 按文件形状分流 ——
有 `nodes` 走 UI 校验，没有就走 API 校验（`[id, slot]` 必须指向本文档内的节点、输入值只能是标量或引用、
不允许 `widgets_values` 残留）；带 `HyperFlowLoader` 的图再断言 ClipProj 接线、`boogu`、`weights_in=disk`、
`euler`、`steps ∈ {4,6,8}`，qwen / TTS payload 只查引用。实测输出（2026-11-13，11 条全过）：

```
api: 15 nodes, BasicGuider, CLIPLoader, ClipProjApply, CreateVideo, HyperFlowLoader, ...
steps=6
ok: references resolve, 8B + ClipProj wiring as expected (weights_in=disk)
...
api: 4 nodes, PreviewAudio, Qwen3TTSModelLoader, Qwen3TTSVoiceDesign, SaveAudio
ok: references resolve (not an H3 graph, no ClipProj assertions)
```

**已实测（手动提交 `/prompt`）**：11 条 payload **全部实际跑通**，不只是静态校验 —— H3 四条、
qwen-image 六条（t2i / image_edit / background_removal × Q4/Q8）、TTS 一条。

**适配已完成**：11 条 payload 已随 [SwotAtmk/infinite-creation](https://github.com/SwotAtmk/infinite-creation)
落地（`src\infinite-creation\workflows\`），`workflow-specs.js` 的 sourceFile / roles 与
`workflow-runner.js` 的 `mapRoleValue` / `bindMedia` 同步改完，`npm test` 253 项通过（`plan3\README.md` §8.5）。

静态自检（不加载模型、不提交）：

```powershell
& $py "D:\localAI\ComfyUI-last\plan3\bat\check_graphs.py"
# 期望最后一行：ok: every node reference and input name resolves
```

它把 4 个脚本的 8 种图都 build 一遍，对照官方 API 图检查节点类型与输入名 ——
ComfyUI 对不认识的输入是**静默忽略**的，写错名字只会「出图但参数没生效」。

---

## 7. 实测

### 7.1 三次成功运行的日志（t2v，`hyperflow_t2v_clipproj_8b.json`）

| 时间 | 耗时 | 输出 |
|---|---|---|
| 21:43:06 | **281.70 s** | `t2v_00001_.mp4` |
| 21:51:37 | **277.87 s** | `t2v_00002_.mp4` |
| 22:02:01 | **293.65 s** | `t2v_00003_.mp4` |

产物在 `D:\Comfy-Desktop\ComfyUI-Shared\output\hyperflow\`，`ffprobe`：

```
video: h264, 1344x768, 24/1, 124 frames
audio: aac, 32000 Hz, 2 channels
duration: 5.166688 s, size: 1.31 MB
```

### 7.2 单次 294 s 花在哪

| 阶段 | 耗时 | 日志 |
|---|---|---|
| 文本编码（8B fp8） | ~10 s | `Requested to load BooguTEModel_` → DiT 加载开始 |
| DiT 加载 | ~5 s | `HyperFlow: 18 factorized blocks, two-time=True, 6-step schedule` |
| **采样 6 步** | **~230 s** | `6/6 [03:50<00:00, 38.4s/it]` |
| VAE 解码 | ~31 s | 音频 576 MB staged、视频 4965 MB staged |
| 合计 | **293.65 s** | `Prompt executed in 293.65 seconds` |

关键日志（每次启动都一样，可作为「装对了」的判据）：

```
Using pytorch attention
Using Comfy Kitchen attention            ← --use-ck-attention 生效
Model storage policy: fast_disk=True     ← 自动判定（没传 --fast-disk，见下）
Requested to load BooguTEModel_          ← type=boogu 走对了分支
model_type FLOW_AV
HyperFlow: 18 factorized blocks, two-time=True, 6-step schedule
HyperFlow: transformer weights in disk (weights_in=auto)
loaded completely; 15298.95 MB usable, 8936.71 MB loaded, full load: True
```

`weights_in=auto` 不是「猜」：它查 `comfy.storage.model_fast_disk([path])`，
而那个函数在 `args.fast_disk` 为真时直接返回 True（`comfy/storage.py:104`），
`disk` 走的是同一个判断（`storage.py:105`），所以上面那行日志现在会显示 `weights_in=disk`，
行为不变。`args.fast_disk` **本机没传也已经是 True**（`storage.py:104-110` 按磁盘类型自动判定），
真实启动参数里没有 `--fast-disk`；显式 `--disable-fast-disk` 才会退回内存模式，
而那样 32 GB 内存顶不住 9 GB DiT + 10 GB 编码器 + 采样激活。

### 7.3 显存已在极限（用户实测结论，务必照做）

**1344×768×124 帧 / 6 步这套参数已经把 24 GB 用满。**
开跑前必须关掉所有占显存的程序（浏览器硬件加速、其它 ComfyUI 实例、游戏、录屏等）。
否则 **OOM，或退化成显存↔系统内存的数据交换，单次生成从 ~5 分钟变成 ~16 分钟**。

> **2026-11-17 更新**：下面这张表里缺了最大的那一项——**文本编码器**。
> fp8 编码器实际占 14.54 GB（staged 16,721 MB），是真正撞墙的地方；
> 换成 heretic 的 `int8_convrot` 版降到 8.47 GB（staged 10,470 MB），
> 上述"关程序"的硬要求随之解除。详见 **§7.7**。
> 另外 VAE 解码那一段（5.5 GB）本节描述的"最挤"判断仍然成立。

日志里能看出余地有多薄：

| 项 | 值 |
|---|---|
| 总显存 | 24,560 MB |
| 加载时可用 | 15,298.95 MB |
| DiT 实际载入 | 8,936.71 MB |
| 视频 VAE（解码时 staged） | 4,965 MB |
| 音频 VAE（解码时 staged） | 576 MB |

> **2026-11-18 补记**：上表的「总显存 24,560 / 可用 15,299」是 **HIP 自己的账**
> （`torch.cuda.mem_get_info()`），不是任务管理器。同一个任务同日实测整卡真实占用 **21.43 GB**
> （本进程 19.35 + dwm 等 2.08），共享显存 0.53 GB。「显存已在极限」这个判断依然成立，
> 但别拿上表的数字去对任务管理器 —— 口径差 5.8 GB，见 **§7.10**。

采样结束时 DiT 还占着，紧接着就要摊 5.5 GB 的 VAE —— 这一段是最挤的。
aimdo 0.6.0 的「dynamic VRAM loading / Staged」在显存紧的时候会把权重推来推去，
一旦要跨到系统内存，就是那 16 分钟。

**因此**：

- 分辨率可以再往上探（换 int8 编码器后 `1344×768` 与 `1280×720` 的采样余量几乎相同），
  但**帧数**才是成本项：见 §7.8 的长度推演
- 要更长就分段生成再拼（`bat\multisegment*` / `bat\scenes*`，见 §11）
- 要更快就 `HyperFlowSigmas=4`（牺牲质量），别指望 `--fast-disk` 再挤时间
- **要连跑第二次，先看 §7.5**：不是这套参数太极限的问题，是上一轮的权重还驻留在显存里

### 7.4 试跑用的是长提示词

三次实测用的提示词是官方示例那条**长提示词**，不是短关键词：

```
A street musician plays a weathered acoustic guitar on a cobblestone corner at golden hour.
The camera slowly pushes in from a wide shot to a medium close-up as passers-by drift through
the warm backlight. Soft strumming, distant chatter and a passing tram bell fill the soundtrack.
```

282 字符 / 47 词，比旧环境 `plan\` 的 t2v 基线（169 字符短提示词）长一倍以上。
这点值得记一笔：**0.2.36 曾经在长提示词上出过 CK 回归**（图片「脏」、长提示词丢失），
0.2.40 下这条长提示词没有复现——出片正常、音轨也在。

### 7.5 连续第二次生成必爆：诊断与解法（2026-11-12 实测）

**现象**：第一次成功（~294 s），第二次必在**装载文本编码器**时爆，日志停在
`Requested to load BooguTEModel_` 之后，一个字都不再往下写，只能重启进程。

**账目**（`/system_stats` 的 `vram_free`，实测）：

| 时机 | vram_free |
|---|---|
| 冷启动 | 23.82 / 23.98 GB |
| 跑完一次、未卸载 | **9.42 GB** |
| `POST /free` 后 1 s | 16.98 GB |
| 后 3 s | 22.46 GB |
| 后 4.1 s | **23.52 GB** |

跑完一次时 DiT 8.9 + 视频 VAE 5.0 + 音频 VAE 0.6 ≈ **14.5 GB 仍驻留**；
第二次要装 10.59 GB 的编码器 → 需 25.0 GB，24 GB 装不下。
**这不是泄漏，是上一轮没卸。** 冷启动 23.82 与卸载后 23.52 只差 0.30 GB（碎片 + context）。

**解法**：每次点 Queue **之前**跑一次：

```powershell
& "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 `
  "D:\localAI\ComfyUI-last\plan3\t2v\step0_free.py"
```

脚本 POST `/free`（`unload_models` + `free_memory`）后**轮询到 `total - 1.5 GB` 才返回**，
达不到就报 `FAILED` 并以退出码 1 结束（批跑可以据此中止）。实测 4.1 s 拿回 14.1 GB，
第二次生成只多付 **13 s** 重载（编码器 9.0 s + DiT 4.3 s），占 294 s 的 4.4%。

**为什么图内卸载节点不够**（`ClipProjFree(scope="all models")` 挂图尾，实测仍然爆）：

| | 图内 `ClipProjFree` | `/free`（worker 线程） |
|---|---|---|
| `unload_all_models()` | ✓ | ✓ |
| `soft_empty_cache()` | ✓ `force=True` | ✓ |
| `gc.collect()` | **✗** | ✓ （`main.py:432`） |
| 清执行缓存 `e.reset()` | **✗** | ✓ （`main.py:425`） |

`unload_all_models()` 只是把模型从 `current_loaded_models` 弹出并 `detach()`
（`model_management.py:2171` → `free_memory(1e30)`）。只要还有 Python 引用
（executor、`caches.outputs` 里的 latent / IMAGE），对象就活着，显存不还。
图内节点执行时整个 prompt 还在跑、引用链完整，所以卸了个寂寞。

上表说的是当初自写的 `ClipProjFree`。后来装的 `ComfyUI-UnloadModels` 补上了 `gc.collect()`，
但它在这套 `--cache-none` 下已经没有可卸的东西，而且时机也不对，同样做不到「下次提交前干净」，
所以已删掉 —— 见 §8.10。

**`--vram-headroom` 无效，而且注定无效**：它只传给
`comfy_aimdo.control.init_devices`（`main.py:296`），管的是 **DynamicVRAM 的预算**；
而 GGUF DiT 是 `disable_dynamic=True` 加载的（`loader_nodes.py:142`），压根不在这个账上。
1 / 2 / 3 / 4 GB 都不用试。

### 7.6 图缓存会让「第二次生成」的实验变假

`execution.py:455` 在跑每个节点前先查 `caches.outputs.get(unique_id)`，命中就把上次的
UI 输出重播一遍直接返回——**连 `SaveVideo` 都一样**。缓存 key 是输入签名
（`caching.py:117`：`[class_type, is_changed]` + 全部祖先签名）。本图
`noise_seed: 42` + `control_after_generate: "fixed"`，所以**同一提示词第二次是 0 秒、
不写新文件、不碰显存**。

- 判据：`Prompt executed in ≈ 280 s` 才是真跑；**`< 1 s` 就是缓存命中，这次实验作废**。
- 想连跑同一提示词：改 seed，或把 `control_after_generate` 设成 `randomize`，
  或先跑一次 `/free`（`e.reset()` 会新建整个 `CacheSet`，缓存一起清掉）。
- 所以「昨天连跑三次都成功」和「第二次必爆」并不矛盾：三次的输入必然不同，
  而爆的那次一定是改了提示词之后真正重跑的。

### 7.7 fp8 文本编码器在 gfx1100 上被摊成 bf16，换 int8_convrot 省 6.2 GB（2026-11-17 实测）

**真峰值是文本编码器，不是 DiT。** DiT（GGUF，`disable_dynamic=True`）稳定 8,937 MB；
编码器按**文件大小**骗人：`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` 磁盘只有
10.02 GB，日志却写 `16,721MB Staged`（1.67×）。

原因：gfx1100 没有 fp8 GEMM，`mixed_precision_ops(..., full_precision_mm=True)`
（`comfy/sd.py:114`，`ops.py` 只会抬高这个标志）要求 MMA 输入为 bf16 →
fp8 权重在**装载时就物化成 bf16**，staged 体积对齐的是 bf16 原始体积（16.33 GiB），
不是文件体积。上游 trace 佐证：fp8 只覆盖语言塔 50 层 × 7 个 linear，
vision tower 351 个 key 与 `embed_tokens` 恒为 bf16。

**对照实测**（同一台机器、同一批参数，唯一变量是 `CLIPLoader.clip_name`）：

| TE 文件 | 磁盘 | 日志 `Staged` | 编码阶段实测占用 | 864×480×73 |
|---|---|---|---|---|
| `..._fp8_e4m3fn` | 10.02 GB | **16,721 MB** | **14.54 GB**（free 9.44，撞墙） | 采样段 free 13.6–14.2 |
| `qwen3vl_8b_int8_convrot`（stock，仅做对照） | 9.35 GB | 8,916 MB | 10.48 GB（free 13.50） | — |
| `qwen3-vl-8b-heretic-1.3.0_int8_convrot` | 10.98 GB | **10,470 MB** | **8.47 GB**（free 15.51） | 69.3 s |

`int8_convrot` 是 ComfyUI 原生量化格式：int8 权重 + per-row scale，**运行时才反量化**，
staged 与磁盘 1:1，所以换它等于白拿 6.25 GB。

**破限不受影响**：HF `craftingmod/Qwen3-VL-8B-Heretic-INT8` 是
`DreamFast/Qwen3-VL-8B-Heretic-1.3.0` 的量化版（Apache-2.0），同一个去审查基座，
量化不会把拒答加回来；vision tower / embed / lm_head / 首末层按设计留 bf16。
下载走 `https://hf-mirror.com/craftingmod/Qwen3-VL-8B-Heretic-INT8/resolve/main/qwen3-vl-8b-heretic-1.3.0-int8convrot.safetensors`
→ `models\text_encoders\qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors`。
注意：Civitai 在本机不可达；aria2 的 Windows TLS 后端不认 `--check-certificate=false`，
会因吊销服务器脱机报 `80092013`，改用 `curl.exe --ssl-no-revoke -C - -L` 下。

**换完之后的余量**（`bat\bench\test_once.py`，同一长提示词、seed 12345、6 步、`--cache-none`）：

| 场景 | 耗时 | 采样段 free | min free |
|---|---|---|---|
| 864×480×73 | 69.3 s | 14.04 | 13.28 |
| 1280×720×124（5.17 s） | **252.3 s** | 13.06 | 10.57 |
| 1344×768×124（§7.3 的"上限"） | **287.3 s** | 13.01 | 10.28 |

两条 124 帧都一次跑通，不再需要为编码器关后台程序。`min free` 那 10.3–10.5 是采样里的
瞬时尖峰（预览/attention 临时缓冲，0.5 s 级）；它随帧数缓慢下滑，124 帧 12.7 GB → 413 帧 8.8 GB，详见 §7.8。

**顺带修正 §7.5**：第二次爆的原因是「上一轮 DiT 8.9 + VAE 5.0 + 音频 VAE 0.6 = 14.5 GB 驻留
+ 编码器要装」；把 16,721 换成 10,470 后这笔账从 25.0 GB 降到约 19 GB，仍建议 Queue 前跑 `/free`，
但已经不再是硬性失败点。

**顺带修正旧误读**：早先记的「四组实验 min vram_free 都是 9.44 GB」不是 DiT 峰值，
是编码器阶段的占用——DiT 装载前的 14.54 GB。

**落地（新一套，原文件一个字节没动）**：

| 新增 | 内容 |
|---|---|
| `bat\scenes_8b_heretic_int8\` | `gen_h3_scenes-8b-heretic-int8.py` + 同名 `.bat` + `prompt.txt` |
| `bat\multisegment_8b_heretic_int8\` | 同上，`multisegment` |
| `bat\ref2va_8b_heretic_int8\` | 同上，含 `img\` 示例参考图 |
| `bat\scenes_ref_8b_heretic_int8\` | 同上，含 `img\` |
| `API_workflows_int8\` | 4 条 H3 payload（`/prompt` 直接 POST） |
| `molbal_workflows_int8\` | 4 条 UI 图；已另存到 `user\default\workflows\*_int8.json`，界面里直接可见 |
| `bat\bench\test_once.py` | 显存曲线压测工具（`--clip` 可换编码器对照），判据见本节 |

新脚本与上游同名脚本逐字节同源，差异只有三处：`CLIP_NAME` 常量、docstring 里的模型名、
以及"不要开其它 GPU 程序"那条显存备注。冒烟测试：`512x288` / 2 s / 4 步 / seed 999 → 40.1 s 出片。

**边界：int8 省的是编码阶段，不会延长单段时长。** 编码完 TE 立即卸载，采样阶段显存里是
DiT 8,937 MB + 采样激活，与 TE 的量化档位无关。实测 480P 328 帧可用（345 两次结果不一致，按不可用）、
413 帧跨线，720P 124 帧稳、243 帧跨线；换回 fp8 同参数结果一样（用户手动对照，两套同样爆）。
所以 §7.8 那张长度表对 fp8 / int8 两套编码器通用 —— **想跑更长只能动 DiT、降分辨率或分段拼接**，
换编码器这条路已经到头了。

### 7.8 单段最长能出多少秒（2026-11-17 实测：不开窗口 480P 13.67 s / 720P 5.17 s）

> **本节是不开上下文窗口的结论。开了 `MiniMaxH3ContextWindows` 能到 1344×768 × 362 帧（15.08 s），
> 见 §7.9。**

**int8 编码器不延长单段时长** —— 这是本轮最重要的一条更正，替换掉本节此前的"工作集恒定、显存不是限制项"的推演。

换 int8 省下的 6.2 GB 发生在**编码阶段**，而长度墙出现在**采样阶段**，两者在时间上不重叠：
编码完 TE 就卸载（`Requested to load BooguTEModel_` 之后紧跟 `Requested to load MiniMaxH3`，
中间没有任何 TE 驻留），采样时显存里只有 DiT 8,937 MB + 采样激活。所以长度线
在 fp8 / int8 下是同一处 —— 用户手动对照确认：两套编码器同参数同样爆。

实测条件：破限 `qwen3-vl-8b-heretic-1.3.0_int8_convrot`、`bat\bench\prompt_long.txt`
（1,729 字符三字段长提示词）、6 步、seed 12345、每档前 `/free` 并等显存回到 `total - 1 GB`。

| 分辨率 | 帧数 | 秒 | 耗时 | 采样 s/it | min free | 结论 |
|---|---|---|---|---|---|---|
| 864×480 | 124 | 5.17 | 97.5 s | 10.2 | 12.73 | 稳 |
| 864×480 | 294 | 12.25 | 285.8 s | 36.6 | 10.25 | 稳 |
| 864×480 | 328 | 13.67 | 未实测 | — | — | **建议上限（保守）** |
| 864×480 | 345 | 14.38 | 362.4 s | 48.1 | 9.81 | 边界：本轮实测稳，手动测试爆 → 按不可用 |
| 864×480 | 413 | 17.21 | 1001 s 未完成 | 253.8 | 8.84 | **跨线** |
| 1280×720 | 124 | 5.17 | 252–260 s | 34.4 | 10.7 | 稳 |
| 1280×720 | 243 | 10.13 | 600 s 时中断 | 579 | 7.04 | **跨线** |

#### 判爆只看两件事：`Model Initializing` 耗时 + 每步 s/it

跨线不是 OOM，是掉进"每步重搬权重"的慢车道，所以 `/system_stats` 的 `vram_free`
不会报警（413 帧那档 min free 还有 8.84 GB）。可靠信号只有两个，爆了**至少 ×3**：

| 档位 | `Model Initializing` | 首步 s/it | 稳态 s/it |
|---|---|---|---|
| 864×480 / 1280×720 的正常档（124 帧） | ~10 s | 10.2 | 10.2 |
| 1280×720 × 243（跨线） | **9 分 39 秒** | **579** | 579 |

日志原文（720p 243 帧）：

```
MiniMaxH3 loaded completely; 9632.10 MB usable, 8936.71 MB loaded, full load: True
0%|  Model Initializing ...   1/6 [09:39<48:15, 579.14s/it, Model Initialization complete!]
```

`usable` 只剩 695 MB（9,632 − 8,937）。**这是"权重预算里的余量"，不是"权重被踢出去、每步搬回来"的证据** ——
同一行日志还写着 `full load: True`，权重是整份驻留的。`usable` 只是 `model_management.py:1025`
那串 `max/min` 从 `get_free_memory()` 现算的**装载预算**（AMD 上还挂了 `MIN_WEIGHT_MEMORY_RATIO = 0.4`），
它决定「能装多少」，不约束装进去之后占多少（`--reserve-vram 6` 把 usable 砍到 9,855 MB、
物理峰值一个字节没变，见 §7.10）。720P 243 帧这档真正吃紧的是**全片注意力的激活**，不在权重账上。
**首步的 s/it 已经含初始化时间**，所以拿它跟基线比就是最省事的判据，`bat\bench\probe_limit.py`
已按「首步 s/it > 基线 × 3」实现。

#### 显存随帧数缓慢下滑，不是常数

早先"像素翻倍只多 0.78 GB、工作集几乎恒定"的观察只覆盖到 124 帧。拉到 413 帧后：

| 864×480 | 124 帧 | 294 帧 | 345 帧 | 413 帧 |
|---|---|---|---|---|
| min free | 12.73 | 10.25 | 9.81 | 8.84 |

帧数涨 3.3 倍，min free 掉 3.9 GB。**结论是缓慢下滑，不是恒定** —— 所以长档必须逐档实测，
不能从 124 帧的数据外推。

**345 帧这张档两次结果不一致**：本轮（长提示词、int8 TE、每档前 `/free`）362.4 s 跑完、min free 9.81 GB，
是稳的；用户手动测试（int8 与原版各自跑）在 345 帧爆显存。差异还没定位到单一变量，所以
**保守按 328 帧（13.67 s）当安全上限，345 标成不可用**。"爆"的判据见下一节，别只看显存余量。

#### token 账：上限约 39k（2026-11-18 更正公式）

`length / 4` 那版把帧数当连续量算，**公式是错的**。latent 时间轴是按 `17n+5` 抽的，
单窗只有 `((L − 5) // 17) × 5 + 2` 帧（L ≤ 5 时 2 帧）：

```
latent_t = 2 if L <= 5 else ((L - 5) // 17) * 5 + 2
tokens   = latent_t × (W / 32) × (H / 32)
```

864×480 = 27×15 = **405 token/帧**，1280×736 = 40×23 = **920/帧**，1344×768 = 42×24 = **1,008/帧**。
双向验证过：124 帧 864×480 → 37×405 = 14,985；362 帧 1344×768 → 107×1,008 = 107,856（与日志吻合）。

| 档位 | 公式旧值 | 实值 | 实测 |
|---|---|---|---|
| 864×480 × 124 | 12,555 | **14,985** | 稳 |
| 864×480 × 294 | 29,768 | **35,235** | 稳 |
| 864×480 × 328 | 33,210 | **39,285** | 建议上限（未测） |
| 864×480 × 345 | 34,931 | **41,310** | 边界，按不可用 |
| 864×480 × 413 | 41,816 | **49,410** | 爆 |
| 1280×736 × 124 | 27,900 | **34,040** | 稳（表中旧记作 720P） |
| 1280×736 × 243 | 54,675 | **66,240** | 爆 |

> `1280×720` 的 `H/32` 是 22.5，不在 32 网格上；实跑 latent 取到 23（=736），上表按 920/帧算。

**安全线约 39k token**（328 帧 = 39,285），345 帧（41,310）在边界上。
旧公式给的「33k」与旧环境那张「约 33.5k 天花板」是同一个低估 —— 两处都乘约 1.19 就得到这张表，
所以两边的结论其实一直是一致的，只是绝对数偏低。

**开窗口时按单窗算，不按总帧数**：1344×768 × 107 帧 = 32×1,008 = 32,256 token/窗，
4 窗的 362 帧（107/22）因此能稳 —— 这才是窗口机制真正的原理，不是"总帧数变少了"。

按 39k 反推（**未实测**）：

| 分辨率 | 单段稳 | 建议上限 |
|---|---|---|
| 864×480 | 328 帧 / 13.67 s | **328 / 13.67 s** |
| 1280×736 | 124 帧 / 5.17 s | 141 帧 / 5.88 s（38,640，未测；旧表给的 158 帧是 42,300，超线） |
| 1344×768 | 124 帧 / 5.17 s | 124 / 5.17 s（实测；更长只能靠窗口，§7.9） |

- 帧数被 `17n+5` 卡成网格：5.17 / 6.58 / 8.00 / 9.42 / 10.83 / 12.25 / 13.67 / 15.08 / 16.50 / 17.21 s，**没有 11.5 s 这种东西**。
- 想拍长镜头：**两条路** —— 开上下文窗口（§7.9，1344×768 可到 15.08 s），或用 `--max-duration` 首帧续接（新 int8 套默认 5 s 一段）。
- **别去试跨线的档**：480p 413 帧跑满 1000 s 未完成，长时间的分页搬运实测把显卡驱动顶崩过一次。

**采样结束后 DiT 为什么"自己"消失**：不是谁主动卸载。`--cache-none` 用 `NullCache` 不存节点输出，
采样节点跑完 `complete_node_execution()`（`comfy_execution/graph.py:368-373`）pop 掉
`execution_cache` 里唯一强引用 → ModelPatcher 引用计数归零 →
`weakref.finalize(real_model, cleanup_models)`（`model_management.py:825-826`）摘掉 LoadedModel →
`reset_cast_buffers()` 末尾 `soft_empty_cache()`（`:1491`）把 8.9 GB 还给驱动。
**因此卸载类节点/钩子在这里收益恒为 0**（反证：只去掉 `--cache-none`，钩子立刻打印
`freed 8937 MB`，但那一刻模型本来就在显存里，等于没省）。

---

### 7.9 上下文窗口：单段 15.08 s（2026-11-17 实测，接在 §7.8 之后）

§7.8 的 39k token 天花板是**单窗**结论。接入 `MiniMaxH3ContextWindows` 后，采样被切成若干
重叠窗口，激活峰值按「窗口」计，长度不再受单窗 token 限制，改受 **窗口数 × 单窗显存** 约束。

节点只有 5 个输入，**没有「窗口数」这个参数**，窗口数由 ComfyUI 按帧数自己算：

| 参数 | 默认 | 本机用值 | 说明 |
|---|---|---|---|
| `context_length` | 124 | 107 | 单窗帧数，必须 17n+5 |
| `context_overlap` | 39 | 22 | 相邻窗口共享帧数，必须 17n+5 且 ≤ length−5 |
| `fuse_method` | `pyramid` | 不动 | 静态融合默认档，其余三档无对比数据 |
| `freenoise` | `true` | 不动 | 各窗口复用窗口 1 的噪声；动作重复时才考虑关 |
| `split_conds_to_windows` | `false` | 不动 | 多段顺序剧情才开 |

窗口数（`comfy/context_windows.py:888` `create_windows_static_standard`）：

```
窗口数 = 1 + ceil((总帧数 − context_length) / (context_length − context_overlap))
```

#### 实测（6 步，2130 字符长提示词）

| 分辨率 | 帧数 | 秒 | ctx / ov | 窗口 | 耗时 | 每窗每步 | 结论 |
|---|---|---|---|---|---|---|---|
| 1344×768 | 243 | 10.13 | 124 / 39 | 3 | 875 s | 48.6 s/it | 稳 |
| 1344×768 | 362 | 15.08 | 107 / 39 | 5 | 1,216 s | 40.5 s/it | 未爆，贴线（约 +11% 压力开销） |
| **1344×768** | **362** | **15.08** | **107 / 22** | **4** | **874 s** | **36.4 s/it** | **稳，推荐档** |
| 1280×736 | 362 | 15.08 | 107 / 39 | 5 | 1,066 s | 35.6 s/it | 同样 5 窗却舒适 |

`107 = 17×6+5`，是 362 帧下能保住 4 窗口的最小窗口长度：要 4 窗口就得
`(362 − ctx)/3 ≤ ctx − ov`，缩到 90 会变成 5 窗口、反而更慢。

#### 差 9% 像素就跨过临界线

最后两行是同一个 5×107 窗口排布，只有分辨率不同：`1344×768` 每窗 40.5 s/it（贴线），
`1280×736` 每窗 35.6 s/it（舒适，比 1344×768 的 4 窗还便宜）。

像素只差 9%（1,032,192 vs 942,080），却把 5 窗从压力区拉回舒适区 —— **24 GB 的临界就是这么窄**，
也再次印证「越线不是慢一点，而是换一档」。按像素比 0.913 外推预测 1,049 s，实测 1,066 s，偏差 1.7%，
分辨率→耗时的缩放关系可以直接用来估算。

#### 推论：`1280×736` 上 430 帧 ≈ 同样耗时，出 17.92 s（**未实测**）

窗口成本只由**窗长 × 窗数**决定，与总帧数无关。所以同一组 5×107 窗口可以装更长的片子：

| 配置 | 窗口 | 预计 | 片长 |
|---|---|---|---|
| 362 帧 / 107 / 39（上表实测） | 5 | 1,066 s | 15.08 s |
| **430 帧 / 107 / 22** | **5** | **≈1,066 s** | **17.92 s** |

这是 24 GB 上唯一摸到 18 秒的路子。代价是**超出训练范围 362 帧**，画面可能发散且不报错，
只能实测；VAE 解码也会随帧数多约 5 秒（未计入）。

> 别用 `1280×736 × 362 / 107 / 22`（4 窗 ≈ 853 s）去省那 20 秒 —— 分辨率低 9%，
> 不如直接用 `1344×768 × 362 / 107 / 22` 的 874 s。

#### 别把 §7.8 的 `1280×720` 和这里的 `1344×768` 混起来

§7.8 表里的「720P」是字面 `1280×720`（早期实测、**不开窗口**）：124 帧 252–260 s 稳、243 帧跨线爆。
本节是 `1344×768`（H3 原生画布、工作流默认值、**开窗口**）与 `1280×736`（今天试的低一档）：
243 帧 875 s 稳、362 帧 874–1,216 s。

所以「分辨率更大、帧数反而更多」不是数据矛盾，差异来自**开关窗口**：
`1280×720 × 243` 当年爆在全片注意力的激活上，`1344×768 × 243` 现在被 3 个窗口压住了。

`context_length` / `context_overlap` 都按**帧**切，与分辨率无关 —— 分辨率只影响单窗显存（token 数），
不影响窗口数。这两件事分开看就不会混。

#### 单位成本回到 5 秒时代

| 档位 | 耗时 | 成片 | 每成片秒 |
|---|---|---|---|
| 1344×768 × 124（不开窗口） | 280 s | 5.17 s | 54 s |
| 1344×768 × 362，107 / 22 | 874 s | 15.08 s | **58 s** |

3 倍片长、3.1 倍时间 —— 窗口机制把长度做成了近似线性。

#### `context_overlap` 的开销在两处，不只是窗口数

5 窗 → 4 窗只降 20% 窗口数，实测耗时却降 28%（1,216 → 874 s）。差额来自融合区：
融合成本按「窗口数 × 重叠 latent」计，`39 → 22` 把重叠 latent 从 17 降到 7，两部分同时降。
**所以在 24 GB 上 `overlap` 是唯一线性的省显存旋钮，而且比窗口数比例更有效。**

#### 显存账本

| 分辨率 | 单窗（124 帧） | 依据 |
|---|---|---|
| 864×480 | ≈ 0.85 GB | 实测 1 / 4 / 8 窗 = 11.33 / 14.48 / 17.15 GB |
| 1344×768 | ≈ 3.5–4 GB | 3 窗稳、5 窗贴线、4 窗舒服 |

底（权重 + 采样固定部分）约 10.1 GB。**24 GB 上 1344×768 的预算是 4 个 107 帧窗口**，
第 5 个开始贴线，第 6 个必爆。

> **2026-11-18 补记**：上面这两个数都是 **torch 口径**。同参数实测（864×480×124）整卡真实占用
> **21.43 GB**、本进程 19.35 GB，比 torch 报的 13.54 GB 多 5.8 GB。「底 10.1 GB」同理偏低，
> 拿它做 24 GB 的加减法会高估余量。口径问题见 **§7.10**。
> 窗口预算本身是实测出来的，结论不受影响；但**别用账面数字推算新档位**，一律实测。

#### 判爆仍是 §7.8 那两件事，基准换成分辨率

- `Model Initializing`：正常 10–60 s，漂到 150 s 以上即爆
- 每窗每步 s/it 与**同分辨率**基线比，**×3 以上即爆**
- 爆了是二元悬崖：越线后要么每步重搬 8.4 GB 权重、要么激活溢出进共享显存，超 100 MB 与超 3 GB 等效
  （两种机制都没单独验证，但**判据一样：×3 以上**）

反过来，「耗时落在线性区间」就是没爆的证明：1,216 s / 5 窗 / 6 步 = 40.5 s/it/窗，
若真爆，反推不爆时应为 10–13 s/it/窗 —— 1344×768 是 480P 的 2.5 倍像素，不可能那么快。

#### 两个硬约束

1. **训练范围 124–362 帧（5–15 s）**。上游节点说明：*trained range is ~124-362, longer is untested*。
   超过不是显存问题，是模型没见过，先表现为画面发散且不报错。**15.08 s 就是天花板。**
2. **多窗口有已知未修缺陷**：ComfyUI #15982（2026-08-30 开，至今 open 零回复）——
   `IndexListContextHandler` 不告诉模型「窗口在时间轴上的位置」，每个窗口都从 0 秒开始，
   第二窗起可能周期性闪烁 / 动作重演。本机 3 窗与 4 窗成片暂未观察到明显差异，
   `ov` 39→22 的接缝肉眼也看不出来。

#### 工作流与工具

- 带窗口节点的 UI 工作流：`molbal_workflows_int8_cw/`（`tools\make_cw_workflows.py` 从 `molbal_workflows_int8/` 生成，改参数后重跑该脚本，别手改 JSON）
- 命令行直接出片：`bat\cw_8b_heretic_int8\gen_h3_cw-8b-heretic-int8.bat` —— 单段长片，交互式问 `context_length` / `context_overlap`（默认 107 / 22），也给 `--ctx` / `--ov`；`--dry-run` 不提交，只打印窗口数与耗时区间
- 逐档判爆探针：`bat\bench\probe_cw.py`（`est_windows()` 复算窗口数；预爆线 22.0 GB、共享显存 >0.35 GB 提前中断；`--early-stop N` / `--keep-going`）

---

### 7.10 显存口径：任务管理器是对的，torch 少报 5.8 GB（2026-11-18 实测）

同一个任务（864×480 × 124 帧 / 6 步 / `bat\multisegment_8b_heretic\prompt.txt`，2,134 字符）
在 DiT 稳态同时读这几个口径：

| 口径 | 读数 | 取法 |
|---|---|---|
| torch 峰值（日志里的 `peak_used`） | 13.54 GB | `torch.cuda.max_memory_allocated` |
| HIP 视角本进程已用（23.98 − free） | 13.54 GB | `torch.cuda.mem_get_info()` |
| **任务管理器：本进程专用** | **19.35 GB** | `\GPU Process Memory(*)\Dedicated Usage` |
| **任务管理器：整卡专用** | **21.43 GB** | `\GPU Adapter Memory(*)\Dedicated Usage` |
| 整卡共享 | 0.53 GB | `\GPU Adapter Memory(*)\Shared Usage` |

三种条件（无窗口 headless / 窗口 107+22 / 全新启动）跑出来**完全一样：19.35 / 21.43**，
所以不是缓存、也不是某次启动的偏差。一次运行的时间线（前数=本进程专用，括号=torch）：

| 阶段 | 本进程专用 | torch |
|---|---|---|
| 服务起好、未提交 | 0.25 | — |
| 提交后 t=0（TE 装载中） | 5.46 | 0.46 |
| TE 装完 | 11.8 | 8.53 |
| **TE 卸载瞬间** | **5.23** | — |
| DiT 装完、进采样 | **19.35** | 10.95 |
| `POST /free` 之后 | 3.61（整卡 5.63） | — |

三条结论：

1. **TE 的 6.5 GB 确实释放了**（11.8 → 5.23），所以「编码器常驻抢显存」这条老解释在采样阶段不成立。
2. `/free` 之后仍留 3.61 GB，但第二轮峰值不再叠加 —— 可回收，不是泄漏。
3. DiT 阶段 torch 报 10.95（DiT 8.94 + 激活 ~2），物理 19.35，**差 8.4 GB**。

#### 根因：ROCm 在 Windows 上报的可用显存偏大

`ROCm/rocm-systems#16035`（2026-11-17 开）：PAL 后端（Windows 默认）的
`pal::Device::globalFreeMemory` 只减**本进程**的分配和预算，不减别的进程；
Linux 的 KFD、Windows 上非默认的 ROCr 后端、CUDA 在 WDDM 上都报整卡可用。
原文的后果说得很直接：按 `hipMemGetInfo` 定分配大小的程序会**过度承诺**，
WDDM 随后把一部分挪进共享内存、**慢好几倍**；例子就是 24 GB 的 RX 7900 XTX
（llama.cpp 溢 5.5 GiB 进共享内存，prompt 处理 4118 → 444 tok/s）。
旁证：`ggml-org/llama.cpp#30250`（同卡，报 24,410 MiB 可用而任务管理器已用 2 GB）、
`ROCm/TheRock#9192`（Windows + ComfyUI，KSampler 1 s → 25 s，专用 31.4/32 GB）。
修复 PR 是 `ROCm/rocm-systems#16013`（2026-11-18 开，**还没进任何发行版**）。

所以「16 GB 的 5080 反而稳、24 GB 的 7900 XTX 会顶爆」不是玄学：CUDA 在 WDDM 上报整卡可用，
ComfyUI 不会超装；HIP 报的数偏乐观，ComfyUI 照它规划就顶到 23.9，剩下交给 WDDM 分页。

#### 二十秒自查（不加载模型，不占显存）

```powershell
& "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" `
  "D:\localAI\ComfyUI-last\plan3\bat\bench\check_vram_report.py"
# HIP 报      : total 23.98  可用 23.84  已用 0.15 GB
# 任务管理器  : 专用 2.26  共享 0.24 GB（专用就是整卡已用）
# 差值        : 2.12 GB
# → #16035 仍在：HIP 没扣掉别的进程占的显存
```

**差值 <1 GB 就是修复已进 runtime 的信号**，届时用 `probe_vram.py` 复测峰值确认。

#### 三个想当然的杠杆，实测全部无效

| 试法 | 结果 |
|---|---|
| `--reserve-vram 6` | `usable` 15,299 → 9,855 MB，DiT 仍 `full load: True`，物理峰值 **19.35 / 21.43 一个字节没变** |
| `GPU_ENABLE_PAL=0`（切 ROCr 后端） | 无效：0/1 各跑一次空白探针，两次日志都是 `paldevice.cpp:1106`、`rocr` 命中 0 次 —— ROCm 7 的 Windows 只有 PAL 后端 |
| `--disable-dynamic-vram` | **直接顶爆，把机器逼到快死机**：动态 VRAM 是省显存的那一层，绝不能关 |

`usable` 只是 `model_management.py:1025` 那串 `max/min` 从 `get_free_memory()` 现算的**装载预算**，
它决定「装多少」，装进去之后物理占用不受它约束 —— 这就是 `--reserve-vram` 失效的原因。
同理，任何「改规划参数省显存」的想法在这套组合上都是空的。

#### 还差 8.4 GB 没解释（未验证）

DiT 阶段物理 19.35、torch 10.95，差 8.4 GB ≈ GGUF 文件本身 8,634 MiB。
最可能是 GGUF 的映射页与反量化权重**双份常驻**，WDDM 把两份都算进专用显存，而 torch 只统计 tensor。
**这只是「数字对得上」级别的怀疑，没有实测**；验证方法是换非 GGUF 的 fp8 DiT 对比峰值。

#### 判爆口径不变

仍然按**任务管理器整卡专用 >23.9 GB 即爆、共享 >0.6 GB 继续观望**。
`probe_vram.py` 现在同时采 Windows 计数器（`peak_os_ded` / `peak_os_shared` / `peak_os_proc`），
日志里那行 `peak_used 13.54 GB` 只是 torch 口径，**别拿它当整卡占用**。

---

## 8. 踩坑

### 8.1 GGUF 里的 tensor 名**不带** `model.diffusion_model.` 前缀

`gguf_io.py` 里是 `state_dict[tensor.name.removeprefix(TENSOR_PREFIX)]`，
而实测 647 个 tensor **一个都不带**前缀（`removeprefix` 对不匹配的串原样返回，所以正常）。
别看到「前缀匹配 0/647」就以为文件坏了。

### 8.2 文件没有 `general.architecture`

这是 stable-diffusion.cpp 的布局。ComfyUI-GGUF 只接受它认识的 architecture，
所以 HyperFlow 自己读 tensor、只借 ComfyUI-GGUF 的**反量化算子**（`GGUFBackend.find()`）。
手工核对用 `tools\check_gguf.py`，期望输出含：

```
general.architecture: ABSENT (what HyperFlow expects)
tensors: 647
quant types: {'F32': 19, 'BF16': 296, 'Q6_K': 85, 'Q4_K': 247}
blocks: 47  dense-qkv: 30  low-rank: 18
  -> the loader should log 'HyperFlow: 18 factorized blocks'
```

### 8.3 「18 factorized blocks」是怎么数出来的

47 个 block 里，30 个用融合的 `attn.qkv_proj`，18 个用低秩拆分的 `xxx.down` / `xxx.up`（1 个块两者都有）。
`model_patch.py:27` 的 `PART` 正则要求一个模块同时有 `down.weight` 与 `up.weight` 两片叶子
才折叠成 `LowRankLinear`，所以数出来正好 18 —— 和日志逐字对上，可以用来验证文件没被换过。

### 8.4 `ComfyUI-GGUF-Loader`（分叉）会静默接管 `UnetLoaderGGUF`

见 §5.5。症状是 `GGUFBackend.find()` 抛 `KeyError`，报错信息里完全没有「装错节点」的暗示。

### 8.5 ClipProj 单卡别用 `ClipProjLoader`

all-in-one 版本把编码器钉在卡上，在 24 GB 的单卡上白占 4–9 GB。用 `Load CLIP` + `ClipProj Apply`
两段式，编码器用完即放。

### 8.6 heretic（abliterated）编码器反而更差

ClipProj 作者的实测：`-0.026` / `-0.034` cosine。别被「无审查版」吸引。

### 8.7 清华 pypi 镜像对 `gguf` 返回 403

换 `mirrors.aliyun.com/pypi/simple`（已在 `plan2` 验证过同样现象）。

### 8.8 `curl.exe` 必须加 `--ssl-no-revoke`

系统代理 `127.0.0.1:26561` 的 MITM 证书做不了吊销检查，不加会直接失败。
另外 `raw.staticdn.net` 的 DNS 解析不出来，`raw.githubusercontent.com` 直连可用（带上面那个开关）。

### 8.9 32B GGUF 会被「静默」认成 Mistral 3 24B

见 §4.2。`detect_te_model` 不认识的权重不会报错，只会掉到宽度匹配的通用分支。

### 8.10 别用图内节点代替 `/free`

「跑完就卸」在图上做不到彻底，而且**时机本身就错了**。

**`ComfyUI-UnloadModels` 已卸载**（2026-11-17）。它提供的 `UnloadCPUModels` / `UnloadAfterSampling`
实现并不差 —— `unload_nodes.py:82-83` 有 `gc.collect()` + `mm.soft_empty_cache()`，
不是早期那种漏了 `gc.collect()` 的半成品。删它的原因是我们这套参数下它无事可做：

- `--cache-none` 用 `NullCache`，采样节点结束时 `execution_cache` 里的强引用被 pop，
  ModelPatcher 引用归零 → `cleanup_models` 摘掉 LoadedModel → `reset_cast_buffers()` 末尾
  `soft_empty_cache()` 已经把 8.9 GB 还回去（机制见 §7.8 末）。图内已经没有可卸的东西。
- 更根本的是时机：需要卸的是**上一轮**的残留（DiT 8.9 + 视频 VAE 5.0 + 音频 VAE 0.6 ≈ 14.5 GB），
  而那必须发生在**下一次提交之前**。图内节点属于同一张图，改不了下一次提交时的初始状态。

所以正确入口是 `/free`，且要在**提交之前**调。历史证据保留：早期自写节点
`ClipProjFree(all models)`（**缺** `gc.collect()`）挂在图尾，实测第二次仍然爆（见 §7.5）。

节点清单只剩四个：`ComfyUI-ClipProj`、`ComfyUI-GGUF`、`ComfyUI-HyperFlow-Flash`、`ComfyUI-QWEN3_TTS`。

### 8.11 换机时先跑一次 `t2v\step0_free.py` 的冷启动基线

冷启动 `vram_free` 应该是 `total - 0.2 GB` 左右（本机 23.82 / 23.98）。
如果开机就只剩十几 GB，说明还有别的进程占着显存，先解决那个，再谈生成。

---

## 9. 提示词

这条是新环境最容易踩的坑，而且**看起来像模型问题，其实是提示词问题**
（用户已确认根因在提示词，不是模型也不是分辨率）。

**完整书写规则不在本章**，在本机资产
`bat\提示词模板\MiniMax-H3-提示词书写规则.md`（19 KB，依据官方两份写作指南 + ComfyUI 官方提示词页 +
本机 `minimax_h3_prompt.py` 源码写成）。**写提示词前先看那份**，本章只讲三件新环境特有的事：
CFG 1 没有负向分支、三种信封结构怎么选、以及本机尺寸/帧数的硬约束。

`bat\提示词模板\` 里还有三个 `.txt` 示例模板（视频 / 静帧 / 照片）。它们和规则 md 有一处冲突：
`提示词模板-视频.txt` 的「画质锁定」模块建议写 `Shot on ARRI Alexa 65, 35mm lens`，
而规则 md §4 明确把摄影器材参数列为**要删的元信息**。以规则 md 为准。

### 9.1 机制：CFG 1 没有负向分支

`BasicGuider` 的 CFG 锁死为 1（§4.4，不可改），所以图里根本不存在负向条件。后果是：

| 你以为 | 实际 |
|---|---|
| `no anime, avoid cartoon style` 会**压制**动漫 | 这些词照样被编码进条件向量，只是变成了「有动漫/CG 味」的强信号 |
| 换个"无审查"编码器能修 | 不能。问题在条件向量里有那个词，不在编码器 |
| 调高 CFG 让负向生效 | CFG 一动模型就崩（蒸馏模型只训过 1） |

社区口径一致：guidance-distilled 模型上负向提示「不是效果弱，是**完全没有**作用」，
剩下的是词本身的正向语义。所以**别写禁令，只写你要的东西**。

### 9.2 三种信封结构，别混用

| 场景 | 用哪种 | 形状 |
|---|---|---|
| t2v（无参考） | 三字段 | `integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music` |
| i2v / flf2v（首末帧） | 指令行 + 三字段 | 先一段「`<Picture 1>` 对齐 0.00 秒」的指令行，空一行再写三字段（规则 md §1.1） |
| ref2v（参考图/多素材改写） | 六段 或 三字段 | 六段见规则 md §6；官方 example 与 `bat\ref2va_8b_heretic\prompt.txt` 是两种现成写法 |

三条硬格式，漏了会明显掉质量：

- **三个字段一个都不能删**。没内容写 `N/A`，不要整段去掉（规则 md §4）。
- 字段标签逐字照抄，顺序固定，不能调换。
- 风格句放在 `[Shot 1]` **之后的第一句**，且是正面陈述：
  `Photoreal 35mm film, natural skin texture, shallow depth of field.`
  官方示例也是这么写的：`Photoreal 35mm action film, one continuous 10-second shot.`
- 写实类提示词里不要出现 `anime`、`cartoon`、`CG`、`render`、`illustration` 任何一个词，
  哪怕前面加了 `no` / `avoid` / `not`。
- 提示词要**长**：本机三次实测用的是官方 282 字符长提示词（§7.4）；短关键词更容易丢细节。

### 9.3 本机的尺寸与帧数（会静默取整）

| 项 | 值 | 后果 |
|---|---|---|
| `length` | **124–481 帧**，向上吸附到 `17k+5` | 传 110/120 都变 124，传 200 变 209，**不报错不告警**（规则 md §4.1）。写分镜时间点前先确认实际帧数 |
| 原生画布 | 短边 **768**（16:9 → 1344×768） | 这是原生尺寸；`bat\` 默认 `864×480` 是降档，能跑但画质掉 |
| 本机上限 | 分辨率不再设限（720p 与 1344×768 采样余量几乎相同）；**帧数**见 §7.8 推演 | 超过推演值不会 OOM，先表现为画面发散 |

### 9.4 分辨率不是风格问题的原因

曾怀疑 1344×768 触发「风格漂移」，已排除：旧环境同分辨率、同一模型出片正常。
作为参考，社区反馈 H3 在 **768p 档依从性明显变差、352/416p 正常**（`MiniMaxAI/MiniMax-H3`
discussion #65）。但这属于「提示词跟随度」，不是「画风被改写」，两者别混。

本机换 int8 编码器后分辨率不再是瓶颈（1280×720 与 1344×768 的采样余量只差 0.05 GB，§7.8），所以这条只能记着，不能靠降分辨率解决。

### 9.5 heretic 编码器不是风格开关

ClipProj 作者实测 heretic / abliterated 编码器的语义分数**更差**（−0.026 / −0.034，§8.6）。
本环境用 heretic 是用户选择，**不要指望它改变画风** —— 画风全在提示词里。

---

## 10. 复现步骤

```powershell
$py   = "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
$cn   = "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes"
$wf   = "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows"
$here = "D:\localAI\ComfyUI-last\plan3\tools"

# 1. 节点
git clone --depth 1 https://v4.gh-proxy.org/https://github.com/city96/ComfyUI-GGUF "$cn\ComfyUI-GGUF"
git clone --depth 1 https://v4.gh-proxy.org/https://github.com/Video-Rebirth/ComfyUI-HyperFlow-Flash "$cn\ComfyUI-HyperFlow-Flash"
#    ClipProj 从旧环境整目录复制（或自行 git clone）

# 2. 依赖
& $py -m pip install gguf -i https://mirrors.aliyun.com/pypi/simple/

# 3. 模型（见 §5.3 的落点表）

# 4. 生成 4 个 UI 工作流 + 四项自检（API payload 由界面图离线转换，见 plan3\README.md §8）
& $py "$here\make_workflow.py"
Get-ChildItem "$wf\hyperflow_*_clipproj_8b.json" | ForEach-Object { & $py "$here\check_workflow.py" $_.FullName }
& $py "$here\check_workflow.py" "D:\localAI\ComfyUI-last\plan3\API_workflows\*.json"   # 11 条 payload（§6.2）
& $py "$here\check_gguf.py"
& $py "D:\localAI\ComfyUI-last\plan3\bat\check_graphs.py"   # bat 脚本的 8 种 API 图

# 5. Desktop 里填启动参数（6 条，见 §3）：--enable-manager --use-ck-attention --preview-method auto
#    --disable-smart-memory --cache-none --fp16-intermediates
# 6. 关掉所有占显存的程序
# 7. 每次点 Queue 之前先卸一次（连续生成必须做，见 §7.5）
& $py "D:\localAI\ComfyUI-last\plan3\t2v\step0_free.py"
# 8. 跑工作流（提示词怎么写见 §9）
```

---

## 11. 未验证 / 后续

| 项 | 状态 |
|---|---|
| `hyperflow_i2v` 续段工作流 | 图**已生成**（`hyperflow_i2v_clipproj_8b.json`），`bat\multisegment` / `scenes` 的末帧续接**已实跑通过**（2026-11-12）；段间拼接处的音轨连续性未逐项评估 |
| `ref2va`（参考图锁角色） | 权重已下载（`minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf`，9,220,352,512 字节 = 远端 `totalLength`），工作流已生成，**已实跑通过**（2026-11-12） |
| `bat\` 四个生成脚本 | **已实跑通过**（2026-11-12）；静态校验 `check_graphs.py` 与 `--help` 也正常 |
| `API_workflows\` 11 条 payload（§6.2） | **全部已实测通过**：H3 四条 + qwen-image 六条 + TTS 一条都提交过 `/prompt` 并出片/出音频；**已完成 [infinite-creation](https://github.com/SwotAtmk/infinite-creation) 适配**（`plan3\README.md` §8.5） |
| 8B + ClipProj 的语义保真度 | **未逐项评估**。这条组合在两个环境都没有先例（旧环境是 4B 投影喂原版 H3）。若出现「画面跟得上提示词但语义散」或「语音糊」，第一个怀疑对象是投影矩阵 |
| 语音质量 | ClipProj README 提示：cosine 0.90 够视觉语义但**不够音素**，非英语更差；v3.1 就是为此改的，但中文对白仍建议实测 |
| 32B 的可能性 | 只有 `fp8` safetensors（约 32 GB）一条路，需内存加到 64 GB。改 `comfy/sd.py` 加 GGUF 分支是下策（升级即丢） |
| `--use-ck-attention` 的加速幅度 | 未做 A/B。旧环境结论是生视频几乎无质量差别、快一个数量级，本次未复测 |
| `preview_watch` 内核补丁（预览 + step0 卸载 DiT） | **未移植**。旧环境 `plan\bat\preview_watch\frame_preview_kernel.patch`（3 文件：`latent_preview.py` / `execution.py` / `comfy_extras/nodes_minimax_h3.py`）的三个锚点在 0.44.2 上**逐项吻合**，理论上可手工移植；没做的原因是它的「step0 卸载 DiT」是预览解码的副作用，命中条件是**动态 DiT**，而本机 DiT 是 `disable_dynamic=True` 的 GGUF（见 §7.5），换一条分支；且中途 `vae.decode()` 要在满显存上临时摊 5 GB。需要实时预览时再单独评估 |
