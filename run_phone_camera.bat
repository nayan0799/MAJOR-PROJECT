@echo off
cd /d "%~dp0"
if "%SMARTBUS_PHONE_IP%"=="" (
  set /p SMARTBUS_PHONE_IP=Enter phone IP address: 
)
if not exist .venv\Scripts\python.exe (
  echo Run run_backend.bat once to create the environment.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python yolo_phone_camera.py
