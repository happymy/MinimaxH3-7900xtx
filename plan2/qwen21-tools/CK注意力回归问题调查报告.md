# Comfy Kitchen INT8 注意力回归问题调查报告

> **本文件是副本。** 权威版本为 `plan\CK注意力回归问题调查报告.md`（350 行）。
> 2026-10-06 同步：把 §7.3 从「H3 DiT 侧存在未验证风险」更新为「✅ 已验证安全」，
> 依据是 `plan\ck_ab_20261002\` 的受控 A/B（864x480 / 5s=124帧 / 20步 / seed 1234，
> r=0.99533、SSIM=0.98849、mad=0.9125、锐度 ck 侧 +5.50%、端到端 1.54x）。
> 本目录（`plan2\qwen21-tools\`）是 Qwen-Image 2.1 侧的工具链与 flag 实测，
> §1~§6 的 Qwen 崩坏证据链同样以此为准。


**问题**：AMD RDNA3 (RX 7900 XTX) 上启用 `--use-ck-attention` 后，Qwen-Image 2.1 生成严重损坏
**定位结论**：comfy-kitchen 0.2.36 的 masked attention 重写引入，非配置问题
**报告日期**：2026-10-01
**受影响版本**：comfy-kitchen 0.2.36（2026-09-29 发布）
**关联上游 issue**：[Comfy-Org/comfy-kitchen#226](https://github.com/Comfy-Org/comfy-kitchen/issues/226)（open，0 评论）

---

## 1. 摘要

在 RX 7900 XTX（RDNA3 / gfx1100，ROCm）上，ComfyUI 0.38.0 + comfy-kitchen 0.2.36 使用
`--use-ck-attention` 时，Qwen-Image 2.1 输出严重损坏（绿色/紫色伪影、纹理破碎、结构崩坏），
但生成过程无任何异常抛出。

**仅切换注意力后端**（`--use-ck-attention` → 不带该参数），同一工作流、同一 seed、同一模型，
输出立即恢复正常。

经 5 组配置自动化对照实验 + token 长度二分 + 源码定位，确认：

| 结论 | 依据 |
|---|---|
| 唯一原因是 `--use-ck-attention` | 5 组 flag 对照，脏/干净图清晰二分（见 §3） |
| `--fp16-intermediates` 无关 | A≈BASE，B≈C |
| `--force-upcast-attention` 无关 | D≈BASE |
| 存在**精确的 token 长度边界** | 69 CJK 字正常，74 字损坏（见 §4） |
| 边界 = **64**，即注意力核的 tile 宽度 | `sage_attention.py` L98/L116，`_SAGE_CTA_K = 64`（见 §5） |
| 由 comfy-kitchen **0.2.36** 引入 | 0.2.35 之后仅 #207/#208 改过 masked attention（见 §6） |

**没有修复版本可用**：0.2.36 即 PyPI 最新，0.2.37 不存在。

---

## 2. 环境

| 项 | 值 |
|---|---|
| GPU | AMD Radeon RX 7900 XTX 24GB |
| 架构 | RDNA3 / gfx1100 |
| OS | Windows 11 |
| Backend | ROCm 7.2.1 |
| PyTorch | 2.9.1+rocm7.2.1 |
| ComfyUI | 0.38.0 (`fb2315f11db0ebfaafa9099a5df5227dc6bb42bc`) |
| comfy-kitchen | **0.2.36**（2026-09-29T00:47:15Z 发布） |
| triton | 未安装（ck 回退 HIP/eager 后端） |
| 扩散模型 | `qwen-image-2.1-UC-Q4_K_M.gguf` / `Q8_0.gguf` |
| 文本编码器 | `qwen3vl_8b_int8_convrot.safetensors` |
| VAE | `qwen_image_2.1_vae_bf16.safetensors` |
| 采样 | euler / simple / 25 步 / cfg 1.0 / 1024×1024 |

复现命令（干净对照只需去掉 `--use-ck-attention`）：

```bat
python main.py --windows-standalone-build --enable-dynamic-vram ^
  --disable-pinned-memory --fp16-intermediates --disable-smart-memory ^
  --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
