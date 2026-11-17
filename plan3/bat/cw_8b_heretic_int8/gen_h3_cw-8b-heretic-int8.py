# -*- coding: utf-8 -*-
"""MiniMax H3 单段长片（上下文窗口版）—— ComfyUI API 直连。【8B 破限(Heretic) int8 编码器】

与 multisegment 版的区别：不切段、不用首帧续接，整段一次出，靠 MiniMaxH3ContextWindows
把采样切成重叠窗口 —— 单段可到 15 s / 362 帧（部署总结 §7.9）。

窗口参数（节点只有 5 个输入，**没有窗口数**，由帧数自动算）：
    context_length   单窗帧数   17n+5，默认 107
    context_overlap  相邻重叠   17n+5 且 ≤ length-5，默认 22
    默认组合 1344x768 x 362 帧 → 4 窗口，本机实测 874 s

显存（24 GB，判据见 §7.9）：
    1344x768 的预算是 4 个 107 帧窗口；第 5 个贴线（耗时 +11%），第 6 个必爆。
    爆了不是 OOM，是每步重搬 8.4 GB 权重，慢 3-4 倍。

用法:
    python gen_h3_cw-8b-heretic-int8.py            # 交互式：提示词 / 尺寸 / 时长 / ctx / ov / 步数 / 种子
    python gen_h3_cw-8b-heretic-int8.py --duration 15
    python gen_h3_cw-8b-heretic-int8.py --size 864x480 --duration 27
    python gen_h3_cw-8b-heretic-int8.py --prompt-file prompt.txt --ctx 124 --ov 39
    python gen_h3_cw-8b-heretic-int8.py --duration 15 --dry-run    # 只出图与预估
"""

import argparse
import importlib.util
import json
import os
import random
import shutil
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(
    HERE, '..', 'multisegment_8b_heretic_int8', 'gen_h3_multisegment-8b-heretic-int8.py'))
