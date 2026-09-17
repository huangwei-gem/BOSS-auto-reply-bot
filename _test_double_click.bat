@echo off
REM Simulate double-click: run start_bot.bat in a new window and wait
start "BOSS Bot Test" /wait cmd /c "start_bot.bat < nul 2>&1"
echo Exit code: %errorlevel%
pause
