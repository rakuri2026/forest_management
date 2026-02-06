# Backend Testing Guide - Per-Block Sampling

## Quick Start

### Step 1: Restart Backend Server

```bash
cd D:\forest_management\backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Look for:**
- ✓ "Application startup complete"
- ✓ No import errors
- ✓ Server running on http://localhost:8001

---

## Step 2: Get Authentication Token

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"demo@forest.com\",\"password\":\"Demo1234\"}"
```

**Save the `access_token` from response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**Set environment variable (Windows CMD):**
```cmd
set TOKEN=eyJhbGc...
```

---

## Step 3: Find a Calculation with Blocks

```bash
curl "http://localhost:8001/api/forests/calculations" \
  -H "Authorization: Bearer %TOKEN%"
```

**Look for a calculation with multiple blocks:**
```json
{
  "id": "01455ee4-3b2a-46c0-a49d-e99d8b25edcf",
  "forest_name": "Test Forest",
  "result_data": {
    "blocks": [
      {"block_name": "Block A", "area_hectares": 150.5},
      {"block_name": "Block B", "area_hectares": 75.2},
      {"block_name": "Block C", "area_hectares": 1.8}
    ]
  }
}
```

**Save the calculation ID:**
```cmd
set CALC_ID=01455ee4-3b2a-46c0-a49d-e99d8b25edcf
```

---

## Step 4: Create Systematic Sampling (NEW API)

```bash
curl -X POST "http://localhost:8001/api/calculations/%CALC_ID%/sampling/create" \
  -H "Authorization: Bearer %TOKEN%" \
  -H "Content-Type: application/json" \
  -d "{\"sampling_type\":\"systematic\",\"sampling_intensity_percent\":0.5,\"min_samples_per_block\":5,\"min_samples_small_blocks\":2,\"plot_shape\":\"circular\",\"plot_radius_meters\":12.6156}"
```

---

## Expected Response (Success)

```json
{
  "sampling_design_id": "uuid-here",
  "calculation_id": "uuid-here",
  "sampling_type": "systematic",
  "total_points": 130,
  "total_blocks": 3,
  "forest_area_hectares": 227.5,
  "requested_intensity_percent": 0.5,
  "actual_intensity_per_hectare": 0.571,
  "sampling_percentage": 0.285,
  "plot_area_sqm": 500.0,
  "total_sampled_area_hectares": 0.65,

  "blocks_info": [
    {
      "block_number": 1,
      "block_name": "Block A",
      "block_area_hectares": 150.5,
      "samples_generated": 75,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.498
    },
    {
      "block_number": 2,
      "block_name": "Block B",
      "block_area_hectares": 75.2,
      "samples_generated": 50,
      "minimum_enforced": false,
      "actual_intensity_percent": 0.664
    },
    {
      "block_number": 3,
      "block_name": "Block C",
      "block_area_hectares": 1.8,
      "samples_generated": 5,
      "minimum_enforced": true,    ← KEY: Minimum was enforced!
      "actual_intensity_percent": 2.778
    }
  ]
}
```

---

## What to Verify

### ✓ Check 1: Total Points
- Sum of all blocks' `samples_generated` = `total_points`
- Example: 75 + 50 + 5 = 130 ✓

### ✓ Check 2: Minimum Enforcement
- **Block C** (1.8 ha, small):
  - Without minimum: 1.8 × 0.5% / 0.05 ha = 0.18 samples → 0 samples
  - With minimum: 5 samples ✓
  - `minimum_enforced: true` ✓

### ✓ Check 3: Large Blocks
- **Block A** (150.5 ha):
  - 150.5 × 0.5% / 0.05 ha = 15.05 samples → 75 samples (systematic grid)
  - `minimum_enforced: false` (didn't need it) ✓

### ✓ Check 4: Intensity Adjustment
- Block C actual intensity: 2.778%
- This is (5 samples × 0.05 ha / 1.8 ha) × 100 = 2.78% ✓

---

## Test Scenarios

### Test 1: Very Small Block (<1 ha)

**Expected:**
- Should get `min_samples_small_blocks` (default 2)
- `minimum_enforced: true`

### Test 2: Large Block (>100 ha)

**Expected:**
- Should get samples from intensity calculation
- `minimum_enforced: false`

### Test 3: Custom Minimums

```json
{
  "min_samples_per_block": 8,
  "min_samples_small_blocks": 3
}
```

**Expected:**
- Large blocks: minimum 8 samples
- Small blocks: minimum 3 samples

### Test 4: Random Sampling

```bash
curl -X POST "http://localhost:8001/api/calculations/%CALC_ID%/sampling/create" \
  -H "Authorization: Bearer %TOKEN%" \
  -H "Content-Type: application/json" \
  -d "{\"sampling_type\":\"random\",\"sampling_intensity_percent\":1.0,\"min_samples_per_block\":10,\"plot_shape\":\"circular\"}"
```

**Expected:**
- Random point distribution
- Still enforces minimum per block

---

## Error Cases to Test

### 1. Invalid Minimum (>10)
```json
{
  "min_samples_per_block": 15
}
```
**Expected:** HTTP 422 validation error

### 2. Invalid Intensity (>10%)
```json
{
  "sampling_intensity_percent": 15.0
}
```
**Expected:** HTTP 422 validation error

### 3. Missing Plot Configuration
```json
{
  "sampling_type": "systematic",
  "plot_shape": null
}
```
**Expected:** HTTP 400 error

---

## Automated Test Script

Run the Python test script:

```bash
cd D:\forest_management
venv\Scripts\python test_sampling_backend.py
```

This will:
1. Login automatically
2. Find a test calculation
3. Run multiple sampling tests
4. Verify results
5. Test error cases

---

## Success Criteria

Before proceeding to frontend updates, verify:

- [ ] ✓ Backend starts without errors
- [ ] ✓ Systematic sampling creates points per block
- [ ] ✓ Minimum samples enforced for small blocks
- [ ] ✓ `blocks_info` array includes all blocks
- [ ] ✓ `minimum_enforced` flag is correct
- [ ] ✓ Grid spacing calculated automatically (no manual input)
- [ ] ✓ Random sampling works with minimums
- [ ] ✓ Validation rejects invalid parameters
- [ ] ✓ Response includes `requested_intensity_percent`

---

## Common Issues

### Issue: "No calculation with blocks found"
**Fix:** Upload a forest boundary that creates multiple blocks (multi-polygon)

### Issue: "Sampling design already exists"
**Fix:** Delete existing design first or use different calculation

### Issue: Import errors on startup
**Fix:** Check that all files were saved correctly, restart server

### Issue: Grid generates 0 points
**Fix:** Block might be too small for grid spacing - check logs

---

## Next Steps After Testing

Once all tests pass:
1. Update frontend `SamplingTab.tsx` with new parameters
2. Update `api.ts` to send new fields
3. Update UI to display per-block results
4. Add warnings when minimum is enforced

---

**Ready to test?**

1. Start backend server
2. Run: `venv\Scripts\python test_sampling_backend.py`
3. Review results
4. Report any errors for fixing
