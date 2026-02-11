# Soil Analysis - Future Implementation TODO

**Status**: ⏳ Disabled (February 9, 2026)
**Priority**: Medium
**Difficulty**: Low to Medium

---

## Quick Summary

Enhanced soil analysis is **fully coded but disabled** because it crashes PostgreSQL 18. The simplest fix is to increase PostgreSQL memory settings and re-enable the code.

---

## To Re-enable (Quick Steps)

### Step 1: Optimize PostgreSQL Memory

**File**: `C:\Program Files\PostgreSQL\18\data\postgresql.conf`

**Change these lines**:
```ini
shared_buffers = 512MB          # Change from 128MB
work_mem = 32MB                 # Change from 4MB
maintenance_work_mem = 256MB    # Change from 64MB
effective_cache_size = 2GB      # Adjust based on RAM
```

**Restart PostgreSQL**:
```batch
net stop postgresql-x64-18
net start postgresql-x64-18
```

### Step 2: Re-enable Code

**File**: `D:\forest_management\backend\app\services\analysis.py`

**Function 1**: `analyze_soil()` (line ~1403)
- Delete lines 1424-1437 (the "return empty results" section)
- Keep the rest as-is

**Function 2**: `analyze_soil_geometry()` (line ~2303)
- Delete lines 2314-2326 (the "return empty results" section)
- Keep the rest as-is

### Step 3: Test

```bash
# Restart backend
cd D:\forest_management\backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001

# Upload small boundary file (1-5 hectares)
# Watch backend logs for soil analysis queries
# Verify no PostgreSQL crashes
```

---

## What You'll Get

When re-enabled, users will see:

✅ **Soil Texture**: 12-class USDA classification (e.g., "Clay Loam", "Sandy Loam")
✅ **Carbon Stock**: Tonnes per hectare in topsoil
✅ **Fertility**: 5-class rating (Very Low to Very High) with score 0-100
✅ **Compaction**: 4-level status with management alerts

---

## If It Still Crashes

Try **Option 2** from `FUTURE_SOIL_ANALYSIS.md`:
- Simplify to 5 bands instead of 8
- Skip fertility assessment
- Keep texture + carbon + compaction only

---

## Files to Reference

1. **`FUTURE_SOIL_ANALYSIS.md`** - Full implementation guide
2. **`CLAUDE.md`** - Project development log
3. **`backend/app/services/analysis.py`** - Source code

---

## Estimated Time

- **PostgreSQL optimization**: 15 minutes
- **Code re-enabling**: 5 minutes
- **Testing**: 30 minutes
- **Total**: ~1 hour

---

## Success Criteria

✅ Analysis completes without PostgreSQL crashes
✅ Soil metrics display in frontend with colored badges
✅ System remains stable under multiple concurrent uploads
✅ Performance acceptable (<30 seconds per forest)

---

**Remember**: Test with SMALL boundary files first!

