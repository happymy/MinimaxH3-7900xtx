# -*- coding: utf-8 -*-
"""一次 H3 生成：提交固定图，全程轮询 /system_stats 记显存曲线。

    python test_once.py --out run.txt --seed 12345
    python test_once.py --out run.txt --size 1344x768 --length 124 --clip <te>.safetensors

图直接复用 gen_h3_scenes-8b-heretic.py 的 build_graph，避免第二份定义。
判据：comfyui.log 里 `Model BooguTEModel_ ... NNNMB Staged` 是文本编码器的真实体积
（fp8 文件会被摊成 bf16，标称 -40% 不成立）；曲线 min(vram_free) 看采样段余量。
"""

import argparse
import importlib.util
import json
import time
import urllib.request

HERE = __file__.rsplit("\\", 1)[0]
GEN = HERE + r"\..\scenes_8b_heretic\gen_h3_scenes-8b-heretic.py"
API = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def vram_free():
    d = json.loads(OPENER.open(API + "/system_stats", timeout=5).read())
    dev = d["devices"][0]
    return dev["vram_free"] / 2 ** 30, dev["vram_total"] / 2 ** 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="曲线输出文件")
    ap.add_argument("--length", type=int, default=73, help="帧数，17n+5；73 = 24fps 下 3 秒")
    ap.add_argument("--size", default="864x480")
    ap.add_argument("--steps", type=int, default=6, choices=(4, 6, 8))
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--clip", help="覆盖 CLIPLoader 的 clip_name（只改本次 payload）")
    ap.add_argument("--prompt", default="A slow push-in on a weathered wooden gate in tall grass at golden hour, "
                                        "warm backlight, gentle wind, distant birds.")
    a = ap.parse_args()

    w, h = (int(x) for x in a.size.lower().split("x"))
    gen = load(GEN, "gen_h3_scenes")
    graph = gen.build_graph(a.prompt, w, h, a.length, a.steps, a.seed)
    if a.clip:
        for n in graph.values():
            if n.get("class_type") == "CLIPLoader":
                n["inputs"]["clip_name"] = a.clip
    print("graph: %d nodes, %dx%d, %d frames, %d steps, seed %d"
          % (len(graph), w, h, a.length, a.steps, a.seed))

    t0 = time.time()
    pid = gen.submit(graph)
    print("prompt_id:", pid)

    series = []
    done_at = None
    while time.time() - t0 < 3600:
        el = time.time() - t0
        try:
            vf, vt = vram_free()
            series.append((el, vf))
            line = "  %6.1fs  vram_free=%.2f / %.2f GB" % (el, vf, vt)
            hist = json.loads(OPENER.open(API + "/history/" + pid, timeout=5).read())
            if pid in hist:
                st = hist[pid].get("status", {})
                for msg in st.get("messages", []):
                    if msg[0] == "execution_error":
                        print(line)
                        raise SystemExit("execution_error: " + json.dumps(msg[1], ensure_ascii=False)[:400])
                if st.get("status_str") in ("success", "completed"):
                    done_at = el
                    print(line + "   <- done")
                    break
            print(line)
        except SystemExit:
            raise
        except Exception as e:
            print("  %6.1fs  poll error: %s" % (el, e))
        time.sleep(0.5)

    if not series:
        raise SystemExit("no samples")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("seed=%d size=%s frames=%d steps=%d\n" % (a.seed, a.size, a.length, a.steps))
        for el, vf in series:
            f.write("%.2f %.3f\n" % (el, vf))

    lo = min(series, key=lambda x: x[1])
    print("\ntotal %.1fs (%d samples)" % (done_at or series[-1][0], len(series)))
    print("min vram_free %.2f GB at %.1fs  ->  peak used %.2f GB"
          % (lo[1], lo[0], series[0][1] * 0 + (vram_free()[1] - lo[1])))
    print("curve ->", a.out)


if __name__ == "__main__":
    main()
