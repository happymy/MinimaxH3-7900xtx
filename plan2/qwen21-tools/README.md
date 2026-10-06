# qwen21-tools

Qwen-Image 2.1 (GGUF) 在本地 ComfyUI 上的工作流工具集。

配套的三个工作流在 `ComfyUI\user\default\workflows\`：

| 文件 | 用途 |
|---|---|
| `qwen_image_2_1_t2i_gguf.json` | 文生图 |
| `qwen_image_2_1_image_edit_gguf.json` | 图生图 / 编辑 |
| `qwen_image_2_1_background_removal_gguf.json` | 抠图 / 去背景 |

环境：ComfyUI 0.38.0，portable + ROCm torch 2.9.1（RX 7900 XTX 24 GB）。

**启动 ComfyUI（2026-10-03 更新）**：本目录是**生图**工具链，必须用
**`run_amd_gpu_no_ck_attention.bat`**（关 ck）。H3 生视频才用带 ck 的
`run_amd_gpu_enable_dynamic_vram.bat`。两个脚本都带 `--enable-dynamic-vram`，
动态显存这条不变，别认错脚本。

> ⚠️ 原文此处写的是「只能用 `run_amd_gpu_enable_dynamic_vram.bat`」，那条只验了动态显存、
> 没拆开 ck 变量。后续实测：ck 生图会「脏」且**超长提示词会丢失**，故生图一律关 ck。
> 详见 `plan2\Qwen-Image-2.1-GGUF-部署总结.md` §3 与 `plan\CK注意力回归问题调查报告.md`。

---

## 脚本

| 脚本 | 作用 |
|---|---|
| `check_workflows.py` | 静态校验：悬空 link、`UnetLoaderGGUF` 数量、引用的模型是否真在磁盘上。无参数。 |
| `fetch_schema.py` | 从运行中的 ComfyUI `/object_info` 抓 `node_schema.json`（转换器依赖它）。 |
| `ui2api.py <in.json> <out.json>` | 前端 UI 格式 → API prompt 格式（含子图展开、widget 位置映射）。 |
| `run_api.py <api.json> [prefix]` | 把转换后的 API 图丢给 `/prompt` 并轮询到出结果。 |
| `adapt_workflows.py` | 从**已安装的** `comfyui-workflow-templates` 官方模板重新生成三个 GGUF 工作流。Comfy-Org 出新模板时用它重新适配。 |

`node_schema.json` 是缓存，升级 ComfyUI 后跑一次 `fetch_schema.py` 刷新。

## 用法

```powershell
$py  = "D:\localAI\ComfyUI-last\ComfyUI_windows_portable\python_embeded\python.exe"
$wf  = "D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\user\default\workflows"
Set-Location "D:\localAI\ComfyUI-last\plan2\qwen21-tools"   # 2026-10-03 修正：本目录在 plan2 下，原写的 \qwen21-tools\ 已失效

# 1. 改完工作流先静态校验
& $py check_workflows.py

# 2. 转成 API 格式并真实跑一遍（无头，不需要开 UI）
& $py ui2api.py "$wf\qwen_image_2_1_t2i_gguf.json" api_t2i.json
& $py run_api.py api_t2i.json mytest

