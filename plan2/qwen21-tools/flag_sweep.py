# -*- coding: utf-8 -*-
"""Sweep ComfyUI launch flags, run T82 under each.

T82 is 74 CJK chars / 82 tokens / 68 tokens surviving the template mask.
It is the shortest prompt that reliably produced a dirty image under the
original flags, so it is the cheapest probe that can tell a fix from a
non-fix.

Every config also gets its actual CommandLine read back from CIM, so a typo
in a bat is caught instead of silently passing.
"""
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
# 本地 API 直连：系统代理 127.0.0.1:26561 不放行 loopback 会回 404；
# 空 ProxyHandler 同时绕过环境变量与注册表代理，不依赖启动方式。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
import zlib

sys.stdout.reconfigure(encoding="utf-8")

PORTABLE = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PORTABLE, "ComfyUI", "output")
TPL = os.path.join(HERE, "api_base_0033.json")
BASE = "http://127.0.0.1:%d" % 8188
RESULT = os.path.join(HERE, "flag_sweep.json")
SRC_PNG = "LEN_T82_00001.png"

# (label, bat, note)
CONFIGS = [
    ("B", "run_amd_gpu_fp16_mid_only.bat",
     "keep fp16-intermediates, drop ck-attention"),
    ("A", "run_amd_gpu_ck_attn_only.bat",
     "keep ck-attention, drop fp16-intermediates"),
    ("D", "run_amd_gpu_ck_fp16_upcast.bat",
     "keep both, add --force-upcast-attention"),
    ("BASE", "run_amd_gpu_enable_dynamic_vram.bat",
     "original config, control: expected dirty"),
    ("C", "run_amd_gpu_default_attention.bat",
     "neither flag, control: expected clean"),
]

CREATE_NO_WINDOW = 0x08000000


def log(msg):
    print(msg, flush=True)


def port_open():
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", 8188))
        return True
    except OSError:
        return False
    finally:
        s.close()


def comfy_processes():
    """All ComfyUI server processes, identified by their main.py argument.

    Never matches on image name -- the agent harness is also python.exe.
    """
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        raw = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=90,
        ).stdout.strip()
    except Exception as e:
        log("    查询进程失败: %s" % e)
        return []
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    out = []
    for d in data:
        cmd = (d.get("CommandLine") or "")
        if "main.py" in cmd and "python_embeded" in cmd:
            out.append((int(d["ProcessId"]), cmd))
    return out


def stop_comfy():
    for pid, _ in comfy_processes():
        log("    停止 ComfyUI PID %d" % pid)
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=60)
    for _ in range(60):
        if not port_open() and not comfy_processes():
            return True
        time.sleep(1)
    return not port_open()


