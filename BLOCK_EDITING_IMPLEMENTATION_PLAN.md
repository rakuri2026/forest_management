# Block Vertex Editing Implementation Plan

## Overview
Implement block boundary vertex editing (add, move, delete) similar to sub-area editing, with automatic clipping of sub-areas when they fall outside the block boundary after edits.

## User Requirements Summary

### 1. Block Vertex Editing Capabilities
- **Move vertices**: Drag existing vertices to new positions
- **Add vertices**: Click on edge to add new vertex
- **Delete vertices**: Select vertex and delete
- **Create new blocks**: Split existing blocks with new division lines

### 2. Constraints
- **Outer block vertices = Forest boundary vertices**: Moving outer vertices must also update forest boundary
- **Inner block vertices**: Can be edited independently
- **Sub-area auto-clipping**: When block boundary changes, sub-areas outside the new boundary are automatically clipped to fit

### 3. Area Impact
- Moving shared vertices affects area of adjacent blocks
- Sub-areas that become invalid are clipped (not deleted)

---

## Implementation Plan

### Phase 1: UI Infrastructure for Block Editing

**Frontend Changes:**

1. **Create BlockEditor Component** (`frontend/src/components/BlockEditor.tsx`)
   - Similar structure to MapEditor but for block editing
   - Render all blocks with editing controls
   - Handle vertex editing events

2. **Add "Edit Blocks" mode in MapEditor**
   - New mode: `mode: 'edit_boundary' | 'edit_blocks' | 'edit_subareas'`
   - Toggle between boundary/blocks/sub-areas editing

3. **Block Layer Properties**
   ```typescript
   interface Block {
     id: string;
     name: string;
     geometry: GeoJSON.Polygon;
     area_hectares: number;
     is_outer: boolean;  // true if this block shares boundary with forest boundary
   }
   ```

### Phase 2: Vertex Editing Events

**Frontend Changes:**

1. **Setup Leaflet-Geoman controls for blocks**
   ```typescript
   mapInstance.pm.addControls({
     editMode: true,
     drawPolygon: false,
     removalMode: true,
   });
   ```

2. **Handle pm:editstart, pm:edit, pm:editend events**
   - Track which block is being edited
   - For each vertex change, check if it's an outer or inner vertex
   - Update block geometry in real-time

3. **Distinguish Outer vs Inner Vertices**
   - Compare block vertices with forest boundary vertices
   - Outer vertices: shared with forest boundary → update forest boundary too
   - Inner vertices: only affect the block being edited

### Phase 3: Sub-Area Auto-Clipping Logic

**Backend Implementation (Python):**

1. **New endpoint or extend existing:**
   - Modify `PATCH /sub-areas/{sub_area_id}` or create new block update endpoint
   - Add `clip_to_block: bool` parameter

2. **Clipping Algorithm:**
   ```python
   def clip_subarea_to_block(subarea_geometry, block_geometry):
       """
       Clip sub-area to block boundary using Shapely
       """
       from shapely.geometry import shape, mapping
       
       subarea = shape(subarea_geometry)
       block = shape(block_geometry)
       
       # Intersection = clipped sub-area
       clipped = subarea.intersection(block)
       
       if clipped.is_empty:
           return None  # Sub-area completely outside
       
       return mapping(clipped)  # Return GeoJSON
   ```

3. **Integration with Block Update:**
   - After block geometry is updated
   - Loop through all sub-areas
   - For each sub-area:
     - Check if it's within new block boundary
     - If not, clip to block
     - Update sub-area geometry in database

### Phase 4: Save Flow

**Frontend (BlockEditor.tsx):**

1. **On vertex edit complete:**
   ```typescript
   // After pm:editend
   const handleBlockEdit = async (editedBlockId, newGeometry) => {
     // 1. Update block geometry
     await forestApi.updateBlock(calculationId, editedBlockId, {
       geometry: newGeometry
     });
     
     // 2. Backend will automatically clip sub-areas
     // 3. Return updated sub-areas in response
   };
   ```

2. **Update Forest Boundary:**
   - If outer vertices changed, also update `calculation.geometry`

**Backend (forests.py):**

