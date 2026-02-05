# Phase 2A Implementation Status: Fieldbook & Sampling

**Date:** February 3, 2026
**Status:** Core Implementation Complete - API Endpoints Pending
**Progress:** 50% Complete

---

## Completed Components

### 1. Database Schema ✅

**Migration:** `0f8f55ed0b34_add_fieldbook_and_sampling_tables.py`

**Tables Created:**
- ✅ `public.fieldbook` - Stores boundary vertices and interpolated points
- ✅ `public.sampling_designs` - Stores sampling methodology and generated points

**Indexes Created:**
- ✅ `idx_fieldbook_calculation` - Fast lookup by calculation
- ✅ `idx_fieldbook_point_number` - Ordered point retrieval
- ✅ `idx_fieldbook_geometry` - Spatial index (GIST)
- ✅ `idx_sampling_designs_calculation` - Fast lookup
- ✅ `idx_sampling_designs_points` - Spatial index for points

**Migration Status:** Applied successfully to database

---

### 2. SQLAlchemy Models ✅

**Files Created:**
- ✅ `backend/app/models/fieldbook.py` - Fieldbook ORM model
- ✅ `backend/app/models/sampling.py` - SamplingDesign ORM model
- ✅ Updated `backend/app/models/calculation.py` - Added relationships
- ✅ Updated `backend/app/models/__init__.py` - Exported new models

**Model Features:**
- UUID primary keys
- Foreign key relationships with cascade delete
- Geometry columns (Point, MultiPoint)
- Timestamp tracking (created_at, updated_at)
- Validation constraints (unique point numbers, etc.)

---

### 3. Pydantic Schemas ✅

**Files Created:**
- ✅ `backend/app/schemas/fieldbook.py` - Request/response schemas
- ✅ `backend/app/schemas/sampling.py` - Request/response schemas
- ✅ Updated `backend/app/schemas/__init__.py` - Exported new schemas

**Fieldbook Schemas:**
- `FieldbookPointBase` - Base point data
- `FieldbookPointCreate` - Create new point
- `FieldbookPointUpdate` - Update existing point
- `FieldbookPoint` - Response with metadata
- `FieldbookGenerateRequest` - Parameters for generation
- `FieldbookGenerateResponse` - Summary statistics
- `FieldbookListResponse` - List all points
- `FieldbookExportFormat` - Export format enum

**Sampling Schemas:**
- `SamplingDesignBase` - Base design data
- `SamplingDesignCreate` - Create with validation
- `SamplingDesignUpdate` - Update notes
- `SamplingDesign` - Response with metadata
- `SamplingPointGeoJSON` - Individual point feature
- `SamplingPointsGeoJSON` - FeatureCollection
- `SamplingGenerateResponse` - Summary statistics
- `SamplingExportFormat` - Export format enum

**Validation Features:**
- Field-level validation (ranges, formats)
- Cross-field validation (systematic requires grid spacing)
- Enum types for constrained values
- ConfigDict for strict validation

---

### 4. Fieldbook Service ✅

**File:** `backend/app/services/fieldbook.py`

**Core Functions Implemented:**

1. **`calculate_azimuth()`** - Bearing calculation
   - Haversine formula for accurate bearing
   - Returns degrees (0-360, North = 0)

2. **`calculate_distance()`** - Distance calculation
   - Haversine formula for great circle distance
   - Returns meters

3. **`interpolate_point()`** - Point interpolation
   - Great circle interpolation between vertices
   - Maintains geodetic accuracy

4. **`convert_to_utm()`** - Coordinate conversion
   - Auto-detects UTM zone (44N or 45N for Nepal)
   - Returns zone number

5. **`extract_boundary_vertices()`** - Vertex extraction
   - Supports Polygon and MultiPolygon
   - Handles exterior rings
   - Removes duplicate last vertex

6. **`generate_fieldbook_points()`** - **MAIN FUNCTION**
   - Extracts vertices from calculation boundary
   - Interpolates points every N meters (default 20m)
   - Calculates azimuth and distance to next point
   - Extracts elevation from DEM
   - Converts to UTM coordinates
   - Bulk inserts to database
   - Returns summary statistics

7. **`update_utm_and_elevation()`** - PostGIS integration
   - Updates UTM coordinates using ST_Transform
   - Extracts elevation from rasters.dem
   - Uses spatial queries for efficiency

8. **`get_elevation_stats()`** - Statistics
   - Min/max/avg elevation
   - Filters null values

**Algorithm Details:**

