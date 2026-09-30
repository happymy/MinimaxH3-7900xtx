# -*- coding: utf-8 -*-
"""MiniMax H3 参考图生成视频（ref2va）—— 多段参考图生成 + ffmpeg 拼接。【8B 破限(Heretic)文本编码器版】

与 gen_h3_ref2va.py（4B 版）唯一的差别是文本编码器三件套：
    qwen3-vl-4b-heretic-Q4_K_M.gguf / krea2 / mmh3-4b-ClipProj-v3.1
 -> qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors / boogu / mmh3-8b-ClipProj-v3.1
ref2va 段 0 与 fl2va 段 i>0 两张图共用同一组常量，两张图同步切到 8B。
分辨率、步数、采样器、seed、拼接逻辑全部一致，便于单变量对照。

为什么 8B 值得试（ref2va 尤其明显）:
    8B 与官方 32B 的 Qwen3-VL 视觉塔逐项相同（27 层 / hidden 1152 / deepstack [8,16,24]），
    但语言侧从 4B 的 3-bit（MOSTLY_Q3_K_M）升到 FP8。参考图走视觉塔 -> 图像路径零损失，
    提示词走语言侧 -> 语义路径升精度，这正是 ref2va/r2v 主力档。

显存:
    8B(破限版) 编码期峰值约 11-12 GB（4B 约 3.6 GB）。8B 与 DiT 不能同时驻留，
    所以两个 ForceUnloadBeforeDecode 节点是必需而非优化：
      节点 6  在 latent 输出与 SamplerCustomAdvanced 之间 -> 采样前卸 8B
      节点 12 在 SamplerCustomAdvanced 与解码之间         -> 解码前卸 DiT
    段间 POST /free 保留，防上一段 8B 权重页残留。

用法:
    单段: python gen_h3_ref2va.py --prompt "..." --ref "a.png,b.png" [--size 864x480 --duration 5 --steps 20 --seed 123]
    多段: python gen_h3_ref2va.py --segments 3 --prompt "..." --ref "D:/refs/a.png" [--size 864x480 ...]
    交互: python gen_h3_ref2va.py        # 段数 -> 配置只问一次 -> 自动多段复用 -> 拼接长视频

配置复用:
    所有段共用第一段的提示词/参考图/参数（交互只问一次）。

连贯拼接（像一次生成的长视频，参考实测 gen_h3_multisegment）:
    段 0 用参考图（ref2va）生成；
    段 i>0 切 fl2va：自动抽取上一段最后一帧作为 first_frame 首帧续接
    （同实测多段脚本：同一提示词 + first_frame，concat 时 trim 掉与上段重复的首帧），
    各段画面连续、风格一致，拼接后整体像一段一次生成的长视频。
    全部段共用同一种子（同实测脚本），保证风格稳定。

参考图:
    --ref 可重复（--ref a.png --ref b.png），或多个路径用英文逗号分隔；传目录自动扫描图片。
    提示词中用 <Picture 1>/<Picture 2>/... 按顺序引用参考图。

拼接:
    参考 multisegment：各段独立生成 mp4 后按顺序 ffmpeg concat 为一个文件
    （各段无共享首帧，不做 trim）；输出文件名带种子，已存在自动加 _1/_2 防覆盖。

与既有优化保持一致:
    - 每段提交前 POST /free 卸载模型释放 VRAM。
    - 图中带 ForceUnloadBeforeDecode（采样后先卸载再解码）。
    - ref2va 用 er_sde 采样器，unet 为 minimax_h3_ref2va_pruned-Q4_K_M.gguf。
"""
import json, urllib.request, urllib.error, urllib.parse, time, sys, argparse, os, random, tempfile, subprocess, re

API = 'http://127.0.0.1:8188'
FFMPEG = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe'

GGUF_REF2VA = 'minimax_h3_ref2va_pruned-Q4_K_M.gguf'   # 段 0：参考图生成
GGUF_FL2VA = 'minimax_h3_fl2va_pruned-Q4_K_M.gguf'     # 段 i>0：上一段末帧首帧续接
CLIP_NAME = 'qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors'
CLIP_TYPE = 'boogu'
CLIP_PROJ = 'mmh3-8b-ClipProj-v3.1.safetensors'
VIDEO_VAE = 'minimax_h3_video_vae_fp16.safetensors'
AUDIO_VAE = 'minimax_h3_audio_vae_fp32.safetensors'

