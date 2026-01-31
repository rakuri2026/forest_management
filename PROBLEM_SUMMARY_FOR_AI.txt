# Critical Bug: Features East/South/West Always Empty

## Problem Statement
A Python FastAPI backend analyzes forest boundaries and should return nearby features in 4 directions (North, East, South, West). **Only "Features North" populates with data. Features East/South/West are always `None` in the database.**

## What We Know FOR CERTAIN

### 1. The SQL Queries Work Perfectly
When tested directly with the same geometry, the queries return features in ALL directions:
```
NORTH: 7 features ✅
EAST: 11 features ✅
SOUTH: 8 features ✅
WEST: 14 features ✅
```

### 2. The Function Works in Isolation
When `analyze_nearby_features()` is called standalone (outside the upload flow), it returns all 4 directions correctly:
```python
result_features = {
    'features_north': 'River/Strem Flow Line, Gothdanda, ...',
    'features_east': 'River/Strem Flow Line, Chaughada, ...',
    'features_south': 'River/Strem Flow Line, Kyampadanda, ...',
    'features_west': 'Karra Khola, River/Strem Flow Line, ...'
}
```

### 3. Database Shows Only North is Saved
```
Features North: "River/Strem Flow Line, Gothdanda, Kyampadanda, Phikrepakha, Pipalechok, unclassified"
Features East: None
Features South: None
Features West: None
```

### 4. NO Console Logs Appear During Upload
Despite adding print statements with `flush=True`, `PYTHONUNBUFFERED=1`, and `-u` flag, **ZERO debug output appears in the console during file upload**. The console only shows application startup, then nothing when files are uploaded.

## Code Structure

### Function: `analyze_nearby_features(geometry_wkt: str, db: Session)`
**Location:** `D:\forest_management\backend\app\services\analysis.py` (lines 1408-1519)

**How it works:**
1. Loops through 9 different database tables (roads, rivers, POI, etc.)
2. For each direction (north, east, south, west):
   - Queries each table for nearby features within 100m
   - Uses ST_Azimuth to calculate bearing angles
   - Filters by angle ranges (North: 315-45°, East: 45-135°, etc.)
   - Appends feature names to `features_list`
3. Stores result: `result_features[f"features_{direction_name}"] = features_str`
4. Returns dict with all 4 keys

**Called from:** `analyze_block_geometry()` at line 297

### Upload Flow
1. User uploads file → `POST /api/forests/upload` (forests.py:211)
2. Backend calls `analyze_forest_boundary(calc_id, db)` (forests.py:295)
3. For each block, calls `analyze_block_geometry()` (analysis.py:46)
4. Block analysis calls `analyze_nearby_features()` (analysis.py:297)
5. Results merged via `block_results.update(nearby_results)` (analysis.py:298)
6. Saved to database via SQL UPDATE (forests.py:303)

## What We've Tried (All Failed)

### 1. ❌ Unicode Encoding Fix
- **Issue:** Thought print() was crashing on Nepali characters
- **Fix:** Added try/except around print statements
- **Result:** Standalone test works, but real upload still broken

### 2. ❌ Transaction Rollback Fixes
- **Issue:** Thought failed transactions were contaminating subsequent queries
- **Fix:** Added `db.rollback()` in exception handlers
- **Result:** No change

### 3. ❌ Python Output Buffering
- **Issue:** Thought print statements were buffered
- **Fixes Applied:**
  - Added `-u` flag to python command
  - Set `PYTHONUNBUFFERED=1` environment variable
  - Added `flush=True` to all print statements
- **Result:** Still NO console output during uploads

### 4. ❌ GeoJSON to WKT Conversion Error
- **Issue:** Suspected geometry conversion failures
- **Fix:** Added rollback before raising exception
- **Result:** No improvement

## Key Mystery

**Why does the function work perfectly in isolation but fail during actual uploads?**

The standalone test uses the EXACT same:
- Database session
- WKT geometry string
- Function code
- Database credentials

Yet it returns all 4 directions. But during real uploads, only North is saved.

## Critical Questions to Answer

1. **Why no console logs?** Even with unbuffered output and flush=True, print statements during upload don't appear. This suggests:
   - The code path isn't executing at all?
   - Output is redirected somewhere else?
   - Uvicorn/FastAPI is capturing stdout?

2. **Where is the data lost?** Between these points:
   - `analyze_nearby_features()` returns dict (works in test)
   - `block_results.update(nearby_results)` merges it
   - Data saved to database (only North appears)

3. **Is there a silent exception?** Could an exception be raised after North but before East/South/West, and being caught/swallowed somewhere?

## Environment Details

- **OS:** Windows 11
- **Python:** 3.14
- **Framework:** FastAPI with Uvicorn (--reload mode)
- **Database:** PostgreSQL 15 with PostGIS
- **ORM:** SQLAlchemy 2.0.45

## Files to Examine

1. `D:\forest_management\backend\app\services\analysis.py` - Main analysis logic
2. `D:\forest_management\backend\app\api\forests.py` - Upload endpoint
3. `D:\forest_management\start_server_8001.bat` - Server startup script

## Request for Help

**What could cause a function to work perfectly in isolation but only return partial data (1 of 4 dictionary keys) when called during the actual application flow, with NO error messages and NO console output?**

Specific help needed:
1. How to debug when print statements don't appear (even with unbuffered output)?
2. What could cause only the FIRST iteration of a loop to save, but not subsequent ones?
3. How to trace where dictionary values are being lost between function return and database save?

## Test Commands

Run standalone test (works):
```bash
cd D:\forest_management
.\venv\Scripts\python.exe test_features_direct.py
```

Check database after upload:
```bash
cd D:\forest_management
.\venv\Scripts\python.exe check_db.py
```

## Expected vs Actual

**Expected in database:**
```json
{
  "features_north": "River/Strem Flow Line, ...",
  "features_east": "River/Strem Flow Line, Chaughada, ...",
  "features_south": "River/Strem Flow Line, ...",
  "features_west": "Karra Khola, ..."
}
```

**Actual in database:**
```json
{
  "features_north": "River/Strem Flow Line, ...",
  "features_east": null,
  "features_south": null,
  "features_west": null
}
```
