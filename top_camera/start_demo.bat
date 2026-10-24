@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py --port 8001
) else (
  echo Run setup_demo.ps1 with Python 3.12 first.
)
pause
