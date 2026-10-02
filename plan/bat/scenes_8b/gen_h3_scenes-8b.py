# -*- coding: utf-8 -*-
"""MiniMax H3 分镜多段视频生成（每段独立提示词/时长 + 首帧续接拼接）—— 通过 ComfyUI API。【8B 文本编码器版】

与 gen_h3_scenes.py（4B 版）唯一的差别是文本编码器三件套：
    qwen3-vl-4b-heretic-Q4_K_M.gguf / krea2 / mmh3-4b-ClipProj-v3.1
 -> qwen3vl_8b_fp8_scaled.safetensors / boogu / mmh3-8b-ClipProj-v3.1
分镜切块、每段时长、超长镜头自动拆分、拼接逻辑全部一致，便于单变量对照。

显存（8B 版唯一需要额外留意的地方）:
    8B 编码期峰值约 11-12 GB，4B 约 3.6 GB。8B 与 DiT 绝不能同时驻留，
    所以图中两个 ForceUnloadBeforeDecode 节点不是优化而是必需：
      节点 6  夹在 latent 输出与 SamplerCustomAdvanced 之间 -> 采样前卸 8B
      节点 12 夹在 SamplerCustomAdvanced 与 VAEDecode/VAEDecodeAudio 之间 -> 解码前卸 DiT
    段与段之间的 POST /free 同样保留，防止上一段的 8B 权重页残留。
    24 GB 卡上不要同时开浏览器/其他 GPU 程序。

与 gen_h3_multisegment.py 的关系:
    multisegment = 所有段共用一条提示词、统一时长；
    本脚本 scenes  = 每段可给不同提示词与不同时长（如 10s 戴手套 / 4s 按压 / 4s 抚额），
    段间仍用「上一段末帧 -> first_frame」续接，拼接后像一次生成的长视频。

用法:
    python gen_h3_scenes-8b.py --prompt-file 分镜.txt [--duration 10,4,4] [--size 864x480 --steps 20 --seed 123]
    python gen_h3_scenes-8b.py        # 交互式（prompt.txt 或粘贴，支持 ###/=== 切块，回车用默认）

分镜文件格式（UTF-8 或 GBK 均可）:
    以「### 或 === 开头」的行作为段分隔（该行本身不参与提示词），每块 = 一条提示词；
    以 # 开头的行视为注释整行忽略；块数 = 段数。
    每个提示词块内部建议按 H3 三字段写：
        integrated_multimodal_description: ...
        overall_soundscape: ...
        non_diegetic_music: ...

每段时长:
    --duration 支持逗号分隔逐段指定，如 10,4,4 → 段0=10s 段1=4s 段2=4s；
    单个数字/缺省 → 所有段统一（默认 5s）。块数多于时长数时补齐末值。

超长镜头自动拆分（硬件单段上限）:
    显存决定一次只能出 N 秒。--max-duration（默认 5s，0=不限制）是这个上限。
    某段时长超过上限时自动拆成 ceil(时长/上限) 个等长「生成单元」，彼此首帧续接接力，
    拼接后仍是一个连续镜头。所以 --duration 10,4,4 在上限 5s 下实际生成 4 个单元：
        镜头1 第1/2段 5.0s | 镜头1 第2/2段 5.0s | 镜头2 4.0s | 镜头3 4.0s
    未超过上限的段不拆，行为与之前完全一致。

    注意：同一镜头的多个拆分单元共用同一条提示词，靠首帧续接保证画面连续。
    所以一「块」最好只写一个能保持住的动作（幂等），
    递进/过程性动作（手指滑到发际、掏出手机、镜头先拉后推）会被每段重演一遍。
    稳妥做法：一块一个动作，需要 10 秒就写两块各 5 秒，别依赖自动拆分。

拼接方式（同实测 multisegment）:
    段 0 走 t2v（无首帧）；段 i>0 用上一段视频最后一帧作为 first_frame 续接（fl2va）。
    每段完成后下载 mp4 -> ffmpeg 提取末帧 -> 上传 ComfyUI input/ -> 下一段 LoadImage。
    全部段完成后 ffmpeg 按顺序 concat（后续段 trim 掉与上段重复的首帧）。
    全部段共用同一种子，保证风格稳定（同实测脚本）。

与既有优化保持一致:
    - 每段提交前 POST /free 卸载模型释放 VRAM（实测 3 连跑全过）
    - 图中带 ForceUnloadBeforeDecode 节点（采样后先卸载再解码）
"""
import json, urllib.request, urllib.error, urllib.parse, urllib.response, time, sys, argparse, os, subprocess, tempfile, random, math

