@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_h3_scenes.py %*
pause >nul
