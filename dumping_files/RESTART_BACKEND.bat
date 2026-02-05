@echo off
REM Quick restart for backend server

echo ========================================
echo Restarting Backend Server
echo ========================================
echo.

REM Kill backend on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Stopping backend (PID: %%a)
    taskkill /F /PID %%a
)

echo.
echo Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo Starting backend server...
echo.

REM Start backend in new window
start "Backend Server (Port 8001)" cmd /k "cd /d D:\forest_management && start_backend.bat"

echo.
echo ========================================
echo Backend is restarting...
echo Wait 5-10 seconds for startup to complete
echo Then try: http://localhost:8001/docs
echo ========================================
echo.
pause
