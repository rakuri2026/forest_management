# Spatial Features Implementation - Prompt Format

**Version:** 1.0
**Date:** April 15, 2026

---

## PROMPT 1: Set Up Project Structure

```
Create frontend components for Spatial Features:
- ActivityMapView.tsx in /components/YearlyActivities/
- DrawingCanvas.tsx in /components/YearlyActivities/

These components handle:
1. Display map with forest layers
2. Drawing spatial features (point, line, polygon)
3. Editing existing features
4. Base map switching
```

**Files to create:**
- `frontend/src/components/YearlyActivities/ActivityMapView.tsx`
- `frontend/src/components/YearlyActivities/DrawingCanvas.tsx`

---

## PROMPT 2: Add Base Maps

```
In ActivityMapView.tsx, add base map selector:

const BASE_MAPS = {
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Esri'
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap'
  },
  topo: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap'
  }
};

Use default: 'satellite'
```

---

## PROMPT 3: Load Forest Layers

```
In ActivityMapView.tsx, load and display layers:

1. Fetch calculation boundary:
   const calcData = await forestApi.getCalculation(calculationId);
   setBoundaryGeometry(calcData.geometry);

2. Fetch blocks:
   const blocksData = await forestApi.getBlocks(calculationId);
   setBlockLayers(blocksData.blocks);

3. Fetch sub-areas:
   const subAreasData = await forestApi.listSubAreas(calculationId);
   setSubAreaLayers(subAreasData.sub_areas);

4. Render with GeoJSON in MapContainer
```

---

## PROMPT 4: Coordinate Conversion

```
In DrawingCanvas.tsx, create coordinate parser:

function parseGeometry(geometry, featureType):
  # GeoJSON uses [lng, lat], Leaflet needs [lat, lng]
  # MUST convert for display
  
  if featureType == 'point':
    return [[coords[1], coords[0]]]    # [lng, lat] → [lat, lng]
  elif featureType == 'line':
    return coords.map(c => [c[1], c[0]])
  elif featureType == 'polygon':
    ring = coords[0]
    return ring.map(c => [c[1], c[0]])
```

**IMPORTANT:** When saving, convert BACK to [lng, lat] format!

---

## PROMPT 5: Draw Point

```
In DrawingCanvas.tsx:

function createPoint(latlng):
  geometry = JSON.stringify({
    type: 'Point',
    coordinates: [latlng.lng, latlng.lat]   # [lng, lat] for GeoJSON
  })
  
  await yearlyActivitiesApi.createDrawnFeature(activityId, {
    feature_type: 'point',
    geometry,
    properties: { name, year }
  })
```

---

## PROMPT 6: Draw Line

```
In DrawingCanvas.tsx:

function createLine(currentPoints):
  # currentPoints is array of LatLng objects
  coordinates = currentPoints.map(p => [p.lng, p.lat])  # [lng, lat]
  
  # Calculate length
  length = currentPoints.reduce((acc, p, i) => {
    return acc + (i > 0 ? currentPoints[i-1].distanceTo(p) : 0)
  }, 0)
  
  geometry = JSON.stringify({
    type: 'LineString',
    coordinates
  })
  
  await yearlyActivitiesApi.createDrawnFeature(activityId, {
    feature_type: 'line',
    geometry,
    properties: { length_m: Math.round(length), name, year }
  })
```

---

## PROMPT 7: Draw Polygon

```
In DrawingCanvas.tsx:

function createPolygon(currentPoints):
  # Must close polygon (add first point at end)
  coords = currentPoints.map(p => [p.lng, p.lat])
  firstPoint = currentPoints[0]
  lastPoint = currentPoints[currentPoints.length - 1]
  
  if firstPoint.distanceTo(lastPoint) > 1:
    coords.push([firstPoint.lng, firstPoint.lat])
  
  # Calculate area using simple bounding box
  polygon = L.polygon(currentPoints.map(p => [p.lat, p.lng]))
  bounds = polygon.getBounds()
  latSpan = bounds.getNorthEast().lat - bounds.getSouthWest().lat
  lngSpan = bounds.getNorthEast().lng - bounds.getSouthWest().lng
  areaSqM = Math.abs(latSpan * 111320) * Math.abs(lngSpan * 111320)
  
  geometry = JSON.stringify({
    type: 'Polygon',
    coordinates: [coords]
  })
  
  await yearlyActivitiesApi.createDrawnFeature(activityId, {
    feature_type: 'polygon',
    geometry,
    properties: { area_sqm: Math.round(areaSqM), name, year }
  })
```

---

## PROMPT 8: Live Measurements