1. **New endpoint: `PATCH /blocks/{block_id}`**
   ```python
   @router.patch("/calculations/{calculation_id}/blocks/{block_id}")
   async def update_block(...):
       # 1. Update block geometry
       # 2. Check if it's an outer block
       # 3. If outer, also update forest boundary
       # 4. Clip all sub-areas to new block boundaries
       # 5. Recalculate block and sub-area areas
       # 6. Return updated data
   ```

### Phase 5: Validation & Warnings

**Frontend - Real-time Feedback:**

1. **Show warnings during editing:**
   - "This vertex is shared with forest boundary - moving it will update the outer boundary"
   - "This change will affect X adjacent block(s)"
   - "Y sub-area(s) will be clipped to fit within block"

2. **Area recalculation:**
   - Update block area in real-time as vertices are moved
   - Show area change delta

---

## Data Flow

```
User edits block vertex
       ↓
Frontend: Detect outer vs inner vertex
       ↓
If outer: Queue forest boundary update
       ↓
Frontend: Send block geometry to backend
       ↓
Backend: Update block geometry
       ↓
Backend: Check all sub-areas against new block
       ↓
For sub-areas outside:
  Backend: Clip to block boundary
       ↓
Backend: Save all updates, recalculate areas
       ↓
Frontend: Reload and display updated data
       ↓
User sees updated blocks and clipped sub-areas
```

---

## API Endpoints

### New Endpoints

1. **Update Block Geometry**
   ```
   PATCH /api/forests/calculations/{id}/blocks/{block_id}
   Body: {
     geometry: GeoJSON,
     update_boundary: boolean  // true if outer vertex changed
   }
   Response: {
     success: true,
     block: {...},
     clipped_sub_areas: [...],  // List of sub-areas that were clipped
     forest_boundary: {...}  // Updated if outer block
   }
   ```

2. **Get Block with Sub-areas**
   ```
   GET /api/forests/calculations/{id}/blocks/{block_id}
   Response: {
     block: {...},
     sub_areas: [...]
   }
   ```

### Modified Endpoints

1. **List Blocks** - Add sub-areas to response
   ```
   GET /api/forests/calculations/{id}/blocks
   ```

---

## Files to Modify

### Backend
1. `backend/app/api/forests.py`
   - Add `update_block` endpoint
   - Add `clip_subarea_to_block` function
   - Modify block update to handle sub-area clipping

2. `backend/app/schemas/forest.py`
   - Add `BlockUpdateRequest` schema

### Frontend
1. `frontend/src/components/BlockEditor.tsx` (NEW)
   - New component for block editing
   - Similar to MapEditor structure

2. `frontend/src/pages/CalculationDetail.tsx`
   - Add "Edit Blocks" button/mode
   - Integrate BlockEditor component

3. `frontend/src/services/api.ts`
   - Add `updateBlock`, `getBlock` API methods

4. `frontend/src/utils/geometryValidation.ts`
   - Add `isOuterVertex`, `findAdjacentBlocks` functions

---

## Implementation Priority

1. **P0 - Core**
   - Render blocks with editing controls
   - Handle vertex add/move/delete
   - Update block geometry in database

2. **P1 - Important**
   - Detect outer vs inner vertices
   - Update forest boundary for outer vertices
   - Auto-clip sub-areas

3. **P2 - Nice to Have**
   - Real-time area display
   - Adjacent block area updates
   - Validation warnings

---

## Testing Scenarios

1. **Single block - move outer vertex**
   - Block's outer edge should match forest boundary
   - Both should update together

2. **Multiple blocks - move inner vertex**
   - Only the affected block should change
   - Adjacent block should not change

3. **Multiple blocks - move outer vertex**
   - Block boundary updates
   - Forest boundary updates
   - Other blocks not affected

4. **Sub-area clipping**
   - Create sub-area within block
   - Move block vertex to exclude sub-area area
   - Sub-area should be clipped to new block boundary

5. **Sub-area completely outside**
   - Create sub-area near block edge
   - Move block vertex to completely exclude sub-area
   - Sub-area should be clipped to smallest remaining area (or handle gracefully)

---

## Summary

This implementation will allow users to:
1. Edit block boundaries with full vertex control
2. See automatic forest boundary updates for outer vertices
3. Have sub-areas automatically clipped when they fall outside block boundaries
4. Maintain data integrity without losing user-entered sub-area data
