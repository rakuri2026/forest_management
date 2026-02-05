@echo off
echo ===============================================
echo FORCE RESTART BACKEND - Fixing CORS Issue
echo ===============================================
echo.

echo Step 1: Killing ALL Python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul

echo.
echo Step 2: Waiting for processes to close...
timeout /t 3 /nobreak >nul

echo.
echo Step 3: Clearing Python cache...
cd backend
for /r %%i in (*.pyc) do @del "%%i" 2>nul
for /d /r %%i in (__pycache__) do @rd /s /q "%%i" 2>nul
cd ..

echo.
echo Step 4: Starting backend with NEW CORS configuration...
echo.
echo ========================================
echo Backend Server Starting on Port 8001
echo CORS: Allowing localhost:3000
echo API Docs: http://localhost:8001/docs
echo ========================================
echo.

cd backend
..\venv\Scripts\python.exe -u -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

pause
