@echo off
rem Deletes every saved reef (accounts are kept). Next time the game starts you get the starter reef
rem and the first quest again. Close start-server.bat first.
cd /d "%~dp0server"
set /p OK=This deletes your reef and everything in it. Type YES and press Enter to continue: 
if /i not "%OK%"=="YES" exit /b
python nemo_server.py --apk ..\nemo.apk --port 8080 --reset-worlds
pause
