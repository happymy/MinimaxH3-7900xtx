@echo off
rem HyperFlow Flash + 8B heretic: reference images to video, then last-frame continuation. See plan3\README.md.
chcp 65001 >nul
cd /d "%~dp0"
"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 "%~dp0gen_h3_ref2va-8b-heretic.py" %*
pause