STEPS_DEFAULT = 20
DEFAULT_SIZE = (864, 480)
MAX_REFS = 9
IMG_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')


def frames_for(duration):
    base = max(5, round(duration * 24))
    return base + (5 - base % 17) % 17


def build_graph(prompt, width, height, length, steps, seed, refs, ref_image_size='match'):
    """段 0：ref2va 参考图生成（rell 模板同构）；refs 为已上传图片文件名列表。"""
    n = {'1': {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': GGUF_REF2VA}},
         '2': {'class_type': 'CCTechClipProjLoader', 'inputs': {'clip_name': CLIP_NAME, 'type': CLIP_TYPE, 'projection': CLIP_PROJ}},
         '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': VIDEO_VAE}},
         '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': AUDIO_VAE}},
         '5': {'class_type': 'MiniMaxH3ReferenceToVideo', 'inputs': {
             'clip': ['2', 0], 'vae': ['3', 0], 'audio_vae': ['4', 0],
             'prompt': prompt, 'width': width, 'height': height, 'length': length,
             'ref_image_size': ref_image_size}},
         '6': {'class_type': 'ForceUnloadBeforeDecode', 'inputs': {'latent': ['5', 1]}},
         '7': {'class_type': 'BasicGuider', 'inputs': {'model': ['1', 0], 'conditioning': ['5', 0]}},
         '8': {'class_type': 'BasicScheduler', 'inputs': {'model': ['1', 0], 'scheduler': 'simple', 'steps': steps, 'denoise': 1}},
         '9': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'er_sde'}},
         '10': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': seed}},
         '11': {'class_type': 'SamplerCustomAdvanced', 'inputs': {
             'noise': ['10', 0], 'guider': ['7', 0], 'sampler': ['9', 0], 'sigmas': ['8', 0], 'latent_image': ['6', 0]}},
         '12': {'class_type': 'ForceUnloadBeforeDecode', 'inputs': {'latent': ['11', 0]}},
         '13': {'class_type': 'VAEDecode', 'inputs': {'samples': ['12', 0], 'vae': ['3', 0]}},
         '14': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['12', 0], 'vae': ['4', 0]}},
         '15': {'class_type': 'CreateVideo', 'inputs': {'images': ['13', 0], 'fps': 24, 'audio': ['14', 0], 'bit_depth': 8}},
         '16': {'class_type': 'SaveVideo', 'inputs': {'video': ['15', 0], 'filename_prefix': 'video/MiniMax_H3', 'format': 'auto'}}}
    for i, name in enumerate(refs):
        nid = str(17 + i)
        n[nid] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
        n['5']['inputs']['ref_images.ref_image_%d' % i] = [nid, 0]
    return n


def build_fl_graph(prompt, width, height, length, steps, seed, first_frame):
    """段 i>0：fl2va 首帧续接（实测 gen_h3_multisegment 的图）：first_frame=上一段末帧。"""
    n = {'1': {'class_type': 'UnetLoaderGGUF', 'inputs': {'unet_name': GGUF_FL2VA}},
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
         '16': {'class_type': 'SaveVideo', 'inputs': {'video': ['15', 0], 'filename_prefix': 'video/MiniMax_H3', 'format': 'auto'}},
         '17': {'class_type': 'LoadImage', 'inputs': {'image': first_frame}}}
    n['5']['inputs']['first_frame'] = ['17', 0]
    return n


def free_vram():
    """POST /free：卸载模型并释放 DynamicVRAM 残留物理页。"""
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


def upload_image(path, prefix=None):
    """POST /upload/image 上传到 ComfyUI input/，返回可用做 LoadImage widgets 的文件名。

    prefix 加在文件名前，避免多张参考图 basename 相同互相覆盖。
    """
    import mimetypes, uuid
    ctype = mimetypes.guess_type(path)[0] or 'image/png'
    with open(path, 'rb') as f:
        data = f.read()
    fname = os.path.basename(path)
    if prefix:
        fname = prefix + '_' + fname
    boundary = '----oc' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{fname}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n').encode('utf-8') + data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    req = urllib.request.Request(API + '/upload/image', data=body,
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    return r['name'] if not r.get('subfolder') else r['subfolder'] + '/' + r['name']


