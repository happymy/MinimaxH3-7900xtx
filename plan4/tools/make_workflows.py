# -*- coding: utf-8 -*-
"""生成 plan4 的 API payload 与 UI 工作流 JSON。

全部走标准 H3（不用 HyperFlow），与 bat/gen_sulphur.py 同一套节点与模型。
需要先启动 ComfyUI（读 /object_info 拿 widget 顺序与插槽类型）。

    python make_workflows.py

输出：
    API_workflows/sulphur_{t2v,i2v,flf2v,ref2v}.json   —— /prompt 的 inner graph
    workflows/sulphur_{t2v,i2v,flf2v,ref2v}.json       —— 可拖进 Desktop 的 UI 图
"""
import json
import os
import urllib.request

API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UNET = "Sulphur-3-Q4_K_M.gguf"
TE = "qwen3-vl-4b-heretic-Q4_K_M.gguf"
PROJ = "mmh3-4b-ClipProj-v3.1.safetensors"
TE8 = "qwen3vl_8b_int8_convrot.safetensors"
TE8H = "qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors"
PROJ8 = "mmh3-8b-ClipProj-v3.1.safetensors"
VVAE = "minimax_h3_video_vae_int8_convrot.safetensors"
AVAE = "minimax_h3_audio_vae_fp32.safetensors"
PROMPT_FILE = os.path.join(ROOT, "bat", "prompt.txt")
SEED = 3538674239439636468
W, H, LENGTH, STEPS = 864, 480, 124, 20

_INFO = {}


def info(node):
    if node not in _INFO:
        with OPENER.open(API + "/object_info/" + node, timeout=15) as r:
            _INFO[node] = json.load(r)[node]
    return _INFO[node]


def base_graph(te=TE, proj=PROJ, clip_cls="CLIPLoaderGGUF"):
    prompt = ""
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, encoding="utf-8") as f:
            prompt = f.read().strip()
    ctype = "krea2" if clip_cls == "CLIPLoaderGGUF" else "boogu"
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET}},
        "1b": {"class_type": "MiniMaxH3SigmaShift", "inputs": {
            "model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "2": {"class_type": clip_cls, "inputs": {"clip_name": te, "type": ctype}},
        "2b": {"class_type": "ClipProjApply", "inputs": {"clip": ["2", 0], "projection": proj}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VVAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AVAE}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2b", 0], "vae": ["3", 0], "prompt": prompt,
            "width": W, "height": H, "length": LENGTH}},
        "6": {"class_type": "ForceUnloadBeforeDecode", "inputs": {"latent": ["5", 1]}},
        "7": {"class_type": "BasicGuider", "inputs": {"model": ["1b", 0], "conditioning": ["5", 0]}},
        "8": {"class_type": "BasicScheduler", "inputs": {
            "model": ["1b", 0], "scheduler": "simple", "steps": STEPS, "denoise": 1}},
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": SEED}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["10", 0], "guider": ["7", 0], "sampler": ["9", 0],
            "sigmas": ["8", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "ForceUnloadBeforeDecode", "inputs": {"latent": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["12", 0], "vae": ["4", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {
            "images": ["13", 0], "fps": 24, "audio": ["14", 0], "bit_depth": 8}},
        "16": {"class_type": "SaveVideo", "inputs": {
            "video": ["15", 0], "filename_prefix": "video/Sulphur_H3", "format": "auto"}},
    }


def variants():
    out = {}
    configs = [
        ("", TE, PROJ, "CLIPLoaderGGUF"),
        ("_8b", TE8, PROJ8, "CLIPLoader"),
        ("_8b_heretic", TE8H, PROJ8, "CLIPLoader"),
    ]
    for suffix, te, proj, cls in configs:
        out["t2v" + suffix] = base_graph(te, proj, cls)

        i2v = base_graph(te, proj, cls)
        i2v["17"] = {"class_type": "LoadImage", "inputs": {"image": "example.png"}}
        i2v["5"]["inputs"]["first_frame"] = ["17", 0]
        out["i2v" + suffix] = i2v

        flf2v = base_graph(te, proj, cls)
        flf2v["17"] = {"class_type": "LoadImage", "inputs": {"image": "first.png"}}
        flf2v["18"] = {"class_type": "LoadImage", "inputs": {"image": "last.png"}}
        flf2v["5"]["inputs"]["first_frame"] = ["17", 0]
        flf2v["5"]["inputs"]["last_frame"] = ["18", 0]
        out["flf2v" + suffix] = flf2v

        ref2v = base_graph(te, proj, cls)
        ref2v["17"] = {"class_type": "LoadImage", "inputs": {"image": "reference.png"}}
        ref2v["19"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
            "positive": ["5", 0], "latent": ["5", 1], "vae": ["3", 0],
            "image": ["17", 0], "frame_idx": 0}}
        ref2v["7"]["inputs"]["conditioning"] = ["19", 0]
        out["ref2v" + suffix] = ref2v
    return out


