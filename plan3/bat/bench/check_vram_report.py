# -*- coding: utf-8 -*-
"""二十秒自查：HIP 报的可用显存 vs 任务管理器报的整卡占用。

    python check_vram_report.py

判读：HIP 的"已用" = total - free。它应该 ≈ 任务管理器的整卡已用。
差值就是 ROCm issue #16035（Windows PAL 后端只算本进程），本条修好后差值应降到 <0.5 GB。
"""
import subprocess


def taskmgr():
    """任务管理器口径（GB）：专用 / 共享。"""
    out = subprocess.run(["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage",
                          r"\GPU Adapter Memory(*)\Shared Usage", "-sc", "1"],
                         capture_output=True, text=True, timeout=60).stdout
    head = row = None
    for line in out.splitlines():
        if not line.startswith('"'):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if "(PDH-CSV" in parts[0]:
            head = parts
        elif head:
            row = parts
            break
    ded = shr = 0.0
    for path, val in zip(head[1:], row[1:]):
        try:
            v = float(val)
        except ValueError:
            continue
        if "Dedicated Usage" in path:
            ded = max(ded, v)
        elif "Shared Usage" in path:
            shr = max(shr, v)
    return ded / 2 ** 30, shr / 2 ** 30


def main():
    import torch
    free, total = (x / 2 ** 30 for x in torch.cuda.mem_get_info())
    ded, shr = taskmgr()
    hip_used = total - free
    gap = ded - hip_used

    print("HIP 报      : total %.2f  可用 %.2f  已用 %.2f GB" % (total, free, hip_used))
    print("任务管理器  : 专用 %.2f  共享 %.2f GB（专用就是整卡已用）" % (ded, shr))
    print("差值        : %.2f GB" % gap)
    if gap > 1.0:
        print("→ #16035 仍在：HIP 没扣掉别的进程占的显存（现在这台机器就是这个状态）")
    else:
        print("→ 差值 <1 GB，修复合入的可能性很大，可用 probe_vram.py 复测峰值确认")


if __name__ == "__main__":
    main()
