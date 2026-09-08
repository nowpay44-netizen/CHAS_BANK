@echo off
title CHASBANK Demo
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% neq 0 (
  echo Python 3 is required. Install Python from python.org and try again.
  pause
  exit /b 1
)
py -m pip install -r requirements.txt
start "" http://127.0.0.1:5000
py app.py
pause
