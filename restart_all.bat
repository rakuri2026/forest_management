@echo off
REM ============================================================
REM Community Forest Management System - Restart All Servers
REM ============================================================
REM Stops all servers and restarts them
REM ============================================================

title Community Forest Management - Restarting Servers

cls
echo.
echo ========================================
echo  Community Forest Management System
echo  Restarting All Servers...
echo ========================================
echo.

REM STEP 1: Stop all servers
echo ========================================
echo  STEP 1/2: Stopping All Servers
echo ========================================
echo.

echo [1/3] Stopping Backend Server...
taskkill /F /IM python.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] No backend processes running
) else (
    echo [OK] Backend stopped
)
echo.

echo [2/3] Stopping Frontend Server...
taskkill /F /IM node.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] No frontend processes running
) else (
    echo [OK] Frontend stopped
)
echo.

echo [3/3] Closing server windows...
taskkill /FI "WINDOWTITLE eq Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend*" /F >nul 2>&1
echo [OK] Server windows closed
echo.

echo [OK] All servers stopped
echo.
echo [INFO] Waiting 3 seconds before restart...
timeout /t 3 /nobreak >nul
echo.

REM STEP 2: Start all servers
echo ========================================
echo  STEP 2/2: Starting All Servers
echo ========================================
echo.

echo [1/3] Checking PostgreSQL database...
sc query postgresql-x64-15 2>nul | find "RUNNING" >nul
if errorlevel 1 (
    echo [WARNING] PostgreSQL is not running!
    echo [INFO] Starting PostgreSQL...
    net start postgresql-x64-15 2>nul
    timeout /t 2 /nobreak >nul
)
echo [OK] PostgreSQL is running
echo.

echo [2/3] Starting Backend Server (Port 8001)...
start "Backend Server - Port 8001" cmd /k "cd /d D:\forest_management\backend && ..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo [OK] Backend server window opened
echo.

echo [INFO] Waiting for backend to initialize (5 seconds)...
timeout /t 5 /nobreak >nul
echo.

echo [3/3] Starting Frontend Server (Port 3001)...
start "Frontend Server - Port 3001" cmd /k "cd /d D:\forest_management\frontend && npm run dev"
echo [OK] Frontend server window opened
echo.

echo ========================================
echo  Restart Complete!
echo ========================================
echo.
echo  Backend API:  http://localhost:8001
echo  API Docs:     http://localhost:8001/docs
echo  Frontend:     http://localhost:3001
echo.
echo  Quick Login:  Click "Quick Login" button
echo  Or use:       demo@forest.com / Demo1234
echo.
echo ========================================
echo.
echo.
pause
