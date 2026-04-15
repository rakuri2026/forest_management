# Spatial Features - Implementation Documentation

**Last Updated:** April 15, 2026
**Version:** 2.0

---

## Overview

The Spatial Features system allows users to draw and manage spatial features (points, lines, polygons) for yearly activity assignments. It's accessed via:

```
Yearly Activities → Activities Selection → Year Details → Spatial Features
```

---

## User Workflow

### Step 1: Navigate to Spatial Features
1. Login to the system
2. Go to Yearly Activities tab
3. Click on an Activity Selection
4. Click on any Year (1-10)
5. Click "Spatial Features" button

### Step 2: Draw a Feature
1. Select an activity from dropdown
2. Enter feature name (required)
3. Select a year
4. Choose feature type: Point, Line, or Polygon
5. Click "Start Drawing"
6. Click on map to draw:
   - **Point:** Single click
   - **Line:** Click multiple points, double-click to finish
   - **Polygon:** Click multiple points (min 3), double-click to close

### Step 3: Edit Features
1. Find feature in "Drawn Features" list
2. Click "Edit" button
3. Click on map to add vertex OR
4. Feature highlights with orange dashed line
5. Click vertices to move them
6. Click "Stop Editing" when done

### Step 4: Copy Feature to Another Year
1. In Drawn Features list, click the feature
2. In "Feature Options" panel, click target year button (Y1, Y2, etc.)
3. Feature is duplicated to that year

### Step 5: Delete Feature
1. Click "Delete" button next to feature
2. Confirm in pop-up

---

## Map Controls

### Base Maps
Three maps available via dropdown:
- **Satellite** (default) - Esri World Imagery
- **Street Map** - OpenStreetMap
- **Topographic** - OpenTopoMap

### Layers Displayed
When viewing Spatial Features:
- Forest boundary (gray outline)
- Blocks (blue, 5 blocks)
- Sub-areas (by category colors)
- Activity features (by category)

### Measurements
Live measurements shown while drawing:
- **Line:** Length in meters/feet
- **Polygon:** Area in m²/ha or acres

Unit toggle switches between Metric/Imperial.

---

## Technical Notes

### Geometry Format

**Coordinate Order:** GeoJSON uses [longitude, latitude] = [x, y]

```javascript
// Point
{ "type": "Point", "coordinates": [85.0411, 27.4426] }

// LineString  
{ "type": "LineString", "coordinates": [[85.0411, 27.4426], [85.0415, 27.4430], ...] }

// Polygon (ring must close)
{ "type": "Polygon", "coordinates": [[ [85.0411, 27.4426], [85.0415, 27.4430], [85.0411, 27.4426] ]] }
```

**Storage:** Coordinates stored as WKT in database (PostGIS geometry)

---

## Known Issues & Fixes

### Issue: Polygon Disappears After Double-Click
**Symptom:** Polygon draws but disappears when double-clicking to finish.

**Likely Cause:** Backend shapely.Polygon() parse error.

**Fix Applied:** Backend now handles nested polygon coordinates:
```python
# In yearly_activities.py, update_drawn_feature
ring = coords[0] if coords[0] and isinstance(coords[0][0], list) else coords
geom = shapely.Polygon(ring)
```

**If still occurring:**
1. Check console log: `[createPolygon] saving geometry:`
2. Check backend logs for shapely error
3. Verify geometry format matches GeoJSON spec

### Issue: Edit Vertex Causes 500 Error
**Symptom:** Backend returns 500 when adding/moving vertex.

**Fix:** Backend now handles polygon coordinate extraction.

### Issue: Features Display Incorrectly (Vertically Stretched)
**Cause:** Coordinate order mismatch - [lat, lng] vs [lng, lat]

**Fix:** parseGeometry converts [lng, lat] → [lat, lng] for Leaflet display, but saves as [lng, lat] for GeoJSON.

---

## File Changes

### Frontend Files Modified
| File | Purpose |
|------|---------|
| `ActivityMapView.tsx` | Main view with layers, base maps |
| `DrawingCanvas.tsx` | Drawing, edit, measurements |

### Backend Files Modified
| File | Purpose |
|------|---------|
| `yearly_activities.py` | Updated polygon handling |

---

## Testing Checklist

- [ ] Draw point - appears on map
- [ ] Draw line - appears, shows length while drawing
- [ ] Draw polygon - appears, shows area while drawing
- [ ] Double-click finishes drawing
- [ ] Feature saved in database
- [ ] Feature appears after page refresh
- [ ] Edit button works
- [ ] Add vertex to line works
- [ ] Add vertex to polygon works
- [ ] Copy to year works
- [ ] Delete feature works
- [ ] Base map switching works
- [ ] Layer display (boundary, blocks, sub-areas)

---

## Backup & Restore

**Backup Branch:** `backup-before-spatial-features-v2`

To restore:
```bash
git checkout backup-before-spatial-features-v2
```

---

## Future Improvements

1. [ ] Undo/redo for drawing
2. [ ] Snap to grid
3. [ ] Measurement in acres toggle
4. [ ] Export to KML/GeoJSON
5. [ ] Color by year gradient
6. [ ] Labels on map