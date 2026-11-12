@echo off
rem Evenly sample N frames and a contact sheet, to judge a render. Model-free.
chcp 65001 >nul
cd /d "%~dp0"
"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 "%~dp0gen_h3_qc_frames.py" %*
pause