def collect_refs(paths):
    """展开 --ref/交互输入为存在的图片文件列表。路径可为文件或目录。"""
    out = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        if os.path.isdir(p):
            out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(IMG_EXTS))
        elif os.path.isfile(p):
            out.append(p)
        else:
            print('  WARN: 找不到参考图: %s' % p)
    return out


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


def tag_line(refs):
    return ' '.join('<Picture %d>' % (i + 1) for i in range(len(refs)))


def ask_prompt(tags=''):
    if tags:
        print('参考图标签（复制进提示词即可引用，顺序见上）：%s' % tags)
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
        if tags:
            print('引用图片：%s' % tags)
        p = input('提示词: ').strip()
        if p:
            return p
        print('  提示词不能为空')


def ask_refs():
    """询问参考图片目录：扫描目录内所有图片（文件名无关，固定命名的图放在该目录即可），有几张加载几张。"""
    while True:
        raw = input('参考图片目录（回车=无参考图）: ').strip().strip('"')
        if not raw:
            return []
        if not os.path.isdir(raw):
            print('  不是有效目录: %s，请重输' % raw)
            continue
        refs = collect_refs([raw])
        if refs:
            return refs
        print('  目录内没有图片，请重输')


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


def concat_videos(workdir, out_path):
    """ffmpeg 顺序拼接各段 mp4（段 i>0 首帧=上段末帧，trim 掉重复首帧，同实测 multisegment）。"""
    segs = sorted((f for f in os.listdir(workdir) if re.fullmatch(r'seg\d+\.mp4', f)),
                  key=lambda s: int(re.search(r'\d+', s).group(0)))
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


