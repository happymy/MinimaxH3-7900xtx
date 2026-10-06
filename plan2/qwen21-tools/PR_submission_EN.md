# English version: supplementary material for comfy-kitchen issue #226

> Intended as a follow-up comment on https://github.com/Comfy-Org/comfy-kitchen/issues/226.
> Narrows the bug down to specific lines and commits.

---

## Addition: token-length boundary pinned to exactly 64 (the attention kernel's tile width)

I reproduced this on an identical setup (RX 7900 XTX / RDNA3 gfx1100 / ROCm / comfy-kitchen 0.2.36 / Qwen-Image 2.1) and was able to pin the failure to a precise boundary.

### Key finding: an exact token-length threshold, boundary = 64

Same Chinese prompt, progressively lengthened, everything else held constant:

| total tokens | surviving after mask | output | verdict |
|---|---|---|---|
| 78 | **64** | 1054 KB | ✅ correct |
| 82 | **68** | 1696 KB | ❌ corrupted |
| 86 | 72 | 1714 KB | ❌ corrupted |
| 94 | 80 | 1704 KB | ❌ corrupted |

(The tokenizer mask drops a 14-token system turn, so "78 tokens" means only 64 actually reach attention.)

**All four are correct with `--use-ck-attention` disabled** (1046 / 1042 / 923 KB), confirming ck is the only variable.

**The boundary lands exactly on 64**, matching hard-coded thresholds in `comfy_kitchen`:

```python
# comfy_kitchen/sage_attention.py
CTA_K = 64                       # L21

# _prepare_attn_mask
L82-90   and 64 < attn_mask.shape[3] <= 2048          -> fused path
L96-102  attn_mask.shape[-1] <= (64 if _hip_backend is not None else 1024)
                                              -> return mask unchanged
L105-113 stride(2) != 0 and shape[2] > 1            -> dense mask path
L114-132 else key mask, tile_k = _SAGE_CTA_K        -> sage_prepare_key_mask
```

```python
# comfy_kitchen/backends/hip/__init__.py
_SAGE_CTA_K = 64                  # L2824

def _sage_can_fuse_dense_mask(attn_mask):     # L3038
    ...
    and 64 < attn_mask.shape[3] <= 2048        # L3044, same threshold
```

`<=64` and `>64` take **entirely different code paths**. This looks like it could be an off-by-one or a tile-local mask application issue at the tile boundary.

### 5-config flag sweep

Same prompt, same seed; restarted per group and **verified the effective flags via CIM** to rule out editing the wrong file:

| group | fp16-intermediates | ck-attention | upcast | artifact | verdict |
|---|---|---|---|---|---|
| BASE | yes | yes | - | 1689 KB | corrupted |
| A | - | yes | - | 1698 KB | corrupted |
| D | yes | yes | yes | 1694 KB | corrupted |
| B | yes | - | - | 1043 KB | correct |
| C | - | - | - | 1043 KB | correct |

Pixel-level clustering: within-group mean diff 0.61-0.98 (<1% of pixels),
**cross-group mean diff 50.8 (98% of pixels changed)**.

Noise floor: two same-seed reruns differ by 0.88 mean, so <1.0 is noise and 50.8 is a real effect.

### Version bisect: introduced in 0.2.36

`sage_attention.py` was modified **exactly twice** after 0.2.35 (2026-09-17), both on 2026-09-27:

| commit | change |
|---|---|
| `690f7659` | Optimize int8 attention with mask. (#207) - `sage_attention.py` +75/-51 |
| `c8c7825f` | Int8 attention optimizations. (#208) - `int8_attn.hip` +396/-59 |

Both landed **only in 0.2.36** (2026-09-29). This matches "it worked before": 0.2.35 used the pre-#207 mask path.

The later `19ea55b9` (#214) is an 8-line change that fixes **NaN**, not correctness.

### Ruled out

- Corrupt model files (4x SHA256 match)
- Quantization format (Q4_K_M corrupts identically)
- VRAM / offload pressure
- `--fp16-intermediates` (unrelated)
- `--force-upcast-attention` (unrelated)
- `ModelSamplingAuraFlow(shift=3.1)` (no effect)
- Raising cfg (still corrupted at cfg 4.0)

### One note: this may not be Qwen-specific

If the tile-boundary handling is at fault, any model using a **short key mask** (shape `[1,1,1,K]`) could be affected.

For example the banded attention in #177 for MiniMax H3 uses a per-key additive bias. In my ck vs non-ck comparison H3 gives correlation 0.99786 with mean pixel diff 2.33/255. H3 generation is bit-exact on reruns under identical conditions (124/124 frames sha256-identical, SSIM = 1.000000), so that difference is not noise. It is far smaller than the Qwen corruption, but it may not be intended behavior.

Mentioning it in case it is related. Not certain that it is.

### Environment

```
GPU:           AMD Radeon RX 7900 XTX 24GB (RDNA3 / gfx1100)
Backend:       ROCm 7.2.1
PyTorch:       2.9.1+rocm7.2.1
ComfyUI:       0.38.0 (fb2315f11db0ebfaafa9099a5df5227dc6bb42bc)
comfy-kitchen: 0.2.36
triton:        not installed (ck falls back to HIP/eager)
Model:         qwen-image-2.1-UC-Q4_K_M.gguf / Q8_0.gguf  (both corrupt)
TE:            qwen3vl_8b_int8_convrot.safetensors
VAE:           qwen_image_2.1_vae_bf16.safetensors
Sampling:      euler / simple / 25 steps / cfg 1.0 / 1024x1024
```

### Reproduction

```bat
python main.py --windows-standalone-build --enable-dynamic-vram ^
  --disable-pinned-memory --fp16-intermediates --disable-smart-memory ^
  --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
```

Removing `--use-ck-attention` restores correct output with every other argument unchanged.

Happy to provide comparison images or raw data if useful.
