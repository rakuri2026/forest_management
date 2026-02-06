# Sampling System Upgrade - Per-Block Minimum Enforcement

## Date: February 6, 2026
## Status: ✅ IMPLEMENTED

---

## Problem Identified

The previous sampling system generated samples for the **entire forest** without considering individual blocks. This caused issues:

**Example Problem:**
```
Forest with 3 blocks (0.5% intensity, random sampling):
❌ Block A (150 ha): 75 samples
❌ Block B (100 ha): 50 samples
❌ Block C (2 ha):   1 sample  ← NOT STATISTICALLY VALID!
```

**Forestry Rule Violation:**
- **Minimum 5 samples per block (for blocks ≥ 1 hectare)**
- **Minimum 2 samples for small blocks (< 1 hectare)**

---

## New Solution: Per-Block Sampling

### ✅ Changes Implemented

1. **Sampling Intensity as Percentage** (instead of grid spacing)
   - Input: `sampling_intensity_percent` (default: 0.5%)
   - System calculates grid spacing automatically
   - More intuitive for foresters

2. **Minimum Samples Enforcement**
   - Configurable: 2-10 samples
   - Default: **5 samples** for blocks ≥ 1 hectare
   - Default: **2 samples** for blocks < 1 hectare
   - Automatically enforced per block

3. **Per-Block Generation**
   - Samples generated separately for each block
   - Ensures proper spatial distribution
   - Works for systematic, random, and stratified sampling

---

## New API Parameters

### Request Parameters

```json
{
  "sampling_type": "systematic",
  "sampling_intensity_percent": 0.5,          // NEW: % of block area
  "min_samples_per_block": 5,                 // NEW: Min for blocks ≥1ha
  "min_samples_small_blocks": 2,              // NEW: Min for blocks <1ha
  "plot_shape": "circular",
  "plot_radius_meters": 12.6156,              // Default 500m² plot
  "notes": "Systematic sampling"
}
```

### Deprecated Parameters
- `intensity_per_hectare` - Use `sampling_intensity_percent` instead
- `grid_spacing_meters` - Calculated automatically

---

## Response Format

### New Per-Block Information

```json
{
  "sampling_design_id": "uuid",
  "sampling_type": "systematic",
  "total_points": 130,
  "total_blocks": 3,
  "forest_area_hectares": 252.0,
  "requested_intensity_percent": 0.5,
  "actual_intensity_per_hectare": 0.516,
  "sampling_percentage": 0.258,

  "blocks_info": [
    {
      "block_number": 1,
      "block_name": "Block A",
      "block_area_hectares": 150.0,
      "samples_generated": 75,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.50
    },
    {
      "block_number": 2,
      "block_name": "Block B",
      "block_area_hectares": 100.0,
      "samples_generated": 50,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.50
    },
    {
      "block_number": 3,
      "block_name": "Block C",
      "block_area_hectares": 2.0,
      "samples_generated": 5,
      "minimum_enforced": true,           // ⚠️ Minimum enforced!
      "actual_intensity_percent": 2.50    // Adjusted from 0.5% to 2.5%
    }
  ]
}
```

---

## How It Works

### Algorithm

```
For each block in forest:

    1. Determine minimum samples:
       if block_area < 1 ha:
           minimum = min_samples_small_blocks (default 2)
       else:
           minimum = min_samples_per_block (default 5)

    2. Calculate samples from intensity:
       sample_area = block_area × (intensity% / 100)
       samples_from_intensity = sample_area / plot_area

    3. Apply maximum:
       final_samples = max(minimum, samples_from_intensity)

    4. Generate points:
       - For systematic: calculate grid spacing to get final_samples
       - For random: generate final_samples random points
       - For stratified: distribute final_samples across strata

    5. Store with block assignment
```

### Grid Spacing Calculation (Systematic)

```python
block_area_sqm = block_area_ha × 10,000
spacing_meters = sqrt(block_area_sqm / num_samples)
```

**Example:**
- Block: 100 ha = 1,000,000 m²
- Target: 50 samples
- Spacing: √(1,000,000 / 50) = √20,000 = 141 meters

---

## Testing Examples

### Example 1: Large Forest with Mixed Block Sizes

**Input:**
```
Forest: 3 blocks
- Block A: 150 ha
- Block B: 100 ha
- Block C: 2 ha
Intensity: 0.5%
Plot size: 500m² (circular, r=12.62m)
Min samples: 5 (large), 2 (small)
```

