@echo off
REM Create local backup of forest_management project
REM Excludes: venv, node_modules, .git, __pycache__, uploads, exports

echo ========================================
echo Creating Local Backup - 2026-02-05
echo ========================================
echo.

set BACKUP_DIR=D:\forest_management_backup_2026-02-05
set SOURCE_DIR=D:\forest_management

echo Creating backup directory...
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo.
echo Copying files (this may take a few minutes)...
echo Excluding: venv, node_modules, .git, __pycache__, uploads, exports
echo.

xcopy "%SOURCE_DIR%" "%BACKUP_DIR%" /E /I /H /Y /EXCLUDE:%SOURCE_DIR%\backup_exclude.txt

echo.
echo ========================================
echo Backup Complete!
echo ========================================
echo Location: %BACKUP_DIR%
echo.
echo To restore from this backup:
echo 1. Delete D:\forest_management
echo 2. Rename D:\forest_management_backup_2026-02-05 to D:\forest_management
echo 3. Recreate venv: python -m venv venv
echo 4. Install packages: .\venv\Scripts\pip install -r backend\requirements.txt
echo 5. Install frontend: cd frontend && npm install
echo.
pause
