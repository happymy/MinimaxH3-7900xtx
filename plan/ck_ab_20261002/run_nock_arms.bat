@echo off
REM no_ck 臂两轮: 短跑(对照 ck_r1) + 全长(对照 ck_full). 参数与 ck 臂逐项相同.
setlocal
set PY=D:\localAI\ComfyUI-last\ComfyUI_windows_portable\python_embeded\python.exe
set TD=D:\localAI\ComfyUI-last\plan\ck_ab_20261002
set PF=D:\localAI\ComfyUI-last\plan\bat\multisegment_8b\prompt.txt

echo === B1: nock short (1s / 4 steps / seed 1234) ===
"%PY%" "%TD%\gen_h3_ck_ab.py" --tag nock_s --prompt-file "%PF%" --seed 1234 --duration 1 --steps 4
echo === B1 exit=%ERRORLEVEL% ===

echo === B2: nock full (5s / 20 steps / seed 1234) ===
"%PY%" "%TD%\gen_h3_ck_ab.py" --tag nock_full --prompt-file "%PF%" --seed 1234 --duration 5 --steps 20
echo === B2 exit=%ERRORLEVEL% ===

echo ALL_DONE
endlocal
