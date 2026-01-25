@echo off
REM Start both Backend and Frontend servers

echo ========================================
echo Community Forest Management System
echo Starting Backend and Frontend...
echo ========================================
echo.

REM Start backend in new window
start "Backend Server" cmd /k "cd /d D:\forest_management && start_server_8001.bat"

REM Wait a bit for backend to start
timeout /t 3 /nobreak

REM Start frontend in new window
start "Frontend Server" cmd /k "cd /d D:\forest_management && start_frontend.bat"

echo.
echo ========================================
echo Servers are starting...
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to close this window (servers will continue running)
pause