API = 'http://127.0.0.1:8188'
FFMPEG = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe'

# 模型文件（与 molbal_workflows/test 里 t2v/i2v 模板一致，首帧续接用 fl2va unet）
GGUF_UNET = 'minimax_h3_fl2va_pruned-Q4_K_M.gguf'
CLIP_NAME = 'qwen3vl_8b_fp8_scaled.safetensors'
CLIP_TYPE = 'boogu'
CLIP_PROJ = 'mmh3-8b-ClipProj-v3.1.safetensors'
VIDEO_VAE = 'minimax_h3_video_vae_fp16.safetensors'
AUDIO_VAE = 'minimax_h3_audio_vae_fp32.safetensors'

SEED_DEFAULT = None          # 未指定 seed 时随机生成
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
    raise RuntimeError('提示词文件编码无法识别（尝试 utf-8/gbk 均失败）')


def split_prompt_blocks(text):
    """按「### 或 === 开头」的行切分为提示词块列表；以 # 开头的整行注释忽略。"""
    blocks, cur = [], []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith('###') or s.startswith('==='):
            if cur:
                blocks.append('\n'.join(cur).strip())
                cur = []
            continue
        if s.startswith('#'):
            continue
        cur.append(ln)
    if cur:
        blocks.append('\n'.join(cur).strip())
    return [b for b in blocks if b.strip()]


def parse_durations(raw, n_shot):
    """'10,4,4' -> [10.0,4.0,4.0]；单个数字/空 -> 全部统一 5s；短则补齐末值。"""
    if raw is None:
        return [5.0] * n_shot
    parts = [p.strip() for p in str(raw).split(',') if p.strip()]
    if not parts:
        return [5.0] * n_shot
    ds = [float(p) for p in parts]
    if len(ds) == 1:
        ds = ds * n_shot
    elif len(ds) < n_shot:
        ds = ds + [ds[-1]] * (n_shot - len(ds))
    return ds[:n_shot]


