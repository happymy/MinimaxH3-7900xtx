# -*- coding: utf-8 -*-
"""把 plan1 的 8B / 8B-heretic 脚本族移植到 plan4（一次性迁移工具）。

只改模型常量与 ClipProj 节点，其余逻辑（分段、首帧、参考图、QC）原样保留。
8B 编码器用 plan3 的 int8_convrot 版（省显存且实测跑通），不用 plan1 的 fp8 版。
"""
import os

SRC = r"D:\localAI\ComfyUI-last\plan\bat"
DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bat")
DIRS = [
    "multisegment_8b", "multisegment_8b_heretic",
    "ref2va_8b", "ref2va_8b_heretic",
    "scenes_8b", "scenes_8b_heretic",
    "scenes_ref_8b", "scenes_ref_8b_heretic",
]
REPL = [
    ("'minimax_h3_fl2va_pruned-Q4_K_M.gguf'", "'Sulphur-3-Q4_K_M.gguf'"),
    ("'minimax_h3_ref2va_pruned-Q4_K_M.gguf'", "'Sulphur-3-Q4_K_M.gguf'"),
    ("'qwen3vl_8b_fp8_scaled.safetensors'", "'qwen3vl_8b_int8_convrot.safetensors'"),
    ("'qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors'",
     "'qwen3-vl-8b-heretic-1.3.0_int8_convrot.safetensors'"),
    ("'minimax_h3_video_vae_fp16.safetensors'", "'minimax_h3_video_vae_int8_convrot.safetensors'"),
    ("'CCTechClipProjLoader', 'inputs': {'clip_name': CLIP_NAME, 'type': CLIP_TYPE, 'projection': CLIP_PROJ}",
     "'ClipProjLoader', 'inputs': {'clip_name': CLIP_NAME, 'type': CLIP_TYPE, 'projection': CLIP_PROJ, 'device': 'cuda:0', 'mode': 'dynamic'}"),
]


def main():
    n = 0
    for d in DIRS:
        src_dir = os.path.join(SRC, d)
        for name in os.listdir(src_dir):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(src_dir, name), encoding="utf-8") as f:
                text = f.read()
            for a, b in REPL:
                text = text.replace(a, b)
            with open(os.path.join(DST, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print("%-20s -> %s" % (d, name))
            n += 1
    print("migrated %d scripts" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
