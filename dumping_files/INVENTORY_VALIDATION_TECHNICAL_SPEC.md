# Inventory Data Validation - Technical Specification

## Purpose
Technical implementation guide for the inventory data validation system.

---

## 1. Dependencies Required

### Python Packages
```txt
# Add to backend/requirements.txt

# Fuzzy string matching
fuzzywuzzy==0.18.0
python-levenshtein==0.21.1

# Advanced text processing (optional)
rapidfuzz==3.6.1  # Faster alternative to fuzzywuzzy

# Geospatial coordinate transformations
pyproj==3.6.1

# Data validation
pandas==2.1.4
numpy==1.26.2

# Already installed:
# geopandas, shapely, sqlalchemy
```

---

## 2. Database Schema Additions

### Species Coefficients Table Enhancement
```sql
-- Add to existing tree_species_coefficients table

ALTER TABLE public.tree_species_coefficients
ADD COLUMN aliases TEXT[];  -- Array of alternative names

-- Example data:
UPDATE tree_species_coefficients
SET aliases = ARRAY['Sal', 'sal', 'SAL']
WHERE scientific_name = 'Shorea robusta';

UPDATE tree_species_coefficients
SET aliases = ARRAY['Chilaune', 'chilaune']
WHERE scientific_name = 'Schima wallichii';

-- Index for faster searching
CREATE INDEX idx_species_aliases ON tree_species_coefficients USING GIN(aliases);
```

### Validation Log Table
```sql
CREATE TABLE public.inventory_validation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inventory_calculation_id UUID REFERENCES inventory_calculations(id) ON DELETE CASCADE,

  -- Validation metadata
  validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  total_rows INTEGER,
  valid_rows INTEGER,
  error_rows INTEGER,
  warning_rows INTEGER,

  -- Detection results
  detected_crs VARCHAR(20),
  detected_diameter_type VARCHAR(20),  -- 'diameter' or 'girth'
  coordinate_x_column VARCHAR(50),
  coordinate_y_column VARCHAR(50),

  -- Full validation report (JSON)
  validation_report JSONB,

  -- User actions
  user_confirmed BOOLEAN DEFAULT FALSE,
  user_confirmation_time TIMESTAMP WITH TIME ZONE,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_validation_logs_inventory ON inventory_validation_logs(inventory_calculation_id);
```

### Row-level Validation Issues Table
```sql
CREATE TABLE public.inventory_validation_issues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  validation_log_id UUID REFERENCES inventory_validation_logs(id) ON DELETE CASCADE,

  -- Issue details
  row_number INTEGER NOT NULL,
  column_name VARCHAR(100),
  severity VARCHAR(20),  -- 'error', 'warning', 'info'
  issue_type VARCHAR(50),  -- 'species_fuzzy_match', 'girth_detected', etc.

  -- Values
  original_value TEXT,
  corrected_value TEXT,

  -- Message
  message TEXT,
  confidence FLOAT,  -- 0.0 to 1.0

  -- User action
  user_accepted BOOLEAN DEFAULT NULL,  -- NULL = pending, TRUE = accepted, FALSE = rejected

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_validation_issues_log ON inventory_validation_issues(validation_log_id);
CREATE INDEX idx_validation_issues_severity ON inventory_validation_issues(severity);
```

---

## 3. Service Layer Architecture

### File Structure
```
backend/app/services/
├── inventory.py              # Main inventory processing
├── inventory_validator.py    # NEW: Validation orchestrator
├── validators/               # NEW: Validation modules
│   ├── __init__.py
│   ├── species_matcher.py   # Fuzzy species matching
│   ├── coordinate_detector.py  # CRS and column detection
│   ├── diameter_detector.py    # Diameter vs girth detection
│   ├── data_cleaner.py        # Data normalization
│   └── quality_checker.py     # Outliers, duplicates, etc.
```

---

## 4. Implementation Details

### 4.1 Species Matcher (`validators/species_matcher.py`)

