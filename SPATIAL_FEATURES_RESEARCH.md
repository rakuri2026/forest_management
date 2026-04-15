# Spatial Features Implementation - Research Documentation

**Document Version:** 1.0
**Date:** April 15, 2026
**Project:** Community Forest Management System - Yearly Activities Spatial Features

---

## 1. Executive Summary

This document provides detailed technical research on the Spatial Features implementation in the Community Forest Management System. The feature enables forest managers to draw and manage spatial features (points, lines, polygons) for yearly activity assignments within community forest boundaries.

### Key Features Implemented
1. **Visualize** forest boundaries, blocks, and sub-areas on the activity map
2. **Draw** spatial features (points, lines, polygons) for activity locations
3. **Edit** existing features (add vertices, move, delete)
4. **Copy** features between different years (Year 1-10)
5. **Provide** multiple base map options (Satellite, Street, Topographic)
6. **Display** live measurements during drawing
7. **Filter** features by sub-area category
8. **Assign** activities to locations (block/sub-area assignment)
9. **Toggle** measurement units (metric/imperial)

### Key Findings
- **Coordinate Handling**: GeoJSON uses [lng, lat], Leaflet uses [lat, lng] - requires conversion
- **Backend Integration**: Uses Shapely for geometry, PostGIS for storage
- **Known Limitation**: Polygon edit requires delete + redraw

---

## 2. System Architecture

### 2.1 Frontend Components

| Component | File Path | Purpose |
|-----------|-----------|---------|
| ActivityMapView.tsx | `frontend/src/components/YearlyActivities/ActivityMapView.tsx` | Main map view with layers, base maps, filtering |
| DrawingCanvas.tsx | `frontend/src/components/YearlyActivities/DrawingCanvas.tsx` | Drawing canvas for creating/editing features |
| YearDetailEditor.tsx | `frontend/src/components/YearlyActivities/YearDetailEditor.tsx` | Yearly activity detail modal |
| YearlyActivitiesTab.tsx | `frontend/src/components/YearlyActivitiesTab.tsx` | Main tab container |

### 2.2 Backend API

| Endpoint | File | Method | Purpose |
|-----------|------|--------|---------|
| `/drawn-features` | `yearly_activities.py` | POST | Create drawn feature |
| `/drawn-features/{id}` | `yearly_activities.py` | PATCH | Update drawn feature |
| `/drawn-features/{id}` | `yearly_activities.py` | DELETE | Delete drawn feature |
| `/blocks-with-subareas` | `yearly_activities.py` | GET | Get blocks and sub-areas |

### 2.3 Database Schema

```sql
-- Table: activity_drawn_features
CREATE TABLE activity_drawn_features (
    id UUID PRIMARY KEY,
    proposed_activity_id UUID REFERENCES proposed_yearly_activities(id),
    feature_type VARCHAR(20), -- 'point', 'line', 'polygon'
    geometry GEOMETRY(Geometry, 4326), -- PostGIS geometry
    properties JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 3. Technical Implementation Details

### 3.1 Coordinate System

**GeoJSON Standard:** Uses [longitude, latitude] = [x, y] format
```javascript
// Point
{ "type": "Point", "coordinates": [85.0411, 27.4426] }

// LineString
{ "type": "LineString", "coordinates": [[85.0411, 27.4426], [85.0415, 27.4430], ...] }

// Polygon (must close - first and last point must match)
{ "type": "Polygon", "coordinates": [[ [85.0411, 27.4426], [85.0415, 27.4430], ..., [85.0411, 27.4426] ]] }
```

**Display Conversion:** Leaflet uses [latitude, longitude] = [y, x]
```javascript
// parseGeometry converts: [lng, lat] → [lat, lng] for display
// handleMapClickForEdit converts back: [lat, lng] → [lng, lat] for saving
```

### 3.2 Flow Diagram

```
User Action: Draw Feature
    ↓
DrawingCanvas.tsx - handleMapClick / handleDoubleClick
    ↓
createPoint() / createLine() / createPolygon()
    ↓
Calculate measurements (length/area) - live display
    ↓
yearlyActivitiesApi.createDrawnFeature()
    ↓
Backend API - POST /drawn-features
    ↓
Shapely geometry creation → WKT storage in PostGIS
    ↓
User Action: View Features
    ↓
loadDrawnFeatures() - fetch from API
    ↓
parseGeometry() - convert [lng, lat] → [lat, lng] for Leaflet
    ↓
