# Per-Block Sampling Parameter Overrides - Implementation Guide

## Overview

This feature allows users to specify different sampling parameters for individual forest blocks within the same calculation. This is crucial for resource-intensive sampling design work where different blocks may require different sampling intensities or methodologies.

**Implementation Date**: February 8, 2026
**Status**: Backend Complete, Frontend Pending

---

## Database Schema Changes

### Migration: `7c7fdcb9a324_add_block_overrides_to_sampling_designs.py`

Added two JSONB columns to `sampling_designs` table:

```sql
-- Default parameters applied to all blocks unless overridden
ALTER TABLE public.sampling_designs
ADD COLUMN default_parameters JSONB;

-- Block-specific parameter overrides
ALTER TABLE public.sampling_designs
ADD COLUMN block_overrides JSONB;

-- GIN index for efficient JSON queries
CREATE INDEX idx_sampling_block_overrides
ON public.sampling_designs USING gin(block_overrides);
```

### Data Structure

**default_parameters**:
```json
{
  "sampling_type": "systematic",
  "sampling_intensity_percent": 0.5,
  "min_samples_per_block": 5,
  "min_samples_small_blocks": 2,
  "boundary_buffer_meters": 50.0,
  "min_distance_meters": null
}
```

**block_overrides**:
```json
{
  "Block 1": {
    "sampling_intensity_percent": 1.0,
    "min_samples_per_block": 10
  },
  "Block 2": {
    "sampling_type": "random",
    "boundary_buffer_meters": 100.0
  },
  "Ward 5": {
    "sampling_intensity_percent": 0.3,
    "min_samples_per_block": 3
  }
}
```

---

## Backend Implementation

### 1. Schema Updates (`backend/app/schemas/sampling.py`)

Added `BlockOverride` schema for type safety:

```python
class BlockOverride(BaseModel):
    """Per-block sampling parameter overrides"""
    sampling_type: Optional[Literal["systematic", "random", "stratified"]] = None
    sampling_intensity_percent: Optional[Decimal] = Field(None, ge=0.1, le=10.0)
    min_samples_per_block: Optional[int] = Field(None, ge=2, le=20)
    boundary_buffer_meters: Optional[float] = Field(None, ge=0.0, le=200.0)
    min_distance_meters: Optional[int] = Field(None, ge=5, le=500)
```

Updated `SamplingDesignBase` to include:

```python
block_overrides: Optional[Dict[str, BlockOverride]] = Field(
    None,
    description="Per-block parameter overrides. Key is block name (e.g., 'Block 1')"
)
```

Updated `SamplingDesign` response schema:

```python
default_parameters: Optional[Dict[str, Any]] = None
block_overrides: Optional[Dict[str, Any]] = None
```

### 2. Service Layer Updates (`backend/app/services/sampling.py`)

**Function signature updated**:
```python
def create_sampling_design(
    # ... existing parameters ...
    block_overrides: Optional[dict] = None
) -> SamplingGenerateResponse:
```

**Key logic changes**:

1. **Build default parameters dictionary** (lines ~428-436):
```python
default_parameters = {
    "sampling_type": sampling_type,
    "sampling_intensity_percent": float(sampling_intensity_percent),
    "min_samples_per_block": min_samples_per_block,
    "min_samples_small_blocks": min_samples_small_blocks,
    "boundary_buffer_meters": boundary_buffer_meters,
    "min_distance_meters": min_distance_meters
}
```

2. **Apply block-specific overrides** (lines ~453-467):
```python
for block_number, block_wkt, block_name, block_area_ha in blocks:
    # Apply block-specific overrides if they exist
    block_sampling_type = sampling_type
    block_intensity_percent = sampling_intensity_percent
    block_min_samples_per_block = min_samples_per_block
    # ... other parameters ...

    if block_overrides and block_name in block_overrides:
        override = block_overrides[block_name]
        block_sampling_type = override.get("sampling_type", sampling_type)
        block_intensity_percent = Decimal(str(override.get("sampling_intensity_percent", sampling_intensity_percent)))
        # ... apply other overrides ...
        logger.info(f"  Applying overrides for {block_name}: {override}")

    # Use block-specific parameters for point generation
    # ...
```

3. **Save to database** (lines ~558-593):
```python
# Save default parameters
if default_parameters:
    update_defaults_query = text("""
        UPDATE public.sampling_designs
        SET default_parameters = CAST(:params AS jsonb)
        WHERE id = :design_id
    """)
    db.execute(update_defaults_query, {
        "params": json.dumps(default_parameters),
        "design_id": str(sampling_design.id)
    })

# Save block overrides
if block_overrides:
    # Convert to JSON-serializable format
    serializable_overrides = {}
    for block_name, override_params in block_overrides.items():
        if hasattr(override_params, 'model_dump'):
            serializable_overrides[block_name] = override_params.model_dump(exclude_none=True)
        else:
            serializable_overrides[block_name] = override_params

    update_overrides_query = text("""
        UPDATE public.sampling_designs
        SET block_overrides = CAST(:overrides AS jsonb)
        WHERE id = :design_id
    """)
    db.execute(update_overrides_query, {
        "overrides": json.dumps(serializable_overrides),
        "design_id": str(sampling_design.id)
    })
```

