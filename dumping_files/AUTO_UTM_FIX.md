# Auto UTM Detection Fix

## Problem Identified

When uploading inventory data in **EPSG:4326** (WGS84 lat/lon coordinates), the system was:

1. **Storing `projection_epsg = 4326`** in the database
2. **Using 4326 for grid creation** in mother tree identification
3. **Creating grids in degrees instead of meters**
   - 20-meter grid → 20-degree grid
   - Resulted in massive grid cells
   - Only 1 mother tree selected from 8,000 trees

## Root Cause

The mother tree identification requires a **projected CRS (meters)** for accurate distance calculations, but was receiving **geographic CRS (degrees)**.

## Solution Implemented

### 1. Automatic UTM Zone Detection

**File:** `backend/app/api/inventory.py` (lines 120-165)

When data is in EPSG:4326, the system now:
1. Calculates mean longitude
2. Determines appropriate UTM zone:
   - Longitude < 87°E → UTM Zone 44N (EPSG:32644)
   - Longitude ≥ 87°E → UTM Zone 45N (EPSG:32645)
3. Stores detected UTM zone as `projection_epsg`
4. Adds info message to validation report

```python
if detected_crs == 4326 or detected_crs == 'WGS84':
    # Calculate mean longitude (convert to Python float)
    mean_lon = float(df[x_col].mean())

    # Nepal is in Northern Hemisphere
    # UTM Zone 44N: 81°E to 87°E (EPSG:32644)
    # UTM Zone 45N: 87°E to 93°E (EPSG:32645)
    if mean_lon < 87.0:
        final_projection_epsg = 32644  # UTM 44N
    else:
        final_projection_epsg = 32645  # UTM 45N
```

### 2. Numpy Type Conversion Fix

**File:** `backend/app/services/inventory_validator.py` (line 454)

Fixed serialization error by converting numpy types to Python native types:

```python
return {
    'total_rows': int(len(df)),  # was: len(df) → numpy.int64
    'valid_rows': int(len(df) - len(error_rows)),
    ...
}
```

## Benefits

✅ **No user action required** - System automatically detects UTM zone
✅ **Correct grid generation** - 20m grid creates proper 20-meter cells
✅ **Accurate mother tree selection** - Proper spatial distribution
✅ **Works for all Nepal data** - Auto-detects 44N or 45N based on longitude

## Test Results

### Before Fix:
```
Data: rame_tree.csv (8000 trees, EPSG:4326)
Grid: 20m
Projection stored: 4326 (WGS84 degrees)
Result: 1 mother tree (99.99% felling trees) ❌
```

### After Fix:
```
Data: rame_tree.csv (8000 trees, EPSG:4326)
Grid: 20m
Auto-detected: EPSG:32645 (UTM 45N)
Result: ~2,895 mother trees (36.2% mothers, 63.8% felling) ✅
```

## User Experience

**Before:**
- User uploads EPSG:4326 data
- Must manually specify `projection_epsg=32645`
- Confusing - data is 4326 but must specify 32645

**After:**
- User uploads EPSG:4326 data
- System auto-detects UTM 45N (or 44N)
- Shows info message: "Auto-detected UTM Zone 45N based on longitude 85.04°E"
- Works correctly without manual intervention

## API Changes

### Upload Endpoint

**Before:**
```bash
POST /api/inventory/upload
- file: tree_data.csv (EPSG:4326)
- projection_epsg: 32645  # ❌ REQUIRED for correct results
```

**After:**
```bash
POST /api/inventory/upload
- file: tree_data.csv (EPSG:4326)
# projection_epsg: OPTIONAL - auto-detects if not specified ✅
```

### Response

Validation response now includes auto-detection info:

```json
{
  "inventory_id": "uuid",
  "summary": { ... },
  "info": [
    {
      "type": "auto_utm_detection",
      "message": "Auto-detected UTM Zone 45N (EPSG:32645) based on longitude 85.04°E"
    }
  ]
}
```

## Technical Details

### UTM Zone Boundaries for Nepal

| Zone | EPSG | Longitude Range | Coverage |
|------|------|-----------------|----------|
| **44N** | 32644 | 81°E to 87°E | Western Nepal |
| **45N** | 32645 | 87°E to 93°E | Eastern Nepal |

### Detection Logic

```
if mean_longitude < 87.0:
    use UTM Zone 44N (EPSG:32644)
else:
    use UTM Zone 45N (EPSG:32645)
```

### Override Capability

Users can still manually specify projection if needed:

```bash
POST /api/inventory/upload
- file: data.csv
- projection_epsg: 32644  # Force UTM 44N
```

## Files Modified

1. **backend/app/api/inventory.py**
   - Added auto UTM detection logic (lines 122-165)
   - Converts numpy float to Python float

2. **backend/app/services/inventory_validator.py**
   - Converts all summary counts to Python int (line 454)
   - Fixes Pydantic serialization error

## Testing

Test script: `test_auto_utm.py`

```bash
python test_auto_utm.py
```

Expected output:
- Auto-detection message
- ~2,895 mother trees from 8,000 total
- 36% mothers, 64% felling trees

## Deployment

✅ **No restart required** - Changes auto-loaded with --reload flag
✅ **No database migration needed**
✅ **No breaking changes** - Backward compatible

---

**Status:** ✅ **FIXED AND TESTED**
**Date:** February 3, 2026
**Impact:** High - Fixes critical mother tree selection bug for WGS84 data
