# -*- coding: utf-8 -*-
"""MiniMax H3 视频任务「生成中实时预览」监视器 —— 独立脚本版。

功能（与 ComfyUI 内核已实现的帧预览链路同源，本脚本负责“在旁边盯着”）:
    只要 ComfyUI 上有人在跑视频生成任务（无论由谁提交：项目 server / 手动 API / 工作流
    页面），本脚本就自动:
      1. 检测任务开始/结束（轮询 GET /queue 的 queue_running / queue_pending）
      2. 任务采样期间轮询 %TEMP%\\iw-preview-* 目录，实时打印内核落盘的真实预览帧
         （这些帧是采样中途用工作流的 video VAE 解码 latent 得到的成片分辨率真帧，不是
          34x60 小图；第一批在 step 0 触发，**附带把 DiT 提前卸载 —— 见下方
          「【step 0 首批预览的附加效果】」**，之后每 total_steps//4 步一批，
          20 步任务出 4 批，每批 6 帧）
      3. 可选 --collect 把帧复制到指定目录统一留底
      4. 可选 --open 在首个预览目录出现时用资源管理器打开一次
      5. 任务结束打印该任务的总预览帧数与耗时

与内核的关系（重要）:
    预览帧由 ComfyUI 内置改动负责生成并落盘（latent_preview.py 的采样 callback 解码后
    写入 %TEMP% 下的 iw-preview-{MMddHHmmss}-{pid%100000} 文件夹，首个任务自动弹过一次
    资源管理器）; 本脚本零侵入、纯监视，不干预生成、不重复解码、不改工作流。
    因此内核链路需处于已部署状态，且任务请求的 extra_data.preview_file=true
    （项目侧默认 true；手动 POST /prompt 若不传则 ComfyUI 默认 true）。

【step 0 首批预览的附加效果：提前卸载 DiT】(2026-10-07 补记):
    链路: step 0 触发第一批预览 -> video VAE decode -> ComfyUI 的 free_memory
    -> 动态 DiT 被卸载、压到低水位 -> 后续采样再按需换回。
    即「借首批预览的解码动作，在采样最早期就把 DiT 卸一次」，不是本脚本
    发出的卸载请求（本脚本仍是零侵入，见上）。
    2026-10-07 更新：触发点从 step 1 提前到 step 0（内核 latent_preview.py
    条件改为 step % every == 0），卸载时机再早一个采样步。

    为什么值得这么做（实机经验）:
      1. 反复加载模型的耗时 << 爆显存的代价。显存一旦被顶爆，--enable-dynamic-vram
         不会崩进程，而是把数据退到系统内存（页面文件 / swap）走，那一段渲染
         **非常慢**；所以宁可让 DiT 反复进出，也不让它把显存顶满。
      2. 长提示词（文本张量大）与长视频时长（帧多、latent 大）时最明显 ——
         这两类任务采样期显存占用最高，提前卸载的收益最大。
      3. --enable-dynamic-vram 下「显存爆了」不等于出错：只有内存也被耗尽时，
         操作系统才会卡死。因此真正的风险不是报错，而是**整机卡死** ——
         提前卸载是防卡死，不是防报错。

    对本脚本的影响: 零。卸载由内核 VAE decode 自带的 free_memory 触发，
    本脚本不发任何卸载请求、不干预生成，仍保持零侵入纯监视。

【内核修改清单】本次功能改动了以下文件（相对 ComfyUI_windows_portable\\，均为 UTF-8）:
  1. ComfyUI\\latent_preview.py          —— 帧预览主战场：模块级状态（_frame_preview_
     enabled / vae / dir / count）、_save_frame_preview() 解码中途 x0 落盘、采样 callback
     挂载（step % every == 0，即 step 0 首批 + 每 total_steps//4 步一批）、set_frame_preview_enabled/
     vae() 开关与注册。
  2. ComfyUI\\comfy_extras\\nodes_minimax_h3.py —— H3 节点注册视频 VAE：
     MiniMaxH3ImageToVideo.execute（约 142 行）与 MiniMaxH3ReferenceToVideo.execute
     （约 294 行）各加一行 latent_preview.set_frame_preview_vae(vae)。全量覆盖
     plan/molbal_workflows/final 的 15 个视频工作流（i2v / t2v 共用 ImageToVideo、
     ref2v 用 ReferenceToVideo），未改任何工作流文件；MiniMaxH3AddGuide 等只是
     锚点/增强节点，非任务入口，不需要注册。
  3. ComfyUI\\execution.py              —— 每任务开关：set_frame_preview_enabled(
     extra_data.get("preview_file", True))，任务开始前 set_frame_preview_vae(None) 重置。
  注意：本地 ComfyUI 目录本身是 git 仓库，`git status` 权威确认本地仅以上 3 个
  文件被改动（即帧预览功能全集）。与官方 0.38.0 全量对比另有 11 个文件不同，经
  git log 逐一归因，全是 9-30 `git pull` 拉到的官方上游提交（tag 之后的 master
  提交，如 crf 默认值提升、资产恢复、DynamicGroup 等），非本地改动，无需手工迁移。
  节点/回调代码在启动时加载，修改后必须重启 ComfyUI 才生效。

【内核改动 diff】以下补丁在本目录，均已在官方 0.38.0 源码树 `git apply --check` 验证通过:
  - frame_preview_kernel.patch（约 8KB, 3 文件）: 本地改动权威版，由 git diff 直接
    生成，只含帧预览功能的 3 个文件（latent_preview / execution / nodes_minimax_h3）。
    只迁帧预览功能用这个: 在官方 0.38.0 源码树根目录 `git apply` 即可。
  - official-0.38.0-to-current.patch（约 63KB, 14 文件）: 官方 0.38.0 tag zip ->
    当前内核的完整复刻 = 帧预览 3 文件 + 11 个 9-30 git pull 拉到的官方上游提交
    （a65316bd 视频编码 crf 默认 18/24、e6beab52+ebd432a7 资产硬盘恢复、986c4d15
    minimax VAE num_layers=36、2d2fa46e DynamicGroup 输入、fb2315f1 qwen 2.1
    int8/int4 cache 崩溃修复）。要 100% 复刻当前内核环境用这个。
  - 权威核对法: 当前内核目录是 git 仓库，随时
    `git -C ComfyUI_windows_portable\\ComfyUI status` 查看本地改动，比任何 patch 可靠。
  - 旧恢复手段仍在: D:\\localAI\\ComfyUI-last\\ComfyUI_windows_portable - 副本\\
    （2026-08-26 内核完整备份，版本 0.34.0）。

为什么是轮询而不是 WebSocket:
    与 plan/bat 其余脚本一致，只用标准库直连本地 API，不引第三方依赖。
    ComfyUI 单 worker 串行执行，同一时刻至多一个任务在采样，%TEMP% 新出现的
    iw-preview-* 目录必然属于“当前最早开始且仍在运行”的任务，按此绑定即可。

用法:
    持续监视:     python watch_h3_preview.py
    只盯当前队列: python watch_h3_preview.py --once
    带归档:       python watch_h3_preview.py --collect D:/previews
    再弹一次窗:   python watch_h3_preview.py --open
    轮询加速:     python watch_h3_preview.py --interval 2
    退出:         Ctrl+C 随时退出，不影响 ComfyUI 上正在跑的任务
"""
import json, urllib.request, urllib.error, os, sys, time, argparse, glob, shutil, tempfile

