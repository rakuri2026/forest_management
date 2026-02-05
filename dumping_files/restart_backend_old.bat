@echo off
echo Stopping any running servers...
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>nul
timeout /t 2 /nobreak >nul

echo Starting backend server on port 8001...
cd D:\forest_management\backend
start "Forest Backend" cmd /k "..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001"

echo.
echo Backend server starting on http://localhost:8001
echo API Docs: http://localhost:8001/docs
echo.
pause
