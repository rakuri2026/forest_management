@echo off
echo Starting Backend Server...
cd /d %~dp0backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001
