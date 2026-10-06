# -*- coding: utf-8 -*-
"""ComfyUI /free 端点调用工具 —— 卸载模型、清掉 Dynamic VRAM 残留。

用法:
    python free_vram.py                 # 查状态 -> POST /free -> 轮询验证释放了多少
    python free_vram.py --status        # 只看 VRAM / 队列状态，不调用 /free
    python free_vram.py --interval 60   # 每 60s 自动调用一次（批跑时挂旁边），Ctrl+C 退出
    python free_vram.py --no-verify     # 发出 /free 后立即返回，不等待验证

为什么需要它:
    --enable-dynamic-vram 下残留物理页会让同一条工作流越跑越慢（十几分钟的
    活拖成几小时）。多段脚本已在段间调 /free，本工具用于段外的手动清理、
    以及批跑期间的周期清理。

限制（重要，源码实测于 0.38.0）:
    1. /free 是异步 flag 端点，不是立即释放。server.py 的 post_free 只做
       prompt_queue.set_flag(...) 就返回 HTTP 200；真正的
       unload_all_models() + e.reset() + gc.collect() + soft_empty_cache()
       由 main.py 的 prompt worker 在下一次 q.get() 返回后调用 get_flags()
       才执行。所以 200 ≠ 已释放，必须用 /system_stats 的 vram_free 验证。
    2. 生成进行中调用是安全的：不会打断当前 prompt，flag 挂到它执行完才
       生效（这正是多段脚本「段间 POST /free」让下一段干净开跑的原理）。
    3. 空闲时秒级生效：set_flag 的 notify() 唤醒阻塞在 q.get(timeout=1000)
       的 worker，get() 因队列空且 timeout 非 None 立即返回 None ->
       get_flags() -> 卸载。
    4. 它救不了「单个任务内部越跑越慢」——那种情况只能重启 ComfyUI。
       本工具解决的是任务之间的累积。
    5. 任务执行中 VRAM 自己会波动（DiT -> 解码的阶段切换、图里的
       ForceUnloadBeforeDecode），那不是 /free 的效果。只有 running 归零之后
       vram_free 上升，才算 flag 真正被消费、释放生效。
"""
import json, urllib.request, urllib.error, time, sys, argparse

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8188
BASE = 'http://%s:%d' % (DEFAULT_HOST, DEFAULT_PORT)

GB = 2 ** 30
MB = 2 ** 20

sys.stdout.reconfigure(line_buffering=True)   # 重定向到文件时也逐行落盘


def api(path, data=None, timeout=15):
    """GET 或 POST 一个 JSON 端点，返回解析后的 dict。"""
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE + path, data=body, headers=headers,
                                 method='POST' if data is not None else 'GET')
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return json.loads(raw) if raw.strip() else {}   # /free 回 200 空体


def stats():
    """VRAM 与队列快照（/queue 拿不到时 running/pending 记为 -1）。"""
    dev = api('/system_stats')['devices'][0]
    try:
        q = api('/queue')
        running, pending = len(q['queue_running']), len(q['queue_pending'])
    except Exception:
        running = pending = -1
    return {'free': dev['vram_free'], 'total': dev['vram_total'],
            'running': running, 'pending': pending}


def show(tag, st):
    n = lambda v: '?' if v < 0 else str(v)
    print('[%s] %-7s vram_free=%.2f/%.2f GB  running=%s pending=%s' %
          (time.strftime('%H:%M:%S'), tag, st['free'] / GB, st['total'] / GB,
           n(st['running']), n(st['pending'])))


def free():
    """POST /free：服务端只 set_flag 就返回 200，真正释放在 worker 线程。"""
    api('/free', {'unload_models': True, 'free_memory': True})


def verify(before, timeout):
    """轮询 /system_stats 到 vram_free 上升或超时。返回 (末次快照, 耗时, 是否上升)。"""
    t0 = time.time()
    st = dict(before)
    while time.time() - t0 < timeout:
        time.sleep(1.0)
        try:
            st = stats()
        except Exception:
            break
        if st['free'] > before['free'] + 50 * MB:
            return st, time.time() - t0, True
    return st, time.time() - t0, False


def loop(args):
    """周期模式：每 interval 秒调一次 /free，直到 Ctrl+C。

    服务不可达时打印错误并继续下一轮（ComfyUI 重启后能自动接上），
    这是挂机清理真正需要的失败方式。
    """
    print('interval mode: /free every %ds, Ctrl+C to stop' % args.interval)
    n = 0
    try:
        while True:
            n += 1
            try:
                free()
                st = stats()
            except Exception as e:
                print('[%s] ERROR: %s' % (time.strftime('%H:%M:%S'), e))
                time.sleep(args.interval)
                continue
            show('#%d' % n, st)
            if st['running'] > 0:
                print('        a job is running -> the flag applies when it finishes')
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('stopped after %d /free call(s)' % n)


def main():
    global BASE
    ap = argparse.ArgumentParser(
        description='调用 ComfyUI /free 卸载模型、释放 Dynamic VRAM 残留。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''注意: /free 是异步 flag 端点, HTTP 200 只代表 flag 已设置;
真正释放由 prompt worker 在当前任务结束后执行, 故用 /system_stats 的
vram_free 验证。生成中调用不会打断任务, 也救不了单个任务内部的变慢。''')
    ap.add_argument('--host', default=DEFAULT_HOST, help='ComfyUI 地址（默认 %s）' % DEFAULT_HOST)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT, help='端口（默认 %d）' % DEFAULT_PORT)
    ap.add_argument('--status', action='store_true', help='只查询状态，不调用 /free')
    ap.add_argument('--interval', type=int, default=0,
                    help='每隔 N 秒自动调用一次 /free 并循环，Ctrl+C 退出（0=只调一次）')
    ap.add_argument('--timeout', type=int, default=30,
                    help='验证释放效果的轮询秒数（默认 30）')
    ap.add_argument('--no-verify', action='store_true', help='发出 /free 后立即返回，不等待验证')
    args = ap.parse_args()
    BASE = 'http://%s:%d' % (args.host, args.port)

    try:
        st0 = stats()
    except Exception as e:
        print('ERROR: cannot reach ComfyUI at %s : %s' % (BASE, e))
        return 2
    show('before', st0)
    if args.status:
        return 0

    if args.interval > 0:
        loop(args)
        return 0

    try:
        free()
    except urllib.error.HTTPError as e:
        print('ERROR: POST /free -> %s %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))
        return 1
    except Exception as e:
        print('ERROR: POST /free failed: %s' % e)
        return 1
    print('POST /free -> 200  (flag set; release runs on the worker thread)')
    if args.no_verify:
        return 0

    st1, dt, rose = verify(st0, args.timeout)
    show('after', st1)
    delta = (st1['free'] - st0['free']) / GB
    if st1['running'] > 0:
        # 任务没结束 -> flag 尚未被消费，此刻的 VRAM 变化只可能是任务自身
        # 的阶段切换（DiT -> 解码、ForceUnloadBeforeDecode），不能算作 /free。
        print('vram %+.2f GB in %.1fs (job still running -> not from /free)' % (delta, dt))
        print('  the flag is pending; it applies when the job finishes')
    elif rose:
        print('released %.2f GB in %.1fs' % (delta, dt))
    else:
        print('vram unchanged (%+.2f GB) in %.1fs' % (delta, dt))
        print('  no model resident (already free), or the worker has not cycled yet')
    return 0


if __name__ == '__main__':
    sys.exit(main())
