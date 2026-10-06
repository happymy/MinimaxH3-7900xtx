# `--use-ck-attention` corrupts Qwen-Image 2.1 output when the prompt exceeds 64 tokens

## Summary

ComfyUI's `--use-ck-attention` flag routes attention through Comfy Kitchen's
INT8 kernels. On this machine (AMD Radeon RX 7900 XTX, ROCm, comfy-kitchen
0.2.31) that kernel silently produces wrong results for Qwen-Image 2.1 once
the text conditioning stream crosses a 64-token boundary. The image renders,
but the prompt is effectively ignored and the output degrades into noise.

The failure is a hard cliff, not a gradual quality loss:

| prompt length | kept tokens | result |
|---|---|---|
| 69 chars / 78 tokens | 64 | clean |
| 74 chars / 82 tokens | 68 | corrupted |
| 80 chars / 86 tokens | 72 | corrupted |
| 100 chars / 101 tokens | 87 | corrupted |

Every corruption case was fixed by removing a single launch flag. No model,
sampler, or prompt change was involved.

## Steps to reproduce

1. Launch ComfyUI with `--use-ck-attention`:
   ```
   python main.py --windows-standalone-build --enable-dynamic-vram \
     --disable-pinned-memory --fp16-intermediates --disable-smart-memory \
     --reserve-vram 6 --disable-api-nodes --cache-none --use-ck-attention
   ```
2. Load `qwen-image-2.1-UC-Q4_K_M.gguf` with `qwen3vl_8b_int8_convrot` and
   `qwen_image_2.1_vae_bf16`.
3. Generate with this prompt (100 chars, 101 tokens, 87 surviving the template
   mask):
   ```
   11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。
   ```
4. Observe: corrupted output, prompt ignored.
5. Remove only `--use-ck-attention` and regenerate. Observe: correct output.

## Flag isolation

Five launch configurations were tested with an otherwise byte-identical
workflow (same prompt read back from the previous PNG's `tEXt` metadata, same
seed, cfg 1.0, steps 25, euler/simple, same unet). The images split into
exactly two equivalence classes, and the split falls precisely on
`--use-ck-attention`:

| config | `--fp16-intermediates` | `--use-ck-attention` | `--force-upcast-attention` | size | vs BASE |
|---|---|---|---|---|---|
| BASE | yes | yes | — | 1689 KB | — |
| A | no | yes | — | 1698 KB | max 99 / 0.9% |
| D | yes | yes | yes | 1694 KB | max 92 / 0.4% |
| B | yes | no | — | 1043 KB | max 241 / 98% |
| C | no | no | — | 1043 KB | max 241 / 98% |

Reading the table:

- **BASE, A, D are near-identical to each other** (mean abs diff 0.69-0.98,
  under 1% of pixels changed). All three carry `--use-ck-attention`.
- **B and C are near-identical to each other** (mean abs diff 0.61, 0.1% of
  pixels). Neither carries it.
- **The two classes differ almost everywhere** (mean abs diff ~50.8, 98-99.8%
  of pixels changed). They are different images.

The 0.6-1.0 mean differences within a class are this box's run-to-run
non-determinism, measured independently at mean 0.88 on a same-seed rerun.

Conclusion: `--use-ck-attention` is the sole cause. `--fp16-intermediates` and
`--force-upcast-attention` have no measurable effect on output.

## Why 64 tokens

`comfy/text_encoders/qwen_image21.py` wraps the prompt in a chat template and
masks out the system turn. That mask removes a fixed 14 leading tokens, so the
DiT receives `total_tokens - 14`.

The last passing sample had exactly **64** surviving tokens and the first
failing sample had **68**. 64 is a standard attention tile/block size, which
makes a boundary-crossing bug in the masked-attention path the likely
mechanism rather than a model capability limit.

Verified as *not* the cause:

- No length cap exists in code. `Qwen3VLSDTokenizer` has `max_length=99999999`;
  the encoder preserves sequence length; the DiT computes
  `seq_txt = encoder_hidden_states.shape[1]` dynamically.
- The attention mask is correct. `151644` is `<|im_start|>`, there are three of
  them (system/user/assistant), and `im_starts[1]` correctly selects the user
  turn, so the mask drops only the system turn. The full prompt reaches the
  encoder.
- Same result with Q4_K_M and Q8_0, so quantization is irrelevant.
- Prompt enhancer stays unloaded (`ComfySwitchNode` is lazy, `switch=False`
  never evaluates the branch), so it cannot be interfering.

## Impact

Any Qwen-Image 2.1 prompt longer than ~64 tokens is affected. Real-world
prompts exceed that routinely, so this is not an edge case.

`--use-ck-attention` was adopted for MiniMax H3 on this machine, where it
measured a 2.70x sampling speedup, 0.40 GiB lower peak VRAM, and 0.99786
correlation versus the previous configuration. It is a genuine win for that
model, which is why removing it globally is not the preferred fix. The
problem is that one global flag is shared by model families that need
different behavior.

## Suggested fix

The bug appears to be in Comfy Kitchen's masked-attention path rather than in
ComfyUI's model code, so this may need to be reported upstream to
`comfy-kitchen`. A few angles worth checking there:

1. Masked attention when the text stream crosses a 64-token block boundary,
   specifically for the joint image+text attention used by Qwen-Image.
2. Whether the INT8 path handles a variable-length text mask correctly when
   `seq_txt` exceeds the kernel's block size.
3. Whether the correct result is recoverable by routing Qwen-Image 2.1 through
   a non-INT8 Comfy Kitchen backend.

If a fix lands in a later comfy-kitchen release, a single launch flag would
work for both model families and the 2.70x MiniMax H3 speedup is preserved.

As an interim workaround, Qwen-Image 2.1 can be run without
`--use-ck-attention`. A launch script omitting only that flag was verified to
produce correct output at all tested prompt lengths up to 101 tokens.

## Environment

- ComfyUI: portable Windows build, ROCm
- GPU: AMD Radeon RX 7900 XTX, 24 GiB
- comfy-kitchen: 0.2.31 (backends detected: hip, eager, cuda; triton unavailable)
- Models: `qwen-image-2.1-UC-Q4_K_M.gguf`, `qwen3vl_8b_int8_convrot.safetensors`,
  `qwen_image_2.1_vae_bf16.safetensors`
- Sampler: steps 25, cfg 1.0, euler / simple, seed fixed, 1024x1024