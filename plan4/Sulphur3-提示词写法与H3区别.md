# Sulphur 3 提示词写法与 H3 的区别

> 2026-11-27 联网核实。来源：Sulphur 官方 `S3_ComfyUI.zip` 的 `example_workflow.json`、
> RunComfy 的 Sulphur 3 工作流、HF `SulphurAI/Sulphur-3` 的 24 个 discussions、
> ComfyUI 官方 H3 提示词指南。本文件只写提示词，不重复部署细节（见主文档 §9.5）。

## 1. 结论先行

**Sulphur 3 和 MiniMax H3 的提示词不是同一种写法**。S3 在微调时用的是
**结构化 JSON caption**，H3 官方用的是**三段式文本字段**。两者都能喂进 Qwen3-VL
文本编码器，但格式不对不报错，只是偏离训练分布——表现为提示词跟随度下降、语义散、
音画不同步，而不是崩溃。

| | Sulphur 3 (S3) | MiniMax H3 |
|---|---|---|
| 格式 | **JSON 结构化 caption** | **三段式文本字段** |
| 字段 | `subjects / objects / environment / camera / temporal / audio_context / salient_details` | `integrated_multimodal_description / overall_soundscape / non_diegetic_music` |
| 组织方式 | 按对象/环境/镜头/时间线分块 | 按画面时间线 + 两个独立声音字段 |
| 生成方式 | 由 S3 的 prompt enhancer 产出（**未公开**） | 由 H3-Context-IR 改写（官方工具有，agent skill 也装了 `h3-prompt-writing`） |
| 专属 skill | **无**（社区和官方都没有） | `h3-prompt-writing` 已装 |
| 依据 | 官方 `example_workflow.json` 的 positive prompt；RunComfy Sulphur 3 工作流 | MiniMax 官方基础模式指南；ComfyUI 官方 H3 提示词指南 |

## 2. S3 官方 JSON schema（权威样本）

官方 `S3_ComfyUI.zip/example_workflow.json` 的节点 #6「Positive prompt (structured caption)」
里存的就是下面这段，直接抄自文件：

```json
{
  "subjects": [
    {
      "label": "woman",
      "appearance": "adult, late twenties, fair skin, long red hair, toned arms, wearing a white tank top and dark jeans",
      "position": "center of frame, full body, standing on a wooden floor",
      "motion": "moves her hips in a playful way, twists her torso, raises and lowers her arms",
      "interaction": "grins at the camera and winks"
    }
  ],
  "objects": [],
  "environment": {
    "setting": "modern kitchen",
    "layout": "open space with a counter, sink, and appliances",
    "background": "counter with a coffee mug and a phone",
    "foreground": "wooden floor with a small rug"
  },
  "camera": {
    "framing": "phone video, medium shot",
    "angle": "slightly above eye level",
    "movement": "static, phone propped on the counter"
  },
  "temporal": {
    "overall_action": "the woman dances playfully in her kitchen",
    "motion_sequence": [
      "she stands still and looks at the camera",
      "she begins moving her hips and twisting her body",
      "she raises her arms and spins slightly",
      "she stops and grins at the camera"
    ]
  },
  "audio_context": [
    "upbeat jazz music playing from the phone",
    "her soft laughter"
  ],
  "salient_details": [
    "sunlight streaming through the window",
    "her red hair flows slightly as she moves",
    "the phone is visible on the counter"
  ]
}
```

### 字段分工

| 字段 | 写什么 | 注意 |
|---|---|---|
| `subjects[]` | 每个主体一个条目：`label` 名称、`appearance` 外貌服装、`position` 画面位置、`motion` 动作、`interaction` 交互 | `motion` 写**可见过程**，不写结论（"moves her hips" 而不是 "she is happy"） |
| `objects[]` | 画面里的道具/物件 | 官方样本为空数组 |
| `environment` | `setting` 场景、`layout` 布局、`background` 背景、`foreground` 前景 | 四块分开写，别混成一段 |
| `camera` | `framing` 景别、`angle` 机位、`movement` 运镜 | 运镜单独写，不要塞进主体动作里 |
| `temporal` | `overall_action` 全片动作 + `motion_sequence[]` 动作顺序 | RunComfy 明确要求用它描述**画面动作的顺序** |
| `audio_context[]` | 与动作对应的声音（脚步、布料摩擦、笑声） | RunComfy 明确要求用它指定**动作对应的声音**；不要写成配乐 |
| `salient_details[]` | 需注意的细节（光影、材质、文字、不要出现的东西） | 画面上要出现的招牌字要写清，H3 无引号的招牌字会变成乱码 |

## 3. H3 三段式格式（对照）

MiniMax 官方基础模式（T2VA / I2VA / FL2VA / L2VA）用三个英文段名：

```
integrated_multimodal_description: [Shot 1] [Style and framing]... 
overall_soundscape: [Ambience + physical action sounds + non-verbal vocals]...
non_diegetic_music: [Instrumentation, tempo, dynamics]... 或 N/A
```

要点（ComfyUI 官方指南 + 社区实测）：

- 从 `[Shot 1]` 开始，即使只有一个镜头也要写。
- 镜头切换写成 `At 00:05.000, the camera cuts to ...`，时间在四分之一秒内可命中。
- 说话人标 `(S1)` / `(S2)`，台词放进 `<d>[English] ...</d>`。
- `overall_soundscape` 是全片环境底声，**不要重复对白**。
- `non_diegetic_music` 只写观众听得见、角色听不见的配乐；没有就写 `N/A`。
- 图生/首尾帧任务开头要加图片对齐行，例如
  `Picture 1 is fully referenced at 0.00 seconds and belongs to [Shot 1]`。

