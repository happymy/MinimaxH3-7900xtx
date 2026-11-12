@echo off
rem Pull first / middle / last frame out of a video, for ref2va references. Model-free.
chcp 65001 >nul
cd /d "%~dp0"
"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 "%~dp0gen_extract_frames.py" %*
pause
