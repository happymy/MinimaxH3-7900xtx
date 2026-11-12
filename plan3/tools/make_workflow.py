"""Build the 8B + ClipProj variant of the four stock HyperFlow workflows.

Each stock graph (``stock_<family>.json``, a snapshot of
``example_workflows/hyperflow_<family>.json``) points its ``CLIPLoader`` at
``qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors``. That file cannot run on
gfx1100 (RX 7900 XTX), so this rewrites the encoder path to Qwen3-VL-8B Heretic
plus a calibrated projection matrix, leaving every sampling parameter untouched.

Two outputs per family, same three changes each:

    hyperflow_<family>_clipproj_8b.json      UI graph, into %WORKFLOWS%
    API_workflows/hyperflow_<family>_clipproj_8b_api.json
                                             /prompt payload, into ../API_workflows

    python make_workflow.py              # all four, both formats
    python make_workflow.py ref2v        # just one
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = (r"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
             r"\user\default\workflows")
API_OUT = os.path.join(os.path.dirname(HERE), "API_workflows")

FAMILIES = ("t2v", "i2v", "flf2v", "ref2v")

CLIP_NAME = "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors"
CLIP_TYPE = "boogu"          # the branch comfy/sd.py takes for Qwen3-VL-8B + H3
MATRIX = "mmh3-8b-ClipProj-v3.1-mlp.safetensors"

# "auto" = the loader picks (disk when --fast-disk, ram otherwise). "disk" keeps
# whatever does not fit in VRAM inside the GGUF file's mmap and streams it back
# layer by layer instead of copying 9 GB into RAM (loader_nodes.py:92).
WEIGHTS_IN = "disk"

TITLES = {
    "t2v": ("text to video",
            "**Change**: the prompt, size and length in the blue group."),
    "i2v": ("first frame to video",
            "Load your image in **First frame**; the video starts on it."),
    "flf2v": ("first and last frame to video",
              "Load your images in **First frame** and **Last frame**; the "
              "video starts on the first and ends on the last."),
    "ref2v": ("video from reference images",
              "Load your references in **<Picture 1>** and **<Picture 2>** and "
              "name them that way in the prompt. To add up to 9, connect more "
              "images to the reference node; they are `<Picture 3>`, "
              "`<Picture 4>`, ... in that order."),
}


def note(family, dit):
    title, lead = TITLES[family]
    return """## HyperFlow H3 Flash: %s

**Encoder adapted for gfx1100** (RX 7900 XTX): the stock 32B `nvfp4_awq` needs Blackwell FP4, so this graph uses **Qwen3-VL-8B Heretic** (DreamFast 1.3.0) + a calibrated projection matrix instead.

%s

| Folder | File |
|---|---|
| `diffusion_models/` | `%s` |
| `text_encoders/` | `%s` |
| `clip_projections/` | `%s` |
| `vae/` | `minimax_h3_video_vae_fp16.safetensors`, `minimax_h3_audio_vae_fp32.safetensors` |

**Length** is frames at 24 fps, snapped to 17n+5: 124 is 5.2 s. `steps` in **HyperFlow Sigmas** is 4 (speed), 6 (default) or 8 (quality).

**`weights_in` = `disk`**: transformer weights that do not fit in VRAM stay in the GGUF file and stream to the GPU layer by layer instead of being copied into RAM. Set it back to `auto` if a run gets slower.

**Keep** `euler`, CFG 1, `boogu` on Load CLIP, and no negative prompt. The model was trained for them.

**Prompt**: English, the three fields `integrated_multimodal_description` / `overall_soundscape` / `non_diegetic_music`. Put the visual style in the **first sentence** of `[Shot 1]` -- e.g. `Photoreal 35mm film, natural skin texture, shallow depth of field.` Do **not** write "no anime" / "avoid ..." / any prohibition: at CFG 1 there is no negative branch, so those words feed the very style you are rejecting and the 6-step model follows them.

**Before running**: close every other GPU application. At 1344x768x124 this graph sits at the VRAM ceiling; competing allocations turn the run into paging.

**32 GB of RAM**: start ComfyUI with `--fast-disk --use-ck-attention`.

