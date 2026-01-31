@echo off
REM Restart only the backend server (keep frontend running)

echo ========================================
echo RESTARTING BACKEND SERVER
echo ========================================
echo.

REM Kill backend on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Killing backend on port 8001 (PID: %%a)
    taskkill /F /PID %%a
)

echo.
echo Waiting 2 seconds...
timeout /t 2 /nobreak

echo.
echo Starting backend server...
echo.

REM Start backend in new window
start "Backend Server (PORT 8001)" cmd /k "cd /d D:\forest_management && start_server_8001.bat"

echo.
echo ========================================
echo Backend server is starting...
echo Backend:  http://localhost:8001
echo ========================================
echo.
echo WAIT 10 seconds for backend to fully start!
echo.
echo Watch the backend window for:
echo "Application startup complete"
echo.
pause