def input_type(node, name):
    d = info(node)["input"]
    for group in ("required", "optional"):
        if name in d.get(group, {}):
            t = d[group][name]
            return t[0] if isinstance(t, list) else t
    return "*"


def api_to_ui(graph, title):
    """API graph（字符串 id）→ UI workflow（整数 id + links）。"""
    keys = sorted(graph, key=lambda k: (len(k), k))
    remap = {k: i + 1 for i, k in enumerate(keys)}
    nodes, links, pending = [], [], []
    link_id = 0

    for k in keys:
        node = graph[k]
        cls = node["class_type"]
        ins = node["inputs"]
        ndef = info(cls)
        order = ndef["input_order"]["required"] + ndef["input_order"].get("optional", [])
        ui_inputs, widgets = [], []
        for name in order:
            if name not in ins or name == "unique_id":
                continue
            v = ins[name]
            is_link = isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in graph
            if is_link:
                src, slot = v
                link_id += 1
                links.append([link_id, remap[src], slot, remap[k], len(ui_inputs), input_type(cls, name)])
                ui_inputs.append({"name": name, "type": input_type(cls, name), "link": link_id})
                pending.append((remap[src], slot, link_id))
            else:
                widgets.append(v)
        out_names = ndef.get("output_name") or ndef.get("output") or []
        ui_outputs = []
        for idx, name in enumerate(out_names):
            ui_outputs.append({"name": name, "type": (ndef.get("output") or [name])[idx], "links": []})
        nodes.append({
            "id": remap[k], "type": cls,
            "pos": [80 + (remap[k] % 4) * 300, 80 + (remap[k] // 4) * 260],
            "size": [270, 120], "flags": {}, "order": remap[k] - 1, "mode": 0,
            "inputs": ui_inputs, "outputs": ui_outputs,
            "properties": {"Node name for S&R": cls},
            "widgets_values": widgets,
        })

    for node in nodes:
        for idx, out in enumerate(node["outputs"]):
            out["links"] = [lid for (nid, s, lid) in pending if nid == node["id"] and s == idx]

    return {
        "id": title, "revision": 0,
        "last_node_id": max(remap.values()), "last_link_id": link_id,
        "nodes": nodes, "links": links, "groups": [],
        "config": {}, "extra": {}, "version": 0.4,
    }


def main():
    api_dir = os.path.join(ROOT, "API_workflows")
    ui_dir = os.path.join(ROOT, "workflows")
    os.makedirs(api_dir, exist_ok=True)
    os.makedirs(ui_dir, exist_ok=True)
    for name, graph in variants().items():
        with open(os.path.join(api_dir, "sulphur_%s.json" % name), "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=1)
        ui = api_to_ui(graph, "sulphur_%s" % name)
        with open(os.path.join(ui_dir, "sulphur_%s.json" % name), "w", encoding="utf-8") as f:
            json.dump(ui, f, ensure_ascii=False, indent=1)
        print("generated %s: %d nodes, %d links" % (name, len(ui["nodes"]), len(ui["links"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
