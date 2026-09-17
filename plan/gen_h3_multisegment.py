# -*- coding: utf-8 -*-
"""MiniMax H3 多段视频生成（首尾帧拼接）—— 通过 ComfyUI API。

用法:
    python gen_h3_multisegment.py --prompt "第一段提示词" --segments 3 [--size 864x480 --duration 5 --steps 20 --seed 123]
    python gen_h3_multisegment.py        # 交互式（同 gen_video_ask.bat 风格，回车用默认）

分段提示词:
    --prompt 支持用换行分多条，行数决定段落数（每段一条）；若只有一条则所有段落复用。
    --segments 优先于换行数。

拼接方式:
    段 0 走 t2v（无参考帧）；段 i>0 用上一段视频的最后一帧作为 first_frame 续接（fl2va）。
    每段完成后下载 mp4 -> ffmpeg 提取末帧 -> 上传到 ComfyUI input/ -> 下一段 LoadImage。
    全部段完成后 ffmpeg 按顺序 concat 为一个文件（后续段 trim 掉与上一段重复的首帧）。

与既有优化保持一致:
    - 每段提交前 POST /free 卸载模型释放 VRAM（同 gen_video.py free_vram 实测 3 连跑全过）
    - 图中带 ForceUnloadBeforeDecode 节点（与三个 gguf 工作流一致：采样后先卸载再解码）
"""
import json, urllib.request, urllib.error, urllib.parse, urllib.response, time, sys, argparse, os, subprocess, tempfile

API = 'http://127.0.0.1:8188'
FFMPEG = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build-shared\bin\ffmpeg.exe'

# 模型文件（与 molbal_workflows/test 里 t2v/i2v 模板一致）
GGUF_UNET = 'minimax_h3_fl2va_pruned-Q4_K_M.gguf'
CLIP_NAME = 'qwen3-vl-4b-heretic-Q4_K_M.gguf'
CLIP_TYPE = 'krea2'
CLIP_PROJ = 'mmh3-4b-ClipProj-v3.1.safetensors'
VIDEO_VAE = 'minimax_h3_video_vae_fp16.safetensors'
AUDIO_VAE = 'minimax_h3_audio_vae_fp32.safetensors'

SEED_DEFAULT = 757358688076805
STEPS_DEFAULT = 20
DEFAULT_SIZE = (864, 480)   # 480P 16:9，H3 标注 0.4MP 档


def frames_for(duration):
    base = max(5, round(duration * 24))
    return base + (5 - base % 17) % 17


def build_graph(prompt, width, height, length, steps, seed, first_frame=None):
    """构造与 minimax_h3_t2v-gguf 模板同构的 API 图；i>0 时接 LoadImage -> first_frame。"""
    n = {'1': {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': GGUF_UNET}},
         '2': {'class_type': 'CCTechClipProjLoader', 'inputs': {'clip_name': CLIP_NAME, 'type': CLIP_TYPE, 'projection': CLIP_PROJ}},
         '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': VIDEO_VAE}},
         '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': AUDIO_VAE}},
         '5': {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {
             'clip': ['2', 0], 'vae': ['3', 0],
             'prompt': prompt, 'width': width, 'height': height, 'length': length}},
         '6': {'class_type': 'ForceUnloadBeforeDecode', 'inputs': {'latent': ['5', 1]}},
         '7': {'class_type': 'BasicGuider', 'inputs': {'model': ['1', 0], 'conditioning': ['5', 0]}},
         '8': {'class_type': 'BasicScheduler', 'inputs': {'model': ['1', 0], 'scheduler': 'simple', 'steps': steps, 'denoise': 1}},
         '9': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'res_multistep'}},
         '10': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': seed}},
         '11': {'class_type': 'SamplerCustomAdvanced', 'inputs': {
             'noise': ['10', 0], 'guider': ['7', 0], 'sampler': ['9', 0], 'sigmas': ['8', 0], 'latent_image': ['6', 0]}},
         '12': {'class_type': 'ForceUnloadBeforeDecode', 'inputs': {'latent': ['11', 0]}},
         '13': {'class_type': 'VAEDecode', 'inputs': {'samples': ['12', 0], 'vae': ['3', 0]}},
         '14': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['12', 0], 'vae': ['4', 0]}},
         '15': {'class_type': 'CreateVideo', 'inputs': {'images': ['13', 0], 'fps': 24, 'audio': ['14', 0], 'bit_depth': 8}},
         '16': {'class_type': 'SaveVideo', 'inputs': {'video': ['15', 0], 'filename_prefix': 'video/MiniMax_H3', 'format': 'auto'}}}
    if first_frame is not None:
        n['17'] = {'class_type': 'LoadImage', 'inputs': {'image': first_frame}}
        n['5']['inputs']['first_frame'] = ['17', 0]
    return n


