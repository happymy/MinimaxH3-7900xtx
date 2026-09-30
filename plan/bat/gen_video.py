# -*- coding: utf-8 -*-
"""通过 ComfyUI API 用提示词生成视频（MiniMax H3 T2V，本地 GGUF）。

用法:
    python gen_video.py --prompt "一只猫在跑步" [--width 640 --height 480 --duration 5] [--seed 12345]
    python gen_video.py --prompt "..." --turbo     # 启用 Lightning/Turbo LoRA，6 步加速

默认 480P / 5s（硬性 VRAM 上限），步数 20；`--turbo` 走 lora(600step v4, strength 1.0)+6 步。
"""
import json, urllib.request, urllib.error, urllib.parse, time, sys, argparse, os

WF = r'D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\user\default\workflows\video_minimax_h3_t2v_uncensored_enhancer.json'
API = 'http://127.0.0.1:8188'
OUT = r'D:\Comfy-Desktop\ComfyUI-Shared\output'


def build_graph(prompt, width, height, duration, seed, steps, turbo):
    wf = json.load(open(WF, encoding='utf-8'))
    inst = [n for n in wf['nodes'] if n['id'] == 140][0]
    subname = inst['type']
    sg = next(s for s in wf['definitions']['subgraphs'] if s['id'] == subname)

    links_out = {l[0]: l for l in wf['links']}       # outer links array
    links_in = {l['id']: l for l in sg['links']}      # inner links dict

    # 重写实例 widgets_values（索引来自 T2V 外层 node 140，已验证）
    wv = inst['widgets_values']
    wv[0] = prompt
    wv[1] = width
    wv[2] = height
    wv[3] = duration
    wv[4] = seed
    wv[9] = turbo
    wv[10] = steps

    inst_inputs = inst['inputs']
    inst_widget_idx = [s for s in inst_inputs if s.get('widget')]
    inst_wvals = inst.get('widgets_values', [])

    def instance_value(slot_name):
        for s in inst_inputs:
            if s['name'] == slot_name:
                if s.get('link') is not None:
                    ol = links_out[s['link']]
                    return [str(ol[1]), ol[2]]
                if s.get('widget'):
                    return inst_wvals[inst_widget_idx.index(s)]
                return None
        return None

    def node_inputs(n):
        inp = n.get('inputs', [])
        wvals = n.get('widgets_values', [])
        wi = 0
        out = {}
        for slot in inp:
            if slot.get('link') is not None:
                if slot.get('widget'):
                    wi += 1
                continue
            if slot.get('widget'):
                out[slot['name']] = wvals[wi] if wi < len(wvals) else None
                wi += 1
        return out

    api = {}
    for n in wf['nodes']:
        if n['id'] == 140 or n['type'] == 'MarkdownNote':
            continue
        api[str(n['id'])] = {'class_type': n['type'], 'inputs': node_inputs(n)}
    for n in sg['nodes']:
        api['inner_' + str(n['id'])] = {'class_type': n['type'], 'inputs': node_inputs(n)}

    for link in sg['links']:
        if link['target_id'] == -20:
            continue
        tkey = 'inner_' + str(link['target_id'])
        tname = next(nn for nn in sg['nodes'] if nn['id'] == link['target_id'])['inputs'][link['target_slot']]['name']
        if link['origin_id'] == -10:
            val = instance_value(sg['inputs'][link['origin_slot']]['name'])
            if val is not None:
                api[tkey]['inputs'][tname] = val
            continue
        api[tkey]['inputs'][tname] = ['inner_' + str(link['origin_id']), link['origin_slot']]

    for link in wf['links']:
        if link[1] != 140:
            continue
        il = next(l for l in sg['links'] if l['target_id'] == -20)
        oi = next(n for n in wf['nodes'] if n['id'] == link[3])
        iname = next(s['name'] for s in oi['inputs'] if s.get('link') == link[0])
        api[str(link[3])]['inputs'][iname] = ['inner_' + str(il['origin_id']), il['origin_slot']]

    return api


def free_vram():
    """POST /free：卸载模型并释放 DynamicVRAM 残留物理页。

    aimdo 的 fault-in 权重在任务完成后不自动释放，连续生成时上段残留
    会挤占 VRAM，第二段主模型 fault-in 无空间 → 乒乓 swap → Model
    Initializing 卡死。每次提交前清场可保证连续生成可靠性（实测 3 连跑全过）。
    """
    req = urllib.request.Request(API + '/free',
                                 data=json.dumps({'unload_models': True, 'free_memory': True}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        urllib.request.urlopen(req, timeout=15)
        print('vram: freed (unloaded models)')
    except Exception as e:
        print('WARN: free_vram failed: %s' % e)


def submit(graph):
    req = urllib.request.Request(API + '/prompt',
                                 data=json.dumps({'prompt': graph}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError('submit failed: ' + e.read().decode('utf-8', 'replace')[:2000])
    if 'error' in resp:
        raise RuntimeError('submit error: ' + json.dumps(resp, ensure_ascii=False)[:2000])
    return resp['prompt_id']


def wait(pid, timeout=3600, interval=5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            h = json.loads(urllib.request.urlopen(f'{API}/history/{pid}', timeout=5).read())
        except Exception:
            time.sleep(interval)
            continue
        if pid in h:
            st = h[pid].get('status', {})
            for m in st.get('messages', []):
                if m[0] == 'execution_error':
                    raise RuntimeError('execution error: ' + json.dumps(m[1], ensure_ascii=False)[:2000])
            if st.get('status_str') in ('success', 'completed'):
                print('done  elapsed %.1fs' % (time.time() - start))
                return h[pid].get('outputs', {})
            if st.get('status_str') == 'error':
                raise RuntimeError('queue error: ' + json.dumps(st, ensure_ascii=False)[:2000])
        print('  running %.0fs' % (time.time() - start))
        time.sleep(interval)
    raise RuntimeError('timeout')


def main():
    ap = argparse.ArgumentParser(description='MiniMax H3 T2V video via ComfyUI API')
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--width', type=int, default=640)
    ap.add_argument('--height', type=int, default=480)
    ap.add_argument('--duration', type=float, default=5)
    ap.add_argument('--seed', type=int, default=757358688076805)
    ap.add_argument('--steps', type=int, default=20)
    ap.add_argument('--turbo', action='store_true', default=False)
    a = ap.parse_args()

    if a.width * a.height > 640 * 480:
        print('WARN: 超过 480P 硬性 VRAM 上限，可能爆显存')

    free_vram()
    graph = build_graph(a.prompt, a.width, a.height, a.duration, a.seed, a.steps, a.turbo)
    pid = submit(graph)
    print('prompt_id:', pid)
    print('queue: submitted')

    outputs = wait(pid)
    # 定位视频文件（节点 92 走 'images' 键 + animated；gifs/videos 为 VHS 兼容路径）
    for nid, outs in outputs.items():
        for k, v in outs.items():
            items = v if isinstance(v, list) else [v]
            for it in items:
                if isinstance(it, dict) and it.get('filename', '').endswith('.mp4') and \
                   (it.get('animated') or k in ('gifs', 'videos')):
                    sub = it.get('subfolder') or ''
                    src = os.path.join(OUT, sub, it['filename']) if sub else os.path.join(OUT, it['filename'])
                    print('output:', API + '/view?filename=' + urllib.parse.quote(it['filename'], safe='') +
                          ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '') + '&type=' + it.get('type', 'output'))
                    print('local file:', src)


if __name__ == '__main__':
    sys.exit(main())