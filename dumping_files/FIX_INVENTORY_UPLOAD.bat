@echo off
echo ===============================================
echo FIX INVENTORY UPLOAD - Complete Restart
echo ===============================================
echo.

echo This will:
echo 1. Stop all Python and Node processes
echo 2. Clear Python cache
echo 3. Restart backend with CORS fix
echo 4. Restart frontend
echo.
pause

echo.
echo Step 1: Stopping all servers...
echo Killing Python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul

echo Killing Node processes...
taskkill /F /IM node.exe /T 2>nul

echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo Step 2: Clearing Python cache...
cd backend
for /r %%i in (*.pyc) do @del "%%i" 2>nul
for /d /r %%i in (__pycache__) do @rd /s /q "%%i" 2>nul
cd ..

echo.
echo Step 3: Starting Backend (Port 8001) with CORS fix...
start "Backend Server (Port 8001) - CORS FIXED" cmd /k "cd /d D:\forest_management && FORCE_RESTART_BACKEND.bat"

echo Waiting 5 seconds for backend to start...
timeout /t 5 /nobreak >nul

echo.
echo Step 4: Starting Frontend (Port 3000)...
start "Frontend Server (Port 3000)" cmd /k "cd /d D:\forest_management && start_frontend.bat"

echo.
echo ===============================================
echo Servers are starting in new windows!
echo.
echo WAIT 10 SECONDS, then test:
echo 1. Open: http://localhost:3000
echo 2. Login with: newuser@example.com
echo 3. Go to Inventory Upload
echo 4. Try uploading your CSV
echo.
echo The CORS error should be FIXED!
echo ===============================================
echo.
pause
