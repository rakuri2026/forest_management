# Test CSV Files for Tree Inventory Validation

This directory contains test CSV files designed to validate the inventory upload and validation system.

## Test Files

### 1. `valid_inventory.csv`
**Purpose:** Baseline test with perfect data
**Features:**
- 10 trees with correct species names
- Proper diameter and height values
- Standard column names (species, dia_cm, height_m, class, LONGITUDE, LATITUDE)
- Geographic coordinates (EPSG:4326)
- All values within normal ranges

**Expected Result:** ✅ Pass validation with no errors

---

### 2. `typo_species.csv`
**Purpose:** Test species name fuzzy matching
**Features:**
- Typos: "Shoria robusta" (missing 'e'), "shorea robasta" (wrong vowel)
- Incorrect spelling: "Pinus roxburghi" (missing 'i')
- Minor typos: "Dalbargia sisso" (missing 'e')
- Local names: "sal", "Sakhu", "chilaune", "Asna"
- Mixed case variations

**Expected Result:** ⚠️ Warnings with fuzzy match suggestions
- System should match "Shoria robusta" → "Shorea robusta" (confidence: ~85%)
- System should match local names using alias database
- Should provide confidence scores for each match

---

### 3. `girth_measurements.csv`
**Purpose:** Test girth vs diameter detection and auto-conversion
**Features:**
- Column named "girth_cm" instead of "dia_cm"
- Values range from 79.2 to 163.7 cm (typical girth values)
- Mean value > 100 cm (strong indicator of girth)

**Expected Result:** ℹ️ Info message about girth detection
- System should detect measurement type as "girth"
- Should auto-convert: `diameter = girth / π`
- Should provide sample conversions for user verification
- Example: 143.0 cm girth → 45.5 cm diameter

---

### 4. `utm_coordinates.csv`
**Purpose:** Test UTM coordinate detection (EPSG:32644/32645)
**Features:**
- Column names: "X" and "Y" instead of LONGITUDE/LATITUDE
- Coordinates in UTM Zone 44N projection
- X values: ~645,000 (Easting)
- Y values: ~3,068,000 (Northing)
- Nepal geographic extent

**Expected Result:** ℹ️ Info about CRS detection
- System should detect CRS as EPSG:32644 or 32645
- Should recognize flexible column names (X/Y)
- Should validate against Nepal UTM bounds
- Should be ready for transformation to EPSG:4326 for storage

---

### 5. `swapped_coords.csv`
**Purpose:** Test detection of swapped latitude/longitude
**Features:**
- LONGITUDE column contains latitude values (27.71-27.72)
- LATITUDE column contains longitude values (85.32-85.33)
- Values are swapped but still within Nepal bounds

**Expected Result:** ⚠️ Warning about swapped coordinates
- System should detect: LONGITUDE values < 50 (should be 80-88)
- System should detect: LATITUDE values > 50 (should be 26-30)
- Should offer to auto-swap the columns
- Should validate corrected coordinates against Nepal bounds

---

### 6. `seedlings.csv`
**Purpose:** Test seedling handling (DBH < 10 cm)
**Features:**
- All trees have dia_cm < 10 (range: 3.8 to 9.5 cm)
- Height values provided (range: 1.9 to 4.8 m)
- Class marked as "C" (seedling class)

**Expected Result:** ℹ️ Info about seedlings detected
- System should identify all as seedlings
- Height values should be used for record but noted
- Volume calculations should use seedling-specific formulas
- Should mark as "Seedling" in remark field (not eligible for felling or mother tree)

---

### 7. `extreme_values.csv`
**Purpose:** Test validation of outliers and impossible values
**Features:**
- Row 1: DBH = 250 cm (too large), Height = 55 m (too tall)
- Row 2: DBH = 0.5 cm (too small), Height = 0.3 m (too short)
- Row 4: Height = -5.0 m (negative value)
- Row 6: DBH = 1500 cm (clearly wrong - likely mm instead of cm)
- Row 8: Height = 250 m (clearly wrong - likely cm instead of m)
- Row 9: Longitude = 90.0 (outside Nepal)
- Row 10: Latitude = 35.0 (outside Nepal)

**Expected Result:** ❌ Errors for invalid data
- DBH validations:
  - DBH < 1 cm → Error (too small)
  - DBH > 200 cm → Warning (extremely large, verify)
  - DBH > 500 cm → Error (likely unit error, possibly mm)
- Height validations:
  - Height < 1.3 m → Error (below breast height)
  - Height < 0 → Error (negative value)
  - Height > 50 m → Warning (extremely tall for Nepal)
  - Height > 100 m → Error (likely unit error, possibly cm)
- Coordinate validations:
  - Longitude outside 80-88.3 → Error (outside Nepal)
  - Latitude outside 26.3-30.5 → Error (outside Nepal)

---

