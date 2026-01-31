@echo off
REM Stop Community Forest Management System servers (Backend and Frontend)

echo ========================================
echo Stopping Backend and Frontend servers...
echo ========================================
echo.

REM Kill all uvicorn processes on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Killing process on port 8001 (PID: %%a)
    taskkill /F /PID %%a
)

REM Kill all node.js processes (frontend)
echo Stopping frontend server...
taskkill /F /IM node.exe 2>nul

echo.
echo Server stopped.
echo.
pause
