# Qwen-Image 2.1 GGUF 本地部署总结

> 项目目录：`D:\localAI\ComfyUI-last\`
> 完成日期：2026-09-30
> 状态：**已完成并实测通过**

---

## 1. 目标

把 `abenzerps/Qwen-Image-2.1-Uncensored-GGUF` 部署进本地 ComfyUI portable，
交付 Comfy-Org 官方 Qwen-Image 2.1 工作流的**完整三件套**（t2i / image_edit / background_removal），
并改写为 GGUF 加载，最后用**真实生成**验证每一条都跑得通。

---

## 2. 结论

| 项 | 结果 |
|---|---|
| 三件套工作流 | 已交付，静态校验全 clean |
| 真实生成验证 | 三条全部 `execution_success` |
| ComfyUI 版本 | 0.34.0 → **0.38.0**（Qwen-Image 2.1 节点需要） |
| 工作区状态 | git clean @ `fb2315f1` |
| 遗留阻塞 | 无 |

---

## 3. 环境

| 项 | 值 |
|---|---|
| GPU | AMD Radeon RX 7900 XTX，24 GB |
| 内存 | 31.9 GB |
| torch | `2.9.1+rocm7.2.1`（ROCm 7.2.53211-158bd99533） |
| ComfyUI | 0.38.0，commit `fb2315f11db0ebfaafa9099a5df5227dc6bb42bc` |
| 提交说明 | `Fix crash when selecting int8 or int4 cache in qwen image 2.1 (#16667)` |
| Python | portable 内置 `python_embeded` |
| 磁盘 | D: 约 215 GB 可用 |
| 端口 | 8188 |

**启动方式（强制，2026-10-03 更新）**：Qwen-Image 2.1 属于**生图**，必须用
`ComfyUI_windows_portable\run_amd_gpu_no_ck_attention.bat`。

| 用途 | 启动脚本 | `--use-ck-attention` |
|------|----------|:---:|
| **Qwen 生图**（本文件范围：Image-2.1 t2i / edit / 抠图） | `run_amd_gpu_no_ck_attention.bat` | ❌ 关 |
| **H3 生视频**（t2v / i2v / ref2v） | `run_amd_gpu_enable_dynamic_vram.bat` | ✅ 开 |

两个脚本**都带 `--enable-dynamic-vram`** —— 动态显存策略是 OOM 的关键，这条不变；
区别只在 ck 开关，所以别认错脚本。

**⚠️ 为什么改（2026-10-03 用户实测，与本文 09-30 的原结论相反）**：
原文写「只能用 enable_dynamic_vram」，那条结论只验了「动态显存」，没拆开 ck 变量。
后续实测发现 ck 对**生图**是负向的：

- 图片会「脏」、与提示词不符；
- **超过一定长度的提示词会丢失**。

因此生图一律关 ck。反过来 ck 对**生视频**几乎看不出质量影响，且快一个数量级
（20 分钟片子 → 5 分多钟），所以 H3 视频继续带 ck。

> 换其它启动方式动态显存策略不生效，Qwen-Image 2.1 会 OOM —— 这条仍然成立。
> 交叉证据见 `plan\CK注意力回归问题调查报告.md`（Qwen 侧 token 64 边界二分）
> 与 `plan\ck_ab_20261002\`（H3 侧受控 A/B，结论：H3 走 ck 安全）。

---

## 4. 交付物

### 4.1 工作流

位置：`ComfyUI_windows_portable\ComfyUI\user\default\workflows\`

| 文件 | 大小 | 用途 |
|---|---|---|
| `qwen_image_2_1_t2i_gguf.json` | 74,993 B | 文生图 |
| `qwen_image_2_1_image_edit_gguf.json` | 93,805 B | 图生图 / 编辑 |
| `qwen_image_2_1_background_removal_gguf.json` | 51,499 B | 抠图 / 去背景 |

`UnetLoaderGGUF` 节点在 `widgets_values` 里的槽位分别是 **11 / 12 / 11**（三者不同，改脚本时别搞混）。

### 4.2 工具集

位置：`D:\localAI\ComfyUI-last\qwen21-tools\`

| 文件 | 作用 |
|---|---|
| `check_workflows.py` | 静态校验：悬空 link / loader 数量 / 模型是否在盘 |
| `fetch_schema.py` | 抓 `/object_info` → `node_schema.json`（1009 类） |
| `ui2api.py` | UI 格式 → API prompt 格式（子图展开、widget 定位） |
| `run_api.py` | 无头执行并轮询出结果 |
| `adapt_workflows.py` | 从已安装的官方模板重新适配 |
| `node_schema.json` | 缓存，升级 ComfyUI 后刷新 |
| `README.md` | 用法 + 踩坑记录 |

详见 `qwen21-tools\README.md`。

### 4.3 输入图

从官方模板下载的参考图，放在 `ComfyUI\input\`：

- `angry_broccoli.png`（1,194,081 B）— image_edit 用
- `portrait_model_denim.png`（1,181,250 B）— image_edit 用
- `clothing_light_blue_denim_shirt.png`（1,366,572 B）— background_removal 用

---

## 5. 模型

### 5.1 实际使用的

| 角色 | 目录 | 文件 | 大小 | 用于 |
|---|---|---|---|---|
| DiT | `diffusion_models` | `qwen-image-2.1-UC-Q4_K_M.gguf` | 4.29 GiB | 全部三个 |
| 基础 TE | `text_encoders` | `qwen3vl_8b_int8_convrot.safetensors` | 8.71 GiB | 全部三个 |
| VAE | `vae` | `qwen_image_2.1_vae_bf16.safetensors` | 0.63 GiB | 全部三个 |
| PE 改写 t2i | `text_encoders` | `qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors` | 8.82 GiB | 仅 t2i |
| PE 改写 i2i | `text_encoders` | `qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors` | 8.82 GiB | 仅 image_edit |

全部 size 校验通过，来源 Comfy-Org / hf-mirror。

### 5.2 磁盘上其它同系列权重（当前未被引用）

`qwen3-vl-4b-heretic-Q4_K_M.gguf`、`qwen3-vl-4b-heretic.mmproj-f16.gguf`、
`qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors`、`qwen3vl_8b_fp8_scaled.safetensors`、
`qwen_image_vae.safetensors`

换量化方案时可直接用。

### 5.3 显存约束

两个 PE 模型（各 8.82 GiB）是提示词改写用的。**同时全量加载会爆显存。**
t2i 工作流的 `switch` 置 `false` 时 PE 模型不进显存；置 `true` 才启用改写，耗时会明显变长。
background_removal 不需要 PE 模型。

---

## 6. 工作流适配做了什么

上游来源是**已安装的** `comfyui-workflow-templates` 0.11.70 的 JSON，不是 GitHub 拉的原版，
这样交付物能跟着已装的版本走。

改动只有两处：

1. `UNETLoader` → `UnetLoaderGGUF`，**去掉** `weight_dtype`，**保留** `unet_name`
2. 重写 `## Model Links` 注释里 `**diffusion_models**` 那一行，指向 GGUF 仓库

其余原样保留 —— 子图、MarkdownNote、ImageCompare 都不动。

---

## 7. 依赖与节点

### 7.1 pip 修复的包

| 包 | 版本 |
|---|---|
| `comfy-aimdo` | 0.5.5 |
| `comfy-kitchen` | 0.2.36 |
| `comfyui-embedded-docs` | 0.5.13 |
| `comfyui_frontend_package` | 1.53.6 |
| `comfyui-workflow-templates` | 0.11.70 |
| `comfyui-workflow-templates-core` | 0.3.361 |
| `comfyui-workflow-templates-json` | 0.1.96 |

`comfyui-workflow-templates-media-assets-01==0.1.48` **主动跳过** —— 阿里云镜像卡在 0 字节。

pip 走 `mirrors.aliyun.com/pypi/simple`，模型走 hf-mirror + aria2c。

### 7.2 自定义节点

| 节点 | 版本 / commit | 备注 |
|---|---|---|
| `ComfyUI-GGUF-Loader` | `b848640` (v2.16.7) | **fork 版**，不是 `leejet` 原版 |
| `ComfyUI-KJNodes` | `5710537` | |
| `ComfyUI-ClipProj` | v0.1.4 (`c01ba8f`) | |
| `ComfyUI-ForceUnloadBeforeDecode` | 无 .git | 显存回收 |

GGUF fork 的 `IMG_ARCH_LIST` 已被改过，加了 `"qwen_image21"`。

---

## 8. 实测结果

全部无头执行，ComfyUI 0.38.0 在线，端口 8188。

| 工作流 | 耗时 | 输出 | 尺寸 | 结果 |
|---|---|---|---|---|
| background_removal | 124 s | `qwen21_bgremove_wftest2_00001.png` | 896×1152 | `execution_success`，四角 alpha=0 |
| image_edit | 310 s | `qwen21_imgedit_wftest_00001.png` | 896×1152 | `execution_success`，PE LLM 改写了 prompt |
| t2i | 46 s | `qwen21_t2i_wftest_00001.png` | 1024×1024 | `execution_success`，`switch=false` |
| t2i（工具搬迁后复测） | 46 s | `qwen21_tools_recheck_00001.png` | 1024×1024 | `execution_success` |

静态校验输出：

```
qwen_image_2_1_t2i_gguf.json               links=3    UnetLoaderGGUF=1 models=4 OK
qwen_image_2_1_image_edit_gguf.json        links=5    UnetLoaderGGUF=1 models=4 OK
qwen_image_2_1_background_removal_gguf.json links=4   UnetLoaderGGUF=1 models=3 OK

RESULT: all clean
```

转换器输出节点数：t2i = 15，image_edit = 18，background_removal = 12。

---

## 9. 关键踩坑

这一节是本次最有价值的部分。**改转换器 / 换模型前先读。**

### 9.1 Autogrow / DynamicCombo 的 API 输入是扁平点号 key

**这是最容易浪费时间的一个坑，因为它不报错。**

`Autogrow` 和 `DynamicCombo`（`COMFY_DYNAMICCOMBO_V3`）的嵌套输入，API 端**不接受** dict 容器，
必须是 `"images.image_1"`、`"format.bit_depth"` 这种扁平点号 key。

机制：`execution.py:169` 把 prompt 的原始 input dict 直接当 `live_inputs` 传下去，
`_io.py`（`Autogrow._expand_schema_for_dynamic` L1168 / `DynamicCombo._expand_schema_for_dynamic` L1255）
拿 `finalize_prefix(...)`（L1074）生成的点号名去比对。
**键名对不上就静默丢弃，节点退回默认值，不抛异常。**

实测症状：背景移除跑出来是 **1024×1024 而不是 896×1152**，日志里没有任何报错。
`qwen21_bgremove_wftest_00001.png`（1024×1024，错）和 `qwen21_bgremove_wftest2_00001.png`（896×1152，对）
就是修复前后的对照。

需要扁平化的具体字段：

| 节点 | 字段 |
|---|---|
| `SaveImageAdvanced` | `format` + `format.bit_depth` + `format.input_color_space` |
| `TextEncodeQwenImage21` | `images.image_1` / `images.image_2` |
| `TextGenerate` | `sampling_mode` + `.temperature` / `.top_k` / `.top_p` / `.min_p` / `.repetition_penalty` / `.seed` / `.presence_penalty` |

**反向注意**：`BatchImagesNode` 的 `image0` / `image1` 是**真名**，不是 autogrow 计数器。
别去剥后缀，会把值打错位置。

### 9.2 `widgets_values` 是按全量声明 widget 顺序定位的

`widgets_values` 是**位置数组**，对应类的**完整**声明 widget 列表，
**包含前端专用的 `control_after_generate`**（例如 seed 后面那个 `"randomize"`）。

所以按 `object_info` 的 `inputs` 里那些 `widget` 标记去推下标**推不出来** —— 那套下标和实际存储顺序不一致。
`fetch_schema.py` 记的是类的完整声明顺序，转换器靠两条规则定位：

- 类型不匹配就跳过
- combo 值不在选项列表里就跳过

### 9.3 combo 的第二元素有两种形态

`object_info` 里 combo 的第二个元素要么是选项列表，要么是配置 dict。
**非 list 就当"选项未知"，接受任意标量。**

### 9.4 `ImageCompare` 在官方模板里 `widgets_values` 是空的

它必需的 `compare_view` 没有任何值可发，API 端永远满足不了。
纯预览节点，`run_api.py` 提交前直接删掉。

### 9.5 子图的 link 语义

- 子图里从输入节点（-10）出发的 link，指向的是**接口槽位**而不是节点
- 落到输出节点（-20）的 link，才是顶层实例会重新导出的那些
- 子图实例上的 `widgets_values` 按子图接口输入顺序排，**跳过纯 socket 类型**（如 `IMAGE`）
- 实例上有真实入向 link 时，以 link 为准，忽略存储值

### 9.6 GGUF 加载器必须传 `custom_operations`

测这个加载器**必须**传 `model_options={"custom_operations": GGMLOps()}`，或直接调 `UnetLoaderGGUF.load_unet`。

不传的话 `load_state_dict` 会把 `checkpoint` 的维度算成 `nbytes / 2`，
然后抛出 **232 条** `While copying` 之类的假错误。

`GGMLTensor.numel()` 返回打包后的字节数，这是**设计如此**，不是 bug。

### 9.7 ComfyUI 版本

0.34.0 没有 Qwen-Image 2.1 节点，必须升到 0.38.0。
当前 commit 恰好修了一个相关崩溃：选择 int8 / int4 cache 时崩溃（#16667）。

---

## 10. 常用命令

```powershell
$py = "D:\localAI\ComfyUI-last\ComfyUI_windows_portable\python_embeded\python.exe"
$wf = "D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\user\default\workflows"
Set-Location "D:\localAI\ComfyUI-last\qwen21-tools"

# 静态校验
& $py check_workflows.py

# 转 API 格式 + 无头跑一遍
& $py ui2api.py "$wf\qwen_image_2_1_t2i_gguf.json" api_t2i.json
& $py run_api.py api_t2i.json mytest

# ComfyUI 升级后刷新 schema
& $py fetch_schema.py

# Comfy-Org 出新模板后重新适配
& $py adapt_workflows.py
```

输出图在 `ComfyUI\output\`。

---

## 11. 官方 skill 的调查结论

用户问过 Qwen-Image 2.1 有没有官方 skill，查证结果：

**Qwen 官方：没有。** `QwenLM/Qwen-Image-2.1` 仓库根目录只有
`LICENSE` / `README.md` / `assets` / `prompt_rewrite`，**无 `skills/`，无任何 `SKILL.md`**。
官方给的是 Diffusers pipeline `QwenImage21Pipeline` 和 `prompt_rewrite/` 代码 + PE 权重。
（搜索到的 `qwencloud-image-generation`、`runapi-ai/qwen-image` 都是第三方，且都走云 API 要 key。）

**Comfy 官方：有，但全绑云端。** `Comfy-Org/comfy-skills`（213 star）里 12 个 skill，但：

1. `skills/` 那 12 个 `.md` 在 README 里标为 legacy / Frozen / 待移除，正主是 `claude-code/` 插件
2. 全部指向 Comfy Cloud 的托管 MCP `https://cloud.comfy.org/mcp`，要 OAuth
3. 另一批（`comfy` / `comfy-debug` / `comfy-relay` / `comfy-director` / `comfy-build`）
   随 `comfy-cli` 发布，`comfy skills install` 装 —— **本机未装 comfy-cli**

两套都驱动不了本地 portable 部署，它们假设模型跑在 Comfy Cloud 上。

**决定**：不装。改为把本次实测踩出来的经验固化成 `qwen21-tools\README.md`，
比装一个用不上的云端 skill 更有价值。已装 skill 位于 `~\.agents\skills\`（67 个），不在本次改动范围内。

---

## 12. 后续可做

- [ ] t2i 的 `switch=true`（启用 PE 改写）实测耗时和显存峰值
- [ ] 换其它 GGUF 量化（Q2_K / Q5_K / Q6_K）对比质量与速度
- [ ] 试 `qwen3-vl-4b-heretic-Q4_K_M.gguf` 小 TE，验证能否省出显存同时全量加载两个 PE
- [ ] Comfy-Org 更新模板后跑 `adapt_workflows.py` 重新适配
- [ ] 把 `qwen21-tools` 收成一个真正的 agent skill（放 `~\.agents\skills\`）