def extract_last_frame(video_path, png_path):
    """ffmpeg 取视频最后一帧存 PNG（用作下一段续接参考图）。"""
    subprocess.run([FFMPEG, '-y', '-sseof', '-0.1', '-i', video_path, '-frames:v', '1', png_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('  last frame ->', png_path)


def unique_path(path):
    """已存在则在扩展名前加 _1/_2/...，防止覆盖。"""
    stem, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = '%s_%d%s' % (stem, n, ext)
        n += 1
    return path


def run_segment(prompt, size, duration, steps, seed, out_path, refs=None, first_frame=None,
                ref_image_size='match', cur=1, total=1):
    """生成一段视频并下载到 out_path。

    refs 不为空 -> 段 0：ref2va 参考图生成；
    first_frame 不为空 -> 段 i>0：fl2va 以上段末帧首帧续接（实测 multisegment 方式）。
    """
    length = frames_for(duration)
    if first_frame is not None:
        free_vram()
        graph = build_fl_graph(prompt, size[0], size[1], length, steps, seed, first_frame)
    else:
        uploaded = []
        for j, p in enumerate(refs):
            print('  上传参考图 [%d/%d]: %s' % (j + 1, len(refs), p))
            uploaded.append(upload_image(p, prefix='h3seg%02d_%03d_seed%d' % (cur - 1, j, seed)))
        free_vram()
        graph = build_graph(prompt, size[0], size[1], length, steps, seed, uploaded, ref_image_size)
    pid = submit(graph)
    print('  prompt_id:', pid)
    outputs = wait(pid, cur=cur, total=total)
    v = find_video_file(outputs, '.mp4')
    if v is None:
        raise RuntimeError('段 %d: outputs 中未找到 mp4: %s' % (cur, json.dumps(outputs, ensure_ascii=False)))
    sub = v.get('subfolder') or ''
    url = API + '/view?filename=' + urllib.parse.quote(v['filename'], safe='') + \
          ('&subfolder=' + urllib.parse.quote(sub, safe='') if sub else '') + '&type=' + v.get('type', 'output')
    download(url, out_path)


def parse_size(text, default):
    try:
        w, h = text.lower().split('x')
        return int(w), int(h)
    except ValueError:
        print('  无法解析 %s，用 864x480' % text)
        return default


def main():
    ap = argparse.ArgumentParser(description='MiniMax H3 reference-to-video (ref2va) multi-segment via ComfyUI API')
    ap.add_argument('--prompt', help='提示词（按换行拆段，每行一段；只有一行则所有段复用）')
    ap.add_argument('--prompt-file', help='从文件读提示词（UTF-8/GBK 自动识别，行为段）')
    ap.add_argument('--segments', type=int, default=0, help='段数（多段时各段分别生成后拼接）')
    ap.add_argument('--ref', action='append', default=[], help='参考图片路径/目录，多段时每项=该段参考图（可重复）')
    ap.add_argument('--size', help='宽x高，默认 864x480')
    ap.add_argument('--duration', type=float, default=5, help='每段时长（秒），默认 5')
    ap.add_argument('--steps', type=int, default=STEPS_DEFAULT)
    ap.add_argument('--ref-image-size', choices=['match', 'max'], default='match',
                    help="参考图缩放：match=缩到成片分辨率(快)，max=2048px 短边(保真度高、更慢)")
    ap.add_argument('--seed', type=int, default=None, help='种子（默认随机，全部段共用）')
    ap.add_argument('--out', default=None, help='输出文件（默认 h3_ref2va_<seed>.mp4，已存在自动加 _1/_2）')
    a = ap.parse_args()

    interactive = not (a.prompt or a.prompt_file)

    # ---- 配置只问一次，所有段复用（提示词/参考图/参数全部同第一段）----
    if interactive:
        n_seg = ask('段数 [1]: ', 1, int)
        refs = ask_refs()
        for j, p in enumerate(refs):
            print('  <Picture %d> = %s' % (j + 1, os.path.basename(p)))
        prompt = ask_prompt(tag_line(refs))
        w0, h0 = ask_size()
        a.duration = ask('每段时长（秒）[5]: ', 5.0, float)
        a.steps = ask('步数[%d]: ' % STEPS_DEFAULT, STEPS_DEFAULT, int)
        size = (w0, h0)
    else:
        prompt = (a.prompt or read_prompt_file(a.prompt_file)).strip()
        n_seg = a.segments or 1
        refs = collect_refs(a.ref)
        size = parse_size(a.size, DEFAULT_SIZE) if a.size else DEFAULT_SIZE

    if len(refs) > MAX_REFS:
        raise RuntimeError('参考图最多 %d 张，收到 %d' % (MAX_REFS, len(refs)))

    if a.seed is None:
        a.seed = random.randint(0, 2**63)
    if a.out is None:
        a.out = 'h3_ref2va_%d.mp4' % a.seed
    out_path = unique_path(a.out if os.path.isabs(a.out) else os.path.join(
        os.path.dirname(os.path.abspath(a.out)) or '.', a.out))

    length = frames_for(a.duration)
    print('\n>>> %d 段，各段共用配置与种子 (%dx%d, length=%d 帧), 每段 %.0fs, %d 步, seed=%d, ref_image_size=%s'
          % (n_seg, size[0], size[1], length, a.duration, a.steps, a.seed, a.ref_image_size))

    if n_seg == 1:
        run_segment(prompt, size, a.duration, a.steps, a.seed, out_path,
                    refs=refs, ref_image_size=a.ref_image_size, cur=1, total=1)
        print('done. output:', out_path)
        return 0

    workdir = tempfile.mkdtemp(prefix='h3_ref2va_')
    prev_tail = None   # 上一段末帧（已上传到 ComfyUI 的文件名），用于下一段首帧续接
    for i in range(n_seg):
        print('\n=== 段 %d/%d (seed=%d): %s' % (i + 1, n_seg, a.seed, prompt[:60]))
        seg_path = os.path.join(workdir, 'seg%d.mp4' % i)
        if i == 0:
            # 段 0：ref2va 参考图生成
            if len(refs) > MAX_REFS:
                raise RuntimeError('参考图最多 %d 张，收到 %d' % (MAX_REFS, len(refs)))
            run_segment(prompt, size, a.duration, a.steps, a.seed, seg_path,
                        refs=refs, ref_image_size=a.ref_image_size, cur=i + 1, total=n_seg)
        else:
            # 段 i>0：fl2va 以上段末帧首帧续接（同实测 multisegment：同一提示词 + first_frame）
            run_segment(prompt, size, a.duration, a.steps, a.seed, seg_path,
                        first_frame=prev_tail, cur=i + 1, total=n_seg)
        if i + 1 < n_seg:
            tail_png = os.path.join(workdir, 'tail%d.png' % i)
            extract_last_frame(seg_path, tail_png)
            prev_tail = upload_image(tail_png, prefix='h3tail%02d_seed%d' % (i, a.seed))
    print('\n=== 拼接 %d 段 ===' % n_seg)
    concat_videos(workdir, out_path)
    print('done. output:', out_path)
    print('分段文件保留在:', workdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())