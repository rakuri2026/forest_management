@echo off
REM Complete fresh start - no reload, clean slate

echo ===============================================
echo FRESH START - Complete Reset
echo ===============================================
echo.

echo Step 1: Killing ALL Python processes...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo Step 2: Deleting ALL Python cache...
cd backend
for /r %%i in (*.pyc) do @del "%%i" 2>nul
for /d /r %%i in (__pycache__) do @rd /s /q "%%i" 2>nul
cd ..

echo Step 3: Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo Step 4: Starting server WITHOUT auto-reload...
echo This will use a clean Python instance
echo.

cd backend
..\venv\Scripts\python.exe -u -m uvicorn app.main:app --host 0.0.0.0 --port 8001

pause
