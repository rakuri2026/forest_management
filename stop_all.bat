@echo off
REM Stop Both Backend and Frontend Servers

echo ========================================
echo Stopping Backend and Frontend Servers
echo ========================================
echo.

REM Kill backend on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Killing backend on port 8001 (PID: %%a)
    taskkill /F /PID %%a
)

REM Kill frontend (node.js)
echo Stopping frontend server...
taskkill /F /IM node.exe 2>nul

echo.
echo All servers stopped.
echo.
pause
