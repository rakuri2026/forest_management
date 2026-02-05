@echo off
REM Force complete restart with cache clearing

echo ========================================
echo FORCE RESTART - Clearing all caches
echo ========================================
echo.

echo Step 1: Killing all Python and Node processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul

echo.
echo Step 2: Clearing Python cache...
cd backend
for /r %%i in (*.pyc) do del "%%i" 2>nul
for /d /r %%i in (__pycache__) do rd /s /q "%%i" 2>nul
cd ..

echo.
echo Step 3: Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo Step 4: Starting backend fresh...
start "Backend Server (Port 8001)" cmd /k "cd /d D:\forest_management && start_backend.bat"

echo.
echo ========================================
echo Server restarting...
echo Wait 10 seconds, then try:
echo   http://localhost:8001/api/species/all
echo ========================================
echo.
pause
