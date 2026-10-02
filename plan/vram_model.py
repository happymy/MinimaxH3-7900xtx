# -*- coding: utf-8 -*-
"""H3 显存估算模型 v2：正确口径。
关键修正：
  1. WMI DedicatedUsage 是「适配器」口径，不受 comfy-aimdo headroom 硬约束 -> 不能当 ComfyUI 侧硬上界
  2. 峰值发生在采样阶段，不是 TE 阶段 -> 不能用 TE 权重去减
  3. 可用预算 = 装载可行性判据（代码保证），峰值是「有多少用多少」的上界包络
"""
MiB = 1024 ** 2

V_TOTAL_MIB   = 24560.0        # 启动日志 Total VRAM
RESERVE_MIB   = 6 * 1024.0     # --reserve-vram 6 -> EXTRA_RESERVED_VRAM = comfy-aimdo headroom
INFER_MIB     = 0.8 * 1024.0   # minimum_inference_memory() 的 0.8 GiB 项
B_ADAPTER_MIB = 3064758272 / MiB   # WMI 空闲实测 2,923 MiB（ComfyUI 未运行）

F = {
    "te4b": 2497281696, "mmproj4b": 836180704, "proj4b": 26256128,
    "te8b_stock": 10588637512, "te8b_heretic": 10017064632, "proj8b": 41990896,
    "unet": 11420663904, "vae_video": 5207808496, "vae_audio": 605254808,
}
def mib(n): return n / MiB

BUDGET_ADMIT = V_TOTAL_MIB - RESERVE_MIB            # load_models_gpu 准入上界
BUDGET_USABLE = BUDGET_ADMIT - B_ADAPTER_MIB        # 再扣非 ComfyUI 占用

print("=" * 80)
print("§1  预算：两个不同的界，别混用")
print("=" * 80)
print(f"  V_total                      {V_TOTAL_MIB:>9,.0f} MiB   启动日志")
print(f"  EXTRA_RESERVED_VRAM          {RESERVE_MIB:>9,.0f} MiB   --reserve-vram 6（双重作用，见下）")
print(f"    ├ comfy/model_management    -> load_models_gpu 准入检查的 extra_mem 项")
print(f"    └ comfy_aimdo.control       -> set_simple_vram_headroom，驱动层保持常空")
print(f"  minimum_inference_memory()    {INFER_MIB + RESERVE_MIB:>9,.1f} MiB   = 0.8 GiB + 6 GiB")
print(f"  适配器非 ComfyUI 基线（实测） {B_ADAPTER_MIB:>9,.0f} MiB   WMI，ComfyUI 未运行")
print()
print(f"  [装载判据] 可驻留上限 = V_total - reserve            {BUDGET_ADMIT:>9,.0f} MiB")
print(f"  [实际可用] 可驻留上限 - 非 ComfyUI 基线              {BUDGET_USABLE:>9,.0f} MiB")
print()
print("  ⚠ 18,416 MiB 不是 WMI 峰值的上界。WMI 是适配器口径，含驱动池 + ROCm/HIP kernel")
print("    workspace + torch 非缓存分配 + 主机映射缓冲，这些不过 ComfyUI 的账。")

print()
print("=" * 80)
print("§2  装载可行性判据：  phase_weight + reserve + B_adapter <= V_total")
print("=" * 80)
print(f"  判据等价于  phase_weight <= {BUDGET_USABLE:,.0f} MiB")
print()
PHASES = [
    ("① TE 4B (T1)",        mib(F["te4b"] + F["mmproj4b"] + F["proj4b"]),
     "GGUF 文本塔 + mmproj + proj"),
    ("① TE 8B stock (T2)",  mib(F["te8b_stock"] + F["proj8b"]),
     "fp8 safetensors，自带视觉塔"),
    ("① TE 8B 破限 (T2b)", 16721.0,
     "实测 staged（非磁盘值，见 §3）"),
    ("② 采样 UNet（全驻留）", mib(F["unet"]),
     "实际流式，此为上界假设"),
    ("③ VAE decode",        mib(F["vae_video"] + F["vae_audio"]),
     "ForceUnloadBeforeDecode 后，UNet 已腾空"),
]
print(f"{'阶段':<24} {'权重 MiB':>10} {'余量 MiB':>11} {'判定':>6}  说明")
for name, w, note in PHASES:
    slack = BUDGET_USABLE - w
    ok = "✓" if slack >= 0 else "✗ 超"
    print(f"{name:<24} {w:>10,.0f} {slack:>11,.0f} {ok:>6}  {note}")

