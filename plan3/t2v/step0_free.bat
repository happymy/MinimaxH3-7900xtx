@echo off
rem Free every model before the next Queue. See the deployment doc, section 7.5.
rem Kept ASCII on purpose: a .bat with Chinese needs UTF-8 without BOM + chcp 65001.
"C:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe" -X utf8 "%~dp0step0_free.py" %*
pause