### 3. API Endpoint Updates (`backend/app/api/sampling.py`)

Updated `create_sampling` endpoint to convert Pydantic models to dicts:

```python
# Convert block_overrides from Pydantic models to dicts if present
block_overrides_dict = None
if request.block_overrides:
    block_overrides_dict = {}
    for block_name, override in request.block_overrides.items():
        if hasattr(override, 'model_dump'):
            block_overrides_dict[block_name] = override.model_dump(exclude_none=True)
        elif hasattr(override, 'dict'):
            block_overrides_dict[block_name] = override.dict(exclude_none=True)
        else:
            block_overrides_dict[block_name] = override

# Pass to service layer
summary = create_sampling_design(
    # ... other params ...
    block_overrides=block_overrides_dict
)
```

---

## API Usage

### Create Sampling Design with Block Overrides

**Endpoint**: `POST /api/forests/calculations/{calculation_id}/sampling/create`

**Request Body**:
```json
{
  "sampling_type": "systematic",
  "sampling_intensity_percent": 0.5,
  "min_samples_per_block": 5,
  "min_samples_small_blocks": 2,
  "boundary_buffer_meters": 50.0,
  "plot_shape": "circular",
  "plot_radius_meters": 12.6156,
  "notes": "Custom sampling with block-specific parameters",
  "block_overrides": {
    "Block 1": {
      "sampling_intensity_percent": 1.0,
      "min_samples_per_block": 10
    },
    "Block 2": {
      "sampling_type": "random",
      "boundary_buffer_meters": 100.0
    },
    "Ward 5": {
      "sampling_intensity_percent": 0.3,
      "min_samples_per_block": 3
    }
  }
}
```

**Response**:
```json
{
  "sampling_design_id": "uuid-here",
  "calculation_id": "uuid-here",
  "sampling_type": "systematic",
  "total_points": 45,
  "total_blocks": 3,
  "forest_area_hectares": 125.5,
  "requested_intensity_percent": 0.5,
  "actual_intensity_per_hectare": 0.358,
  "blocks_info": [
    {
      "block_number": 1,
      "block_name": "Block 1",
      "block_area_hectares": 50.2,
      "samples_generated": 25,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.99
    },
    {
      "block_number": 2,
      "block_name": "Block 2",
      "block_area_hectares": 45.8,
      "samples_generated": 12,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.52
    }
  ]
}
```

### Get Sampling Design (includes parameters)

**Endpoint**: `GET /api/sampling/{design_id}`

**Response**:
```json
{
  "id": "uuid-here",
  "calculation_id": "uuid-here",
  "sampling_type": "systematic",
  "total_points": 45,
  "created_at": "2026-02-08T12:00:00Z",
  "updated_at": "2026-02-08T12:00:00Z",
  "default_parameters": {
    "sampling_type": "systematic",
    "sampling_intensity_percent": 0.5,
    "min_samples_per_block": 5,
    "boundary_buffer_meters": 50.0
  },
  "block_overrides": {
    "Block 1": {
      "sampling_intensity_percent": 1.0,
      "min_samples_per_block": 10
    },
    "Block 2": {
      "sampling_type": "random",
      "boundary_buffer_meters": 100.0
    }
  }
}
```

---

## Testing

### Test Script

Run the included test script to verify functionality:

```bash
cd D:\forest_management
.\venv\Scripts\python test_block_overrides.py
```

**Prerequisites**:
1. Backend server must be running on port 8001
2. Must have a user account (email: newuser@example.com)
3. Must have at least one calculation with uploaded boundary

**Test Steps**:
1. Login to get access token
2. Find a calculation with multiple blocks
3. Create sampling design with block overrides
4. Verify parameters were stored correctly
5. Check per-block sampling results

### Manual Testing

1. **Restart backend** to pick up code changes:
```bash
cd D:\forest_management\backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001
```

2. **Test via API docs**: Navigate to http://localhost:8001/docs

3. **Use the test script** as shown above

---

## Frontend Implementation (PENDING)

### Required UI Components

1. **Block Selection Interface** (`frontend/src/components/SamplingTab.tsx`):
   - Display list of all blocks in calculation
   - Checkbox to enable per-block customization
   - Expandable sections for each block

2. **Default Parameters Section**:
   - Input fields for default sampling parameters
   - Applied to all blocks unless overridden
   - Clear visual distinction from overrides

3. **Block Override Sections**:
   - Only shown when block is selected for override
   - Same parameter inputs as default section
   - Visual indicator showing which parameters are overridden
   - "Reset to default" button for each block

