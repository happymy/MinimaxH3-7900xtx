# plan3 — HyperFlow H3 Flash（Comfy Desktop）工作区

> **本目录是仓库唯一现行线**（2026-11-12 起）。根 `README.md` 是索引；
> `plan\` 与 `plan2\` 属旧 portable 环境，**已废弃**，只留作历史对照。
>
> ### ✅ 强烈建议：就按本目录这套部署
>
> Comfy Desktop + HyperFlow H3 Flash GGUF + Qwen3-VL-8B heretic + `mmh3-8b-ClipProj-v3.1-mlp`。
> UI 工作流与 API 工作流**都已实测跑通**（API 四条于 2026-11-12 手动提交 `/prompt` 验证）。
> 旧 portable（`plan\`）那套原生 H3 20 步方案：同 5 s 片 480P ≈ 570 s，本方案 720P ≈ 280 s，
> 不要再混搭旧参数、旧模型清单或旧工作流。
>
> `plan\` 是旧 portable 环境的 MiniMax H3 资产，`plan2\` 是 Qwen-Image 2.1，
> **`plan3\` 只放新装的 Comfy Desktop 环境**（ComfyUI 0.45.2 / ROCm 7.14）这一条线。
> 三个目录平级，互不覆盖。仓库侧是 `D:\localAI\ComfyUI-last\plan3\` 的副本；
> **参考图 / 测试素材那 6 个 PNG 不入库**（`bat\测试素材\`、`bat\ref2va_8b_heretic\img\`、
> `bat\scenes_ref_8b_heretic\img\`，各 2 张、内容相同），实机路径见 §4。

---

## 1. 顶层构成

| 文件 / 目录 | 内容 |
|---|---|
| `HyperFlow-H3-Flash-GGUF-部署总结.md` | **主文档**。目标 / 结论 / 环境 / 选型取舍 / 安装清单 / 工作流改动 / 实测与显存预算（含 §7.5 连续生成、§7.6 图缓存）/ 踩坑 / 提示词 / 复现 / 未验证 |
| `tools\` | 工作流生成与自检（9 个文件：4 份 UI 快照 + 4 份 API 快照 + 3 个脚本） |
| `API_workflows\` | **API 格式工作流**（`/prompt` 直连的 payload），由 `tools\make_workflow.py` 生成，4 个 family |
| `bat\` | API 直连的分段生成脚本（7 个脚本目录，从 `plan\bat` 移植/原样复制）+ `check_graphs.py` 静态自检 + `提示词模板\`（写提示词前先看）+ `测试素材\` |
| `t2v\` | 运行时工具。`step0_free.py`，**每次点 Queue 之前跑一次** |

---

## 1.2 同环境里的非 H3 资产（qwen-image 2.1 / Qwen3-TTS）

同一个 Comfy Desktop 实例里还装了这两条线，与 H3 互不影响（模型、工作流都分开）。
文件来源：旧环境 `D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\`，**全部是复制，没有链接**。

**模型**（`C:\Comfy-Desktop\ComfyUI-Shared\models\`）

| 目录 | 文件 | 字节 |
|---|---|---|
| `diffusion_models` | `qwen-image-2.1-UC-Q4_K_M.gguf` / `qwen-image-2.1-UC-Q8_0.gguf` | 4,604,558,112 / 7,591,557,920 |
| `text_encoders` | `qwen3vl_8b_int8_convrot.safetensors` | 9,350,798,360 |
| `text_encoders` | `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` / `…pe_i2i…` | 各 9,471,072,252 |
| `vae` | `qwen_image_2.1_vae_bf16.safetensors` | 675,509,688 |
| `TTS\Qwen3-TTS-12Hz-1.7B-VoiceDesign\` | `model.safetensors` + `speech_tokenizer\model.safetensors` | 3,833,402,552 + 682,293,092 |

**TTS 模型有两份**：插件里路径写死 `folder_paths.models_dir + "\TTS"`，
Desktop 的 `models_dir` 是 `…\ComfyUI\ComfyUI\models`（Shared 只是 extra search path），
所以除了 Shared 那份，`C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\TTS\` 下也必须有一份，否则节点报找不到模型。

**工作流**（`…\ComfyUI\ComfyUI\user\default\workflows\`）

- `qwen_image_2_1_{t2i,image_edit,background_removal}{,_-Q8_0}_gguf.json` —— 6 个，UI 格式，节点定义内嵌在 `definitions.subgraphs`
- `qwen3_tts_voice_design_ui.json` —— **UI 格式**，4 节点：`Qwen3TTSModelLoader` → `Qwen3TTSVoiceDesign` →（`SaveAudio` + `PreviewAudio`）。
  由 `DarioFT/ComfyUI-Qwen3-TTS` 的 `example_workflows/voice_design.json` 改编：保留 loader / voice design / 预览三条，
  裁掉它自带的 voice clone + prompt 存取节点（本机插件没有），节点名与 widget 顺序换成本机 `PGCRT/ComfyUI-QWEN3_TTS` 的定义，
  文案与音色描述沿用原来那份 API 工作流。
- `user\default\api_payloads\qwen3_tts_voice_design{,_GGUF}.json` —— **API 格式**（`/prompt` payload），
  **不在 workflows 目录**，所以不会出现在工作流列表里。原因：API 格式顶层就是节点表、没有 `nodes`/`links`，
  拖进界面必报 `TypeError: e is not iterable`。`_GGUF` 那份用的 `QwenTTSModelsLoader` / `QwenTTSVoiceDesignGenerate`
  本机（和旧环境）都没有，属于未落地的设想稿，未适配。

**依赖**

- qwen-image 全部用 ComfyUI 0.44.2 内置节点（`TextEncodeQwenImage21` / `QwenImage21Cache` /
  `ComfySwitchNode` / `BatchImagesNode` / `TextGenerate` / `ImageCompare` / `SaveImageAdvanced` /
  `ResolutionSelector` / `PreviewAny` / `PrimitiveStringMultiline`）+ 已装的 `ComfyUI-GGUF`，**没装额外自定义节点**
- TTS 需要 `custom_nodes\ComfyUI-QWEN3_TTS` + `qwen-tts 0.1.1`（连同 soundfile / accelerate /
  librosa / numba / llvmlite / sox / onnxruntime / scikit-learn / cloudpickle / narwhals / platformdirs）

**TTS 与 transformers 5.x：改用官方 PR，不再在节点里打补丁**。`qwen-tts 0.1.1` 是写给
`transformers 4.57.3` 的，本机是 `5.20.2`。第一版在 `qwen3_tts_nodes.py` 里叠了 4 个
API 兼容补丁，报错消失了但**生成的音频不对**。查下来官方仓库有对应 PR：

- `QwenLM/Qwen3-TTS` PR **#360「Support Transformers 5」**（作者 andimarafioti，open，
  close #237）。它除了修 API，还点出两个**静默行为退化**：
  1. 5.x 的 `ROPE_INIT_FUNCTIONS` 没有 `default`，且低内存加载可能让非持久化
     `inv_freq` buffer 变成全零 → 「第 0 个位置一致，后面越跑越偏，可能永不 EOS」；
  2. 5.x 的 Mimi 用滑窗因果注意力，4.57.3 下是 full causal → 参考 codec token 变了，
     ICL（音色克隆）对齐被破坏。
  所以这不是「补 API 就能好」的问题，**必须按 PR 改源码**。

落地方式：**逐字节复制 PR 分支的 6 个文件**到 `site-packages\qwen_tts`（不是手写），
原文件备份在 `%TEMP%\opencode\qwen_tts_0.1.1_orig`：

```
qwen_tts\__init__.py
qwen_tts\_transformers_compat.py                       （新增）
qwen_tts\core\models\configuration_qwen3_tts.py
qwen_tts\core\models\modeling_qwen3_tts.py
qwen_tts\core\tokenizer_12hz\modeling_qwen3_tts_tokenizer_v2.py
qwen_tts\inference\qwen3_tts_tokenizer.py
```

已核对：这些文件与安装的 0.1.1 **只差 PR 本身的改动**，没有夹带 main 上的其它变化。
`pyproject.toml` 的版本 pin 没有覆盖（不影响运行）。

**本地只偏离 PR 两处，都有实测理由**：

1. `patch_transformers_rope_registry()`：PR 是把 `default` 塞进**全局**
   `ROPE_INIT_FUNCTIONS`；本机 5.20.2 的 `modeling_utils._init_weights` 会构造
   `{..."default": module.compute_default_rope_parameters, **ROPE_INIT_FUNCTIONS}`，
   全局 key 会盖掉模块自己的方法 → 加载 qwen 的 codec 时直接
   `AttributeError: 'MimiConfig' object has no attribute 'rope_theta'`。改为**只把
   打过补丁的表绑到 qwen_tts 各模块的引用上**，transformers 自己的模型不受影响。
   （因此 PR 自带的 `test_default_rope_initializer_is_registered` 那条断言在本机不成立。）
2. `patch_transformers_rope_registry()` 的调用点移到 `__init__.py` 的子模块 import
   **之后**——上面的扫描要能找到已经加载的 qwen_tts 模块。

`custom_nodes\ComfyUI-QWEN3_TTS\qwen3_tts_nodes.py` 已**恢复成上游原样**（4 个 shim 全删）。

验证（CPU / bf16，走节点同款 `device_map='cpu' + dtype='bfloat16'` 路径，不占显卡）：

- `qwen_tts` 模块内的 registry 有 `default`，transformers 全局表**没有**（不污染）
- talker 2 个 rope 模块、codec 1 个 rope 模块，`inv_freq` 全非零（关掉 `restore_rope_buffers`
  做对照也是非零，说明本机没踩到那个全零分支）
- codec 的 `sliding_window = 8000 = max_position_embeddings`（本来就不是滑窗）
- `generate_voice_design` 出 `24000 Hz / (17280,) float32`，peak 0.55 / rms 0.11

脚本：`%TEMP%\opencode\verify_pr360.py`、`verify_pr360_devicemap.py`、`verify_no_restore.py`；
PR 原始 patch 与 `tests/test_transformers_compat.py` 也留在 `%TEMP%\opencode\pr360_*`。

**代价**：不要为了让它「干净」而把 transformers 降到 4.57.3 —— 那会连带把
`huggingface_hub` 从 2.2.0 退回 0.36.2、`tokenizers` 从 0.23.3 退回 0.22.2，
H3 与 qwen-image 现在依赖的是 5.x。改过的 6 个文件在 `pip install -U qwen-tts`
或重装/升级 ComfyUI 环境后会被覆盖，届时按上面同一份 PR 重放即可。

**没纳入的**：`plan\API_workflows\…\image_qwen_image_edit_2511_i2i.json`（Qwen-Image-Edit-2511）。
它要 `qwen_image_edit_2511_fp8mixed.safetensors`、`Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`、
`qwen_2.5_vl_7b_fp8_scaled.safetensors` 三个模型，**旧环境也没有**，拷过去跑不起来。

### GGUF 节点认不出 `qwen_image21`（已修，改的是自定义节点）

新环境装的是 upstream `city96/ComfyUI-GGUF`，`loader.py` 的 `IMG_ARCH_LIST` 里只有
`qwen_image`（1.0/Edit 那代），没有 qwen-image 2.1 的 `qwen_image21`，于是
`UnetLoaderGGUF` 直接 `ValueError: Unexpected architecture type in GGUF file: 'qwen_image21'`。
旧环境能用是因为它装的是 `ComfyUI-GGUF-Loader`（CCTech fork），那份已经把这个 arch 加进去了。

修法只有一处（`custom_nodes\ComfyUI-GGUF\loader.py:12`，加一个字符串）：

```
IMG_ARCH_LIST = {..., "qwen_image", "qwen_image21"}
```

**不需要**再照抄 upstream issue #487 的 `input_act` 补丁。那条 issue 针对的是
0.39 时代的 `Linear.forward(input, input_act=…)` 签名；本机 0.44.2 已经把融合激活改成
模块级 `comfy.ops.linear_input_act(linear, x, "swiglu")`（`comfy/ops.py:1082`），
GGUF 权重不是 `QuantizedTensor` → 走 1089 行的 eager 分支，先算 `_eager_input_act(x, "swiglu")`
再调 `linear(...)`，而 `GGMLOps.Linear.forward_comfy_cast_weights(input)` 只收一个参数正好对得上。

实测（CPU，`--cpu`，走节点同款 `gguf_sd_loader` → `load_diffusion_model_state_dict`）：

- `qwen-image-2.1-UC-Q4_K_M.gguf`：arch `qwen_image21`，297 个 key
- 识别成 `comfy.ldm.qwen_image21.model.QwenImage21Transformer2DModel`，latent format `QwenImage21`
- `SwiGLUFeedForward` 是**未融合**版本（`fused=False`，权重是 `proj`/`gate_layer`），
  `proj` 是 `(12288, 4096) uint8`（GGUF 量化按原样保留，没有解包成 float）
- 同一份权重上跑 `comfy.ops.linear_input_act(mlp.out, x, "swiglu")` → `(1, 5, 4096)`，
  与不融合路径同形状，说明融合分支在 GGMLOps 下也是通的（本文件不走这条路）

脚本：`%TEMP%\opencode\verify_qwen_image21_gguf.py`。Q8_0 没有单独再跑一遍——两者只差量化档位，
卡住的那个 arch 判断是同一个 gate。

**代价**：这个改动在 `custom_nodes` 里，ComfyUI-Manager 更新该节点或重装环境会被覆盖，
届时把那一处字符串加回去即可（等 upstream 合并后就不用管了）。

### 跑起来但「显存爆 + 非常慢」（已定位：是启动参数，不是模型）

第一次跑通 t2i 后症状：24 GB 卡上显存几乎占满，第一步之前就花了 78 秒。
日志（`…\ComfyUI\user\comfyui.log`）给的是结论，不是猜的：

```
Model storage policy: fast_disk=True paths=[…qwen_image_2.1_vae_bf16.safetensors]
Model Qwen35TEModel_      prepared for dynamic VRAM loading.  9031MB Staged.
Model QwenImage21TEModel_ prepared for dynamic VRAM loading.  8916MB Staged.   (×2)
loaded completely; 8284.17 MB usable, 7367.88 MB loaded, full load: True
```

- 两个文本编码器是 **qwen-image 2.1 的设计**，不是工作流冗余：t2i 只有**一个** `CLIPLoader`，
  它本身就有 `clip_name`（Qwen3-VL 8B）+ `clip_name_1`（9B PE）两个输入。
  9 GB + 9 GB 全程靠 smart memory 留在卡上，于是 DiT 只剩 8.28 GB 可用窗口。
- `fast_disk=True` **不是** `--fast-disk` 带出来的：`comfy/storage.py:104-110` 在没传
  `--fast-disk / --disable-fast-disk` 时按磁盘类型自动判定，本机 SSD 判定为 True。
  摘掉 `--fast-disk` 后日志第 105 行仍是 `fast_disk=True`，磁盘直读路径没变。
  该模式按 `comfy/ops.py:248` 不把权重复制进 pinned RAM，靠 32 GB 内存的页缓存兜 25 GB 模型
  （2×9 GB TE + 7.4 GB DiT）——这是"慢"的背景，但不是这次的主因。
- 真正让它变轻的是 smart memory：默认会把两个 TE 一直留在卡上，旧环境则用完就卸。
  对照旧环境 `run_amd_gpu_enable_dynamic_vram.bat` 的参数：

| | 旧环境 0.39.2 | 新环境原来 | 现在 |
|---|---|---|---|
| 磁盘直读 | 自动 | 自动（`--fast-disk` 也是它带的） | 自动 |
| 用后释放显存 | `--disable-smart-memory` | 无（默认常驻） | 已加 |
| 节点结果缓存 | `--cache-none` | 默认 | 已加 |
| pinned 内存 | `--disable-pinned-memory` | 默认开（13066 MB） | 已关闭 |
| 预留显存 | `--reserve-vram 6` | 无 | 已加 |
| 中间量 | `--fp16-intermediates` | 无 | 已加 |

现在的启动参数（Desktop 的 `installations.json` → `launchArgs`）：

```
--enable-manager --use-ck-attention --preview-method auto
--disable-smart-memory --cache-none --reserve-vram 6 --disable-pinned-memory --fp16-intermediates
```

（`--enable-dynamic-vram` 在 0.44.2 是默认开的，不必再写。）

实测（`user/comfyui.log`），同一工作流、1024²、25 步、Q4_K_M：

| | 0.44.2（think+refine 开） | 0.45.2（think/refine 关） |
|---|---|---|
| 采样 | 1.86 s/it | 2.59 s/it |
| 整条 `Prompt executed` | 118.95 s | 81.02 s |
| DiT 载入 | `7367.88 MB` | `4487.25 MB` |
| DiT 载入时 usable | 17017.84 MB | 22560.80 MB |

两处变化：

1. **GGUF 认对了量化类型**。同一个文件，0.44.2 打的是 `gguf qtypes: BF16 (68), Q8_0 (229)`，
   0.45.2 是 `BF16 (68), Q4_K (165), Q6_K (64)` —— 229 = 165 + 64，同一批张量。
   实测文件结构（`gguf` 读 header）：Q4_K 2646.7 + Q6_K 1680.0 + BF16 64.5 = 4391.2 MiB，
   正好等于文件大小。于是 DiT 占用从 7367 MB 掉到 4487 MB（≈文件大小，量化态原样驻留）。
2. **关掉 think / refine 少了一个 9 GB 编码器**：0.44.2 那条链路同时驻留
   `Qwen35TEModel_ 9031 MB`（Qwen3-VL 8B）和 `QwenImage21TEModel_ 8916 MB`；
   0.45.2 + think/refine 关，只剩 8916 MB 那一个（正/负各跑一次）。

代价是每步慢了：`1.86 → 2.59 s/it`（25 步多 18 秒）。最可能的原因是 K-quant 按量化态驻留、
线性层每步现场反量化；0.44.2 那份按 8.5 bit/参数铺开（≈7.37 GB，与日志吻合），算得更快但多吃 2.9 GB。
**这条是推断，没有单独 A/B 验证。** 总体仍是 0.45.2 更快：省掉 9 GB 编码器的加载比每步多花的 18 秒值钱。

顺带：`installations.json` 里 `comfyVersionTag` 还写着 `v0.44.2`（Desktop 的账本滞后），
以日志的 `ComfyUI version: 0.45.2` + `comfy-kitchen 0.2.41` 为准。

如果改完还是慢，下一步才是 `--disable-dynamic-vram`：社区里 AMD RDNA3 + 慢盘的 10× 减速就是靠它
（ComfyUI #15661，维护者 rattus128 的回复）。但同一位维护者也提醒，GGUF 用户不建议关动态显存；
本机 DiT 4.5 GB 能整体驻留，所以这条留着当备选，不先动。

### H3 有没有被这组参数拖慢（实测：没有）

| | 改前 | 改后第 1 条 | 改后第 2 条 | 改后复测 | 0.45.2 |
|---|---|---|---|---|---|
| 6 步采样 | 38.33 s/it | 37.33 s/it | 38.49 s/it | 38.38 s/it | 37.98 s/it |
| 总耗时 | 296.78 s（近期 272–296） | 350.26 s | 284.12 s | 292.65 s | 280.27 s |
| DiT 载入时可用显存 | 15299 MB | 9854 MB | 9745 MB | 9634 MB | 15299 MB |

「改后第 1/2 条 + 复测」是第二套参数（`--reserve-vram 6` 生效中，所以 usable 只有 9.6 GB）；
「0.45.2」那一列已换成推荐第三条（`--disable-smart-memory --cache-none --fp16-intermediates`），
usable 回到 15299 MB，采样 37.98 s/it —— 和 0.44.2 没区别，H3 不受版本升级影响。

采样没变，295 s 正好落在 272–296 的老基线里。350 s 那条只是重启后第一发的冷启动账：
DiT 9 GB 从盘读 36 s（第二发只要 7 s），外加 16.7 GB 文本编码器和两个 VAE 冷读。

真正的代价是 `--reserve-vram 6`：可用显存 15299 → 9634–9854 MB。6 步短片撑得住，
H3 长片 / 高分辨率 / 连跑时余量不够会掉进部分载入，那时才真的慢。
现已摘掉它和 `--disable-pinned-memory`（qwen 那边靠的是 `--disable-smart-memory` + `--cache-none`，
这两条不动），0.45.2 复测 usable 回到 15299 MB、采样 37.98 s/it，两边都不用再牺牲。

### 480P 能跑多长（实测：832×480 × 345 帧，再往上就断崖）

| width×height | length | 秒 | token | 实测 |
|---|---|---|---|---|
| 832×480 | 345 | 14.4 | 33,540 | **324 s，不爆显存** |
| 832×480 | 362 | 15.1 | 35,100 | 爆显存 → 掉进部分载入，慢 3–4 倍（约 1000–1300 s） |

token 公式（H3 是 16× 空间 + 4× 时间压缩 + 1×2×2 patch）：

```
tokens = (length / 4) × (width / 32) × (height / 32)
```

- `1344×768×124`（720P 5.2 s）= 31,248
- `832×480×345`（480P 14.4 s）= 33,540

两个都在这张卡的线内侧，所以**720P/5 秒和 480P/14.4 秒是同一个显存档位**，上限大约 33.5k token。

关键：跨过这条线的代价不是线性的。345 → 362 只多了 5% token，时间直接 ×3–4，
因为掉进部分载入后每步都要重新搬权重。**480P 就按 345 帧（14.4 秒）当上限，别去试 362。**

同理，720P 若想加长，`1344×768` 每帧 252 token，34500/252 ≈ 137 帧（5.7 秒）就是那档的天花板。

填法：`width` / `height` 必须能被 32 整除（`nodes_minimax_h3.py:145-147`），`length` 只能取 17k+5。
480P 用 `832×480` 正好两项都满足；想要和 1344×768 同构图的 2/3 版是 `896×512`（多约 15% token）。
估算精度：先前按 720P 外推给 362 帧 ≈ 350 s，实测 345 帧 324 s，偏差 ~8%，可以当作 ±10% 用。

---

## 1.5 每天用的流程（先看这段）

```powershell
# 1. 启动 ComfyUI，参数见 §1.2「跑起来但显存爆/非常慢」
# 2. 关掉所有占显存的程序（浏览器硬件加速、别的 ComfyUI、游戏）
# 3. 卸掉上一轮的残留 —— 连续第二次生成不跑这个必爆显存（主文档 §7.5）
& "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 `
  "D:\localAI\ComfyUI-last\plan3\t2v\step0_free.py"