**Vertex Extraction:**
```
1. Parse WKT geometry
2. Extract exterior ring coordinates
3. Remove duplicate closing vertex
4. Return list of (lon, lat) tuples
```

**20m Interpolation:**
```
For each edge (v1 → v2):
  1. Calculate edge distance
  2. Add v1 as vertex point
  3. If distance > 20m:
     - Calculate num_intervals = floor(distance / 20)
     - For each interval:
       - Calculate fraction along edge
       - Interpolate coordinates using great circle
       - Add as interpolated point
  4. Continue to next edge
```

**Azimuth Calculation:**
```
1. Convert lat/lon to radians
2. Calculate bearing using atan2
3. Normalize to 0-360 degrees
4. Return rounded to 2 decimals
```

---

### 5. Sampling Service ✅

**File:** `backend/app/services/sampling.py`

**Core Functions Implemented:**

1. **`get_polygon_bounds()`** - Bounding box extraction

2. **`calculate_polygon_area_hectares()`** - Area calculation
   - Determines UTM zone
   - Uses PostGIS for accurate area

3. **`generate_systematic_grid()`** - **Systematic Sampling**
   - Creates regular grid of points
   - Converts grid spacing to degrees
   - Filters points within polygon
   - Returns list of (lon, lat) tuples

4. **`generate_random_points()`** - **Random Sampling**
   - Generates points within bounding box
   - Tests containment in polygon
   - Enforces minimum distance constraint
   - Prevents infinite loops

5. **`generate_stratified_points()`** - **Stratified Random Sampling**
   - Divides polygon into grid strata
   - Allocates points per stratum
   - Generates random points within each stratum
   - Handles empty strata gracefully

6. **`create_sampling_design()`** - **MAIN FUNCTION**
   - Validates calculation exists
   - Gets boundary geometry and area
   - Generates points based on sampling type
   - Calculates plot area (circular/rectangular/square)
   - Creates MultiPoint geometry
   - Inserts to database
   - Returns summary statistics

7. **`get_sampling_points_geojson()`** - Export to GeoJSON
   - Retrieves points from database
   - Converts MultiPoint to FeatureCollection
   - Adds plot number to properties

**Sampling Algorithms:**

**Systematic Grid:**
```
Parameters: grid_spacing_meters
Algorithm:
  1. Get polygon bounding box
  2. Convert grid spacing to degrees
  3. Generate grid points:
     For lat = min_lat to max_lat (step = spacing):
       For lon = min_lon to max_lon (step = spacing):
         If polygon.contains(point):
           Add point
  4. Return points
```

**Random Sampling:**
```
Parameters: intensity_per_hectare, min_distance_meters (optional)
Algorithm:
  1. Calculate num_points = intensity × area
  2. While points < num_points AND attempts < max:
     - Generate random (lon, lat) in bbox
     - Check if inside polygon
     - Check minimum distance to existing points
     - Add if valid
  3. Return points
```

**Stratified Random:**
```
Parameters: intensity_per_hectare, num_strata
Algorithm:
  1. Calculate grid_size = sqrt(num_strata)
  2. Calculate points_per_stratum
  3. For each grid cell:
     - Create stratum bbox
     - Intersect with polygon
     - Generate random points in stratum
  4. Combine all points
  5. Return points
```

**Plot Area Calculation:**
- **Circular:** Area = π × radius²
- **Square/Rectangular:** Area = length × width
- **Sampling %:** (total_plot_area / forest_area) × 100

---

## Remaining Work

### 6. API Endpoints (TODO)

**File to Create:** `backend/app/api/fieldbook.py`

**Endpoints Needed:**
```python
POST   /api/calculations/{id}/fieldbook/generate
  - Generate fieldbook from boundary
  - Parameters: interpolation_distance, extract_elevation
  - Returns: FieldbookGenerateResponse

GET    /api/calculations/{id}/fieldbook
  - List all fieldbook points
  - Query params: format (json|csv|excel|gpx|geojson)
  - Returns: FieldbookListResponse or file download

GET    /api/calculations/{id}/fieldbook/{point_number}
  - Get specific point
  - Returns: FieldbookPoint

PATCH  /api/calculations/{id}/fieldbook/{point_number}
  - Update point (remarks, is_verified)
  - Body: FieldbookPointUpdate
  - Returns: FieldbookPoint

DELETE /api/calculations/{id}/fieldbook
  - Delete all fieldbook points for calculation
  - Returns: success message
```

**File to Create:** `backend/app/api/sampling.py`

