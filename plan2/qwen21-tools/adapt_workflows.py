"""Re-adapt the official Comfy-Org Qwen-Image 2.1 workflow templates to the
abenzerps GGUF DiT. Reads the installed comfyui-workflow-templates JSONs
(0.11.70) so the delivered workflows track whatever upstream ships."""
import json, os, re, shutil, sys

TPL = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\python_embeded\Lib\site-packages\comfyui_workflow_templates_json\templates"
WF = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\user\default\workflows"

GGUF = "qwen-image-2.1-UC-Q4_K_M.gguf"
GGUF_URL = "https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-GGUF/resolve/main/" + GGUF
GGUF_REPO = "https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-GGUF"

TASKS = [
    ("image_qwen_image_2_1_t2i.json", "qwen_image_2_1_t2i_gguf.json"),
    ("image_qwen_image_2_1_image_edit.json", "qwen_image_2_1_image_edit_gguf.json"),
    ("image_qwen_image_2_1_background_removal.json", "qwen_image_2_1_background_removal_gguf.json"),
]

DIT_BULLET = ("- [%s](%s) — uncensored Q4_K_M GGUF, loaded by the **UNET Loader (GGUF)** "
              "node instead of UNETLoader" % (GGUF, GGUF_URL))


def adapt(path):
    w = json.load(open(path, encoding="utf-8"))
    changes = []

    for sg in (w.get("definitions", {}) or {}).get("subgraphs", []) or []:
        unet = next((n for n in sg.get("nodes", []) if n.get("type") == "UNETLoader"), None)
        if unet is None:
            continue

        unet["type"] = "UnetLoaderGGUF"
        props = unet.setdefault("properties", {})
        props["Node name for S&R"] = "UnetLoaderGGUF"
        props["models"] = [{"name": GGUF, "url": GGUF_URL, "directory": "diffusion_models"}]
        unet["widgets_values"] = [GGUF]
        unet["widgets_values_named"] = {"unet_name": GGUF}
        changes.append("subgraph node %s UNETLoader -> UnetLoaderGGUF" % unet["id"])

        # the unet_name widget is fed by the subgraph's own interface, so the
        # top-level instance must carry the GGUF at the same slot
        slot = next(l["origin_slot"] for l in sg["links"]
                    if l.get("target_id") == unet["id"] and l.get("target_slot") == 0)
        inst = next(n for n in w["nodes"] if n["type"] == sg["id"])
        old = inst["widgets_values"][slot]
        inst["widgets_values"][slot] = GGUF
        changes.append("instance widgets_values[%d] %s -> %s" % (slot, old, GGUF))

    for n in w.get("nodes", []):
        if n.get("type") != "MarkdownNote":
            continue
        vals = n.get("widgets_values") or []
        if not vals:
            continue
        txt = vals[0]
        if "## Model Links" not in txt:
            continue
        new, cnt = re.subn(r"(\*\*diffusion_models\*\*\n\n)(?:- .*\n?)+", r"\1" + DIT_BULLET + "\n", txt)
        if not cnt:
            continue
        new, c2 = re.subn(r"(\*\*diffusion_models\*\*\n\n)(?:- .*\n?)+",
                          r"\1" + DIT_BULLET + "\n", new)
        if c2:
            new = new.replace("- [ModelScope:Comfy-Org/Qwen-Image-2.1](https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1)",
                              "- [ModelScope:Comfy-Org/Qwen-Image-2.1](https://modelscope.cn/models/Comfy-Org/Qwen-Image-2.1)\n"
                              "- [Hugging Face:abenzerps/Qwen-Image-2.1-Uncensored-GGUF](%s)" % GGUF_REPO)
        vals[0] = new
        n["widgets_values"] = vals
        changes.append("note %s: diffusion_models section -> GGUF" % n["id"])

    return w, changes


def check(w):
    """graph integrity: no dangling links, and no leftover UNETLoader anywhere."""
    bad = []

    def links_of(container):
        out = set()
        for l in container.get("links", []) or []:
            out.add(l[0] if isinstance(l, (list, tuple)) else l.get("id"))
        return out

    def scan(nodes, ids, where):
        for n in nodes:
            for inp in n.get("inputs", []) or []:
                if inp.get("link") is not None and inp["link"] not in ids:
                    bad.append("%s node %s input %s -> missing link %s" % (where, n.get("id"), inp.get("name"), inp["link"]))
            if n.get("type") == "UNETLoader":
                bad.append("%s node %s still UNETLoader" % (where, n.get("id")))

    scan(w.get("nodes", []), links_of(w), "top")
    n_gguf = 0
    for sg in (w.get("definitions", {}) or {}).get("subgraphs", []) or []:
        scan(sg.get("nodes", []), links_of(sg), "subgraph %s" % sg.get("name"))
        n_gguf += sum(1 for n in sg.get("nodes", []) if n.get("type") == "UnetLoaderGGUF")
    if n_gguf != 1:
        bad.append("expected exactly 1 UnetLoaderGGUF, found %d" % n_gguf)
    return bad


rc = 0
for src, dst in TASKS:
    sp = os.path.join(TPL, src)
    if not os.path.exists(sp):
        print("MISSING TEMPLATE: " + sp)
        rc = 1
        continue
    w, changes = adapt(sp)
    bad = check(w)
    dp = os.path.join(WF, dst)
    if os.path.exists(dp):
        shutil.copy2(dp, dp + ".bak")
    with open(dp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(w, f, ensure_ascii=False, indent=2)
    print("%-42s -> %s  (%d B)" % (src, dst, os.path.getsize(dp)))
    for c in changes:
        print("    " + c)
    for b in bad:
        rc = 1
        print("    ! " + b)
    if not bad:
        print("    graph OK")

sys.exit(rc)
