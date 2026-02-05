@echo off
REM Start Both Backend and Frontend Servers

echo ========================================
echo Community Forest Management System
echo Starting Backend and Frontend...
echo ========================================
echo.

REM Start backend in new window
start "Backend Server (Port 8001)" cmd /k "cd /d D:\forest_management && start_backend.bat"

REM Wait for backend to start
timeout /t 5 /nobreak

REM Start frontend in new window
start "Frontend Server (Port 3000)" cmd /k "cd /d D:\forest_management && start_frontend.bat"

echo.
echo ========================================
echo Servers are starting...
echo Backend:  http://localhost:8001/docs
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to close this window (servers will continue running)
pause
