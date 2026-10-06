# -*- coding: utf-8 -*-
"""Generate the Q8_0 set of the Qwen-Image 2.1 workflows.

Each Q4_K_M workflow in the user directory is copied and only the
UnetLoaderGGUF model reference is switched to qwen-image-2.1-UC-Q8_0.gguf.
Everything else -- CLIP, VAE, PE, the shift node just added, sampler
settings -- stays identical, so the Q4 and Q8 sets differ by exactly one
value.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\localAI\ComfyUI-last"
WF = os.path.join(ROOT, r"ComfyUI_windows_portable\ComfyUI\user\default\workflows")
Q4 = "qwen-image-2.1-UC-Q4_K_M.gguf"
Q8 = "qwen-image-2.1-UC-Q8_0.gguf"

FILES = [
    "qwen_image_2_1_t2i_gguf.json",
    "qwen_image_2_1_image_edit_gguf.json",
    "qwen_image_2_1_background_removal_gguf.json",
]


def swap(path, out):
    d = json.load(open(path, encoding="utf-8"))
    changed = 0
    for g in d.get("definitions", {}).get("subgraphs", []):
        for n in g.get("nodes", []):
            if n.get("type") != "UnetLoaderGGUF":
                continue
            wv = n.get("widgets_values") or []
            for i, v in enumerate(wv):
                if v == Q4:
                    wv[i] = Q8
                    changed += 1
            n["widgets_values"] = wv
            # widgets_values_named 也要同步
            nm = n.get("widgets_values_named")
            if isinstance(nm, dict):
                for k, v in nm.items():
                    if v == Q4:
                        nm[k] = Q8
                        changed += 1
    if changed == 0:
        return "未找到 Q4_K_M 引用，跳过"
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return "已切换 %d 处 -> Q8_0" % changed


def verify(path):
    d = json.load(open(path, encoding="utf-8"))
    g = d["definitions"]["subgraphs"][0]
    ns = {n["id"]: n for n in g["nodes"]}
    unet = None
    for n in g["nodes"]:
        if n["type"] == "UnetLoaderGGUF":
            unet = (n.get("widgets_values") or [None])[0]
    ms = [n for n in g["nodes"] if n["type"] == "ModelSamplingAuraFlow"]
    chain = []
    for l in [x for x in g["links"] if x["type"] == "MODEL"]:
        o = ns.get(l["origin_id"])
        t = ns.get(l["target_id"])
        chain.append("%s->%s" % (o["type"] if o else "?", t["type"] if t else "?"))
    return unet, (ms[0]["widgets_values"][0] if ms else None), chain


for name in FILES:
    src = os.path.join(WF, name)
    dst = os.path.join(WF, name.replace("_gguf.json", "-Q8_0_gguf.json"))
    print("\n" + "=" * 96)
    print(name)
    print("  -> %s" % os.path.basename(dst))
    print("  处理: %s" % swap(src, dst))
    unet, shift, chain = verify(dst)
    print("  unet  = %s" % unet)
    print("  shift = %s" % shift)
    print("  链路  = %s" % " | ".join(chain))

print("\n完成")