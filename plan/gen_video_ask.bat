@echo off
rem ================================================================
rem  MiniMax H3 视频生成（交互式）——基于 ComfyUI API
rem  启动同目录下的 gen_video_ask.py，交互询问提示词/尺寸/时长/LoRA
rem  除提示词外均提供默认值（480P / 5s / LoRA 关），回车即用
rem
rem  前置条件：ComfyUI 已运行（默认 http://127.0.0.1:8188）
rem             workflow json 与脚本同目录
rem
rem  用法：双击本文件即可，或命令行 gen_video_ask.bat 透传任意参数
rem ================================================================

rem 固定工作目录为 bat 所在目录，防止路径错乱
cd /d "%~dp0"

rem 切到 GBK 代码页，保证提示词和界面不乱码
chcp 936 >nul

python gen_video_ask.py %*

echo.
echo  生成流程已结束，按任意键关闭窗口...
pause >nul
