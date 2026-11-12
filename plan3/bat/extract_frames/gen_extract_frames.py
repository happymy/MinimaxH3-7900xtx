# -*- coding: utf-8 -*-
"""从视频中抽取 首帧 / 中间帧 / 末帧 并保存（供 ref2va 参考图等使用）。

用法:
    python gen_extract_frames.py --video "D:/xx.mp4"
    python gen_extract_frames.py        # 交互式（输入或拖入视频路径即可）

说明:
    - 默认输出到视频同目录，命名 <视频名>_frame1.png / _framemid.png / _framelast.png
    - 输出文件已存在时自动加 _1/_2/... 后缀，绝不覆盖
    - 中间帧位置 = 视频时长的 50%，可用 --mid 改为 40（表示 40% 位置）
"""
import os, sys, argparse, subprocess

FFMPEG = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe'
FFPROBE = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin\ffprobe.exe'


def ask(msg, default=None, cast=str):
    raw = input(msg).strip().strip('"')
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        print('  无效输入，用默认 %s' % default)
        return default


def unique_path(path):
    """已存在则在扩展名前加 _1/_2/...，防止覆盖。"""
    stem, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(path):
        path = '%s_%d%s' % (stem, n, ext)
        n += 1
    return path


def probe_duration(video):
    r = subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', video], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RuntimeError('无法读取视频时长: %s' % r.stderr.strip()[:500])


def extract(video, out, seek_opts=None):
    """seek_opts=None 抽首帧；否则为 ffmpeg 定位选项列表，如 ['-ss','2.500'] 或 ['-sseof','-0.1']。"""
    cmd = [FFMPEG, '-y']
    if seek_opts:
        cmd += seek_opts
    cmd += ['-i', video, '-frames:v', '1', out]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('  saved ->', out)


def main():
    ap = argparse.ArgumentParser(description='从视频抽 首/中/末 三帧保存（防覆盖）')
    ap.add_argument('--video', help='视频文件路径（交互模式可拖入）')
    ap.add_argument('--out-dir', help='输出目录（默认=视频所在目录）')
    ap.add_argument('--mid', type=int, default=50, help='中间帧位置百分比 0-100（默认 50）')
    ap.add_argument('--yes', action='store_true', help='跳过确认直接抽取')
    a = ap.parse_args()

    if a.video:
        video = a.video.strip().strip('"')
    else:
        while True:
            video = ask('视频文件路径（可拖入窗口）: ', '').strip().strip('"')
            if video:
                break
            print('  路径不能为空')
    if not os.path.isfile(video):
        print('  错误: 找不到视频文件: %s' % video)
        return 1

    dur = probe_duration(video)
    stem = os.path.splitext(os.path.basename(video))[0]
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(video))
    if not os.path.isdir(out_dir):
        print('  错误: 输出目录不存在: %s' % out_dir)
        return 1

    mid_pct = max(0, min(100, a.mid))
    first = unique_path(os.path.join(out_dir, stem + '_frame1.png'))
    mid = unique_path(os.path.join(out_dir, stem + '_framemid.png'))
    last = unique_path(os.path.join(out_dir, stem + '_framelast.png'))

    print('>>> %s  (%.1fs, %.0f%% 处取中间帧)' % (os.path.basename(video), dur, mid_pct))
    print('    first :', first)
    print('    mid   :', mid)
    print('    last  :', last)
    if not a.yes and input('开始抽取？(回车=是 / n=取消): ').strip().lower() in ('n', 'no', '否'):
        print('已取消')
        return 0

    extract(video, first)
    extract(video, mid, ['-ss', '%.3f' % (dur * mid_pct / 100.0)])
    extract(video, last, ['-sseof', '-0.1'])
    print('done. 3 帧已保存到:', out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())