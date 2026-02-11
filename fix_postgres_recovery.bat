@echo off
echo ========================================
echo PostgreSQL Recovery Mode Fix Script
echo ========================================
echo.

echo Step 1: Checking PostgreSQL service status...
echo.
sc query postgresql-x64-15 | find "STATE"
if %errorlevel% neq 0 (
    echo Service not found with name postgresql-x64-15
    echo Trying alternative names...
    sc query | find "postgresql" /i
)
echo.

echo Step 2: Stopping PostgreSQL service...
echo.
net stop postgresql-x64-15 2>nul
if %errorlevel% equ 0 (
    echo PostgreSQL service stopped successfully
) else (
    echo Failed to stop service, trying alternative name...
    net stop postgresql-x64-14 2>nul
)
echo.
echo Waiting 10 seconds for clean shutdown...
timeout /t 10 /nobreak
echo.

echo Step 3: Checking for recovery signal files...
echo.
set PGDATA=C:\Program Files\PostgreSQL\15\data
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

echo Step 5: Starting PostgreSQL service...
echo.
net start postgresql-x64-15
if %errorlevel% equ 0 (
    echo PostgreSQL service started successfully
) else (
    echo Failed to start service, trying alternative name...
    net start postgresql-x64-14
)
echo.

echo Step 6: Waiting for PostgreSQL to initialize...
timeout /t 15 /nobreak
echo.

echo Step 7: Testing database connection...
echo.
"C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -d cf_db -c "SELECT 'Database is working!' as status;" 2>nul
if %errorlevel% equ 0 (
    echo SUCCESS: Database connection working!
) else (
    echo WARNING: Database connection still has issues
    echo Check logs at: %PGDATA%\log\
)
echo.

echo ========================================
echo Script completed!
echo ========================================
echo.
echo If still having issues:
echo 1. Check logs: %PGDATA%\log\
echo 2. Verify PostgreSQL version matches paths above
echo 3. Run this script as Administrator
echo.
pause