**Calculation:**
```
Block A: 150 ha × 0.5% = 0.75 ha sample area
         0.75 ha / 0.05 ha = 15 samples ✓ (>5)

Block B: 100 ha × 0.5% = 0.50 ha sample area
         0.50 ha / 0.05 ha = 10 samples ✓ (>5)

Block C: 2 ha × 0.5% = 0.01 ha sample area
         0.01 ha / 0.05 ha = 0.2 samples → 0 samples
         Apply minimum: 5 samples ✓

Total: 15 + 10 + 5 = 30 samples
```

### Example 2: Very Small Block

**Input:**
```
Block: 0.8 ha (<1 ha)
Intensity: 0.5%
Min small blocks: 2
```

**Calculation:**
```
0.8 ha × 0.5% = 0.004 ha sample area
0.004 ha / 0.05 ha = 0.08 samples → 0 samples
Apply minimum: 2 samples ✓ (small block rule)
```

### Example 3: Systematic Grid Spacing

**Input:**
```
Block: 100 ha
Target: 50 samples
```

**Grid Calculation:**
```
Area: 100 ha = 1,000,000 m²
Spacing: √(1,000,000 / 50) = 141 meters
Result: 7×7 grid ≈ 49-50 points ✓
```

---

## User Interface Updates Needed

### Sampling Form (Frontend)

**Replace grid spacing input with:**
```
┌─────────────────────────────────────────────┐
│ Sampling Intensity: [0.5] %                 │
│ (percentage of block area to sample)        │
│                                             │
│ Minimum Samples:                            │
│ • Large blocks (≥1 ha): [5] samples         │
│ • Small blocks (<1 ha): [2] samples         │
│                                             │
│ Plot Configuration:                         │
│ Shape: (•) Circular  ( ) Square             │
│ Radius: [12.62] meters (500m² plot)         │
└─────────────────────────────────────────────┘
```

### Results Display

**Show per-block breakdown:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sampling Design Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: Systematic
Requested Intensity: 0.5%
Total Points: 130 samples

Block Distribution:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Block A (150 ha): 75 samples (0.50%)
Block B (100 ha): 50 samples (0.50%)
Block C (2 ha):   5 samples (2.50%) ⚠️

⚠️ Note: Block C intensity adjusted from 0.5% to 2.5%
         to meet minimum 5 samples requirement

Total Sampled: 0.258% of forest area
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Benefits

### ✅ Statistical Validity
- Each block has adequate sample size
- Meets forestry standards (min 5 samples)
- Better confidence intervals

### ✅ Flexible Configuration
- Adjustable minimums (2-10 range)
- Different rules for small vs large blocks
- User can override defaults

### ✅ Better User Experience
- Intuitive intensity percentage
- Automatic grid spacing calculation
- Clear per-block feedback

### ✅ Forestry Best Practices
- Systematic sampling preferred
- Block-wise stratification
- Proper spatial distribution

---

## Testing Checklist

- [ ] **Single large block** (>100 ha) with 0.5% intensity
- [ ] **Single small block** (<1 ha) with 0.5% intensity
- [ ] **Multi-block forest** with mixed sizes
- [ ] **Very small block** (0.5 ha) - should get 2 samples
- [ ] **Systematic sampling** - verify grid spacing is calculated
- [ ] **Random sampling** - verify minimum enforced
- [ ] **Custom minimums** (e.g., min=3 for small, min=8 for large)
- [ ] **Response includes blocks_info** array
- [ ] **Frontend displays** per-block breakdown
- [ ] **Export works** with new data structure

---

## Migration Notes

### Backward Compatibility

Old API calls using `grid_spacing_meters` or `intensity_per_hectare` will:
1. Log a deprecation warning
2. Use default `sampling_intensity_percent = 0.5%`
3. Still work but recommend update

### Database

No migration needed - existing `sampling_designs` table compatible.
New field `points_block_assignment` stores per-block data.

---

## Next Steps

1. **Update Frontend UI** to show new parameters
2. **Add validation warnings** in UI when minimum is enforced
3. **Update documentation** and user guides
4. **Test with real forest data**
5. **Get user feedback** from foresters

---

## Files Modified

### Backend
- `backend/app/schemas/sampling.py` - New parameters and response
- `backend/app/services/sampling.py` - Per-block generation logic
- `backend/app/api/sampling.py` - Updated endpoint

### Frontend (TODO)
- `frontend/src/components/SamplingTab.tsx` - Update form
- `frontend/src/services/api.ts` - Update API calls

---

**Implementation completed:** February 6, 2026
**Ready for testing:** Yes
**Ready for production:** After frontend updates and testing
