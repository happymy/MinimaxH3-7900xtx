# -*- coding: utf-8 -*-
"""Build a labelled contact sheet from the BISECT_* outputs for side-by-side review."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI\output"
DEST = r"D:\localAI\ComfyUI-last\qwen21-tools\对照图.png"

manifest = json.load(open(os.path.join(HERE, "bisect_manifest.json"), encoding="utf-8"))

items = []
for m in manifest:
    if not m.get("files"):
        continue
    fn = sorted(m["files"])[-1]
    p = os.path.join(OUT, fn)
    if os.path.exists(p):
        items.append((m["tag"], fn, p))

if not items:
    print("没有可用的输出图")
    sys.exit(1)

COLS = 4
THUMB = 384
LABEL_H = 26
PAD = 8

rows = (len(items) + COLS - 1) // COLS
W = COLS * THUMB + (COLS + 1) * PAD
H = rows * (THUMB + LABEL_H) + (rows + 1) * PAD

sheet = Image.new("RGB", (W, H), (24, 24, 26))
dr = ImageDraw.Draw(sheet)

for i, (tag, fn, p) in enumerate(items):
    r, c = divmod(i, COLS)
    x = PAD + c * (THUMB + PAD)
    y = PAD + r * (THUMB + LABEL_H + PAD)
    im = Image.open(p).convert("RGB").resize((THUMB, THUMB), Image.LANCZOS)
    sheet.paste(im, (x, y))
    dr.rectangle([x, y, x + THUMB - 1, y + THUMB - 1], outline=(90, 90, 95))
    dr.text((x + 2, y + THUMB + 6), "%s  %s" % (tag, fn[-9:-4]), fill=(235, 235, 235))

sheet.save(DEST)
print("对照图: %s  (%dx%d, %d 张)" % (DEST, W, H, len(items)))
for tag, fn, _ in items:
    print("   %-18s %s" % (tag, fn))
