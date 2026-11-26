# -*- coding: utf-8 -*-
"""给 plan4 的生成脚本套上 S3 官方采样参数（幂等）。

官方 example_workflow.json 的 note：
  CFG 1；shift_video 12 / shift_audio 3；Euler；simple schedule。
S3 是 guidance-distilled，negative prompt 在 CFG 1 下被忽略。

改动：
  1. 在 UnetLoaderGGUF 后插 MiniMaxH3SigmaShift(shift_video=12, shift_audio=3)
  2. BasicGuider / BasicScheduler 的 model 改指向 SigmaShift
  3. KSamplerSelect 的 res_multistep / er_sde 改 euler
"""
import glob
import os

BAT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bat")
HOOK = "'1b': {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['1', 0], 'shift_video': 12.0, 'shift_audio': 3.0}},"


def patch(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "MiniMaxH3SigmaShift" in text:
        return "already patched"
    out = []
    inserted = 0
    for line in text.split("\n"):
        out.append(line)
        if "'class_type': 'UnetLoaderGGUF'" in line and "'1':" in line:
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + HOOK)
            inserted += 1
    text = "\n".join(out)
    text = text.replace("'model': ['1', 0]", "'model': ['1b', 0]")
    text = text.replace("'sampler_name': 'res_multistep'", "'sampler_name': 'euler'")
    text = text.replace("'sampler_name': 'er_sde'", "'sampler_name': 'euler'")
    # 上面的全局替换会把 SigmaShift 自己的 model 也改成 1b（自引用），改回来
    text = text.replace(
        "'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['1b', 0]",
        "'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': ['1', 0]")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return "patched %d graph(s)" % inserted


def main():
    files = [os.path.join(BAT, "gen_sulphur.py")] + sorted(glob.glob(os.path.join(BAT, "*8b*.py")))
    for p in files:
        print("%-38s %s" % (os.path.basename(p), patch(p)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
