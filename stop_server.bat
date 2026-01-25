@echo off
REM Stop Community Forest Management System server

echo ========================================
echo Stopping FastAPI server...
echo ========================================
echo.

REM Kill all uvicorn processes on port 8000 and 8001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Killing process on port 8000 (PID: %%a)
    taskkill /F /PID %%a
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo Killing process on port 8001 (PID: %%a)
    taskkill /F /PID %%a
)

echo.
echo Server stopped.
echo.
pause
