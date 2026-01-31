@echo off
REM Quick restart script to apply fixes

echo ========================================
echo STOPPING ALL SERVERS
echo ========================================
echo.

REM Kill backend on port 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Killing backend on port 8001 (PID: %%a)
    taskkill /F /PID %%a
)

REM Kill all node.js (frontend)
echo Stopping frontend server...
taskkill /F /IM node.exe 2>nul

echo.
echo Waiting 3 seconds...
timeout /t 3 /nobreak

echo ========================================
echo STARTING SERVERS WITH FIXES
echo ========================================
echo.

REM Start backend in new window
start "Backend Server (PORT 8001)" cmd /k "cd /d D:\forest_management && start_server_8001.bat"

REM Wait for backend to start
echo Waiting 5 seconds for backend to start...
timeout /t 5 /nobreak

REM Start frontend in new window
start "Frontend Server (PORT 3000)" cmd /k "cd /d D:\forest_management && start_frontend.bat"

echo.
echo ========================================
echo SERVERS ARE STARTING...
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo WAIT 15-20 SECONDS before uploading!
echo.
echo Backend window should show: "Application startup complete"
echo Frontend window should show: "Local: http://localhost:3000"
echo.
pause
