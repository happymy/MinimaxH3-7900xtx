# -*- coding: utf-8 -*-
"""step0: unload every model and wait until the VRAM is actually back.

    python step0_free.py                 # wait until ~total-1.5 GB is free
    python step0_free.py --target 21     # or name the threshold yourself (GB)
    python step0_free.py --no-wait       # fire /free and leave

Run it right before you hit Queue, not after the previous run. This is the
step the old multisegment script did at the top of every segment
(``free_vram()`` in gen_h3_multisegment-8b.py).

Why not a node in the graph: ComfyUI's own /free handler runs
``unload_all_models()``, ``e.reset()``, ``gc.collect()`` and then
``soft_empty_cache()`` (main.py:416-433). A node inside the graph can call the
first and the last, but it cannot run gc while the prompt it runs in still holds
the references -- so the models come back from ``detach()`` as live objects and
the VRAM stays taken. That is the "unload is not complete" you observed.

Exit code is 0 only when the threshold was reached, so a batch wrapper can stop
before wasting a 5 minute run on an OOM.
"""

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
# The system proxy answers 404 for 127.0.0.1 (see plan/bat/free_vram/free_vram.py).
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
GB = 1024 ** 3


def api(path, data=None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=body, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {})
    raw = OPENER.open(req, timeout=15).read()
    return json.loads(raw) if raw.strip() else {}


def snapshot():
    dev = api("/system_stats")["devices"][0]
    queue = api("/queue")
    return (dev["vram_free"], dev["vram_total"],
            len(queue["queue_running"]) + len(queue["queue_pending"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None, help="default 127.0.0.1:8188")
    ap.add_argument("--target", type=float, default=None,
                    help="GB of free VRAM to wait for (default: total - 1.5)")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--no-wait", action="store_true")
    a = ap.parse_args()

    global BASE
    if a.host:
        BASE = a.host if "://" in a.host else "http://" + a.host

    free, total, queued = snapshot()
    print("before  : vram_free=%.2f / %.2f GB  queued=%d" % (free / GB, total / GB, queued))
    if queued:
        print("note    : a prompt is queued; /free only takes effect after it finishes")

    api("/free", {"unload_models": True, "free_memory": True})
    if a.no_wait:
        print("posted  : /free (not waiting)")
        return 0

    target = (a.target * GB) if a.target else (total - 1.5 * GB)
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        time.sleep(1.0)
        free, total, _ = snapshot()
        print("  %4.1fs : vram_free=%.2f GB" % (time.time() - t0, free / GB))
        if free >= target:
            print("ok      : %.2f GB free (target %.2f), took %.1fs"
                  % (free / GB, target / GB, time.time() - t0))
            return 0

    print("FAILED  : only %.2f GB free after %.0fs (target %.2f)."
          % (free / GB, a.timeout, target / GB))
    print("          the DiT or a VAE did not go back; the next run will likely OOM.")
    print("          fallbacks: restart ComfyUI, or compare with --disable-dynamic-vram.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
