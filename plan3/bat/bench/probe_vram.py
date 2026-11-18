# -*- coding: utf-8 -*-
"""单次 720p×5s 的显存时间线：只跑到第 1 步，观察 N 秒就中断，不等渲染完成。

    python probe_vram.py --secs 10 --runs 2

判读依据（comfy\\model_management.py）：
    line 944  extra_mem = max(minimum_inference_memory(), memory_required + extra_reserved_memory())
    line 1025 usable = max(0, free+L - E,  min((free+L)*0.4, (free+L) - minf)) - L
    line 458  MIN_WEIGHT_MEMORY_RATIO = 0.4
所以 usable ≈ free - E（正常）或 ≈ 0.4*free（term3 赢，即激活预估 E > 0.6*free）。
后者意味着权重预算只比权重本身大几百 MB，每步都要重搬 → s/it 涨 3-5 倍。
日志里同步出现的指纹是 `0 models unloaded.`（model_management.py:1009-1011）。
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request

API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.normpath(os.path.join(HERE, "..", "..", "API_workflows", "hyperflow_t2v_clipproj_8b.json"))
INT8 = "qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors"
PROMPT_FILE = r"D:\localAI\ComfyUI-last\plan3\bat\multisegment_8b_heretic\prompt.txt"
TMP = r"C:\Users\GAME\AppData\Local\Temp\opencode"
LOGS = [os.path.join(TMP, "comfy_h3.log"), os.path.join(TMP, "comfy_h3.err.log")]

STEP_RE = re.compile(r"([1-9])/(\d+)\s*\[")
COMFY_PID = 0


def http(method, path, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    return OPENER.open(req, timeout=timeout).read()


def dev():
    return json.loads(http("GET", "/system_stats"))["devices"][0]


def gb(x):
    return round(x / 2 ** 30, 2)


def os_mem(pid):
    """任务管理器口径（GB）：adapter 专用 / adapter 共享 / 本进程专用。torch 说多少和这里无关。"""
    try:
        out = subprocess.run(["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage",
                              r"\GPU Adapter Memory(*)\Shared Usage",
                              r"\GPU Process Memory(*)\Dedicated Usage", "-sc", "1"],
                             capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return None, None, None
    head, row = None, None
    for line in out.splitlines():
        if not line.startswith('"'):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if "(PDH-CSV" in parts[0]:
            head = parts
        elif head is not None and len(parts) >= len(head) - 1:
            row = parts
            break
    if not head or not row:
        return None, None, None
    ded = shr = proc = 0.0
    tag = "pid_%d_" % pid
    for path, val in zip(head[1:], row[1:]):
        try:
            v = float(val)
        except ValueError:
            continue
        if "Adapter Memory" in path:
            if "Dedicated Usage" in path:
                ded = max(ded, v)
            elif "Shared Usage" in path:
                shr = max(shr, v)
        elif tag in path:
            proc += v
    return round(ded / 2 ** 30, 2), round(shr / 2 ** 30, 2), round(proc / 2 ** 30, 2)


def comfy_pid():
    """8188 的监听进程 = ComfyUI 本体（Start-Process 报的 pid 会被子进程替换）。"""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-NetTCPConnection -LocalPort 8188 -State Listen).OwningProcess"],
                             capture_output=True, text=True, timeout=40).stdout
        return int(out.split()[0])
    except Exception:
        return 0


class Tail:
    """增量读日志：按 \\n 切行，半行留在缓冲里，避免跨轮切碎。"""

    def __init__(self, paths):
        self.paths = list(paths)
        self.off = {p: (os.path.getsize(p) if os.path.exists(p) else 0) for p in self.paths}
        self.buf = ""

    def read(self):
        raw = b""
        for p in self.paths:
            if not os.path.exists(p):
                continue
            with open(p, "rb") as f:
                f.seek(self.off[p])
                chunk = f.read()
                self.off[p] += len(chunk)
            raw += chunk
        self.buf += raw.decode("utf-8", "replace").replace("\r", "\n")
        lines = self.buf.split("\n")
        self.buf = lines.pop()
        return [ln for ln in lines if ln.strip()]


def wait_idle(limit=240):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            d = dev()
            q = json.loads(http("GET", "/queue"))
            if not q.get("queue_running") and not q.get("queue_pending"):
                return d
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("ComfyUI 没起来或队列没空（%.0f s）" % (time.time() - t0))


def build_graph(seed, args):
    g = json.load(open(GRAPH, encoding="utf-8"))
    g["2"]["inputs"]["clip_name"] = INT8
    g["8"]["inputs"]["noise_seed"] = seed
    g["5"]["inputs"]["length"] = args.length
    g["5"]["inputs"]["width"] = 1344
    g["5"]["inputs"]["height"] = 768
    g["6"]["inputs"]["steps"] = 6
    if args.cw:
        ctx, ov = (int(v) for v in args.cw.split("/"))
        g["20"] = {"inputs": {"model": ["1", 0], "context_length": ctx, "context_overlap": ov,
                              "fuse_method": "pyramid", "freenoise": True,
                              "split_conds_to_windows": False},
                   "class_type": "MiniMaxH3ContextWindows"}
        g["9"]["inputs"]["model"] = ["20", 0]
        g["6"]["inputs"]["model"] = ["20", 0]
    if args.weights:
        g["1"]["inputs"]["weights_in"] = args.weights
    if os.path.exists(PROMPT_FILE):
        g["5"]["inputs"]["prompt"] = open(PROMPT_FILE, encoding="utf-8").read().strip()
    return g


def run_once(args, idx):
    log = Tail(LOGS)
    log.read()                                   # 丢掉上一轮残留
    base = dev()
    http("POST", "/prompt", {"prompt": build_graph(args.seed + idx, args)})

    t0 = time.time()
    samples, events = [], []
    step1 = None
    hit = False

    while time.time() - t0 < args.timeout:
        try:
            d = dev()
        except Exception:
            time.sleep(0.5)
            continue
        t = round(time.time() - t0, 1)
        osd, oss, osp = os_mem(COMFY_PID)
        s = {"t": t, "free": gb(d["vram_free"]), "tfree": gb(d["torch_vram_free"]),
             "os_ded": osd, "os_shared": oss, "os_proc": osp}
        samples.append(s)
        for line in log.read():
            keep = re.search(r"Requested to load (\S+)|(\d+)MB Staged|[0-9.]+ MB usable|(\d+) models unloaded|Using context windows", line)
            if keep:
                events.append({"t": t, "free": s["free"], "text": line.strip()[-150:]})
            if STEP_RE.search(line) and step1 is None:
                step1 = t
        if step1 is not None and t - step1 >= args.secs:
            hit = True
            break
        time.sleep(0.5)

    http("POST", "/interrupt", {})
    http("POST", "/queue", {"clear": True})
    time.sleep(2)
    try:
        d = dev()
        samples.append({"t": round(time.time() - t0, 1), "free": gb(d["vram_free"]), "tfree": gb(d["torch_vram_free"])})
    except Exception:
        pass
    http("POST", "/free", {"unload_models": True, "free_memory": True})
    time.sleep(3)
    after = dev()

    pre = [s for s in samples if step1 is None or s["t"] < step1]
    peak = max(samples, key=lambda s: base["vram_total"] / 2 ** 30 - s["free"]) if samples else None
    osd = [s["os_ded"] for s in samples if s.get("os_ded")]
    oss = [s["os_shared"] for s in samples if s.get("os_shared") is not None]
    out = {
        "run": idx,
        "peak_used": None if peak is None else round(base["vram_total"] / 2 ** 30 - peak["free"], 2),
        "peak_used_at": None if peak is None else peak["t"],
        "peak_os_ded": max(osd) if osd else None,
        "peak_os_shared": max(oss) if oss else None,
        "peak_os_proc": max((s["os_proc"] for s in samples if s.get("os_proc") is not None), default=None),
        "free_before_load_gb": min((s["free"] for s in pre), default=None),
        "free_after_free_gb": gb(after["vram_free"]),
        "step1_reached": hit,
        "events": events,
        "samples": samples,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=int, default=10, help="第 1 步跑多久就中断")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--length", type=int, default=124)
    ap.add_argument("--cw", default=None, help="上下文窗口 ctx/ov（如 107/22）；不给就不挂节点")
    ap.add_argument("--weights", default=None, choices=["auto", "disk", "ram"],
                    help="HyperFlowLoader 的 weights_in（默认用图里的 disk）")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default=os.path.join(TMP, "vram_probe.json"))
    args = ap.parse_args()

    d = wait_idle()
    global COMFY_PID
    COMFY_PID = comfy_pid()
    print("comfy pid %d" % COMFY_PID)
    total = d["vram_total"] / 2 ** 30
    print("baseline: total %.2f GB, free %.2f GB, torch_free %.2f GB" % (
        total, d["vram_free"] / 2 ** 30, d["torch_vram_free"] / 2 ** 30))

    results = []
    for i in range(args.runs):
        http("POST", "/free", {"unload_models": True, "free_memory": True})
        time.sleep(3)
        r = run_once(args, i)
        results.append(r)
        print("\n=== run %d ===  peak_used %.2f GB @%.1fs | OS 专用 %s GB 共享 %s GB | 本进程 %s GB | free 最低 %.2f | /free 后 %.2f | 触到第1步 %s" % (
            i + 1, r["peak_used"] or -1, r["peak_used_at"] or -1,
            r["peak_os_ded"], r["peak_os_shared"], r["peak_os_proc"],
            r["free_before_load_gb"] if r["free_before_load_gb"] is not None else -1,
            r["free_after_free_gb"], r["step1_reached"]))
        for e in r["events"]:
            print("  %6.1fs  free %5.2f  %s" % (e["t"], e["free"], e["text"]))

    json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n采样点 %d 个 → %s" % (sum(len(r["samples"]) for r in results), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
