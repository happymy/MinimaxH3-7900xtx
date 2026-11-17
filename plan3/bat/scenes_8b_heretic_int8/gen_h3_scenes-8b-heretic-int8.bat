@echo off
rem HyperFlow Flash + 8B heretic: per-shot prompts and durations. See plan3\README.md.
chcp 65001 >nul
cd /d "%~dp0"
"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 "%~dp0gen_h3_scenes-8b-heretic-int8.py" %*
pause
