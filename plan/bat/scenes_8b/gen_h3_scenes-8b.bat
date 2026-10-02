@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_h3_scenes-8b.py %*
pause >nul
