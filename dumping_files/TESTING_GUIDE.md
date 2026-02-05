# Tree Inventory Testing Guide

## Quick Start

The server should be running at: **http://localhost:8001**

### 1. Check Server Status
```bash
curl http://localhost:8001/health
```

Expected response:
```json
{"status":"healthy","database":"connected","version":"1.0.0"}
```

### 2. View API Documentation
Open in browser: **http://localhost:8001/docs**

This shows all available endpoints with interactive testing interface.

---

## Authentication

### Register a Test User
```bash
curl -X POST "http://localhost:8001/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email":"tester@example.com",
    "password":"TestPass123",
    "full_name":"Test User"
  }'
```

### Login to Get Token
```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email":"tester@example.com",
    "password":"TestPass123"
  }'
```

**Save the access_token from the response!**

---

## Testing Inventory Upload

### Using the token (replace YOUR_TOKEN):
```bash
TOKEN="YOUR_TOKEN_HERE"
```

### 1. List Available Species
```bash
curl -X GET "http://localhost:8001/api/inventory/species" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Download Template
```bash
curl -X GET "http://localhost:8001/api/inventory/template" \
  -H "Authorization: Bearer $TOKEN" \
  -o TreeInventory_Template.csv
```

### 3. Upload Valid Inventory
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/valid_inventory.csv" \
  -F "grid_spacing_meters=20.0"
```

Expected response structure:
```json
{
  "summary": {
    "total_rows": 10,
    "valid_rows": 10,
    "error_count": 0,
    "warning_count": 0,
    "ready_for_processing": true
  },
  "data_detection": {
    "columns_detected": {...},
    "crs": {...},
    "diameter_type": {...}
  },
  "errors": [],
  "warnings": [],
  "info": [],
  "corrections": [],
  "inventory_id": "uuid-here",
  "next_step": "POST /api/inventory/{inventory_id}/process"
}
```

### 4. Test with Typo Species Names
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/typo_species.csv" \
  -F "grid_spacing_meters=20.0"
```

Should show warnings with fuzzy match suggestions.

### 5. Test with Girth Measurements
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/girth_measurements.csv" \
  -F "grid_spacing_meters=20.0"
```

Should detect girth and show conversion info.

### 6. Test with UTM Coordinates
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/utm_coordinates.csv" \
  -F "grid_spacing_meters=20.0" \
  -F "projection_epsg=32644"
```

Should detect UTM zone 44N.

### 7. Test with Extreme Values
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/extreme_values.csv" \
  -F "grid_spacing_meters=20.0"
```

Should show multiple errors for invalid values.

---

## Using the Interactive API Docs

1. Open browser: **http://localhost:8001/docs**

2. Click **"Authorize"** button (top right)

3. Enter: `Bearer YOUR_TOKEN` (replace YOUR_TOKEN)

4. Click **Authorize**, then **Close**

5. Now you can test any endpoint:
   - Click endpoint to expand
   - Click **"Try it out"**
   - Fill in parameters
   - Click **"Execute"**
   - View response below

### Recommended Testing Order:

1. **GET /api/inventory/species** - See available tree species
2. **GET /api/inventory/template** - Download CSV template
3. **POST /api/inventory/upload** - Upload test files
4. **GET /api/inventory/my-inventories** - List your uploads
5. **GET /api/inventory/{id}/status** - Check processing status
6. **GET /api/inventory/{id}/summary** - Get summary statistics
7. **GET /api/inventory/{id}/trees** - List individual trees
8. **GET /api/inventory/{id}/export** - Export results (CSV or GeoJSON)

---

## Test Files Available

Located in: `tests/fixtures/`

1. **valid_inventory.csv** - Perfect data (should pass)
2. **typo_species.csv** - Species name errors (fuzzy matching)
3. **girth_measurements.csv** - Girth instead of diameter (auto-convert)
4. **utm_coordinates.csv** - UTM coordinates (CRS detection)
5. **swapped_coords.csv** - Lat/lon reversed (swap detection)
6. **seedlings.csv** - DBH < 10 cm (seedling handling)
7. **extreme_values.csv** - Outliers and errors (validation errors)
8. **missing_values.csv** - Missing data (error handling)
9. **flexible_columns.csv** - Non-standard column names (column detection)

See `tests/fixtures/README.md` for detailed explanation of each file.

---

## Checking the Database

### Connect to PostgreSQL:
```bash
psql -U postgres -d cf_db
```

### View Tables:
```sql
-- List all inventory tables
\dt public.inventory*
\dt public.tree*

-- Count species
SELECT COUNT(*) FROM public.tree_species_coefficients;
-- Expected: 25

-- View species list
SELECT scientific_name, local_name FROM public.tree_species_coefficients ORDER BY scientific_name;

-- Check uploaded inventories
SELECT id, user_id, uploaded_filename, status, total_trees, created_at
FROM public.inventory_calculations
ORDER BY created_at DESC
LIMIT 5;

-- Check individual trees
SELECT species, dia_cm, height_m, remark, ST_AsText(location) as coords
FROM public.inventory_trees
WHERE inventory_calculation_id = 'YOUR_INVENTORY_ID'
LIMIT 10;
```

---

## Troubleshooting

### Server Not Running?
```bash
cd D:\forest_management
start.bat
```

Or manually:
```bash
cd D:\forest_management\backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Port Already in Use?
```bash
# Use a different port
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### Database Connection Failed?
Check PostgreSQL is running:
```bash
psql -U postgres -d cf_db
```

If error, check `backend/.env` file has correct credentials.

### Token Expired?
Login again to get a new token (tokens expire after 30 minutes).

### File Upload Error?
- Check file path is correct
- Check file is valid CSV
- Check Authorization header is set
- Check token is not expired

---

## Expected Validation Behaviors

### ✅ Valid Data
- Returns `ready_for_processing: true`
- No errors
- Minimal or no warnings

### ⚠️ Typos/Fuzzy Matches
- Returns warnings with suggestions
- Shows confidence scores
- Can proceed if confidence > 85%

### ℹ️ Auto-Corrections
- Girth → Diameter conversion
- CRS detection
- Column name mapping
- Shows what was detected

### ❌ Invalid Data
- Returns `ready_for_processing: false`
- Lists all errors
- Cannot proceed until fixed

---

## Testing Checklist

- [ ] Server health check passes
- [ ] Can register and login user
- [ ] Can list 25 tree species
- [ ] Can download template CSV
- [ ] Valid inventory uploads successfully
- [ ] Typo species shows fuzzy matches
- [ ] Girth detection works
- [ ] UTM coordinates detected
- [ ] Extreme values show errors
- [ ] Missing values show errors
- [ ] Can list my inventories
- [ ] Can view inventory status
- [ ] Can export results (once processing complete)

---

## Next Steps After Testing

1. Review validation results
2. Adjust thresholds if needed
3. Test full processing workflow (volume calculations)
4. Test mother tree identification
5. Test export formats (CSV, GeoJSON)
6. Integrate with frontend

---

**Created:** February 1, 2026
**Purpose:** Guide for testing tree inventory system
**Server:** http://localhost:8001
**Docs:** http://localhost:8001/docs
