# -*- coding: utf-8 -*-
"""H3 ck-attention A/B 专用探针（只增, 不改动 plan\\bat\\ 内任何现有脚本）.

为什么不用 gen_h3_multisegment-8b.py:
  它末尾的 concat_segments() 无论几段都会用 libx264 重编码一遍 (CRF 23),
  等于在「生成差异」之上再叠一层有损压缩, 削弱比对的灵敏度.
  本探针复刻完全相同的图 (同模型/同 sampler/同 scheduler/同 steps/同 seed),
  只多挂一个 SaveImage 把 VAEDecode 出来的帧以**无损 PNG** 落盘, 并跳过重编码.
  这样比对的输入就是解码器输出本身, 不含任何二次有损.

与 ck 相关的唯一变量是 ComfyUI 启动 flag, 图本身逐节点相同, 所以两臂跑的是
同一份代码、同一份 prompt、同一 seed —— 差异只能来自 attention 后端.

用法:
  python gen_h3_ck_ab.py --tag ck      --seed 1234 --duration 5 --steps 20
  # (换 no_ck 启动脚本后)
  python gen_h3_ck_ab.py --tag nock    --seed 1234 --duration 5 --steps 20
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

API = "http://127.0.0.1:8188"

# 与 plan\bat\multisegment_8b\gen_h3_multisegment-8b.py 逐字一致
GGUF_UNET = "minimax_h3_fl2va_pruned-Q4_K_M.gguf"
CLIP_NAME = "qwen3vl_8b_fp8_scaled.safetensors"
CLIP_TYPE = "boogu"
CLIP_PROJ = "mmh3-8b-ClipProj-v3.1.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
DEFAULT_SIZE = (864, 480)


def frames_for(duration):
    base = max(5, round(duration * 24))
    return base + (5 - base % 17) % 17


def build_graph(prompt, width, height, length, steps, seed, tag):
    """与 gen_h3_multisegment-8b.py 的 build_graph 同构, 额外挂 SaveImage(无损帧)."""
    n = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": GGUF_UNET}},
        "2": {"class_type": "CCTechClipProjLoader",
              "inputs": {"clip_name": CLIP_NAME, "type": CLIP_TYPE, "projection": CLIP_PROJ}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0],
            "prompt": prompt, "width": width, "height": height, "length": length}},
        "6": {"class_type": "ForceUnloadBeforeDecode", "inputs": {"latent": ["5", 1]}},
        "7": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["5", 0]}},
        "8": {"class_type": "BasicScheduler",
              "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": steps, "denoise": 1}},
        "9": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["10", 0], "guider": ["7", 0], "sampler": ["9", 0],
            "sigmas": ["8", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "ForceUnloadBeforeDecode", "inputs": {"latent": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["12", 0], "vae": ["4", 0]}},
        "15": {"class_type": "CreateVideo",
               "inputs": {"images": ["13", 0], "fps": 24, "audio": ["14", 0], "bit_depth": 8}},
        "16": {"class_type": "SaveVideo",
               "inputs": {"video": ["15", 0], "filename_prefix": "ck_ab/%s_video" % tag,
                          "format": "auto"}},
        # 与采样/解码无关的旁路, 只为拿到无损 PNG 帧
        "17": {"class_type": "SaveImage",
               "inputs": {"images": ["13", 0], "filename_prefix": "ck_ab/%s" % tag}},
    }
    return n


def free_vram():
    req = urllib.request.Request(
        API + "/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print("  /free 忽略:", e)


def submit(graph):
    req = urllib.request.Request(
        API + "/prompt", data=json.dumps({"prompt": graph}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("提交失败 %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:2000]))
    if resp.get("node_errors"):
        raise RuntimeError("节点报错: " + json.dumps(resp["node_errors"], ensure_ascii=False)[:2000])
    return resp["prompt_id"]


def wait(pid, label=""):
    t0 = time.time()
    dots = 0
    while True:
        try:
            h = json.loads(urllib.request.urlopen("%s/history/%s" % (API, pid), timeout=10).read())
        except Exception:
            h = {}
        if h.get(pid):
            st = h[pid].get("status", {})
            if st.get("status_str") == "error" or st.get("completed") is False and st.get("messages"):
                err = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                if err:
                    raise RuntimeError("执行错误: " + json.dumps(err, ensure_ascii=False)[:2000])
            out = h[pid].get("outputs", {})
            if out:
                return out
        el = time.time() - t0
        if el % 15 < 1.2:
            dots += 1
            print("    %s 已等待 %5.0fs ..." % (label, el), flush=True)
        if el > 7200:
            raise RuntimeError("超时 2h")
        time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser(description="H3 ck-attention A/B 探针 (无损帧)")
    ap.add_argument("--tag", required=True, help="臂标识, 决定输出前缀, 如 ck / nock / ck_rerun")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--size", default="864x480")
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--sampler", default="res_multistep")
    ap.add_argument("--scheduler", default="simple")
    a = ap.parse_args()

    with open(a.prompt_file, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            prompt = raw.decode(enc)
            used_enc = enc
            break
        except UnicodeDecodeError:
            continue
    prompt = prompt.strip()
    w, h = (int(x) for x in a.size.lower().split("x"))
    length = frames_for(a.duration)

    stats = json.loads(urllib.request.urlopen(API + "/system_stats", timeout=10).read())
    print("=" * 68)
    print("臂 tag          : %s" % a.tag)
    print("ComfyUI         : %s" % stats["system"]["comfyui_version"])
    print("prompt          : %s (%d 字符, 解码 %s)" % (os.path.basename(a.prompt_file), len(prompt), used_enc))
    print("参数            : %dx%d, %.1fs = %d 帧, %d 步, %s/%s, seed=%d"
          % (w, h, a.duration, length, a.steps, a.sampler, a.scheduler, a.seed))
    print("=" * 68)

    free_vram()
    graph = build_graph(prompt, w, h, length, a.steps, a.seed, a.tag)
    graph["9"]["inputs"]["sampler_name"] = a.sampler
    graph["8"]["inputs"]["scheduler"] = a.scheduler

    t0 = time.time()
    pid = submit(graph)
    print("prompt_id: %s" % pid)
    outputs = wait(pid, a.tag)
    el = time.time() - t0
    print("\n完成, 用时 %.1fs (%.2f min)" % (el, el / 60))

    manifest = {"tag": a.tag, "prompt_id": pid, "seed": a.seed, "steps": a.steps,
                "size": [w, h], "length": length, "duration": a.duration,
                "sampler": a.sampler, "scheduler": a.scheduler,
                "prompt_sha256": __import__("hashlib").sha256(prompt.encode("utf-8")).hexdigest(),
                "elapsed_sec": round(el, 1),
                "outputs": {k: v for k, v in outputs.items()}}
    mp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "run_%s.json" % a.tag)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("清单: %s" % mp)
    for nid, o in outputs.items():
        imgs = o.get("images", [])
        vids = o.get("gifs", []) or []
        print("  节点 %s: images=%d  videos=%d" % (nid, len(imgs), len(vids)))
        for im in imgs[:3]:
            print("     - %s" % im.get("filename"))
        if len(imgs) > 3:
            print("     ... 共 %d 张 PNG" % len(imgs))


if __name__ == "__main__":
    sys.exit(main())
