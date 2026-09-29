@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_extract_frames.py %*
pause >nul
