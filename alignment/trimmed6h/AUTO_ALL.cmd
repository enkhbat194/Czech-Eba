@echo off
setlocal EnableExtensions
title Czech800 - automatic Czech sentence alignment (ALL)
set "ROOT=D:\Czech800"
set "URL=https://raw.githubusercontent.com/enkhbat194/Czech-Eba/feat/czech800-alignment-pilot/alignment/trimmed6h/czech800_auto_align.py"
if not exist "%ROOT%\raw\Czech800_tairsan.mkv" (
 echo ERROR: MKV source missing: %ROOT%\raw\Czech800_tairsan.mkv
 pause
 exit /b 1
)
if not exist "%ROOT%\data\trimmed6h_index_909.json" (
 echo ERROR: Run START_TRIMMED6H.cmd first.
 pause
 exit /b 1
)
if not exist "%ROOT%\.venv-align\Scripts\python.exe" (
 echo ERROR: Czech CTC environment missing. Run INSTALL_ALIGNMENT.cmd first.
 pause
 exit /b 1
)
if not exist "%ROOT%\scripts" mkdir "%ROOT%\scripts"
echo Downloading current batch alignment script...
curl.exe --fail --location --retry 2 --output "%ROOT%\scripts\czech800_auto_align.py" "%URL%"
if errorlevel 1 goto :error
echo Running ALL available Czech sentence CTC candidates. This can take significant CPU time.
"%ROOT%\.venv-align\Scripts\python.exe" "%ROOT%\scripts\czech800_auto_align.py" --start 1 --limit 0
if errorlevel 1 goto :error
echo.
echo RESULT JSON: %ROOT%\data\trimmed6h_ctc_candidates.json
echo REPORT JSON: %ROOT%\data\trimmed6h_ctc_report.json
echo Check the generated QA report; only review flagged cases.
pause
exit /b 0
:error
echo AUTO ALIGN FAILED - share the last error lines.
pause
exit /b 1
