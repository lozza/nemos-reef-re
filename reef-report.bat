@echo off
rem Shows what the server has saved about your fish and plant combinations.
cd /d "%~dp0"
python tools\reef_report.py > reef-report.txt
type reef-report.txt
echo.
echo Saved to reef-report.txt
pause
