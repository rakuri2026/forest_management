@echo off
REM Cleanup old/redundant batch files

echo ========================================
echo Cleaning up old batch files
echo ========================================
echo.

echo Moving obsolete batch files to dumping_files folder...
echo.

move /Y "start.bat" "dumping_files\start_old_port8000.bat" 2>nul
move /Y "start_server_8001.bat" "dumping_files\start_server_8001_old.bat" 2>nul
move /Y "restart_backend.bat" "dumping_files\restart_backend_old.bat" 2>nul
move /Y "RESTART_BACKEND_ONLY.bat" "dumping_files\RESTART_BACKEND_ONLY_old.bat" 2>nul
move /Y "RESTART_SERVERS_NOW.bat" "dumping_files\RESTART_SERVERS_NOW_old.bat" 2>nul
move /Y "stop_server.bat" "dumping_files\stop_server_old.bat" 2>nul
move /Y "start_old_backup.bat" "dumping_files\start_old_backup2.bat" 2>nul

echo.
echo ========================================
echo Cleanup complete!
echo ========================================
echo.
echo New batch files (in root folder):
echo   - start_backend.bat     (Start backend on port 8001)
echo   - start_frontend.bat    (Start frontend on port 3000)
echo   - start_all.bat         (Start both servers)
echo   - stop_all.bat          (Stop all servers)
echo   - create_backup.bat     (Create backup)
echo.
echo Old files moved to: dumping_files\
echo.
pause
