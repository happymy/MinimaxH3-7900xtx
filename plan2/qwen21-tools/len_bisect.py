# -*- coding: utf-8 -*-
"""Isolate prompt LENGTH from prompt CONTENT.

Two independent manipulations, both holding the semantic core at the front:

  T*  V0_full truncated at the tail to an exact token count. Core (S1+S2+S3)
      stays intact for every rung; only trailing groups are dropped.
  P*  V6_factsOnly (known PASS at 57 tok) padded at the tail with inert
      quality/lighting words to an exact token count. Core byte-identical.

If T-rungs and P-rungs both flip at the same token count, the discriminator
is length, not content.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
# 本地 API 直连：系统代理 127.0.0.1:26561 不放行 loopback 会回 404；
# 空 ProxyHandler 同时绕过环境变量与注册表代理，不依赖启动方式。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI")

import comfy.text_encoders.qwen_image21 as q21

BASE = "http://127.0.0.1:8188"
HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "api_base_0033.json")

V0 = "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。"
V6 = "11岁中国女孩，站姿居中。上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。"

PAD_UNITS = ["影棚光", "高清", "细节丰富", "锐利对焦", "高质量", "人物孤立",
             "全身正面", "居中构图", "纯净白色背景", "角色设定图",
             "高分辨率", "专业摄影棚", "柔和光线", "干净布景"]

_tok = q21.QwenImage21Tokenizer(embedding_directory=None, tokenizer_data={})


def ntok(text):
    out = _tok.tokenize_with_weights(text, prevent_empty_text=True)
    key = next(iter(out))
    return sum(1 for row in out[key] for t in row if isinstance(t[0], int))


def truncate_to(text, target):
    """Cut the tail so the token count is exactly `target` (or the largest <= target)."""
    lo, hi, best = 0, len(text), None
    while lo <= hi:
        mid = (lo + hi) // 2
        if ntok(text[:mid]) <= target:
            best = text[:mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def pad_to(text, target):
    """Append inert units until the token count reaches `target` (or the largest below)."""
    cur = text
    for u in PAD_UNITS:
        if ntok(cur) >= target:
            break
        cand = cur + "，" + u
        if ntok(cand) <= target:
            cur = cand
    return cur


PLAN = [
    ("T78",  truncate_to(V0, 78)),
    ("T82",  truncate_to(V0, 82)),
    ("T86",  truncate_to(V0, 86)),
    ("T94",  truncate_to(V0, 94)),
    ("P70",  pad_to(V6, 70)),
    ("P78",  pad_to(V6, 78)),
    ("P86",  pad_to(V6, 86)),
    ("P94",  pad_to(V6, 94)),
]

print("=== 计划 ===", flush=True)
rows = []
for tag, txt in PLAN:
    n = ntok(txt)
    rows.append((tag, n, txt))
    print("  %-5s %3d tok  %s" % (tag, n, txt), flush=True)
print(flush=True)


def api_for(prompt, prefix):
    j = json.load(open(TPL, encoding="utf-8"))
    j["459:471"]["inputs"]["prompt"] = prompt
    j["459:474"]["inputs"]["on_false"] = prompt
    j["461"]["inputs"]["filename_prefix"] = "LEN_" + prefix
    return j


def post(api):
    body = json.dumps({"prompt": api, "client_id": "lenbisect"}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    return json.loads(OPENER.open(req, timeout=120).read())["prompt_id"]


def wait(pid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(OPENER.open(BASE + "/history/" + pid, timeout=30).read())
        if pid in h:
            files = []
            for v in h[pid].get("outputs", {}).values():
                files += [x["filename"] for x in v.get("images", [])]
            return h[pid].get("status", {}).get("status_str"), files
        time.sleep(3)
    return "TIMEOUT", []


manifest = []
for i, (tag, n, txt) in enumerate(rows, 1):
    print("[%d/%d] %s (%d tok) 提交…" % (i, len(rows), tag, n), flush=True)
    try:
        pid = post(api_for(txt, tag))
    except urllib.error.HTTPError as e:
        print("    失败:", e.read().decode("utf-8", "replace")[:300], flush=True)
        continue
    st, files = wait(pid)
    print("    -> %s %s" % (st, files), flush=True)
    manifest.append({"tag": tag, "tokens": n, "prompt": txt, "status": st, "files": files})
    json.dump(manifest, open(os.path.join(HERE, "len_manifest.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n全部完成", flush=True)
