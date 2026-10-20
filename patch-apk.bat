@echo off
rem Makes nemo-private.apk, a copy of the game that talks to your PC.
cd /d "%~dp0"
if not exist "nemo.apk" (
  echo Could not find nemo.apk next to this file. See README step 3.
  pause
  exit /b 1
)
set /p IP=Type your PC's IPv4 address (see README step 5) and press Enter: 
python patcher\patch_apk.py nemo.apk http://%IP%:8080 --debug-log
pause