```
In DrawingCanvas.tsx:

function calculateMeasurements(currentPoints, featureType):
  if featureType == 'line' and len >= 2:
    length = calculate distance between all points
    display in overlay: "{length.toFixed(1)} m"
  elif featureType == 'polygon' and len >= 3:
    area = calculate polygon area
    display in overlay: "{area.toFixed(1)} m² ({hectares} ha)"
```

---

## PROMPT 9: Display Features on Map

```
In DrawingCanvas.tsx:

function renderFeatures(drawnFeatures):
  for each feature in drawnFeatures:
    coords = parseGeometry(feature.geometry, feature.feature_type)
    
    if feature_type == 'point':
      return <Marker position={[coords[0][0], coords[0][1]]} />
    elif feature_type == 'line':
      return <Polyline positions={coords} color="#e11d48" weight={3} />
    elif feature_type == 'polygon':
      return <Polygon positions={coords[0]} color="#059669" fillOpacity={0.3} />
```

---

## PROMPT 10: Edit Feature - Add Vertex

```
In DrawingCanvas.tsx handleMapClickForEdit:

function handleMapClickForEdit(latlng):
  coords = parseGeometry(editingFeature.geometry, editingFeature.feature_type)
  
  if feature_type == 'line':
    # Convert [lat, lng] back to [lng, lat]
    coordsLngLat = coords.map(c => [c[1], c[0]])
    coordsLngLat.push([latlng.lng, latlng.lat])
    
    newGeometry = JSON.stringify({
      type: 'LineString',
      coordinates: coordsLngLat
    })
    
    # MUST send feature_type in update
    await yearlyActivitiesApi.updateDrawnFeature(activityId, featureId, {
      geometry: newGeometry,
      feature_type: 'line'   # IMPORTANT!
    })
```

**CRITICAL:** Always send `feature_type` in update request!

---

## PROMPT 11: Backend Geometry Handler

```
In backend yearly_activities.py update_drawn_feature:

function update_drawn_feature(feature_data):
  geojson = json.loads(feature_data.geometry)
  coords = geojson["coordinates"]
  
  if feature_data.feature_type == "point":
    geom = shapely.Point(coords)
  elif feature_data.feature_type == "line":
    geom = shapely.LineString(coords)
  elif feature_data.feature_type == "polygon":
    # Handle nested array for polygon
    ring = coords[0] if coords[0] and isinstance(coords[0][0], list) else coords
    geom = shapely.Polygon(ring)
  
  feature.geometry = geom.wkt
  db.commit()
```

---

## PROMPT 12: Render Boundary/Blocks/Sub-areas

```
In ActivityMapView.tsx MapContainer:

<TileLayer url={BASE_MAPS[baseMap].url} />

{/* Boundary */}
{boundaryGeometry && (
  <GeoJSON data={boundaryGeometry} style={{color: '#666', weight: 2}} />
)}

{/* Blocks */}
{blockLayers.map((block, i) => (
  <GeoJSON key={i} data={block.geometry} style={{color: '#2563eb', fillOpacity: 0.15}} />
))}

{/* Sub-areas by category */}
{subAreaLayers.map((subArea, i) => (
  <GeoJSON 
    key={i} 
    data={subArea.geometry} 
    style={{color: CATEGORY_COLORS[subArea.category]}} 
  />
))}
```

---

## PROMPT 13: Test Checklist

After implementation, verify:

- [ ] Map loads with satellite default
- [ ] Can switch OSM/TOPO maps
- [ ] Boundary layer displays
- [ ] Block layers display (blue)
- [ ] Sub-area layers display (by category color)
- [ ] Can draw point (single click)
- [ ] Can draw line (double-click to finish)
- [ ] Can draw polygon (double-click to close)
- [ ] Polygon appears on map (not disappear!)
- [ ] Live length shows while drawing line
- [ ] Live area shows while drawing polygon
- [ ] Drawn features appear in list
- [ ] Click Edit, then click map adds vertex (line)
- [ ] Copy to year works
- [ ] Delete feature works
- [ ] Auto-fit zooms to layers

---

## Quick Reference: Coordinate Flow

```
DRAWING:
  User click in Leaflet → [lat, lng]
  ↓
  createLine() converts to [lng, lat] for GeoJSON
  ↓
  Save to database

DISPLAYING:
  Database stores: [lng, lat] (WKT)
  ↓
  parseGeometry() converts to [lat, lng]
  ↓
  Leaflet renders: [lat, lng] ✓

EDITING:
  Click on map → [lat, lng]
  ↓
  Convert to [lng, lat]
  ↓
  Send to API with feature_type
  ↓
  Backend handles correctly
```

---

*Use these prompts as step-by-step implementation guide*