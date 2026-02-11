@echo off
echo ========================================
echo PostgreSQL 18 Recovery Mode Fix Script
echo ========================================
echo.

echo Step 1: Checking PostgreSQL 18 service status...
echo.
sc query postgresql-x64-18 | find "STATE"
echo.

echo Step 2: Stopping PostgreSQL 18 service...
echo.
net stop postgresql-x64-18
if %errorlevel% equ 0 (
    echo PostgreSQL service stopped successfully
) else (
    echo Warning: Service may not be running or already stopped
)
echo.
echo Waiting 10 seconds for clean shutdown...
timeout /t 10 /nobreak
echo.

echo Step 3: Checking for recovery signal files...
echo.
set PGDATA=C:\Program Files\PostgreSQL\18\data
if not exist "%PGDATA%" (
    echo PostgreSQL 18 data directory not found at default location
    echo Checking alternative location...
    set PGDATA=C:\Program Files\PostgreSQL\data
)

if exist "%PGDATA%\recovery.signal" (
    echo Found recovery.signal - This is causing recovery mode!
    echo Deleting recovery.signal...
    del "%PGDATA%\recovery.signal"
    echo recovery.signal deleted
) else (
    echo recovery.signal not found
)

if exist "%PGDATA%\standby.signal" (
    echo Found standby.signal - This is causing recovery mode!
    echo Deleting standby.signal...
    del "%PGDATA%\standby.signal"
    echo standby.signal deleted
) else (
    echo standby.signal not found
)
echo.

echo Step 4: Checking postmaster.pid...
echo.
if exist "%PGDATA%\postmaster.pid" (
    echo Found stale postmaster.pid - This can cause issues!
    echo Deleting postmaster.pid...
    del "%PGDATA%\postmaster.pid"
    echo postmaster.pid deleted
) else (
    echo postmaster.pid not found (this is good)
)
echo.

echo Step 5: Starting PostgreSQL 18 service...
echo.
net start postgresql-x64-18
if %errorlevel% equ 0 (
    echo PostgreSQL service started successfully
) else (
    echo ERROR: Failed to start PostgreSQL service
    echo Check Windows Event Viewer for details
)
echo.

echo Step 6: Waiting for PostgreSQL to initialize...
timeout /t 15 /nobreak
echo.

echo Step 7: Testing database connection...
echo.
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cf_db -c "SELECT 'Database is working!' as status;"
if %errorlevel% equ 0 (
    echo SUCCESS: Database connection working!
) else (
    echo WARNING: Database connection still has issues
    echo Trying alternative psql location...
    psql -U postgres -d cf_db -c "SELECT 'Database is working!' as status;"
)
echo.

echo ========================================
echo Script completed!
echo ========================================
echo.
echo Next steps:
echo 1. If successful, restart your backend server
echo 2. If still failing, check logs at: %PGDATA%\log\
echo 3. Share the latest log file for more help
echo.
pause
