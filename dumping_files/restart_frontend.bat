@echo off
echo Stopping all Node.js processes...
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo Starting fresh frontend server...
cd frontend
start "Frontend Server" cmd /k "npm run dev"

echo.
echo Frontend server starting...
echo Please wait a few seconds, then access http://localhost:3000
