# Forest Block Vertex Editing Problems

## Context
We have a Community Forest Management System with:
- **Forest Boundary**: The outer perimeter of the entire forest
- **Forest Blocks**: Sub-divisions within the forest (can be single or multiple)
- **Sub-areas**: Special zones within blocks (protected, plantation, etc.)

## Current Implementation
- Frontend: React + Leaflet + Leaflet-Geoman
- Backend: FastAPI + PostgreSQL/PostGIS

## Problems to Solve

### Problem A: Cannot Select/Delete Vertices
**Current behavior**: User can move vertices (drag) but cannot:
- Click to select a vertex (make it turn red)
- Delete a selected vertex with Delete key

**Expected**: User should be able to click on a vertex to select it, then press Delete to remove it.

**What we tried**:
- Added `removalMode: true` to Geoman controls
- Added `vertexDeletion: true` 
- Tried enabling layer editing explicitly

---

### Problem B: Vertex Moves Not Persisting to Database
**Current behavior**: 
1. User moves vertex in Edit Blocks mode
2. Local state updates (area recalculates)
3. Click "Save Block Changes" - shows "Saved ✓"
4. Navigate away and come back - vertex is back at original position

**Expected**: Moved vertices should persist in database after save.

**Current flow**:
- Frontend sends block geometry to `PATCH /api/forests/calculations/{id}/update-blocks`
- Backend updates `result_data.blocks` in database
- On reload, blocks are loaded from `result_data`

**Likely cause**: Either:
- The geometry is not being sent correctly from frontend
- Or the frontend is loading original blocks instead of edited ones

---

### Problem C: Outer Block Vertices ≠ Forest Boundary
**Current behavior**: When user moves a vertex on the outer edge of a block (which should match the forest boundary), only the block geometry updates. The forest boundary (`calculation.boundary_geom` and `calculation.geometry`) is NOT updated.

**Expected**: 
- When user moves outer block vertex → update BOTH block AND forest boundary
- The forest boundary should always match the outer edge of all blocks combined

**Implementation needed**:
- Detect which vertices are "outer" (shared with forest boundary)
- When saving, if outer vertices changed, also update forest boundary geometry

---

### Problem D: Shared Vertices Between Adjacent Blocks
**Current behavior**: When Block A and Block B share a common boundary (internal edge), they share some vertices at the same coordinates. If user moves one of these shared vertices, only ONE block's vertex moves. This creates:
- Gaps between blocks (if vertices move apart)
- Overlapping blocks (if vertices cross each other)

**Expected**: 
- When user moves a vertex on an internal boundary → BOTH adjacent blocks should move their shared vertex simultaneously
- This maintains topological integrity (no gaps, no overlaps)

**Example**:
```
Block A: [(0,0), (10,0), (10,10), (0,10)]
Block B: [(10,0), (20,0), (20,10), (10,10)]

Shared vertices at: (10,0), (10,10)

If user moves (10,0) to (10,5) for Block A:
- Block A becomes: [(0,0), (10,0), (10,10), (0,10)]
- Block B should ALSO become: [(10,5), (20,0), (20,10), (10,10)]
- Otherwise there's a gap between them
```

**Implementation approaches considered**:
1. **Simultaneous editing**: When vertex is moved, find all blocks sharing that coordinate and update all of them
2. **Constraint-based editing**: Use PostGIS topology to maintain relationships
3. **Visual feedback**: Show warning when move would create gap/overlap

---

## Technical Details

### Frontend Code (MapEditor.tsx)
- Mode: `'edit_blocks'`
- Blocks rendered with `pmIgnore: false` for editing
- Events handled: `pm:editstart`, `pm:edit`, `pm:editend`
- Block layers have `_blockId` property for identification

### Backend Endpoint
- `PATCH /api/forests/calculations/{id}/update-blocks`
- Receives: `{ blocks: [...], update_boundary: boolean }`
- Updates: `calculation.result_data['blocks']`

### Data Structure
```javascript
// Block in frontend
{
  block_id: "preview-0",
  block_name: "Block 1", 
  geometry: { type: "Polygon", coordinates: [...] },
  area_hectares: 100.5,
  index: 0
}

// Forest boundary
{
  type: "MultiPolygon",  // or Polygon
  coordinates: [...]
}
```

---

## Questions for Research

1. How to properly enable vertex selection and deletion in Leaflet-Geoman for GeoJSON layers?
2. How to sync multiple polygon vertices in Leaflet-Geoman when they share coordinates?
3. Best approach to detect "outer" vs "inner" vertices in a polygon?
4. How to persist geometry changes correctly in React state + database?

---

## Success Criteria

After solving these problems:
1. ✅ User can select vertices and delete them
2. ✅ Moved vertices persist after page reload
3. ✅ Outer block boundary moves update forest boundary
4. ✅ Internal shared vertices move together on all adjacent blocks
