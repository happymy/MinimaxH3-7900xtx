"""Verify the adapted workflows against Calliope's real code paths.

Five checks per workflow:

  1. graph integrity   - every link target resolves to a node that exists
  2. roles             - parse_dynamic_inputs / outputs see what we tagged
  3. filling           - smart_fill_inputs produces a value for every role
  4. patching          - patch_workflow writes into EXISTING input keys only
  5. reachability      - the prompt actually arrives at the generator node
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\localAI\ComfyUI-last\src\Calliope\calliope-backend\src")

from calliope.comfyui.parser import (  # noqa: E402
    parse_dynamic_inputs,
    parse_dynamic_outputs,
)
from calliope.comfyui.patcher import patch_workflow  # noqa: E402
from calliope.comfyui.profiles import detect_prompt_profile  # noqa: E402
from calliope.comfyui.smart_fill import smart_fill_inputs  # noqa: E402

TEST = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW\test")

# node id of the node whose real prompt input must receive the text
GENERATOR = {
    "minimax_h3_t2v-gguf-8b-heretic-op.json": ("129", "prompt"),
    "minimax_h3_i2v-gguf-8b-heretic-op.json": ("133", "prompt"),
    "minimax_h3_ref2v-gguf-8b-heretic-op.json": ("145", "prompt"),
    "qwen_image_2_1_t2i-Q8_0_gguf.json": ("9452", "prompt"),
    "qwen_image_2_1_image_edit-Q8_0_gguf.json": ("9474", "prompt"),
    "qwen_image_2_1_background_removal-Q8_0_gguf.json": ("9474", "prompt"),
}

PROBE_PROMPT = "PROBE_PROMPT_SENTINEL"

# Qwen image workflows have no duration concept; only the H3 ones carry one.
NEEDS_DURATION = {
    "minimax_h3_t2v-gguf-8b-heretic-op.json",
    "minimax_h3_i2v-gguf-8b-heretic-op.json",
    "minimax_h3_ref2v-gguf-8b-heretic-op.json",
}

CARRIER_ID = "9900"

failures: list[str] = []


def trace_to_carrier(wf: dict, node_id: str, field: str, depth: int = 0):
    """Walk upstream from ``node_id.field`` looking for the inserted carrier.

    Follows the ACTIVE branch of a ComfySwitchNode (``switch=false`` selects
    ``on_false``, ``switch=true`` selects ``on_true``) so a bypassed rewrite
    chain is reported as bypassed rather than as a broken link.
    """
    if depth > 12:
        return None, [f"...depth limit at {node_id}.{field}"]
    value = (wf.get(node_id, {}).get("inputs") or {}).get(field)
    if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
        return None, [f"{node_id}.{field} = {value!r} (literal, not a link)"]
    src = value[0]
    node = wf.get(src)
    if node is None:
        return None, [f"{node_id}.{field} -> missing node {src}"]
    if src == CARRIER_ID:
        return src, [f"{node_id}.{field} <- {src}"]
    if node.get("class_type") == "ComfySwitchNode":
        branch = "on_true" if node["inputs"].get("switch") else "on_false"
        found, trail = trace_to_carrier(wf, src, branch, depth + 1)
        return found, [f"{node_id}.{field} <- {src}({branch})"] + trail
    # any other upstream node: search it for the first input that reaches the carrier
    for key in (node.get("inputs") or {}):
        val = node["inputs"][key]
        if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
            found, trail = trace_to_carrier(wf, src, key, depth + 1)
            if found:
                return found, [f"{node_id}.{field} <- {src}.{key}"] + trail
    return None, [f"{node_id}.{field} <- {src} ({node.get('class_type')}) [no path to carrier]"]


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"      !! {msg}")


for path in sorted(TEST.glob("*.json")):
    wf = json.loads(path.read_text(encoding="utf-8"))
    print(f"\n{'=' * 76}\n{path.name}")

    # 1. graph integrity -----------------------------------------------------
    dangling = []
    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        for key, value in (node.get("inputs") or {}).items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                if value[0] not in wf:
                    dangling.append(f"{nid}.{key} -> {value[0]}")
    if dangling:
        for d in dangling:
            fail(f"dangling link {d}")
    else:
        print("  [1] graph integrity      ok  (no dangling links)")
    nonint = [k for k in wf if not str(k).isdigit()]
    if nonint:
        fail(f"non-integer node ids remain: {nonint}")
    else:
        print(f"      node ids: all integer ({len(wf)} nodes)")

    # 2. roles ---------------------------------------------------------------
    ins = parse_dynamic_inputs(wf)
    outs = parse_dynamic_outputs(wf)
    print(f"  [2] roles                profile={detect_prompt_profile(wf)}")
    for i in ins:
        print(f"        input  {i['nodeId']:>6}  role={str(i['role']):9} kind={i['kind']:9} {i['label']!r}")
    for o in outs:
        print(f"        output {o['nodeId']:>6}  role={str(o['role']):9} kind={o['kind']:9} {o['label']!r}")
    if not ins:
        fail("no dynamic inputs parsed")
    if not outs:
        fail("no dynamic outputs parsed")
    roles = {i["role"] for i in ins}
    if "prompt" not in roles:
        fail("missing (Input:prompt)")
    if path.name in NEEDS_DURATION and "duration" not in roles:
        fail("missing (Input:duration)")

    # 3. filling -------------------------------------------------------------
    values = smart_fill_inputs(
        ins,
        prompt=PROBE_PROMPT,
        ref_images=["ref_a.png", "ref_b.png"],
        ref_videos=["ref_v.mp4"],
        ref_audios=["ref_a.wav"],
        duration=6,
    )
    print(f"  [3] filling              {values}")

    # 4. patching ------------------------------------------------------------
    patched = patch_workflow(wf, values)
    print("  [4] patching")
    for nid, val in values.items():
        before = set((wf[nid].get("inputs") or {}).keys())
        after = set(patched[nid]["inputs"].keys())
        added = after - before
        ct = wf[nid]["class_type"]
        if added:
            fail(f"[{nid}] {ct} patch created bogus key(s) {sorted(added)}")
        else:
            key = sorted(before & after & {k for k in after})  # noqa: E501
            written = [k for k in before if patched[nid]["inputs"][k] == val]
            print(f"        [{nid}] {ct:26} -> {written}")

    # 5. reachability: does the generator actually receive the prompt? -------
    gid, gfield = GENERATOR[path.name]
    print(f"  [5] reachability         trace {gid}.{gfield} upstream:")
    found, trail = trace_to_carrier(patched, gid, gfield)
    for step in trail:
        print(f"        {step}")
    if not found:
        fail(f"no path from {gid}.{gfield} to the inserted carrier {CARRIER_ID}")
        continue
    got = patched[found]["inputs"]["value"]
    if got != PROBE_PROMPT:
        fail(f"prompt did not reach generator: carrier holds {got!r}")
    else:
        print(f"        => prompt delivered to {gid}.{gfield}  OK")

print(f"\n{'=' * 76}")
if failures:
    print(f"FAILED - {len(failures)} problem(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")