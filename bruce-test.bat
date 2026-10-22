@echo off
rem Starts the server with Bruce's visit running now (for testing; it normally comes some weekends).
cd /d "%~dp0server"
python nemo_server.py --apk ..\nemo.apk --port 8080 --event time_event_bruce
pause