def plan_units(prompts, durations, max_seg):
    """把超过硬件单段上限的镜头自动拆成多个生成单元。

    镜头时长 <= max_seg 的不拆（行为不变）；超过的拆成 ceil(d/max_seg) 个等长单元，
    单元之间靠「上一单元末帧 -> 下一单元 first_frame」接力，拼接后仍是一个连续镜头。
    同一镜头的各单元共用同一条提示词。

    返回 [(提示词, 单元时长, 显示标签)]。
    """
    units = []
    for si, (p, d) in enumerate(zip(prompts, durations)):
        n = math.ceil(d / max_seg) if (max_seg and d > max_seg) else 1
        for k in range(n):
            label = '镜头%d' % (si + 1) if n == 1 else '镜头%d 第%d/%d段' % (si + 1, k + 1, n)
            units.append((p, d / n, label))
    return units


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
        p = input('提示词（多段用 ### 或 === 行分隔）: ').strip()
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
    ap = argparse.ArgumentParser(description='MiniMax H3 分镜多段视频（每段独立提示词/时长 + 首帧续接拼接）')
    ap.add_argument('--prompt-file', help='分镜提示词文件：###/=== 行切块，每块一条（UTF-8/GBK 自动识别）')
    ap.add_argument('--segments', type=int, default=0, help='镜头数（默认=提示词块数）')
    ap.add_argument('--size', help='宽x高，默认 864x480')
    ap.add_argument('--duration', default=None, help='每段时长（秒），逗号分隔逐段指定如 10,4,4；默认 5 全段统一')
    ap.add_argument('--max-duration', type=float, default=5.0,
                    help='硬件单段上限（秒，默认 5）。某段超过就自动拆成多个等长单元首帧续接；0=不限制。'
                         '拆分出的单元共用同一条提示词，所以动作要幂等')
    ap.add_argument('--steps', type=int, default=STEPS_DEFAULT)
    ap.add_argument('--seed', type=int, default=None, help='种子（默认随机，回车/不带则随机）')
    ap.add_argument('--out', default=None, help='输出文件（默认 h3_scenes_<seed>.mp4，已存在自动加 _1/_2）')
    a = ap.parse_args()

    interactive = not a.prompt_file
    if interactive:
        prompts = []
        while not prompts:
            prompts = split_prompt_blocks(ask_prompt())   # 交互粘贴同样支持 ###/=== 切块
        w0, h0 = ask_size()
        a.max_duration = ask('单段生成上限（秒，硬件一次能出的最长时长）[%g]: ' % a.max_duration,
                             a.max_duration, float)
        raw_dur = input('各段时长（秒），逗号分隔逐段指定如 10,4,4 [5]: ').strip()
        durations = parse_durations(raw_dur or '5', len(prompts))
        a.steps = ask('步数[%d]: ' % STEPS_DEFAULT, STEPS_DEFAULT, int)
        a.seed = ask('种子（回车=随机）: ', random.randint(0, 2**63), int)
        size = (w0, h0)
    else:
        prompts = split_prompt_blocks(read_prompt_file(a.prompt_file))
        if a.size:
            try:
                w, h = a.size.lower().split('x')
                size = (int(w), int(h))
            except ValueError:
                print('  无法解析 --size，用 864x480')
                size = DEFAULT_SIZE
        else:
            size = DEFAULT_SIZE
        durations = parse_durations(a.duration, len(prompts))

    if a.seed is None:
        a.seed = random.randint(0, 2**63)
    if a.out is None:
        a.out = 'h3_scenes_%d.mp4' % a.seed

    n_shot = a.segments or len(prompts)
    if len(prompts) == 1:
        prompts = prompts * n_shot
    elif len(prompts) < n_shot:
        prompts = prompts + [prompts[-1]] * (n_shot - len(prompts))
    prompts = prompts[:n_shot]
    durations = parse_durations(','.join(str(d) for d in durations), n_shot)

    units = plan_units(prompts, durations, a.max_duration)
    print('>>> %d 个镜头 %s 秒（单段上限 %s）-> %d 个生成单元'
          % (len(prompts), ','.join(str(round(d, 1)) for d in durations),
             ('%gs' % a.max_duration) if a.max_duration else '不限', len(units)))
    print('    ' + ' | '.join('%s %.1fs' % (lb, d) for _, d, lb in units))
    print('    总时长 %.1fs (%dx%d, %d 步, seed=%d)'
          % (sum(durations), size[0], size[1], a.steps, a.seed))

    workdir = tempfile.mkdtemp(prefix='h3_scenes_')
    output_dir = os.path.dirname(os.path.abspath(a.out)) or '.'
    out_path = a.out if os.path.isabs(a.out) else os.path.join(output_dir, a.out)
    stem, ext = os.path.splitext(out_path)
    n = 1
    while os.path.exists(out_path):
        out_path = '%s_%d%s' % (stem, n, ext)
        n += 1
    seg_videos = []

    n_units = len(units)
    prev_frame = None
    for i, (up, ud, label) in enumerate(units):
        length = frames_for(ud)
        print('\n=== %s (%d/%d, %.2fs, length=%d 帧, %s): %s'
              % (label, i + 1, n_units, ud, length,
                 't2va 起始段' if prev_frame is None else 'fl2va 首帧续接', up[:60]))
        free_vram()
        graph = build_graph(up, size[0], size[1], length, a.steps, a.seed, first_frame=prev_frame)
        pid = submit(graph)
        print('  prompt_id:', pid)
        outputs = wait(pid, cur=i + 1, total=n_units)
        v = find_video_file(outputs, '.mp4')
        if v is None:
            raise RuntimeError('%s: outputs 中未找到 mp4: %s' % (label, json.dumps(outputs, ensure_ascii=False)))
        sub = v.get('subfolder') or ''
        local = os.path.join(workdir, 'seg%d.mp4' % i)
        url = API + '/view?filename=' + urllib.parse.quote(v['filename'], safe='') + \
              ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '') + '&type=' + v.get('type', 'output')
        download(url, local)
        seg_videos.append(local)
        prev_frame = None
        if i + 1 < n_units:
            tail = os.path.join(workdir, 'tail%d.png' % i)
            extract_last_frame(local, tail)
            prev_frame = upload_image(tail)

    print('\n=== 拼接 %d 段 ===' % n_units)
    concat_segments(workdir, out_path)
    print('done. output:', out_path)
    print('分段文件保留在:', workdir)


if __name__ == '__main__':
    sys.exit(main())