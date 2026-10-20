@echo off
rem Starts the Nemo's Reef server. Keep this window open while playing.
cd /d "%~dp0server"
if not exist "..\nemo.apk" (
  echo Could not find nemo.apk next to this file. See README step 3.
  pause
  exit /b 1
)
python nemo_server.py --apk ..\nemo.apk --port 8080
pause