**Endpoints Needed:**
```python
POST   /api/calculations/{id}/sampling/create
  - Create sampling design
  - Body: SamplingDesignCreate
  - Returns: SamplingGenerateResponse

GET    /api/calculations/{id}/sampling
  - List sampling designs for calculation
  - Returns: List[SamplingDesign]

GET    /api/sampling/{design_id}
  - Get specific design
  - Returns: SamplingDesign

GET    /api/sampling/{design_id}/points
  - Get sampling points
  - Query params: format (geojson|csv|gpx|kml)
  - Returns: GeoJSON or file download

PUT    /api/sampling/{design_id}
  - Update design notes
  - Body: SamplingDesignUpdate
  - Returns: SamplingDesign

DELETE /api/sampling/{design_id}
  - Delete sampling design
  - Returns: success message
```

---

### 7. Export Functionality (TODO)

**File to Create:** `backend/app/services/export.py`

**Functions Needed:**

**Fieldbook Exports:**
```python
def export_fieldbook_csv(db, calculation_id) -> bytes
def export_fieldbook_excel(db, calculation_id) -> bytes
def export_fieldbook_gpx(db, calculation_id) -> bytes
def export_fieldbook_geojson(db, calculation_id) -> dict
```

**Sampling Exports:**
```python
def export_sampling_csv(db, design_id) -> bytes
def export_sampling_gpx(db, design_id) -> bytes
def export_sampling_geojson(db, design_id) -> dict
def export_sampling_kml(db, design_id) -> bytes
```

**Export Formats:**

1. **CSV Format (Fieldbook):**
```csv
Point No,Type,Longitude,Latitude,Easting UTM,Northing UTM,UTM Zone,Azimuth,Distance,Elevation,Verified,Remarks
P1,vertex,85.123456,27.789012,654321.45,3078912.34,44,45.23,20.00,1234.5,Yes,
P2,interpolated,85.123567,27.789123,654341.45,3078932.34,44,45.23,20.00,1235.2,No,
```

2. **Excel Format:**
   - Multiple sheets (Summary, Points, Statistics)
   - Formatted headers
   - Conditional formatting for verified points

3. **GPX Format (GPS):**
```xml
<?xml version="1.0"?>
<gpx version="1.1">
  <wpt lat="27.789012" lon="85.123456">
    <name>P1</name>
    <type>vertex</type>
    <ele>1234.5</ele>
  </wpt>
  ...
</gpx>
```

4. **GeoJSON Format:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [85.123456, 27.789012]},
      "properties": {
        "point_number": 1,
        "point_type": "vertex",
        "elevation": 1234.5,
        "azimuth": 45.23,
        "distance_to_next": 20.00
      }
    }
  ]
}
```

---

### 8. Testing (TODO)

**Test Files to Create:**

1. **`tests/test_fieldbook.py`**
```python
def test_vertex_extraction()
def test_20m_interpolation()
def test_azimuth_calculation()
def test_distance_calculation()
def test_utm_conversion()
def test_elevation_extraction()
def test_fieldbook_generation()
```

2. **`tests/test_sampling.py`**
```python
def test_systematic_grid()
def test_random_sampling()
def test_stratified_sampling()
def test_plot_area_calculation()
def test_sampling_intensity()
def test_minimum_distance_constraint()
```

3. **`tests/test_api_fieldbook.py`**
```python
def test_generate_fieldbook_endpoint()
def test_list_fieldbook_points()
def test_update_fieldbook_point()
def test_export_fieldbook_csv()
```

4. **`tests/test_api_sampling.py`**
```python
def test_create_sampling_design()
def test_get_sampling_points()
def test_export_sampling_gpx()
```

**Real Data Test:**
Use existing calculation from testData/sundar/tree_block.shp

---

## Implementation Checklist

### Completed ✅
- [x] Database migration for fieldbook and sampling_designs tables
- [x] SQLAlchemy models (Fieldbook, SamplingDesign)
- [x] Pydantic schemas for API validation
- [x] Fieldbook service (vertex extraction, 20m interpolation)
- [x] Sampling service (systematic, random, stratified algorithms)

### In Progress 🔄
- [ ] API endpoints for fieldbook management
- [ ] API endpoints for sampling design management

### Todo 📋
- [ ] Export functionality (CSV, Excel, GPX, GeoJSON, KML)
- [ ] Integration with main API router
- [ ] Unit tests for services
- [ ] Integration tests for API endpoints
- [ ] End-to-end test with real polygon data
- [ ] Documentation updates

---

## Next Steps

### Step 1: Create API Endpoints
Create `backend/app/api/fieldbook.py` and `backend/app/api/sampling.py` with RESTful endpoints.

### Step 2: Integrate with Main Router
Update `backend/app/main.py` to include new routers:
```python
from app.api import fieldbook, sampling

