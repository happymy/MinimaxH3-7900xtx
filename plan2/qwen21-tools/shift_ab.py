# -*- coding: utf-8 -*-
"""A/B the missing ModelSamplingAuraFlow(shift=3.1).

Same prompts, same seed, same everything as LEN_T78/T82/T86/T94 — the only
added node is ModelSamplingAuraFlow between the UNet loader and the Qwen cache.
Prompts are read back out of the already-generated PNGs so they are byte-identical.
"""
import json
import os
import struct
import sys
import time
import urllib.error
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
SHIFT = 3.1
SHIFT_NODE = "900"


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


def prompt_of(fname):
    j = json.loads(png_texts(os.path.join(OUT, fname))["prompt"])
    return j["459:474"]["inputs"]["on_false"]


def build_with_shift(prompt, prefix, shift=SHIFT):
    j = json.load(open(TPL, encoding="utf-8"))
    j["459:471"]["inputs"]["prompt"] = prompt
    j["459:474"]["inputs"]["on_false"] = prompt
    j[SHIFT_NODE] = {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {"model": ["459:451", 0], "shift": shift, "sampling": "flow"},
    }
    j["459:480"]["inputs"]["model"] = [SHIFT_NODE, 0]
    j["461"]["inputs"]["filename_prefix"] = prefix
    return j


def post(api):
    body = json.dumps({"prompt": api, "client_id": "shiftab"}).encode("utf-8")
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


PLAN = [("T78", "LEN_T78_00001.png"), ("T82", "LEN_T82_00001.png"),
        ("T86", "LEN_T86_00001.png"), ("T94", "LEN_T94_00001.png"),
        ("V0", "BISECT_V0_full_00001.png")]

manifest = []
for i, (tag, src) in enumerate(PLAN, 1):
    p = prompt_of(src)
    tagname = "SHIFT_%s" % tag
    print("[%d/%d] %s (%d字) 插入 shift=%.1f" % (i, len(PLAN), tag, len(p), SHIFT), flush=True)
    json.dump(build_with_shift(p, tagname), open(os.path.join(HERE, "api_%s.json" % tagname), "w",
                 encoding="utf-8"), ensure_ascii=False, indent=2)
    try:
        pid = post(build_with_shift(p, tagname))
    except urllib.error.HTTPError as e:
        print("    失败:", e.read().decode("utf-8", "replace")[:400], flush=True)
        continue
    st, files = wait(pid)
    print("    -> %s %s" % (st, files), flush=True)
    manifest.append({"tag": tag, "src_no_shift": src, "shift": SHIFT,
                     "prompt": p, "status": st, "files": files})
    json.dump(manifest, open(os.path.join(HERE, "shift_manifest.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n完成", flush=True)