#    期望最后一行：ok : 23.5x GB free
# 4. 在网页里点 Queue
```

`step0_free.py` 会等到 `total - 1.5 GB` 才返回；达不到就打印 `FAILED` 并以退出码 1 结束。
**看到 FAILED 就别点 Queue**，先查谁还占着显存。

`bat\free_vram\` 是同一件事的通用版（`--status` 只看状态、`--interval N` 挂机定时清、
`--no-verify` 不等），从 `plan\bat` 原样复制；它的验证只要求「VRAM 有上升」，
**没有 `total - 1.5 GB` 这道门槛**，所以点 Queue 前的拦截仍然用 `step0_free.py`。

懒得敲路径就双击 `t2v\step0_free.bat`（同一个脚本，带 `pause` 让你看结果）。

`bat\` 里的脚本自己会跑 `/free`（`free_vram()`），走脚本时不需要再手动跑一次。

---

## 2. `tools\`

| 文件 | 作用 |
|---|---|
| `stock_{t2v,i2v,flf2v,ref2v}.json` | 官方 `example_workflows/hyperflow_<family>.json` 的 **UI 格式**快照，UI 工作流的起点。上游插件更新后要重新复制 |
| `stock_{t2v,i2v,flf2v,ref2v}_api.json` | 同一批官方示例的 **API 格式**快照（`example_workflows/api/`），API 工作流的起点 |
| `make_workflow.py` | 从快照生成两套 `hyperflow_<family>_clipproj_8b[_api].json`：换 8B heretic 编码器、插 `ClipProjApply`、`weights_in=disk`、改写图内说明（API 那份是同样的三处改动，只是没有 MarkdownNote） |
| `check_workflow.py` | 静态校验，支持一次传多个文件：UI 图查 link 两端；API 图查 `[id, slot]` 引用是否都指向本文档内的节点、有无 UI 残留字段。两种都断言 ClipProj 接线、`boogu`、`weights_in=disk`，以及 `euler` / `steps ∈ {4,6,8}` |
| `check_gguf.py` | 核对 GGUF 结构是否符合 `gguf_io.py` 的预期（无 `general.architecture`、`hyperflow_*` 三件套、低秩块计数） |

全用**新环境的 venv** 跑：

```powershell
$py = "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
& $py make_workflow.py                # 4 个 family，UI + API 共 8 个文件
& $py make_workflow.py ref2v          # 只生成一个
& $py check_workflow.py "C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\hyperflow_i2v_clipproj_8b.json"
& $py check_workflow.py ..\API_workflows\*.json
& $py check_gguf.py
```

`check_gguf.py` 最后一行输出的块数，应当与启动日志里
`HyperFlow: 18 factorized blocks` 的数字一致 —— 这是「文件没被换过」最省事的核对方式。

---

## 3. 四个工作流（非 int8）

`make_workflow.py` 一次生成全部；四个图的骨架相同，差别只在被喂 `clip` 的节点和额外输入。

| 文件 | DiT | 额外输入 | 输出前缀 |
|---|---|---|---|
| `hyperflow_t2v_clipproj_8b.json` | `fl2va` | — | `hyperflow/t2v` |
| `hyperflow_i2v_clipproj_8b.json` | `fl2va` | `first_frame` | `hyperflow/i2v` |
| `hyperflow_flf2v_clipproj_8b.json` | `fl2va` | `first_frame` + `last_frame` | `hyperflow/flf2v` |
| `hyperflow_ref2v_clipproj_8b.json` | **`ref2va`** | 2 张参考图（`<Picture 1>`/`<Picture 2>`） | `hyperflow/ref2v` |

四个图共同的编码路径：

```
CLIPLoader(qwen3-vl-8b-heretic, boogu) -> ClipProjApply(mmh3-8b-ClipProj-v3.1-mlp) -> MiniMaxH3*ToVideo.clip
```

`hyperflow_ref2v` 最多接 9 张参考图（`<Picture 1>`…`<Picture 9>`），
GGUF 路线只吃图片参考，不吃视频/音频参考（那些要走官方 INT8 + Python 包）。

### 3.1 API 工作流（`API_workflows\`）

同四个 family 的 **`/prompt` payload**，由 `tools\make_workflow.py` 从
`tools\stock_<family>_api.json`（官方 `example_workflows/api/` 快照）生成，改动与 UI 那份完全相同：

| # | 改动 |
|---|---|
| 1 | `CLIPLoader`：`qwen3vl_32b_minimax_h3_nvfp4_awq` / `minimax` → `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn` / **`boogu`** |
| 2 | 新增 `ClipProjApply`（`mmh3-8b-ClipProj-v3.1-mlp`），把 `MiniMaxH3*.clip` 从 `["2",0]` 改指向它 |
| 3 | `HyperFlowLoader.weights_in` = **`disk`** |

| 文件 | 节点 | 额外输入 |
|---|---|---|
| `hyperflow_t2v_clipproj_8b_api.json` | 15 | — |
| `hyperflow_i2v_clipproj_8b_api.json` | 16 | `LoadImage`(`20`) → `first_frame` |
| `hyperflow_flf2v_clipproj_8b_api.json` | 17 | `LoadImage`(`20`,`21`) → `first_frame` / `last_frame` |
| `hyperflow_ref2v_clipproj_8b_api.json` | 17 | `LoadImage`(`20`,`21`) → `ref_images.ref_image_0/1` |

提交（**同样要先跑 `t2v\step0_free.py`**）：

```powershell
$body = '{"prompt": ' + (Get-Content -Raw -Encoding utf8 "API_workflows\hyperflow_t2v_clipproj_8b_api.json") + '}'
$body | Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8188/prompt -ContentType application/json
```

改参数直接改 JSON 里的值（都是 model 的 input，不是 widget）：

- 提示词 / 尺寸 / 帧数：`5.inputs.prompt` / `width` / `height` / `length`
- 步数：`6.inputs.steps`（**只取 4 / 6 / 8**）
- 种子：`8.inputs.noise_seed`
- 输出前缀：`14.inputs.filename_prefix`
- i2v / flf2v / ref2v 的图片：`20`/`21` 号 `LoadImage.inputs.image`，文件名相对 `ComfyUI\input\`
  （模板里写的是 `first_frame.png` / `ref_image_1.png` 等占位名，必须换成实际存在的文件）

静态自检：`& $py check_workflow.py ..\API_workflows\*.json` —— 查 `[id, slot]` 引用是否都落在本文档内、
有无 UI 残留字段（`widgets_values`），并断言上面的三处改动、`euler`、`steps ∈ {4,6,8}`。

**已实测（2026-11-12，用户手动提交 `/prompt`）**：四条 payload 均通过实际运行验证，不再只靠静态校验。
静态自检仍建议每次改完先跑一遍：`& $py check_workflow.py ..\API_workflows\*.json`。

---

## 4. `bat\` 脚本（API 直连，不经网页）

从 `plan\bat` 移植；`build_graph()` 已换成 HyperFlow 链，分段 / 末帧续接 / ffmpeg 拼接逻辑原样复用。
**四个生成脚本 2026-11-12 已实跑通过**。

| 目录 | 入口 `.bat` | 作用 |
|---|---|---|
| `multisegment_8b_heretic\` | `gen_h3_multisegment-8b-heretic.bat` | 一条提示词、N 段等长，段间末帧续接 |
| `scenes_8b_heretic\` | `gen_h3_scenes-8b-heretic.bat` | 每段独立提示词 + 独立时长，超长自动拆 |
| `scenes_ref_8b_heretic\` | `gen_h3_scenes_ref-8b-heretic.bat` | 同上 + 参考图/参考视频（段 0 走 ref2va） |
| `ref2va_8b_heretic\` | `gen_h3_ref2va-8b-heretic.bat` | 参考图生视频，多段末帧续接 |
| `extract_frames\` | `gen_extract_frames.bat` | 抽首 / 中 / 末帧（与模型无关） |
| `qc_frames\` | `gen_h3_qc_frames.bat` | 均匀抽 N 帧 + contact sheet（与模型无关） |
| `free_vram\` | `free_vram.bat` | 通用 `/free`：`--status` 只看状态、`--interval N` 挂机定时清、`--no-verify` 不等 |
| `提示词模板\` | — | `MiniMax-H3-提示词书写规则.md`（19 KB，官方两份指南 + 本机节点源码写成）+ 视频 / 静帧 / 照片三个 `.txt` 示例。**写提示词前先看 md**；md 与 `.txt` 冲突时以 md 为准（主文档 §9） |
| `测试素材\` | — | 两张示例参考图，与 `ref2va_8b_heretic\img\` 同内容 |

每个生成脚本目录里还有一份可直接跑的 `prompt.txt`（`ref2va` / `scenes_ref` 另有 `img\` 示例参考图），
首次跑不用自己编提示词。

自检（不提交、不加载模型，纯静态）：

```powershell
& $py "D:\localAI\ComfyUI-last\plan3\bat\check_graphs.py"
# 期望最后一行：ok: every node reference and input name resolves
```

它把 4 个脚本的 8 种图都 build 一遍，对照官方 API 图检查节点类型与输入名 ——
ComfyUI 对不认识的输入是**静默忽略**的，写错名字只会「出图但参数没生效」。

`--steps` 只接受 `4/6/8`（`HyperFlowSigmas` 的硬约束），交互输入越界会回退默认 6。

---

## 5. 硬编码路径（跨机必改）

| 文件 | 常量 | 现值 |
|---|---|---|
| `tools\make_workflow.py` | `WORKFLOWS` | `…\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows` |
| `tools\make_workflow.py` | `API_OUT` | `<plan3>\API_workflows`（按脚本自身位置推导，换目录不用改） |
| `tools\check_gguf.py` | `DEFAULT` | `…\ComfyUI-Shared\models\diffusion_models\…-Q4_K_M.gguf` |
| `tools\check_workflow.py` | — | 路径由命令行传入 |
| `bat\check_graphs.py` | `API` | `…\custom_nodes\ComfyUI-HyperFlow-Flash\example_workflows\api` |
| `bat\*\*.py` | `FFMPEG` | Gyan `ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe` |
| `bat\*\*.py` | `API` | `http://127.0.0.1:8188` |
| `bat\*\*.bat` | python 绝对路径 | `…\ComfyUI\.venv\Scripts\python.exe`（**例外**：`free_vram\free_vram.bat` 是裸 `python`，原样复制未改） |
| `bat\free_vram\free_vram.py` | `DEFAULT_HOST` / `DEFAULT_PORT` | `127.0.0.1` / `8188`（可用 `--host` / `--port` 覆盖） |
| `t2v\step0_free.py` | `BASE` | `http://127.0.0.1:8188`（可用 `--host` 覆盖） |

