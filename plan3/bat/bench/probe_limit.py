# -*- coding: utf-8 -*-
"""单段长度上限逐档试探：每档前 `/free`，跑完记耗时与显存曲线，判爆即停。

    python probe_limit.py --size 1280x720 --lengths 124,243,294,345 --log <comfy.err.log> --out probe_720p.json

`--lengths` 的**第一档是基线**，必须已知能过（脚本要用它的实测 s/it 做外推基准）。

**判爆只看两件事**：`Model Initializing` 的耗时和每步的 s/it。首步的 s/it 已经含
Model Initializing，所以拿它跟基线比就够——正常档约等于基线值，跨线档至少 ×3
（实测 720p 243 帧：初始化 9 分 39 秒，首步 579 s/it vs 基线 34 s/it）。

三条判据任一成立即判该档不合格，并停止更长的档：
  1. **首步 s/it > 基线 s/it × 3**（最灵敏，一次就命中，不必等跑完）
  2. 总耗时 > 1.22 次幂外推 × 2
  3. 全程 min vram_free < 0.5 GB（真 OOM 兜底；跨线时显存往往还剩 8 GB 以上，抓不到）

档与档之间 `POST /free`（unload_models + free_memory）并**等到** vram_free 回到
total - 1.0 GB；没回到位就跳过该档，因为残留会让占用虚高、数据作废。
"""

import argparse
import importlib.util
import json
import os
import re
import time
import urllib.request

API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.normpath(os.path.join(
    HERE, "..", "scenes_8b_heretic_int8", "gen_h3_scenes-8b-heretic-int8.py"))
SIT_RE = re.compile(r"(\d+)/(\d+)\s*\[[^\]]*?(\d+(?:\.\d+)?)s/it\]")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", required=True, help="宽x高")
    ap.add_argument("--lengths", required=True,
                    help="逗号分隔帧数（17n+5），第一档是基线")
    ap.add_argument("--steps", type=int, default=6, choices=(4, 6, 8))
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--log", required=True, help="ComfyUI stderr 日志（tqdm 的 s/it 在里面）")
    ap.add_argument("--out", required=True, help="结果 JSONL")
    ap.add_argument("--prompt-file",
                    help="长提示词文件（三字段格式）；不给就用内置短句")
    ap.add_argument("--max-wait", type=float, default=2400.0, help="单档硬超时（秒）")
    a = ap.parse_args()

    prompt = PROMPT
    if a.prompt_file:
        with open(a.prompt_file, encoding="utf-8") as fh:
            prompt = fh.read().strip()
        print("prompt: %d 字符 from %s" % (len(prompt), os.path.basename(a.prompt_file)),
              flush=True)

    w, h = (int(x) for x in a.size.lower().split("x"))
    lengths = [int(x) for x in a.lengths.split(",")]
    gen = load(GEN, "gen_h3_scenes_int8")

    base_sit = base_len = base_total = None
    results = []

    def emit(rec):
        results.append(rec)
        with open(a.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    if os.path.exists(a.out):
        os.remove(a.out)

    for ln in lengths:
        f0, tot, waited = free_vram()
        print("\n=== %s x %d 帧   free before %.2f / %.2f GB (waited %.1fs)"
              % (a.size, ln, f0, tot, waited), flush=True)
        if waited < 0:
            emit({"size": a.size, "length": ln, "verdict": "skipped",
                  "why": "显存未释放干净 free=%.2f" % f0})
            break

        graph = gen.build_graph(prompt, w, h, ln, a.steps, a.seed)
        off = os.path.getsize(a.log)
        t0 = time.time()
        pid = json.loads(http("POST", "/prompt", {"prompt": graph}))["prompt_id"]
        print("  prompt_id:", pid, flush=True)

        lo, sit, done, verdict = 1e9, None, None, None
        limit = a.max_wait
        while time.time() - t0 < limit:
            f, _ = stats()
            lo = min(lo, f)
            raw, off = read_new(a.log, off)
            step, s = last_sit(raw, a.steps)
            if s is not None:
                sit = s
                if base_sit and step == 1 and s > base_sit * 3:
                    verdict = ("爆：首步 %.1f s/it > 基线 %.1f × 3"
                               "（Model Initializing 就在重搬权重）" % (s, base_sit))
                    http("POST", "/interrupt", {})
                    break
            if lo < 1.0:
                verdict = "min vram_free %.2f GB < 1.0（已贴近分页）" % lo
                http("POST", "/interrupt", {})
                break
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
            time.sleep(1.5)

        el = time.time() - t0
        pred = None
        if done is None and verdict is None:
            verdict = "超时 %.0fs（未完成）" % el
            http("POST", "/interrupt", {})
        elif done is not None:
            if lo < 0.5:
                verdict = "min vram_free %.2f GB < 0.5" % lo
            elif base_total is None:
                verdict = "ok(baseline)"
                base_sit, base_len, base_total = sit, ln, el
                print("  baseline set: s/it %.1f @ %d 帧, total %.0fs"
                      % (base_sit, base_len, base_total), flush=True)
            else:
                pred = base_total * (ln / float(base_len)) ** 1.22
                verdict = ("耗时 %.0fs > 外推 %.0fs × 2" % (done, pred)
                           if done > pred * 2 else "ok")

        emit({"size": a.size, "length": ln, "elapsed": round(el, 1),
              "min_free": round(lo, 2), "sit": sit,
              "linear_sit": round(base_sit * ln / base_len, 1) if base_sit else None,
              "pred_total": round(pred) if pred else None,
              "verdict": verdict})
        if not str(verdict).startswith("ok"):
            print("  stop: 该档不合格，不再加长", flush=True)
            break

    print("\n--- summary ---")
    for r in results:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
