@echo off
setlocal EnableExtensions
title Czech800: Video Audio Alignment Pilot
echo === Czech800: using existing large-v3 results to show review immediately ===
call "%~dp0RUN.cmd" check
if errorlevel 1 goto :fail
echo [1] Check MP4 and M4A audio sync at three positions.
call "%~dp0RUN.cmd" sync
if errorlevel 1 goto :fail
echo [2] Detect video word-card transitions for first 20 rows.
call "%~dp0RUN.cmd" scan --limit 20
if errorlevel 1 goto :fail
echo [3] Import previous 20-word large-v3 ASR timings (no new download).
call "%~dp0RUN.cmd" seed
if errorlevel 1 goto :fail
echo [4] Launch browser review UI.
start "" "http://127.0.0.1:8765"
call "%~dp0RUN.cmd" review
exit /b %ERRORLEVEL%
:fail
echo Error encountered. Do not proceed to export.
pause
exit /b 1