### 8. `missing_values.csv`
**Purpose:** Test handling of missing/empty values
**Features:**
- Row 2: Missing species name
- Row 3: Missing dia_cm
- Row 4: Missing height_m
- Row 6: Missing LONGITUDE
- Row 7: Missing LATITUDE
- Row 8: Missing class

**Expected Result:** ❌ Errors for critical missing values
- Missing species → Error (required for volume calculation)
- Missing dia_cm → Error (required for volume calculation)
- Missing height_m → Warning (can estimate from H/D ratio)
- Missing LONGITUDE or LATITUDE → Error (required for spatial analysis)
- Missing class → Warning (can default to 'B')

---

### 9. `flexible_columns.csv`
**Purpose:** Test flexible column name detection
**Features:**
- Non-standard column names:
  - "tree_species" instead of "species"
  - "diameter" instead of "dia_cm"
  - "ht_m" instead of "height_m"
  - "quality" instead of "class"
  - "lon" and "lat" instead of "LONGITUDE" and "LATITUDE"

**Expected Result:** ✅ Pass with column name mapping
- System should detect:
  - Species column from keywords: species, tree, scientific, botanical
  - Diameter column from keywords: dia, diameter, dbh, girth
  - Height column from keywords: height, ht, h
  - Class column from keywords: class, quality, grade
  - Longitude from keywords: lon, long, longitude, x
  - Latitude from keywords: lat, latitude, y
- Should provide info about detected column mapping

---

## Testing Workflow

### 1. Upload each file via API:
```bash
curl -X POST "http://localhost:8001/api/inventory/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@valid_inventory.csv" \
  -F "grid_spacing_meters=20.0"
```

### 2. Expected API Response Structure:
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
    "columns_detected": {
      "species": "species",
      "diameter": "dia_cm",
      "height": "height_m",
      "class": "class",
      "longitude": "LONGITUDE",
      "latitude": "LATITUDE"
    },
    "crs": {
      "detected": "EPSG:4326",
      "method": "value_range",
      "confidence": "high"
    },
    "diameter_type": {
      "detected": "diameter",
      "confidence": "high",
      "stats": {...}
    }
  },
  "errors": [],
  "warnings": [],
  "info": [],
  "corrections": []
}
```

### 3. Validation Severity Levels:

**ERROR (❌):** Prevents processing
- Missing required fields (species, diameter, coordinates)
- Invalid data types
- Values outside possible ranges
- Negative values for measurements
- Coordinates outside Nepal

**WARNING (⚠️):** Allows processing with user confirmation
- Extremely large/small values (but within possible range)
- Missing optional fields (height, class)
- Low fuzzy match confidence (70-84%)
- Duplicate coordinates

**INFO (ℹ️):** Informational messages
- Auto-corrections applied (girth→diameter, CRS detection)
- Column name mappings
- Seedling detection
- High-confidence fuzzy matches (>85%)

---

## Validation Rules Summary

### Species Name:
- **Method:** Fuzzy matching with Levenshtein distance
- **Threshold:** 85% similarity
- **Fallback:** Check local name aliases
- **Error if:** No match found above 70%

### Diameter (DBH):
- **Expected range:** 1-200 cm
- **Girth detection:** Mean > 100 cm or column name contains "girth"
- **Conversion:** diameter = girth / π (3.14159)
- **Error if:** < 1 cm, > 500 cm, or negative
- **Warning if:** > 200 cm (verify data)

### Height:
- **Expected range:** 1.3-50 m
- **Default:** Estimated from species-specific H/D ratio if missing
- **Error if:** < 1.3 m (below breast height), > 100 m
- **Warning if:** > 50 m (very tall)
- **Seedlings:** Height used for record but noted

### Class:
- **Valid values:** A, B, C (or 1, 2, 3)
- **Default:** B if missing
- **Effect:** A = 90% quality factor, B = 80%, C = seedling

### Coordinates:
- **CRS detection:**
  - Geographic (4326): lon 80-88.3, lat 26.3-30.5
  - UTM 44N (32644): x 200k-700k, y 2.8M-3.5M
  - UTM 45N (32645): x 200k-900k, y 2.8M-3.5M
- **Swap detection:** If lon < 50 and lat > 50, suggest swap
- **Column names:** lon/long/longitude/x, lat/latitude/y
- **Error if:** Outside Nepal bounds in any CRS

---

## Usage in Development

1. **Unit Testing:** Each file tests specific validation logic
2. **Integration Testing:** Complete upload → validation → processing workflow
3. **User Acceptance Testing:** Real-world error scenarios
4. **Documentation:** Examples for user guide

---

## Next Steps

After validating with these files:
1. Fix any bugs in validation logic
2. Adjust thresholds based on test results
3. Add more edge cases if needed
4. Create frontend UI for uploading these test files
5. Generate validation report examples for documentation

---

**Created:** February 1, 2026
**Purpose:** Test suite for Tree Inventory validation system
**Location:** `D:\forest_management\tests\fixtures\`
