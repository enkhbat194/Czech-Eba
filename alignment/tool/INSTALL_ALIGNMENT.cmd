@echo off
setlocal EnableExtensions
title Czech800 - optional Czech CTC alignment
set "ROOT=D:\Czech800"
set "BASE=https://raw.githubusercontent.com/enkhbat194/Czech-Eba/feat/czech800-alignment-pilot/alignment"
if not exist "%ROOT%\scripts" mkdir "%ROOT%\scripts"
echo Download Czech-specific alignment integration from your GitHub...
curl.exe --fail --location --retry 2 --output "%ROOT%\scripts\czech800_align.py" "%BASE%/tool/czech800_align.py"
if errorlevel 1 goto :fail
if not exist "%ROOT%\.venv-align\Scripts\python.exe" py -3.11 -m venv "%ROOT%\.venv-align"
if errorlevel 1 goto :fail
echo Installing WhisperX in a SEPARATE venv. This may download large ML libraries.
"%ROOT%\.venv-align\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%ROOT%\.venv-align\Scripts\python.exe" -m pip install --no-cache-dir whisperx
if errorlevel 1 goto :fail
echo Czech CTC aligner installed. Use ALIGN_FIRST20.cmd.
pause
exit /b 0
:fail
echo Installation error. Existing Whisper/CUDA environment remains unchanged.
pause
exit /b 1
