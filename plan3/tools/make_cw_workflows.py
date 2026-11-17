"""在 molbal_workflows_int8 的四条 UI 工作流里插入 MiniMaxH3ContextWindows。

新开一套目录（molbal_workflows_int8_cw），源工作流一个字节都不动。
插法：loader 的 MODEL 输出 -> 窗口节点 -> HyperFlowSigmas.model / BasicGuider.model，
其余连线、widget 全部原样保留。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "molbal_workflows_int8")
DST = os.path.join(HERE, "..", "molbal_workflows_int8_cw")

CTX_LEN, CTX_OVERLAP = 124, 39
FUSE, FREENOISE, SPLIT = "pyramid", True, False


def insert(node_graph):
    nodes, links = node_graph["nodes"], node_graph["links"]
    loader = next((n for n in nodes
                   if n["type"].endswith("Loader")
                   and any(o["name"] == "MODEL" for o in n.get("outputs", []))), None)
    if loader is None:
        raise SystemExit("找不到输出 MODEL 的 loader")
    slot = [o["name"] for o in loader["outputs"]].index("MODEL")

    # loader 的第 slot 个输出原本直接喂给 guider / sigmas，现在全部改接到窗口节点
    moved = [l for l in links if l[1] == loader["id"] and l[2] == slot]
    if not moved:
        raise SystemExit("loader 的 MODEL 没有下游连线")

    nid, lid = node_graph["last_node_id"] + 1, node_graph["last_link_id"] + 1
    for l in moved:
        l[1], l[2] = nid, 0
    loader["outputs"][slot]["links"] = [lid]

    nodes.append({
        "id": nid, "type": "MiniMaxH3ContextWindows", "pos": [340, 420], "size": [320, 150],
        "flags": {}, "order": max(n.get("order", 0) for n in nodes) + 1, "mode": 0,
        "inputs": [{"name": "model", "type": "MODEL", "link": lid}],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": [l[0] for l in moved],
                     "slot_index": 0}],
        "properties": {"Node name for S&R": "MiniMaxH3ContextWindows"},
        "widgets_values": [CTX_LEN, CTX_OVERLAP, FUSE, FREENOISE, SPLIT],
    })
    links.append([lid, loader["id"], slot, nid, 0, "MODEL"])
    node_graph["last_node_id"], node_graph["last_link_id"] = nid, lid
    return loader["id"], len(moved)


def check(node_graph):
    """连线自洽：每条 link 的终点都在目标节点的对应输入槽上，没有悬空。"""
    by_id = {n["id"]: n for n in node_graph["nodes"]}
    for lid, src, sslot, dst, dslot, ltype in node_graph["links"]:
        assert src in by_id and dst in by_id, "link %d 指向不存在的节点" % lid
        assert by_id[dst]["inputs"][dslot]["link"] == lid, "link %d 未挂在输入槽上" % lid
    for n in node_graph["nodes"]:
        for o in n.get("outputs", []):
            for lid in (o.get("links") or []):
                assert any(l[0] == lid and l[1] == n["id"] for l in node_graph["links"]), \
                    "节点 %d 的输出记了不存在的 link %d" % (n["id"], lid)


def main():
    os.makedirs(DST, exist_ok=True)
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(SRC, fn), encoding="utf-8") as fh:
            wf = json.load(fh)
        loader_id, n = insert(wf)
        check(wf)
        out = os.path.join(DST, fn)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(wf, fh, ensure_ascii=False, indent=2)
        print("%-40s loader=%d 改接 %d 条 -> 窗口节点 %d/%d/%s"
              % (fn, loader_id, n, CTX_LEN, CTX_OVERLAP, FUSE))


if __name__ == "__main__":
    main()
