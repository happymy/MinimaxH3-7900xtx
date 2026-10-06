import json, os, sys

WF = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\user\default\workflows"
MODELS = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\models"
FILES = [
    "qwen_image_2_1_t2i_gguf.json",
    "qwen_image_2_1_image_edit_gguf.json",
    "qwen_image_2_1_background_removal_gguf.json",
]

fail = 0
for fn in FILES:
    p = os.path.join(WF, fn)
    w = json.load(open(p, encoding="utf-8"))
    link_ids = {(l[0] if isinstance(l,(list,tuple)) else l.get("id")) for l in w.get("links", [])}
    problems = []

    # every node input link must exist
    def scan(nodes, where, problems):
        for n in nodes:
            for inp in n.get("inputs", []) or []:
                if inp.get("link") is not None and inp["link"] not in link_ids:
                    problems.append("%s: node %s input %s -> dangling link %s" %
                                    (where, n.get("id"), inp.get("name"), inp["link"]))
            if n.get("type") in ("MarkdownNote", "Note"):
                continue
    scan(w.get("nodes", []), "top", problems)

    def lid(l):
        return l[0] if isinstance(l, (list, tuple)) else l.get("id")

    for d in (w.get("definitions", {}) or {}).get("subgraphs", []) or []:
        sub_links = {lid(l) for l in d.get("links", [])}
        for n in d.get("nodes", []):
            for inp in n.get("inputs", []) or []:
                if inp.get("link") is not None and inp["link"] not in sub_links:
                    problems.append("subgraph %s: node %s input %s -> dangling link %s" %
                                    (d.get("name"), n.get("id"), inp.get("name"), inp["link"]))

    # collect model filenames referenced anywhere in widgets / properties
    blob = json.dumps(w, ensure_ascii=False)
    referenced = set()
    for sub in ("diffusion_models", "text_encoders", "vae"):
        d = os.path.join(MODELS, sub)
        for f in os.listdir(d):
            if f in blob and not f.startswith("put_"):
                referenced.add(os.path.join(sub, f))
    for r in sorted(referenced):
        if not os.path.exists(os.path.join(MODELS, r)):
            problems.append("missing model on disk: " + r)

    gguf = [n for n in w.get("nodes", []) if n.get("type") == "UnetLoaderGGUF"]
    for d in (w.get("definitions", {}) or {}).get("subgraphs", []) or []:
        gguf += [n for n in d.get("nodes", []) if n.get("type") == "UnetLoaderGGUF"]

    print("%-42s links=%-4d UnetLoaderGGUF=%d models=%d %s" %
          (fn, len(link_ids), len(gguf), len(referenced), "OK" if not problems else "FAIL"))
    for pr in problems:
        fail += 1
        print("    ! " + pr)

print("\nRESULT:", "all clean" if fail == 0 else "%d problems" % fail)
sys.exit(1 if fail else 0)
