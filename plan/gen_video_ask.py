# -*- coding: utf-8 -*-
"""交互式 MiniMax H3 T2V 生成（复用 gen_video.py 的核心逻辑）。

除提示词外所有参数都有默认值，直接回车即用：
  尺寸默认 640x480（480P），时长默认 5s，Turbo LoRA 默认关闭。

路径相对本脚本：workflow json 必须与本脚本同目录；换目录/换机可用。
"""
import os, sys, json, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import gen_video

gen_video.WF = os.path.join(BASE, 'video_minimax_h3_t2v_uncensored_enhancer.json')

SHARED_OUT = r'D:\Comfy-Desktop\ComfyUI-Shared\output'
gen_video.OUT = SHARED_OUT if os.path.isdir(SHARED_OUT) else os.path.join(BASE, 'output')

SEED_DEFAULT = 757358688076805
STEPS_DEFAULT = 20


def ask(msg, default, cast):
    raw = input(msg).strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        print('  无效输入，用默认 %s' % default)
        return default


def ask_prompt():
    while True:
        p = input('提示词: ').strip()
        if p:
            return p
        print('  提示词不能为空')


def ask_size():
    print('画面尺寸: [回车]=640x480（480P 默认） | 2=960x540 | 3=1280x720 | 自定义如 832x480')
    raw = input('尺寸: ').strip().lower()
    presets = {'': (640, 480), '2': (960, 540), '3': (1280, 720)}
    if raw in presets:
        return presets[raw]
    try:
        w, h = raw.split('x')
        return int(w), int(h)
    except ValueError:
        print('  无法解析，用默认 640x480')
        return (640, 480)


def ask_turbo():
    raw = input('开启 Turbo LoRA（6 步加速，质量略降）? [N] ').strip().lower()
    return raw in ('y', 'yes', '1')


def print_outputs(outputs):
    for nid, outs in outputs.items():
        for k, v in outs.items():
            items = v if isinstance(v, list) else [v]
            for it in items:
                if isinstance(it, dict) and it.get('filename', '').endswith('.mp4') and \
                   (it.get('animated') or k in ('gifs', 'videos')):
                    sub = it.get('subfolder') or ''
                    src = os.path.join(gen_video.OUT, sub, it['filename']) if sub else os.path.join(gen_video.OUT, it['filename'])
                    print('output:', gen_video.API + '/view?filename=' + urllib.parse.quote(it['filename'], safe='') +
                          ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '') + '&type=' + it.get('type', 'output'))
                    print('local file:', src)


def main():
    prompt = ask_prompt()
    width, height = ask_size()
    duration = ask('时长（秒）[5]: ', 5.0, float)
    turbo = ask_turbo()

    if width * height > 640 * 480:
        print('WARN: 超过 480P 硬性 VRAM 上限，可能爆显存')

    gen_video.free_vram()
    graph = gen_video.build_graph(prompt, width, height, duration, SEED_DEFAULT, STEPS_DEFAULT, turbo)
    pid = gen_video.submit(graph)
    print('prompt_id:', pid)
    print('queue: submitted (lora=%s, %dx%d, %.0fs)' % ('on' if turbo else 'off', width, height, duration))

    print_outputs(gen_video.wait(pid))


if __name__ == '__main__':
    sys.exit(main())