renderFeatures() - display on map
```

### 3.3 Key Functions

#### Frontend Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `parseGeometry()` | DrawingCanvas.tsx:344 | Parse GeoJSON/WKT, convert to [lat, lng] |
| `createPoint()` | DrawingCanvas.tsx:137 | Create point feature |
| `createLine()` | DrawingCanvas.tsx:165 | Create line feature |
| `createPolygon()` | DrawingCanvas.tsx:213 | Create polygon feature |
| `handleMapClickForEdit()` | DrawingCanvas.tsx:296 | Handle edit clicks |
| `renderFeatures()` | DrawingCanvas.tsx:482 | Render features on map |
| `calculateMeasurements()` | DrawingCanvas.tsx:82 | Calculate live measurements |

#### Backend Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `create_drawn_feature()` | yearly_activities.py:700 | Create feature in DB |
| `update_drawn_feature()` | yearly_activities.py:758 | Update feature in DB |
| `delete_drawn_feature()` | yearly_activities.py:825 | Delete feature from DB |
| `get_drawn_features()` | yearly_activities.py:738 | Fetch all features |

---

## 4. User Workflows

### 4.1 Drawing a Feature

```
Step 1: Navigate to Spatial Features
    Yearly Activities → Activities Selection → Year Details → Spatial Features

Step 2: Select Activity
    - Choose activity from dropdown

Step 3: Enter Details
    - Enter feature name (required)
    - Select year (required)
    - Choose type: Point / Line / Polygon

Step 4: Start Drawing
    - Click "Start Drawing" button
    - Click on map to draw:
        * Point: Single click
        * Line: Multiple clicks, double-click to finish
        * Polygon: Multiple clicks (min 3), double-click to close

Step 5: Feature Saved
    - Shows in "Drawn Features" list
    - Appears on map
```

### 4.2 Editing a Feature

```
Step 1: Click Edit Button
    - Next to feature in list

Step 2: Edit Mode Active
    - Feature highlights orange dashed
    - Vertex markers appear (for line/polygon)

Step 3: Modify
    - Click map to add vertex
    - Click on feature to move

Step 4: Save Changes
    - Auto-saves to backend
```

### 4.3 Copy to Another Year

```
Step 1: Select Feature
    - Click in "Drawn Features" list

Step 2: Copy Panel Opens
    - Shows year buttons (Y1-Y10)

Step 3: Click Target Year
    - Feature duplicated with new year property
```

### 4.4 Assign Activity to Location

```
Step 1: Switch Mode
    - Click "Assign Location" in map mode

Step 2: Select Activity
    - Choose from dropdown

Step 3: View Blocks/Sub-areas
    - Shows available locations with categories

Step 4: Assign Location
    - Activities linked to specific blocks/sub-areas
```

### 4.5 Filter Features

```
Step 1: Use Category Filter
    - Select "Filter by sub-area category"
    - Shows only selected category

Step 2: View Results
    - Map updates to show filtered features
    - Count displayed in tag
