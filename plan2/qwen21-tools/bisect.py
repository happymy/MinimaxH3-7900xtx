# -*- coding: utf-8 -*-
"""Leave-one-out bisection of the 0033 prompt.

Everything except the prompt string is held byte-identical to the run that
produced Qwen_image_2.1_00033.png (Q8_0, cfg=1.0, seed 447606998181262,
euler/simple 25 steps, negative empty, PE switch off).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8188"
HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "api_base_0033.json")

S1 = "11岁中国女孩，站姿居中。"                                        # 主体+构图
S2 = "长发，头发梳成辫子，搭在左肩膀上，"                              # 发型
S3 = "上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。"  # 服装
S4 = "女孩漂亮、文静、身材高挑。"                                     # 抽象形容
S5 = "人物孤立，影棚光，"                                              # 孤立+灯光
S6 = "高清，细节丰富，锐利对焦，高质量。"                              # 画质堆砌

FULL = S1 + S2 + S3 + S4 + S5 + S6

# (tag, prompt) — every variant is the full prompt minus exactly one group,
# except V6 which keeps only the two factual groups.
VARIANTS = [
    ("V0_full",   FULL),
    ("V1_noQual", S1 + S2 + S3 + S4 + S5),
    ("V2_noAbstract", S1 + S2 + S3 + S5 + S6),
    ("V3_noStudioLight", S1 + S2 + S3 + S4 + S6),
    ("V4_noHair", S1 + S3 + S4 + S5 + S6),
    ("V5_noClothes", S1 + S2 + S4 + S5 + S6),
    ("V6_factsOnly", S1 + S3),
]


def api_for(prompt):
    j = json.load(open(TPL, encoding="utf-8"))
    j["459:471"]["inputs"]["prompt"] = prompt      # TextGenerate (not executed, kept for parity)
    j["459:474"]["inputs"]["on_false"] = prompt    # ComfySwitchNode false branch == actual path
    return j


def post(api, prefix):
    body = json.dumps({"prompt": api, "client_id": "bisect"}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return r["prompt_id"]


def wait(pid, timeout=900):
    t0 = time.time()
    seen = set()
    while time.time() - t0 < timeout:
        h = json.loads(urllib.request.urlopen(BASE + "/history/" + pid, timeout=30).read())
        if pid in h:
            out = h[pid].get("outputs", {})
            files = []
            for v in out.values():
                files += [x["filename"] for x in v.get("images", [])]
            return h[pid].get("status", {}).get("status_str"), files
        q = json.loads(urllib.request.urlopen(BASE + "/queue", timeout=30).read())
        run = q.get("queue_running", [])
        pend = q.get("queue_pending", [])
        line = "  running=%d pending=%d  %ds" % (len(run), len(pend), time.time() - t0)
        if line not in seen:
            seen.add(line)
            print(line, flush=True)
        time.sleep(3)
    return "TIMEOUT", []


def main():
    print("=== 提示词分组 ===", flush=True)
    for name, txt in (("S1主体构图", S1), ("S2发型", S2), ("S3服装", S3),
                      ("S4抽象", S4), ("S5孤立灯光", S5), ("S6画质", S6)):
        print("  %-12s %s" % (name, txt), flush=True)
    print()
    print("=== 对照方案（共 %d 张）===" % len(VARIANTS), flush=True)
    for tag, txt in VARIANTS:
        print("  %-18s %d字  %s" % (tag, len(txt), txt), flush=True)
    print()

    manifest = []
    for i, (tag, txt) in enumerate(VARIANTS, 1):
        api = api_for(txt)
        p = os.path.join(HERE, "api_%s.json" % tag)
        json.dump(api, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        api["461"]["inputs"]["filename_prefix"] = "BISECT_" + tag
        print("[%d/%d] %s 提交中…" % (i, len(VARIANTS), tag), flush=True)
        try:
            pid = post(api, tag)
        except urllib.error.HTTPError as e:
            print("    提交失败:", e.read().decode("utf-8", "replace")[:400], flush=True)
            continue
        status, files = wait(pid)
        print("    -> %s  %s" % (status, files), flush=True)
        manifest.append({"tag": tag, "prompt": txt, "status": status, "files": files})
        json.dump(manifest, open(os.path.join(HERE, "bisect_manifest.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n全部完成", flush=True)


if __name__ == "__main__":
    main()
