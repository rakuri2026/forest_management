@echo off
REM Start Community Forest Management System

echo ========================================
echo Community Forest Management System
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
echo.

REM Check if dependencies are installed
echo Checking dependencies...
pip list | findstr fastapi > nul
if errorlevel 1 (
    echo Installing dependencies...
    cd backend
    pip install -r requirements.txt
    cd ..
    echo.
)

REM Check database migration status
echo Checking database migrations...
cd backend
alembic current
if errorlevel 1 (
    echo Running database migrations...
    alembic upgrade head
    echo.
)

REM Start the server
echo ========================================
echo Starting FastAPI server...
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health
echo ========================================
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd ..
