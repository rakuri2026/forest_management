# DBH Threshold Fix - Complete Summary

**Date:** 2026-03-05
**Issue:** `regen_dbh` and `sapling_dbh_cm` columns had incorrect DBH ranges in tree model exports

## Problem Description

When exporting tree models to Excel/GPKG:
- `regen_dbh` column was receiving values from 1.0 to 10.0 cm (WRONG)
- `sapling_dbh_cm` column was receiving values from 10.0 to 20.0 cm (WRONG)

**Expected behavior:**
- `regen_dbh` column should only have values 1.0 to 3.9 cm
- `sapling_dbh_cm` column should only have values 4.0 to 9.9 cm

## Root Causes Found

### 1. Incorrect Classification Thresholds (Lines 890-924, 1070-1103)
The `export_to_gpkg()` and `export_to_excel()` functions classified:
- Regeneration: `if dbh < 10` (WRONG - should be `< 4`)
- Sapling: `elif dbh < 20` (WRONG - should be `< 10`)

### 2. Incorrect DBH Generation (Lines 755, 782)
The `generate_regeneration_entries()` function generated:
- Regeneration: `random.uniform(1.0, 4.0)` (WRONG - could generate 4.0)
- Sapling: `random.uniform(4.0, 10.0)` (WRONG - could generate 10.0)

## All Fixes Applied

### Fix 1: export_to_gpkg() Classification (Line ~890)
```python
# BEFORE:
if dbh < 10:
    # Regeneration
    record['regen_dbh'] = dbh
elif dbh < 20:
    # Sapling
    record['sapling_dbh_cm'] = dbh

# AFTER:
if dbh < 4:
    # Regeneration (1-3.99 cm DBH)
    record['regen_dbh'] = dbh
elif dbh < 10:
    # Sapling (4-9.99 cm DBH)
    record['sapling_dbh_cm'] = dbh
elif dbh < 20:
    # Small Pole (10-19.99 cm DBH)
    record['pole_dbh_cm'] = dbh
elif dbh < 30:
    # Large Pole (20-29.99 cm DBH)
    record['pole_dbh_cm'] = dbh
```

### Fix 2: export_to_excel() Classification (Line ~1070)
Same fix applied to Excel export function.

### Fix 3: generate_regeneration_entries() DBH Ranges (Lines 755, 782)
```python
# BEFORE:
'dbh_cm': round(random.uniform(1.0, 4.0), 1)   # Regeneration
'dbh_cm': round(random.uniform(4.0, 10.0), 1)  # Sapling

# AFTER:
'dbh_cm': round(random.uniform(1.0, 3.9), 1)   # Regeneration (max 3.9)
'dbh_cm': round(random.uniform(4.0, 9.9), 1)   # Sapling (max 9.9)
```

### Fix 4: Updated Function Docstrings
- Updated `generate_regeneration_entries()` docstring (Line 684-688)
- Updated `export_to_gpkg()` Size Classes comment (Line 807-811)

## Files Modified

**File:** `backend/app/services/tree_distribution.py`

**Lines changed:**
- Lines 684-688: Function docstring
- Lines 739-762: Regeneration generation (1.0-3.9)
- Lines 766-790: Sapling generation (4.0-9.9)
- Lines 807-811: Size Classes documentation
- Lines 890-924: GPKG export classification logic
- Lines 1070-1103: Excel export classification logic

## Testing Instructions

1. **Restart the backend server:**
   ```batch
   FORCE_RESTART_BACKEND.bat
   ```

2. **Generate a new tree model:**
   - Go to Tree Distribution Model tab
   - Generate a new tree model
   - Export to Excel

3. **Verify the fix:**
   - Open the exported Excel file
   - Check `regen_dbh` column: All values should be 1.0 to 3.9
   - Check `sapling_dbh_cm` column: All values should be 4.0 to 9.9
   - Check `pole_dbh_cm` column: All values should be 10.0 to 29.9
   - Check `tree_dbh_cm` column: All values should be >= 30.0

## Expected Results After Fix

When you export a tree model to Excel, the columns will now have correct DBH ranges:

| Column | DBH Range | Description |
|--------|-----------|-------------|
| `regen_dbh` | 1.0 - 3.9 cm | Unestablished regeneration |
| `sapling_dbh_cm` | 4.0 - 9.9 cm | Established regeneration/sapling |
| `pole_dbh_cm` | 10.0 - 29.9 cm | Pole-sized trees |
| `tree_dbh_cm` | >= 30.0 cm | Mature trees |

## Status

✅ **All fixes applied and ready for testing**

**Next step:** Restart backend and generate a new tree model to verify the fix.