---

## 6. 与新环境的关系

**本目录不含模型、不含 `custom_nodes`、不含工作流本体**，这些都在 `C:\Comfy-Desktop\` 下：

| 类别 | 位置 |
|---|---|
| 工作流 | `C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\hyperflow_<family>_clipproj_8b.json` |
| API 工作流 | `plan3\API_workflows\hyperflow_<family>_clipproj_8b_api.json`（不在 workflows 目录，否则会混进 UI 列表；直接 POST `/prompt`） |
| 模型 | `C:\Comfy-Desktop\ComfyUI-Shared\models\{diffusion_models,text_encoders,vae}\` |
| 投影矩阵 | `C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\clip_projections\` |
| 节点 | `C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes\{ComfyUI-GGUF,ComfyUI-HyperFlow-Flash,ComfyUI-ClipProj}\` |
| 输出 | `D:\Comfy-Desktop\ComfyUI-Shared\output\hyperflow\` |

迁移到另一台机器时，`tools\` 里除 `stock_*.json` 外都要改上表的路径，`bat\` 里要改 `API`、`FFMPEG` 和 `.bat` 里的 python 路径。

---

## 7. 五条不变的结论

1. **GGUF 组 + Qwen3-VL-8B heretic + `mmh3-8b-ClipProj-v3.1-mlp`** 是这台机器（gfx1100 / 24 GB / 32 GB）
   唯一能落地的组合；INT8 组和 32B 编码器都不可达，理由写在主文档 §4。
2. **`--use-ck-attention` 必加**；`--fast-disk` 本机不用写 —— `comfy/storage.py` 会按磁盘类型自动判定为
   True（日志 `Model storage policy: fast_disk=True` 即生效）。真正不能撤的是这一组：
   `--disable-smart-memory --cache-none --fp16-intermediates`（换掉旧环境的「用完就卸」，否则编码器常驻抢显存）。
3. **1344×768×124 帧 / 6 步已是显存上限**：开跑前关掉所有占显存的程序，
   否则会退化成数据交换，5 分钟变 16 分钟。
4. **每次提交前必须 `/free`**（`t2v\step0_free.py`）：跑完一次会留 14.5 GB 驻留，
   第二次装编码器时必爆。图内卸载节点代替不了它——缺 `gc.collect()` 和 `e.reset()`。
   `bat\` 脚本内部的 `free_vram()` 做的就是这件事。
5. **提示词按 `bat\提示词模板\MiniMax-H3-提示词书写规则.md` 写**：三字段缺一不可（没内容写 `N/A`），
   风格句放 `[Shot 1]` 之后第一句。**不要写禁令** —— CFG 锁死 1，没有负向分支，
   `no anime` / `avoid …` 里的词会照样进入条件向量，把风格拉向它。详见主文档 §9。
