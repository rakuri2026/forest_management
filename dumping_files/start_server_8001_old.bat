@echo off
REM Start Community Forest Management System on port 8001

echo ========================================
echo Community Forest Management System
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Disable Python output buffering
set PYTHONUNBUFFERED=1

REM Start the server on port 8001
echo ========================================
echo Starting FastAPI server on port 8001...
echo API Documentation: http://localhost:8001/docs
echo Health Check: http://localhost:8001/health
echo ========================================
echo.

cd backend
..\venv\Scripts\python -u -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
cd ..
