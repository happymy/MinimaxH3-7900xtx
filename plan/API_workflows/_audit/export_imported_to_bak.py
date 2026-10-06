"""Export the workflows currently imported into Calliope's library to RAW/bak.

Source of truth is the live SQLite library (data/calliope.db), not the repo:
whatever the user actually imported - including hand-edited title tags and
saved input schemas - is what gets archived.

Each workflow is written as its raw API-format JSON plus a sidecar `.meta.json`
carrying the library metadata (kind, profile, schemas, enabled) that the JSON
itself does not encode.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

BACKEND = Path(r"D:\localAI\ComfyUI-last\src\Calliope\calliope-backend")
DB = BACKEND / "data" / "calliope.db"
BAK = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW\bak")

# Node ids are opaque; only strip characters that are illegal in a filename.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def slug(name: str) -> str:
    s = _UNSAFE.sub("-", name).strip("-")
    return s or "workflow"


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"library DB not found: {DB}")
    BAK.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM workflows ORDER BY id").fetchall()
    if not rows:
        print("library is empty - nothing exported")
        return

    for r in rows:
        row = dict(r)
        wf = json.loads(row["workflow_json"])
        stem = f"{row['id']:03d}-{slug(row['name'])}"
        wf_path = BAK / f"{stem}.json"
        wf_path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")

        def maybe(key: str):
            v = row.get(key)
            if not v:
                return None
            try:
                return json.loads(v)
            except (TypeError, ValueError):
                return v

        meta = {
            "library_id": row["id"],
            "name": row["name"],
            "kind": row["kind"],
            "prompt_profile": row["prompt_profile"],
            "is_enabled": row["is_enabled"],
            "description": row.get("description"),
            "created_at": row.get("created_at"),
            "input_schema": maybe("input_schema"),
            "output_schema": maybe("output_schema"),
            "node_count": len(wf),
            "source": str(DB),
        }
        (BAK / f"{stem}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        tagged = sum(
            1
            for n in wf.values()
            if isinstance(n, dict)
            and re.search(r"\((input|output)", ((n.get("_meta") or {}).get("title") or ""), re.I)
        )
        print(f"  exported #{row['id']:3d} {row['name']!r}")
        print(f"           -> {wf_path.name}  (nodes={len(wf)}, tagged={tagged}, profile={row['prompt_profile']})")

    print(f"\ndone -> {BAK}")


if __name__ == "__main__":
    main()