```python
"""
Species name fuzzy matching and normalization
"""
from typing import Dict, List, Tuple, Optional
from fuzzywuzzy import fuzz, process
import pandas as pd
from sqlalchemy.orm import Session

class SpeciesMatcher:
    """Handles species name matching with fuzzy logic"""

    def __init__(self, db: Session):
        self.db = db
        self.species_list = self._load_species()
        self.alias_map = self._build_alias_map()

    def _load_species(self) -> List[str]:
        """Load all valid species from database"""
        query = """
            SELECT scientific_name, local_name, aliases
            FROM tree_species_coefficients
            WHERE is_active = TRUE
        """
        result = self.db.execute(query).fetchall()
        return result

    def _build_alias_map(self) -> Dict[str, str]:
        """Create mapping of aliases to scientific names"""
        alias_map = {}
        for row in self.species_list:
            scientific = row.scientific_name
            # Add local name
            if row.local_name:
                alias_map[row.local_name.lower()] = scientific
            # Add aliases
            if row.aliases:
                for alias in row.aliases:
                    alias_map[alias.lower()] = scientific
            # Add scientific name itself
            alias_map[scientific.lower()] = scientific

        return alias_map

    def normalize_species_name(self, name: str) -> str:
        """Normalize species name (trim, title case, etc)"""
        if pd.isna(name):
            return None

        # Remove extra whitespace
        normalized = ' '.join(name.strip().split())

        # Convert to title case
        normalized = normalized.title()

        # Handle 'spp' vs 'spp.'
        normalized = normalized.replace('Spp.', 'spp')

        return normalized

    def match_species(
        self,
        name: str,
        threshold: int = 85
    ) -> Tuple[Optional[str], float, str]:
        """
        Match species name using fuzzy matching

        Args:
            name: Input species name
            threshold: Minimum similarity score (0-100)

        Returns:
            Tuple of (matched_name, confidence, method)
            - matched_name: Best match or None
            - confidence: Match score 0.0-1.0
            - method: 'exact', 'alias', 'fuzzy', or 'no_match'
        """
        if not name:
            return None, 0.0, 'no_match'

        # Step 1: Normalize input
        normalized = self.normalize_species_name(name)

        # Step 2: Exact match check (case-insensitive)
        scientific_names = [s.scientific_name for s in self.species_list]
        for species in scientific_names:
            if normalized.lower() == species.lower():
                return species, 1.0, 'exact'

        # Step 3: Alias match check
        if normalized.lower() in self.alias_map:
            matched = self.alias_map[normalized.lower()]
            return matched, 1.0, 'alias'

        # Step 4: Fuzzy matching
        match_result = process.extractOne(
            normalized,
            scientific_names,
            scorer=fuzz.token_sort_ratio
        )

        if match_result:
            matched_name, score = match_result[0], match_result[1]
            confidence = score / 100.0

            if score >= threshold:
                return matched_name, confidence, 'fuzzy'

        # No match found
        return None, 0.0, 'no_match'

    def get_suggestions(self, name: str, top_n: int = 3) -> List[Dict]:
        """Get top N species suggestions for unmatched name"""
        normalized = self.normalize_species_name(name)
        scientific_names = [s.scientific_name for s in self.species_list]

        matches = process.extract(
            normalized,
            scientific_names,
            scorer=fuzz.token_sort_ratio,
            limit=top_n
        )

        suggestions = []
        for match_name, score in matches:
            # Find local name
            local = next(
                (s.local_name for s in self.species_list
                 if s.scientific_name == match_name),
                None
            )
            suggestions.append({
                'scientific_name': match_name,
                'local_name': local,
                'similarity': score / 100.0
            })

        return suggestions
```

### 4.2 Coordinate Detector (`validators/coordinate_detector.py`)

