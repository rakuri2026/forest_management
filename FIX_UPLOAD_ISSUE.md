# Fix for Upload Analysis Issue

## Problem Found

The backend server was not properly using the Python virtual environment, causing import errors for `shapefile` and `geojson` modules. This caused uploads to get stuck at "PROCESSING" status.

## Solution Applied

1. ✅ Added missing packages to `requirements.txt` (pyshp, geojson)
2. ✅ Updated `start_server_8001.bat` to explicitly use venv's uvicorn
3. ✅ Fixed CORS configuration to use port 8001

## Steps to Fix (YOU NEED TO DO THIS)

### Step 1: Stop All Servers

Open PowerShell in `D:\forest_management`:

```powershell
cd D:\forest_management
.\stop_server.bat
```

Wait 5 seconds, then verify all servers are stopped.

### Step 2: Start Servers with Fixed Configuration

```powershell
.\start_all.bat
```

Two windows will open:
- Backend Server (port 8001) - **WAIT for it to show "Application startup complete"**
- Frontend Server (port 3000) - **WAIT for it to show URL**

⏰ **Wait at least 15-20 seconds** for both servers to fully start.

### Step 3: Test Upload

1. Open browser: **http://localhost:3000**
2. Login with your credentials
3. Go to "Upload" page
4. Upload a NEW file (don't reuse old stuck uploads)
5. Fill in forest name and block name
6. Click Upload

### Step 4: Verify Analysis

After upload completes (may take 1-2 minutes for 5 blocks):

1. Go to "My Uploads" page
2. Click on your new upload
3. You should see ALL 16 parameters filled:
   - ✅ Total Area
   - ✅ Extent (N/S/E/W)
   - ✅ Elevation
   - ✅ Slope
   - ✅ Aspect
   - ✅ Canopy Structure
   - ✅ Above Ground Biomass
   - ✅ Carbon Stock
   - ✅ Forest Health
   - ✅ Forest Type
   - ✅ Land Cover
   - ✅ Forest Loss
   - ✅ Forest Gain
   - ✅ Fire Loss
   - ✅ Temperature
   - ✅ Precipitation

## What Was Wrong?

The backend server was running but couldn't import required modules:
- `import shapefile` → Failed
- `import geojson` → Failed

This caused the file processor to crash silently, leaving uploads stuck at "PROCESSING" status.

## What Changed?

**File: `start_server_8001.bat`**
- OLD: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`
- NEW: `..\venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`

This ensures the backend uses the virtual environment's Python packages.

**File: `backend/app/core/config.py`**
- OLD: `CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"`
- NEW: `CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8001"`

This allows the frontend to communicate with backend on the correct port.

## Troubleshooting

### If upload still gets stuck:

1. Check backend server window for error messages
2. Verify the backend shows: `"Application startup complete"`
3. Try a different file format (KML, GeoJSON, or Shapefile ZIP)
4. Check database:
   ```sql
   psql -U postgres -d cf_db
   SELECT forest_name, status, error_message FROM calculations ORDER BY created_at DESC LIMIT 5;
   ```

### If you see errors about missing modules:

Run this in PowerShell:
```powershell
cd D:\forest_management
.\venv\Scripts\pip install -r backend\requirements.txt
```

Then restart servers.

---

**Once fixed, all new uploads should complete successfully with full analysis results!**
