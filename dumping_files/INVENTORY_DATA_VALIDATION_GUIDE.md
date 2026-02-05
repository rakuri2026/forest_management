# Inventory Data Validation & Error Handling Guide

## Document Purpose
This guide describes common data entry errors in tree inventory CSV files and how the system automatically detects and corrects them.

---

## Table of Contents
1. [Species Name Variations](#1-species-name-variations)
2. [Diameter vs Girth Detection](#2-diameter-vs-girth-detection)
3. [Coordinate Column Names](#3-coordinate-column-names)
4. [Seedling Height Validation](#4-seedling-height-validation)
5. [Coordinate Reference System (CRS) Detection](#5-coordinate-reference-system-crs-detection)
6. [Data Quality Checks](#6-data-quality-checks)
7. [User Feedback System](#7-user-feedback-system)

---

## 1. Species Name Variations

### Problem
Users may enter species names with typos, spelling variations, or inconsistent formatting:
- `Shorea robusta` (correct)
- `shoria robusta` (typo)
- `shorea robasta` (typo)
- `Sal` (local name)
- `SHOREA ROBUSTA` (uppercase)
- `shorea  robusta` (extra spaces)

### System Solution

#### A. Fuzzy Matching Algorithm
```python
# Uses Levenshtein distance for similarity matching
# Threshold: 85% similarity

Examples:
- "shoria robusta" → matches "Shorea robusta" (92% similar)
- "shorea robasta" → matches "Shorea robusta" (93% similar)
- "Quercus spp" → matches "Quercus spp" (100% similar)
```

#### B. Local Name Mapping
```python
# System maintains local name → scientific name mapping
"Sal" → "Shorea robusta"
"Khayar" → "Acacia catechu"
"Sissoo" → "Dalbergia sissoo"
"Chilaune" → "Schima wallichii"
```

#### C. Normalization Rules
1. Convert to title case: `SHOREA ROBUSTA` → `Shorea Robusta`
2. Remove extra spaces: `shorea  robusta` → `shorea robusta`
3. Trim leading/trailing spaces
4. Handle common abbreviations: `spp`, `spp.` → `spp`

#### D. User Feedback
When fuzzy match is used:
```json
{
  "warnings": [
    {
      "row": 5,
      "column": "species",
      "original_value": "shoria robusta",
      "matched_to": "Shorea robusta",
      "confidence": 0.92,
      "message": "Species name auto-corrected (92% match)"
    }
  ]
}
```

#### E. Unmatched Species Handling
If no match found (< 85% similarity):
```json
{
  "errors": [
    {
      "row": 12,
      "column": "species",
      "value": "xyz unknown",
      "message": "Species not recognized. Closest match: 'Tsuga spp' (45% similar)",
      "action_required": "Please verify species name or contact admin to add new species",
      "suggested_species": [
        "Tsuga spp",
        "Terai spp",
        "Hill spp"
      ]
    }
  ]
}
```

---

## 2. Diameter vs Girth Detection

### Problem
Users may provide:
- **DBH (Diameter at Breast Height)** in cm (correct)
- **GBH (Girth at Breast Height)** in cm (needs conversion)

### System Solution

#### A. Automatic Detection Logic

**Statistical Heuristics:**
```python
# Girth is always larger than diameter
# Girth = π × Diameter (approximately 3.14159)
# If values are consistently > 50 cm, likely girth

Detection Rules:
1. If mean(column_values) > 100 cm → Likely GIRTH
2. If mean(column_values) < 50 cm → Likely DIAMETER
3. If 50 <= mean < 100 → Analyze distribution
```

**Distribution Analysis:**
```python
# For same tree population:
# DBH range: 10-60 cm is normal
# GBH range: 31-188 cm for same trees

If 75% of values > 80 cm:
    → Classify as GIRTH
Else:
    → Classify as DIAMETER
```

#### B. Column Name Detection
```python
# Check column headers (case-insensitive)
girth_indicators = ['girth', 'gbh', 'girth_cm', 'cbh', 'circumference']
diameter_indicators = ['diameter', 'dbh', 'dia', 'dia_cm', 'diam']

if column_name in girth_indicators:
    treat_as_girth = True
elif column_name in diameter_indicators:
    treat_as_girth = False
else:
    use_statistical_detection()
```

#### C. Conversion Formula
```python
# When girth is detected:
diameter_cm = girth_cm / π
diameter_cm = girth_cm / 3.14159265359
```

#### D. User Confirmation
When auto-detection is uncertain (50 <= mean < 100):
```json
{
  "validation_request": {
    "column": "dia_cm",
    "detected_type": "uncertain",
    "statistics": {
      "mean": 75.5,
      "min": 31.4,
      "max": 157.0,
      "median": 70.2
    },
    "question": "Is this column DIAMETER or GIRTH?",
    "options": ["diameter", "girth"],
    "suggestion": "Based on mean value of 75.5 cm, this appears to be GIRTH",
    "action_required": true
  }
}
```

#### E. Validation Report
```json
{
  "warnings": [
    {
      "column": "dia_cm",
      "message": "Column detected as GIRTH (mean: 125.3 cm)",
      "action_taken": "Converted to diameter using formula: DBH = GBH / π",
      "sample_conversions": [
        {"original": 94.2, "converted": 30.0},
        {"original": 125.6, "converted": 40.0},
        {"original": 157.0, "converted": 50.0}
      ]
    }
  ]
}
```

---

## 3. Coordinate Column Names

### Problem
Users may use different column names for coordinates:
- `LONGITUDE, LATITUDE` (standard)
- `longitude, latitude` (lowercase)
- `long, lat` (abbreviated)
- `x, y` (GIS convention)
- `X, Y` (uppercase)
- `easting, northing` (projected coordinates)

### System Solution

#### A. Column Name Mapping
```python
# Longitude/X/Easting aliases (case-insensitive)
longitude_aliases = [
    'longitude', 'long', 'lon', 'lng',
    'x', 'easting', 'east',
    'coord_x', 'x_coord', 'long_dd'
]

# Latitude/Y/Northing aliases (case-insensitive)
latitude_aliases = [
    'latitude', 'lat',
    'y', 'northing', 'north',
    'coord_y', 'y_coord', 'lat_dd'
]
```

#### B. Detection Priority
```python
# Priority order for detection:
1. Exact match: 'LONGITUDE', 'LATITUDE'
2. Case-insensitive match: 'longitude', 'latitude'
3. Standard abbreviations: 'long', 'lat'
4. GIS conventions: 'x', 'y'
5. Full words: 'easting', 'northing'

# First match wins
```

#### C. Validation
```python
# After detection, validate coordinate ranges:

For Geographic (EPSG:4326):
    - Longitude: -180 to 180
    - Latitude: -90 to 90
    - Nepal bounds: Long 80-88°E, Lat 26-31°N

For Projected (UTM 44N - EPSG:32644):
    - Easting: 200,000 to 900,000
    - Northing: 2,800,000 to 3,500,000

For Projected (UTM 45N - EPSG:32645):
    - Easting: 200,000 to 900,000
    - Northing: 2,800,000 to 3,500,000
```

#### D. Automatic CRS Detection
```python
def detect_crs(x_values, y_values):
    x_mean = mean(x_values)
    y_mean = mean(y_values)

    # Geographic coordinates (degrees)
    if -180 <= x_mean <= 180 and -90 <= y_mean <= 90:
        if 80 <= x_mean <= 88 and 26 <= y_mean <= 31:
            return 'EPSG:4326'  # Nepal region

    # UTM Zone 44N (Western Nepal)
    elif 200000 <= x_mean <= 900000 and 2800000 <= y_mean <= 3500000:
        if x_mean < 500000:
            return 'EPSG:32644'  # UTM 44N
        else:
            return 'EPSG:32645'  # UTM 45N

    return 'UNKNOWN'
```

#### E. User Notification
```json
{
  "coordinate_detection": {
    "x_column": "long",
    "y_column": "lat",
    "detected_crs": "EPSG:4326",
    "confidence": "high",
    "sample_coordinates": [
      {"x": 85.3240, "y": 27.7172},
      {"x": 85.3245, "y": 27.7180}
    ],
    "validation": "All coordinates within Nepal bounds"
  }
}
```

#### F. Column Not Found Error
```json
{
  "errors": [
    {
      "type": "missing_coordinates",
      "message": "Could not detect coordinate columns",
      "available_columns": ["species", "dbh", "height", "class"],
      "expected_columns": "LONGITUDE/LATITUDE, long/lat, or x/y",
      "action_required": "Please rename coordinate columns to standard names"
    }
  ]
}
```

---

## 4. Seedling Height Validation

### Problem
Seedlings (DBH < 10 cm) often have unreliable height measurements. These should be excluded from volume calculations.

### System Solution

#### A. Business Rules
```python
# DBH Classification
if dbh_cm < 10:
    tree_class = 'SEEDLING'
    height_used_in_calculation = False
elif 10 <= dbh_cm < 20:
    tree_class = 'SAPLING'
    height_used_in_calculation = True
elif 20 <= dbh_cm < 40:
    tree_class = 'POLE'
    height_used_in_calculation = True
else:
    tree_class = 'MATURE'
    height_used_in_calculation = True
```

#### B. Seedling Volume Calculation
```python
# For DBH < 10 cm, ignore height parameter
if dbh_cm < 10:
    if height_m is provided:
        # Calculate volume using default height-diameter ratio
        estimated_height = dbh_cm * 0.8  # H/D ratio = 0.8 for seedlings
        volume = calculate_volume(dbh_cm, estimated_height, species)

        warning = {
            "message": "Height ignored for seedling (DBH < 10 cm)",
            "provided_height": height_m,
            "estimated_height": estimated_height,
            "reason": "Seedling height measurements are unreliable"
        }
    else:
        # Height not provided - use default ratio
        estimated_height = dbh_cm * 0.8
        volume = calculate_volume(dbh_cm, estimated_height, species)
```

#### C. Height-Diameter Ratio Validation
```python
# Flag suspicious height-diameter ratios
def validate_height_diameter_ratio(dbh_cm, height_m):
    ratio = height_m / (dbh_cm / 100)  # Convert DBH to meters

    # Normal ranges for Nepal forests:
    # Conifers: H/D ratio 80-120
    # Broadleaf: H/D ratio 60-100

    if ratio < 40:
        return {
            "status": "warning",
            "message": f"Unusually low H/D ratio ({ratio:.1f}). Tree appears too short.",
            "action": "Using height as provided, but please verify"
        }
    elif ratio > 150:
        return {
            "status": "warning",
            "message": f"Unusually high H/D ratio ({ratio:.1f}). Tree appears too tall.",
            "action": "Using height as provided, but please verify"
        }
    else:
        return {"status": "ok"}
```

#### D. Seedling Handling Report
```json
{
  "seedling_handling": {
    "total_seedlings": 45,
    "height_ignored_count": 45,
    "method": "Default H/D ratio (0.8) used for volume estimation",
    "examples": [
      {
        "row": 3,
        "dbh_cm": 5.2,
        "provided_height_m": 3.5,
        "estimated_height_m": 4.16,
        "message": "Height ignored - seedling classification"
      }
    ]
  }
}
```

#### E. Mother Tree Exclusion
```python
# Seedlings cannot be mother trees
if dbh_cm < 10:
    eligible_for_mother_tree = False
    remark = 'SEEDLING - Not eligible for harvesting'

# Only mature trees (DBH >= 30 cm) can be mother trees
elif dbh_cm >= 30:
    eligible_for_mother_tree = True
else:
    eligible_for_mother_tree = False
    remark = 'SAPLING/POLE - Too young for mother tree designation'
```

---

## 5. Coordinate Reference System (CRS) Detection

### Problem
Users may provide coordinates in different CRS without specifying:
- EPSG:4326 (Geographic - WGS84)
- EPSG:32644 (UTM Zone 44N - Western Nepal)
- EPSG:32645 (UTM Zone 45N - Eastern Nepal)

### System Solution

#### A. Automatic CRS Detection
```python
def detect_crs_from_values(x_values, y_values):
    """
    Detect CRS based on coordinate value ranges
    """
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    x_mean = sum(x_values) / len(x_values)

    # Test 1: Geographic coordinates (degrees)
    if (80 <= x_min <= 88 and 80 <= x_max <= 88 and
        26 <= y_min <= 31 and 26 <= y_max <= 31):
        return {
            'epsg': 4326,
            'name': 'WGS84 Geographic',
            'confidence': 'high',
            'method': 'Value range analysis - Nepal bounds'
        }

    # Test 2: UTM Zone 44N (Western Nepal: 81°E - 87°E)
    if (200000 <= x_min <= 900000 and
        2800000 <= y_min <= 3500000):

        # Determine zone based on easting
        if x_mean < 500000:
            return {
                'epsg': 32644,
                'name': 'WGS84 / UTM Zone 44N',
                'confidence': 'high',
                'method': 'UTM easting/northing range - Western Nepal'
            }
        else:
            return {
                'epsg': 32645,
                'name': 'WGS84 / UTM Zone 45N',
                'confidence': 'high',
                'method': 'UTM easting/northing range - Eastern Nepal'
            }

    # Test 3: Check if values might be swapped
    if (80 <= y_min <= 88 and 26 <= x_min <= 31):
        return {
            'epsg': 'UNKNOWN',
            'error': 'Coordinates appear swapped',
            'suggestion': 'X and Y columns may be reversed',
            'confidence': 'error'
        }

    return {
        'epsg': 'UNKNOWN',
        'confidence': 'none',
        'x_range': [x_min, x_max],
        'y_range': [y_min, y_max]
    }
```

#### B. User CRS Input
```python
# Upload form includes optional CRS field
{
    "file": "TreeLoc.csv",
    "crs": "EPSG:32644",  # Optional - user can specify
    "auto_detect_crs": true  # Default true
}

# If user specifies CRS, skip auto-detection
# If auto-detect enabled and CRS specified, validate consistency
```

#### C. CRS Validation
```python
def validate_crs_consistency(coordinates, user_specified_crs):
    """
    Check if user-specified CRS matches coordinate values
    """
    detected = detect_crs_from_values(coordinates)

    if detected['epsg'] != user_specified_crs:
        return {
            'status': 'warning',
            'user_specified': user_specified_crs,
            'detected': detected['epsg'],
            'message': f"User specified {user_specified_crs} but coordinates appear to be in {detected['name']}",
            'action_required': true,
            'question': "Which CRS is correct?"
        }

    return {'status': 'ok', 'crs': user_specified_crs}
```

#### D. Transformation to Standard CRS
```python
# Always transform to EPSG:4326 for storage
if input_crs == 'EPSG:32644' or input_crs == 'EPSG:32645':
    # Transform UTM to Geographic
    transformer = pyproj.Transformer.from_crs(
        input_crs,
        'EPSG:4326',
        always_xy=True
    )
    lon, lat = transformer.transform(x, y)

# Store in database as EPSG:4326 (Geography type)
location = f"SRID=4326;POINT({lon} {lat})"
```

#### E. CRS Detection Report
```json
{
  "crs_detection": {
    "user_specified": null,
    "auto_detected": "EPSG:32644",
    "confidence": "high",
    "method": "UTM easting/northing range analysis",
    "statistics": {
      "x_range": [456789.12, 489234.56],
      "y_range": [3045678.90, 3078901.23],
      "mean_x": 473011.84,
      "mean_y": 3062290.07
    },
    "transformation": "Converted to EPSG:4326 for storage",
    "sample_transformations": [
      {
        "original": {"x": 456789.12, "y": 3045678.90},
        "transformed": {"lon": 84.1234, "lat": 27.5678}
      }
    ]
  }
}
```

#### F. Unknown CRS Handling
```json
{
  "errors": [
    {
      "type": "unknown_crs",
      "message": "Could not automatically detect coordinate reference system",
      "coordinate_statistics": {
        "x_range": [1234.56, 5678.90],
        "y_range": [9876.54, 12345.67]
      },
      "action_required": "Please specify the EPSG code for your coordinates",
      "common_nepal_crs": [
        {"epsg": 4326, "name": "WGS84 Geographic (Lat/Lon in degrees)"},
        {"epsg": 32644, "name": "UTM Zone 44N (Western Nepal)"},
        {"epsg": 32645, "name": "UTM Zone 45N (Eastern Nepal)"}
      ]
    }
  ]
}
```

---

## 6. Data Quality Checks

### Additional Validation Rules

#### A. Duplicate Trees
```python
# Check for duplicate coordinates (within 1 meter)
def detect_duplicate_locations(trees_df):
    duplicates = []
    for i, row in trees_df.iterrows():
        nearby = trees_df[
            (abs(trees_df['x'] - row['x']) < 0.00001) &  # ~1 meter
            (abs(trees_df['y'] - row['y']) < 0.00001) &
            (trees_df.index != i)
        ]
        if len(nearby) > 0:
            duplicates.append({
                'row': i,
                'coordinates': (row['x'], row['y']),
                'duplicate_count': len(nearby)
            })

    return duplicates
```

#### B. Missing Values
```python
# Required fields
required_fields = ['species', 'dia_cm', 'longitude', 'latitude']

# Optional fields (can be estimated)
optional_fields = ['height_m', 'class']

# Height estimation if missing
if pd.isna(height_m) and dbh_cm >= 10:
    # Use species-specific H/D ratio
    height_m = estimate_height_from_dbh(dbh_cm, species)
    warning = "Height not provided - estimated from DBH"

# Class assignment if missing
if pd.isna(tree_class):
    if dbh_cm < 20:
        tree_class = 'B'  # Poor quality assumed for small trees
    else:
        tree_class = 'A'  # Good quality assumed for mature trees
    warning = "Tree class not provided - assigned based on DBH"
```

#### C. Outlier Detection
```python
# Flag statistical outliers
def detect_outliers(df, column):
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1

    lower_bound = Q1 - 3 * IQR
    upper_bound = Q3 + 3 * IQR

    outliers = df[
        (df[column] < lower_bound) |
        (df[column] > upper_bound)
    ]

    return {
        'count': len(outliers),
        'rows': outliers.index.tolist(),
        'values': outliers[column].tolist(),
        'expected_range': [lower_bound, upper_bound]
    }

# Example outliers:
# - DBH = 250 cm (extremely large)
# - Height = 2 m with DBH = 40 cm (too short)
# - Height = 50 m (too tall for Nepal)
```

#### D. Spatial Outliers
```python
# Check if trees are within reasonable bounds
nepal_bounds = {
    'min_lon': 80.0,
    'max_lon': 88.3,
    'min_lat': 26.3,
    'max_lat': 30.5
}

def check_spatial_bounds(lon, lat):
    if not (nepal_bounds['min_lon'] <= lon <= nepal_bounds['max_lon']):
        return {
            'error': 'Longitude outside Nepal bounds',
            'value': lon,
            'expected_range': [nepal_bounds['min_lon'], nepal_bounds['max_lon']]
        }

    if not (nepal_bounds['min_lat'] <= lat <= nepal_bounds['max_lat']):
        return {
            'error': 'Latitude outside Nepal bounds',
            'value': lat,
            'expected_range': [nepal_bounds['min_lat'], nepal_bounds['max_lat']]
        }

    return {'status': 'ok'}
```

---

## 7. User Feedback System

### Validation Report Structure

```json
{
  "upload_id": "uuid",
  "filename": "TreeLoc.csv",
  "uploaded_at": "2026-02-01T10:30:00Z",
  "status": "validation_complete",

  "summary": {
    "total_rows": 150,
    "valid_rows": 142,
    "rows_with_warnings": 8,
    "rows_with_errors": 0,
    "auto_corrections": 12
  },

  "data_detection": {
    "coordinate_columns": {"x": "long", "y": "lat"},
    "crs_detected": "EPSG:4326",
    "diameter_type": "diameter",
    "species_column": "species"
  },

  "errors": [
    {
      "severity": "error",
      "row": 25,
      "column": "species",
      "value": "unknown tree xyz",
      "message": "Species not recognized",
      "action_required": "Correct species name or skip this row"
    }
  ],

  "warnings": [
    {
      "severity": "warning",
      "row": 5,
      "column": "species",
      "original": "shoria robusta",
      "corrected": "Shorea robusta",
      "confidence": 0.92,
      "message": "Species name auto-corrected (typo detected)"
    },
    {
      "severity": "warning",
      "row": 12,
      "column": "height_m",
      "value": 3.5,
      "dbh_cm": 5.2,
      "message": "Height ignored - seedling (DBH < 10 cm)",
      "action_taken": "Used estimated height (4.16 m) based on H/D ratio"
    }
  ],

  "info": [
    {
      "type": "auto_correction",
      "column": "dia_cm",
      "message": "Column detected as GIRTH - converted to diameter",
      "affected_rows": 150,
      "method": "DBH = GBH / π"
    },
    {
      "type": "crs_transformation",
      "message": "Coordinates transformed from UTM 44N to WGS84",
      "from_crs": "EPSG:32644",
      "to_crs": "EPSG:4326"
    }
  ],

  "statistics": {
    "species_distribution": {
      "Shorea robusta": 45,
      "Schima wallichii": 32,
      "Dalbergia sissoo": 28,
      "Others": 45
    },
    "dbh_classes": {
      "Seedling (<10cm)": 20,
      "Sapling (10-20cm)": 35,
      "Pole (20-40cm)": 55,
      "Mature (>40cm)": 40
    },
    "spatial_extent": {
      "min_lon": 85.3200,
      "max_lon": 85.3456,
      "min_lat": 27.7100,
      "max_lat": 27.7250,
      "area_hectares": 12.5
    }
  },

  "next_steps": {
    "ready_for_processing": true,
    "requires_user_action": false,
    "message": "Data validated successfully. Click 'Process Inventory' to continue."
  }
}
```

---

## 8. Implementation Priority

### Phase 1: Critical Validations (Must Have)
1. ✅ Species name fuzzy matching
2. ✅ Coordinate column detection
3. ✅ CRS detection and transformation
4. ✅ Missing value handling
5. ✅ Duplicate detection

### Phase 2: Important Validations (Should Have)
6. ✅ Diameter vs Girth detection
7. ✅ Seedling height handling
8. ✅ Outlier detection
9. ✅ Spatial bounds checking

### Phase 3: Nice-to-Have (Could Have)
10. Interactive validation UI
11. Manual correction interface
12. Bulk species name addition
13. Template CSV generator

---

## 9. User Interface Flow

### Step 1: Upload
```
User uploads TreeLoc.csv
   ↓
System performs initial validation
   ↓
Displays validation report
```

### Step 2: Review
```
If errors found:
   → User corrects data or confirms auto-corrections
   → Re-upload

If only warnings:
   → User reviews warnings
   → Can accept auto-corrections or reject
```

### Step 3: Confirmation
```
User confirms:
   ✓ Species corrections
   ✓ CRS detection
   ✓ Diameter type
   ✓ Coordinate columns

System proceeds with processing
```

### Step 4: Processing
```
System:
   1. Applies all corrections
   2. Calculates volumes
   3. Identifies mother trees
   4. Generates results
```

---

## 10. Configuration Options

### Admin Settings
```python
# System administrator can configure:

FUZZY_MATCH_THRESHOLD = 0.85  # 85% similarity
GIRTH_DETECTION_THRESHOLD = 100  # cm
SEEDLING_DBH_THRESHOLD = 10  # cm
MOTHER_TREE_MIN_DBH = 30  # cm
HEIGHT_DIAMETER_RATIO_WARNING_LOW = 40
HEIGHT_DIAMETER_RATIO_WARNING_HIGH = 150
MAX_TREE_HEIGHT_NEPAL = 50  # meters
MIN_TREE_HEIGHT_NEPAL = 1  # meters
DUPLICATE_DISTANCE_TOLERANCE = 1  # meters
```

### User Preferences
```python
# Users can set preferences per upload:

auto_correct_species = True  # Auto-apply fuzzy matches
auto_detect_crs = True
auto_convert_girth = True
exclude_seedlings_from_mother_trees = True
require_manual_confirmation_for_low_confidence = True  # < 90% match
```

---

## Conclusion

This comprehensive validation system ensures that:
- ✅ Users can upload data with common formatting variations
- ✅ System automatically detects and corrects most errors
- ✅ Users are informed of all corrections and assumptions
- ✅ Data quality is maintained throughout the process
- ✅ Processing failures are minimized
- ✅ Results are reliable and reproducible

**Next Step:** Implement validation logic in `backend/app/services/inventory_validator.py`
