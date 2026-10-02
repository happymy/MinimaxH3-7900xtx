@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_h3_scenes-8b-heretic.py %*
pause >nul