**Before each run**: free the previous run's models first -- run `plan3/t2v/step0_free.py` (POST /free with `unload_models` + `free_memory`) and wait until it reports ~ `total - 1.5 GB` free. Without that step the second run OOMs while loading the encoder, because the previous run's DiT and VAEs (14.5 GB) are still resident. A free node at the end of the graph is *not* enough: it skips the worker's `gc.collect()` and `e.reset()`.
""" % (title, lead, dit, CLIP_NAME, MATRIX)


def build(family):
    src = os.path.join(HERE, "stock_%s.json" % family)
    dst = os.path.join(WORKFLOWS, "hyperflow_%s_clipproj_8b.json" % family)
    d = json.load(open(src, encoding="utf-8"))
    nodes = {n["id"]: n for n in d["nodes"]}

    clip_loader = next(n for n in d["nodes"] if n["type"] == "CLIPLoader")
    loader = next(n for n in d["nodes"] if n["type"] == "HyperFlowLoader")
    # every family feeds its prompt through one MiniMaxH3 node's `clip` input
    target = next(n for n in d["nodes"] if n["type"].startswith("MiniMaxH3"))

    # 0. where the transformer weights live between steps
    loader["widgets_values"][1] = WEIGHTS_IN
    if isinstance(loader.get("widgets_values_named"), dict):
        loader["widgets_values_named"]["weights_in"] = WEIGHTS_IN

    # 1. point the stock loader at the 8B encoder
    clip_loader["widgets_values"] = [CLIP_NAME, CLIP_TYPE, "default"]

    # 2. re-route the clip link through a new ClipProjApply node
    clip_slot = next(i for i, inp in enumerate(target["inputs"])
                     if inp["name"] == "clip")
    old_link_id = target["inputs"][clip_slot]["link"]

    new_id = d["last_node_id"] + 1
    new_link_id = d["last_link_id"] + 1

    for link in d["links"]:
        if link[0] == old_link_id:
            link[3] = new_id
            link[4] = 0
            break
    else:
        raise SystemExit("%s: link %s not found" % (family, old_link_id))

    d["links"].append([new_link_id, new_id, 0, target["id"], clip_slot, "CLIP"])

    d["nodes"].append({
        "id": new_id,
        "type": "ClipProjApply",
        "pos": [clip_loader["pos"][0] + 340, clip_loader["pos"][1]],
        "size": [320, 60],
        "flags": {},
        "order": clip_loader["order"] + 1,
        "mode": 0,
        "inputs": [{"name": "clip", "type": "CLIP", "link": old_link_id}],
        "outputs": [{"name": "clip", "type": "CLIP", "links": [new_link_id],
                     "slot_index": 0}],
        "properties": {"Node name for S&R": "ClipProjApply"},
        "widgets_values": [MATRIX],
    })

    target["inputs"][clip_slot]["link"] = new_link_id

    # 3. the note in the graph should describe this graph
    text = note(family, loader["widgets_values"][0])
    for n in d["nodes"]:
        if n["type"] == "MarkdownNote":
            n["widgets_values"] = [text]

    d["last_node_id"] = new_id
    d["last_link_id"] = new_link_id

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print("%-6s %-22s clip=%s -> %s.%d  weights_in=%s"
          % (family, os.path.basename(dst), MATRIX, target["type"], clip_slot,
             loader["widgets_values"][1]))


def build_api(family):
    """Same three changes, applied to the official API payload.

    The API snapshot is already the flat {id: {class_type, inputs}} form, so the
    clip link is a ["2", 0] reference rather than a link id: inserting the
    projection means pointing the MiniMaxH3 node at a new node id.
    """
    src = os.path.join(HERE, "stock_%s_api.json" % family)
    dst = os.path.join(API_OUT, "hyperflow_%s_clipproj_8b_api.json" % family)
    d = json.load(open(src, encoding="utf-8"))

    clip_loader = next(n for n in d.values() if n["class_type"] == "CLIPLoader")
    loader = next(n for n in d.values() if n["class_type"] == "HyperFlowLoader")
    target = next(n for n in d.values()
                  if n["class_type"].startswith("MiniMaxH3"))

    loader["inputs"]["weights_in"] = WEIGHTS_IN
    clip_loader["inputs"].update({"clip_name": CLIP_NAME, "type": CLIP_TYPE})

    new_id = str(max(int(k) for k in d) + 1)
    old_ref = target["inputs"]["clip"]
    d[new_id] = {"class_type": "ClipProjApply",
                 "inputs": {"clip": old_ref, "projection": MATRIX}}
    target["inputs"]["clip"] = [new_id, 0]

    os.makedirs(API_OUT, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print("%-6s %-40s clip=%s -> ClipProjApply(%s) -> %s.clip  weights_in=%s"
          % (family, os.path.basename(dst), old_ref[0], new_id,
             target["class_type"], loader["inputs"]["weights_in"]))


def main():
    wanted = sys.argv[1:] or list(FAMILIES)
    unknown = [f for f in wanted if f not in FAMILIES]
    if unknown:
        raise SystemExit("unknown family %s, pick from %s"
                         % (unknown, list(FAMILIES)))
    for family in wanted:
        build(family)
        build_api(family)


main()