def launch(bat):
    """Start the bat with stdin/stdout/stderr all detached from this process.

    The bat ends in `pause`, which would otherwise block forever holding the
    inherited pipe.
    """
    logf = os.path.join(HERE, "comfy_%s.log" % bat[:-4])
    subprocess.run(["cmd", "/c", "del", logf], capture_output=True)
    with open(logf, "wb") as fh:
        subprocess.Popen(
            ["cmd", "/c", bat],
            cwd=PORTABLE, stdin=subprocess.DEVNULL,
            stdout=fh, stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    return logf


def wait_ready(timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if port_open():
            try:
                OPENER.open(BASE + "/system_stats", timeout=20).read()
                log("    就绪，用时 %d 秒" % int(time.time() - t0))
                return True
            except Exception:
                pass
        time.sleep(3)
    return False


def read_actual_flags():
    procs = comfy_processes()
    if not procs:
        return None
    cmd = procs[0][1]
    return {
        "fp16_intermediates": "--fp16-intermediates" in cmd,
        "ck_attention": "--use-ck-attention" in cmd,
        "force_upcast": "--force-upcast-attention" in cmd,
    }


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


def build(prompt, prefix):
    j = json.load(open(TPL, encoding="utf-8"))
    j["459:471"]["inputs"]["prompt"] = prompt
    j["459:474"]["inputs"]["on_false"] = prompt
    j["461"]["inputs"]["filename_prefix"] = prefix
    return j


def run_one(prefix, timeout=1200):
    body = json.dumps({"prompt": build(prompt_of(SRC_PNG), prefix),
                       "client_id": "sweep"}).encode("utf-8")
    req = urllib.request.Request(BASE + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    pid = json.loads(OPENER.open(req, timeout=180).read())["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(OPENER.open(BASE + "/history/" + pid,
                                              timeout=30).read())
        if pid in h:
            files = []
            for v in h[pid].get("outputs", {}).values():
                files += [x["filename"] for x in v.get("images", [])]
            st = h[pid].get("status", {}).get("status_str")
            return st, files, int(time.time() - t0)
        time.sleep(3)
    return "TIMEOUT", [], int(time.time() - t0)


def save(rows):
    json.dump(rows, open(RESULT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def sheet(rows):
    """Labeled contact sheet so all configs can be judged in one look."""
    from PIL import Image, ImageDraw
    ok = [r for r in rows if r.get("files")]
    if not ok:
        return None
    cell, pad, hdr = 480, 8, 34
    cols = 3
    rowsn = (len(ok) + cols - 1) // cols
    W = cols * (cell + pad) + pad
    H = rowsn * (cell + pad + hdr) + pad
    canvas = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(canvas)
    for i, r in enumerate(ok):
        cx = pad + (i % cols) * (cell + pad)
        cy = pad + (i // cols) * (cell + pad + hdr)
        try:
            im = Image.open(os.path.join(OUT, r["files"][0])).convert("RGB")
            im.thumbnail((cell, cell))
            canvas.paste(im, (cx + (cell - im.width) // 2,
                              cy + (cell - im.height) // 2))
        except Exception as e:
            d.text((cx + 10, cy + 10), "load failed: %s" % e, fill=(255, 120, 120))
        label = "%s  %s" % (r["label"], r["bat"].replace("run_amd_gpu_", "")
                            .replace(".bat", ""))
        d.rectangle([cx, cy, cx + cell, cy + cell], outline=(90, 90, 100))
        d.text((cx + 2, cy + cell + 8), label, fill=(235, 235, 240))
    path = os.path.join(HERE, "flag_sweep_sheet.png")
    canvas.save(path)
    return path


rows = []
if os.path.exists(RESULT):
    rows = json.load(open(RESULT, encoding="utf-8"))
done = {r["label"] for r in rows}

for i, (label, bat, note) in enumerate(CONFIGS, 1):
    if label in done:
        log("[%d/%d] %s 已完成，跳过" % (i, len(CONFIGS), label))
        continue
    log("\n[%d/%d] 配置 %s  %s" % (i, len(CONFIGS), label, note))
    log("    bat: %s" % bat)
    stop_comfy()
    launch(bat)
    if not wait_ready():
        log("    启动失败或超时")
        rows.append({"label": label, "bat": bat, "note": note,
                     "error": "startup timeout", "files": []})
        save(rows)
        continue
    flags = read_actual_flags()
    log("    实际 flags: %s" % json.dumps(flags, ensure_ascii=False))
    prefix = "SWEEP_%s_T82" % label
    try:
        st, files, secs = run_one(prefix)
        log("    -> %s %s (%d秒)" % (st, files, secs))
    except urllib.error.HTTPError as e:
        st, files, secs = "HTTP_ERR", [], 0
        log("    -> 提交失败 %s" % e.read().decode("utf-8", "replace")[:300])
    rows.append({"label": label, "bat": bat, "note": note, "flags": flags,
                 "status": st, "files": files, "seconds": secs})
    save(rows)

log("\n全部配置跑完")
sheet_path = sheet(rows)
if sheet_path:
    log("对照图: %s" % sheet_path)

log("\n恢复已验证可用的 default_attention 配置")
stop_comfy()
launch("run_amd_gpu_default_attention.bat")
wait_ready()
save(rows)
log("完成")