@echo off
echo ========================================
echo  Restarting Backend Server (Port 8001)
echo ========================================
echo.

REM Kill any existing Python/Uvicorn processes on port 8001
echo Stopping existing server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak >nul

echo.
echo Starting backend server...
cd /d "%~dp0backend"
start "Backend Server" cmd /k "..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

echo.
echo Backend server is starting...
echo Check the new window for server status
echo.
pause
