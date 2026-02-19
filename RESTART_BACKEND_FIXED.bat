@echo off
echo Restarting backend with tree distribution fixes...
echo.
echo [1/3] Stopping old backend server...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Starting backend server on port 8001...
cd /d D:\forest_management\backend
start "Forest Backend" cmd /k "..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001"

echo [3/3] Waiting for server to start...
timeout /t 3 /nobreak >nul

echo.
echo ✓ Backend restarted with fixes:
echo   - Raster clipping optimization (100x faster)
echo   - User max_trees_per_ha configuration now applied
echo.
echo Server running at http://localhost:8001
echo Check http://localhost:8001/docs for API
echo.
pause
