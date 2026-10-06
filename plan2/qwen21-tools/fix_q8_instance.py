# -*- coding: utf-8 -*-
"""Fix the Q8_0 Qwen-Image 2.1 workflows so the subgraph INSTANCE carries Q8_0.

These workflows serialize the whole parameter set twice:

  * top-level nodes[1] is a subgraph instance (type is a UUID). Its
    `widgets_values` array inlines every exposed input, unet included, at a
    position that varies per workflow (11 for t2i/bg, 12 for edit).
  * definitions.subgraphs[0].nodes[451] is the inner UnetLoaderGGUF holding the
    subgraph's own default.

The instance value overrides the inner default, so the instance is what the UI
shows and what actually runs. A previous pass only rewrote the inner node, which
left every Q8 file executing Q4_K_M.

This pass writes both locations and then cross-checks them against each other
plus against the matching Q4 file, so a half-applied edit cannot pass.
"""
import glob
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

WF = os.path.join(
    r"D:\localAI\ComfyUI-last",
    r"ComfyUI_windows_portable\ComfyUI\user\default\workflows",
)

Q4 = "qwen-image-2.1-UC-Q4_K_M.gguf"
Q8 = "qwen-image-2.1-UC-Q8_0.gguf"


def occurrences(doc, target):
    """Every place `target` sits as a whole widget value.

    An exact match only: the instance node's widgets_values[0] is a long prompt
    and several nodes carry a markdown model list that mentions the filenames
    inline, so a substring search would rewrite documentation text.
    """
    hits = []

    def scan(nodes, where):
        for n in nodes or []:
            for i, v in enumerate(n.get("widgets_values") or []):
                if v == target:
                    hits.append((where, n.get("id"), n.get("type"), i))
            nm = n.get("widgets_values_named")
            if isinstance(nm, dict):
                for k, v in nm.items():
                    if v == target:
                        hits.append((where, n.get("id"), n.get("type"), k))

    scan(doc.get("nodes", []), "instance")
    for g in doc.get("definitions", {}).get("subgraphs", []) or []:
        scan(g.get("nodes", []), "subgraph")
    return hits


def rewrite(path, old, new):
    doc = json.load(open(path, encoding="utf-8"))
    touched = 0

    def patch(nodes):
        n = 0
        for node in nodes or []:
            wv = node.get("widgets_values")
            if isinstance(wv, list):
                for i, v in enumerate(wv):
                    if v == old:
                        wv[i] = new
                        n += 1
            nm = node.get("widgets_values_named")
            if isinstance(nm, dict):
                for k, v in nm.items():
                    if v == old:
                        nm[k] = new
                        n += 1
        return n

    touched += patch(doc.get("nodes", []))
    for g in doc.get("definitions", {}).get("subgraphs", []) or []:
        touched += patch(g.get("nodes", []))

    if not touched:
        return 0
    shutil.copy2(path, path + ".pre-q8fix.bak")
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return touched


def report(path):
    doc = json.load(open(path, encoding="utf-8"))
    inst = occurrences(doc, Q8)
    inner = [h for h in inst if h[0] == "subgraph"]
    top = [h for h in inst if h[0] == "instance"]
    stale = occurrences(doc, Q4)
    return top, inner, stale


print("=" * 100)
print("1) 修正 Q8 文件: 实例节点 + 子图内部 都写 Q8_0")
print("=" * 100)
targets = sorted(
    f for f in glob.glob(os.path.join(WF, "qwen_image_2_1*Q8*.json")) if ".bak" not in f
)
for path in targets:
    n = rewrite(path, Q4, Q8)
    print("  %-46s 改写 %d 处" % (os.path.basename(path), n))

print()
print("=" * 100)
print("2) Q4 文件不动, 确认仍全是 Q4_K_M")
print("=" * 100)
for path in sorted(
    f
    for f in glob.glob(os.path.join(WF, "qwen_image_2_1*.json"))
    if ".bak" not in f and "Q8" not in os.path.basename(f)
):
    q8 = report(path)[2]
    print("  %-46s 残留 Q8_0 引用: %d %s" % (os.path.basename(path), len(q8), "OK" if not q8 else "!!"))

print()
print("=" * 100)
print("3) 交叉校验: Q8 文件两处都必须 Q8_0, 且无 Q4 残留")
print("=" * 100)
allok = True
for path in targets:
    top, inner, stale = report(path)
    ok = bool(top) and bool(inner) and not stale
    allok &= ok
    print("  %s" % os.path.basename(path))
    print("      实例节点 : %s" % (", ".join("id=%s[%s]" % (h[1], h[3]) for h in top) or "无"))
    print("      子图内部 : %s" % (", ".join("id=%s[%s]" % (h[1], h[3]) for h in inner) or "无"))
    print("      Q4 残留  : %d   %s" % (len(stale), "OK" if not stale else "!! 仍有 " + str(stale)))
    print("      判定     : %s" % ("✅ 一致" if ok else "❌ 不一致"))

print()
print("=" * 100)
print("4) Q4/Q8 配对: 除 unet 外应完全相同 (节点数/连线数/shift/模型其余项)")
print("=" * 100)


def shape(path):
    doc = json.load(open(path, encoding="utf-8"))
    subs = doc.get("definitions", {}).get("subgraphs", []) or []
    g = subs[0] if subs else {}
    nodes = list(doc.get("nodes", [])) + list(g.get("nodes", []))
    others = set()
    shift = None
    for n in nodes:
        if n.get("type") == "ModelSamplingAuraFlow":
            shift = (n.get("widgets_values") or [None])[0]
        for v in n.get("widgets_values") or []:
            if isinstance(v, str) and v.endswith((".safetensors", ".gguf")) and v not in (Q4, Q8):
                others.add(v)
    return len(nodes), len(g.get("links", []) or []), shift, others


pairs = [
    ("t2i", "qwen_image_2_1_t2i_gguf.json", "qwen_image_2_1_t2i-Q8_0_gguf.json"),
    ("image_edit", "qwen_image_2_1_image_edit_gguf.json", "qwen_image_2_1_image_edit-Q8_0_gguf.json"),
    ("bg", "qwen_image_2_1_background_removal_gguf.json", "qwen_image_2_1_background_removal-Q8_0_gguf.json"),
]
for tag, a, b in pairs:
    pa, pb = os.path.join(WF, a), os.path.join(WF, b)
    if not (os.path.exists(pa) and os.path.exists(pb)):
        print("  %-12s 文件缺失, 跳过" % tag)
        continue
    na, la, sa, oa = shape(pa)
    nb, lb, sb, ob = shape(pb)
    same = (na == nb) and (la == lb) and (sa == sb) and (oa == ob)
    allok &= same
    print("  %-12s 节点 %d==%d  连线 %d==%d  shift %s==%s  其余模型 %s  %s"
          % (tag, na, nb, la, lb, sa, sb, "同" if oa == ob else "异",
             "OK" if same else "!!"))

print()
print("最终: %s" % ("✅ 全部通过" if allok else "❌ 仍有问题"))
