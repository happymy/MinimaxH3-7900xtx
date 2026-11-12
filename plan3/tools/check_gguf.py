"""Check a HyperFlow GGUF against what ComfyUI-HyperFlow-Flash/gguf_io.py expects.

    python check_gguf.py [path-to.gguf]

Playbook on the output:

* ``general.architecture`` must be ABSENT - the files carry the
  stable-diffusion.cpp layout, and ComfyUI-GGUF would reject an architecture it
  does not know.
* tensor names must start with ``model.diffusion_model.``; the loader strips it
  with ``removeprefix``, but a file without it would keep the wrong prefix and
  the state dict would not match.
* the top-level module list must include ``endpoint_time_embedder``,
  ``hyperflow_gate`` and ``hyperflow_sigmas`` - ``pop_extras`` and
  ``install_two_time`` read them. A 6-step schedule comes from the file.
* count ``down.weight`` blocks: that is the number ``model_patch.FactorizedPlan``
  folds, and the loader logs it as "N factorized blocks".
"""

import collections
import os
import sys

import gguf

DEFAULT = (r"C:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models"
           r"\minimax_h3_fl2va_hyperflow_flash_14b-Q4_K_M.gguf")
PREFIX = "model.diffusion_model."

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
print("file:", path, "%.2f GB" % (os.path.getsize(path) / 1e9))

r = gguf.GGUFReader(path)
names = [t.name for t in r.tensors]

arch = r.fields.get("general.architecture")
print("general.architecture:", arch.contents() if arch else "ABSENT (what HyperFlow expects)")
print("tensors:", len(names))
print("with %s prefix: %d" % (PREFIX, sum(n.startswith(PREFIX) for n in names)))

print("quant types:", dict(collections.Counter(t.tensor_type.name for t in r.tensors)))

non_block = sorted({n for n in names if not n.startswith("blocks.")})
print("non-block tensors:", non_block)

for key in ("endpoint_time_embedder.", "hyperflow_gate", "hyperflow_sigmas"):
    print("has %-24s %s" % (key, any(n.startswith(key) for n in names)))

def blk(pred):
    # token_refiner.blocks.* ends the same way, so require the top-level prefix
    return {int(n.split(".")[1]) for n in names if n.startswith("blocks.") and pred(n)}


blocks = blk(lambda n: True)
dense = blk(lambda n: n.endswith("attn.qkv_proj.weight"))
lowrank = blk(lambda n: n.endswith(".down.weight"))
print("blocks: %d  dense-qkv: %d  low-rank: %d" % (len(blocks), len(dense), len(lowrank)))
print("  -> the loader should log 'HyperFlow: %d factorized blocks'" % len(lowrank))
