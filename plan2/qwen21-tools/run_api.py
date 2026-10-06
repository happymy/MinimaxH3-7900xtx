"""Execute a converted api_*.json through the running ComfyUI server."""
import json, sys, time, urllib.request
# 本地 API 直连：系统代理 127.0.0.1:26561 不放行 loopback 会回 404；
# 空 ProxyHandler 同时绕过环境变量与注册表代理，不依赖启动方式。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BASE = "http://127.0.0.1:8188"
path = sys.argv[1]
prefix = sys.argv[2] if len(sys.argv) > 2 else "wftest"
api = json.load(open(path, encoding="utf-8"))
# ImageCompare stores no widget values at all in the official template, so the API
# has nothing to send for its required `compare_view`; it is a preview-only node.
for k in [k for k, v in api.items() if v["class_type"] == "ImageCompare"]:
    del api[k]
for node in api.values():
    if node["class_type"] in ("SaveImage", "SaveImageAdvanced"):
        node["inputs"]["filename_prefix"] = prefix


def get(p):
    return json.loads(OPENER.open(BASE + p, timeout=60).read())


req = urllib.request.Request(BASE + "/prompt",
                             data=json.dumps({"prompt": api, "client_id": "wf-test"}).encode(),
                             headers={"Content-Type": "application/json"})
try:
    res = json.loads(OPENER.open(req, timeout=120).read())
except urllib.error.HTTPError as e:
    print("REJECTED", e.code)
    print(e.read().decode(errors="replace")[:4000])
    sys.exit(1)

print("prompt_id", res["prompt_id"], "node_errors", json.dumps(res.get("node_errors", {}), ensure_ascii=False)[:1500])
pid = res["prompt_id"]
t0 = time.time()
while time.time() - t0 < 2400:
    time.sleep(8)
    h = get("/history/" + pid)
    if pid in h:
        out = h[pid]
        print("status:", json.dumps(out.get("status", {}), ensure_ascii=False)[:1500])
        for node, val in out.get("outputs", {}).items():
            print("OUTPUT", node, json.dumps(val, ensure_ascii=False)[:800])
        break
    q = get("/queue")
    print("[%4.0fs] running=%d pending=%d" % (time.time() - t0, len(q.get("queue_running", [])), len(q.get("queue_pending", []))), flush=True)
else:
    print("TIMEOUT")
    sys.exit(1)
