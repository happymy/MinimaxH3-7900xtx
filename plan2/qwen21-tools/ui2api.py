"""Convert a ComfyUI frontend workflow (UI format, subgraphs included) into the
API prompt format so a delivered .json can be executed headlessly.

The API references outputs as [node_key, output_slot], so the work is resolving
input links. Inside a subgraph a link originating at the input node (-10) names
an interface slot rather than a node, and a link landing on the output node (-20)
is what the top-level instance re-exports. On the instance, `widgets_values` is
positional over the subgraph's interface inputs, skipping socket-only types
(IMAGE), and a real incoming link on the instance overrides the stored value.
"""
import json, os, sys

WIDGET_TYPES = {"STRING", "BOOLEAN", "INT", "FLOAT", "COMBO"}
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_schema.json")
SCHEMA = json.load(open(SCHEMA_PATH, encoding="utf-8")) if os.path.exists(SCHEMA_PATH) else {}


def put(inputs, cls, name, val):
    """Map a UI socket name onto its API input.

    The API keys every dynamic input by its dotted path (`images.image_1`,
    `format.bit_depth`) and expects no container object, so a socket name only
    needs its autogrow counter suffix dropped when the class declares it flat.
    """
    s = SCHEMA.get(cls) or {}
    base = name.split(".")[0]
    keep = name in s.get("inputs", []) or base in s.get("agrow", []) or base in s.get("wcombo", [])
    inputs[name if keep else base] = val


def lid(l):
    return l[0] if isinstance(l, (list, tuple)) else l["id"]


def load_links(container):
    """normalise both link encodings to the dict form"""
    out = {}
    for l in container.get("links", []) or []:
        if isinstance(l, (list, tuple)):
            out[l[0]] = {"id": l[0], "origin_id": l[1], "origin_slot": l[2],
                         "target_id": l[3], "target_slot": l[4]}
        else:
            out[l["id"]] = l
    return out


def convert(wf):
    api = {}
    subgraphs = {d["id"]: (i, d) for i, d in enumerate(
        (wf.get("definitions", {}) or {}).get("subgraphs", []) or [])}
    top_links = load_links(wf)

    def widget_pairs(node):
        """(name, value) for every widget the node has.

        `widgets_values` is positional over the node's full widget list, which
        also holds widgets the frontend adds itself and never declares -- the
        seed's "randomize"/"fixed" control is the usual one. Walk the declared
        widgets in order and drop any value the declared type or combo options
        reject, which is exactly what those extra slots look like.
        """
        vals = list(node.get("widgets_values") or [])
        s = SCHEMA.get(node["type"]) or {}
        types, opts, dyn = s.get("wtypes", {}), s.get("wopts", {}), s.get("wdyn", {})

        def fits(name, v):
            t = types.get(name)
            if t in ("INT",):
                return isinstance(v, int) and not isinstance(v, bool)
            if t == "FLOAT":
                return isinstance(v, (int, float)) and not isinstance(v, bool)
            if t == "STRING":
                return isinstance(v, str)
            if t == "BOOLEAN":
                return isinstance(v, bool)
            if t == "COMBO":
                o = opts.get(name)
                return v in o if o else isinstance(v, (str, int, float, bool))
            return True

        out, pos = [], 0
        for n in s.get("widgets", []):
            while pos < len(vals) and not fits(n, vals[pos]):
                pos += 1
            if pos >= len(vals):
                break
            v = vals[pos]
            pos += 1
            # a dynamic combo sends its key flat, plus one dotted input per sub-widget
            subs = dyn.get(n, {}).get(v)
            out.append((n, v))
            for sn in subs or ():
                if pos >= len(vals):
                    break
                out.append((f"{n}.{sn}", vals[pos]))
                pos += 1
        return out

    def add(key, node, links, resolve_origin):
        cls = node["type"]
        spec = {"class_type": cls, "inputs": {}}
        for i in node.get("inputs") or []:
            if i.get("link") is None:
                continue
            val = resolve_origin(links[i["link"]])
            if val is not None:
                put(spec["inputs"], cls, i["name"], val)
        for name, val in widget_pairs(node):
            spec["inputs"].setdefault(name, val)
        api[key] = spec

    top_fmt = lambda nid: "t%d" % nid

    instance_outputs = {}       # (instance node id, output slot) -> api value
    for node in wf.get("nodes", []):
        if node.get("type") not in subgraphs:
            continue
        si, sg = subgraphs[node["type"]]
        fmt = lambda nid, si=si: "s%d_%s" % (si, nid)
        s_links = load_links(sg)

        # interface slot -> value (None means "left unconnected on purpose")
        iface = [None] * len(sg["inputs"])
        vals = list(node.get("widgets_values") or [])
        n = 0
        for idx, spec in enumerate(sg["inputs"]):
            if spec["type"] in WIDGET_TYPES:
                iface[idx] = vals[n] if n < len(vals) else None
                n += 1
        for i in node.get("inputs") or []:
            if i.get("link") is None:
                continue
            o = top_links[i["link"]]
            idx = next(k for k, s in enumerate(sg["inputs"]) if s["name"] == i["name"])
            iface[idx] = instance_outputs.get((o["origin_id"], o["origin_slot"])) or [top_fmt(o["origin_id"]), o["origin_slot"]]

        def resolve(l, _fmt=fmt, _iface=iface):
            if l["origin_id"] == -10:
                return _iface[l["origin_slot"]]
            return [_fmt(l["origin_id"]), l["origin_slot"]]

        for n_ in sg.get("nodes", []):
            add(fmt(n_["id"]), n_, s_links, resolve)

        for l in s_links.values():
            if l.get("target_id") == -20:
                instance_outputs[(node["id"], l["target_slot"])] = [fmt(l["origin_id"]), l["origin_slot"]]

    for node in wf.get("nodes", []):
        if node.get("type") in subgraphs or node.get("type") == "MarkdownNote":
            continue
        fmt = top_fmt

        def resolve(l, _fmt=fmt):
            return instance_outputs.get((l["origin_id"], l["origin_slot"])) or [_fmt(l["origin_id"]), l["origin_slot"]]

        add(fmt(node["id"]), node, top_links, resolve)

    return api


def prune(api, out_classes):
    """drop nodes that no output node depends on, the way ComfyUI would"""
    def refs(v):
        return [v[0]] if isinstance(v, list) and v and isinstance(v[0], str) else []

    keep, stack = set(), [k for k, v in api.items() if v["class_type"] in out_classes]
    while stack:
        k = stack.pop()
        if k in keep or k not in api:
            continue
        keep.add(k)
        for v in api[k]["inputs"].values():
            stack.extend(refs(v))
    return {k: v for k, v in api.items() if k in keep}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    raw = json.load(open(src, encoding="utf-8"))
    out_classes = {n for n, s in SCHEMA.items() if s.get("output_node")}
    api = prune(convert(raw), out_classes)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(api, f, ensure_ascii=False, indent=1)
    print("%s -> %d nodes" % (src.rsplit("\\", 1)[-1], len(api)))
    for k in sorted(api, key=lambda x: (x[0], int("".join(c for c in x if c.isdigit()) or 0))):
        v = api[k]
        short = {n: (x if len(str(x)) < 46 else str(x)[:43] + "...")
                 for n, x in v["inputs"].items()}
        print("  %-9s %-22s %s" % (k, v["class_type"], json.dumps(short, ensure_ascii=False)[:240]))
