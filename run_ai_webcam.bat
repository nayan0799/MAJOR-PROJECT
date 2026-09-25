@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run run_backend.bat once to create the environment.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m ai.detector