print()
print("=" * 80)
print("§3  staged 系数（磁盘 → GPU 驻留）：为什么 T2b 超预算而 T2 不超")
print("=" * 80)
print(f"{'变体':<14} {'磁盘 MiB':>10} {'staged MiB':>11} {'系数':>7}  含义")
for k, d, s, note in [
    ("T1_4b",      F["te4b"] + F["mmproj4b"], 3.6*1024, "GGUF 直接映射，膨胀来自结构开销"),
    ("T2_8b",      F["te8b_stock"],            10097.0, "全 fp8，原样上卡 -> 系数 1.000"),
    ("T2b_8b_hrt", F["te8b_heretic"],          16721.0, "混合精度，fp8 张量上卡后被上采样"),
]:
    print(f"{k:<14} {mib(d):>10,.0f} {s:>11,.0f} {s/mib(d):>7.3f}  {note}")
print()
print(f"  判据后果：T2b staged {16721:,.0f} > 可用 {BUDGET_USABLE:,.0f} MiB，")
print(f"            超 {16721 - BUDGET_USABLE:,.0f} MiB  -> 与 Plan.md §11.4 标注的「超出可用显存」吻合")
print(f"            T2   staged {10097:,.0f} < 可用 {BUDGET_USABLE:,.0f} MiB，余 {BUDGET_USABLE-10097:,.0f} MiB")

print()
print("=" * 80)
print("§4  实测峰值 vs 预算：峰值是「有多少用多少」，不是内在需求")
print("=" * 80)
MEAS = [
    ("4B 0.415MP 124f", 22459, 3815, 0.414720, 124),
    ("8B 0.415MP 124f", 20761, 7405, 0.414720, 124),
    ("8B 0.642MP 107f", 21473, 7355, 0.642048, 107),
]
print(f"{'run':<20} {'WMI峰':>8} {'WMI谷':>7} {'谷+峰差':>9} {'峰-准入界':>10} {'MP':>7} {'帧':>5}")
for n, pk, fl, px, fr in MEAS:
    print(f"{n:<20} {pk:>8,.0f} {fl:>7,.0f} {pk-fl:>9,.0f} {pk-BUDGET_ADMIT:>+10,.0f} {px:>7.3f} {fr:>5}")
print()
print("  观察：")
print(f"   · 三点 WMI 峰跨度 {max(m[1] for m in MEAS) - min(m[1] for m in MEAS):,.0f} MiB"
      f"（{(max(m[1] for m in MEAS)/min(m[1] for m in MEAS)-1)*100:.1f}%），"
      "分辨率更高的两点反而不是最高。")
print("   · 谷值越低，峰越高（4B 谷 3,815 → 峰 22,459 为最高）。")
print("     解释：准入只管「装不装得下」，装下后由 comfy-aimdo 6 个 hook 按压力回收，")
print("     所以可用越多、吃越多。WMI 峰值因此度量「拿走了多少」，不度量「需要多少」。")
print("   · 谷-峰差（本次真正吃下的增量）："
      f"{max(m[1]-m[2] for m in MEAS):,.0f} / {min(m[1]-m[2] for m in MEAS):,.0f} MiB")

print()
print("=" * 80)
print("§5  分辨率斜率（含混淆变量，慎用）")
print("=" * 80)
a, b = MEAS[1], MEAS[2]
print(f"  仅有的同 TE 对：{a[0]} vs {b[0]}")
print(f"    Δ分辨率 {b[3]-a[3]:+.3f} MP   Δ帧数 {b[4]-a[4]:+d}   Δ峰值 {b[1]-a[1]:+,.0f} MiB")
print(f"    -> {(b[1]-a[1])/(b[3]-a[3]):,.0f} MiB/MP")
print()
print("  ⚠ 这两个变量同时变了（分辨率↑ 帧数↓），斜率无法归因。")
print("    §11.10.4 预测的 0.60 MP @124 帧（12.2 分钟）尚未实跑，此斜率不能用于外推。")

print()
print("=" * 80)
print("§6  实用速查：改配置前先过这个判据")
print("=" * 80)
print(f"  单个大件上限 = {BUDGET_USABLE:,.0f} MiB（占 24,560 的 {BUDGET_USABLE/V_TOTAL_MIB*100:.0f}%）")
print(f"  余量表：")
for name, w, note in PHASES:
    print(f"    {name:<24} 占预算 {w/BUDGET_USABLE*100:>5.1f}%   余 {BUDGET_USABLE-w:>+9,.0f} MiB")
