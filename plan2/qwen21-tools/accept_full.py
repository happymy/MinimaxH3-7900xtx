# -*- coding: utf-8 -*-
"""Acceptance test: the user's own full prompt under the fixed launch flags.

T82 proved the flag fix. This proves the original prompt -- 95 chars /
101 tokens, well past the 74-char point that used to break -- now renders.
Nothing is changed; the prompt is read back out of the user's own PNG so the
API workflow stays byte-identical to what they actually ran.
"""
import json
import os
import struct
import sys
import time
import urllib.request
# 本地 API 直连：系统代理 127.0.0.1:26561 不放行 loopback 会回 404；
# 空 ProxyHandler 同时绕过环境变量与注册表代理，不依赖启动方式。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
import zlib

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8188"
HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "api_base_0033.json")
OUT = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\output"


def png_texts(path):
    o = {}
    with open(path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return o
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            ln, typ = struct.unpack(">I4s", hdr)
            data = f.read(ln)
            f.read(4)
            t = typ.decode("latin1")
            if t == "tEXt":
                k, _, v = data.partition(b"\x00")
                o[k.decode("latin1")] = v.decode("utf-8", "replace")
            elif t == "iTXt":
                k, _, rest = data.partition(b"\x00")
                c = rest[0]
                rest = rest[2:]
                v, _, _ = rest.partition(b"\x00")
                if c:
                    v = zlib.decompress(v)
                o[k.decode("latin1")] = v.decode("utf-8", "replace")
            elif t == "IDAT":
                break
    return o


def api_of(fname):
    return json.loads(png_texts(os.path.join(OUT, fname))["prompt"])


src = "Qwen_image_2.1_00033.png"
user_api = api_of(src)
user_prompt = user_api["459:474"]["inputs"]["on_false"]
v0_prompt = api_of("BISECT_V0_full_00001.png")["459:474"]["inputs"]["on_false"]

print("用户原始提示词: %d 字符" % len(user_prompt))
print("与 V0_full 相同: %s" % (user_prompt == v0_prompt))
print()

plan = json.load(open(TPL, encoding="utf-8"))
old_cfg = plan["459:458"]["inputs"]["cfg"]
old_steps = plan["459:458"]["inputs"]["steps"]
old_sampler = plan["459:458"]["inputs"]["sampler_name"]
old_sched = plan["459:458"]["inputs"]["scheduler"]

print("沿用用户原参数: cfg=%s steps=%s sampler=%s scheduler=%s" %
      (old_cfg, old_steps, old_sampler, old_sched))
print("仅改 filename_prefix\n")

results = []
for tag, fname, text in (("ACCEPT_0033", src, user_prompt),
                         ("ACCEPT_V0full", "BISECT_V0_full_00001.png", v0_prompt)):
    j = json.load(open(TPL, encoding="utf-8"))
    j["459:471"]["inputs"]["prompt"] = text
    j["459:474"]["inputs"]["on_false"] = text
    j["461"]["inputs"]["filename_prefix"] = tag
    json.dump(j, open(os.path.join(HERE, "api_%s.json" % tag), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    body = json.dumps({"prompt": j, "client_id": "accept"}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    pid = json.loads(OPENER.open(req, timeout=180).read())["prompt_id"]
    print("[%s] %d 字符 已提交..." % (tag, len(text)), flush=True)
    t0 = time.time()
    while time.time() - t0 < 1200:
        h = json.loads(OPENER.open(BASE + "/history/" + pid, timeout=30).read())
        if pid in h:
            files = []
            for v in h[pid].get("outputs", {}).values():
                files += [x["filename"] for x in v.get("images", [])]
            print("    -> %s %s (%d秒)" % (
                h[pid].get("status", {}).get("status_str"), files, int(time.time() - t0)),
                flush=True)
            results.append({"tag": tag, "src": fname, "chars": len(text),
                            "prompt": text, "files": files})
            break
        time.sleep(3)
    else:
        print("    -> 超时", flush=True)
        results.append({"tag": tag, "src": fname, "chars": len(text),
                        "prompt": text, "files": []})
    json.dump(results, open(os.path.join(HERE, "accept_manifest.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)

print("\n完成")