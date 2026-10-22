@echo off
rem Deletes every account and every saved reef. Each device then starts as a brand-new player: the game asks
rem for a profile name (and, after clearing the game's data on the device, an age). Close start-server.bat first.
cd /d "%~dp0server"
set /p OK=This deletes ALL players and reefs. Type YES and press Enter to continue: 
if /i not "%OK%"=="YES" exit /b
python nemo_server.py --apk ..\nemo.apk --port 8080 --reset-all
pause
