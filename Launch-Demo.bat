@echo off
REM Field Intelligence - double-click launcher (Windows).
REM Starts the local application and opens it in your browser.
REM No credentials are stored in this file. If a .env file exists next to it,
REM its contents are loaded so the live Claude Q&A panel is enabled.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    echo %%A| findstr /b /c:"#" >nul || if not "%%A"=="" set "%%A=%%B"
  )
  echo Loaded .env - live Claude Q^&A enabled.
) else (
  echo No .env found - running without live Claude Q^&A. Everything else works.
)

echo Starting Field Intelligence. Close this window or press Ctrl-C to stop.
python demo_ui\serve.py
pause
