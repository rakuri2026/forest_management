# Inventory Data Quality Issues - Complete Reference

## Purpose
Comprehensive guide covering ALL possible user errors, data quality issues, and edge cases in tree inventory data.

---

## Table of Contents
1. [Measurement Errors](#1-measurement-errors)
2. [Data Entry Mistakes](#2-data-entry-mistakes)
3. [Unit Confusion](#3-unit-confusion)
4. [Missing and Invalid Data](#4-missing-and-invalid-data)
5. [Spatial Data Issues](#5-spatial-data-issues)
6. [File Format Issues](#6-file-format-issues)
7. [Statistical Outliers](#7-statistical-outliers)
8. [Logical Inconsistencies](#8-logical-inconsistencies)

---

## 1. Measurement Errors

### 1.1 Extremely Large Diameter Values

#### Problem
Users may enter unrealistic DBH values:
- **300 cm** - Extremely rare in Nepal
- **500 cm** - Impossible for most species
- **1000+ cm** - Clearly an error

#### Realistic Ranges for Nepal
```python
# Species-specific maximum DBH (cm)
realistic_max_dbh = {
    'Shorea robusta': 150,      # Sal - max ~150 cm
    'Schima wallichii': 100,    # Chilaune - max ~100 cm
    'Dalbergia sissoo': 120,    # Sissoo - max ~120 cm
    'Pinus roxburghii': 120,    # Khote Salla - max ~120 cm
    'Abies spp': 150,           # Fir - max ~150 cm
    'default': 150              # General maximum
}

# Global maximum for any tree in Nepal
ABSOLUTE_MAX_DBH = 200  # cm (very conservative)
```

#### Detection Logic
```python
def validate_dbh(dbh_cm, species):
    # Critical error - definitely wrong
    if dbh_cm > ABSOLUTE_MAX_DBH:
        return {
            'severity': 'error',
            'message': f'DBH {dbh_cm} cm is unrealistically large',
            'suggestion': 'May be data entry error (extra digit?)',
            'action': 'reject_row'
        }

    # Warning - unusually large but possible
    species_max = realistic_max_dbh.get(species, realistic_max_dbh['default'])
    if dbh_cm > species_max:
        return {
            'severity': 'warning',
            'message': f'DBH {dbh_cm} cm is unusually large for {species}',
            'typical_max': species_max,
            'action': 'flag_for_review'
        }

    return {'status': 'ok'}
```

#### Common Causes
1. **Extra digit**: 450 instead of 45 (typing error)
2. **Wrong unit**: Entered mm instead of cm (450 mm = 45 cm)
3. **Girth confused with diameter**: 157 cm girth = 50 cm diameter
4. **Copy-paste error**: Pasted height into diameter column

---

### 1.2 Extremely Large Height Values

#### Problem
Users may enter unrealistic heights:
- **80 meters** - Impossible in Nepal
- **100+ meters** - Clearly an error
- **5 meters for 80cm DBH** - Too short

#### Realistic Ranges for Nepal
```python
# Maximum heights by forest type
realistic_max_height = {
    'Terai broadleaf': 35,      # Max ~35m
    'Hill broadleaf': 30,        # Max ~30m
    'Coniferous': 45,            # Max ~45m (Blue Pine)
    'Sub-alpine': 40,            # Max ~40m (Fir, Spruce)
}

ABSOLUTE_MAX_HEIGHT = 50  # meters (very conservative for Nepal)
ABSOLUTE_MIN_HEIGHT = 1.3  # Below breast height
```

#### Detection Logic
```python
def validate_height(height_m, species, dbh_cm):
    # Critical errors
    if height_m > ABSOLUTE_MAX_HEIGHT:
        return {
            'severity': 'error',
            'message': f'Height {height_m} m is unrealistically tall for Nepal',
            'suggestion': 'Nepal max tree height ~45-50m',
            'action': 'reject_row'
        }

    if height_m < ABSOLUTE_MIN_HEIGHT:
        return {
            'severity': 'error',
            'message': f'Height {height_m} m is below breast height (1.3m)',
            'action': 'reject_row'
        }

    # Height-Diameter ratio validation
    hd_ratio = height_m / (dbh_cm / 100)  # Convert DBH to meters

    # Typical H/D ratios for Nepal
    # Conifers: 80-120
    # Broadleaf: 60-100

    if hd_ratio < 30:
        return {
            'severity': 'warning',
            'message': f'Tree appears unusually short (H/D ratio: {hd_ratio:.1f})',
            'height_m': height_m,
            'dbh_cm': dbh_cm,
            'action': 'flag_for_review'
        }

    if hd_ratio > 150:
        return {
            'severity': 'warning',
            'message': f'Tree appears unrealistically tall (H/D ratio: {hd_ratio:.1f})',
            'suggestion': 'May have swapped height and DBH values?',
            'action': 'flag_for_review'
        }

    return {'status': 'ok'}
```

#### Common Causes
1. **Wrong unit**: Entered feet instead of meters (100 ft = 30m)
2. **Decimal error**: 35.5 entered as 355
3. **Swapped columns**: Height in DBH column, DBH in height column
4. **Total height vs merchantable height confusion**

---

### 1.3 Extremely Small Values (< 1 cm DBH)

#### Problem
```python
# Invalid small values
DBH = 0.5 cm   # Impossible to measure at breast height
DBH = 0 cm     # Data entry error
Height = 0.3 m # Below breast height
```

#### Detection
```python
MIN_DBH = 1.0  # cm (practical measurement limit)

if dbh_cm < MIN_DBH:
    return {
        'severity': 'error',
        'message': f'DBH {dbh_cm} cm is too small to measure at breast height',
        'suggestion': 'This may be a seedling - exclude from inventory',
        'action': 'reject_row'
    }
```

---

### 1.4 Negative Values

#### Problem
```python
DBH = -10 cm
Height = -5 m
Latitude = -27.5  # Wrong hemisphere!
```

#### Detection
```python
if dbh_cm < 0 or height_m < 0:
    return {
        'severity': 'error',
        'message': 'Negative values not allowed',
        'action': 'reject_row'
    }

# Latitude check for Nepal
if latitude < 0:
    return {
        'severity': 'error',
        'message': 'Negative latitude detected - Nepal is in Northern Hemisphere',
        'suggestion': 'Check coordinate system or remove negative sign',
        'action': 'reject_row'
    }
```

---

## 2. Data Entry Mistakes

### 2.1 Decimal Point Errors

#### Problem
```python
# User meant 45.5 cm but entered:
45.5   → Correct
455    → Missing decimal point (×10 error)
4.55   → Extra decimal point (÷10 error)
4,55   → European decimal notation (comma instead of period)
```

#### Detection
```python
def detect_decimal_errors(df, column):
    """Detect if values are consistently 10x or 100x off"""
    mean_val = df[column].mean()

    # Check if values look 10x too large
    if mean_val > 200:  # DBH mean > 200 suggests ×10 error
        return {
            'error_type': 'decimal_missing',
            'message': f'Values appear 10x too large (mean: {mean_val:.1f})',
            'suggestion': 'All values may be missing decimal point',
            'correction': 'divide_by_10',
            'confidence': 'high' if mean_val > 300 else 'medium'
        }

    # Check if values look 10x too small
    if mean_val < 3:
        return {
            'error_type': 'extra_decimal',
            'message': f'Values appear 10x too small (mean: {mean_val:.1f})',
            'suggestion': 'All values may have extra decimal point',
            'correction': 'multiply_by_10'
        }

    return {'status': 'ok'}
```

#### European Decimal Notation
```python
# Handle comma as decimal separator
df['dia_cm'] = df['dia_cm'].astype(str).str.replace(',', '.').astype(float)
```

---

### 2.2 Column Swapping

#### Problem
User accidentally swaps data between columns:
```csv
# DBH and Height swapped
species,      dia_cm, height_m
Sal,          25.5,   45      # Correct
Sal,          35,     28.5    # Swapped! (35m height, 28.5cm DBH)
```

#### Detection
```python
def detect_column_swap(df, dbh_col, height_col):
    """Detect if DBH and height columns are swapped"""

    # Count suspicious rows where height > dbh
    # (should be opposite in correct data)
    suspicious = df[df[height_col] > df[dbh_col]]

    if len(suspicious) > len(df) * 0.5:  # More than 50% suspicious
        return {
            'severity': 'error',
            'message': 'DBH and height columns appear to be swapped',
            'suspicious_rows': len(suspicious),
            'total_rows': len(df),
            'suggestion': 'Swap the columns in your CSV file',
            'action_required': True
        }

    return {'status': 'ok'}
```

#### Coordinate Swapping
```python
# Latitude/Longitude swapped
# Correct: (Lat: 27.7, Lon: 85.3)
# Wrong:   (Lat: 85.3, Lon: 27.7)

def detect_coordinate_swap(lat, lon):
    # Nepal bounds: Lat 26-31, Lon 80-88
    if 80 <= lat <= 88 and 26 <= lon <= 31:
        return {
            'error': 'coordinates_swapped',
            'message': 'Latitude and Longitude appear swapped',
            'current_lat': lat,
            'current_lon': lon,
            'action': 'Please swap columns'
        }
    return {'status': 'ok'}
```

---

### 2.3 Copy-Paste Errors

#### Problem
```python
# Same value repeated for multiple trees (copy-paste error)
Tree 1: DBH=35, Height=25
Tree 2: DBH=35, Height=25
Tree 3: DBH=35, Height=25  # Suspicious - exact duplicates
Tree 4: DBH=35, Height=25
```

#### Detection
```python
def detect_duplicate_measurements(df, columns):
    """Detect suspiciously repeated values"""

    duplicates = df[df.duplicated(subset=columns, keep=False)]

    # Calculate percentage of duplicates
    dup_percentage = len(duplicates) / len(df) * 100

    if dup_percentage > 20:  # More than 20% exact duplicates
        return {
            'severity': 'warning',
            'message': f'{dup_percentage:.1f}% of measurements are exact duplicates',
            'duplicate_count': len(duplicates),
            'suggestion': 'Check for copy-paste errors',
            'duplicated_values': duplicates.head(5).to_dict('records')
        }

    return {'status': 'ok'}
```

---

## 3. Unit Confusion

### 3.1 Diameter Units

#### Common Mistakes
```python
# User meant to enter in centimeters (cm) but entered:
- Millimeters: 450 mm → Should be 45 cm
- Inches: 18 inches → Should be 45.7 cm
- Meters: 0.45 m → Should be 45 cm
```

#### Detection
```python
def detect_diameter_unit_error(values):
    mean_val = values.mean()

    # Millimeters (too large)
    if mean_val > 300:
        return {
            'detected_unit': 'millimeters',
            'expected_unit': 'centimeters',
            'conversion': 'divide_by_10',
            'message': f'Values appear to be in mm (mean: {mean_val:.1f})'
        }

    # Meters (too small)
    if mean_val < 1:
        return {
            'detected_unit': 'meters',
            'expected_unit': 'centimeters',
            'conversion': 'multiply_by_100',
            'message': f'Values appear to be in meters (mean: {mean_val:.3f})'
        }

    # Inches (need conversion)
    # Typical DBH in inches: 6-24", in cm: 15-60cm
    # If mean is 10-30 and all integers, might be inches
    if 10 <= mean_val <= 30 and values.apply(lambda x: x == int(x)).mean() > 0.9:
        return {
            'detected_unit': 'possibly_inches',
            'expected_unit': 'centimeters',
            'conversion': 'multiply_by_2.54',
            'confidence': 'medium',
            'message': 'Values may be in inches (all whole numbers 10-30 range)',
            'requires_confirmation': True
        }

    return {'status': 'ok', 'unit': 'centimeters'}
```

---

### 3.2 Height Units

#### Common Mistakes
```python
# User meant meters but entered:
- Feet: 80 feet → Should be 24.4 meters
- Centimeters: 2500 cm → Should be 25 meters
```

#### Detection
```python
def detect_height_unit_error(values):
    mean_val = values.mean()

    # Feet (too large for meters)
    if mean_val > 60:
        return {
            'detected_unit': 'possibly_feet',
            'expected_unit': 'meters',
            'conversion': 'multiply_by_0.3048',
            'message': f'Values appear too large for meters (mean: {mean_val:.1f})'
        }

    # Centimeters (too large)
    if mean_val > 500:
        return {
            'detected_unit': 'centimeters',
            'expected_unit': 'meters',
            'conversion': 'divide_by_100',
            'message': f'Values appear to be in cm (mean: {mean_val:.1f})'
        }

    return {'status': 'ok', 'unit': 'meters'}
```

---

### 3.3 Coordinate Units

#### Problem
```python
# Degrees-Minutes-Seconds (DMS) instead of Decimal Degrees
# Wrong: Lat = 27.42.30  (27° 42' 30")
# Right: Lat = 27.7083

# UTM coordinates in wrong zone
# Zone 44N vs 45N confusion
```

#### Detection
```python
def detect_coordinate_format(values):
    # Check if values contain DMS indicators
    if any(isinstance(v, str) and ('°' in v or "'" in v or '"' in v) for v in values):
        return {
            'format': 'DMS',
            'message': 'Coordinates in Degrees-Minutes-Seconds format',
            'action': 'convert_to_decimal_degrees'
        }

    # Check for reasonable decimal degrees range
    if values.min() > 360 or values.max() < -180:
        return {
            'format': 'unknown',
            'message': 'Coordinate values outside valid range',
            'action': 'verify_coordinate_system'
        }

    return {'format': 'decimal_degrees'}
```

---

## 4. Missing and Invalid Data

### 4.1 Missing Required Fields

#### Problem
```python
# Required fields with NULL/empty values
species = NULL
dia_cm = NULL
longitude = ""
latitude = NaN
```

#### Detection
```python
def validate_required_fields(df):
    required = ['species', 'dia_cm', 'longitude', 'latitude']
    issues = []

    for field in required:
        if field not in df.columns:
            issues.append({
                'severity': 'error',
                'field': field,
                'message': f'Required column "{field}" is missing',
                'action': 'add_column'
            })
        else:
            missing_count = df[field].isna().sum()
            if missing_count > 0:
                issues.append({
                    'severity': 'error',
                    'field': field,
                    'message': f'{missing_count} rows have missing {field}',
                    'affected_rows': df[df[field].isna()].index.tolist(),
                    'action': 'fill_or_remove_rows'
                })

    return issues
```

---

### 4.2 Invalid Characters

#### Problem
```python
# Non-numeric values in numeric columns
dia_cm = "45a"
height_m = "twenty five"
dia_cm = "45.5.2"  # Multiple decimal points
dia_cm = "N/A"
```

#### Detection
```python
def detect_invalid_characters(df, column):
    """Detect non-numeric values in numeric columns"""
    issues = []

    for idx, value in df[column].items():
        try:
            float(value)
        except (ValueError, TypeError):
            issues.append({
                'row': idx + 2,
                'column': column,
                'value': value,
                'message': f'Non-numeric value: "{value}"',
                'action': 'correct_or_remove'
            })

    return issues
```

---

### 4.3 Implicit Missing Values

#### Problem
```python
# Values that represent "missing" but aren't NULL
dia_cm = 0      # Used as placeholder
height_m = -999  # Common missing value code
species = "NA"
species = "unknown"
class = ""      # Empty string
```

#### Detection
```python
def detect_implicit_missing(df):
    """Detect common missing value codes"""
    missing_codes = {
        'numeric': [0, -999, -9999, 999, 9999],
        'string': ['NA', 'N/A', 'na', 'n/a', 'null', 'NULL',
                   'unknown', 'Unknown', 'UNKNOWN', '', ' ']
    }

    issues = []

    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            for code in missing_codes['numeric']:
                count = (df[col] == code).sum()
                if count > 0:
                    issues.append({
                        'column': col,
                        'missing_code': code,
                        'count': count,
                        'message': f'{count} rows use {code} as missing value',
                        'action': 'convert_to_null'
                    })
        else:
            for code in missing_codes['string']:
                count = (df[col] == code).sum()
                if count > 0:
                    issues.append({
                        'column': col,
                        'missing_code': code,
                        'count': count,
                        'action': 'convert_to_null'
                    })

    return issues
```

---

## 5. Spatial Data Issues

### 5.1 Duplicate Coordinates

#### Problem
```python
# Multiple trees at exact same location (impossible)
Tree 1: (85.3240, 27.7172)
Tree 2: (85.3240, 27.7172)  # Exact duplicate
Tree 3: (85.3240, 27.7172)  # Copy-paste error
```

#### Detection
```python
def detect_duplicate_locations(df, lon_col, lat_col, tolerance=0.00001):
    """
    Detect trees at same location (within ~1 meter)
    tolerance = 0.00001 degrees ≈ 1 meter
    """
    duplicates = []

    for idx, row in df.iterrows():
        # Find nearby trees
        nearby = df[
            (abs(df[lon_col] - row[lon_col]) < tolerance) &
            (abs(df[lat_col] - row[lat_col]) < tolerance) &
            (df.index != idx)
        ]

        if len(nearby) > 0:
            duplicates.append({
                'row': idx + 2,
                'coordinates': (row[lon_col], row[lat_col]),
                'duplicate_count': len(nearby),
                'duplicate_rows': (nearby.index + 2).tolist()
            })

    if duplicates:
        return {
            'severity': 'warning',
            'message': f'{len(duplicates)} trees have duplicate coordinates',
            'duplicates': duplicates,
            'suggestion': 'Check for copy-paste errors or GPS measurement issues'
        }

    return {'status': 'ok'}
```

---

### 5.2 Coordinates Outside Valid Bounds

#### Problem
```python
# Coordinates outside Nepal
Longitude = 95.5  # Too far east (Myanmar)
Latitude = 35.2   # Too far north (Tibet)
Longitude = 0.0   # Default/error value
Latitude = 0.0    # Default/error value
```

#### Detection
```python
NEPAL_BOUNDS = {
    'lon_min': 80.0, 'lon_max': 88.3,
    'lat_min': 26.3, 'lat_max': 30.5
}

WORLD_BOUNDS = {
    'lon_min': -180, 'lon_max': 180,
    'lat_min': -90, 'lat_max': 90
}

def validate_coordinates(lon, lat):
    # Check world bounds first
    if not (WORLD_BOUNDS['lon_min'] <= lon <= WORLD_BOUNDS['lon_max']):
        return {
            'severity': 'error',
            'message': f'Longitude {lon} outside valid range (-180 to 180)',
            'action': 'reject_row'
        }

    if not (WORLD_BOUNDS['lat_min'] <= lat <= WORLD_BOUNDS['lat_max']):
        return {
            'severity': 'error',
            'message': f'Latitude {lat} outside valid range (-90 to 90)',
            'action': 'reject_row'
        }

    # Check Nepal bounds
    if not (NEPAL_BOUNDS['lon_min'] <= lon <= NEPAL_BOUNDS['lon_max']):
        return {
            'severity': 'warning',
            'message': f'Longitude {lon} outside Nepal bounds (80-88.3°E)',
            'suggestion': 'Tree location appears outside Nepal',
            'action': 'flag_for_review'
        }

    if not (NEPAL_BOUNDS['lat_min'] <= lat <= NEPAL_BOUNDS['lat_max']):
        return {
            'severity': 'warning',
            'message': f'Latitude {lat} outside Nepal bounds (26.3-30.5°N)',
            'suggestion': 'Tree location appears outside Nepal',
            'action': 'flag_for_review'
        }

    # Check for default/error values
    if lon == 0.0 and lat == 0.0:
        return {
            'severity': 'error',
            'message': 'Coordinates are (0, 0) - Null Island',
            'suggestion': 'GPS coordinates not recorded',
            'action': 'reject_row'
        }

    return {'status': 'ok'}
```

---

### 5.3 Spatial Clustering Issues

#### Problem
```python
# All trees in small area (< 1 hectare) but user claims 50 hectares
# Trees in straight line (GPS track error)
# Trees form perfect grid (simulated data)
```

#### Detection
```python
def analyze_spatial_distribution(df, lon_col, lat_col):
    """Analyze spatial pattern for anomalies"""
    from shapely.geometry import MultiPoint

    # Create point geometry
    points = [Point(lon, lat) for lon, lat in zip(df[lon_col], df[lat_col])]
    multipoint = MultiPoint(points)

    # Calculate convex hull area
    hull = multipoint.convex_hull
    area_deg2 = hull.area
    area_ha = area_deg2 * 111320 * 111320 / 10000  # Rough conversion

    issues = []

    # Check if area is suspiciously small
    tree_count = len(df)
    expected_min_area = tree_count * 0.01  # Assume min 100 trees/ha

    if area_ha < expected_min_area:
        issues.append({
            'severity': 'warning',
            'message': f'{tree_count} trees in only {area_ha:.2f} hectares',
            'suggestion': 'Trees very clustered - check coordinates',
            'area_hectares': round(area_ha, 2)
        })

    # Check for perfect grid pattern (simulated data)
    lon_unique = df[lon_col].nunique()
    lat_unique = df[lat_col].nunique()

    if lon_unique * lat_unique == tree_count:
        issues.append({
            'severity': 'warning',
            'message': 'Trees form perfect grid pattern',
            'suggestion': 'Data may be simulated/synthetic',
            'grid_size': f'{lon_unique} × {lat_unique}'
        })

    return issues
```

---

## 6. File Format Issues

### 6.1 Encoding Problems

#### Problem
```python
# Unicode characters in species names
"Schima wallichii" → "Schima wallichi�" (UTF-8/ASCII issue)
"Shorea robusta" → "ShÃ³rea robusta" (encoding corruption)
```

#### Detection
```python
def detect_encoding_issues(df):
    """Detect garbled characters from encoding problems"""
    issues = []

    for col in df.select_dtypes(include=['object']).columns:
        for idx, value in df[col].items():
            if isinstance(value, str):
                # Check for common encoding artifacts
                if any(char in value for char in ['�', 'Ã', 'â€']):
                    issues.append({
                        'row': idx + 2,
                        'column': col,
                        'value': value,
                        'message': 'Possible encoding issue (garbled characters)',
                        'suggestion': 'Re-save CSV as UTF-8'
                    })

    return issues
```

---

### 6.2 Excel Date Conversion

#### Problem
```python
# Excel auto-converts some text to dates
"1-2" → "Jan-2" or "2001-01-02"
Scientific notation: Large numbers shown as "1.5E+08"
```

#### Detection
```python
def detect_excel_date_corruption(df, column):
    """Detect Excel's automatic date conversion"""
    issues = []

    for idx, value in df[column].items():
        value_str = str(value)

        # Check for date-like patterns
        if re.match(r'\d{4}-\d{2}-\d{2}', value_str):
            issues.append({
                'row': idx + 2,
                'column': column,
                'value': value,
                'message': 'Value looks like Excel date conversion',
                'suggestion': 'Format cells as Text before entering data'
            })

        # Check for scientific notation
        if 'E+' in value_str or 'e+' in value_str:
            issues.append({
                'row': idx + 2,
                'column': column,
                'value': value,
                'message': 'Scientific notation detected',
                'suggestion': 'Format cells as Number with decimal places'
            })

    return issues
```

---

### 6.3 Extra Columns/Rows

#### Problem
```python
# Extra empty rows at end
# Extra summary rows (totals, averages)
# Multiple header rows
# Merged cells causing data issues
```

#### Detection
```python
def detect_extra_rows(df):
    """Detect summary/empty rows that should be removed"""
    issues = []

    # Check for empty rows
    empty_rows = df[df.isna().all(axis=1)]
    if len(empty_rows) > 0:
        issues.append({
            'type': 'empty_rows',
            'count': len(empty_rows),
            'rows': (empty_rows.index + 2).tolist(),
            'action': 'remove_rows'
        })

    # Check for summary rows (common keywords)
    summary_keywords = ['total', 'sum', 'average', 'mean', 'count']
    for col in df.select_dtypes(include=['object']).columns:
        for idx, value in df[col].items():
            if isinstance(value, str) and any(kw in value.lower() for kw in summary_keywords):
                issues.append({
                    'type': 'summary_row',
                    'row': idx + 2,
                    'value': value,
                    'action': 'remove_row'
                })

    return issues
```

---

## 7. Statistical Outliers

### 7.1 IQR-based Outlier Detection

```python
def detect_statistical_outliers(df, column, multiplier=3):
    """
    Detect outliers using Interquartile Range (IQR) method
    multiplier=3 is more conservative (fewer false positives)
    """
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1

    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR

    outliers = df[
        (df[column] < lower_bound) |
        (df[column] > upper_bound)
    ]

    if len(outliers) > 0:
        return {
            'column': column,
            'outlier_count': len(outliers),
            'outlier_rows': (outliers.index + 2).tolist(),
            'outlier_values': outliers[column].tolist(),
            'expected_range': [round(lower_bound, 2), round(upper_bound, 2)],
            'severity': 'warning',
            'message': f'{len(outliers)} outliers detected in {column}'
        }

    return {'status': 'ok'}
```

---

### 7.2 Z-Score Outlier Detection

```python
def detect_zscore_outliers(df, column, threshold=3.5):
    """
    Detect extreme outliers using Z-score
    threshold=3.5 means > 3.5 standard deviations from mean
    """
    from scipy import stats

    z_scores = np.abs(stats.zscore(df[column].dropna()))
    outlier_indices = np.where(z_scores > threshold)[0]

    if len(outlier_indices) > 0:
        outlier_values = df[column].iloc[outlier_indices]
        return {
            'column': column,
            'method': 'z_score',
            'threshold': threshold,
            'outlier_count': len(outlier_indices),
            'outlier_rows': (outlier_indices + 2).tolist(),
            'outlier_values': outlier_values.tolist(),
            'z_scores': z_scores[outlier_indices].tolist()
        }

    return {'status': 'ok'}
```

---

## 8. Logical Inconsistencies

### 8.1 Height-Diameter Relationship

```python
def validate_height_diameter_relationship(df, dbh_col, height_col):
    """
    Validate that height and diameter are logically consistent
    """
    issues = []

    for idx, row in df.iterrows():
        dbh = row[dbh_col]
        height = row[height_col]

        if pd.isna(dbh) or pd.isna(height):
            continue

        # Calculate H/D ratio
        hd_ratio = height / (dbh / 100)

        # Flag suspicious ratios
        if hd_ratio < 20:
            issues.append({
                'row': idx + 2,
                'dbh_cm': dbh,
                'height_m': height,
                'hd_ratio': round(hd_ratio, 1),
                'message': 'Tree appears too short for its diameter',
                'severity': 'warning'
            })

        elif hd_ratio > 200:
            issues.append({
                'row': idx + 2,
                'dbh_cm': dbh,
                'height_m': height,
                'hd_ratio': round(hd_ratio, 1),
                'message': 'Tree appears too tall for its diameter',
                'severity': 'warning',
                'suggestion': 'May have swapped height and DBH?'
            })

    return issues
```

---

### 8.2 Tree Class vs Size Inconsistency

```python
def validate_class_size_consistency(df, dbh_col, class_col):
    """
    Validate that tree quality class matches size
    Class A (good) trees should generally be larger
    """
    issues = []

    # Typical expectations
    # Class A: Good quality, usually larger/mature trees
    # Class B/C: Poor quality, smaller or defective trees

    for idx, row in df.iterrows():
        dbh = row[dbh_col]
        tree_class = row[class_col]

        if pd.isna(tree_class):
            continue

        # Class A tree but very small
        if tree_class == 'A' and dbh < 15:
            issues.append({
                'row': idx + 2,
                'dbh_cm': dbh,
                'class': tree_class,
                'message': 'Small tree (DBH < 15cm) marked as Class A',
                'severity': 'info',
                'suggestion': 'Verify tree class designation'
            })

        # Large tree but poor class
        if tree_class in ['C', 'D'] and dbh > 60:
            issues.append({
                'row': idx + 2,
                'dbh_cm': dbh,
                'class': tree_class,
                'message': 'Large tree (DBH > 60cm) marked as poor class',
                'severity': 'info',
                'suggestion': 'Verify tree class - large trees usually better quality'
            })

    return issues
```

---

### 8.3 Species-Specific Validations

```python
def validate_species_specific_rules(row, species_rules):
    """
    Validate measurements against species-specific constraints
    """
    species = row['species']
    dbh = row['dia_cm']
    height = row['height_m']

    if species not in species_rules:
        return {'status': 'ok'}

    rules = species_rules[species]
    issues = []

    # Check maximum DBH for species
    if dbh > rules['max_dbh']:
        issues.append({
            'field': 'dbh',
            'value': dbh,
            'max_expected': rules['max_dbh'],
            'message': f'{species} DBH {dbh}cm exceeds typical maximum ({rules["max_dbh"]}cm)',
            'severity': 'warning'
        })

    # Check maximum height for species
    if height > rules['max_height']:
        issues.append({
            'field': 'height',
            'value': height,
            'max_expected': rules['max_height'],
            'message': f'{species} height {height}m exceeds typical maximum ({rules["max_height"]}m)',
            'severity': 'warning'
        })

    # Check species-specific H/D ratio
    hd_ratio = height / (dbh / 100)
    if not (rules['hd_ratio_min'] <= hd_ratio <= rules['hd_ratio_max']):
        issues.append({
            'field': 'height_diameter_ratio',
            'value': round(hd_ratio, 1),
            'expected_range': [rules['hd_ratio_min'], rules['hd_ratio_max']],
            'message': f'{species} H/D ratio {hd_ratio:.1f} outside normal range',
            'severity': 'warning'
        })

    return issues

# Species-specific rules database
SPECIES_RULES = {
    'Shorea robusta': {
        'max_dbh': 150,
        'max_height': 35,
        'hd_ratio_min': 50,
        'hd_ratio_max': 100
    },
    'Pinus roxburghii': {
        'max_dbh': 120,
        'max_height': 45,
        'hd_ratio_min': 80,
        'hd_ratio_max': 120
    },
    # ... more species
}
```

---

## Summary: Validation Severity Levels

### ERROR (Must Fix - Reject Row)
- ❌ Missing required fields (species, DBH, coordinates)
- ❌ Negative values
- ❌ DBH > 200 cm (absolutely impossible)
- ❌ Height > 50 m (Nepal maximum)
- ❌ Coordinates outside world bounds
- ❌ Non-numeric values in numeric fields
- ❌ Coordinates at (0, 0)

### WARNING (Review Recommended - Flag Row)
- ⚠️ DBH > species maximum but < 200 cm
- ⚠️ Height > species maximum but < 50 m
- ⚠️ Unusual H/D ratios (< 30 or > 150)
- ⚠️ Coordinates outside Nepal bounds
- ⚠️ Statistical outliers (IQR method)
- ⚠️ Duplicate coordinates
- ⚠️ Species fuzzy match < 95%
- ⚠️ Girth detected and converted

### INFO (Informational - Auto-corrected)
- ℹ️ Species name normalized (capitalization)
- ℹ️ Coordinate column detected
- ℹ️ CRS auto-detected
- ℹ️ Seedling height ignored
- ℹ️ Tree class assigned (if missing)
- ℹ️ Decimal notation corrected (, → .)

---

## Complete Validation Workflow

```python
async def comprehensive_validation(df, user_specified_crs=None):
    """
    Run ALL validation checks in proper order
    """
    report = {
        'errors': [],
        'warnings': [],
        'info': [],
        'statistics': {}
    }

    # 1. File format checks
    encoding_issues = detect_encoding_issues(df)
    report['warnings'].extend(encoding_issues)

    # 2. Missing data checks
    missing_fields = validate_required_fields(df)
    report['errors'].extend(missing_fields)

    if report['errors']:
        return report  # Stop if critical errors

    # 3. Detect implicit missing values
    implicit_missing = detect_implicit_missing(df)
    report['info'].extend(implicit_missing)

    # 4. Column detection
    coord_detector = CoordinateDetector()
    x_col, y_col = coord_detector.detect_coordinate_columns(df)
    dbh_col = detect_diameter_column(df)
    height_col = detect_height_column(df)
    species_col = detect_species_column(df)

    # 5. Unit validation
    if dbh_col:
        unit_check = detect_diameter_unit_error(df[dbh_col])
        if unit_check['status'] != 'ok':
            report['warnings'].append(unit_check)

    # 6. Decimal point errors
    decimal_check = detect_decimal_errors(df, dbh_col)
    if decimal_check['status'] != 'ok':
        report['warnings'].append(decimal_check)

    # 7. Column swapping detection
    if dbh_col and height_col:
        swap_check = detect_column_swap(df, dbh_col, height_col)
        if swap_check['status'] != 'ok':
            report['errors'].append(swap_check)

    # 8. Range validation
    for idx, row in df.iterrows():
        # DBH validation
        dbh_validation = validate_dbh(row[dbh_col], row[species_col])
        if dbh_validation['severity'] == 'error':
            report['errors'].append({**dbh_validation, 'row': idx+2})
        elif dbh_validation.get('severity') == 'warning':
            report['warnings'].append({**dbh_validation, 'row': idx+2})

        # Height validation
        if pd.notna(row[height_col]):
            height_validation = validate_height(
                row[height_col],
                row[species_col],
                row[dbh_col]
            )
            if height_validation.get('severity'):
                report[height_validation['severity']+'s'].append({
                    **height_validation, 'row': idx+2
                })

        # Coordinate validation
        coord_validation = validate_coordinates(row[x_col], row[y_col])
        if coord_validation['severity'] == 'error':
            report['errors'].append({**coord_validation, 'row': idx+2})
        elif coord_validation.get('severity') == 'warning':
            report['warnings'].append({**coord_validation, 'row': idx+2})

    # 9. Statistical outliers
    outliers_dbh = detect_statistical_outliers(df, dbh_col)
    if outliers_dbh['status'] != 'ok':
        report['warnings'].append(outliers_dbh)

    # 10. Spatial validation
    duplicate_coords = detect_duplicate_locations(df, x_col, y_col)
    if duplicate_coords['status'] != 'ok':
        report['warnings'].append(duplicate_coords)

    # 11. Species validation
    species_matcher = SpeciesMatcher(db)
    for idx, row in df.iterrows():
        matched, confidence, method = species_matcher.match_species(row[species_col])
        if method == 'fuzzy':
            report['warnings'].append({
                'row': idx+2,
                'column': species_col,
                'original': row[species_col],
                'corrected': matched,
                'confidence': confidence
            })

    # 12. Logical consistency
    hd_issues = validate_height_diameter_relationship(df, dbh_col, height_col)
    report['warnings'].extend(hd_issues)

    # 13. Calculate statistics
    report['statistics'] = {
        'total_rows': len(df),
        'error_count': len(report['errors']),
        'warning_count': len(report['warnings']),
        'valid_rows': len(df) - len(report['errors'])
    }

    return report
```

---

This comprehensive document now covers EVERY possible data quality issue!
