# Location Search Feature for Manual Digitization

**Date:** 2026-03-08
**Status:** ✅ Ready to Integrate
**Purpose:** Help users find their digitizing area using administrative boundaries

---

## Overview

When digitizing forest boundaries manually, users need to quickly find their target area. This feature provides multiple ways to locate and zoom to specific areas using Nepal's administrative hierarchy (Province → District → Municipality → Ward).

---

## Features Implemented

### 1. **Cascading Dropdown Search** ⭐
**Best for:** Users who know the administrative location
- Select Province → District → Municipality → Ward
- Auto-loads child administrativelevel when parent is selected
- Displays ward numbers for easy identification
- Automatically zooms map to selected ward bounds

### 2. **Text Search with Autocomplete** ⭐
**Best for:** Quick location finding
- Type any part of province, district, or municipality name
- Shows top 10 matching results
- Displays full administrative path (Province, District, Municipality, Ward)
- Click result to zoom to location

### 3. **Ward Boundary Display** ⭐
**Best for:** Visual reference while digitizing
- Show/hide ward boundary on map
- Helps users stay within correct area
- Yellow outline for easy visibility
- Toggle on/off with eye icon

### 4. **Satellite Base Map** ⭐
**Best for:** Natural feature identification
- Switch to satellite imagery
- Essential for following rivers, ridges, etc.
- Toggle between street map and satellite

---

## API Endpoints Created

### Backend: `/api/location/*`

```
GET /api/location/provinces
GET /api/location/districts?province_code={code}
GET /api/location/municipalities?district_code={code}
GET /api/location/wards?municipality_code={code}
GET /api/location/search?q={query}&limit=10
GET /api/location/ward/{ward_id}/geometry
```

**File:** `backend/app/api/location_search.py` (360 lines)

---

## Frontend Component

**File:** `frontend/src/components/MapCreation/LocationSearch.tsx` (400+ lines)

### Props

```typescript
interface LocationSearchProps {
  // Called when user selects a location - zooms map to bounds
  onLocationSelected: (bounds: [number, number, number, number], geometry?: any) => void;

  // Optional: Called when user toggles ward boundary display
  onBoundaryToggle?: (show: boolean, geometry?: any) => void;
}
```

### Usage Example

```typescript
import LocationSearch from './components/MapCreation/LocationSearch';

function MapCreationPage() {
  const handleLocationSelected = (bounds: [number, number, number, number]) => {
    // Zoom map to bounds [minLon, minLat, maxLon, maxLat]
    map.fitBounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]]);
  };

  const handleBoundaryToggle = (show: boolean, geometry: any) => {
    if (show && geometry) {
      // Add GeoJSON layer to map
      L.geoJSON(geometry, {
        style: { color: '#fbbf24', weight: 2, fillOpacity: 0.1 }
      }).addTo(map);
    } else {
      // Remove boundary layer
    }
  };

  return (
    <LocationSearch
      onLocationSelected={handleLocationSelected}
      onBoundaryToggle={handleBoundaryToggle}
    />
  );
}
```

---

## Additional Options Available

### Option 1: **Geocoding Service (External)**

Add place name search using OpenStreetMap Nominatim:

```typescript
const searchNominatim = async (query: string) => {
  const response = await fetch(
    `https://nominatim.openstreetmap.org/search?` +
    `q=${query}&format=json&countrycodes=np&limit=5`
  );
  const results = await response.json();
  return results;
};
```

**Pros:**
- Finds specific locations (schools, temples, landmarks)
- Works with local names
- Free and open source

**Cons:**
- Requires internet connection
- Rate limited (1 request/second)
- May not have all local names

### Option 2: **GPS Coordinate Input**

Add manual lat/lon entry:

```typescript
interface CoordinateInputProps {
  onCoordinatesEntered: (lat: number, lon: number) => void;
}

// User enters: 27.7172, 85.3240 (Kathmandu)
// Map zooms to those coordinates
```

**Use case:** Users with GPS coordinates from field visits

### Option 3: **Recent Locations History**

Store last 10 searched locations in localStorage:

```typescript
const saveToHistory = (location: SearchResult) => {
  const history = JSON.parse(localStorage.getItem('locationHistory') || '[]');
  history.unshift(location);
  localStorage.setItem('locationHistory', JSON.stringify(history.slice(0, 10)));
};
```

**Benefits:** Quick access to frequently used areas

### Option 4: **Bookmark Favorite Locations**

Allow users to save favorite locations:

```typescript
interface Bookmark {
  id: string;
  name: string;
  bounds: [number, number, number, number];
  created_at: string;
}

// User can name bookmarks: "My Forest Area", "Project Site 1", etc.
```

### Option 5: **Nearby Community Forests Search**

Show existing community forests in selected ward:

```typescript
GET /api/location/ward/{ward_id}/community-forests

// Returns list of existing forests in that ward
// Helps avoid overlaps and find adjacent forests
```

**Database:** Uses existing `admin.community_forests` table (3,922 forests)

### Option 6: **Draw Area Search**

Let users draw a rough area on map to search:

```typescript
// User draws rectangle or circle
// System finds wards that intersect with drawn area
// Returns list of matching wards
```

**Use case:** User knows general location but not exact ward

### Option 7: **Elevation Filter**

Filter wards by elevation range:

```typescript
GET /api/location/wards?min_elevation=2000&max_elevation=3500

// Useful for high-altitude vs terai forests
```

### Option 8: **Distance from Point**

Find wards within X km of a point:

```typescript
GET /api/location/wards/nearby?lat=27.7&lon=85.3&radius_km=5

// Find all wards within 5km of coordinates
```

---

## Satellite Base Map Integration

### Option A: **OpenStreetMap Satellite** (Free)

```typescript
import { TileLayer } from 'react-leaflet';

