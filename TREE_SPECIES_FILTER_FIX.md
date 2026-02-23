# Tree Species Filter - Complete Fix

**Date:** February 23, 2026
**Issue:** Swertia chirayita still appearing in Excel exports despite filtering implementation
**Root Cause:** Species analysis didn't include is_tree_species field in potential_species data

---

## Problem Diagnosis

**USER REPORT:** "Swertia chirayita is not tree but exported in excel."

**INVESTIGATION FINDINGS:**

1. ✅ Database column added correctly (`is_tree_species`)
2. ✅ Swertia chirayita marked as FALSE correctly
3. ✅ Tree filtering code added to tree_distribution.py
4. ❌ **PROBLEM:** Species analysis SQL doesn't include `is_tree_species` field
5. ❌ **PROBLEM:** Species dictionary doesn't save `is_tree_species` field

**Result:** The filtering code in tree_distribution.py couldn't find the `is_tree_species` field because it was never loaded from the database into `potential_species`.

---

## Root Cause

### Issue 1: SQL Query Missing Field

**File:** `backend/app/services/analysis.py`
**Line:** 2955-2977

**Problem:**
```sql
SELECT
    tsc.scientific_name,
    tsc.local_name,
    ...
    tsc.economic_value
    -- MISSING: is_tree_species column!
FROM tree_species_coefficients tsc
```

**Fix:**
```sql
SELECT
    tsc.scientific_name,
    tsc.local_name,
    ...
    tsc.economic_value,
    tsc.is_tree_species  -- ADDED
FROM tree_species_coefficients tsc
```

### Issue 2: Dictionary Not Storing Field

**File:** `backend/app/services/analysis.py`
**Line:** 3005-3021

**Problem:**
```python
species_data[scientific_name] = {
    "scientific_name": scientific_name,
    "local_name": r.local_name,
    ...
    "family": r.family
    # MISSING: is_tree_species field!
}
```

**Fix:**
```python
species_data[scientific_name] = {
    "scientific_name": scientific_name,
    "local_name": r.local_name,
    ...
    "family": r.family,
    "is_tree_species": r.is_tree_species if hasattr(r, 'is_tree_species') else True  # ADDED
}
```

---

## Complete Solution

### 1. Database Layer ✅ (Already Done)
```sql
ALTER TABLE tree_species_coefficients
ADD COLUMN is_tree_species BOOLEAN DEFAULT TRUE;

UPDATE tree_species_coefficients
SET is_tree_species = FALSE
WHERE main_uses NOT ILIKE '%wood%'
  AND main_uses NOT ILIKE '%timber%'
  AND main_uses NOT ILIKE '%fuel%'
  AND main_uses NOT ILIKE '%fodder%';
```

**Result:** 83 trees, 54 non-trees

### 2. Analysis SQL Query ✅ (FIXED NOW)
**File:** `backend/app/services/analysis.py` line 2972
```sql
tsc.is_tree_species  -- Added to SELECT clause
```

### 3. Analysis Dictionary ✅ (FIXED NOW)
**File:** `backend/app/services/analysis.py` line 3021
```python
"is_tree_species": r.is_tree_species if hasattr(r, 'is_tree_species') else True
```

### 4. Tree Model Filtering ✅ (Already Done)
**File:** `backend/app/services/tree_distribution.py` lines 1132-1153
```python
tree_species_only = [
    sp for sp in species_list
    if sp.get('is_tree_species', True)
]
```

---

## Files Modified

### First Implementation (Previous Commit: bf945ba)
1. Database: Added `is_tree_species` column
2. `backend/app/services/tree_distribution.py` - Filtering logic

### Second Fix (This Commit)
3. `backend/app/services/analysis.py` line 2972 - SQL query
4. `backend/app/services/analysis.py` line 3021 - Dictionary

---

## Data Flow

### BEFORE (Broken)
```
1. Database query → Missing is_tree_species
2. Species dict → Missing is_tree_species
3. potential_species → Missing is_tree_species
4. Tree filtering → Can't filter (field doesn't exist!)
5. Excel export → Swertia chirayita appears ❌
```

### AFTER (Fixed)
```
1. Database query → Includes is_tree_species ✅
2. Species dict → Saves is_tree_species ✅
3. potential_species → Has is_tree_species ✅
4. Tree filtering → Filters properly ✅
5. Excel export → Swertia chirayita EXCLUDED ✅
```

---

## Testing Steps

### Step 1: Restart Backend Server
**CRITICAL:** Backend must be restarted to load new code
```bash
# Stop current backend
# Start backend fresh
```

### Step 2: Re-run Analysis
**IMPORTANT:** You need to re-analyze the boundary to get updated species data

1. Login to system
2. Go to calculation
3. Click "Analysis" tab
4. Re-run analysis (if needed) or upload new boundary

**Why?** Old calculations have species data WITHOUT the `is_tree_species` field. Re-running analysis will fetch it fresh with the field.

### Step 3: Generate Tree Model
1. Go to "Tree Model" tab
2. Click "Generate Tree Model"
3. Wait for completion
4. Check console log for: "Filtered out X non-tree species"

### Step 4: Verify Excel Export
1. Download Excel file
2. Search for "Swertia chirayita" → Should be **NOT FOUND** ✅
3. Search for "Salix lindleyana" → Should be **NOT FOUND** ✅
4. Search for "Shorea robusta" → Should be **FOUND** ✅

---

## Why It Happens

### Scenario 1: Old Calculation Data
If you're using a calculation that was created BEFORE we added the `is_tree_species` column:
- The `result_data['potential_species']` was saved without this field
- Even though the database now has the field, the old saved data doesn't
- **Solution:** Re-run the analysis or create new calculation

### Scenario 2: Backend Not Restarted
If the backend server wasn't restarted after code changes:
- Old code is still running
- New analysis.py changes not loaded
- **Solution:** Restart backend

### Scenario 3: Both!
Most likely case - both issues combined

---

## Verification Checklist

- [x] Database has `is_tree_species` column
- [x] 83 tree species marked TRUE
- [x] 54 non-tree species marked FALSE
- [x] SQL query includes field (line 2972)
- [x] Dictionary saves field (line 3021)
- [x] Filtering logic exists (tree_distribution.py)
- [ ] **Backend restarted (USER MUST DO)**
- [ ] **Analysis re-run (USER MUST DO)**
- [ ] **Tree model generated (USER MUST DO)**
- [ ] **Excel verified (USER MUST DO)**

---

## Expected Console Output

When generating tree model, you should see:
```
INFO: Filtered out 54 non-tree species (herbs, shrubs).
Using 83 tree species for model generation.
```

If you DON'T see this message:
- Backend wasn't restarted
- OR analysis has old data without `is_tree_species` field

---

## Quick Fix Summary

**What was wrong:**
- Species analysis SQL didn't SELECT the `is_tree_species` column
- Species dictionary didn't store the `is_tree_species` value

**What was fixed:**
- Added `tsc.is_tree_species` to SQL SELECT (analysis.py:2972)
- Added `"is_tree_species": r.is_tree_species` to dict (analysis.py:3021)

**What user must do:**
1. Restart backend server
2. Re-run analysis (or create new calculation)
3. Generate tree model
4. Verify Swertia NOT in Excel

---

## Rollback

If needed, revert to commit before these changes:
```bash
git checkout bf945ba
```

---

**Status:** ✅ Code Fixed, ⏳ Testing Pending (User Action Required)
**Next:** Restart backend → Re-analyze → Generate tree model → Verify Excel
