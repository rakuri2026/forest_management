@echo off
echo ========================================
echo  Restarting All Servers
echo ========================================
echo.

REM Kill existing backend (port 8001)
echo Stopping backend server (port 8001)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

REM Kill existing frontend (port 3000)
echo Stopping frontend server (port 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

timeout /t 2 /nobreak >nul

echo.
echo Starting servers...
echo.

REM Start backend in new window
start "Backend Server (Port 8001)" cmd /k "cd /d %~dp0 && start_backend.bat"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in new window
start "Frontend Server (Port 3000)" cmd /k "cd /d %~dp0 && start_frontend.bat"

echo.
echo ========================================
echo Both servers are starting!
echo Backend: http://localhost:8001/docs
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Check the new windows for server status
pause
