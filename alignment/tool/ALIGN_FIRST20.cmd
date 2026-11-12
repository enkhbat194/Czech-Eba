@echo off
setlocal EnableExtensions
title Czech800 - Czech forced align
set "ROOT=D:\Czech800"
if not exist "%ROOT%\.venv-align\Scripts\python.exe" (
 echo First run INSTALL_ALIGNMENT.cmd from this folder.
 pause
 exit /b 1
)
"%ROOT%\.venv-align\Scripts\python.exe" "%ROOT%\scripts\czech800_align.py" --limit 20 --start 1
if errorlevel 1 pause
