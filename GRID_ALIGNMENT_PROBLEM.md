# Grid Overlay Alignment Problem - Research Document

## Executive Summary

The Community Forest Management System has a grid overlay feature on the Compartment Tab that displays a grid representing mother tree selection cells. However, the grid visually displayed on the map does **not align** with the actual `grid_cell_id` values stored in the database. Two mother trees with different `grid_cell_id` values (e.g., 1506 and 1611) appear in the same visual grid cell when they should be in different cells.

---

## Background: How Mother Trees Are Generated

### Overview

When trees are uploaded via the **Tree Mapping** inventory system, the backend creates a grid over the forest area and assigns each eligible tree to a grid cell. From each cell containing trees, one tree is selected as the "Mother Tree" (the tree closest to the cell's centroid).

### Eligibility Criteria

Only trees with **DBH > 30 cm** are eligible for mother tree selection:

| DBH Range | Classification | Mother Tree Eligible |
|-----------|----------------|---------------------|
| 0.1-4 cm | Regeneration | No |
| 4-10 cm | Sapling | No |
| 10-30 cm | Pole | No |
| >30 cm | Tree | **Yes** |

---

## Backend Algorithm (PostGIS-Based)

The primary method used in the Tree Mapping tab is in `backend/app/services/inventory.py` (lines 927-1117):

### Step 1: Get Eligible Trees

Transform tree locations to projected CRS (UTM zone for Nepal):

```sql
SELECT id, ST_Transform(location::geometry, :projection_epsg) AS geom_proj
FROM public.inventory_trees
WHERE inventory_calculation_id = :inventory_id
  AND dia_cm > 30
  AND remark != 'Seedling';
```

### Step 2: Get Bounding Box in Projected CRS

```sql
SELECT 
    ST_XMin(ST_Extent(geom_proj)) AS xmin,
    ST_YMin(ST_Extent(geom_proj)) AS ymin,
    ST_XMax(ST_Extent(geom_proj)) AS xmax,
    ST_YMax(ST_Extent(geom_proj)) AS ymax
FROM temp_eligible_trees;
```

### Step 3: Generate Grid Cells

Two approaches - first tries `ST_SquareGrid` (PostGIS 3.1+), falls back to manual:

```sql
-- Manual Grid Generation (Fallback - most common)
WITH RECURSIVE x_series AS (
    SELECT :xmin + generate_series(0, CAST((:xmax - :xmin) / :grid_size AS INTEGER)) * :grid_size AS x
),
y_series AS (
    SELECT :ymin + generate_series(0, CAST((:ymax - :ymin) / :grid_size AS INTEGER)) * :grid_size AS y
)
SELECT 
    row_number() OVER () AS cell_id,
    ST_SetSRID(ST_MakeEnvelope(x, y, x + :grid_size, y + :grid_size), :projection_epsg) AS geom
FROM x_series, y_series;
```

### Key Points About Grid Generation:

1. **Origin**: Grid starts from `(xmin, ymin)` - the **lower-left corner** of the bounding box of eligible trees only (DBH > 30cm)
2. **Iteration Order**: 
   - Inner loop: `y += grid_spacing_meters` (goes UP first)
   - Outer loop: `x += grid_spacing_meters` (then goes RIGHT)
3. **Cell ID Assignment**:
   - Cell ID starts at **0**
   - First row (ymin) gets IDs 0, 1, 2, ..., (numCols-1)
   - Second row gets IDs numCols, numCols+1, ...
   - Formula: `cell_id = row * numCols + col`

### Step 4: Find Cells Containing Trees

```sql
SELECT DISTINCT g.cell_id, g.centroid
FROM temp_grid_cells g
JOIN temp_eligible_trees t ON ST_Intersects(g.geom, t.geom_proj);
```

### Step 5: Assign Mother Trees

```sql
WITH nearest_trees AS (
    SELECT DISTINCT ON (c.cell_id)
        c.cell_id,
        t.id AS tree_id
    FROM temp_cells_with_trees c
    CROSS JOIN LATERAL (
        SELECT id, ST_Distance(c.centroid, geom_proj) AS distance
        FROM temp_eligible_trees
        ORDER BY ST_Distance(c.centroid, geom_proj)
        LIMIT 1
    ) t
)
UPDATE public.inventory_trees
SET 
    remark = 'Mother Tree',
    grid_cell_id = nt.cell_id
FROM nearest_trees nt
WHERE inventory_trees.id = nt.tree_id;
```

**Result**: Each grid cell that contains trees gets exactly **one mother tree** (the tree closest to the cell's centroid).

---

## Current Problem

### What Happens Now

The frontend (`CompartmentTab.tsx`) attempts to draw a grid overlay but:

1. **Calculates grid from lat/lon bounds** - This is an approximation
2. **Uses meter-to-degree conversion** - Not precise because:
   - 1° latitude ≈ 111,320 meters (constant)
   - 1° longitude ≈ 111,320 × cos(latitude) meters (varies by latitude)
3. **Doesn't know exact `numCols`** - Number of columns in the grid
4. **Doesn't know exact origin** - The (xmin, ymin) in projected CRS

### Symptoms

- Two mother trees with different `grid_cell_id` values appear in the same visual grid cell
- Example: Trees with `grid_cell_id = 1506` and `grid_cell_id = 1611` show at position X=15, Y=36 on the map

### User Observations

1. From lower-left, user sees approximately **5 vertical × 4 horizontal** grids
2. Grid cell difference 1611 - 1506 = **105** suggests `numCols ≈ 105`
3. Another pair: 1291 - 1187 = **104**

### Database Evidence

- Cell ID range: **4 to 6256** (but only **678 unique** cells have trees)
- Grid spacing: **20 meters** (stored in `inventory_calculations.grid_spacing_meters`)
- Projection: UTM zone (e.g., EPSG:32645 for Nepal)

---

## What We've Tried

| Approach | Description | Result |
|----------|-------------|--------|
| Geographic-based grid | Calculate grid from lat/lon bounds of eligible trees | 60×106 grid drawn but doesn't align |
| Cell ID difference analysis | Analyze consecutive cell_id differences to detect numCols | Found 104 or 105 as potential numCols |
| Different numCols values | Tested 60, 104, 105 columns | Still doesn't match |
| Different origin points | Used bounds of all trees vs. trees with grid_cell_id | Still misalignment |

---

## Required Solution

To correctly replicate the backend grid in the frontend, we need:

### Option 1: Store Grid Metadata in Database

Add columns to track grid creation parameters:

```sql
ALTER TABLE public.inventory_calculations ADD COLUMN IF NOT EXISTS grid_origin_x FLOAT;
ALTER TABLE public.inventory_calculations ADD COLUMN IF NOT EXISTS grid_origin_y FLOAT;
ALTER TABLE public.inventory_calculations ADD COLUMN IF NOT EXISTS grid_num_cols INTEGER;
```

Return these values via API so frontend can draw exact grid.

### Option 2: Replicate Algorithm in Frontend

The frontend must:

1. **Get eligible tree coordinates in projected CRS**
   - Either from API (with projection info)
   - Or compute the exact same bounding box

2. **Recreate the grid** with:
   - Same origin: `(xmin_proj, ymin_proj)` - lower-left corner
   - Same iteration order: y (UP) first, then x (RIGHT)
   - Same formula: `cell_id = row * numCols + col`

3. **Transform to WGS84** for display:
   - Convert grid cell corners from Projected CRS back to lat/lon
   - Draw grid lines at those converted positions

### Key Challenge

The frontend doesn't have access to:
- The exact bounding box in projected CRS
- The exact number of columns (numCols)
- The grid origin coordinates

This information needs to come from the backend API.

---

## Files Involved

### Backend
- `backend/app/services/inventory.py` - Mother tree identification algorithm (lines 927-1117)
- `backend/app/api/compartments.py` - Returns tree data including `grid_cell_id`
- `backend/app/models/inventory.py` - InventoryTree model with `grid_cell_id` field

### Frontend  
- `frontend/src/components/Compartment/CompartmentTab.tsx` - GridOverlay component (lines 27-162)
- `frontend/src/services/api.ts` - API client for tree data

---

## Questions for Research

1. How can we exactly replicate the PostGIS grid generation algorithm in JavaScript/TypeScript?
2. What's the best way to pass grid metadata (origin, numCols) from backend to frontend?
3. Is there a PostGIS equivalent we can call from the API to get grid cell boundaries?
4. How do we accurately convert between projected CRS and WGS84 in the frontend?

---

## Latest Attempt (2026-04-07)

### Approach: Hardcoded numCols = 105

Based on user observation that 1611 - 1506 = 105, tried using numCols = 105.

**Code changes:**
- Hardcoded `numCols = 105`
- Grid origin from eligible tree bounds (DBH >= 30)
- Grid extent = numCols × spacing (not tree extent)
- Added debug labels for cell IDs 1506, 1611, 1291, 1187

**Result:**
- Grid does NOT cover the tree extent
- 2 mother trees appear in same cell

### Analysis

The problem has multiple aspects:
1. **Grid doesn't cover trees** - The grid is drawn too small
2. **Two mother trees in same cell** - Either the visual shows wrong positions, OR there's actually a bug in backend

Possible causes:
- The grid origin is wrong (not matching backend's origin)
- The numCols is not 105
- The formula for cell_id might be different
- The grid spacing might vary (especially if using ST_SquareGrid)

### Mathematical Approach to Solve

If we know where a tree with a specific grid_cell_id should be, and we know its actual lat/lon, we can solve for the grid origin.

For tree at (lat, lon) with grid_cell_id = X:
- If `cell_id = row * numCols + col`
- Then `col = cell_id % numCols` and `row = floor(cell_id / numCols)`
- And the tree should be at: `lon = origin_lon + (col + 0.5) * spacingLon` (center of cell)
- `lat = origin_lat + (row + 0.5) * spacingLat`

We can use multiple trees to solve for origin_lat and origin_lon!

---

## References

- PostGIS Documentation: ST_SquareGrid, ST_MakeEnvelope, ST_Transform
- Backend code: `backend/app/services/inventory.py` - `_identify_mother_trees_postgis` method
- Nepal UTM Zones: EPSG:32645 (Zone 45N) for eastern Nepal
