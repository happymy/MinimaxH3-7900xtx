@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_h3_scenes_ref.py %*
pause >nul
