# -*- coding: utf-8 -*-
"""Qwen-Image 2.1 生图 CK 注意力 A/B 探针.

只跑「短提示词 / 长提示词」两张图, 除提示词长度外所有节点参数相同.
两臂(python main.py 加不加 --use-ck-attention)用同一份脚本、同一 seed,
差异只能来自 attention 后端.

跳过工作流自带的 PE 扩写器(TextGenerate), 因为它的随机扩写会让两臂输入不一致.

用法:
  python qwen_ck_ab.py --tag ck   --out-dir D:\\...\\ck_ab_qwen
  (换 no_ck 启动脚本后)
  python qwen_ck_ab.py --tag nock --out-dir D:\\...\\ck_ab_qwen
"""
import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

COMFY_OUTPUT = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\output"

SHORT_PROMPT = (
    "Studio portrait of a woman in a red wool coat standing in front of a plain grey wall, "
    "soft diffused daylight from the left, sharp focus on her face, muted colour palette"
)

LONG_PROMPT = (
    "Studio portrait of a woman in a heavy red wool coat with a wide notched lapel and horn buttons, "
    "standing three-quarters turned toward the camera in front of a plain matte grey seamless backdrop. "
    "Soft diffused daylight enters from a large window on the left, wrapping her face in gentle gradient, "
    "while a subtle silver reflector on the right lifts the shadow side so no detail is lost in the folds of the coat. "
    "Her dark hair is pulled back loosely, a few strands catching the light, and her expression is calm, "
    "direct and unsmiling, eyes fixed on the lens. The coat fabric reads as dense felted wool: individual fibres, "
    "tiny pills near the cuff, the faint sheen along the shoulder seam, the slight compression where a button pulls. "
    "Under the coat she wears a fine charcoal turtleneck, its ribbed knit visible at the collar. "
    "The camera sits at eye level, an eighty-five millimetre lens at f2.8, so her shoulders fall gently out of focus "
    "while the coat buttons stay razor sharp. The backdrop is uneven in tone, slightly warmer at the top left, "
    "cooler toward the bottom right, with a barely visible seam running vertically behind her. "
    "Colour grading is restrained and muted: desaturated reds, neutral greys, skin kept natural with visible pores "
    "and a little shine on the forehead. The overall image should feel like a quiet editorial fashion portrait, "
    "restrained, tactile and honest, with nothing staged or glossy, no props, no text anywhere in the frame."
)

CASES = [("short", SHORT_PROMPT), ("long", LONG_PROMPT)]


def build(prompt, seed, prefix):
    return {
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": "qwen-image-2.1-UC-Q4_K_M.gguf"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors",
                         "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow",
              "inputs": {"model": ["1", 0], "shift": 3.1, "sampling": "flow"}},
        "5": {"class_type": "QwenImage21Cache",
              "inputs": {"model": ["4", 0], "device": "auto", "dtype": "default"}},
        "6": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": "",
                         "vae": ["3", 0], "resolution": 1024, "images": {}}},
        "7": {"class_type": "EmptyLatentImage",
              "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["5", 0], "positive": ["6", 0], "negative": ["6", 1],
                         "latent_image": ["7", 0], "seed": seed, "steps": 25, "cfg": 1,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": prefix}},
    }


def submit(graph):
    body = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(API + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.loads(OPENER.open(req, timeout=30).read())


def wait_done(pid, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(OPENER.open(API + "/history/" + pid, timeout=20).read())
        if pid in h:
            return h[pid]
        time.sleep(3)
    raise TimeoutError("prompt %s not finished in %ss" % (pid, timeout))


def collect(entry, dest):
    saved = []
    for node_out in entry.get("outputs", {}).values():
        for img in node_out.get("images", []):
            src = os.path.join(COMFY_OUTPUT, img.get("subfolder", ""), img["filename"])
            if not os.path.isfile(src):
                continue
            os.makedirs(dest, exist_ok=True)
            dst = os.path.join(dest, os.path.basename(src))
            shutil.copy2(src, dst)
            saved.append(dst)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="臂名, 如 ck / nock")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=20261022)
    args = ap.parse_args()

    for label, prompt in CASES:
        prefix = "ckab_%s_%s" % (args.tag, label)
        graph = build(prompt, args.seed, prefix)
        print("== %s / %s  (prompt chars=%d)" % (args.tag, label, len(prompt)))
        t0 = time.time()
        try:
            res = submit(graph)
        except urllib.error.HTTPError as e:
            print("   HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:1500]))
            sys.exit(1)
        pid = res["prompt_id"]
        entry = wait_done(pid)
        dt = time.time() - t0
        files = collect(entry, args.out_dir)
        status = entry.get("status", {})
        print("   %s  %.1fs  files=%s  status=%s" % (
            pid[:8], dt, [os.path.basename(f) for f in files], status.get("status_str")))
        for f in files:
            print("   ->", f)
    print("done.")


if __name__ == "__main__":
    main()
