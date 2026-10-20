@echo off
rem Makes nemo-private.apk, a copy of the game that talks to your PC.
cd /d "%~dp0"
if not exist "nemo.apk" (
  echo Could not find nemo.apk next to this file. See README step 3.
  pause
  exit /b 1
)
set /p IP=Type your PC's IPv4 address (see README step 5) and press Enter: 
set EXTRA=
rem 10.0.2.2 is how the Android Studio emulator reaches this PC; it needs a graphics workaround.
if "%IP%"=="10.0.2.2" set EXTRA=--emulator
python patcher\patch_apk.py nemo.apk http://%IP%:8080 --debug-log %EXTRA%
pause
