@echo off
setlocal EnableExtensions
title Czech800: analyze next 20 words
echo CUDA library PATH is configured inside RUN.cmd.
echo The medium model may download on first use.
call "%~dp0RUN.cmd" transcribe --start 21 --limit 40 --model medium
if errorlevel 1 goto :fail
start "" "http://127.0.0.1:8765"
call "%~dp0RUN.cmd" review
exit /b %ERRORLEVEL%
:fail
pause
exit /b 1
