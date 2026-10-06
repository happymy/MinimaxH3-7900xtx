"""Run Calliope's REAL comfyui parsing/fill/patch code against the RAW workflows.

Read-only probe: imports calliope.comfyui.{registry,roles,parser,patcher,smart_fill,profiles}
and reports, per workflow, what Calliope can actually see and write.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

BACKEND = Path(r"D:\localAI\ComfyUI-last\src\Calliope\calliope-backend")
sys.path.insert(0, str(BACKEND / "src"))

from calliope.comfyui.parser import parse_dynamic_inputs, parse_dynamic_outputs  # noqa: E402
from calliope.comfyui.patcher import patch_workflow  # noqa: E402
from calliope.comfyui.profiles import detect_prompt_profile  # noqa: E402
from calliope.comfyui.registry import class_to_input_kind, class_to_patch_field  # noqa: E402
from calliope.comfyui.smart_fill import ref_image_slots, ref_video_slots, smart_fill_inputs  # noqa: E402

RAW = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW")


def rule(t: str = "") -> None:
    print("\n" + "=" * 78 + (f"\n{t}" if t else ""))


for path in sorted(RAW.glob("*.json")):
    wf = json.loads(path.read_text(encoding="utf-8"))
    rule(path.name)

    print(f"  nodes={len(wf)}  profile={detect_prompt_profile(wf)}")

    try:
        ins = parse_dynamic_inputs(wf)
        outs = parse_dynamic_outputs(wf)
        print(f"  dynamic_inputs={len(ins)}  dynamic_outputs={len(outs)}")
    except Exception:
        print("  !! parse_dynamic_inputs RAISED")
        traceback.print_exc()
        continue

    print("  -- tag nodes with (Input)/(Output) in title:")
    for nid, n in wf.items():
        if not isinstance(n, dict):
            continue
        t = (n.get("_meta") or {}).get("title") or ""
        if "(input" in t.lower() or "(output" in t.lower():
            print(f"     [{nid}] {n.get('class_type')} -> {t!r}")
    if not ins and not outs:
        print("     (none — workflow is UNTAGGED)")

    # node-id sanity
    bad_ids = [k for k in wf if not str(k).isdigit()]
    print(f"  -- non-integer node ids: {bad_ids if bad_ids else 'none'}")

    # patch-field table
    print("  -- patch-field resolution:")
    for nid, n in wf.items():
        if not isinstance(n, dict):
            continue
        ct = n.get("class_type", "")
        field = class_to_patch_field(ct)
        keys = set((n.get("inputs") or {}).keys())
        hit = field in keys
        flag = "" if hit else "   <== NOT A REAL INPUT KEY"
        if not hit or ct.startswith(("MiniMaxH3", "Qwen", "Text")):
            print(f"     [{nid}] {ct:34s} -> {field:6s}{flag}")

    # the actual crash probe
    print("  -- smart_fill probe:")
    try:
        slots = ref_image_slots(ins)
        vslots = ref_video_slots(ins)
        print(f"     ref_image_slots={[s['nodeId'] for s in slots]}  ref_video_slots={[s['nodeId'] for s in vslots]}")
    except Exception as e:
        print(f"     !! ref_*_slots RAISED {type(e).__name__}: {e}")

    try:
        vals = smart_fill_inputs(
            ins,
            prompt="PROBE_PROMPT",
            ref_images=["a.png", "b.png"],
            ref_videos=["v.mp4"],
            duration=6,
        )
        print(f"     smart_fill_inputs -> {vals}")
    except Exception as e:
        print(f"     !! smart_fill_inputs RAISED {type(e).__name__}: {e}")

    # end-to-end: can Calliope write a prompt at all?
    tagged_prompt = [i for i in ins if i["role"] == "prompt"]
    if tagged_prompt:
        try:
            out = patch_workflow(wf, {str(tagged_prompt[0]["nodeId"]): "PROBE_PROMPT"})
            nid = str(tagged_prompt[0]["nodeId"])
            print(f"     patched node {nid} inputs -> {list(out[nid]['inputs'].keys())}")
        except Exception as e:
            print(f"     !! patch_workflow RAISED {type(e).__name__}: {e}")
    else:
        print("     no (Input:prompt) node -> Calliope CANNOT inject a prompt")

rule("registry verdict for the classes that matter")
for ct in [
    "MiniMaxH3ImageToVideo",
    "MiniMaxH3ReferenceToVideo",
    "TextEncodeQwenImage21",
    "TextGenerate",
    "ResolutionSelector",
    "CCTechClipProjLoader",
    "ComfyMathExpression",
    "SaveImageAdvanced",
    "SaveVideo",
    "PrimitiveStringMultiline",
    "LoadImage",
    "LoadVideo",
    "LoadAudio",
]:
    print(f"  {ct:30s} kind={class_to_input_kind(ct):10s} patch_field={class_to_patch_field(ct)}")