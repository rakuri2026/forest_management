@echo off
REM Start Community Forest Management System on port 8004

echo ========================================
echo Community Forest Management System
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Start the server on port 8004
echo ========================================
echo Starting FastAPI server on port 8004...
echo API Documentation: http://localhost:8004/docs
echo Health Check: http://localhost:8004/health
echo ========================================
echo.

cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
cd ..
