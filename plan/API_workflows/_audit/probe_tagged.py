"""Prove/disprove: does Calliope survive non-integer node ids ("459:451")?

Simulates the ADAPTED (tagged) form of the Qwen workflows, which is what we
would hand Calliope after adding (Input:...) / (Output:...) role tags.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, r"D:\localAI\ComfyUI-last\src\Calliope\calliope-backend\src")

from calliope.comfyui.parser import parse_dynamic_inputs  # noqa: E402
from calliope.comfyui.smart_fill import smart_fill_inputs  # noqa: E402
from calliope.comfyui.patcher import patch_workflow  # noqa: E402

RAW = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW")

# Tags we would add to make each workflow Calliope-adaptable.
TAGS = {
    "qwen_image_2_1_image_edit-Q8_0_gguf.json": {
        "459:474": "(Input:prompt) Prompt",
        "470": "(Input:image) Source",
        "475": "(Input:image) Ref 2",
        "461": "(Output:image) Result",
    },
    "qwen_image_2_1_t2i-Q8_0_gguf.json": {
        "459:474": "(Input:prompt) Prompt",
        "461": "(Output:image) Result",
    },
    "qwen_image_2_1_background_removal-Q8_0_gguf.json": {
        "470": "(Input:image) Source",
        "461": "(Output:image) Result",
    },
    "minimax_h3_ref2v-gguf-8b-heretic-op.json": {
        "145": "(Input:prompt) Prompt",
        "149": "(Input:image) Ref 1",
        "156": "(Input:video) Ref Video",
        "153": "(Input:audio) Ref Audio",
        "92": "(Output:video) Result",
    },
    "minimax_h3_i2v-gguf-8b-heretic-op.json": {
        "133": "(Input:prompt) Prompt",
        "114": "(Input:image) First Frame",
        "141": "(Input:image) Last Frame",
        "92": "(Output:video) Result",
    },
    "minimax_h3_t2v-gguf-8b-heretic-op.json": {
        "129": "(Input:prompt) Prompt",
        "92": "(Output:video) Result",
    },
}

for name, tags in TAGS.items():
    print("=" * 78)
    print(name)
    wf = json.loads((RAW / name).read_text(encoding="utf-8"))
    for nid, title in tags.items():
        if nid in wf:
            wf[nid].setdefault("_meta", {})["title"] = title
        else:
            print(f"   (node {nid} absent)")

    ins = parse_dynamic_inputs(wf)
    print(f"  parsed {len(ins)} dynamic inputs:")
    for i in ins:
        print(f"     node={i['nodeId']:10s} role={str(i['role']):10s} kind={i['kind']:9s} default={str(i['defaultValue'])[:40]!r}")

    print("  smart_fill_inputs(prompt=..., ref_images=[a,b], ref_videos=[v]):")
    try:
        v = smart_fill_inputs(
            ins, prompt="A cinematic shot", ref_images=["a.png", "b.png"], ref_videos=["v.mp4"]
        )
        print(f"     OK -> {v}")
    except Exception:
        print("     !! RAISED:")
        traceback.print_exc(limit=3)

    prompt_inputs = [i for i in ins if i["role"] == "prompt"]
    if prompt_inputs:
        nid = str(prompt_inputs[0]["nodeId"])
        out = patch_workflow(wf, {nid: "A cinematic shot"})
        written = list(out[nid]["inputs"].keys())
        print(f"  patch_workflow wrote into node {nid} ({wf[nid]['class_type']}).")
        print(f"     keys now: {written}")
        if "prompt" not in written:
            print("     !! VERDICT: prompt was written to the WRONG key -> ComfyUI will ignore it.")
    else:
        print("  !! VERDICT: no (Input:prompt) parsed")
    print()