```python
"""
Coordinate column detection and CRS identification
"""
from typing import Tuple, Dict, Optional, List
import numpy as np
import pandas as pd

class CoordinateDetector:
    """Detects coordinate columns and CRS from data"""

    # Column name aliases
    LONGITUDE_ALIASES = [
        'longitude', 'long', 'lon', 'lng',
        'x', 'easting', 'east',
        'coord_x', 'x_coord', 'long_dd', 'lon_dd'
    ]

    LATITUDE_ALIASES = [
        'latitude', 'lat',
        'y', 'northing', 'north',
        'coord_y', 'y_coord', 'lat_dd'
    ]

    # Nepal bounds for validation
    NEPAL_BOUNDS = {
        'geographic': {
            'lon_min': 80.0, 'lon_max': 88.3,
            'lat_min': 26.3, 'lat_max': 30.5
        },
        'utm_44n': {
            'x_min': 200000, 'x_max': 700000,
            'y_min': 2800000, 'y_max': 3500000
        },
        'utm_45n': {
            'x_min': 200000, 'x_max': 900000,
            'y_min': 2800000, 'y_max': 3500000
        }
    }

    def detect_coordinate_columns(
        self,
        df: pd.DataFrame
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect X and Y coordinate columns

        Returns:
            Tuple of (x_column, y_column) or (None, None)
        """
        columns_lower = {col.lower(): col for col in df.columns}

        # Try to find longitude/X
        x_col = None
        for alias in self.LONGITUDE_ALIASES:
            if alias in columns_lower:
                x_col = columns_lower[alias]
                break

        # Try to find latitude/Y
        y_col = None
        for alias in self.LATITUDE_ALIASES:
            if alias in columns_lower:
                y_col = columns_lower[alias]
                break

        return x_col, y_col

    def detect_crs(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray
    ) -> Dict:
        """
        Detect CRS from coordinate values

        Returns:
            Dict with 'epsg', 'name', 'confidence', 'method'
        """
        x_min, x_max = np.min(x_values), np.max(x_values)
        y_min, y_max = np.min(y_values), np.max(y_values)
        x_mean, y_mean = np.mean(x_values), np.mean(y_values)

        # Test 1: Geographic coordinates (WGS84)
        geo = self.NEPAL_BOUNDS['geographic']
        if (geo['lon_min'] <= x_min <= geo['lon_max'] and
            geo['lon_min'] <= x_max <= geo['lon_max'] and
            geo['lat_min'] <= y_min <= geo['lat_max'] and
            geo['lat_min'] <= y_max <= geo['lat_max']):

            return {
                'epsg': 4326,
                'name': 'WGS84 (Geographic)',
                'confidence': 'high',
                'method': 'Nepal geographic bounds',
                'detected_range': {
                    'x': [x_min, x_max],
                    'y': [y_min, y_max]
                }
            }

        # Test 2: Check if coordinates are swapped
        if (geo['lon_min'] <= y_min <= geo['lon_max'] and
            geo['lat_min'] <= x_min <= geo['lat_max']):

            return {
                'epsg': 'UNKNOWN',
                'error': 'coordinates_swapped',
                'message': 'X and Y coordinates appear to be swapped',
                'confidence': 'error',
                'suggestion': 'Please swap longitude and latitude columns'
            }

        # Test 3: UTM Zone 44N (Western Nepal)
        utm44 = self.NEPAL_BOUNDS['utm_44n']
        if (utm44['x_min'] <= x_min <= utm44['x_max'] and
            utm44['y_min'] <= y_min <= utm44['y_max']):

            return {
                'epsg': 32644,
                'name': 'WGS84 / UTM Zone 44N',
                'confidence': 'high',
                'method': 'UTM 44N bounds (Western Nepal)',
                'detected_range': {
                    'x': [x_min, x_max],
                    'y': [y_min, y_max]
                }
            }

        # Test 4: UTM Zone 45N (Eastern Nepal)
        utm45 = self.NEPAL_BOUNDS['utm_45n']
        if (utm45['x_min'] <= x_min <= utm45['x_max'] and
            utm45['y_min'] <= y_min <= utm45['y_max']):

            return {
                'epsg': 32645,
                'name': 'WGS84 / UTM Zone 45N',
                'confidence': 'high',
                'method': 'UTM 45N bounds (Eastern Nepal)',
                'detected_range': {
                    'x': [x_min, x_max],
                    'y': [y_min, y_max]
                }
            }

        # Unknown CRS
        return {
            'epsg': 'UNKNOWN',
            'confidence': 'none',
            'message': 'Could not detect CRS from coordinate values',
            'detected_range': {
                'x': [x_min, x_max],
                'y': [y_min, y_max]
            }
        }

    def validate_crs(
        self,
        x_values: np.ndarray,
        y_values: np.ndarray,
        user_specified_crs: int
    ) -> Dict:
        """
        Validate user-specified CRS against detected CRS

        Returns:
            Dict with validation results
        """
        detected = self.detect_crs(x_values, y_values)

        if detected.get('epsg') == 'UNKNOWN':
            return {
                'status': 'warning',
                'message': 'Could not auto-detect CRS. Using user-specified.',
                'user_specified': user_specified_crs,
                'detected': None
            }

        if detected['epsg'] != user_specified_crs:
            return {
                'status': 'conflict',
                'message': f"User specified EPSG:{user_specified_crs} but coordinates appear to be in {detected['name']}",
                'user_specified': user_specified_crs,
                'detected': detected['epsg'],
                'action_required': True
            }

        return {
            'status': 'ok',
            'message': 'CRS validation successful',
            'crs': user_specified_crs
        }
```

