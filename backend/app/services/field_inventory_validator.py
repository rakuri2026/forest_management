"""
Field Inventory Validator
Validates CSV uploads with 4 stand types (Regeneration, Sapling, Pole, Tree)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from ..services.validators.species_code_validator import SpeciesCodeValidator

logger = logging.getLogger(__name__)


class FieldInventoryValidator:
    """
    Validator for field inventory CSV files with 4 stand types
    """

    # Required column groups by stand type
    # Allow flexible column name matching
    REQUIRED_COLUMNS = {
        'common': ['block_name', 'sample_plot_number', 'longitude', 'latitude'],
        'regeneration': ['regen_species_scientific', 'regen_dbh', 'regen_count'],
        'sapling': ['sapling_species_scientific', 'sapling_dbh', 'sapling_count'],  # Accept both sapling_dbh and sapling_dbh_cm
        'pole': ['pole_species_scientific', 'pole_dbh', 'pole_height'],  # Accept both pole_dbh_cm and pole_dbh, pole_height_m and pole_height
        'tree': ['tree_species_scientific', 'tree_dbh', 'tree_height']  # Accept both tree_dbh_cm and tree_dbh, tree_height_m and tree_height
    }

    # Column name alternatives (first match wins)
    COLUMN_ALTERNATIVES = {
        'sapling_dbh': ['sapling_dbh_cm', 'sapling_dbh'],
        'pole_dbh': ['pole_dbh_cm', 'pole_dbh'],
        'tree_dbh': ['tree_dbh_cm', 'tree_dbh'],
        'pole_height': ['pole_height_m', 'pole_height'],
        'tree_height': ['tree_height_m', 'tree_height']
    }

    # Optional columns
    OPTIONAL_COLUMNS = {
        'regeneration': ['regen_sn'],
        'sapling': ['sapling_sn'],
        'pole': ['pole_sn', 'pole_class', 
                 'pole_stem_volume_m3', 'pole_branch_volume_m3', 'pole_tree_volume_m3',
                 'pole_gross_volume_m3', 'pole_net_volume_m3', 'pole_firewood_m3'],
        'tree': ['tree_sn', 'tree_class',
                 'tree_stem_volume_m3', 'tree_branch_volume_m3', 'tree_tree_volume_m3',
                 'tree_gross_volume_m3', 'tree_net_volume_m3', 'tree_firewood_m3']
    }

    # DBH thresholds (in cm)
    DBH_THRESHOLDS = {
        'regeneration': {'min': 0, 'max': 4, 'strict': True},
        'sapling': {'min': 4, 'max': 10, 'strict': True},
        'pole': {'min': 10, 'max': 30, 'strict': False},
        'tree': {'min': 30, 'max': 200, 'strict': False}
    }

    def __init__(self, db: Session):
        """Initialize validator with database session"""
        self.db = db
        self.species_validator = SpeciesCodeValidator(db)
        self.errors = []
        self.warnings = []
        self.info = []

    async def validate_field_inventory_file(
        self,
        df: pd.DataFrame,
        calculation_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Validate field inventory CSV file

        Args:
            df: DataFrame with field inventory data
            calculation_id: Optional calculation ID for boundary validation

        Returns:
            Validation report dict
        """
        self.errors = []
        self.warnings = []
        self.info = []

        logger.info(f"[FIELD_INVENTORY_VALIDATOR] Starting validation for {len(df)} rows")

        # 1. Detect and validate columns
        column_detection = self._detect_columns(df)
        if not column_detection['valid']:
            return {
                'success': False,
                'summary': {
                    'total_rows': len(df),
                    'ready_for_processing': False,
                    'has_critical_errors': True
                },
                'data_detection': column_detection,
                'errors': self.errors,
                'warnings': self.warnings,
                'info': self.info
            }

        # 2. Validate coordinates
        coord_validation = self._validate_coordinates(df, column_detection['columns'])

        # 3. Validate duplicate sample plots
        duplicate_validation = self._validate_duplicate_plots(df, column_detection['columns'])

        # 4. Validate all 4 species columns
        species_validation = await self._validate_species_columns(df, column_detection['columns'])

        # 5. Validate DBH ranges for all 4 stand types
        dbh_validation = self._validate_dbh_ranges(df, column_detection['columns'])

        # 6. Validate counts for regeneration and sapling
        count_validation = self._validate_counts(df, column_detection['columns'])

        # 7. Boundary validation (if calculation_id provided)
        boundary_check = None
        if calculation_id:
            boundary_check = await self._validate_boundary(df, column_detection['columns'], calculation_id)

        # Compile summary
        has_critical_errors = len([e for e in self.errors if e['severity'] == 'error']) > 0
        ready_for_processing = not has_critical_errors

        # If boundary check failed, mark as not ready
        if boundary_check and not boundary_check.get('within_tolerance', True):
            ready_for_processing = False
            has_critical_errors = True

        report = {
            'success': ready_for_processing,
            'summary': {
                'total_rows': len(df),
                'ready_for_processing': ready_for_processing,
                'has_critical_errors': has_critical_errors,
                'error_count': len([e for e in self.errors if e['severity'] == 'error']),
                'warning_count': len([w for w in self.warnings if w['severity'] == 'warning']),
                'info_count': len(self.info)
            },
            'data_detection': column_detection,
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }

        if boundary_check:
            report['boundary_check'] = boundary_check

        logger.info(f"[FIELD_INVENTORY_VALIDATOR] Validation complete: ready={ready_for_processing}, errors={len(self.errors)}, warnings={len(self.warnings)}")

        return report

    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect and validate column structure"""
        logger.info(f"[COLUMN_DETECTION] Detecting columns from: {list(df.columns)}")

        detected_columns = {}
        missing_required = []

        # Normalize column names (lowercase)
        df_columns_lower = [col.lower().strip() for col in df.columns]
        column_map = {col.lower().strip(): col for col in df.columns}

        # Detect common columns
        for req_col in self.REQUIRED_COLUMNS['common']:
            found = None
            req_lower = req_col.lower()

            # Exact match
            if req_lower in df_columns_lower:
                found = column_map[req_lower]

            if found:
                detected_columns[req_col] = found
            else:
                missing_required.append(req_col)
                self.errors.append({
                    'severity': 'error',
                    'type': 'missing_column',
                    'message': f"Required column '{req_col}' not found"
                })

        # Detect stand type columns (regeneration, sapling, pole, tree)
        for stand_type, req_cols in self.REQUIRED_COLUMNS.items():
            if stand_type == 'common':
                continue

            for req_col in req_cols:
                found = None
                req_lower = req_col.lower()

                # Try exact match first
                if req_lower in df_columns_lower:
                    found = column_map[req_lower]

                # If not found, try alternatives
                if not found and req_col in self.COLUMN_ALTERNATIVES:
                    for alt in self.COLUMN_ALTERNATIVES[req_col]:
                        alt_lower = alt.lower()
                        if alt_lower in df_columns_lower:
                            found = column_map[alt_lower]
                            logger.info(f"[COLUMN_DETECTION] Using alternative '{alt}' for '{req_col}'")
                            break

                if found:
                    detected_columns[req_col] = found
                else:
                    # For stand-specific columns, it's OK if missing (not all plots have all stand types)
                    self.warnings.append({
                        'severity': 'warning',
                        'type': 'missing_optional_column',
                        'message': f"Optional column '{req_col}' not found (stand type: {stand_type})"
                    })

        # Check if we have at least one stand type
        has_regen = 'regen_species_scientific' in detected_columns
        has_sapling = 'sapling_species_scientific' in detected_columns
        has_pole = 'pole_species_scientific' in detected_columns
        has_tree = 'tree_species_scientific' in detected_columns

        if not (has_regen or has_sapling or has_pole or has_tree):
            self.errors.append({
                'severity': 'error',
                'type': 'no_stand_types',
                'message': 'No stand type columns found. File must have at least one of: regen, sapling, pole, or tree measurements.'
            })
            return {
                'valid': False,
                'columns': detected_columns,
                'missing_required': missing_required,
                'stand_types_present': []
            }

        stand_types_present = []
        if has_regen:
            stand_types_present.append('regeneration')
        if has_sapling:
            stand_types_present.append('sapling')
        if has_pole:
            stand_types_present.append('pole')
        if has_tree:
            stand_types_present.append('tree')

        logger.info(f"[COLUMN_DETECTION] Stand types present: {stand_types_present}")

        return {
            'valid': len(missing_required) == 0,
            'columns': detected_columns,
            'missing_required': missing_required,
            'stand_types_present': stand_types_present
        }

    def _validate_coordinates(self, df: pd.DataFrame, columns: Dict[str, str]) -> Dict[str, Any]:
        """Validate longitude and latitude"""
        logger.info("[COORDINATE_VALIDATION] Validating coordinates...")

        lon_col = columns.get('longitude')
        lat_col = columns.get('latitude')

        if not lon_col or not lat_col:
            return {'valid': False}

        # Check for missing values
        missing_lon = df[lon_col].isna().sum()
        missing_lat = df[lat_col].isna().sum()

        if missing_lon > 0 or missing_lat > 0:
            self.errors.append({
                'severity': 'error',
                'type': 'missing_coordinates',
                'message': f"Missing coordinates: {missing_lon} longitude, {missing_lat} latitude"
            })

        # Check valid ranges (Nepal bounds: ~80-88°E, ~26-31°N)
        valid_lon = df[lon_col].between(80, 88)
        valid_lat = df[lat_col].between(26, 31)

        invalid_lon = (~valid_lon).sum()
        invalid_lat = (~valid_lat).sum()

        if invalid_lon > 0:
            self.warnings.append({
                'severity': 'warning',
                'type': 'invalid_longitude',
                'message': f"{invalid_lon} rows have longitude outside Nepal bounds (80-88°E)"
            })

        if invalid_lat > 0:
            self.warnings.append({
                'severity': 'warning',
                'type': 'invalid_latitude',
                'message': f"{invalid_lat} rows have latitude outside Nepal bounds (26-31°N)"
            })

        return {'valid': True}

    def _validate_duplicate_plots(self, df: pd.DataFrame, columns: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate sample plot coordinates consistency

        NOTE: Multiple rows with same (block_name, sample_plot_number) is EXPECTED
        because one sample plot can have multiple trees/measurements.

        We only check if the same plot has INCONSISTENT coordinates (error).
        """
        logger.info("[DUPLICATE_VALIDATION] Checking for coordinate consistency per plot...")

        block_col = columns.get('block_name')
        plot_col = columns.get('sample_plot_number')
        lat_col = columns.get('latitude')
        lon_col = columns.get('longitude')

        if not block_col or not plot_col or not lat_col or not lon_col:
            return {'valid': True}  # Skip validation if columns missing

        # Group by (block_name, sample_plot_number) and check coordinate consistency
        inconsistent_plots = []

        for (block, plot), group in df.groupby([block_col, plot_col]):
            # Get unique coordinates for this plot (ignoring NaN)
            unique_coords = group[[lat_col, lon_col]].dropna().drop_duplicates()

            # If a plot has more than one unique coordinate pair, that's an error
            if len(unique_coords) > 1:
                inconsistent_plots.append({
                    'block_name': block,
                    'sample_plot_number': plot,
                    'coordinate_count': len(unique_coords),
                    'coordinates': unique_coords.to_dict('records')
                })

        if inconsistent_plots:
            # This is common when GPS is recorded per tree instead of per plot
            # Change to WARNING instead of ERROR - we'll use first coordinate or centroid
            self.warnings.append({
                'severity': 'warning',
                'type': 'inconsistent_coordinates',
                'message': f"Found {len(inconsistent_plots)} plots with varying GPS coordinates (will use first coordinate for plot center)",
                'details': inconsistent_plots[:5] if len(inconsistent_plots) > 5 else inconsistent_plots  # Limit details to first 5
            })
            logger.warning(f"[DUPLICATE_VALIDATION] {len(inconsistent_plots)} plots have varying coordinates (common when GPS recorded per tree)")

        # Count unique sample plots
        unique_plots = df[[block_col, plot_col]].drop_duplicates()
        total_measurements = len(df)
        unique_plot_count = len(unique_plots)

        logger.info(f"[DUPLICATE_VALIDATION] Found {unique_plot_count} unique sample plots with {total_measurements} total measurements")

        # Add info message about multiple measurements per plot (this is normal and expected)
        if total_measurements > unique_plot_count:
            self.info.append({
                'type': 'multiple_measurements',
                'message': f"Dataset has {total_measurements} measurements from {unique_plot_count} sample plots (multiple measurements per plot is normal)"
            })

        return {'valid': True, 'unique_plot_count': unique_plot_count, 'total_measurements': total_measurements}

    async def _validate_species_columns(self, df: pd.DataFrame, columns: Dict[str, str]) -> Dict[str, Any]:
        """Validate all 4 species columns"""
        logger.info("[SPECIES_VALIDATION] Validating species columns...")

        species_columns = {
            'regeneration': columns.get('regen_species_scientific'),
            'sapling': columns.get('sapling_species_scientific'),
            'pole': columns.get('pole_species_scientific'),
            'tree': columns.get('tree_species_scientific')
        }

        validation_results = {}

        for stand_type, col_name in species_columns.items():
            if not col_name or col_name not in df.columns:
                continue

            logger.info(f"[SPECIES_VALIDATION] Validating {stand_type} species column: {col_name}")

            # Get unique species values (excluding NaN)
            unique_species = df[col_name].dropna().unique()

            invalid_species = []
            for species_value in unique_species:
                if pd.isna(species_value) or str(species_value).strip() == '':
                    continue

                # Validate species
                scientific_name, species_code, method, confidence, warning = \
                    self.species_validator.validate_species_value(species_value, None)

                if warning:
                    invalid_species.append({
                        'original': species_value,
                        'resolved': scientific_name,
                        'method': method,
                        'confidence': confidence,
                        'warning': warning
                    })

            if invalid_species:
                self.warnings.append({
                    'severity': 'warning',
                    'type': f'{stand_type}_species_validation',
                    'message': f"{len(invalid_species)} species in {stand_type} may need review",
                    'details': invalid_species
                })

            validation_results[stand_type] = {
                'total_unique': len(unique_species),
                'invalid_count': len(invalid_species)
            }

        logger.info(f"[SPECIES_VALIDATION] Complete: {validation_results}")
        return validation_results

    def _validate_dbh_ranges(self, df: pd.DataFrame, columns: Dict[str, str]) -> Dict[str, Any]:
        """Validate DBH ranges for all 4 stand types"""
        logger.info("[DBH_VALIDATION] Validating DBH ranges...")

        dbh_columns = {
            'regeneration': columns.get('regen_dbh'),
            'sapling': columns.get('sapling_dbh_cm'),
            'pole': columns.get('pole_dbh_cm'),
            'tree': columns.get('tree_dbh_cm')
        }

        validation_results = {}

        for stand_type, col_name in dbh_columns.items():
            if not col_name or col_name not in df.columns:
                continue

            thresholds = self.DBH_THRESHOLDS[stand_type]
            min_dbh = thresholds['min']
            max_dbh = thresholds['max']
            strict = thresholds['strict']

            # Get non-null values
            dbh_values = df[col_name].dropna()

            if len(dbh_values) == 0:
                continue

            # Check range
            out_of_range = (dbh_values < min_dbh) | (dbh_values > max_dbh)
            out_of_range_count = out_of_range.sum()

            if out_of_range_count > 0:
                severity = 'error' if strict else 'warning'
                issue_type = 'dbh_out_of_range'

                message = f"{stand_type.capitalize()}: {out_of_range_count} DBH values outside expected range ({min_dbh}-{max_dbh} cm)"

                if strict:
                    self.errors.append({
                        'severity': severity,
                        'type': issue_type,
                        'stand_type': stand_type,
                        'message': message,
                        'expected_range': f"{min_dbh}-{max_dbh} cm"
                    })
                else:
                    self.warnings.append({
                        'severity': severity,
                        'type': issue_type,
                        'stand_type': stand_type,
                        'message': message,
                        'expected_range': f"{min_dbh}-{max_dbh} cm"
                    })

            validation_results[stand_type] = {
                'total': len(dbh_values),
                'out_of_range': int(out_of_range_count),
                'expected_range': f"{min_dbh}-{max_dbh} cm",
                'strict': strict
            }

        logger.info(f"[DBH_VALIDATION] Complete: {validation_results}")
        return validation_results

    def _validate_counts(self, df: pd.DataFrame, columns: Dict[str, str]) -> Dict[str, Any]:
        """Validate count columns for regeneration and sapling"""
        logger.info("[COUNT_VALIDATION] Validating count columns...")

        count_columns = {
            'regeneration': columns.get('regen_count'),
            'sapling': columns.get('sapling_count')
        }

        validation_results = {}

        for stand_type, col_name in count_columns.items():
            if not col_name or col_name not in df.columns:
                continue

            # Check for invalid counts (<= 0)
            counts = df[col_name].dropna()
            invalid_counts = (counts <= 0).sum()

            if invalid_counts > 0:
                self.errors.append({
                    'severity': 'error',
                    'type': 'invalid_count',
                    'stand_type': stand_type,
                    'message': f"{stand_type.capitalize()}: {invalid_counts} rows have count <= 0"
                })

            validation_results[stand_type] = {
                'total': len(counts),
                'invalid': int(invalid_counts)
            }

        logger.info(f"[COUNT_VALIDATION] Complete: {validation_results}")
        return validation_results

    async def _validate_boundary(
        self,
        df: pd.DataFrame,
        columns: Dict[str, str],
        calculation_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Validate sample plots against boundary"""
        logger.info(f"[BOUNDARY_VALIDATION] Checking boundary for calculation {calculation_id}")

        try:
            from ..services.boundary_validator import validate_inventory_boundary
            from shapely.geometry import Point

            lon_col = columns.get('longitude')
            lat_col = columns.get('latitude')

            if not lon_col or not lat_col:
                return None

            # Extract unique sample plot points
            plot_points = []
            for idx, row in df.iterrows():
                if pd.notna(row[lon_col]) and pd.notna(row[lat_col]):
                    plot_points.append((
                        float(row[lon_col]),
                        float(row[lat_col]),
                        idx + 1
                    ))

            # Validate boundary (20% tolerance)
            boundary_result = validate_inventory_boundary(
                self.db,
                calculation_id,
                plot_points,
                tolerance_percent=20.0
            )

            logger.info(f"[BOUNDARY_VALIDATION] Result: {boundary_result['out_of_boundary_percentage']}% outside")

            # If >20% outside, add error
            if not boundary_result['within_tolerance']:
                self.errors.append({
                    'severity': 'error',
                    'type': 'boundary_error',
                    'message': boundary_result.get('error_message', 'Too many sample plots outside boundary')
                })
            elif boundary_result['needs_correction']:
                self.warnings.append({
                    'severity': 'warning',
                    'type': 'boundary_warning',
                    'message': f"{boundary_result['out_of_boundary_count']} sample plots are outside boundary (within 20% tolerance)"
                })

            return boundary_result

        except Exception as e:
            logger.error(f"[BOUNDARY_VALIDATION] Error: {str(e)}")
            self.warnings.append({
                'severity': 'warning',
                'type': 'boundary_check_error',
                'message': f"Could not validate boundary: {str(e)}"
            })
            return None
