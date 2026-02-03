@echo off
REM Start Backend Server (Port 8001)

echo ========================================
echo Community Forest Management - Backend
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Disable Python output buffering
set PYTHONUNBUFFERED=1

REM Start the backend server on port 8001
echo ========================================
echo Starting Backend Server on Port 8001
echo API Documentation: http://localhost:8001/docs
echo Health Check: http://localhost:8001/health
echo ========================================
echo.

cd backend
..\venv\Scripts\python -u -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
cd ..