4. **Summary View**:
   - Table showing sampling parameters per block
   - Highlight blocks with overrides
   - Show expected sample counts before generation

### Proposed UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ Sampling Design Configuration                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Default Parameters (applied to all blocks)              │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Sampling Type:     [Systematic ▼]                   │ │
│ │ Intensity (%):     [0.5]                            │ │
│ │ Min Samples:       [5]                              │ │
│ │ Boundary Buffer:   [50m]                            │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ Per-Block Overrides (optional)                          │
│ ☑ Enable block-specific parameters                      │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ▼ Block 1 (50.2 ha)                    [Override]   │ │
│ │   ┌──────────────────────────────────────────────┐  │ │
│ │   │ Intensity (%):  [1.0]  ← Overridden          │  │ │
│ │   │ Min Samples:    [10]   ← Overridden          │  │ │
│ │   │ Other params:   Using defaults                │  │ │
│ │   │                          [Reset to Default]   │  │ │
│ │   └──────────────────────────────────────────────┘  │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ ▶ Block 2 (45.8 ha)                    [Override]   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ Summary Table                                           │
│ ┌────────┬───────┬──────────┬────────┬────────────────┐ │
│ │ Block  │ Area  │ Type     │ Intens.│ Est. Samples   │ │
│ ├────────┼───────┼──────────┼────────┼────────────────┤ │
│ │ Block 1│ 50.2  │Systematic│ 1.0% ⚡│ ~25            │ │
│ │ Block 2│ 45.8  │Systematic│ 0.5%   │ ~11            │ │
│ │ Block 3│ 30.0  │Systematic│ 0.5%   │ ~7             │ │
│ └────────┴───────┴──────────┴────────┴────────────────┘ │
│                                                          │
│                     [Generate Sampling Design]           │
└─────────────────────────────────────────────────────────┘

Legend: ⚡ = Overridden parameter
```

### Implementation Steps

1. **Fetch block information** from calculation result_data
2. **Build form state** with default parameters and empty overrides
3. **Handle override toggles** for each block
4. **Validate parameters** before submission
5. **Build request payload** with block_overrides dictionary
6. **Submit to API** and handle response
7. **Display results** showing per-block statistics

---

## Files Modified

### Backend
- `backend/alembic/versions/7c7fdcb9a324_add_block_overrides_to_sampling_designs.py` (NEW)
- `backend/app/models/sampling.py` (lines 49-56)
- `backend/app/schemas/sampling.py` (lines 7-33, 87-91, 156-162)
- `backend/app/services/sampling.py` (lines 359-375, 428-510, 558-593)
- `backend/app/api/sampling.py` (lines 81-99)

### Testing
- `test_block_overrides.py` (NEW)
- `BLOCK_OVERRIDES_IMPLEMENTATION.md` (NEW - this file)

### Frontend (PENDING)
- `frontend/src/components/SamplingTab.tsx` (to be modified)
- `frontend/src/types/sampling.ts` (to be created/updated)

---

## Migration Instructions

### For Existing Installations

1. **Stop backend server**:
```bash
# Press Ctrl+C in terminal running uvicorn
```

2. **Run database migration**:
```bash
cd D:\forest_management\backend
..\venv\Scripts\alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade 2749022978b3 -> 7c7fdcb9a324, add_block_overrides_to_sampling_designs
Added default_parameters and block_overrides columns to sampling_designs
```

3. **Restart backend server**:
```bash
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001
```

4. **Verify migration**:
```bash
..\venv\Scripts\alembic current
```

Should show: `7c7fdcb9a324 (head)`

5. **Test functionality**:
```bash
cd D:\forest_management
.\venv\Scripts\python test_block_overrides.py
```

---

## Known Limitations

1. **Frontend UI not yet implemented**: Users must use API directly or wait for UI implementation
2. **No validation of block names**: API accepts any string as block name - must match exactly with calculation blocks
3. **No migration of existing designs**: Existing sampling designs will have NULL values for default_parameters and block_overrides
4. **Override precedence**: Overrides completely replace default values - no partial merging within individual parameters

---

## Future Enhancements

1. **Block name autocomplete**: API endpoint to list available block names for a calculation
2. **Template management**: Save and reuse block override configurations
3. **Validation warnings**: Warn if override block name doesn't match any actual blocks
4. **Visual preview**: Show sampling points on map colored by block before generation
5. **Bulk operations**: Apply same override to multiple blocks at once
6. **Export/import**: Save block override configurations as JSON files

---

## Support

For issues or questions:
1. Check backend logs for detailed error messages
2. Verify migration was applied: `alembic current`
3. Test with `test_block_overrides.py` script
4. Review API docs at http://localhost:8001/docs

---

**Last Updated**: February 8, 2026
**Status**: Backend Complete ✓ | Frontend Pending ⏳
