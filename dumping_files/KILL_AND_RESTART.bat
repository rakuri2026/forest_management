@echo off
echo Killing all Python and Node processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul

echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo Starting Backend Server...
cd /d D:\forest_management
start "Backend (Port 8001) - FIXED" cmd /k "cd /d D:\forest_management\backend && ..\venv\Scripts\python -u -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

echo Waiting 5 seconds for backend...
timeout /t 5 /nobreak >nul

echo Starting Frontend Server...
start "Frontend (Port 3000)" cmd /k "cd /d D:\forest_management\frontend && npm run dev"

echo.
echo ==============================================
echo  SERVERS STARTING IN NEW WINDOWS
echo ==============================================
echo.
echo Backend: http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Wait 10 seconds, then test upload in browser!
echo.
pause
