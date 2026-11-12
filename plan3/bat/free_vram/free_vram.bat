@echo off
chcp 65001 >nul
cd /d "%~dp0"
python free_vram.py %*
pause >nul
