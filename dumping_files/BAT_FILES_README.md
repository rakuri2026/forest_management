# Batch Files Guide

## Essential Batch Files in Root Directory

### 1. `start_all.bat` (RECOMMENDED)
**Purpose:** Starts both backend and frontend servers in separate windows

**Usage:**
```bash
start_all.bat
```

**What it does:**
- Starts backend server on port 8001 in a new window
- Waits 3 seconds for backend to initialize
- Starts frontend server on port 3000 in a new window
- Both servers run independently

**Access URLs:**
- Backend API: http://localhost:8001
- Frontend App: http://localhost:3000
- API Docs: http://localhost:8001/docs

---

### 2. `start_server_8001.bat`
**Purpose:** Starts only the backend FastAPI server

**Usage:**
```bash
start_server_8001.bat
```

**What it does:**
- Activates Python virtual environment
- Starts FastAPI server on port 8001
- Enables hot-reload for development

**Access URLs:**
- API: http://localhost:8001
- Docs: http://localhost:8001/docs
- Health: http://localhost:8001/health

---

### 3. `start_frontend.bat`
**Purpose:** Starts only the frontend development server

**Usage:**
```bash
start_frontend.bat
```

**What it does:**
- Changes to frontend directory
- Runs `npm run dev`
- Starts Vite development server

**Access URLs:**
- Frontend: http://localhost:3000

---

### 4. `stop_server.bat`
**Purpose:** Stops all running backend and frontend servers

**Usage:**
```bash
stop_server.bat
```

**What it does:**
- Finds and kills all processes on port 8001 (backend)
- Kills all node.js processes (frontend)
- Cleans up running servers completely

---

## Quick Start Guide

### First Time Setup
1. Ensure Python virtual environment exists: `python -m venv venv`
2. Install backend dependencies: `cd backend && pip install -r requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`

### Daily Development Workflow

**Option A: Run Everything**
```bash
start_all.bat
```
This opens two command windows - one for backend, one for frontend.

**Option B: Run Separately**
```bash
# Terminal 1: Backend only
start_server_8001.bat

# Terminal 2: Frontend only
start_frontend.bat
```

**Stop All Servers**
```bash
stop_server.bat
```

---

## Troubleshooting

### Backend won't start
1. Check if port 8001 is in use: `netstat -ano | findstr :8001`
2. Stop any existing servers: `stop_server.bat`
3. Verify virtual environment: `venv\Scripts\activate`
4. Check database connection: `psql -U postgres -d cf_db`

### Frontend won't start
1. Check if port 3000 is in use: `netstat -ano | findstr :3000`
2. Kill node processes: `taskkill /F /IM node.exe`
3. Reinstall dependencies: `cd frontend && npm install`
4. Clear node cache: `npm cache clean --force`

### Port conflicts
If port 8001 or 3000 is already in use:
- Backend: Edit `start_server_8001.bat` and change `--port 8001` to another port
- Frontend: Edit `frontend/vite.config.ts` to change the port

---

## Backup/Old Files

Located in `dumping_files/` directory:
- `start_server_8004.bat` - Old backend on port 8004
- `restart_frontend.bat` - Force restart frontend
- `start_old_backup.bat` - Original start.bat (port 8000)

These files are kept for reference but not needed for regular operation.

---

## File Locations

```
D:\forest_management\
├── start_all.bat              ← Start everything (RECOMMENDED)
├── start_server_8001.bat      ← Backend only
├── start_frontend.bat         ← Frontend only
├── stop_server.bat            ← Stop all servers
├── backend/
│   └── app/
│       └── main.py
├── frontend/
│   └── src/
└── dumping_files/
    ├── start_server_8004.bat
    ├── restart_frontend.bat
    └── start_old_backup.bat
```

---

## Summary

**For most users:** Just run `start_all.bat` and you're good to go!

**Active Ports:**
- 8001: Backend API (FastAPI)
- 3000: Frontend (Vite/React)

**Stop Everything:**
Run `stop_server.bat` when done.
