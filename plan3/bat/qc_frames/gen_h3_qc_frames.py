# -*- coding: utf-8 -*-
r"""H3 产物质检抽帧：均匀抽 N 帧 + 首/末帧，可选拼 contact sheet。

用途：判断不同分辨率/不同时长档位的画质差异（糊不糊、噪点多不多、提示词跟随度），
把 MP4 变成可识图的 PNG。识别环节走 vision-deepseek skill，本脚本只负责抽帧。

用法:
    python gen_h3_qc_frames.py --video "D:/xx.mp4" --count 8 --sheet
    python gen_h3_qc_frames.py --dir "D:/out/video" --count 6 --sheet --only 165,166,167
    python gen_h3_qc_frames.py                    # 交互式（可拖入视频路径）

说明:
    - 基于同目录 gen_extract_frames.py 扩展（只增不改，原脚本保留）
    - 输出到 <视频名>_qc\<n> 目录，命名 f00_t0.000.png / f03_t1.940.png / first.png / last.png
    - 已存在则自动加 _1/_2/... 后缀，绝不覆盖
    - --sheet 额外用 ffmpeg tile 滤镜拼一张 contact sheet，一张图看全片
    - 帧位置取区间中点（(i+0.5)/N），避开首尾可能出现的淡入淡出/关键帧过渡
"""
import os, sys, glob, shutil, argparse, subprocess

# ffmpeg / ffprobe 候选路径，按优先级探测；本机两处都装了
_BIN_CANDIDATES = [
    r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin',
    r'D:\localAI\ffmpeg8\ffmpeg-8.0.1-full_build-shared\bin',
]


def _find_bin(name):
    """返回 <exe 路径>，找不到抛 RuntimeError。"""
    for d in _BIN_CANDIDATES:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    p = shutil.which(name) or shutil.which(name + '.exe')
    if p:
        return p
    raise RuntimeError('找不到 %s，已探测: %s' % (name, ' , '.join(_BIN_CANDIDATES)))


def ffmpeg_bin():
    return _find_bin('ffmpeg')


def ffprobe_bin():
    return _find_bin('ffprobe')


def unique_path(path):
    """已存在则在扩展名前加 _1/_2/...，防止覆盖。"""
    stem, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = '%s_%d%s' % (stem, n, ext)
        n += 1
    return path


