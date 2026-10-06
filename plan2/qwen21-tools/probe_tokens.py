# -*- coding: utf-8 -*-
"""Run the 7 bisect prompts through the real ComfyUI Qwen-Image-2.1 tokenizer.

Then replay the keep-mask from QwenImage21TEModel.encode_token_weights
(qwen_image21.py L52-61) to show exactly what text reaches the DiT.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

COMFY = r"D:\localAI\ComfyUI-last\ComfyUI_windows_portable\ComfyUI"
sys.path.insert(0, COMFY)

import comfy.text_encoders.qwen_image21 as q21

PROMPTS = [
    ("V0_full", "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。"),
    ("V1_noQual", "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。人物孤立，影棚光，"),
    ("V2_noAbstract", "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。"),
    ("V3_noStudioLight", "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。高清，细节丰富，锐利对焦，高质量。"),
    ("V4_noHair", "11岁中国女孩，站姿居中。上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。女孩漂亮、文静、身材高挑。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。"),
    ("V5_noClothes", "11岁中国女孩，站姿居中。长发，头发梳成辫子，搭在左肩膀上，女孩漂亮、文静、身材高挑。人物孤立，影棚光，高清，细节丰富，锐利对焦，高质量。"),
    ("V6_factsOnly", "11岁中国女孩，站姿居中。上身穿白色短袖衬衫，下身穿深蓝色裙子，白色厚裤袜，亮面小皮鞋。"),
]

IM_END = 151644

tok = q21.QwenImage21Tokenizer(embedding_directory=None, tokenizer_data={})
sd = tok.qwen3vl_8b                       # Qwen3VLSDTokenizer
hf = sd.tokenizer                         # underlying HF tokenizer object
print("内置 tokenizer 目录: %s" % getattr(sd, "tokenizer_path", "?"))
print("llama_template: %r" % tok.llama_template)
print()

print("=== 关键：文本里的 <|im_end|> 是否被编码成 token %d ===" % IM_END)
for probe in ("<|im_end|>", "<|im_start|>"):
    r = hf(probe)
    ids = r["input_ids"] if isinstance(r, dict) else r.input_ids
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    print("   编码 %-14r -> %-24s 命中151644: %s" % (
        probe, ids, IM_END in ids))
print()

hdr = "%-16s %-6s %-9s %-11s %-8s %s" % ("变体", "总token", "151644数", "im_starts[1]", "丢弃数", "掩码后剩下的文本")
print("=" * 132)
print(hdr)
print("=" * 132)

for tag, text in PROMPTS:
    out = tok.tokenize_with_weights(text, prevent_empty_text=True)
    key = next(iter(out))
    toks = [t for row in out[key] for t in row]
    ints = [t[0] for t in toks if isinstance(t[0], int)]

    im_starts = [i for i, t in enumerate(ints) if t == IM_END]
    cut = im_starts[1] if len(im_starts) > 1 else 0
    kept = ints[cut:]

    try:
        kept_text = hf.decode(kept, skip_special_tokens=False)
    except Exception:
        kept_text = "?"

    print("%-16s %-6d %-9d %-11s %-8d %s" % (
        tag, len(ints), len(im_starts),
        (str(cut) if cut else "0(不丢弃)"),
        cut, repr(kept_text)[:70]))
