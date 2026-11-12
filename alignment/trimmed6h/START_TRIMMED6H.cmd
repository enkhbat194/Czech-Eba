@echo off
setlocal EnableExtensions
title Czech800 - trimmed 6h review
set "ROOT=D:\Czech800"
set "BASE=https://raw.githubusercontent.com/enkhbat194/Czech-Eba/feat/czech800-alignment-pilot/alignment"
if not exist "%ROOT%\scripts" mkdir "%ROOT%\scripts"
if not exist "%ROOT%\data" mkdir "%ROOT%\data"
if not exist "%ROOT%\raw\Czech800_tairsan.mkv" (
  echo ERROR: Missing "%ROOT%\raw\Czech800_tairsan.mkv"
  pause
  exit /b 1
)
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo ERROR: Missing installed Python venv. Run the original INSTALL.cmd.
  pause
  exit /b 1
)
echo [1/3] Download local reviewer ...
curl.exe --fail --location --retry 2 --output "%ROOT%\scripts\czech800_trimmed_review.py" "%BASE%/trimmed6h/czech800_trimmed_review.py"
if errorlevel 1 goto :error
echo [2/3] Download trimmed SRT / ASR / 810-target timeline map ...
curl.exe --fail --location --retry 2 --output "%ROOT%\data\trimmed6h_index_909.json" "%BASE%/trimmed6h/video_srt_909_to_czech810_timeline_candidates.json"
if errorlevel 1 goto :error
if not exist "%ROOT%\data\czech_810_alignment_targets.json" (
  curl.exe --fail --location --retry 2 --output "%ROOT%\data\czech_810_alignment_targets.json" "%BASE%/data/czech_810_alignment_targets.json"
  if errorlevel 1 goto :error
)
echo [3/3] Start review server at http://127.0.0.1:8766 ...
start "" "http://127.0.0.1:8766"
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\czech800_trimmed_review.py"
if errorlevel 1 goto :error
exit /b 0
:error
echo Startup error. Check the printed message.
pause
exit /b 1
