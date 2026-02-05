# Batch Files Guide

## Quick Reference

### Main Batch Files (Use These)

| File | Purpose | Port |
|------|---------|------|
| `start_backend.bat` | Start backend server only | 8001 |
| `start_frontend.bat` | Start frontend server only | 3000 |
| `start_all.bat` | Start both servers together | 8001 & 3000 |
| `stop_all.bat` | Stop all running servers | - |
| `create_backup.bat` | Create project backup | - |

### Usage Examples

#### Starting the Full System
```batch
start_all.bat
```
This will:
1. Start backend on http://localhost:8001
2. Start frontend on http://localhost:3000
3. Open both in separate windows

#### Starting Only Backend (for API development/testing)
```batch
start_backend.bat
```
- API Docs: http://localhost:8001/docs
- Health Check: http://localhost:8001/health

#### Starting Only Frontend (when backend is already running)
```batch
start_frontend.bat
```
- Frontend: http://localhost:3000

#### Stopping Everything
```batch
stop_all.bat
```
Kills all backend (port 8001) and frontend (node.js) processes.

## Important Notes

### Default Port: 8001
- Backend runs on **port 8001** (not 8000)
- This is documented in CLAUDE.md
- Port 8000 is used by the old F:\CF_application

### Cleanup Performed
Old/redundant batch files have been moved to `dumping_files/`:
- ~~start.bat~~ (used wrong port 8000)
- ~~start_server_8001.bat~~ (renamed to start_backend.bat)
- ~~restart_backend.bat~~ (duplicate functionality)
- ~~RESTART_BACKEND_ONLY.bat~~ (duplicate functionality)
- ~~RESTART_SERVERS_NOW.bat~~ (duplicate of start_all.bat)
- ~~stop_server.bat~~ (renamed to stop_all.bat)

### Why These Names?

**Clear and Descriptive:**
- `start_backend` - Obvious what it starts
- `start_frontend` - Obvious what it starts
- `start_all` - Obvious it starts everything
- `stop_all` - Obvious it stops everything

**No Port Numbers in Names:**
- Port is configured in the script
- Names remain valid even if ports change
- Cleaner file listing

## Troubleshooting

### Port Already in Use
If you get "port already in use" error:
1. Run `stop_all.bat` first
2. Wait 5 seconds
3. Run the start script again

### Backend Not Starting
Check:
1. Virtual environment exists: `venv\` folder present?
2. Dependencies installed: run `venv\Scripts\pip list`
3. Database running: try connecting with psql

### Frontend Not Starting
Check:
1. Node modules installed: `frontend\node_modules\` exists?
2. If not: `cd frontend && npm install`

## Advanced Usage

### Running Cleanup Script
To move old batch files to dumping_files:
```batch
cleanup_old_batch_files.bat
```

### Manual Server Control

**Start Backend Manually:**
```batch
venv\Scripts\activate
cd backend
..\venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Start Frontend Manually:**
```batch
cd frontend
npm run dev
```

**Check What's Running on Port 8001:**
```batch
netstat -aon | findstr ":8001"
```

**Kill Specific Process by PID:**
```batch
taskkill /F /PID <pid_number>
```

## File History

- **2026-02-02**: Cleaned up redundant batch files, created clear naming structure
- **2026-01-28**: Added frontend support
- **2026-01-21**: Initial project setup

---

For more information, see:
- CLAUDE.md - Full project documentation
- SETUP.md - Installation guide
- README.md - Project overview
