# Fieldbook Reference Column - Performance Optimization

## Problem
Initial implementation of `rasters.find_nearest_feature()` was extremely slow (5+ hours for 295 points)

## Root Cause
The function searched **all features** in each table without distance filtering:
```sql
-- OLD (SLOW): No distance filter
SELECT ... FROM river.river_line
WHERE (river_name IS NOT NULL OR features IS NOT NULL)
ORDER BY ST_Distance(...) LIMIT 1
```

This required calculating distance to **every single feature** in the database before finding the nearest one.

## Solution (User's Suggestion)
**Filter within 100m FIRST, then UNION, then find nearest:**

```sql
-- NEW (FAST): Filter within 100m using ST_DWithin
SELECT ... FROM river.river_line
WHERE (river_name IS NOT NULL OR features IS NOT NULL)
  AND ST_DWithin(ST_Transform(geom, 32645), v_point_utm, 100)  -- KEY!
```

## Why This Works

### Performance Benefits:
1. **Spatial Index Usage**: `ST_DWithin` leverages GIST spatial indexes
2. **Reduced Dataset**: Only processes ~5-20 nearby features vs. thousands
3. **Faster UNION**: Combining small filtered sets instead of full tables
4. **Efficient Sorting**: Finding nearest from small set is trivial

### Estimated Performance:
- **Old approach**: ~5+ hours for 295 points
- **New approach**: ~10-30 minutes for 295 points
- **Speedup**: ~10-30x faster

## Implementation

### SQL Function
**File**: `fix_fieldbook_reference_fast.sql`
**Function**: `rasters.find_nearest_feature(lon, lat)`

### Backend Integration
**File**: `backend/app/services/fieldbook.py`
**Lines**: 506-530
**Called**: During `update_utm_and_elevation()` after fieldbook generation

### Output Format
- `Feature Name: DIR(azimuth°) distanceM`
- Example: `River/Strem Flow Line: NE(33°) 5m`
- Only shown when reference changes from previous point (reduces repetition)

## Feature Sources (within 100m)
1. Rivers (`river.river_line`)
2. Roads (`infrastructure.road`)
3. Settlements (`admin.settlement`)
4. Points of Interest (`infrastructure.poi`)

## Future Improvements
1. Add spatial indexes if missing: `CREATE INDEX idx_road_geom ON infrastructure.road USING GIST(geom);`
2. Consider caching common references for repeat queries
3. Parallel processing for multiple fieldbooks
4. Progressive distance expansion (50m, 100m, 200m) if no features found

## Credits
Optimization strategy suggested by user during implementation of fieldbook reference column feature.
