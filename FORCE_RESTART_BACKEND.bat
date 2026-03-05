@echo off
title FORCE RESTART BACKEND - CLEAR ALL CACHE
cls
echo.
echo ========================================
echo  FORCE RESTART BACKEND (CLEAR CACHE)
echo ========================================
echo.

echo [1/5] Killing ALL Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo [OK] All Python processes killed
echo.

echo [2/5] Waiting 3 seconds for processes to fully stop...
timeout /t 3 /nobreak >nul
echo [OK] Wait complete
echo.

echo [3/5] Clearing Python bytecode cache (__pycache__)...
cd /d D:\forest_management\backend
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo [OK] Cache cleared
echo.

echo [4/5] Verifying tree_distribution.py has DBH threshold fixes...
findstr /C:"random.uniform(1.0, 3.9)" app\services\tree_distribution.py >nul
if errorlevel 1 (
    echo [ERROR] tree_distribution.py doesn't have DBH fix (3.9)!
    echo [ERROR] Code changes may not be saved properly!
    pause
    exit /b 1
) else (
    echo [OK] tree_distribution.py has DBH threshold fixes
)
echo.

echo [5/5] Starting Backend Server (Port 8001)...
start "Backend Server - Port 8001" cmd /k "..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo [OK] Backend server started in new window
echo.

echo ========================================
echo  RESTART COMPLETE!
echo ========================================
echo.
echo  Backend API:  http://localhost:8001
echo  API Docs:     http://localhost:8001/docs
echo.
echo  Now generate a new Tree Model and export to Excel:
echo  - regen_dbh column: values should be 1.0 to 3.9
echo  - sapling_dbh_cm column: values should be 4.0 to 9.9
echo  - pole_dbh_cm column: values should be 10.0 to 29.9
echo  - tree_dbh_cm column: values should be >= 30.0
echo.
echo ========================================
echo.
pause