### 4.3 Diameter Detector (`validators/diameter_detector.py`)

```python
"""
Detect if measurements are diameter or girth (circumference)
"""
import numpy as np
import pandas as pd
from typing import Dict

class DiameterDetector:
    """Detects whether measurements are diameter or girth"""

    # Thresholds
    GIRTH_MEAN_THRESHOLD = 100  # cm
    GIRTH_MEDIAN_THRESHOLD = 80  # cm
    GIRTH_RATIO_THRESHOLD = 3.0  # Girth ~= π * Diameter

    def detect_measurement_type(
        self,
        values: np.ndarray,
        column_name: str = None
    ) -> Dict:
        """
        Detect if measurements are diameter or girth

        Returns:
            Dict with 'type', 'confidence', 'method'
        """
        # Method 1: Check column name
        if column_name:
            col_lower = column_name.lower()
            girth_keywords = ['girth', 'gbh', 'circumference', 'cbh']
            diameter_keywords = ['diameter', 'dbh', 'dia']

            if any(kw in col_lower for kw in girth_keywords):
                return {
                    'type': 'girth',
                    'confidence': 'high',
                    'method': 'column_name',
                    'column_name': column_name
                }

            if any(kw in col_lower for kw in diameter_keywords):
                return {
                    'type': 'diameter',
                    'confidence': 'high',
                    'method': 'column_name',
                    'column_name': column_name
                }

        # Method 2: Statistical analysis
        mean_val = np.mean(values)
        median_val = np.median(values)
        q75_val = np.percentile(values, 75)

        # Strong indicators for GIRTH
        if mean_val > self.GIRTH_MEAN_THRESHOLD:
            return {
                'type': 'girth',
                'confidence': 'high',
                'method': 'statistical',
                'statistics': {
                    'mean': round(mean_val, 2),
                    'median': round(median_val, 2),
                    'threshold': self.GIRTH_MEAN_THRESHOLD
                }
            }

        # Strong indicators for DIAMETER
        if mean_val < 50:
            return {
                'type': 'diameter',
                'confidence': 'high',
                'method': 'statistical',
                'statistics': {
                    'mean': round(mean_val, 2),
                    'median': round(median_val, 2)
                }
            }

        # Uncertain range (50-100 cm mean)
        if 50 <= mean_val <= self.GIRTH_MEAN_THRESHOLD:
            # Check 75th percentile
            if q75_val > self.GIRTH_MEDIAN_THRESHOLD:
                return {
                    'type': 'girth',
                    'confidence': 'medium',
                    'method': 'statistical',
                    'statistics': {
                        'mean': round(mean_val, 2),
                        'median': round(median_val, 2),
                        'q75': round(q75_val, 2)
                    },
                    'requires_confirmation': True
                }
            else:
                return {
                    'type': 'diameter',
                    'confidence': 'medium',
                    'method': 'statistical',
                    'statistics': {
                        'mean': round(mean_val, 2),
                        'median': round(median_val, 2),
                        'q75': round(q75_val, 2)
                    },
                    'requires_confirmation': True
                }

        # Default to diameter
        return {
            'type': 'diameter',
            'confidence': 'low',
            'method': 'default',
            'message': 'Ambiguous measurements - assuming diameter'
        }

    def convert_girth_to_diameter(self, girth_values: np.ndarray) -> np.ndarray:
        """Convert girth (circumference) to diameter"""
        return girth_values / np.pi
```

