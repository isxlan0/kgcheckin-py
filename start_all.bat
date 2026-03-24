@echo off
setlocal

cd /d "%~dp0"
set "KUGOU_SIGNER_HOME=%CD%"

where python >nul 2>nul
if %errorlevel%==0 goto run_python
where py >nul 2>nul
if %errorlevel%==0 goto run_py

echo Python interpreter not found. Install Python 3.10+ or create .venv first.
exit /b 1

:run_python
python bootstrap_env.py %*
exit /b %errorlevel%

:run_py
py -3 bootstrap_env.py %*
exit /b %errorlevel%
