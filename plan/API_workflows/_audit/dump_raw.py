"""Ground-truth dump of every RAW workflow.

No assumptions: print the full node list, every input key, and every link so the
adaptation can be written against what is actually there.
"""
from __future__ import annotations

import json
from pathlib import Path

RAW = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW")


def show(path: Path) -> None:
    wf = json.loads(path.read_text(encoding="utf-8"))
    print("=" * 96)
    print(f"### {path.name}   ({len(wf)} nodes)")
    print("=" * 96)
    for nid, n in wf.items():
        if not isinstance(n, dict):
            print(f"[{nid}]  <non-dict> {n!r}")
            continue
        title = (n.get("_meta") or {}).get("title") or ""
        print(f"\n[{nid}] {n.get('class_type')}   {title!r}")
        for ik, iv in (n.get("inputs") or {}).items():
            if isinstance(iv, list) and len(iv) == 2 and isinstance(iv[0], str):
                src = iv[0]
                sname = wf.get(src, {}).get("class_type", "?") if isinstance(wf.get(src), dict) else "?"
                print(f"    {ik:32} <- link {src}[{iv[1]}]  ({sname})")
            elif isinstance(iv, list):
                print(f"    {ik:32} = {json.dumps(iv, ensure_ascii=False)[:150]}")
            elif isinstance(iv, str) and len(iv) > 120:
                print(f"    {ik:32} = {iv[:120]!r}...  [{len(iv)} chars]")
            else:
                print(f"    {ik:32} = {json.dumps(iv, ensure_ascii=False)[:150]}")
    print()


for p in sorted(RAW.glob("*.json")):
    show(p)