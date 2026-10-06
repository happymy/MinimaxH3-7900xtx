# -*- coding: utf-8 -*-
"""Insert ModelSamplingAuraFlow(shift=3.1) into every Qwen-Image 2.1 workflow.

Matches the official blueprint's "Text to Image (Qwen-Image)" placement: the
shift node is the last model patch before the KSampler. In these workflows that
slot sits between QwenImage21Cache and the sampler, so the chain becomes

    UnetLoaderGGUF -> QwenImage21Cache -> ModelSamplingAuraFlow -> KSampler

Each file is backed up before touching it, and skipped if it already has the
node.
"""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\localAI\ComfyUI-last"
WF = os.path.join(ROOT, r"ComfyUI_windows_portable\ComfyUI\user\default\workflows")

FILES = [
    ("文生图", "qwen_image_2_1_t2i_gguf.json"),
    ("图像编辑", "qwen_image_2_1_image_edit_gguf.json"),
    ("背景移除", "qwen_image_2_1_background_removal_gguf.json"),
]

SHIFT = 3.1000000000000005


def node_props():
    return {
        "cnr_id": "comfy-core",
        "ver": "0.3.48",
        "Node name for S&R": "ModelSamplingAuraFlow",
        "enableTabs": False,
        "tabWidth": 65,
        "tabXOffset": 10,
        "hasSecondTab": False,
        "secondTabText": "Send Back",
        "secondTabOffset": 80,
        "secondTabWidth": 65,
    }


def patch(path):
    d = json.load(open(path, encoding="utf-8"))
    subs = d.get("definitions", {}).get("subgraphs", [])
    if not subs:
        return "无子图，跳过"

    g = subs[0]
    if any(n["type"] == "ModelSamplingAuraFlow" for n in g["nodes"]):
        return "已有 shift，跳过"

    # 找 QwenImage21Cache 与 KSampler 之间的那根 MODEL 连线
    by_id = {n["id"]: n for n in g["nodes"]}
    cache_id = ks_id = None
    for l in g["links"]:
        if l["type"] != "MODEL":
            continue
        o, t = by_id.get(l["origin_id"]), by_id.get(l["target_id"])
        if o and t and o["type"] == "QwenImage21Cache" and t["type"] == "KSampler":
            cache_id, ks_id = l["origin_id"], l["target_id"]
            break
    if cache_id is None:
        return "未找到 Cache->KSampler 连线，跳过"

    new_id = g.get("state", {}).get("lastNodeId", 0) + 1
    link_a = g.get("state", {}).get("lastLinkId", 0) + 1
    link_b = link_a + 1

    # 1) Cache 输出改指到新节点
    by_id[cache_id]["outputs"][0]["links"] = [link_a]

    # 2) 原连线重定义为 Cache -> 新节点
    for l in g["links"]:
        if l["origin_id"] == cache_id and l["target_id"] == ks_id and l["type"] == "MODEL":
            l.update({"id": link_a, "target_id": new_id, "target_slot": 0})
            break

    # 3) 新增 新节点 -> KSampler
    g["links"].append({"id": link_b, "origin_id": new_id, "origin_slot": 0,
                       "target_id": ks_id, "target_slot": 0, "type": "MODEL"})

    # 4) KSampler 的 model 输入指向新连线
    for inp in by_id[ks_id]["inputs"]:
        if inp["name"] == "model":
            inp["link"] = link_b
            break

    # 5) 插入节点，字段照官方 blueprint 序列化
    by_id[cache_id]["order"] = len(g["nodes"]) - 1
    g["nodes"].append({
        "id": new_id,
        "type": "ModelSamplingAuraFlow",
        "pos": [1450, 460],
        "size": [300, 110],
        "flags": {},
        "order": len(g["nodes"]),
        "mode": 0,
        "inputs": [
            {"localized_name": "model", "name": "model", "type": "MODEL", "link": link_a},
            {"localized_name": "shift", "name": "shift", "type": "FLOAT",
             "widget": {"name": "shift"}, "link": None},
        ],
        "outputs": [
            {"localized_name": "MODEL", "name": "MODEL", "type": "MODEL",
             "slot_index": 0, "links": [link_b]},
        ],
        "properties": node_props(),
        "widgets_values": [SHIFT],
    })

    g.setdefault("state", {})
    g["state"]["lastNodeId"] = new_id
    g["state"]["lastLinkId"] = link_b

    shutil.copy2(path, path + ".pre-shift31.bak")
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return "已插入 id=%d link=%d/%d" % (new_id, link_a, link_b)


def verify(path):
    g = json.load(open(path, encoding="utf-8"))["definitions"]["subgraphs"][0]
    ns = {n["id"]: n for n in g["nodes"]}
    ms = [n for n in g["nodes"] if n["type"] == "ModelSamplingAuraFlow"]
    if not ms:
        return "校验失败: 无 shift 节点", []
    chain = []
    for l in sorted([x for x in g["links"] if x["type"] == "MODEL"], key=lambda x: x["id"]):
        chain.append("%s->%s" % (ns[l["origin_id"]]["type"], ns[l["target_id"]]["type"]))
    return "shift=%s" % ms[0]["widgets_values"], chain


for tag, name in FILES:
    p = os.path.join(WF, name)
    print("\n" + "=" * 90)
    print("%s  %s" % (tag, name))
    print("  处理: %s" % patch(p))
    st, chain = verify(p)
    print("  校验: %s" % st)
    print("  链路: %s" % " | ".join(chain))

print("\n完成")