def probe(video):
    """返回 {w,h,fps,frames,duration,v_codec,a_codec}。"""
    exe = ffprobe_bin()
    cmd = [exe, '-v', 'error', '-print_format', 'json',
           '-show_format', '-show_streams', video]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise RuntimeError('ffprobe 失败: %s' % r.stderr.strip()[:500])
    import json
    j = json.loads(r.stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    num, _, den = v.get('avg_frame_rate', '0/1').partition('/')
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    dur = float(j['format'].get('duration') or v.get('duration') or 0)
    return {
        'w': v['width'], 'h': v['height'],
        'fps': fps, 'frames': int(v.get('nb_frames') or 0), 'duration': dur,
        'v_codec': v['codec_name'], 'pix_fmt': v.get('pix_fmt'),
        'a_codec': a['codec_name'] if a else None,
    }


def grab(video, out, seek_opts=None):
    """seek_opts=None 抽首帧；否则为 ffmpeg 定位选项，如 ['-ss','1.940'] 或 ['-sseof','-0.1']。"""
    cmd = [ffmpeg_bin(), '-y', '-loglevel', 'error']
    if seek_opts:
        cmd += seek_opts
    cmd += ['-i', video, '-frames:v', '1', out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError('抽帧失败 %s: %s' % (os.path.basename(out), r.stderr.strip()[:300]))


def sheet(video, out, n, info, cols=4, cell_w=480):
    """均匀抽 n 帧缩放后拼成 contact sheet（tile 滤镜）。"""
    dur = info['duration']
    if dur <= 0 or n <= 0:
        return None
    rows = max(1, (n + cols - 1) // cols)
    cell_h = max(2, int(round(cell_w * info['h'] / float(info['w'])) // 2 * 2))
    vf = ("fps=%.6f/%s," % (n, ('%.6f' % dur))
          + "scale=%d:%d:force_original_aspect_ratio=decrease," % (cell_w, cell_h)
          + "tile=%dx%d:padding=4:margin=4:color=black" % (cols, rows))
    cmd = [ffmpeg_bin(), '-y', '-loglevel', 'error', '-i', video,
           '-vf', vf, '-frames:v', '1', '-update', '1', out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0 or not os.path.isfile(out):
        print('    [警告] contact sheet 生成失败: %s' % r.stderr.strip()[:300])
        return None
    return out


def do_one(video, out_root, count, with_first_last, with_sheet, cols, cell_w):
    stem = os.path.splitext(os.path.basename(video))[0]
    out_dir = unique_path(os.path.join(out_root, stem + '_qc'))
    os.makedirs(out_dir, exist_ok=True)

    info = probe(video)
    print('>>> %s' % os.path.basename(video))
    print('    %dx%d  %.3f fps  %d 帧  %.3f s  %s/%s  音频 %s' % (
        info['w'], info['h'], info['fps'], info['frames'], info['duration'],
        info['v_codec'], info['pix_fmt'], info['a_codec'] or '无'))

    made = []
    dur = info['duration']
    for i in range(count):
        t = dur * (i + 0.5) / count
        p = os.path.join(out_dir, 'f%02d_t%.3f.png' % (i, t))
        grab(video, p, ['-ss', '%.3f' % t])
        made.append(p)
    if with_first_last:
        for tag, opt in (('first', None), ('last', ['-sseof', '-0.1'])):
            p = os.path.join(out_dir, '%s.png' % tag)
            grab(video, p, opt)
            made.append(p)
    print('    抽帧 %d 张 -> %s' % (len(made), out_dir))

    if with_sheet:
        sp = os.path.join(out_dir, 'sheet.png')
        got = sheet(video, unique_path(sp), count, info, cols=cols, cell_w=cell_w)
        if got:
            print('    拼图   -> %s  (%d 帧 / %d 列)' % (got, count, cols))
            made.append(got)
    return made


def main():
    ap = argparse.ArgumentParser(description='H3 产物质检抽帧（均匀 N 帧 + 首末帧 + contact sheet，防覆盖）')
    ap.add_argument('--video', help='单个视频文件（交互模式可拖入）')
    ap.add_argument('--dir', help='目录批量处理（配合 --only 过滤文件名）')
    ap.add_argument('--only', help='逗号分隔的文件名片段过滤，如 165,166,167')
    ap.add_argument('--out-dir', help='输出根目录（默认=视频所在目录）')
    ap.add_argument('--count', type=int, default=8, help='均匀抽帧数（默认 8）')
    ap.add_argument('--cols', type=int, default=4, help='拼图列数（默认 4）')
    ap.add_argument('--cell-width', type=int, default=480, help='拼图单格宽像素（默认 480）')
    ap.add_argument('--no-first-last', action='store_true', help='不抽首帧/末帧')
    ap.add_argument('--no-sheet', action='store_true', help='不生成 contact sheet')
    ap.add_argument('--yes', action='store_true', help='跳过确认直接抽')
    a = ap.parse_args()

    videos = []
    if a.video:
        videos = [a.video.strip().strip('"')]
    elif a.dir:
        pats = a.dir.strip().strip('"')
        videos = sorted(glob.glob(os.path.join(pats, '*.mp4')))
        if a.only:
            keys = [k.strip() for k in a.only.split(',') if k.strip()]
            videos = [v for v in videos if any(k in os.path.basename(v) for k in keys)]
    else:
        while True:
            v = input('视频文件路径（可拖入窗口）: ').strip().strip('"')
            if v:
                videos = [v]
                break
            print('  路径不能为空')

    if not videos:
        print('  错误: 没找到可处理的 mp4')
        return 1
    missing = [v for v in videos if not os.path.isfile(v)]
    if missing:
        for v in missing:
            print('  错误: 找不到视频文件: %s' % v)
        return 1

    root = a.out_dir or os.path.dirname(os.path.abspath(videos[0]))
    if not os.path.isdir(root):
        print('  错误: 输出目录不存在: %s' % root)
        return 1

    print('ffmpeg : %s' % ffmpeg_bin())
    print('ffprobe: %s' % ffprobe_bin())
    print('待处理 %d 个视频，均匀抽 %d 帧，首末帧 %s，拼图 %s，输出根目录 %s' % (
        len(videos), a.count, '否' if a.no_first_last else '是',
        '否' if a.no_sheet else '是', root))
    if not a.yes and input('开始抽帧？(回车=是 / n=取消): ').strip().lower() in ('n', 'no', '否'):
        print('已取消')
        return 0

    total = 0
    for v in videos:
        try:
            total += len(do_one(v, root, max(1, a.count), not a.no_first_last,
                                not a.no_sheet, max(1, a.cols), a.cell_width))
        except Exception as e:
            print('    [失败] %s' % e)
    print('done. 共 %d 张图' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