CWP = os.path.normpath(os.path.join(HERE, '..', 'bench', 'probe_cw.py'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 图构造 + 提交/等待/下载复用 multisegment 版；窗口数与节点插入复用探针
# （两处都照 ComfyUI 源码写的，不在这里再抄一遍公式）
gen = load(BASE, 'h3_multi')
cw = load(CWP, 'h3_probe_cw')

DEFAULT_SIZE = (1344, 768)   # H3 原生画布，窗口的意义就在原生尺寸上跑长片
DEFAULT_CTX, DEFAULT_OV = 107, 22
TRAIN_MAX = 362              # 上游训练范围上限（124-362，5-15 s），超了画面先发散
SIT_REF, PX_REF, CTX_REF = 874 / 24, 1344 * 768, 107   # 1344x768/107 窗/6 步实测 874 s


def latent_t(v):
    return 2 if v <= 5 else ((v - 5) // 17) * 5 + 2


def parse_size(raw):
    try:
        w, h = raw.lower().split('x')
        return int(w), int(h)
    except ValueError:
        raise SystemExit('--size 要写成 宽x高，例如 1344x768')


def check_cw(ctx, ov):
    for name, v in (('context_length', ctx), ('context_overlap', ov)):
        if v < 5 or (v - 5) % 17:
            raise SystemExit('%s=%d 不合法：必须 17n+5（22/39/56/73/90/107/124/141…）' % (name, v))
    if ov > ctx - 5:
        raise SystemExit('context_overlap=%d 超过 context_length-5=%d'
                         '（节点会自己夹到 %d，要更长的重叠就加大 context_length）'
                         % (ov, ctx - 5, ctx - 5))


def predict(w, h, ctx, ov, frames, steps):
    """返回 (窗口数, 下界秒, 上界秒)。

    锚点是 §7.9 的 1344x768/107/四窗实测（874 s）按 像素^1.62 × 窗长^1.62 缩放；
    贴显存线还会再多约 11%，所以上界给 +15%。三个实测点都落在区间内。
    """
    n = cw.est_windows(frames, ctx, ov)
    ratio = ((w * h) / PX_REF) * (latent_t(ctx) / latent_t(CTX_REF))
    lo = n * steps * SIT_REF * ratio ** 1.62
    return n, lo, lo * 1.15


def download(url, dest):
    with gen.OPENER.open(url, timeout=600) as r, open(dest, 'wb') as f:
        shutil.copyfileobj(r, f)


def ask_prompt():
    """只认本目录的 prompt.txt —— gen.ask_prompt 会去读 multisegment 那份，这里不能串。"""
    p = os.path.join(HERE, 'prompt.txt')
    if os.path.exists(p):
        text = gen.read_prompt_file(p)
        print('发现 prompt.txt，内容如下：')
        print('-' * 40)
        print(text)
        print('-' * 40)
        if input('使用以上内容？(回车=是 / n=重新输入): ').strip().lower() in ('', 'y', 'yes', '是'):
            return text
    while True:
        text = input('提示词: ').strip()
        if text:
            return text
        print('  提示词不能为空')


def main():
    ap = argparse.ArgumentParser(description='MiniMax H3 单段长片（窗口版）')
    ap.add_argument('--prompt')
    ap.add_argument('--prompt-file', help='UTF-8/GBK 自动识别，整文件当一条提示词')
    ap.add_argument('--size', default=None, help='宽x高，默认 1344x768')
    ap.add_argument('--duration', type=float, default=None, help='秒，默认 15（向上吸附到 17n+5）')
    ap.add_argument('--steps', type=int, default=6, choices=(4, 6, 8))
    ap.add_argument('--seed', type=int, default=None, help='默认随机')
    ap.add_argument('--ctx', type=int, default=None,
                    help='context_length，17n+5，默认 107（交互模式下会问）')
    ap.add_argument('--ov', type=int, default=None,
                    help='context_overlap，17n+5 且 ≤ length-5，默认 22（交互模式下会问）')
    ap.add_argument('--out', default=None)
    ap.add_argument('--dry-run', action='store_true', help='只打印图与预估，不提交')
    a = ap.parse_args()

    interactive = not a.prompt and not a.prompt_file

    if a.prompt:
        prompt = a.prompt.strip()
    elif a.prompt_file:
        prompt = gen.read_prompt_file(a.prompt_file)
    else:
        prompt = ask_prompt()
    if not prompt:
        raise SystemExit('提示词为空')

    size = parse_size(a.size) if a.size else DEFAULT_SIZE
    duration = a.duration if a.duration is not None else gen.ask('时长（秒）[15]: ', 15.0, float)
    if duration <= 0:
        raise SystemExit('时长要大于 0')

    ctx = a.ctx
    if ctx is None:
        ctx = gen.ask('context_length（17n+5，窗口越长看到的连续时间越长、越吃显存）[%d]: ' % DEFAULT_CTX,
                      DEFAULT_CTX, int) if interactive else DEFAULT_CTX
    ov = a.ov
    if ov is None:
        ov = gen.ask('context_overlap（17n+5，重叠越大接缝越软、窗口越多）[%d]: ' % DEFAULT_OV,
                     DEFAULT_OV, int) if interactive else DEFAULT_OV
    check_cw(ctx, ov)

    length = gen.frames_for(duration)
    steps = a.steps
    seed = a.seed if a.seed is not None else random.randint(0, 2 ** 63)

    n, lo, hi = predict(size[0], size[1], ctx, ov, length, steps)
    print('>>> %dx%d, %d 帧 (%.2f s), %d 步, seed=%d' % (size[0], size[1], length, length / 24, steps, seed))
    print('    ctx=%d ov=%d -> %d 个窗口，预估 %.0f-%.0f s (%.1f-%.1f min)'
          % (ctx, ov, n, lo, hi, lo / 60, hi / 60))

    if length > TRAIN_MAX:
        print('    ! %d 帧超出训练范围（124-362 / 5-15 s），画面可能发散且不报错' % length)
    if n >= 5 and size[0] * size[1] >= 900000:
        print('    ! %d 个窗口在这档像素上会贴显存线，实测耗时 +11%%；到 6 个就是 3-4 倍慢车道' % n)

    graph = gen.build_graph(prompt, size[0], size[1], length, steps, seed)
    cw.add_cw(graph, ctx, ov, freenoise=True)

    if a.dry_run:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
        return 0

    out = a.out or 'h3_cw_%d.mp4' % seed
    stem, ext = os.path.splitext(out)
    i = 1
    while os.path.exists(out):
        out = '%s_%d%s' % (stem, i, ext)
        i += 1

    gen.free_vram()
    pid = gen.submit(graph)
    print('    prompt_id:', pid)
    outputs = gen.wait(pid, timeout=max(1800, secs * 3), cur=1, total=1)
    v = gen.find_video_file(outputs, '.mp4')
    if v is None:
        raise SystemExit('outputs 里没有 mp4: ' + json.dumps(outputs, ensure_ascii=False)[:1500])
    sub = v.get('subfolder') or ''
    url = (gen.API + '/view?filename=' + urllib.parse.quote(v['filename'], safe='')
           + ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '')
           + '&type=' + v.get('type', 'output'))
    download(url, out)
    print('done:', os.path.abspath(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
