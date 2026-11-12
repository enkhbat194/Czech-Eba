@echo off
setlocal EnableExtensions
set "ROOT=D:\Czech800"
set "PATH=%ROOT%\.venv\Lib\site-packages\nvidia\cublas\bin;%ROOT%\.venv\Lib\site-packages\nvidia\cudnn\bin;%ROOT%\.venv\Lib\site-packages\nvidia\cuda_runtime\bin;%PATH%"
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\czech800_tool.py" %*
exit /b %ERRORLEVEL%