API = 'http://127.0.0.1:8188'
# 本地 API 直连：系统代理不放行 loopback 会回 404；空 ProxyHandler 同时绕过环境变量与注册表代理。
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_queue():
    """GET /queue：返回 {queue_running, queue_pending}，每个条目 = [num, prompt_id, graph, extra_data, outputs]。"""
    with OPENER.open(urllib.request.Request(API + '/queue', method='GET'), timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def get_history(prompt_id):
    """GET /history/{id}：任务结果与最终状态（success / error），轮询到任务结束时取一次。"""
    try:
        with OPENER.open(urllib.request.Request(API + '/history/%s' % prompt_id, method='GET'), timeout=5) as r:
            h = json.loads(r.read().decode('utf-8'))
            return h.get(prompt_id)
    except Exception:
        return None


def preview_dirs():
    """当前 %TEMP% 下所有 iw-preview-* 目录（按修改时间倒序，最新的在最前）。"""
    out = glob.glob(os.path.join(tempfile.gettempdir(), 'iw-preview-*'))
    return sorted(out, key=lambda p: os.path.getmtime(p), reverse=True)


def frames_of(directory):
    """目录下所有预览帧 jpg（按文件名排序，如 step005_f17.jpg）。"""
    return sorted(f for f in os.listdir(directory) if f.lower().endswith('.jpg'))


def now():
    return time.strftime('%H:%M:%S')


class Task:
    """一个被监视的视频生成任务。"""

    def __init__(self, prompt_id, preview_enabled):
        self.prompt_id = prompt_id          # 任务唯一 id
        self.preview_enabled = preview_enabled  # extra_data.preview_file（False 则内核不落帧）
        self.start = time.time()            # 开始时间戳（用于统计耗时）
        self.dir = None                     # 绑定的 %TEMP% 预览目录
        self.seen = set()                   # 已打印过的帧文件名（增量输出用）
        self.finished = False               # 是否已在运行队列中消失


def main():
    ap = argparse.ArgumentParser(
        description='监视 ComfyUI 上的视频生成任务，实时展示采样中途的真实预览帧（内核落盘 %TEMP%\\iw-preview-*）')
    ap.add_argument('--interval', type=int, default=5, help='轮询间隔秒数，默认 5')
    ap.add_argument('--once', action='store_true',
                    help='检测到队列清空（无 running 且无 pending）即退出；默认持续监视直到 Ctrl+C')
    ap.add_argument('--collect', default=None,
                    help='把每个任务的预览帧复制到该目录（按 prompt_id 子目录留底）')
    ap.add_argument('--open', action='store_true',
                    help='首个预览目录出现时用资源管理器再打开一次（内核默认已自动弹过一次）')
    a = ap.parse_args()

    known_dirs = set(preview_dirs())  # 启动前已存在的目录视为历史，不监视
    tasks = []                        # 按开始顺序排列的 Task 列表

    print('[%s] 帧预览监视器启动，ComfyUI: %s（Ctrl+C 退出）' % (now(), API))
    if a.collect:
        os.makedirs(a.collect, exist_ok=True)
        print('[%s] 预览帧将归档到: %s' % (now(), a.collect))

    while True:
        try:
            q = get_queue()
        except Exception as e:
            # ComfyUI 没起来或重启中：重试即可，不影响任何一边。
            print('[%s] WARN: 无法连接 ComfyUI: %s' % (now(), e))
            time.sleep(a.interval)
            continue

        running = {item[1]: item for item in q.get('queue_running', [])}
        pending_ids = {item[1] for item in q.get('queue_pending', [])}

        # ---- 1) 检测新任务：不在 tasks 里的 running / pending 任务单独记一条 ----
        for pid in running:
            if any(t.prompt_id == pid for t in tasks):
                continue
            extra = running[pid][3] if len(running[pid]) > 3 else {}
            enabled = extra.get('preview_file', True)
            t = Task(pid, enabled)
            tasks.append(t)
            state = '正在运行' if pid in running else '排队中'
            if enabled:
                print('[%s] ▶ 任务开始 %s（%s，帧预览已开启）' % (now(), pid[:8], state))
            else:
                print('[%s] ▶ 任务开始 %s（%s，extra_data.preview_file=false，无预览帧）'
                      % (now(), pid[:8], state))
        for pid in pending_ids:
            if any(t.prompt_id == pid for t in tasks):
                continue
            t = Task(pid, True)
            tasks.append(t)
            print('[%s] ▶ 任务排队 %s' % (now(), pid[:8]))

        # ---- 2) 绑定新预览目录到“最早开始且未绑定”的运行中任务 ----
        dirs = set(preview_dirs())
        for d in sorted(dirs - known_dirs, key=lambda p: os.path.getmtime(p)):
            owner = next((t for t in tasks if t.dir is None and not t.finished and t.preview_enabled), None)
            if owner is None:
                continue  # 没有可绑定的任务（理论上不会发生），跳过
            owner.dir = d
            known_dirs.add(d)
            print('[%s] ★ 新预览目录: %s（任务 %s）' % (now(), d, owner.prompt_id[:8]))
            if a.open:
                os.startfile(d)
                print('[%s]   已用资源管理器打开' % now())

        # ---- 3) 增量打印新帧 + 可选归档 ----
        for t in tasks:
            if t.dir is None or not os.path.isdir(t.dir):
                continue
            for f in frames_of(t.dir):
                if f in t.seen:
                    continue
                t.seen.add(f)
                print('[%s]   [预览] %s：%s' % (now(), t.prompt_id[:8], f))
                if a.collect:
                    dest = os.path.join(a.collect, t.prompt_id[:8])
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy2(os.path.join(t.dir, f), os.path.join(dest, f))

        # ---- 4) 任务结束：打印统计 ----
        for t in list(tasks):
            if t.finished:
                continue
            if t.prompt_id in running or t.prompt_id in pending_ids:
                continue  # 还在队列里
            t.finished = True
            h = get_history(t.prompt_id)
            status = (h.get('status', {}) or {}).get('status_str', '?') if h else '?'
            elapsed = time.time() - t.start
            if t.preview_enabled:
                n = len(t.seen)
                print('[%s] ✔ 任务 %s 结束（%s，耗时 %.0fs，预览帧 %d 张）%s'
                      % (now(), t.prompt_id[:8], status, elapsed, n,
                         ' -> %s' % t.dir if t.dir else '（未产生预览帧）'))
            else:
                print('[%s] ✔ 任务 %s 结束（%s，耗时 %.0fs，未开启帧预览）'
                      % (now(), t.prompt_id[:8], status, elapsed))

        # ---- 5) --once：队列彻底清空即退出 ----
        if a.once and not running and not pending_ids:
            print('[%s] 队列已清空，--once 退出' % now())
            break

        time.sleep(a.interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[%s] 监视器已退出（不影响 ComfyUI 上正在跑的任务）' % now())
        sys.exit(0)