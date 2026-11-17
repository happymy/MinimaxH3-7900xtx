"""Sanity-check ComfyUI workflow JSONs: links, references, and the 8B wiring.

    python check_workflow.py <workflow.json> [more.json ...]

A UI link is broken when either the origin output does not list it, the target
input does not point back at it, or it is missing from the ``links`` array.
Those three failures are silent in the canvas, so they only surface as "prompt
outputs nothing" at run time.

The API payload (flat ``{id: {class_type, inputs}}``) has no links array, so it
gets the reference checks instead: every ``[id, slot]`` must name a node in the
same file, every value must be a primitive or such a reference, and no UI
leftovers are allowed.

When the file carries the HyperFlow 8B path (``HyperFlowLoader``), its wiring is
asserted as well. The qwen / TTS payloads in ``API_workflows`` have nothing to
assert beyond the references, so they skip that block.
"""

import json
import sys

CLIP_NAMES = (
    "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
    "qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors",
)
CLIP_TYPE = "boogu"
MATRIX = "mmh3-8b-ClipProj-v3.1-mlp.safetensors"


def fail(problems):
    print("PROBLEMS:")
    for x in problems:
        print(" -", x)
    raise SystemExit(1)


def by_type(d, name):
    """(id, node) of the single node of that class_type, or (None, None)."""
    hits = [(k, n) for k, n in d.items() if n["class_type"] == name]
    return hits[0] if len(hits) == 1 else (None, None)


def check_api(d):
    problems = []

    for nid, node in d.items():
        if "widgets_values" in node:
            problems.append("%s: UI field widgets_values in an API payload" % nid)
        for key, val in node["inputs"].items():
            if isinstance(val, list):
                if len(val) != 2 or not isinstance(val[0], str):
                    problems.append("%s.%s: malformed reference %r" % (nid, key, val))
                elif val[0] not in d:
                    problems.append("%s.%s -> missing node %s" % (nid, key, val[0]))
            elif isinstance(val, dict):
                problems.append("%s.%s: dict value, the API wants a flat input"
                                % (nid, key))

    types = sorted({n["class_type"] for n in d.values()})
    print("api: %d nodes, %s" % (len(d), ", ".join(types[:6])
                                 + (", ..." if len(types) > 6 else "")))
    if problems:
        fail(problems)

    if "HyperFlowLoader" not in types:
        print("ok: references resolve (not an H3 graph, no ClipProj assertions)")
        return

    clip_loader = next((n for n in d.values() if n["class_type"] == "CLIPLoader"), None)
    loader = next((n for n in d.values() if n["class_type"] == "HyperFlowLoader"), None)
    target = next((n for n in d.values()
                   if n["class_type"].startswith("MiniMaxH3")), None)
    cp_id, cp = by_type(d, "ClipProjApply")
    for label, node in (("CLIPLoader", clip_loader), ("MiniMaxH3*", target),
                        ("ClipProjApply", cp)):
        if node is None:
            problems.append("%s missing from the 8B graph" % label)

    if clip_loader is not None:
        if clip_loader["inputs"].get("clip_name") not in CLIP_NAMES:
            problems.append("CLIPLoader still points at %s"
                            % clip_loader["inputs"].get("clip_name"))
        if clip_loader["inputs"].get("type") != CLIP_TYPE:
            problems.append("CLIPLoader type is %r, expected %s"
                            % (clip_loader["inputs"].get("type"), CLIP_TYPE))
    if loader["inputs"].get("weights_in") != "disk":
        problems.append("HyperFlowLoader weights_in is %r, expected 'disk'"
                        % loader["inputs"].get("weights_in"))

    if cp is not None:
        clip_ref = cp["inputs"].get("clip")
        if not (isinstance(clip_ref, list) and d.get(clip_ref[0]) is clip_loader):
            problems.append("ClipProjApply.clip does not come from CLIPLoader")
        if cp["inputs"].get("projection") != MATRIX:
            problems.append("ClipProjApply projection is %r"
                            % cp["inputs"].get("projection"))
        consumers = sorted(k for k, n in d.items()
                           if n["inputs"].get("clip") == [cp_id, 0])
        if len(consumers) != 1 or d[consumers[0]] is not target:
            problems.append("ClipProjApply output feeds %s, expected only the "
                            "MiniMaxH3 node" % consumers)

    sampler = next((n for n in d.values() if n["class_type"] == "KSamplerSelect"), None)
    sigmas = next((n for n in d.values() if n["class_type"] == "HyperFlowSigmas"), None)
    if sampler is None or sigmas is None:
        problems.append("KSamplerSelect / HyperFlowSigmas missing")
    else:
        if sampler["inputs"].get("sampler_name") != "euler":
            problems.append("sampler is %r" % sampler["inputs"].get("sampler_name"))
        if sigmas["inputs"].get("steps") not in (4, 6, 8):
            problems.append("HyperFlowSigmas steps=%r, only 4/6/8 exist"
                            % sigmas["inputs"].get("steps"))
        print("steps=%d" % sigmas["inputs"]["steps"])

    if problems:
        fail(problems)
    print("ok: references resolve, 8B + ClipProj wiring as expected "
          "(weights_in=%s)" % loader["inputs"]["weights_in"])