def free_vram():
    """POST /free：卸载模型并释放 DynamicVRAM 残留物理页（同 gen_video.py）。"""
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


def wait(pid, timeout=3600, interval=5, cur=1, total=1):
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
                print('  段 %d/%d 完成  耗时 %.1fs' % (cur, total, time.time() - start))
                return h[pid].get('outputs', {})
            if st.get('status_str') == 'error':
                raise RuntimeError('queue error: ' + json.dumps(st, ensure_ascii=False)[:2000])
        print('  段 %d/%d 已运行 %.0fs' % (cur, total, time.time() - start))
        time.sleep(interval)
    raise RuntimeError('timeout')


def find_mp4(outputs): return find_video_file(outputs, '.mp4')
def find_video_file(outputs, suffix):
    for outs in outputs.values():
        if not isinstance(outs, dict):
            continue
        for items in outs.values():
            lst = items if isinstance(items, list) else [items]
            for it in lst:
                if isinstance(it, dict) and it.get('filename', '').lower().endswith(suffix):
                    return it
    return None


def download(url, dest):
    urllib.request.urlretrieve(url, dest)
    print('  downloaded ->', dest)


def extract_last_frame(video_path, png_path):
    """ffmpeg 取视频最后一帧存 PNG。"""
    subprocess.run([FFMPEG, '-y', '-sseof', '-0.1', '-i', video_path, '-frames:v', '1', png_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('  last frame ->', png_path)


def upload_image(png_path):
    """POST /upload/image 上传到 ComfyUI input/，返回可用做 LoadImage widgets 的文件名。"""
    import mimetypes
    ctype = mimetypes.guess_type(png_path)[0] or 'image/png'
    with open(png_path, 'rb') as f:
        data = f.read()
    boundary = '----oc' + uuid4hex()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{os.path.basename(png_path)}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n').encode('utf-8') + data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    req = urllib.request.Request(API + '/upload/image', data=body,
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    name = r['name'] if not r.get('subfolder') else r['subfolder'] + '/' + r['name']
    return name


def uuid4hex():
    import uuid
    return uuid.uuid4().hex


def concat_segments(workdir, out_path):
    """ffmpeg 顺序拼接各段 mp4（i>0 段 trim 掉与上段共享的重复首帧）。"""
    segs = sorted(f for f in os.listdir(workdir) if f.startswith('seg') and f.endswith('.mp4'))
    segs = sorted(segs, key=lambda s: int(re_digits(s)))
    inputs, flt, maps = [], [], []
    for i, s in enumerate(segs):
        inputs += ['-i', os.path.join(workdir, s)]
        if i == 0:
            flt.append(f'[{i}:v:0]setpts=PTS-STARTPTS[v{i}]')
            flt.append(f'[{i}:a:0]asetpts=PTS-STARTPTS[a{i}]')
        else:
            flt.append(f'[{i}:v:0]trim=start_frame=1,setpts=PTS-STARTPTS[v{i}]')
            flt.append(f'[{i}:a:0]atrim=start_sample=1,asetpts=PTS-STARTPTS[a{i}]')
        maps += [f'[v{i}]', f'[a{i}]']
    cmd = [FFMPEG, '-y'] + inputs + \
          ['-filter_complex', ';'.join(flt) + ';' + ''.join(maps) + f'concat=n={len(segs)}:v=1:a=1[outv][outa]'] + \
          ['-map', '[outv]', '-map', '[outa]', '-c:v', 'libx264', '-c:a', 'aac', out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('concat ->', out_path)


def re_digits(s):
    import re as _re
    return _re.search(r'\d+', s).group(0)


def ask(msg, default, cast):
    raw = input(msg).strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        print('  无效输入，用默认 %s' % default)
        return default


def read_prompt_file(path):
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read().strip()
        except UnicodeDecodeError:
            continue
    raise RuntimeError('prompt.txt 编码无法识别（尝试 utf-8/gbk 均失败）')


def ask_prompt():
    txt = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompt.txt')
    if os.path.exists(txt):
        p = read_prompt_file(txt)
        print('发现 prompt.txt，内容如下：')
        print('----------------------------------------')
        print(p)
        print('----------------------------------------')
        if input('使用以上内容？(回车=是 / n=重新输入): ').strip().lower() in ('', 'y', 'yes', '是'):
            return p
    while True:
        p = input('提示词: ').strip()
        if p:
            return p
        print('  提示词不能为空')


def ask_size():
    print('画面尺寸: [回车]=864x480（480P 默认） | 2=960x540 | 3=1280x720 | 自定义如 832x480')
    raw = input('尺寸: ').strip().lower()
    presets = {'': DEFAULT_SIZE, '2': (960, 540), '3': (1280, 720)}
    if raw in presets:
        return presets[raw]
    try:
        w, h = raw.split('x')
        return int(w), int(h)
    except ValueError:
        print('  无法解析，用默认 864x480')
        return DEFAULT_SIZE


def main():
    ap = argparse.ArgumentParser(description='MiniMax H3 multi-segment video (first-frame chaining) via ComfyUI API')
    ap.add_argument('--prompt', help='提示词（单条，全部段复用）；与 --prompt-file 互斥')
    ap.add_argument('--prompt-file', help='从文件读提示词（UTF-8/GBK 自动识别，内容整文件为一条）')
    ap.add_argument('--segments', type=int, default=0, help='段落数（默认=提示词行数，至少 1）')
    ap.add_argument('--size', help='宽x高，默认 864x480')
    ap.add_argument('--duration', type=float, default=5)
    ap.add_argument('--steps', type=int, default=STEPS_DEFAULT)
    ap.add_argument('--seed', type=int, default=SEED_DEFAULT)
    ap.add_argument('--out', default='h3_multisegment.mp4')
    a = ap.parse_args()

    if a.prompt:
        prompts = [a.prompt.strip()]
    elif a.prompt_file:
        prompts = [read_prompt_file(a.prompt_file)]
    else:
        prompts = [ask_prompt()]
        w0, h0 = ask_size()
        a.duration = ask('每段时长（秒）[5]: ', 5.0, float)
        total = ask('总时长（秒）: ', 5.0, float)
        a.segments = max(1, round(total / a.duration))
        a.steps = ask('步数[%d]: ' % STEPS_DEFAULT, STEPS_DEFAULT, int)
        a.seed = ask('种子（回车=默认 %d）: ' % SEED_DEFAULT, SEED_DEFAULT, int)
        size = (w0, h0)
    if a.size:
        try:
            w, h = a.size.lower().split('x')
            size = (int(w), int(h))
        except ValueError:
            print('  无法解析 --size，用 864x480')
            size = DEFAULT_SIZE
    elif not a.prompt and not a.prompt_file:
        pass
    else:
        size = DEFAULT_SIZE

    n_seg = a.segments or len(prompts)
    if len(prompts) == 1:
        prompts = prompts * n_seg
    elif len(prompts) < n_seg:
        prompts = prompts + [prompts[-1]] * (n_seg - len(prompts))
    prompts = prompts[:n_seg]

    length = frames_for(a.duration)
    print('>>> %d 段，每段 %ds，总时长 %.0fs (%dx%d, length=%d 帧), %d 步' % (n_seg, a.duration, a.duration * n_seg, size[0], size[1], length, a.steps))

    workdir = tempfile.mkdtemp(prefix='h3_seg_')
    output_dir = os.path.dirname(os.path.abspath(a.out)) or '.'
    out_path = a.out if os.path.isabs(a.out) else os.path.join(output_dir, a.out)
    stem, ext = os.path.splitext(out_path)
    n = 1
    while os.path.exists(out_path):
        out_path = '%s_%d%s' % (stem, n, ext)
        n += 1
    seg_videos = []

    prev_frame = None
    for i in range(n_seg):
        print('\n=== 段 %d/%d: %s' % (i + 1, n_seg, prompts[i][:60]))
        free_vram()
        graph = build_graph(prompts[i], size[0], size[1], length, a.steps, a.seed, first_frame=prev_frame)
        pid = submit(graph)
        print('  prompt_id:', pid)
        outputs = wait(pid, cur=i + 1, total=n_seg)
        v = find_video_file(outputs, '.mp4')
        if v is None:
            raise RuntimeError('段 %d: outputs 中未找到 mp4: %s' % (i, json.dumps(outputs, ensure_ascii=False)))
        sub = v.get('subfolder') or ''
        local = os.path.join(workdir, 'seg%d.mp4' % i)
        url = API + '/view?filename=' + urllib.parse.quote(v['filename'], safe='') + \
              ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '') + '&type=' + v.get('type', 'output')
        download(url, local)
        seg_videos.append(local)
        prev_frame = None
        if i + 1 < n_seg:
            tail = os.path.join(workdir, 'tail%d.png' % i)
            extract_last_frame(local, tail)
            prev_frame = upload_image(tail)

    print('\n=== 拼接 %d 段 ===' % n_seg)
    concat_segments(workdir, out_path)
    print('done. output:', out_path)
    print('分段文件保留在:', workdir)


if __name__ == '__main__':
    sys.exit(main())