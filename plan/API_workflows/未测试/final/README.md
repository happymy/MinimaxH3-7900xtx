# API 格式工作流 · 交付层

2026-10-02 新建。**与 `molbal_workflows\final\` 逐层对齐**，补上 API 格式此前缺失的交付层。

## 性质

本目录是 **`API_workflows\` 下各变体目录的纯拷贝**，sha256 逐份校验一致。

- 原目录**一个字节都没动**，两份报告里 `plan\API_workflows\未测试\op-8b-heretic\*.json` 这类精确路径引用继续有效。
- 用途是「取哪一版交付」看这一层就够，不用去翻 `omy\` / `op\` / `8b\` 这些语义不统一的历史目录名。
- **不要在两处同时改**：改了 `final\` 不会回写原目录，反之亦然。要改请改原目录后重新拷贝。

## 分层与来源

| 交付层 | 拷贝自 | 文本编码器 | 官方 prompt |
|---|---|---|---|
| `final\4b\` | `API_workflows\omy\` | 4B stock | 无 |
| `final\4b\op\` | `API_workflows\未测试\op\` | 4B stock | 有 |
| `final\8b\` | `API_workflows\未测试\8b\` | 8B stock | 无 |
| `final\op-8b\` | `API_workflows\未测试\op-8b\` | 8B stock | 有 |
| `final\op-8b-heretic\` | `API_workflows\未测试\op-8b-heretic\` | 8B 破限 | 有 |

每个目录 3 份：`minimax_h3_{t2v,i2v,ref2v}-gguf-api*.json`，共 15 份。

## 三套文本编码器（实测取自工作流原文）

| 变体 | 视觉塔 | 投影头 |
|---|---|---|
| 4B | `qwen3-vl-4b-heretic-Q4_K_M.gguf` | `mmh3-4b-ClipProj-v3.1.safetensors` |
| 8B stock | `qwen3vl_8b_fp8_scaled.safetensors` | `mmh3-8b-ClipProj-v3.1.safetensors` |
| 8B 破限 | `qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors` | `mmh3-8b-ClipProj-v3.1.safetensors` |

三套变体的 UNet / VAE 完全相同：`minimax_h3_fl2va_pruned-Q4_K_M.gguf`、`minimax_h3_video_vae_fp16.safetensors`、`minimax_h3_audio_vae_fp32.safetensors`。

> 4B 那份文件名带 `heretic` 字样，但走的是 **Q4_K_M 量化**、不是破限权重；只有 8B 破限那份是 `fp8_e4m3fn` 破限权重。命名容易混，以本表为准。

## 与 UI 格式交付层的对应

| 变体 | UI 格式 | API 格式 |
|---|---|---|
| 4B 无 op | `molbal_workflows\final\4b\` | `API_workflows\未测试\final\4b\` |
| 4B + op | `molbal_workflows\final\4b\op\` | `API_workflows\未测试\final\4b\op\` |
| 8B 无 op | `molbal_workflows\final\8b\` | `API_workflows\未测试\final\8b\` |
| 8B + op | `molbal_workflows\final\op-8b\` | `API_workflows\未测试\final\op-8b\` |
| 8B 破限 + op | `molbal_workflows\final\op-8b-heretic\` | `API_workflows\未测试\final\op-8b-heretic\` |

> UI 格式的 8B 工作流多带一条 32B 视觉塔选项 `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` 和 3 个 fp8 量化 UNet —— 这些在 JSON 里是 `name` + HF `url` 的**自动下载条目，本机并未安装**（`models\text_encoders\` 里只有 4B 与 8B 两套）。API 格式这 15 份只保留 `qwen3vl_8b_fp8_scaled` 一条，不含 32B。

## 不在本交付层内

| 目录 | 原因 |
|---|---|
| `API_workflows\Calliope\` / `go\` | Krea2 T2I 调试线，与 H3 无关，且 5 套 `bak` 命名不统一尚未清理 |
| `API_workflows\omy\bak 01\` | 调试期快照 |

## 提醒

API 格式工作流走 `POST /prompt` 提交，**参数覆盖只在内存中做，不写回本目录的 JSON**。