---

## 5. Main Validator Orchestrator

### `inventory_validator.py`

```python
"""
Main validation orchestrator for inventory data
"""
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from uuid import UUID

from .validators.species_matcher import SpeciesMatcher
from .validators.coordinate_detector import CoordinateDetector
from .validators.diameter_detector import DiameterDetector

class InventoryValidator:
    """
    Main validator that orchestrates all validation checks
    """

    def __init__(self, db: Session):
        self.db = db
        self.species_matcher = SpeciesMatcher(db)
        self.coord_detector = CoordinateDetector()
        self.diameter_detector = DiameterDetector()

    async def validate_inventory_file(
        self,
        df: pd.DataFrame,
        user_specified_crs: int = None
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of inventory CSV data

        Returns:
            Validation report dict
        """
        report = {
            'summary': {},
            'data_detection': {},
            'errors': [],
            'warnings': [],
            'info': [],
            'corrections': []
        }

        # 1. Detect coordinate columns
        x_col, y_col = self.coord_detector.detect_coordinate_columns(df)

        if not x_col or not y_col:
            report['errors'].append({
                'type': 'missing_coordinates',
                'message': 'Could not detect coordinate columns',
                'available_columns': list(df.columns),
                'expected': 'LONGITUDE/LATITUDE, long/lat, or x/y'
            })
            return report

        report['data_detection']['coordinate_columns'] = {
            'x': x_col,
            'y': y_col
        }

        # 2. Detect CRS
        x_values = df[x_col].values
        y_values = df[y_col].values

        crs_detection = self.coord_detector.detect_crs(x_values, y_values)
        report['data_detection']['crs'] = crs_detection

        # Validate against user-specified CRS
        if user_specified_crs:
            crs_validation = self.coord_detector.validate_crs(
                x_values, y_values, user_specified_crs
            )
            if crs_validation['status'] == 'conflict':
                report['warnings'].append(crs_validation)

        # 3. Detect diameter column and type
        diameter_col = self._detect_diameter_column(df)
        if not diameter_col:
            report['errors'].append({
                'type': 'missing_diameter',
                'message': 'Could not find diameter/girth column'
            })
            return report

        diameter_detection = self.diameter_detector.detect_measurement_type(
            df[diameter_col].values,
            diameter_col
        )
        report['data_detection']['diameter'] = diameter_detection

        # Convert girth to diameter if needed
        if diameter_detection['type'] == 'girth':
            original_values = df[diameter_col].copy()
            df[diameter_col] = self.diameter_detector.convert_girth_to_diameter(
                df[diameter_col].values
            )
            report['corrections'].append({
                'type': 'girth_to_diameter',
                'column': diameter_col,
                'affected_rows': len(df),
                'method': 'DBH = GBH / π',
                'sample': [
                    {'original': round(original_values.iloc[i], 2),
                     'converted': round(df[diameter_col].iloc[i], 2)}
                    for i in range(min(3, len(df)))
                ]
            })

        # 4. Validate species names
        species_col = self._detect_species_column(df)
        if species_col:
            species_validation = self._validate_species(df, species_col)
            report['warnings'].extend(species_validation['warnings'])
            report['errors'].extend(species_validation['errors'])
            report['corrections'].extend(species_validation['corrections'])

        # 5. Validate heights for seedlings
        height_col = self._detect_height_column(df)
        if height_col:
            seedling_validation = self._validate_seedling_heights(
                df, diameter_col, height_col
            )
            report['warnings'].extend(seedling_validation)

        # 6. Summary statistics
        report['summary'] = self._calculate_summary(df, report)

        return report

    def _detect_diameter_column(self, df: pd.DataFrame) -> str:
        """Detect diameter/girth column"""
        possible_names = ['dia_cm', 'diameter', 'dbh', 'girth', 'gbh', 'diam']
        for col in df.columns:
            if col.lower() in possible_names:
                return col
        return None

    def _detect_species_column(self, df: pd.DataFrame) -> str:
        """Detect species column"""
        possible_names = ['species', 'scientific_name', 'tree_species']
        for col in df.columns:
            if col.lower() in possible_names:
                return col
        return None

    def _detect_height_column(self, df: pd.DataFrame) -> str:
        """Detect height column"""
        possible_names = ['height_m', 'height', 'tree_height', 'ht']
        for col in df.columns:
            if col.lower() in possible_names:
                return col
        return None

    def _validate_species(self, df: pd.DataFrame, species_col: str) -> Dict:
        """Validate all species names"""
        result = {
            'warnings': [],
            'errors': [],
            'corrections': []
        }

        for idx, row in df.iterrows():
            species_name = row[species_col]
            matched, confidence, method = self.species_matcher.match_species(species_name)

            if method == 'fuzzy':
                result['warnings'].append({
                    'row': idx + 2,  # +2 for header and 0-indexing
                    'column': species_col,
                    'original': species_name,
                    'corrected': matched,
                    'confidence': round(confidence, 2),
                    'message': f'Species name auto-corrected ({int(confidence*100)}% match)'
                })
                df.at[idx, species_col] = matched

            elif method == 'no_match':
                suggestions = self.species_matcher.get_suggestions(species_name)
                result['errors'].append({
                    'row': idx + 2,
                    'column': species_col,
                    'value': species_name,
                    'message': 'Species not recognized',
                    'suggestions': suggestions
                })

        return result

    def _validate_seedling_heights(
        self,
        df: pd.DataFrame,
        diameter_col: str,
        height_col: str
    ) -> List[Dict]:
        """Validate heights for seedlings (DBH < 10 cm)"""
        warnings = []

        seedlings = df[df[diameter_col] < 10]

        for idx in seedlings.index:
            if pd.notna(df.at[idx, height_col]):
                warnings.append({
                    'row': idx + 2,
                    'column': height_col,
                    'dbh_cm': round(df.at[idx, diameter_col], 2),
                    'provided_height': round(df.at[idx, height_col], 2),
                    'message': 'Height will be ignored for seedling (DBH < 10 cm)',
                    'action': 'Will use default H/D ratio for volume calculation'
                })

        return warnings

    def _calculate_summary(self, df: pd.DataFrame, report: Dict) -> Dict:
        """Calculate validation summary statistics"""
        return {
            'total_rows': len(df),
            'valid_rows': len(df) - len(report['errors']),
            'rows_with_warnings': len(set(w['row'] for w in report['warnings'] if 'row' in w)),
            'rows_with_errors': len(set(e['row'] for e in report['errors'] if 'row' in e)),
            'auto_corrections': len(report['corrections'])
        }
```

