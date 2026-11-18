# -*- coding: utf-8 -*-
"""给 ComfyUI 内核装一个「step 0 卸 DiT」钩子（没有预览功能）。

    python step0_free.py --install    # 打钩子（幂等，首次自动备份 .step0free.bak）
    python step0_free.py --status
    python step0_free.py --revert

为什么：plan1 的 step 0 帧预览之所以能省显存，靠的是「VAE decode -> free_memory ->
DiT 被提前卸载」这条**副作用**，不是预览本身。预览现在官方自带（--preview-method auto，
latent2rgb，几乎不占显存），所以这里只留卸载那一步，不落盘、不弹窗、不起监视脚本。

判据（跑 probe_vram.py 看）：整卡峰值从 21.43 GB 降下来、步时不变差 → 有用；
步时明显变慢 → 掉进「每步重搬权重」的慢车道，立刻 --revert。
"""
import argparse
import py_compile
import shutil
import sys

DEFAULT = r"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\latent_preview.py"
MARK = "# iwm-step0-free"
ANCHOR = "        preview_bytes = None\n"
HOOK = """        if step == 0:  # iwm-step0-free
            comfy.model_management.unload_all_models()
            comfy.model_management.soft_empty_cache()
            logging.info("step0-free: unloaded models before step 1")
"""


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def install(path):
    src = read(path)
    if MARK in src:
        return "already installed"
    if src.count(ANCHOR) != 1:
        return "FAIL: anchor 'preview_bytes = None' appears %d times" % src.count(ANCHOR)
    shutil.copyfile(path, path + ".step0free.bak")
    write(path, src.replace(ANCHOR, HOOK + ANCHOR))
    py_compile.compile(path, doraise=True)
    return "installed (backup: %s.step0free.bak)" % path


def revert(path):
    bak = path + ".step0free.bak"
    shutil.copyfile(bak, path)
    py_compile.compile(path, doraise=True)
    return "reverted from %s" % bak


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comfy", default=DEFAULT, help="path to latent_preview.py")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.revert:
        print(revert(a.comfy))
    elif a.install:
        print(install(a.comfy))
    else:
        print("installed" if MARK in read(a.comfy) else "not installed")
    print("restart ComfyUI for changes to take effect" if not a.status else "")


if __name__ == "__main__":
    sys.exit(main())
