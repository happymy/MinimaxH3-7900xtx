# -*- coding: utf-8 -*-
"""提交 API_workflows 的任意图（t2v / i2v / flf2v / ref2v）。

复用 gen_sulphur 的 submit/wait/download/concat，不重复实现。

    python run_workflow.py t2v --prompt-file prompt.txt --out out.mp4
    python run_workflow.py i2v --image ref.png --prompt-file prompt.txt
    python run_workflow.py flf2v --image first.png --last-image last.png
    python run_workflow.py ref2v --image ref.png
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_sulphur as gs

ROOT = os.path.dirname(HERE)
WF_DIR = os.path.join(ROOT, "API_workflows")


def frames_for(duration):
    base = max(5, round(duration * 24))
    return base + (5 - base % 17) % 17


def main():
    ap = argparse.ArgumentParser()
    workflows = ["t2v", "i2v", "flf2v", "ref2v"]
    workflows += [w + s for w in workflows for s in ("_8b", "_8b_heretic")]
    ap.add_argument("workflow", choices=workflows)
    ap.add_argument("--image", help="首帧 / 参考图（i2v / flf2v / ref2v）")
    ap.add_argument("--last-image", help="尾帧（flf2v）")
    ap.add_argument("--prompt-file", default=os.path.join(HERE, "prompt.txt"))
    ap.add_argument("--size", default="864x480")
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    path = os.path.join(WF_DIR, "sulphur_%s.json" % a.workflow)
    with open(path, encoding="utf-8") as f:
        graph = json.load(f)

    prompt = ""
    if os.path.exists(a.prompt_file):
        with open(a.prompt_file, encoding="utf-8") as f:
            prompt = f.read().strip()
    w, h = (int(x) for x in a.size.lower().split("x"))
    seed = a.seed if a.seed is not None else gs.random.randint(0, 2 ** 63 - 1)

    for node in graph.values():
        c = node["class_type"]
        if c == "MiniMaxH3ImageToVideo":
            node["inputs"].update(prompt=prompt, width=w, height=h,
                                  length=frames_for(a.duration))
        elif c == "BasicScheduler":
            node["inputs"]["steps"] = a.steps
        elif c == "RandomNoise":
            node["inputs"]["noise_seed"] = seed

    images = []
    if a.image:
        images.append(gs.upload_image(a.image))
    if a.last_image:
        images.append(gs.upload_image(a.last_image))
    if images:
        it = iter(images)
        for node in graph.values():
            if node["class_type"] == "LoadImage":
                node["inputs"]["image"] = next(it, images[0])

    out = a.out or "sulphur_%s_%d.mp4" % (a.workflow, seed)
    print(">>> %s | %dx%d | %d 帧 | %d 步 | seed=%d" % (
        a.workflow, w, h, frames_for(a.duration), a.steps, seed))
    pid = gs.submit(graph)
    print("  prompt_id:", pid)
    outputs = gs.wait(pid)
    v = gs.find_video_file(outputs, ".mp4")
    if v is None:
        raise RuntimeError("outputs 中未找到 mp4: %s" % json.dumps(outputs, ensure_ascii=False)[:800])

    workdir = tempfile.mkdtemp(prefix="sulphur_wf_")
    local = os.path.join(workdir, "seg0.mp4")
    sub = v.get("subfolder") or ""
    url = gs.API + "/view?filename=" + gs.urllib.parse.quote(v["filename"], safe="") + \
          ("&subfolder=" + gs.urllib.parse.quote(sub, safe="") if sub else "") + \
          "&type=" + v.get("type", "output")
    gs.download(url, local)
    out_path = out if os.path.isabs(out) else os.path.join(os.getcwd(), out)
    gs.concat_segments(workdir, out_path)
    print("done. output:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
