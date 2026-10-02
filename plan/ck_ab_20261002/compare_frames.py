# -*- coding: utf-8 -*-
"""H3 ck-attention A/B 帧级比对工具.

用途: 判定 `--use-ck-attention` 是否改变 H3 输出, 以及差异是「int8 量化噪声」
还是「Qwen-Image 同款崩坏」. 两者数值上都表现为高相似度, 只有形态能区分,
所以本脚本同时产出数值表和可视化图.

方法:
  1. ffmpeg 逐帧无损抽成 PNG (从解码帧导出, 不二次有损压缩)
  2. 逐帧算 sha256 / mean|diff| / Pearson r / PSNR / SSIM / 锐度(Laplacian var)
  3. 找出差异最大的帧, 导出 100% 原尺寸裁切对照 + 差异放大热力图

用法:
  python compare_frames.py <A.mp4> <B.mp4> --tag ck_vs_nock [--out-dir .] [--zoom 320]

判读:
  sha256 全等            -> ck 对该配置完全无影响
  r>0.999 且 SSIM>0.99  -> 数值噪声量级, 结构无损
  局部纹理断裂/色块      -> 崩坏(靠 --zoom 图人工确认, 数字不能替代眼睛)
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r'C:\Users\GAME\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build-shared\bin\ffmpeg.exe'
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")


def resolve_inputs(path):
    """支持三种输入: .mp4 文件 / 单张 .png(自动匹配同前缀序列) / 目录内 PNG 序列."""
    path = os.path.abspath(path)
    if path.lower().endswith(".mp4"):
        return ("mp4", [path])
    d = os.path.dirname(path)
    base = os.path.basename(path)
    if base.lower().endswith(".png"):
        # ck_r1_00001_.png -> 去掉帧号段, 前缀 = "ck_r1_"
        import re as _re
        m = _re.match(r"^(.*)_\d+_\.png$", base, _re.I)
        prefix = (m.group(1) if m else os.path.splitext(base)[0]) + "_"
    else:
        prefix = base
    hits = sorted(f for f in os.listdir(d)
                  if f.lower().endswith(".png") and f.startswith(prefix))
    if not hits:
        raise RuntimeError("未找到 PNG 序列: " + path)
    return ("png", [os.path.join(d, f) for f in hits])


def extract_frames(src, out_dir):
    """mp4 -> 无损抽帧; PNG 序列 -> 直接使用(已是解码器输出, 无二次有损)."""
    kind, files = resolve_inputs(src)
    if kind == "png":
        return files
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(out_dir, f))
    else:
        os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run(
        # ffmpeg >= 5 已移除 -vsync, 正确写法是 -fps_mode passthrough (逐帧透传不做帧率转换)
        [FFMPEG, "-v", "error", "-i", mp4, "-fps_mode", "passthrough",
         os.path.join(out_dir, "f%05d.png")],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 抽帧失败: " + r.stderr[:500])
    files = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
    if not files:
        raise RuntimeError("未抽出任何帧: " + mp4)
    return [os.path.join(out_dir, f) for f in files]


def to_gray_u8(path):
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64)


def ssim(a, b, data_range=255.0):
    """Wang et al. 2004 标准 SSIM: 11x11 高斯窗 sigma=1.5, K1=0.01, K2=0.03."""
    C1 = (0.01 * data_range) ** 2
    C2 = (0.03 * data_range) ** 2
    mu_a = gaussian_filter(a, 1.5, truncate=3.5)
    mu_b = gaussian_filter(b, 1.5, truncate=3.5)
    saa = gaussian_filter(a * a, 1.5, truncate=3.5) - mu_a * mu_a
    sbb = gaussian_filter(b * b, 1.5, truncate=3.5) - mu_b * mu_b
    sab = gaussian_filter(a * b, 1.5, truncate=3.5) - mu_a * mu_b
    num = (2 * mu_a * mu_b + C1) * (2 * sab + C2)
    den = (mu_a ** 2 + mu_b ** 2 + C1) * (saa + sbb + C2)
    return float(np.mean(num / den))


def laplacian_var(path):
    """锐度代理: 4 邻域拉普拉斯响应方差 (越大越锐)."""
    g = to_gray_u8(path)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1]
           + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def main():
    ap = argparse.ArgumentParser(description="H3 ck-attention A/B 帧级比对")
    ap.add_argument("a", help="A 视频 (基准, 通常是非 ck 臂)")
    ap.add_argument("b", help="B 视频 (对照, 通常是 ck 臂)")
    ap.add_argument("--tag", default="ab", help="输出文件名前缀")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--zoom", type=int, default=320, help="100%% 裁切边长")
    ap.add_argument("--amp", type=int, default=8, help="差异热力图放大倍数")
    a = ap.parse_args()

    out = os.path.abspath(a.out_dir)
    os.makedirs(out, exist_ok=True)
    fa = extract_frames(a.a, os.path.join(out, "_frames_a"))
    fb = extract_frames(a.b, os.path.join(out, "_frames_b"))
    print("A %s: %d 帧" % (os.path.basename(a.a), len(fa)))
    print("B %s: %d 帧" % (os.path.basename(a.b), len(fb)))
    if len(fa) != len(fb):
        print("!! 帧数不等, 只比对共同的前 %d 帧" % min(len(fa), len(fb)))
    n = min(len(fa), len(fb))

    rows = []
    for i in range(n):
        pa, pb = fa[i], fb[i]
        # 注意: 哈希**像素**而非 PNG 文件字节 —— 同内容不同 PNG 编码元数据会导致
        # 文件 sha256 不同但像素完全一致, 用文件哈希会把"确定性"误判成"有差异".
        ga, gb = to_gray_u8(pa), to_gray_u8(pb)
        pa_rgb = np.asarray(Image.open(pa).convert("RGB"))
        pb_rgb = np.asarray(Image.open(pb).convert("RGB"))
        ha = hashlib.sha256(pa_rgb.tobytes()).hexdigest()
        hb = hashlib.sha256(pb_rgb.tobytes()).hexdigest()
        d = np.abs(ga - gb)
        mad = float(d.mean())
        r = float(np.corrcoef(ga.ravel(), gb.ravel())[0, 1])
        mse = float(((ga - gb) ** 2).mean())
        psnr = float("inf") if mse == 0 else float(10 * np.log10(255.0 ** 2 / mse))
        rows.append({
            "frame": i + 1,
            "sha_equal": ha == hb,
            "mad": round(mad, 4),
            "pearson_r": round(r, 8),
            "psnr_db": ("inf" if psnr == float("inf") else round(psnr, 4)),
            "ssim": round(ssim(ga, gb), 8),
            "sharp_a": round(laplacian_var(pa), 3),
            "sharp_b": round(laplacian_var(pb), 3),
        })
        if (i + 1) % 24 == 0 or i == n - 1:
            print("  ...%d/%d 帧已比对" % (i + 1, n))

    n_equal = sum(1 for x in rows if x["sha_equal"])
    sharp_a = np.mean([x["sharp_a"] for x in rows])
    sharp_b = np.mean([x["sharp_b"] for x in rows])
    summary = {
        "tag": a.tag,
        "a": os.path.abspath(a.a),
        "b": os.path.abspath(a.b),
        "frames_compared": n,
        "frames_sha_equal": n_equal,
        "bit_identical": n_equal == n,
        "mad_mean": round(float(np.mean([x["mad"] for x in rows])), 4),
        "mad_max": round(float(np.max([x["mad"] for x in rows])), 4),
        "pearson_r_min": round(float(np.min([x["pearson_r"] for x in rows])), 8),
        "pearson_r_mean": round(float(np.mean([x["pearson_r"] for x in rows])), 8),
        "ssim_min": round(float(np.min([x["ssim"] for x in rows])), 8),
        "ssim_mean": round(float(np.mean([x["ssim"] for x in rows])), 8),
        "sharp_a_mean": round(float(sharp_a), 3),
        "sharp_b_mean": round(float(sharp_b), 3),
        "sharp_delta_pct": (round((sharp_b - sharp_a) / sharp_a * 100, 3)
                            if sharp_a else None),
        "worst_frame": max(rows, key=lambda x: x["mad"])["frame"],
        "per_frame": rows,
    }

    mp = os.path.join(out, "%s_metrics.json" % a.tag)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n===== 汇总 (%s) =====" % a.tag)
    print("  比对帧数        : %d" % n)
    print("  sha256 全等帧数 : %d  -> %s"
          % (n_equal, "两臂位级一致(ck 无影响)" if n_equal == n else "存在差异"))
    if n_equal != n:
        print("  mean|diff|      : 均 %.4f  最大 %.4f" % (summary["mad_mean"], summary["mad_max"]))
        print("  Pearson r       : 最小 %.8f  均 %.8f"
              % (summary["pearson_r_min"], summary["pearson_r_mean"]))
        print("  SSIM            : 最小 %.8f  均 %.8f"
              % (summary["ssim_min"], summary["ssim_mean"]))
        print("  锐度 A->B       : %.1f -> %.1f (%+.2f%%)"
              % (sharp_a, sharp_b, summary["sharp_delta_pct"] or 0))
        print("  差异最大帧      : #%d" % summary["worst_frame"])

        # 可视化: 差异最大帧的三联图 + 100% 裁切
        wi = summary["worst_frame"] - 1
        ia = np.asarray(Image.open(fa[wi]).convert("RGB"), dtype=np.int16)
        ib = np.asarray(Image.open(fb[wi]).convert("RGB"), dtype=np.int16)
        diff = np.abs(ia - ib).max(axis=2)
        heat = np.clip(diff.astype(np.float64) * a.amp, 0, 255).astype(np.uint8)
        Image.fromarray(np.hstack([ia.astype(np.uint8), ib.astype(np.uint8),
                                    np.stack([heat] * 3, axis=2)])).save(
            os.path.join(out, "%s_worst_full.png" % a.tag))
        h, w = diff.shape
        z = a.zoom
        cy, cx = h // 2, w // 2
        y0, x0 = max(0, cy - z // 2), max(0, cx - z // 2)
        sl = (slice(y0, y0 + z), slice(x0, x0 + z))
        Image.fromarray(np.hstack([
            ia[sl].astype(np.uint8), ib[sl].astype(np.uint8),
            np.stack([np.clip(diff[sl].astype(np.float64) * a.amp, 0, 255).astype(np.uint8)] * 3, axis=2),
        ])).resize((z * 3, z), Image.NEAREST).save(
            os.path.join(out, "%s_worst_zoom%d.png" % (a.tag, z)))
        print("\n  可视化: %s_worst_full.png / %s_worst_zoom%d.png  (A | B | 差异x%d)"
              % (a.tag, a.tag, z, a.amp))
    print("  指标文件: %s" % mp)


if __name__ == "__main__":
    main()
