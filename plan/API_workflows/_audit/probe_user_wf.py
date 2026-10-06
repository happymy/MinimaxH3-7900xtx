"""Run Calliope's real code against the workflow the user actually runs.

Question: when Calliope fills the prompt, does the generator node's real
`prompt` input actually change?
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\localAI\ComfyUI-last\src\Calliope\calliope-backend\src")

from calliope.comfyui.parser import parse_dynamic_inputs, parse_dynamic_outputs
from calliope.comfyui.patcher import patch_workflow
from calliope.comfyui.profiles import detect_prompt_profile
from calliope.comfyui.registry import class_to_input_kind, class_to_patch_field
from calliope.comfyui.smart_fill import smart_fill_inputs

BAK = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\Calliope\bak 05 OK\YES_minimax_h3_ref2v-gguf-api-NOAV.json")

wf = json.loads(BAK.read_text(encoding="utf-8"))

print(f"nodes={len(wf)}  profile={detect_prompt_profile(wf)}")
print()

ins = parse_dynamic_inputs(wf)
outs = parse_dynamic_outputs(wf)
print("PARSED INPUTS (what the UI form shows):")
for i in ins:
    print(f"   node={i['nodeId']:>5}  role={str(i['role']):9} kind={i['kind']:9} {i['label']!r}")
print("PARSED OUTPUTS:")
for o in outs:
    print(f"   node={o['nodeId']:>5}  role={str(o['role']):9} kind={o['kind']:9} {o['label']!r}")
print()

print("PATCH FIELD for every node in the graph:")
for nid, n in wf.items():
    if not isinstance(n, dict):
        continue
    ct = n.get("class_type", "")
    f = class_to_patch_field(ct)
    k = class_to_input_kind(ct)
    keys = set((n.get("inputs") or {}).keys())
    mark = "" if f in keys else "   <== NOT A REAL INPUT KEY"
    print(f"   [{nid:>5}] {ct:28} kind={k:9} -> {f:7}{mark}")
print()

print("SIMULATED enqueue: smart_fill + patch")
values = smart_fill_inputs(
    ins,
    prompt="A SENTINEL PROMPT THAT MUST REACH THE GENERATOR",
    ref_images=["ref.png"],
    duration=5,
)
print("   values =", values)
patched = patch_workflow(wf, values)
print()

print("DID THE GENERATOR ACTUALLY CHANGE?")
for nid in ("300", "145"):
    n = wf.get(nid)
    if not n:
        continue
    print(f"   [{nid}] {n['class_type']}")
    for ik, iv in (n.get("inputs") or {}).items():
        pv = (patched[nid].get("inputs") or {}).get(ik, "<ABSENT>")
        changed = "CHANGED" if pv != iv else "unchanged"
        show_iv = str(iv)[:70]
        show_pv = str(pv)[:70]
        print(f"       {ik:22} before={show_iv!r}")
        print(f"       {'':22} after ={show_pv!r}   {changed}")

# the decisive question: follow the generator's prompt input back to a literal
gen = patched["145"]
chain = gen["inputs"].get("prompt")
print()
print(f"generator 145.prompt = {chain}")
if isinstance(chain, list):
    src = chain[0]
    print(f"   -> node {src}: {patched[src]['class_type']}")
    v = patched[src]["inputs"].get("value")
    print(f"   -> {src}.value = {str(v)[:120]!r}")
    print()
    if "SENTINEL" in str(v):
        print("VERDICT: prompt DOES reach the generator through node 300.")
    else:
        print("VERDICT: prompt does NOT reach the generator.")
else:
    print(f"   -> literal (no link). VERDICT: prompt cannot be injected here at all.")