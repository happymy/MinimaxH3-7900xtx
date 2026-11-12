"""Static check of the API graphs the plan3/bat generators build.

    python check_graphs.py

Loads each generator, builds one graph per entry point, then verifies that
every node reference resolves and that every input name exists on that node
type, using the official API workflows as the signature source. This catches
the silent kind of mistake: ComfyUI ignores an input it does not recognise, so
a renamed slot fails as "prompt outputs nothing", not as an error.
"""

import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
API = (r"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\custom_nodes"
       r"\ComfyUI-HyperFlow-Flash\example_workflows\api")

# Not in any official API graph: ClipProjApply is the ClipProj node we add,
# LoadVideo/GetVideoComponents are core nodes scenes_ref uses for video refs.
EXTRA = {
    "ClipProjApply": {"clip", "projection"},
    "LoadVideo": {"file"},
    "GetVideoComponents": {"video"},
    # optional inputs no official API graph wires, but the UI node accepts
    "HyperFlowLoader": {"unet_name", "weights_in"},
    "CreateVideo": {"images", "audio", "fps", "bit_depth"},
}


def signatures():
    sigs = {}
    for name in sorted(os.listdir(API)):
        if name.endswith("_int8_api.json"):
            continue
        d = json.load(open(os.path.join(API, name), encoding="utf-8"))
        for node in d.values():
            sigs.setdefault(node["class_type"], set()).update(node["inputs"])
    for name, keys in EXTRA.items():
        sigs.setdefault(name, set()).update(keys)
    return sigs


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(where, graph, sigs):
    bad = []
    ids = set(graph)
    for nid, node in graph.items():
        ct = node["class_type"]
        if ct not in sigs:
            bad.append("%s node %s: unknown class_type %s" % (where, nid, ct))
            continue
        for key, val in node["inputs"].items():
            if key not in sigs[ct]:
                bad.append("%s node %s (%s): no input %r, known %s"
                           % (where, nid, ct, key, sorted(sigs[ct])))
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                if val[0] not in ids:
                    bad.append("%s node %s (%s) input %r -> missing node %s"
                               % (where, nid, ct, key, val[0]))
    return bad


def main():
    sigs = signatures()
    problems = []
    cases = []

    p = os.path.join(HERE, "multisegment_8b_heretic",
                     "gen_h3_multisegment-8b-heretic.py")
    m = load(p, "ms")
    cases.append(("multisegment", m.build_graph("p", 864, 480, 124, 6, 1)))
    cases.append(("multisegment+first", m.build_graph("p", 864, 480, 124, 6, 1, "a.png")))

    p = os.path.join(HERE, "scenes_8b_heretic", "gen_h3_scenes-8b-heretic.py")
    m = load(p, "sc")
    cases.append(("scenes", m.build_graph("p", 864, 480, 124, 6, 1)))
    cases.append(("scenes+first", m.build_graph("p", 864, 480, 124, 6, 1, "a.png")))

    p = os.path.join(HERE, "scenes_ref_8b_heretic",
                     "gen_h3_scenes_ref-8b-heretic.py")
    m = load(p, "sr")
    cases.append(("scenes_ref ref", m.build_ref_graph(
        "p", 864, 480, 124, 6, 1, ["a.png", "b.png"], [])))
    cases.append(("scenes_ref fl", m.build_fl_graph("p", 864, 480, 124, 6, 1, "a.png")))

    p = os.path.join(HERE, "ref2va_8b_heretic", "gen_h3_ref2va-8b-heretic.py")
    m = load(p, "r2")
    cases.append(("ref2va ref", m.build_graph(
        "p", 864, 480, 124, 6, 1, ["a.png", "b.png"])))
    cases.append(("ref2va fl", m.build_fl_graph("p", 864, 480, 124, 6, 1, "a.png")))

    for where, graph in cases:
        problems.extend(check(where, graph, sigs))

    for where, graph in cases:
        used = sorted({n["class_type"] for n in graph.values()})
        print("%-16s nodes=%2d  %s" % (where, len(graph), " ".join(used)))

    if problems:
        print("\nPROBLEMS:")
        for x in problems:
            print(" -", x)
        raise SystemExit(1)
    print("\nok: every node reference and input name resolves")


main()
