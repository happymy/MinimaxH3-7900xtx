# H3 `--use-ck-attention` A/B 对照测试（2026-10-02 实测）

对应 `Plan.md §12.6` 待办第 1 条「一次 H3 ck / 非-ck 对照确认 DiT 主干可信度」的完整留档。

**结论一句话**：**H3 DiT 主干走 ck 安全**，端到端 **1.54x** 加速可用；差异是 int8 量化导致的系统性微差 + ck 侧一致更锐，**不是** Qwen-Image 2.1 那种崩坏。待办 1 已关闭。

先读 [`H3_ck_attention_AB测试报告.md`](H3_ck_attention_AB测试报告.md)（结论 + 设计 + 数据 + 踩坑记录）。

---

## 1. 来源与可复现性

| 项 | 值 |
|---|---|
| 实测工作区 | `D:\localAI\ComfyUI-last\plan\ck_ab_20261002\`（本目录为其入库副本） |
| 实测日期 | 2026-10-02 |
| ComfyUI | 0.38.0（`fb2315f1`） |
| 显卡 | AMD 7900 XTX（HIP） |
| 参数 | 864×480 / 5s = 124 帧 / 20 步 / cfg 1.0 / `res_multistep` + `simple` / seed 1234 |
| 唯一变量 | 启动 flag `--use-ck-attention`（两臂 flag 集合经程序化核对，差异仅此一项，见 `arm_flags.json`） |

⚠️ **脚本内含硬编码本机路径**，跨机复用须先改：
- `gen_h3_ck_ab.py` → `API = "http://127.0.0.1:8188"`
- `compare_frames.py` → `FFMPEG` 常量（WinGet 安装路径，换机/换版本必改）

## 2. 目录内容

### 报告与脚本

| 文件 | 说明 |
|---|---|
| `H3_ck_attention_AB测试报告.md` | **主报告**：结论 / 测试设计 / 5 组数据 / 机制解读 / 处置 / 踩坑记录 |
| `gen_h3_ck_ab.py` | A/B 探针。复刻 `plan\bat\multisegment_8b\gen_h3_multisegment-8b.py` 的图，**额外挂 `SaveImage` 输出无损 PNG**（原脚本末尾 `concat_segments()` 无论几段都会 libx264 重编码 CRF 23，会叠一层有损压缩） |
| `compare_frames.py` | 帧级比对工具：像素 sha256 / mean\|diff\| / Pearson r / PSNR / SSIM / 锐度 + 三联可视化。SSIM 用 `scipy.ndimage.gaussian_filter` 按 Wang et al. 2004 标准式自实现（本机无 skimage） |
| `run_nock_arms.bat` | no_ck 臂两轮（短 + 全长）驱动 |

### 原始数据

| 文件 | 说明 |
|---|---|
| `arm_flags.json` | 两臂启动 flag 留证（A_ck / B_nock 的完整命令行） |
| `run_ck_r1/r2/ck_full/nock_s/nock_full.json` | 5 次运行清单：prompt_id / 参数 / prompt sha256 / 耗时 / 输出文件 |
| **`MAIN_ck_vs_nock_124f_metrics.json`** | **主结果**，124 帧逐帧指标 + 汇总 |
| `p1_ck_determinism_metrics.json` | 噪声地板验证：ck 臂同参数连跑两次，39/39 帧像素 sha256 全等 |
| `p3_ck_vs_nock_short_metrics.json` | 4 步短跑对照（差异更大，用于观察步数依赖） |
| `selftest_identical_metrics.json` | 量具自检 · 恒等路径（同 mp4 两次 → 107/107 全等） |
| `selftest_perturbed_metrics.json` | 量具自检 · 灵敏度路径（亮度 +1/255 → mad=1.23 / r=0.99968 / SSIM=0.9931） |

### 未入库（可由脚本重新生成）

| 项 | 位置 |
|---|---|
| 无损 PNG 帧 365 张 | `D:\...\ComfyUI\output\ck_ab\`（`ck_r1_*` / `ck_r2_*` / `ck_full_*` / `nock_s_*` / `nock_full_*`） |
| 可视化对照图 | 实测工作区 `vis_fullframes.png`、`*_worst_full.png`、`*_worst_zoom*.png` |
| mp4 | 同上 + `ComfyUI\output\video\` |
| ComfyUI 启动日志 | 实测工作区 `comfy_nock.log` / `.err.log`、`nock_arms.log` |

## 3. 复用前必读的两个工具坑

复用 `compare_frames.py` 或照抄其逻辑时注意——**这两点都曾导致假阳性结论**：

1. **sha256 必须哈希像素数组，不能哈希 PNG 文件字节。** 同内容、不同 PNG 编码元数据的两个文件字节不同但像素完全一致；用文件哈希会把「完全确定性」误判成「每帧都有差异」。

2. **PNG 序列前缀要用正则 `^(.*)_\d+_\.png$` 提取，不能用 `rsplit("_", 1)`。** 后者会把帧号当前缀（`ck_r1_00001_`），glob 只命中 1 帧 —— 初版正是因此在只比到 1 帧的情况下宣布「39/39 通过」，结论作废重做。

另：ffmpeg ≥ 5 已移除 `-vsync`，正确写法是 `-fps_mode passthrough`。
