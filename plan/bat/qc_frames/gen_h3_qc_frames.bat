@echo off
chcp 65001 >nul
cd /d "%~dp0"
python gen_h3_qc_frames.py %*
pause >nul
