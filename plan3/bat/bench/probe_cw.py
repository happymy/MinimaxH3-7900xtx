# -*- coding: utf-8 -*-
"""H3 上下文窗口逐档试探：图构造复用 gen_h3_scenes-8b-heretic-int8.build_graph，
只把 BasicGuider/HyperFlowSigmas 的 model 改接到 MiniMaxH3ContextWindows。

    python probe_cw.py --size 864x480 --lengths 124,362,656 --log <comfy.err.log> --out cw.json

**判据与 probe_limit.py 不同**：窗口化后每一步要对每个窗口各跑一遍，所以
每步 s/it ≈ 窗口数 × 单窗基线 s/it（480P×124 帧实测 10.2 s/it）。
  * 窗口数从日志里数 `Context window i/N:`（真值，不是我算的）
  * 首步 s/it > 窗口数 × 基线 × 1.6 → 判爆（窗口没生效 / 权重反复重搬）
  * 全程 min vram_free < 1.0 GB → 判爆
`--lengths` 第一档必须是不开窗也能过的基线（用来定单窗 s/it）。
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import time
import urllib.request

API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.normpath(os.path.join(
    HERE, "..", "scenes_8b_heretic_int8", "gen_h3_scenes-8b-heretic-int8.py"))
SIT_RE = re.compile(r"(\d+)/(\d+)\s*\[[^\]]*?(\d+(?:\.\d+)?)s/it\]")
WIN_RE = re.compile(r"Context window (\d+)/(\d+): frames (\d+)-(\d+) of (\d+)")
USE_RE = re.compile(r"Using context windows: Context length (\d+) with overlap (\d+) for (\d+) frames")
GUARD_TOTAL = 23.9   # 总占用（GB）达到即判爆：24 GB 卡到 24 GB 就是爆显存
GUARD_SHARED = 0.6   # 共享显存增量（GB）：用户实测超过此值就可能爆/驱动崩
GUARD_FREE = 4.0     # 保护性阈值：专用显存只剩这么多就提前中断，不等真爆
GUARD_TOTAL_STOP = 22.0   # 预爆线：到 24 就来不及了，22 GB 就先撤
GUARD_SHARED_STOP = 0.35  # 预爆线：共享显存开始涨就停，不等 0.6
GUARD_INIT = 240.0   # Model Initializing 超过这么多秒才算真卡死（冷启动编译会花 90-120 s）
SIT_RATIO = 16.0     # 首步 s/it 相对单窗基线的失控上限
PROMPT = ("A slow push-in on a weathered wooden gate in tall grass at golden hour, "
          "warm backlight, gentle wind, distant birds.")


def http(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    return OPENER.open(req, timeout=30).read()


def stats():
    d = json.loads(http("GET", "/system_stats"))["devices"][0]
    return d["vram_free"] / 2 ** 30, d["vram_total"] / 2 ** 30


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def free_vram(headroom=1.0, wait=150):
    try:
        http("POST", "/interrupt", {})
        http("POST", "/queue", {"clear": True})
    except Exception:
        pass
    http("POST", "/free", {"unload_models": True, "free_memory": True})
    t0 = time.time()
    while time.time() - t0 < wait:
        f, tot = stats()
        if tot - f <= headroom:
            return f, tot, time.time() - t0
        time.sleep(2)
    return f, tot, -1.0


def read_new(log, off):
    with open(log, "rb") as fh:
        fh.seek(off)
        raw = fh.read()
    return raw, off + len(raw)


def last_sit(raw, steps):
    """只认 `n/<steps>` 那条 tqdm：VAE 解码也有 s/it，全局取最后一个会抓错阶段。"""
    hits = [(int(m.group(1)), float(m.group(3)))
            for m in SIT_RE.finditer(raw.decode("utf-8", "replace"))
            if int(m.group(2)) == steps]
    return hits[-1] if hits else (None, None)


def gpu_counter(counter):
    """typeperf 单次采样，返回按列序的数值列表；失败返回 []。"""
    try:
        out = subprocess.run(["typeperf", "\\GPU Adapter Memory(*)\\%s" % counter, "-sc", "1"],
                             capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return []
    for line in out.splitlines():
        if not line.startswith('"'):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2 or parts[0].startswith("(PDH-CSV"):
            continue
        vals = []
        for p in parts[1:]:
            try:
                vals.append(float(p))
            except ValueError:
                vals.append(0.0)
        return vals
    return []


def pick_adapter():
    """列下标：专用显存占用最大的那块就是 7900 XTX（LUID 重启会变，不能写死）。"""
    vals = gpu_counter("Dedicated Usage")
    return vals.index(max(vals)) if vals else None


def shared_gb(idx):
    if idx is None:
        return None
    vals = gpu_counter("Shared Usage")
    return vals[idx] / 2 ** 30 if len(vals) > idx else None


def est_windows(length, context_length=124, context_overlap=39):
    """窗口数：照 comfy/context_windows.create_windows_static_standard 逐条复算，
    不是估的（17n+5 帧先换成 5n+2 的 latent，delta = len - overlap）。"""
    lt = 2 if length <= 5 else ((length - 5) // 17) * 5 + 2
    win = 2 if context_length <= 5 else ((context_length - 5) // 17) * 5 + 2
    ov = 2 if context_overlap <= 5 else ((context_overlap - 5) // 17) * 5 + 2
    ov = min(ov, win - 5)
    if lt <= win:
        return 1
    d = win - ov
    n = 0
    for start in range(0, lt, d):
        n += 1
        if start + win >= lt:
            break
    return n


def add_cw(graph, context_length, context_overlap, freenoise):
    """把窗口节点插在 loader 与 guider/sigmas 之间（loader 输出 -> 19 -> 7/8）。"""
    graph["19"] = {"class_type": "MiniMaxH3ContextWindows", "inputs": {
        "model": ["1", 0],
        "context_length": context_length,
        "context_overlap": context_overlap,
        "fuse_method": "pyramid",
        "freenoise": freenoise,
        "split_conds_to_windows": False}}
    graph["7"]["inputs"]["model"] = ["19", 0]
    graph["8"]["inputs"]["model"] = ["19", 0]
    return graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", required=True, help="宽x高")
    ap.add_argument("--lengths", required=True, help="逗号分隔帧数，第一档当基线")
    ap.add_argument("--context-length", type=int, default=124, help="17n+5，默认 124")
    ap.add_argument("--context-overlap", type=int, default=39, help="17n+5，默认 39")
    ap.add_argument("--no-freenoise", dest="freenoise", action="store_false")
    ap.add_argument("--no-context-windows", dest="cw", action="store_false",
                    help="不开窗口（基线档用；只有第一档该关）")
    ap.add_argument("--base-sit", type=float, default=None,
                    help="单窗基线 s/it；不给就用 --lengths 第一档实测")
    ap.add_argument("--steps", type=int, default=6, choices=(4, 6, 8))
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--log", required=True, help="ComfyUI stderr 日志")
    ap.add_argument("--out", required=True, help="结果 JSONL")
    ap.add_argument("--prompt-file", help="长提示词文件；不给就用内置短句")
    ap.add_argument("--max-wait", type=float, default=3600.0)
    ap.add_argument("--early-stop", type=int, default=0,
                    help="跑到第 N 步还没异常就中断记 ok（只找爆点，不跑完整段）")
    ap.add_argument("--keep-going", action="store_true",
                    help="某一档判爆后继续跑后面的档（从大到小搜索时需要）")
    a = ap.parse_args()

    prompt = PROMPT
    if a.prompt_file:
        with open(a.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read().strip()
        print("prompt: %d 字符" % len(prompt), flush=True)

    w, h = (int(x) for x in a.size.lower().split("x"))
    lengths = [int(x) for x in a.lengths.split(",")]
    gen = load(GEN, "gen_h3_scenes_int8")

    base_sit = a.base_sit
    adapter = pick_adapter()
    sh0 = shared_gb(adapter)
    print("adapter col %s, idle shared %.2f GB" % (adapter, sh0 or 0), flush=True)
    results = []

    def emit(rec):
        results.append(rec)
        with open(a.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    if os.path.exists(a.out):
        os.remove(a.out)

    for i, ln in enumerate(lengths):
        f0, tot, waited = free_vram()
        print("\n=== %s x %d 帧  cw=%s(%d/%d) freenoise=%s  free before %.2f/%.2f GB"
              % (a.size, ln, a.cw, a.context_length, a.context_overlap, a.freenoise,
                 f0, tot), flush=True)
        if waited < 0:
            emit({"size": a.size, "length": ln, "verdict": "skipped",
                  "why": "显存未释放干净 free=%.2f" % f0})
            break

        graph = gen.build_graph(prompt, w, h, ln, a.steps, a.seed)
        if a.cw:
            add_cw(graph, a.context_length, a.context_overlap, a.freenoise)
        off = os.path.getsize(a.log)
        t0 = time.time()
        pid = json.loads(http("POST", "/prompt", {"prompt": graph}))["prompt_id"]
        print("  prompt_id:", pid, flush=True)

        lo, sit, done, verdict = 1e9, None, None, None
        windows = est_windows(ln, a.context_length, a.context_overlap) if a.cw else 1
        cum = {}            # step -> tqdm 累计均值 s/it
        per_step = []       # 反解出的单步真实耗时
        per_window = None
        init_t = None
        sh_peak, sh, t_sh = 0.0, None, 0.0
        while time.time() - t0 < a.max_wait:
            f, _ = stats()
            lo = min(lo, f)
            used = tot - f
            raw, off = read_new(a.log, off)
            text = raw.decode("utf-8", "replace")
            if init_t is None and "Model Initializing" in text:
                init_t = time.time() - t0
            step, s = last_sit(raw, a.steps)
            if step is not None:
                cum[step] = s
                sit = s
                n = len(cum)
                if n >= 2:
                    n1, n0 = sorted(cum)[-1], sorted(cum)[-2]
                    per_step.append(n1 * cum[n1] - n0 * cum[n0])  # 单步真实耗时
                per_window = s / max(1, windows)
            init_done = step is not None or "Initialization complete" in text

            # ① 显存到顶＝爆（24 GB 卡吃满就是爆）
            if used >= GUARD_TOTAL:
                verdict = "爆：总占用 %.2f GB ≥ %.1f" % (used, GUARD_TOTAL)
            # ② 共享显存超过 0.6 GB＝已经溢出（这台机器上就是系统开始卡）
            elif sh is not None and sh - (sh0 or 0) > GUARD_SHARED:
                verdict = "爆：共享显存 +%.2f GB > %.1f" % (sh - (sh0 or 0), GUARD_SHARED)
            # ③ 预爆：不等 24 GB／0.6 GB 才动手，驱动崩溃会拖死整机
            elif used >= GUARD_TOTAL_STOP:
                verdict = ("预爆：总占用 %.2f GB ≥ %.1f（提前中断）"
                           % (used, GUARD_TOTAL_STOP))
            elif sh is not None and sh - (sh0 or 0) > GUARD_SHARED_STOP:
                verdict = ("预爆：共享显存 +%.2f GB > %.2f（提前中断）"
                           % (sh - (sh0 or 0), GUARD_SHARED_STOP))
            # ④ 每窗耗时成倍＝爆（窗口数按源码公式复算，不是估的）
            elif base_sit and per_window and per_window > base_sit * 2.0:
                verdict = ("爆：每窗 %.1f s/it = 单窗基线 %.1f 的 %.1f 倍（%d 窗）"
                           % (per_window, base_sit, per_window / base_sit, windows))
            # ④ 初始化卡死：有显存压力 60 s 即算，无压力等到 240 s（冷启动编译要 90-120 s）
            elif init_t is not None and not init_done:
                init_el = time.time() - t0 - init_t
                if init_el > (60.0 if used >= 23.0 else GUARD_INIT):
                    verdict = ("爆：Model Initializing %.0f s 未完成（总占用 %.1f GB）"
                               % (init_el, used))
            if verdict:
                http("POST", "/interrupt", {})
                break

            # 只找爆点：跑到 N 步都没异常就提前收工，不必跑完整段
            if a.early_stop and step is not None and len(cum) >= a.early_stop:
                verdict = "ok(early %d 步)" % len(cum)
                http("POST", "/interrupt", {})
                break

            if time.time() - t_sh > 2.0:
                v = shared_gb(adapter)
                t_sh = time.time()
                if v is not None:
                    sh = v
                    sh_peak = max(sh_peak, v - (sh0 or 0))

            hist = json.loads(http("GET", "/history/" + pid))
            if pid in hist:
                st = hist[pid].get("status", {})
                for msg in st.get("messages", []):
                    if msg[0] == "execution_error":
                        verdict = "execution_error: " + json.dumps(
                            msg[1], ensure_ascii=False)[:300]
                        break
                if verdict is None and st.get("status_str") in ("success", "completed"):
                    done = time.time() - t0
                    break
            if verdict:
                break
            time.sleep(0.4)

        el = time.time() - t0
        # 提前收工那次走不到下面的 done 分支，基线要在这里落
        if base_sit is None and sit is not None:
            base_sit = sit
            print("  baseline: 单窗 s/it %.1f @ %d 帧" % (base_sit, ln), flush=True)
        if done is None and verdict is None:
            verdict = "超时 %.0fs（未完成）" % el
            http("POST", "/interrupt", {})
        elif done is not None:
            if base_sit is None:
                base_sit = sit
                verdict = "ok(baseline)"
                print("  baseline: 单窗 s/it %.1f @ %d 帧, total %.0fs"
                      % (base_sit, ln, el), flush=True)
            else:
                # 每窗耗时必须落在「单窗基线 ~ 2 倍」之间（正常 ≈1.25 倍）
                ratio = (per_window or 0) / base_sit
                verdict = "ok" if 0.4 <= ratio <= 2.0 else \
                    "可疑：每窗 %.1f s/it = 基线 %.1f 的 %.1f 倍" % (per_window, base_sit, ratio)

        emit({"size": a.size, "length": ln, "cw": a.cw,
              "context": [a.context_length, a.context_overlap] if a.cw else None,
              "freenoise": a.freenoise if a.cw else None,
              "windows": windows,
              "init_sec": round(init_t, 1) if init_t is not None else None,
              "shared_peak": round(sh_peak, 2),
              "vram_peak": round(tot - lo, 2),
              "elapsed": round(el, 1), "min_free": round(lo, 2),
              "per_window": round(per_window, 1) if per_window else None,
              "pw_ratio": round((per_window or 0) / base_sit, 2) if base_sit and per_window else None,
              "per_step": [round(x, 1) for x in per_step],
              "verdict": verdict})
        if not str(verdict).startswith("ok"):
            print("  stop: 该档不合格", flush=True)
            if not a.keep_going:
                break

    print("\n--- summary ---")
    for r in results:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
