# 中文版：提交到 comfy-kitchen issue #226 的补充材料

> 用途：贴到 https://github.com/Comfy-Org/comfy-kitchen/issues/226 作为补充评论。
> 定位到具体代码行与提交，可直接帮助上游缩小范围。

---

## 补充：token 长度边界精确定位到 64（注意力核 tile 宽度）

我在完全相同的环境下复现了这个问题（RX 7900 XTX / RDNA3 gfx1100 / ROCm / comfy-kitchen 0.2.36 / Qwen-Image 2.1），并且把边界精确定位到了代码。

### 关键发现：存在精确的 token 长度阈值，边界 = 64

同一段中文 prompt 逐步加长，其余参数全部不变：

| token 总数 | 掩码后存活 | 输出 | 判定 |
|---|---|---|---|
| 78 | **64** | 1054 KB | ✅ 正常 |
| 82 | **68** | 1696 KB | ❌ 损坏 |
| 86 | 72 | 1714 KB | ❌ 损坏 |
| 94 | 80 | 1704 KB | ❌ 损坏 |

（tokenizer 掩码会丢弃 14 token 的 system turn，所以 78 token 实际只有 64 个参与注意力）

**关闭 ck 后这四组全部正常**（1046 / 1042 / 923 KB），确认 ck 是唯一变量。

**边界精确落在 64**，与 `comfy_kitchen` 中的硬编码阈值一致：

```python
# comfy_kitchen/sage_attention.py
CTA_K = 64                       # L21

# _prepare_attn_mask
L82-90   and 64 < attn_mask.shape[3] <= 2048          → 融合路径
L96-102  attn_mask.shape[-1] <= (64 if _hip_backend is not None else 1024)
                                              → 原样返回 mask
L105-113 stride(2) != 0 and shape[2] > 1            → dense mask 路径
L114-132 否则 key mask，tile_k = _SAGE_CTA_K         → sage_prepare_key_mask
```

```python
# comfy_kitchen/backends/hip/__init__.py
_SAGE_CTA_K = 64                  # L2824

def _sage_can_fuse_dense_mask(attn_mask):     # L3038
    ...
    and 64 < attn_mask.shape[3] <= 2048        # L3044 同一阈值
```

`≤64` 与 `>64` 走的是**完全不同的代码路径**。这看起来像是 tile 边界处理上的 off-by-one 或 tile 内掩码应用问题。

### 5 组 flag 对照实验

同 prompt、同 seed，逐组重启并从 CIM 校验实际生效的 flag：

| 组 | fp16-intermediates | ck-attention | upcast | 产物 | 判定 |
|---|---|---|---|---|---|
| BASE | ✅ | ✅ | — | 1689 KB | ❌ |
| A | — | ✅ | — | 1698 KB | ❌ |
| D | ✅ | ✅ | ✅ | 1694 KB | ❌ |
| B | ✅ | — | — | 1043 KB | ✅ |
| C | — | — | — | 1043 KB | ✅ |

像素级聚类：组内平均差 0.61–0.98（<1% 像素），**跨组平均差 50.8（98% 像素变化）**。

噪声地板：同 seed 复跑两次平均差 0.88，因此 <1.0 为噪声，50.8 是真实效应。

### 版本定位：0.2.36 引入

`sage_attention.py` 在 0.2.35（2026-09-17）之后**仅被改过两次**，都在 2026-09-27：

| 提交 | 说明 |
|---|---|
| `690f7659` | Optimize int8 attention with mask. (#207) — `sage_attention.py` +75/−51 |
| `c8c7825f` | Int8 attention optimizations. (#208) — `int8_attn.hip` +396/−59 |

这两个提交只进了 **0.2.36**（2026-09-29）。这与「以前能用」一致——之前是 0.2.35，走 #207 之前的旧 mask 路径。

后续 `19ea55b9`（#214）只改了 8 行，修的是 **NaN**，不是正确性。

### 已排除

- 模型文件损坏（4× SHA256 一致）
- 量化格式（Q4_K_M 同样损坏）
- 显存 / offload 压力
- `--fp16-intermediates`（无关）
- `--force-upcast-attention`（无关）
- `ModelSamplingAuraFlow(shift=3.1)`（无效）
- 提高 cfg（4.0 仍损坏）

### 一点提醒：可能不止 Qwen

如果 tile 边界处理确实有问题，那么使用**短的 key mask**（`[1,1,1,K]` 形状）的模型也可能受影响。

比如 #177 里描述的 MiniMax H3 带状注意力——它的 mask 是每 key 一个加性偏置。我这边 H3 的 ck vs 非 ck 对照相关性是 0.99786、平均像素差 2.33/255。同样的条件下 H3 复跑是**位级确定**的（124/124 帧 sha256 一致，SSIM = 1.000000），所以这个差异不是噪声。量级远小于 Qwen 的崩坏，但可能不是预期行为。

供参考，不确定是否相关。

### 环境

```
GPU:        AMD Radeon RX 7900 XTX 24GB (RDNA3 / gfx1100)
Backend:    ROCm 7.2.1
PyTorch:    2.9.1+rocm7.2.1
ComfyUI:    0.38.0 (fb2315f11db0ebfaafa9099a5df5227dc6bb42bc)
comfy-kitchen: 0.2.36
triton:     未安装（ck 回退 HIP/eager）
模型:       qwen-image-2.1-UC-Q4_K_M.gguf / Q8_0.gguf  (两者均损坏)
TE:         qwen3vl_8b_int8_convrot.safetensors
VAE:        qwen_image_2.1_vae_bf16.safetensors
采样:       euler / simple / 25 步 / cfg 1.0 / 1024×1024
```

### 复现命令

```bat
python main.py --windows-standalone-build --enable-dynamic-vram ^
  --disable-pinned-memory --fp16-intermediates --disable-smart-memory ^
  --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
```

去掉 `--use-ck-attention` 即恢复正常，其余参数完全不变。

如果需要对照图或原始数据我可以提供。