```

---

## 3. 排除实验：5 组 flag 对照

同一 prompt（T82）、同 seed，逐组重启 ComfyUI 并**从 CIM 校验实际生效的 flag**（防止改错文件）。
产物像素级互比。

| 组 | fp16-intermediates | ck-attention | upcast-attention | 产物大小 | 判定 |
|---|---|---|---|---|---|
| BASE | ✅ | ✅ | — | 1689 KB | ❌ 脏 |
| A | — | ✅ | — | 1698 KB | ❌ 脏 |
| D | ✅ | ✅ | ✅ | 1694 KB | ❌ 脏 |
| B | ✅ | — | — | 1043 KB | ✅ 干净 |
| C | — | — | — | 1043 KB | ✅ 干净 |

**聚类分析**：

| 对比 | 平均像素差 | 变化像素占比 |
|---|---|---|
| BASE ↔ A | 0.69 | < 1% |
| BASE ↔ D | 0.98 | < 1% |
| A ↔ D | 0.75 | < 1% |
| B ↔ C | 0.61 | 0.1% |
| **跨簇（脏组 ↔ 干净组）** | **50.8** | **98%** |

结论：`BASE/A/D` 聚成一簇（都开 ck，都脏），`B/C` 聚成一簇（都不开 ck，都干净）。
跨簇差异 50.8 / 98% 像素变化，是数量级级别的信号。

> **噪声地板**：同 seed 复跑两次，平均像素差 0.88（max 69）。
> 因此**平均差 < 1.0 视为噪声**，本实验的组内 0.61–0.98 全部落在噪声内，组间 50.8 是真实效应。

**判定**：ck 是唯一变量。`--fp16-intermediates` 与 `--force-upcast-attention` 均无关。

### 产物文件大小是可靠指纹

| 类别 | PNG 大小 |
|---|---|
| 干净 | 937–1043 KB |
| 损坏 | 1689–1745 KB |

---

## 4. Token 长度二分：存在精确边界

逐步加长同一段中文 prompt，其余参数不变：

| 标记 | CJK 字符 | token | 输出 | 判定 |
|---|---|---|---|---|
| T78 | 69 | 78（掩码后存活 64） | 1054 KB | ✅ 正常 |
| **T82** | **74** | **82（存活 68）** | **1696 KB** | ❌ **损坏** |
| T86 | — | 86（存活 72） | 1714 KB | ❌ 损坏 |
| T94 | — | 94（存活 80） | 1704 KB | ❌ 损坏 |

同一组 token 在**关闭 ck** 后全部正常（`ATTN_T78/T82/T86` = 1046 / 1042 / 923 KB）。

**边界精确落在 64**。注意 tokenizer 掩码会丢掉 system turn（14 token），
所以「78 token」实际只有 64 个参与注意力——**真正的阈值是注意力核的 tile 宽度 64，不是 prompt 字符数**。

> ⚠️ **这一点极易被误诊**：早期怀疑的「78 token / 74 CJK 字上限」完全是核内 block size 的伪像。
> 任何未来出现「长度上限」症状的场景，都应**先查启动 flag**。

### 补充：其他参数均无法规避

| 实验 | T78 | T82 | 结论 |
|---|---|---|---|
| 加 `ModelSamplingAuraFlow(shift=3.1)` | 1050 KB 正常 | 1726 KB 损坏 | shift 不影响 |
| cfg 1.0 → 4.0 | 739 KB 正常 | 1286 KB 损坏 | 提高 cfg 无法规避 |

---

## 5. 源码定位：64 的出处

`comfy_kitchen/sage_attention.py`：

```python
L21   CTA_K = 64
L22   LARGE_CTA_K = 128

# _prepare_attn_mask 三条分支
L82-90   and 64 < attn_mask.shape[3] <= 2048        → 融合路径，原样返回
L96-102  attn_mask.shape[-1] <= (64 if _hip_backend is not None else 1024)
                                              → 原样返回 mask，不预处理
L105-113 stride(2) != 0 and shape[2] > 1          → 打包 dense mask
L114-132 否则走 key mask，tile_k = _SAGE_CTA_K     → sage_prepare_key_mask
```

`comfy_kitchen/backends/hip/__init__.py`：

```python
L2824  _SAGE_CTA_K = 64

def _sage_can_fuse_dense_mask(attn_mask):
    ...
    and 64 < attn_mask.shape[3] <= 2048            # 同一阈值
```

`64` 在两处独立出现，**是 HIP 注意力核的 tile 宽度**。`≤64` 与 `>64` 走**完全不同的代码路径**。
实测 T78（存活 64 token）走第一条，T82（存活 68 token）走第二条——正好跨过。

Qwen-Image 2.1 的 mask 构造（`comfy/ldm/qwen_image/model.py` L176-178）：

```python
if encoder_hidden_states_mask is not None:
    attn_mask = torch.zeros((batch_size, 1, seq_txt + seq_img), ...)
    attn_mask[:, 0, :seq_txt] = encoder_hidden_states_mask
```

经 `attention.py` L629-633 升维为 4 维 `[B,1,1,L]` 后传入 ck。
`seq_txt` 的变化直接改变 mask 内容与 tile 数（`(L+63)//64`）。

---

## 6. 版本定位：0.2.36 引入的回归

`sage_attention.py` 在 0.2.35 之后**仅被修改过两次**，均在 2026-09-27：