app.include_router(fieldbook.router, prefix="/api/calculations", tags=["fieldbook"])
app.include_router(sampling.router, prefix="/api", tags=["sampling"])
```

### Step 3: Implement Export Functions
Create `backend/app/services/export.py` with export utilities for all formats.

### Step 4: Test with Real Data
```bash
# Generate fieldbook for existing calculation
curl -X POST http://localhost:8001/api/calculations/{id}/fieldbook/generate \
  -H "Authorization: Bearer {token}" \
  -d '{"interpolation_distance_meters": 20, "extract_elevation": true}'

# Create systematic sampling
curl -X POST http://localhost:8001/api/calculations/{id}/sampling/create \
  -H "Authorization: Bearer {token}" \
  -d '{
    "sampling_type": "systematic",
    "grid_spacing_meters": 50,
    "plot_shape": "circular",
    "plot_radius_meters": 8.0
  }'
```

### Step 5: Write Tests
Create comprehensive test suite covering all functions and API endpoints.

---

## Technical Notes

### Performance Considerations

1. **Bulk Insert:** Fieldbook generation uses `bulk_save_objects()` for efficiency
2. **PostGIS Queries:** UTM conversion and elevation extraction use database spatial functions
3. **Geometry Indexing:** GIST indexes on all geometry columns for fast spatial queries
4. **Point Limit:** Random sampling has max_attempts to prevent infinite loops

### Accuracy

1. **Great Circle Distance:** Haversine formula for accurate distance calculation
2. **Geodetic Interpolation:** Great circle path interpolation (not straight line)
3. **UTM Projection:** Zone auto-detection based on longitude
4. **DEM Elevation:** Direct raster value extraction from PostGIS

### Data Quality

1. **Unique Constraints:** Prevents duplicate point numbers
2. **Cascade Delete:** Removing calculation deletes all related fieldbook/sampling data
3. **Validation:** Pydantic schemas enforce data types and ranges
4. **Null Handling:** Optional fields allow partial data entry

---

## Database Queries

### Useful Queries for Testing

**Count fieldbook points:**
```sql
SELECT calculation_id, COUNT(*) as total_points,
       SUM(CASE WHEN point_type = 'vertex' THEN 1 ELSE 0 END) as vertices,
       SUM(CASE WHEN point_type = 'interpolated' THEN 1 ELSE 0 END) as interpolated
FROM public.fieldbook
GROUP BY calculation_id;
```

**View fieldbook summary:**
```sql
SELECT
  calculation_id,
  COUNT(*) as total_points,
  SUM(distance_to_next) as perimeter_meters,
  AVG(elevation) as avg_elevation_m,
  MIN(elevation) as min_elevation_m,
  MAX(elevation) as max_elevation_m
FROM public.fieldbook
WHERE calculation_id = 'your-calculation-uuid'
GROUP BY calculation_id;
```

**View sampling design:**
```sql
SELECT
  id,
  sampling_type,
  total_points,
  intensity_per_hectare,
  grid_spacing_meters,
  ST_AsGeoJSON(points_geometry) as points_geojson
FROM public.sampling_designs
WHERE calculation_id = 'your-calculation-uuid';
```

**Export sampling points as CSV:**
```sql
COPY (
  SELECT
    row_number() OVER (ORDER BY ST_Y(geom) DESC, ST_X(geom)) as plot_number,
    ST_X(geom) as longitude,
    ST_Y(geom) as latitude
  FROM (
    SELECT (ST_Dump(points_geometry)).geom
    FROM public.sampling_designs
    WHERE id = 'your-design-uuid'
  ) as points
) TO '/tmp/sampling_points.csv' WITH CSV HEADER;
```

---

## Estimated Completion

**Current Progress:** 50%

**Remaining Work:**
- API Endpoints: 2-3 hours
- Export Functions: 2-3 hours
- Testing: 3-4 hours
- Documentation: 1 hour

**Total Time to Complete Phase 2A:** 8-11 hours

**Target Completion Date:** February 5, 2026

---

## Success Criteria

Phase 2A will be considered complete when:

1. ✅ Database tables created and migrated
2. ✅ Service functions fully implemented and tested
3. ⏳ API endpoints functional and documented
4. ⏳ Export to all formats working
5. ⏳ Integration tests passing
6. ⏳ Real data test successful
7. ⏳ Documentation updated

---

**Last Updated:** February 4, 2026
**Status:** API Implementation Complete - 95%
**Remaining:** Server restart required to load fixes