```

---

## 5. Data Models

### 5.1 Sub-Area Categories

| Category | Color Code | Description |
|----------|------------|--------------|
| protected | #ef4444 | Protected zone |
| plantation | #10b981 | Plantation area |
| pro-poor | #f59e0b | Pro-poor income generation |
| religious | #8b5cf6 | Religious area |
| biodiversity | #06b6d4 | Bio-diversity rich area |
| tourist | #ec4899 | Tourist attraction |
| office | #6b7280 | Office area |
| private_land | #dc2626 | Private land (excluded) |

### 5.2 Feature Properties

| Property | Type | Description |
|----------|------|-------------|
| area_sqm | number | Area in square meters (polygon) |
| length_m | number | Length in meters (line) |
| name | string | Feature name |
| year | number | Year (1-10) |
| activity_id | string | Linked activity |
| sub_area_id | string | Linked sub-area |
| block_id | string | Linked block |

### 5.3 Base Map Sources

| Map Type | URL | Provider |
|----------|-----|----------|
| Satellite | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | Esri |
| Street | `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` | OpenStreetMap |
| Topographic | `https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png` | OpenTopoMap |

---

## 6. Metrics & Measurements

### 6.1 Length Calculation

```javascript
// Line length using Haversine formula
const length = points.reduce((acc, p, i) => {
    return acc + (i > 0 ? points[i - 1].distanceTo(p) : 0);
}, 0);
```

### 6.2 Area Calculation

```javascript
// Polygon area using Shoelace formula
for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += points[i].lng * points[j].lat;
    area -= points[j].lng * points[i].lat;
}
area = Math.abs(area) / 2;
const metersPerDegree = 111320;
area = Math.abs(area) * metersPerDegree * metersPerDegree;
```

### 6.3 Unit Conversion

| From | To | Factor |
|------|-----|-------|
| meters | feet | 3.28084 |
| square meters | acres | 0.000247105 |
| square meters | hectares | 0.0001 |

---

## 7. Performance Considerations

### 7.1 Map Rendering
- Features rendered using Leaflet GeoJSON layer
- Auto-fit bounds adjusts padding: `[50, 50]`
- Use `key` prop to force re-render on filter change

### 7.2 Data Loading
- Boundary, blocks, sub-areas loaded once on mount
- Drawn features fetched per activity
- Use React `useEffect` dependencies for proper refresh

### 7.3 State Management
- Local state for map, layers, editing
- Parent component manages feature list
- API calls use async/await pattern

---

## 8. Security & Validation

### 8.1 Input Validation
- Feature name required before drawing
- Year selection required (1-10)
- Minimum vertices: Point=1, Line=2, Polygon=3
- Double-click signals drawing completion

### 8.2 Backend Validation
```python
# Backend uses Shapely for geometry validation
# Invalid geometry returns error
```

### 8.3 API Authentication
```python
# All endpoints require user authentication
current_user: User = Depends(get_current_user)
```

---

## 9. Issues Encountered & Solutions

### 5.1 Issue: Polygon Disappears After Drawing

**Symptom:** Polygon draws but disappears on double-click

**Root Cause:** 
- Backend shapely.Polygon() expects specific coordinate format
- Frontend was sending incorrect structure

**Solution Applied:**
```python
# Backend fix in yearly_activities.py
ring = coords[0] if coords[0] and isinstance(coords[0][0], list) else coords
geom = shapely.Polygon(ring)
```

**Additional Frontend Fix:**
- parseGeometry() was wrapping polygon coords twice - removed extra wrapping

### 5.2 Issue: Edit Vertex 500 Error

**Symptom:** Adding vertex to line/polygon returns 500

**Root Cause:**
- Backend uses feature_type from database
- Frontend wasn't sending feature_type in PATCH request

**Solution Applied:**
```javascript
yearlyActivitiesApi.updateDrawnFeature(activityId, featureId, {
    geometry: newGeometry,
    feature_type: feature.feature_type // ← Added
});
```

### 5.3 Issue: Features Display Vertically Stretched

**Symptom:** Line/polygon appears vertically elongated

**Root Cause:** Coordinate order - [lng, lat] treated as [lat, lng]

**Solution:**
- parseGeometry() converts [lng, lat] → [lat, lng] for display
- handleMapClickForEdit converts back [lat, lng] → [lng, lat] for saving

### 5.4 Current Limitations

| Feature | Status | Notes |
|---------|--------|-------|
| Point draw | ✅ Working | |
| Line draw | ✅ Working | |
| Polygon draw | ✅ Working | Fixed |
| Point edit | ✅ Working | |
| Line edit (add vertex) | ✅ Working | Fixed |
| Line edit (move vertex) | ⚠️ Partial | Only for existing points |
| Polygon edit | ❌ Not supported | Delete and redraw |

---

## 10. Testing Checklist

### 6.1 Drawing Tests
- [ ] Draw point - appears on map
- [ ] Draw line - shows length while drawing
- [ ] Draw polygon - shows area while drawing
- [ ] Double-click finishes drawing
- [ ] Feature saves to database
- [ ] Feature appears after page refresh

### 6.2 Edit Tests
- [ ] Edit button activates edit mode
- [ ] Click adds vertex to line
- [ ] Changes save to database
- [ ] Feature updates on map

### 6.3 Copy/Delete Tests
- [ ] Copy feature to different year
- [ ] Delete feature works

### 6.4 Map Tests
- [ ] Base map switching (Satellite/OSM/TOPO)
- [ ] Layer display (boundary, blocks, sub-areas)
- [ ] Auto-zoom to layers

---

## 11. Research Questions

### 7.1 Coordinate Handling
1. Why does GeoJSON use [lng, lat] while Leaflet uses [lat, lng]?
2. How can we standardize coordinate handling across the system?
3. Should we convert on frontend or backend?

### 7.2 Edit Functionality
1. Why does polygon edit still fail after multiple fixes?
2. Is there a better approach than current vertex manipulation?
3. Should we use Leaflet-Geoman for editing instead?

### 7.3 Performance
1. How does rendering large number of features affect performance?
2. Should we implement clustering orsimplification?
3. What's the maximum recommended features per activity?

### 7.4 Data Storage
1. Should we store GeoJSON or WKT in database?
2. Could we use separate geometry tables for better query performance?
3. How to handle geometry validation?

---

## 12. Additional Features Documented

### 10.1 Assignment Mode (Assign Location)
- Allows assigning activities to specific blocks/sub-areas
- Shows Block/Sub-Area selector in separate panel
- Features linked to locations in database

### 10.2 Category Filtering
- Filter features by sub-area category (8 categories)
- Real-time map update with count display

### 10.3 Auto-Fit Bounds
- Map automatically zooms to fit all layers
- Combines boundary, blocks, sub-areas, and features

### 10.4 Sub-Area Layer Display
- Each sub-area category has unique color
- Renders on both View and Draw modes

### 10.5 Feature Properties Storage
- Name, year, area_sqm, length_m stored in JSONB
- Linked to activities and sub-areas via UUIDs

### 10.6 Measurement Display
- Live overlay during drawing (top-right)
- Shows length for lines
- Shows area in m² and hectares
- Supports metric/imperial toggle

---

## 13. Database Queries

### 11.1 Fetch Blocks with Sub-areas
```sql
SELECT block_id, block_name, sub_areas
FROM result_data->'blocks'
WHERE calculation_id = $1;
```

### 11.2 Fetch Sub-areas
```sql
SELECT id, name, category, geometry, area_hectares
FROM sub_areas
WHERE calculation_id = $1;
```

### 11.3 Fetch Drawn Features
```sql
SELECT id, feature_type, ST_AsGeoJSON(geometry) as geojson, properties
FROM activity_drawn_features
WHERE proposed_activity_id = $1;
```

---

## 14. API Request/Response Format

### 12.1 Create Feature (POST)
```javascript
// Request
{
    feature_type: 'polygon',
    geometry: '{"type":"Polygon","coordinates":[[...]]}',
    properties: { area_sqm: 8122, name: 'My Polygon', year: 1 }
}

