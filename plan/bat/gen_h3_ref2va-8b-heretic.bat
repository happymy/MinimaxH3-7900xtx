@echo off
chcp 65001 >nul
cd /d "%~dp0"
python gen_h3_ref2va-8b-heretic.py %*
pause >nul