def check_ui(d):
    nodes = {n["id"]: n for n in d["nodes"]}
    by_link = {link[0]: link for link in d["links"]}

    problems = []

    for link in d["links"]:
        lid, oid, oslot, tid, tslot, ltype = link
        out = nodes.get(oid, {}).get("outputs", [])
        if oid not in nodes:
            problems.append(f"link {lid}: origin node {oid} missing")
        elif oslot >= len(out) or lid not in (out[oslot].get("links") or []):
            problems.append(f"link {lid}: origin {oid}.out[{oslot}] does not list it")
        ins = nodes.get(tid, {}).get("inputs", [])
        if tid not in nodes:
            problems.append(f"link {lid}: target node {tid} missing")
        elif tslot >= len(ins) or ins[tslot].get("link") != lid:
            problems.append(f"link {lid}: target {tid}.in[{tslot}] does not point back")

    for n in d["nodes"]:
        for i, inp in enumerate(n.get("inputs") or []):
            lid = inp.get("link")
            if lid is not None and lid not in by_link:
                problems.append(f'{n["id"]}.in[{i}] {inp["name"]}: link {lid} not in links')
        for i, out in enumerate(n.get("outputs") or []):
            for lid in out.get("links") or []:
                if lid not in by_link:
                    problems.append(f'{n["id"]}.out[{i}] {out["name"]}: link {lid} not in links')

    print("links:", len(d["links"]), "nodes:", len(d["nodes"]))
    if problems:
        fail(problems)

    cp = next((n for n in d["nodes"] if n["type"] == "ClipProjApply"), None)
    if cp is not None:
        # both ends, found by type: the t2v/i2v/flf2v/ref2v graphs differ only in ids
        src = by_link[cp["inputs"][0]["link"]]
        clip_loader = nodes[src[1]]
        assert clip_loader["type"] == "CLIPLoader", clip_loader["type"]
        assert clip_loader["widgets_values"][:2] == [CLIP_NAME, CLIP_TYPE], \
            clip_loader["widgets_values"]

        dst = by_link[cp["outputs"][0]["links"][0]]
        chosen = nodes[dst[3]]
        assert chosen["type"].startswith("MiniMaxH3"), chosen["type"]
        assert chosen["inputs"][dst[4]]["name"] == "clip", chosen["inputs"][dst[4]]
        assert chosen["inputs"][dst[4]]["link"] == dst[0]

        assert cp["widgets_values"] == [MATRIX], cp["widgets_values"]

        loader = next((n for n in d["nodes"] if n["type"] == "HyperFlowLoader"), None)
        assert loader is not None, "ClipProjApply without HyperFlowLoader"
        assert loader["widgets_values"][1] == "disk", loader["widgets_values"]

        print("ok: 8B + ClipProj wiring as expected (%s, weights_in=%s)"
              % (chosen["type"], loader["widgets_values"][1]))

    free = next((n for n in d["nodes"] if n["type"] == "ClipProjFree"), None)
    if free is not None:
        assert free["widgets_values"] == ["all models"], free["widgets_values"]
        origin = by_link[free["inputs"][0]["link"]][1]
        assert nodes[origin]["type"] == "CreateVideo", nodes[origin]["type"]
        print("ok: ClipProjFree(all models) anchored after CreateVideo")

    print("ok: every link agreed on both ends")


for p in sys.argv[1:]:
    print("--", p)
    d = json.load(open(p, encoding="utf-8"))
    if "nodes" not in d:
        check_api(d)
    else:
        check_ui(d)