// Response
{
    id: 'uuid',
    proposed_activity_id: 'uuid',
    feature_type: 'polygon',
    geometry: 'POLYGON((...))',
    properties: {...},
    created_at: 'timestamp'
}
```

### 12.2 Update Feature (PATCH)
```javascript
// Request
{
    geometry: '{"type":"Polygon","coordinates":[[...]]}',
    feature_type: 'polygon'
}

// Response (same as create)
```

---

## 15. Deployment Notes

### 13.1 Environment Variables
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/cf_db
SECRET_KEY=your-secret-key
```

### 13.2 Required Packages (Backend)
- fastapi
- sqlalchemy
- shapely
- geoalchemy2
- postgis

### 13.3 Required Packages (Frontend)
- react-leaflet
- leaflet
- antd
- axios

---

## 16. Future Improvements

### 8.1 High Priority
- [ ] Fix polygon edit functionality
- [ ] Add undo/redo for drawing
- [ ] Implement geometric validation

### 8.2 Medium Priority
- [ ] Add feature snapping to boundaries
- [ ] Export to KML/GeoJSON
- [ ] Color features by year (gradient)

### 8.3 Low Priority
- [ ] Measurement unit toggle (metric/imperial)
- [ ] Multiple selection for batch operations
- [ ] Feature labels on map

---

## 17. References

### 9.1 Documentation Files
- `SPATIAL_FEATURES_DOCUMENTATION.md` - Implementation notes
- `CLAUDE.md` - System overview
- `backend/app/api/yearly_activities.py` - Backend API
- `frontend/src/components/YearlyActivities/` - Frontend components

### 9.2 External Resources
- GeoJSON Specification: https://tools.ietf.org/html/rfc7946
- Leaflet Documentation: https://leafletjs.com/
- Shapely Documentation: https://shapely.readthedocs.io/
- PostGIS Documentation: https://postgis.net/documentation/

---

## 17. Contact & Version Control

**Backup Branch:** `backup-before-spatial-features-v2`

**Git Commands:**
```bash
# Check current branch
git status

# Create backup
git checkout -b backup-before-spatial-features-v2

# Restore if needed
git checkout backup-before-spatial-features-v2
```

---

*Document prepared for research and system improvement purposes*
*Last updated: April 15, 2026*