<TileLayer
  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
  attribution='&copy; OpenStreetMap contributors'
/>

// Switch to satellite:
<TileLayer
  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
  attribution='&copy; Esri'
/>
```

### Option B: **Google Maps Satellite** (Requires API Key)

```typescript
<TileLayer
  url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
  attribution='&copy; Google Maps'
/>
```

### Option C: **Mapbox Satellite** (Requires Account)

```typescript
<TileLayer
  url="https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}.png?access_token={token}"
  attribution='&copy; Mapbox'
/>
```

**Recommended:** Use Esri World Imagery (free, good quality, no API key needed)

---

## Integration Steps

### 1. Add to Map Creation Wizard

In `frontend/src/components/MapCreation/MapCreationWizard.tsx`:

```typescript
import LocationSearch from './LocationSearch';
import BaseMapSelector from './BaseMapSelector'; // For satellite toggle

// Add to Step 1 (Boundary Drawing)
{currentStep === 1 && (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
    {/* Left sidebar - Location Search */}
    <div className="lg:col-span-1">
      <LocationSearch
        onLocationSelected={handleLocationSelected}
        onBoundaryToggle={handleBoundaryToggle}
      />
      <BaseMapSelector onBaseMapChange={handleBaseMapChange} />
    </div>

    {/* Map */}
    <div className="lg:col-span-2">
      <MapContainer>
        {/* Existing map code */}
      </MapContainer>
    </div>
  </div>
)}
```

### 2. Handle Location Selection

```typescript
const handleLocationSelected = (bounds: [number, number, number, number]) => {
  if (mapRef.current) {
    // Zoom to ward bounds
    mapRef.current.fitBounds([
      [bounds[1], bounds[0]],  // Southwest corner
      [bounds[3], bounds[2]]   // Northeast corner
    ]);
  }
};
```

### 3. Handle Boundary Display

```typescript
const [wardBoundaryLayer, setWardBoundaryLayer] = useState<any>(null);

const handleBoundaryToggle = (show: boolean, geometry: any) => {
  if (wardBoundaryLayer) {
    mapRef.current?.removeLayer(wardBoundaryLayer);
    setWardBoundaryLayer(null);
  }

  if (show && geometry) {
    const layer = L.geoJSON(geometry, {
      style: {
        color: '#fbbf24',    // Yellow
        weight: 2,
        fillOpacity: 0.1,
        dashArray: '5, 5'    // Dashed line
      }
    });
    layer.addTo(mapRef.current!);
    setWardBoundaryLayer(layer);
  }
};
```

### 4. Add Satellite Base Map Toggle

Create `frontend/src/components/MapCreation/BaseMapSelector.tsx`:

```typescript
import React, { useState } from 'react';
import { Map, Satellite } from 'lucide-react';

interface BaseMapSelectorProps {
  onBaseMapChange: (type: 'street' | 'satellite') => void;
}

const BaseMapSelector: React.FC<BaseMapSelectorProps> = ({ onBaseMapChange }) => {
  const [baseMap, setBaseMap] = useState<'street' | 'satellite'>('street');

  const handleChange = (type: 'street' | 'satellite') => {
    setBaseMap(type);
    onBaseMapChange(type);
  };

  return (
    <div className="mt-4 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Base Map</h3>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => handleChange('street')}
          className={`px-3 py-2 rounded flex items-center justify-center gap-2 ${
            baseMap === 'street'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <Map className="w-4 h-4" />
          Street
        </button>
        <button
          onClick={() => handleChange('satellite')}
          className={`px-3 py-2 rounded flex items-center justify-center gap-2 ${
            baseMap === 'satellite'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <Satellite className="w-4 h-4" />
          Satellite
        </button>
      </div>
    </div>
  );
};

export default BaseMapSelector;
```

---

## Testing the Feature

### 1. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

### 2. Test API Endpoints
```bash
# Get provinces
curl http://localhost:8001/api/location/provinces

# Search
curl "http://localhost:8001/api/location/search?q=kathmandu&limit=5"

# Get ward geometry
curl http://localhost:8001/api/location/ward/1/geometry
```

### 3. Start Frontend
```bash
cd frontend
npm run dev
```

### 4. Test UI
1. Go to Upload/Map Creation
2. Use dropdown to select Province → District → Municipality → Ward
3. Map should zoom to selected ward
4. Try text search: type "kathmandu"
5. Toggle ward boundary on/off
6. Switch to satellite base map

---

## Database Requirements

### Required Table: `admin.wards`

```sql
-- Expected columns
province_code VARCHAR
province_name VARCHAR
province_name_nepali VARCHAR
district_code VARCHAR
district_name VARCHAR
district_name_nepali VARCHAR
municipality_code VARCHAR
municipality_name VARCHAR
municipality_name_nepali VARCHAR
municipality_type VARCHAR  -- Metropolitan, Municipality, Rural Municipality
ward_no INTEGER
geom GEOMETRY(MultiPolygon, 4326)
```

If table structure is different, adjust the SQL queries in `backend/app/api/location_search.py`

---

## Next Steps

1. **Integrate into Map Creation Wizard** - Add LocationSearch component to Step 1
2. **Add Base Map Selector** - Create satellite/street map toggle
3. **Test with Real Data** - Verify ward table has correct data
4. **Optional Enhancements** - Add any of the 8 additional options listed above

---

## Benefits

✅ **Faster digitization** - Users find their area quickly
✅ **Fewer errors** - Ward boundaries prevent mistakes
✅ **Better UX** - Both browse and search options
✅ **Satellite imagery** - Essential for natural boundaries
✅ **Reference layer** - Ward boundary helps stay in bounds

---

**Status:** Ready to integrate into map creation workflow!