| 提交 | 说明 | 规模 |
|---|---|---|
| `690f7659` | Optimize int8 attention with mask. (#207) | `sage_attention.py` +75/−51；`int8_attn.hip` +85/−18 |
| `c8c7825f` | Int8 attention optimizations. (#208) | `sage_attention.py` +46/−13；`int8_attn.hip` **+396/−59** |

版本时间线：

```
0.2.34   2026-09-15
0.2.35   2026-09-17
  ├─ 690f7659  2026-09-27  Optimize int8 attention with mask (#207)   ← 引入
  ├─ c8c7825f  2026-09-27  Int8 attention optimizations (#208)         ← 引入
  ├─ d73ec168  2026-09-27  Fix performance regression (仅 CUDA 侧)
  ├─ 0432be9a  2026-09-28  int8 attention optimization (仅 CUDA 侧)
  ├─ b54f8512  2026-09-28  Support larger shapes in cuda int8 attention (仅 CUDA 侧)
0.2.36   2026-09-29   ← 打包了上述全部改动
  └─ 19ea55b9  2026-09-29  Fix NaN on older AMD with -inf masks (#214)  ← 只修 NaN，+8 行
```

**#207/#208 只进了 0.2.36**。这解释了 issue #226 报告者「以前能用」——
他此前用 0.2.35，走的是 #207 之前的旧 mask 路径。

后续 `19ea55b9`（#214，gfx1103）只改了 8 行，修的是 **NaN**，不是正确性。

**PyPI 版本核对**：

```
0.2.36  上传 2026-09-29T00:47:15Z   ← 已安装，且是最新
0.2.37+  不存在
```

**结论：不存在可用的修复版本。**

---

## 7. 影响范围

### 7.1 已确认受影响

- **Qwen-Image 2.1**（本报告）。文本流长度跨过 64 token 即损坏。

### 7.2 文本编码器不受影响

H3 的 conditioning 编码器是 **Qwen3-VL-32B（截断 50 层）**（`comfy/sd.py` 注释）。
其注意力获取点 `comfy/text_encoders/qwen_vl.py` L418：

```python
optimized_attention = optimized_attention_for_device(pixel_values.device, mask=False, small_input=True)
```

而 `attention.py` L940-945：

```python
def optimized_attention_for_device(device, mask=False, small_input=False):
    if small_input:
        ...
        return attention_basic      # ← 函数最开头就 return
```

**`small_input=True` 提前返回 `attention_basic`（纯 einsum），永远到不了 L913 的 ck 分支。**
且 `qwen_vl.py` 不向注意力传任何 mask（用 cu_seqlens 变长拼接）。

→ **任何模型的文本编码器都不受此 bug 影响。**

### 7.3 ✅ 已验证安全：H3 DiT 主干（2026-10-02 受控 A/B）

`attention.py` L913 的 ck 覆盖是全局的（无按模块区分），只有显式调用 `optimized_attention`
的模块才吃到。对 H3：

| 部件 | 是否走 ck |
|---|---|
| 文本编码器 Qwen3-VL | **否**（见 7.2） |
| DiT 主干 `ldm/minimax/model.py` | **是** ← 2.70x 加速来源 |
| VAE `ldm/minimax/vae.py` L313 | 是（独立调用，仅 int8 量化权重时） |

DiT 使用的带状 mask（`[1,1,1,K]`，raised-cosine 衰减偏置，见 issue #177 描述）
**确实命中 #207/#208 重写的路径**。

**已测数据**：同 seed 1234、8 步、1280×736×107f，ck vs 非 ck：

- 采样 106.0 → 39.26 s/it（**2.70x**）
- 峰值显存 21.37 → 20.97 GiB（**−0.40**）
- 全 107 帧逐帧比对：**相关系数 0.99786**、平均像素差 2.33/255

**这个差异不是噪声。** 同一份 plan 文档 L855 记录了 H3 的噪声地板：
同 TE 复跑 **124/124 帧 sha256 完全一致，SSIM = 1.000000，PSNR = inf**——
即 H3 生成是**位级确定**的，运行间噪声为零。

> 位级确定 vs 0.99786 相关性 → ck 确实改变了输出。
> 差异集中在细节（锐度 +4.05%、平坦区噪声 −5%）而非整体加噪，量级远小于 Qwen 的崩坏，
> 但**是否为预期行为、还是同一正确性缺陷的轻微表现，当时无法判定**。

**2026-10-02 已判定**（甜点档 864×480 / 5s=124 帧 / 20 步 / seed 1234 的受控 A/B，两臂 flag 集合经程序化核对仅差 `--use-ck-attention`）：

| 判据 | 崩坏应有 | 实测 | 判定 |
|---|---|---|---|
| 高饱和绿/紫伪影像素占比 | 显著 > 0 | **两臂均 0.000%** | ❌ 无 |
| 误差空间形态 | 局部团块 | mad 变异系数 **0.146**，均匀弥散 | ❌ 无 |
| 误差频率分布 | 低频块状 | 粗糙度比 **0.54–0.57**，高频为主 | ❌ 无 |
| 100% 裁切目视复核 | 纹理断裂 / 肢体变形 / 假边缘 | **逐项无损坏**，锐化属「细节更清楚」 | ❌ 无 |
| 步数依赖 | 步数越多越坏 | 4 步 r=0.928 → **20 步 r=0.995（收敛）** | ❌ 反向 |

主结果 **r = 0.99533、SSIM = 0.98849（124 帧全部 > 0.98）、mad = 0.9125、锐度 ck 侧 +5.50% ± 2.10%（124 帧全部同向）、端到端 411.5s → 633.4s（1.54x）**。

**结论：H3 文本侧安全（源码核实）+ H3 DiT 主干安全（实测确认），H3 可继续使用 ck。差异性质是 int8 量化导致的系统性微差（落在另一个同样合法的采样结果上），不是 Qwen 那种崩坏。Qwen-Image 2.1 的禁用结论不变。**

> ⚠️ 边界：仅覆盖 comfy-kitchen 0.2.36 + Q4_K_M DiT / 8B fp8 TE + 864×480/20 步 + 单 seed 1234。升级 comfy-kitchen、换量化档位或换分辨率后须重跑。完整证据、原始指标与踩坑记录见 **`ck_ab_20261002\`**。

---

## 8. 缓解措施

### 8.1 立即可用（已实施）

分两个启动脚本，按模型切换：

| 用途 | 启动脚本 |
|---|---|
| Qwen-Image 2.1 | `run_amd_gpu_no_ck_attention.bat`（去掉 `--use-ck-attention`） |
| MiniMax H3 | `run_amd_gpu_enable_dynamic_vram.bat`（保留 `--use-ck-attention`） |

两个脚本除 ck 开关外**完全一致**，保证 A/B 可比。

### 8.2 已排除的规避手段

以下均**实测无效**，不必重复尝试：

- `--fp16-intermediates`（无关）
- `--force-upcast-attention`（无关）
- `ModelSamplingAuraFlow(shift=3.1)`（对齐官方 blueprint，但不影响本 bug）
- 提高 cfg（4.0 仍损坏）
- 缩短 prompt 到 64 token 以内（可行但限制创作，且边界是核参数不是模型限制）

### 8.3 待办

1. 用一次 H3 ck / 非-ck 对照确认 DiT 主干可信度
2. 关注 #226 修复进展
3. 若 #226 长期无响应，考虑向 #226 补充本文档的 token 边界定位数据——
   精确到 64 tile 宽度有助于上游定位到具体 commit

---

## 9. 完整排除清单

以下均已单独验证，**不是**本问题的原因：

| 假设 | 排除依据 |
|---|---|
| 模型文件损坏 | 4× SHA256 校验一致 |
| 量化格式（Q8_0） | Q4_K_M 同样损坏 |
| 显存 / offload 压力 | 同配置下仅切 flag 即恢复 |
| PE 惰性分支 | 已单独验证 |
| tokenizer mask | `probe_tokens.py` 证明仅丢弃 system turn |
| token 长度上限 | **撤回**：系核内 block size 伪像，见 §4 |
| 缺少 shift 3.1 | 加了仍损坏，见 §4 |
| cfg = 1.0 | cfg 4.0 仍损坏 |
| ComfyUI 自身 bug | 0.2.35 时代正常（据 #226 报告者） |

---

## 10. 附：证据文件

| 文件 | 说明 |
|---|---|
| `qwen21-tools/flag_sweep.py` | 5 组配置自动化对照驱动（按 `main.py` 定位 PID，从 CIM 校验实际 flag，生成对照图） |
| `qwen21-tools/flag_sweep_sheet.png` | 5 组 T82 渲染对照图（带标注） |
| `qwen21-tools/probe_tokens.py` | 证明 tokenizer mask 只丢弃 system turn |
| `qwen21-tools/add_shift_all.py` | 为所有 Qwen 工作流插入 `ModelSamplingAuraFlow(shift=3.1)` |
| `qwen21-tools/make_q8_set.py` | 生成 Q8_0 版工作流副本 |
| `output/SWEEP_{BASE,A,D,B,C}_T82_00001.png` | 5 组对照产物 |
| `output/LEN_{T78,T82,T86,T94}_00001.png` | token 长度二分产物 |
| `output/ATTN_{T78,T82,T86}_00001.png` | 关闭 ck 的同组对照（全部正常） |
| `output/SHIFT_{T78,T82}_00001.png` | 加 shift 3.1 后（无效） |
| `output/CFG4_{T78,T82,T86}_00001.png` | cfg 4.0（无效） |
| `output/ACCEPT_{0033,V0full}_00001.png` | 验收：100 字 / 101 token 完整 prompt 修复后正常 |