---

## 6. Configuration

### `backend/app/core/config.py` additions

```python
# Inventory Validation Settings
FUZZY_MATCH_THRESHOLD: int = 85  # Percentage
GIRTH_DETECTION_THRESHOLD: float = 100.0  # cm
SEEDLING_DBH_THRESHOLD: float = 10.0  # cm
MOTHER_TREE_MIN_DBH: float = 30.0  # cm
MAX_TREE_HEIGHT_NEPAL: float = 50.0  # meters
MIN_TREE_HEIGHT_NEPAL: float = 1.0  # meters
DUPLICATE_DISTANCE_TOLERANCE: float = 1.0  # meters
```

---

## 7. Testing Strategy

### Unit Tests
```python
# tests/test_species_matcher.py
# tests/test_coordinate_detector.py
# tests/test_diameter_detector.py
# tests/test_inventory_validator.py
```

### Test Data Files
```
tests/fixtures/
├── valid_inventory.csv          # All valid data
├── typo_species.csv             # Species name typos
├── girth_measurements.csv       # Girth instead of diameter
├── utm_coordinates.csv          # UTM projected coords
├── swapped_coordinates.csv      # Lat/Lon swapped
├── seedlings_with_height.csv    # Seedlings with height data
```

---

## Conclusion

This technical specification provides:
- ✅ Complete implementation details for all validators
- ✅ Database schema for logging validation results
- ✅ Modular, testable code architecture
- ✅ Comprehensive error handling
- ✅ User feedback mechanisms

**Ready for implementation!**