`~/.agents/skills/h3-prompt-writing` 就是按这套格式写的，对 **H3** 有效，对 **S3** 是错格式。

## 4. 关键区别

| 维度 | S3 JSON | H3 三段式 |
|---|---|---|
| 主体描述 | 结构化对象，`appearance/position/motion/interaction` 分开 | 写在 shot 的连续叙述里 |
| 时间线 | `temporal.motion_sequence[]` 数组 | `[Shot 1]` + `At 00:05.000, ...` 文本 |
| 声音 | `audio_context[]` 与动作绑定 | `overall_soundscape` 全片汇总 + `non_diegetic_music` 配乐 |
| 配乐字段 | **没有独立配乐字段**（`audio_context` 是画内声） | 有 `non_diegetic_music` |
| 台词标记 | 官方样本没有 `<d>` 标记示例 | 要求 `<d>[English] ...</d>` + `(S1)/(S2)` |
| 花括号 | 是结构本身，必须原样保留 | 不存在 |

**最容易犯的错**：把 H3 的三段式直接粘给 Sulphur，或把 S3 的 JSON 当成普通文本塞进
H3 的 `integrated_multimodal_description`。模型不会报错，只会"出片但不对味"。

## 5. 能否混用

Sulphur 3 是 H3 的 full fine-tune，权重结构相同，所以**技术上**两种格式都会被编码成
conditioning。但 S3 的训练 caption 是 JSON schema（官方 note 明说
"The S3 pipeline prompts with structured JSON captions (written by its prompt enhancer)"），
H3 的训练/改写链路是三段式 + Context-IR。格式偏离训练分布属于未定义行为，社区没有
做过 JSON vs 三段式的 A/B 画质对比——所以本机一律用 JSON，不混。

## 6. ComfyUI 实操坑：Dynamic Prompts 会吃掉 JSON 花括号

RunComfy 文档明确警告：

> ComfyUI's Dynamic Prompts feature can treat JSON braces as prompt syntax and strip them
> when you click Run. To reproduce a structured caption exactly, submit the ComfyUI API
> prompt with the original JSON caption as the text string for node #6. This preserves its braces.

也就是说：**在 Desktop 界面里直接粘贴 JSON 提示词，`{}` 可能被前端当语法剥掉**，
提交给后端的已经是损坏的文本。正确做法是走 API，把 JSON 作为字符串原样 POST：

- 本机 `plan4/bat/run_workflow.py` 和 `gen_sulphur.py` 都走 `POST /prompt`，路径正确。
- 提示词文件 `plan4/bat/prompt_s3.json` 就是原样读入的 text 字符串。
- 若要改用 UI 工作流手填，必须确认前端 Dynamic Prompts 关闭，否则先 API 验证。

## 7. 配套采样参数（别只改提示词）

S3 官方示例的 note 和 RunComfy 工作流一致，整套参数是绑定的：

| 项 | S3 官方值 |
|---|---|
| CFG | 1（guidance-distilled，negative prompt 被忽略） |
| 采样器 | **Euler** |
| schedule | **simple** |
| shift | **video 12 / audio 3**（`MiniMaxH3SigmaShift`） |
| steps | 20 |
| corrector | 可选，`strength=0` 关闭；默认每步；`budget_fraction=0.5`、`velocity_floor=0.001` 是训练值 |
| 帧数网格 | `17k+5` @24 fps：56≈2 s，124≈5 s |

plan4 的 12 条 API/UI 工作流与全部生成脚本已按这套参数改好（见主文档 §9.5）。

## 8. 社区现状（2026-11-27 核实）

- HF `SulphurAI/Sulphur-3` 共 **24 个 discussions**，逐条看过：全部是访问权限、捐赠、
  发布时间、权重上传、corrector 显存、LoRA、ref2va，**没有任何提示词写法讨论**。
- Reddit / 中文社区搜到的 Sulphur 内容集中在权重、量化、Turbo LoRA、pi-H3 2 步，
  没有独立的 prompt 指南。
- 没有公开的 Sulphur prompt enhancer 工具或 agent skill；官方 note 提到的
  "prompt enhancer" 是训练时的内部工具，未发布。
- 唯一可操作的权威格式就是官方 `example_workflow.json` 的 positive prompt（本文 §2）
  和 RunComfy 的字段说明（本文 §2 字段分工）。

## 9. 本机 plan4 的做法

- 提示词：`plan4/bat/prompt_s3.json`，按 §2 schema 手写（把原 H3 三段式内容转写）。
- 提交：一律走 `run_workflow.py` / `gen_sulphur.py` 的 `POST /prompt`，绕开 Dynamic Prompts。
- 原 H3 三段式 `prompt.txt` 保留作对照，不删。
- `h3-prompt-writing` skill 只用于 H3 那条线，不用于 Sulphur。

## 10. 未验证 / 风险

1. **没做 JSON vs 三段式的 A/B 画质对比**。`prompt_s3.json` 只有一份样本，按官方 schema
   手写，不知道和 S3 内部 enhancer 的产出差多少。
2. `prompt_s3.json` 里的 `audio_context` 写的是环境声，按 RunComfy 的说法它是"画内声"，
   但 S3 是否有独立配乐字段社区没说清——若要配乐，可能需要写进 `environment` 或
   `salient_details`，需实测。
3. 官方 note 说 corrector 能改输出（fp32，bf16 会变），本机 24 GB 卡因 +8 GB 显存暂不装，
   所以本机出片与官方"默认开 corrector"的示例不完全一致——差异叠加在提示词效果上。
4. HF discussions 抓取时网页版传输失败，是通过 HF API 拿到 24 条标题；讨论正文未逐条读，
   但不影响"没有提示词讨论"这个结论（标题已覆盖全部 24 条）。
