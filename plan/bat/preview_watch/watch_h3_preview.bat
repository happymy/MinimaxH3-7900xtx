@echo off
chcp 65001 >nul
cd /d "%~dp0"
python watch_h3_preview.py %*
pause >nul