# ComfyUI 升级后刷新 schema
& $py fetch_schema.py
```

输出图在 `ComfyUI\output\`。

---

## 转换器为什么这么写

这三条是实际踩出来的，改转换器前先读。

### Autogrow / DynamicCombo 的 API 输入是扁平点号 key

`Autogrow`、`DynamicCombo`（`COMFY_DYNAMICCOMBO_V3`）的嵌套输入，API 端**不接受** dict 容器，
必须是 `"images.image_1"`、`"format.bit_depth"` 这种扁平点号 key。
`execution.py` 把 prompt 的原始 input dict 直接当 `live_inputs` 传下去，
`_io.py` 拿 `finalize_prefix(...)` 生成的点号名去比对，键名对不上就**静默丢弃**、节点退回默认值。

症状：背景移除跑出来是 1024×1024 而不是 896×1152，prompt 里没报错。

例：
- `SaveImageAdvanced` → `format` + `format.bit_depth` + `format.input_color_space`
- `TextEncodeQwenImage21` → `images.image_1` / `images.image_2`
- `TextGenerate.sampling_mode` → `sampling_mode` + `.temperature` / `.top_k` / `.top_p` / `.min_p` / `.repetition_penalty` / `.seed` / `.presence_penalty`

注意 `BatchImagesNode` 的 `image0` / `image1` 是**真名**，不是 autogrow 计数器，别去剥后缀。

### `widgets_values` 是按全量声明 widget 顺序定位的

包含前端专用的 `control_after_generate`（例如 seed 后面那个 `"randomize"`）。
所以按 `object_info` 的 `inputs` 里那些 `widget` 标记去推下标**推不出来**——那套下标和实际存储顺序不一致。
`fetch_schema.py` 记的是类的完整声明顺序，靠"类型不匹配就跳过、combo 值不在选项里就跳过"来定位。

### 组合框的第二元素有两种形态

`object_info` 里 combo 的第二个元素要么是选项列表，要么是配置 dict。
非 list 就当"选项未知"，接受任意标量。

### `ImageCompare` 在官方模板里 `widgets_values` 是空的

它必需的 `compare_view` 没有任何值可发，API 端永远满足不了。
纯预览节点，`run_api.py` 会直接删掉。

### 子图

子图里从输入节点（-10）出发的 link 指的是**接口槽位**而不是节点；
落到输出节点（-20）的 link 才是顶层实例会重新导出的那些。
子图实例上的 `widgets_values` 按子图接口输入顺序排，**跳过纯 socket 类型**（如 `IMAGE`），
实例上有真实入向 link 时以 link 为准。

---

## GGUF 相关的坑

- GGUF 加载器是 **fork 版** `ChrisColeTech/ComfyUI-GGUF-Loader` @ `b8486409`（v2.16.7），不是 `leejet/ComfyUI-GGUF`。
  它的 `IMG_ARCH_LIST` 已被改成包含 `"qwen_image21"`。
- 要测这个加载器**必须**传 `model_options={"custom_operations": GGMLOps()}`（或直接调 `UnetLoaderGGUF.load_unet`）。
  不传的话 `load_state_dict` 会把 `checkpoint` 的维度算成 `nbytes/2`，
  然后抛出 232 条 `While copying` 之类的假错误。
- `GGMLTensor.numel()` 返回的是打包后的字节数，这是设计如此，不是 bug。

## 模型

| 角色 | 目录 | 文件 | 大小 | 用在 |
|---|---|---|---|---|
| DiT | `diffusion_models` | `qwen-image-2.1-UC-Q4_K_M.gguf` | 4.29 GiB | 全部三个 |
| 基础文本编码器 | `text_encoders` | `qwen3vl_8b_int8_convrot.safetensors` | 8.71 GiB | 全部三个 |
| VAE | `vae` | `qwen_image_2.1_vae_bf16.safetensors` | 0.63 GiB | 全部三个 |
| PE 改写 t2i | `text_encoders` | `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` | 8.82 GiB | 仅 t2i |
| PE 改写 i2i | `text_encoders` | `qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors` | 8.82 GiB | 仅 image_edit |

两个 PE 模型是提示词改写用的（`abenzerps` 版是 9B Qwen3.5，非官方 README 里的 9B Qwen3-VL）。
**同时全量加载会爆显存** —— t2i 工作流的 `switch` 置 `false` 时 PE 模型不进显存，实测 46 s 出图；
置 `true` 则启用改写，耗时明显变长。background_removal 不需要 PE 模型。

磁盘上还有几个同系列的其它权重（`qwen3-vl-4b-heretic*` GGUF、`qwen3vl_8b_fp8_scaled`、`qwen_image_vae`），
当前三个工作流都没引用，是之前试装留下的，换量化时可以直接用。
