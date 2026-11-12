@echo off
setlocal EnableExtensions
title Czech800 Tool - Install
set "ROOT=D:\Czech800"
set "BASE=https://raw.githubusercontent.com/enkhbat194/Czech-Eba/feat/czech800-alignment-pilot/alignment"
echo === Czech800: Installing local tool ===
if not exist "%ROOT%\raw\Czech800.mp4" echo WARNING: %ROOT%\raw\Czech800.mp4 missing
if not exist "%ROOT%\raw\Czech800.m4a" echo WARNING: %ROOT%\raw\Czech800.m4a missing
if not exist "%ROOT%\.venv\Scripts\python.exe" (
 echo ERROR: Existing Python venv missing: %ROOT%\.venv
 pause
 exit /b 1
)
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\scripts" mkdir "%ROOT%\scripts"
echo [1/4] Download code from YOUR GitHub branch...
curl.exe --fail --location --retry 2 --output "%ROOT%\scripts\czech800_tool.py" "%BASE%/tool/czech800_tool.py"
if errorlevel 1 goto :fail
echo [2/4] Download complete Czech-Mongolian 810-row dataset...
curl.exe --fail --location --retry 2 --output "%ROOT%\data\czech_810_alignment_targets.json" "%BASE%/data/czech_810_alignment_targets.json"
if errorlevel 1 goto :fail
echo [3/4] Download pre-existing Whisper large-v3 first20 timestamps...
curl.exe --fail --location --retry 2 --output "%ROOT%\data\first20_largev3_asr_legacy.json" "%BASE%/data/first20_largev3_asr_legacy.json"
if errorlevel 1 goto :fail
echo [4/4] Add small local dependencies; keep existing faster-whisper and CUDA...
"%ROOT%\.venv\Scripts\python.exe" -m pip install --no-cache-dir "numpy>=1.26,<3" "scipy>=1.12,<2" "opencv-python-headless>=4.8,<5" "rapidfuzz>=3.5,<4" "flask>=3.0,<4"
if errorlevel 1 goto :fail
echo.
echo Setup complete. Press any key.
echo NEXT: run START_PILOT.cmd (from this same folder).
pause
exit /b 0
:fail
echo ERROR: Setup stopped. Read error lines above. No source audio modified.
pause
exit /b 1
