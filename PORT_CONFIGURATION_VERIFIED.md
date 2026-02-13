# Port Configuration - VERIFIED & FIXED

## ✅ Correct Configuration

**Backend Server:**
- Port: **3001**
- URL: http://localhost:3001
- Docs: http://localhost:3001/docs
- Configured in: `start_backend.bat` line 4

**Frontend Server:**
- Port: **3000** (Vite dev server)
- URL: http://localhost:3000
- Configured in: `vite.config.ts` line 7

**Frontend API Calls:**
- Backend URL: `http://localhost:3001`
- Configured in: `frontend/src/services/api.ts` line 12

---

## 🔧 Issues Fixed

### Issue 1: Vite Proxy Misconfigured
**Before:**
```typescript
// vite.config.ts line 10
target: 'http://localhost:8001',  // ❌ WRONG
```

**After:**
```typescript
// vite.config.ts line 10
target: 'http://localhost:3001',  // ✅ CORRECT
```

### Issue 2: Misleading Comment in start_all.bat
**Before:**
```batch
start "Backend Server (Port 8001)" cmd /k ...  // ❌ Misleading
```

**After:**
```batch
start "Backend Server (Port 3001)" cmd /k ...  // ✅ Accurate
```

---

## How to Start Servers

### Option 1: Use start_all.bat (Recommended)

```batch
cd D:\forest_management
start_all.bat
```

This will:
1. Start backend on port **3001** (new window)
2. Wait 5 seconds
3. Start frontend on port **3000** (new window)

### Option 2: Start Manually

**Terminal 1 - Backend:**
```batch
cd D:\forest_management
start_backend.bat
```

**Terminal 2 - Frontend:**
```batch
cd D:\forest_management
start_frontend.bat
```

---

## Verification

After starting servers, verify they're running:

**1. Backend Health Check:**
```bash
curl http://localhost:3001/health
```
Expected: `{"status":"healthy", ...}`

**2. Backend API Docs:**
Open browser: http://localhost:3001/docs

**3. Frontend:**
Open browser: http://localhost:3000

**4. Check Processes (Windows):**
```batch
netstat -ano | findstr :3001
netstat -ano | findstr :3000
```

---

## Summary

✅ Backend: **Port 3001**
✅ Frontend: **Port 3000**
✅ All configuration files aligned
✅ start_all.bat uses correct ports
✅ Vite proxy fixed to point to 3001
✅ API service points to 3001

**Status:** Port configuration verified and corrected
**Date:** February 13, 2026
