@echo off
chcp 936 >nul
cd /d "%~dp0"
python gen_h3_ref2va.py %*
pause >nul
