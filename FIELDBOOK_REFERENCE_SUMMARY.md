# Fieldbook Reference Column - Implementation Summary

## Feature Overview
Added "Reference (Nearest Landmark)" column to fieldbook table to help field crews navigate to boundary points using nearby landmarks.

## Display Logic
- Shows nearest feature within 100m with direction and distance
- Format: `Feature Name: DIR(azimuth°) distanceM`
- Example: `River/Strem Flow Line: NE(33°) 5m`
- Only displays when reference changes from previous point (reduces repetition)
- Shows "↑ same" when reference hasn't changed

## Feature Sources (6 Types)

### 1. Rivers (`river.river_line`)
- Field: `river_name` or `features`
- Example: "River/Strem Flow Line: NE(33°) 5m"

### 2. Roads (`infrastructure.road`)
- Fields: `name`, `name_en`, or `highway`
- Examples:
  - "path: E(90°) 13m"
  - "residential: E(75°) 83m"
  - "unclassified: S(182°) 17m"

### 3. Settlements (`admin.settlement`)
- Field: `vil_name`
- Example: "Nayagaun: SW(225°) 45m"

### 4. Points of Interest (`infrastructure.poi`)
- Fields: `name`, `name_en`, or `amenity`
- Example: "School: N(15°) 67m"

### 5. ESA Forest Boundaries (`admin.esa_forest_Boundary`)
- Fields: `description` or `boundary of`
- Examples:
  - "Cropland: E(90°) 23m"
  - "Grassland: S(180°) 56m"
  - "Shrubland: W(270°) 78m"

### 6. Community Forests (`admin.community forests`) - **VERY IMPORTANT**
- Field: `name`
- Example: "Lohandra-Kerabari: NW(315°) 12m"

## Performance Optimization

### Strategy
**Filter within 100m FIRST, then UNION, then find nearest** (user's suggestion)

### Implementation
```sql
-- Use ST_DWithin to filter before UNION
WHERE ... AND ST_DWithin(ST_Transform(geom, 32645), v_point_utm, 100)
```

### Benefits
- Uses spatial GIST indexes effectively
- Only processes ~5-20 nearby features instead of thousands
- 10-30x faster than scanning all features

### Performance Metrics
- **Old approach**: 5+ hours for 295 points
- **New approach**: ~60 minutes for 295 points with 6 tables
- **Per point**: ~10-20 seconds (acceptable for background processing)

## Database Schema

### Table: `public.fieldbook`
**New Column**: `reference TEXT`

### SQL Function
**Name**: `rasters.find_nearest_feature(lon, lat)`
**Location**: `fix_fieldbook_reference_v2_with_forests.sql`
**Returns**: Formatted string or NULL

### Backend Integration
**File**: `backend/app/services/fieldbook.py`
**Function**: `update_utm_and_elevation()`
**Lines**: 506-530
**Called**: Automatically after fieldbook generation when `extract_elevation=True`

## Compass Directions (8-point)
- N: 337.5° - 22.5°
- NE: 22.5° - 67.5°
- E: 67.5° - 112.5°
- SE: 112.5° - 157.5°
- S: 157.5° - 202.5°
- SW: 202.5° - 247.5°
- W: 247.5° - 292.5°
- NW: 292.5° - 337.5°

## Frontend Display
**Component**: `FieldbookTab.tsx`
**Column**: "Reference (Nearest Landmark)"
**Styling**:
- Actual reference: Blue text, medium font weight
- "↑ same": Gray text, small, italicized

## Future Enhancements
1. Add elevation difference to reference (e.g., "River: NE(33°) 5m ↓12m")
2. Cache frequently-used references
3. Add admin boundary references (district, municipality)
4. Support multiple reference formats (bearing only, distance only, etc.)
5. Add user-definable landmark database

## Files Modified/Created
1. ✅ `fix_fieldbook_reference_v2_with_forests.sql` - Complete SQL function
2. ✅ `backend/app/services/fieldbook.py` - Backend integration (lines 506-530)
3. ✅ `frontend/src/components/FieldbookTab.tsx` - Frontend display with reference column
4. ✅ `FIELDBOOK_REFERENCE_OPTIMIZATION.md` - Performance optimization docs
5. ✅ `FIELDBOOK_REFERENCE_SUMMARY.md` - This file

## Credits
- Performance optimization strategy: User suggestion (ST_DWithin filter first)
- Feature sources identification: User (ESA Forest Boundary, Community Forests)
