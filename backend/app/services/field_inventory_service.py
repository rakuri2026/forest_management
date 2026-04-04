"""
Field Inventory Service
Processes field inventory data with 4 stand types and calculates forest condition
"""
import os
import pandas as pd
import numpy as np
import math
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from datetime import datetime
import logging
import time

from ..models.field_inventory import (
    FieldInventoryCalculation,
    FieldInventorySamplePlot,
    FieldInventoryMeasurement,
    FieldInventoryBlockSummary
)
from ..models.inventory import TreeSpeciesCoefficient
from ..utils.diameter_classifier import DiameterClassifier

logger = logging.getLogger(__name__)

# Debug logging for volume calculation comparison
DEBUG_VOLUME_CALC = os.environ.get('DEBUG_VOLUME_CALC', 'false').lower() == 'true'

def _debug_log(msg: str):
    """Print debug message if DEBUG_VOLUME_CALC is enabled"""
    if DEBUG_VOLUME_CALC:
        print(f"[FIELD_INV_VOLUME] {msg}")


class FieldInventoryService:
    """
    Service for processing field inventory data
    """

    def __init__(self, db: Session):
        """Initialize service with database session"""
        self.db = db
        self.species_coefficients = self._load_species_coefficients()

    def _load_species_coefficients(self) -> Dict[str, Dict]:
        """Load species coefficients from database (including wood density for carbon calculations)"""
        query = text("""
            SELECT scientific_name, local_name, a, b, c, a1, b1, s, m, bg, growth_rate, wood_density_gm_cm3
            FROM public.tree_species_coefficients
            WHERE is_active = TRUE
        """)
        result = self.db.execute(query).fetchall()

        coefficients = {}
        for row in result:
            coefficients[row[0]] = {
                'local_name': row[1],
                'a': row[2],
                'b': row[3],
                'c': row[4],
                'a1': row[5],
                'b1': row[6],
                's': row[7],
                'm': row[8],
                'bg': row[9],
                'growth_rate': row[10],
                'wood_density': float(row[11]) if row[11] is not None else 0.65  # Default to 0.65 if missing
            }

        return coefficients

    async def process_field_inventory(
        self,
        field_inventory_id: UUID,
        df: pd.DataFrame,
        column_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Process complete field inventory

        Args:
            field_inventory_id: UUID of field inventory calculation
            df: DataFrame with field inventory data
            column_mapping: Column mapping dict

        Returns:
            Processing summary dict
        """
        start_time = time.time()

        # Get field inventory calculation record
        field_inventory = self.db.query(FieldInventoryCalculation).filter(
            FieldInventoryCalculation.id == field_inventory_id
        ).first()

        if not field_inventory:
            raise ValueError(f"Field inventory {field_inventory_id} not found")

        try:
            # Update status
            field_inventory.status = 'processing'
            self.db.commit()
            logger.info(f"[FIELD_INVENTORY] Processing {field_inventory_id} with {len(df)} rows")

            # 1. Parse CSV and create sample plots
            sample_plots = await self._create_sample_plots(field_inventory_id, df, column_mapping)
            logger.info(f"[FIELD_INVENTORY] Created {len(sample_plots)} sample plots")

            # 2. Create measurements for all stand types
            measurements_count = await self._create_measurements(sample_plots, df, column_mapping)
            logger.info(f"[FIELD_INVENTORY] Created {measurements_count} measurements")

            # 3. Calculate volumes for pole and tree
            await self._calculate_volumes(field_inventory_id)
            logger.info(f"[FIELD_INVENTORY] Volumes calculated")

            # 4. Calculate per-hectare extrapolation by block
            block_summaries = await self._calculate_per_hectare(field_inventory_id, field_inventory)
            logger.info(f"[FIELD_INVENTORY] Per-hectare calculated for {len(block_summaries)} blocks")

            # 5. Assess forest condition for each block
            await self._assess_forest_condition(block_summaries)
            logger.info(f"[FIELD_INVENTORY] Forest condition assessed")

            # 6. Calculate MAI for each block
            await self._calculate_mai(block_summaries, field_inventory_id)
            logger.info(f"[FIELD_INVENTORY] MAI calculated")

            # 7. Update summary statistics
            field_inventory.total_sample_plots = len(sample_plots)
            field_inventory.total_blocks = len(block_summaries)
            field_inventory.status = 'completed'
            field_inventory.completed_at = datetime.utcnow()
            field_inventory.processing_time_seconds = int(time.time() - start_time)
            self.db.commit()

            logger.info(f"[FIELD_INVENTORY] Processing complete in {field_inventory.processing_time_seconds}s")

            return {
                'success': True,
                'field_inventory_id': str(field_inventory_id),
                'total_sample_plots': len(sample_plots),
                'total_blocks': len(block_summaries),
                'measurements_count': measurements_count,
                'processing_time_seconds': field_inventory.processing_time_seconds
            }

        except Exception as e:
            # Update status to failed
            field_inventory.status = 'failed'
            field_inventory.error_message = str(e)
            self.db.commit()
            logger.error(f"[FIELD_INVENTORY] Processing failed: {str(e)}")
            raise

    async def _create_sample_plots(
        self,
        field_inventory_id: UUID,
        df: pd.DataFrame,
        column_mapping: Dict[str, str]
    ) -> List[FieldInventorySamplePlot]:
        """Create sample plot records"""
        sample_plots_dict = {}

        block_col = column_mapping.get('block_name')
        plot_col = column_mapping.get('sample_plot_number')
        lon_col = column_mapping.get('longitude')
        lat_col = column_mapping.get('latitude')

        # NTFP column mappings (optional)
        firewood_col = column_mapping.get('firewood_kg_per_100sqm_per_year')
        grass_col = column_mapping.get('grass_kg_per_100sqm_per_year')
        bedding_col = column_mapping.get('bedding_material_kg_per_100sqm_per_year')
        ntfp_col = column_mapping.get('ntfp_kg_per_100sqm_per_year')

        for idx, row in df.iterrows():
            try:
                block_name = str(row[block_col])
                plot_number = int(float(row[plot_col]))  # Convert to float first in case it's "1.0"
                lon = float(row[lon_col])
                lat = float(row[lat_col])
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"[SAMPLE_PLOTS] Skipping row {idx}: Invalid data - {str(e)}")
                continue

            # Create unique key
            key = (block_name, plot_number)

            # Create sample plot only once per unique (block, plot) combination
            # If multiple rows have different coordinates for same plot (common when GPS recorded per tree),
            # we use the FIRST coordinate encountered as the plot center
            if key not in sample_plots_dict:
                # Extract NTFP values (optional, default to None)
                firewood = None
                grass = None
                bedding = None
                ntfp = None

                try:
                    if firewood_col and firewood_col in df.columns:
                        val = row[firewood_col]
                        if pd.notna(val) and val != '':
                            firewood = float(val)
                except (ValueError, TypeError):
                    pass

                try:
                    if grass_col and grass_col in df.columns:
                        val = row[grass_col]
                        if pd.notna(val) and val != '':
                            grass = float(val)
                except (ValueError, TypeError):
                    pass

                try:
                    if bedding_col and bedding_col in df.columns:
                        val = row[bedding_col]
                        if pd.notna(val) and val != '':
                            bedding = float(val)
                except (ValueError, TypeError):
                    pass

                try:
                    if ntfp_col and ntfp_col in df.columns:
                        val = row[ntfp_col]
                        if pd.notna(val) and val != '':
                            ntfp = float(val)
                except (ValueError, TypeError):
                    pass

                sample_plot = FieldInventorySamplePlot(
                    field_inventory_calculation_id=field_inventory_id,
                    block_name=block_name,
                    sample_plot_number=plot_number,
                    location=f'SRID=4326;POINT({lon} {lat})',
                    firewood_kg_per_100sqm_per_year=firewood,
                    grass_kg_per_100sqm_per_year=grass,
                    bedding_material_kg_per_100sqm_per_year=bedding,
                    ntfp_kg_per_100sqm_per_year=ntfp
                )
                self.db.add(sample_plot)
                sample_plots_dict[key] = sample_plot

        self.db.flush()
        return list(sample_plots_dict.values())

    async def _create_measurements(
        self,
        sample_plots: List[FieldInventorySamplePlot],
        df: pd.DataFrame,
        column_mapping: Dict[str, str]
    ) -> int:
        """Create measurement records for all stand types"""
        measurements_count = 0

        # Create lookup dict for sample plots
        plot_lookup = {}
        for plot in sample_plots:
            key = (plot.block_name, plot.sample_plot_number)
            plot_lookup[key] = plot

        # Get column names
        block_col = column_mapping.get('block_name')
        plot_col = column_mapping.get('sample_plot_number')

        # Process each row
        for idx, row in df.iterrows():
            block_name = str(row[block_col])
            plot_number = int(row[plot_col])
            key = (block_name, plot_number)

            sample_plot = plot_lookup.get(key)
            if not sample_plot:
                continue

            # Create measurements for each stand type present
            # 1. Regeneration
            if self._has_stand_type_data(row, 'regeneration', column_mapping):
                measurement = self._create_stand_measurement(
                    row, 'Regeneration', sample_plot.id, column_mapping
                )
                if measurement:
                    self.db.add(measurement)
                    measurements_count += 1

            # 2. Sapling
            if self._has_stand_type_data(row, 'sapling', column_mapping):
                measurement = self._create_stand_measurement(
                    row, 'Sapling', sample_plot.id, column_mapping
                )
                if measurement:
                    self.db.add(measurement)
                    measurements_count += 1

            # 3. Pole
            if self._has_stand_type_data(row, 'pole', column_mapping):
                measurement = self._create_stand_measurement(
                    row, 'Pole', sample_plot.id, column_mapping
                )
                if measurement:
                    self.db.add(measurement)
                    measurements_count += 1

            # 4. Tree
            if self._has_stand_type_data(row, 'tree', column_mapping):
                measurement = self._create_stand_measurement(
                    row, 'Tree', sample_plot.id, column_mapping
                )
                if measurement:
                    self.db.add(measurement)
                    measurements_count += 1

        self.db.flush()
        return measurements_count

    def _has_stand_type_data(self, row: pd.Series, stand_type: str, column_mapping: Dict[str, str]) -> bool:
        """Check if row has data for this stand type"""
        # Map stand type to column prefix
        if stand_type == 'regeneration':
            prefix = 'regen'
        elif stand_type == 'sapling':
            prefix = 'sapling'
        elif stand_type == 'pole':
            prefix = 'pole'
        elif stand_type == 'tree':
            prefix = 'tree'
        else:
            prefix = stand_type.lower()

        species_col = column_mapping.get(f'{prefix}_species_scientific')

        if not species_col or species_col not in row.index:
            return False

        # Check if species is present and not null
        species_value = row[species_col]
        return pd.notna(species_value) and str(species_value).strip() != ''

    def _create_stand_measurement(
        self,
        row: pd.Series,
        stand_type: str,
        sample_plot_id: UUID,
        column_mapping: Dict[str, str]
    ) -> Optional[FieldInventoryMeasurement]:
        """Create a measurement record for a specific stand type"""
        # Determine column prefix
        if stand_type == 'Regeneration':
            prefix = 'regen'
        elif stand_type == 'Sapling':
            prefix = 'sapling'
        elif stand_type == 'Pole':
            prefix = 'pole'
        elif stand_type == 'Tree':
            prefix = 'tree'
        else:
            return None

        # Get column names
        species_col = column_mapping.get(f'{prefix}_species_scientific')
        dbh_col = column_mapping.get(f'{prefix}_dbh_cm') or column_mapping.get(f'{prefix}_dbh')
        height_col = column_mapping.get(f'{prefix}_height_m')
        class_col = column_mapping.get(f'{prefix}_class')
        count_col = column_mapping.get(f'{prefix}_count')
        sn_col = column_mapping.get(f'{prefix}_sn')
        
        # Volume columns (if present in uploaded file - e.g., from Tree Model export)
        stem_vol_col = column_mapping.get(f'{prefix}_stem_volume_m3')
        branch_vol_col = column_mapping.get(f'{prefix}_branch_volume_m3')
        tree_vol_col = column_mapping.get(f'{prefix}_tree_volume_m3')
        gross_vol_col = column_mapping.get(f'{prefix}_gross_volume_m3')
        net_vol_col = column_mapping.get(f'{prefix}_net_volume_m3')
        firewood_vol_col = column_mapping.get(f'{prefix}_firewood_m3')

        if not species_col:
            return None

        # Get species
        species = str(row[species_col]).strip()
        if not species or species == '' or pd.isna(row[species_col]):
            return None

        # Get local name from species coefficients
        species_local = self.species_coefficients.get(species, {}).get('local_name')

        # Get DBH
        dbh_cm = None
        if dbh_col and dbh_col in row.index:
            dbh_value = row[dbh_col]
            if pd.notna(dbh_value):
                try:
                    dbh_cm = float(dbh_value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"[MEASUREMENT] Cannot convert DBH to float: '{dbh_value}' (column: {dbh_col})")
                    return None  # Skip this measurement if DBH is invalid

        # Get height
        height_m = None
        height_estimated = False
        if height_col and height_col in row.index:
            height_value = row[height_col]
            if pd.notna(height_value):
                try:
                    height_m = float(height_value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"[MEASUREMENT] Cannot convert height to float: '{height_value}' (column: {height_col}), will estimate if possible")
                    # Don't return None yet - height can be estimated for pole/tree
            elif dbh_cm and stand_type in ['Pole', 'Tree']:
                # Estimate height for pole/tree if missing
                height_m = dbh_cm * 0.8
                height_estimated = True

            # If height still not available but we have DBH, estimate it
            if not height_m and dbh_cm and stand_type in ['Pole', 'Tree']:
                height_m = dbh_cm * 0.8
                height_estimated = True

        # Get class
        tree_class = None
        if class_col and class_col in row.index:
            class_value = row[class_col]
            if pd.notna(class_value) and str(class_value).strip() != '':
                tree_class = str(class_value).strip()

        # Get count (for regeneration and sapling)
        count = 1
        if count_col and count_col in row.index:
            count_value = row[count_col]
            if pd.notna(count_value):
                try:
                    count = int(float(count_value))  # Convert to float first to handle "1.0"
                except (ValueError, TypeError) as e:
                    logger.warning(f"[MEASUREMENT] Cannot convert count to int: '{count_value}' (column: {count_col}), using default 1")
                    count = 1

        # Get SN
        sn = None
        if sn_col and sn_col in row.index:
            sn_value = row[sn_col]
            if pd.notna(sn_value):
                try:
                    sn = int(float(sn_value))
                except (ValueError, TypeError) as e:
                    logger.warning(f"[MEASUREMENT] Cannot convert SN to int: '{sn_value}' (column: {sn_col}), skipping")

        # Get pre-calculated volumes (if present in uploaded file - e.g., from Tree Model export)
        # These will be used directly instead of recalculating
        precalc_volumes = {}
        if stand_type in ['Pole', 'Tree']:
            volume_cols = [
                ('stem_volume', stem_vol_col),
                ('branch_volume', branch_vol_col),
                ('tree_volume', tree_vol_col),
                ('gross_volume', gross_vol_col),
                ('net_volume', net_vol_col),
                ('firewood_m3', firewood_vol_col),
            ]
            for vol_key, vol_col in volume_cols:
                if vol_col and vol_col in row.index:
                    vol_value = row[vol_col]
                    if pd.notna(vol_value):
                        try:
                            precalc_volumes[vol_key] = float(vol_value)
                        except (ValueError, TypeError):
                            pass

        # Classify DBH
        dbh_class = None
        if dbh_cm:
            dbh_class = DiameterClassifier.classify_detailed(dbh_cm)

        measurement = FieldInventoryMeasurement(
            sample_plot_id=sample_plot_id,
            stand_type=stand_type,
            sn=sn,
            species_scientific=species,
            species_local=species_local,
            dbh_cm=dbh_cm,
            height_m=height_m,
            height_estimated=height_estimated,
            tree_class=tree_class,
            count=count,
            dbh_class=dbh_class,
            # Use pre-calculated volumes if available
            stem_volume=precalc_volumes.get('stem_volume'),
            branch_volume=precalc_volumes.get('branch_volume'),
            tree_volume=precalc_volumes.get('tree_volume'),
            gross_volume=precalc_volumes.get('gross_volume'),
            net_volume=precalc_volumes.get('net_volume'),
            firewood_m3=precalc_volumes.get('firewood_m3'),
        )

        return measurement

    async def _calculate_volumes(self, field_inventory_id: UUID):
        """Calculate volumes for pole and tree measurements"""
        logger.info("[VOLUME_CALCULATION] Starting volume calculations for pole and tree...")

        # Get all pole and tree measurements
        measurements = self.db.query(FieldInventoryMeasurement).join(
            FieldInventorySamplePlot
        ).filter(
            FieldInventorySamplePlot.field_inventory_calculation_id == field_inventory_id,
            FieldInventoryMeasurement.stand_type.in_(['Pole', 'Tree'])
        ).all()

        logger.info(f"[VOLUME_CALCULATION] Calculating volumes for {len(measurements)} pole/tree measurements")

        for measurement in measurements:
            # Skip if no DBH
            if not measurement.dbh_cm or measurement.dbh_cm < 10:
                continue

            # Skip if volumes already exist (pre-calculated from Tree Model export)
            # Use pre-calculated volumes if they were provided during import
            if measurement.net_volume is not None and measurement.net_volume > 0:
                logger.info(f"[VOLUME_CALCULATION] Using pre-calculated volumes for {measurement.species_scientific} (DBH: {measurement.dbh_cm})")
                continue

            # Get species coefficients
            species = measurement.species_scientific
            if species not in self.species_coefficients:
                logger.warning(f"[VOLUME_CALCULATION] Species not found: {species}")
                continue

            coef = self.species_coefficients[species]

            # Get or estimate height
            height_m = measurement.height_m
            height_estimated = False
            if not height_m:
                height_m = measurement.dbh_cm * 0.8
                height_estimated = True

            # Calculate volumes (Forest Regulation 2079 compliant)
            dbh_cm = float(measurement.dbh_cm)

            # Debug logging
            _debug_log(f"INPUT: dbh={dbh_cm}, height={height_m}, height_estimated={height_estimated}, class={measurement.tree_class}")
            _debug_log(f"SPECIES: {species}")
            _debug_log(f"COEFFS: a={coef.get('a')}, b={coef.get('b')}, c={coef.get('c')}, a1={coef.get('a1')}, b1={coef.get('b1')}, s={coef.get('s')}, m={coef.get('m')}, bg={coef.get('bg')}")

            # 1. Stem volume (काण्डको आयतन)
            # Formula: V = exp(a + b*ln(DBH) + c*ln(H)) / 1000
            # Source: Forest Regulation 2079, Table 1
            if coef['a'] is not None and coef['b'] is not None and coef['c'] is not None:
                log_dbh = math.log(dbh_cm)
                log_height = math.log(height_m)
                exp_value = coef['a'] + coef['b'] * log_dbh + coef['c'] * log_height
                stem_volume = math.exp(exp_value) / 1000.0
                
                if DEBUG_VOLUME_CALC:
                    _debug_log(f"[FIELD_INV_VOLUME] STEM: log(dbh)={log_dbh}, log(height)={log_height}, exp={exp_value}, stem_vol={stem_volume}")
            else:
                stem_volume = 0.0
                if DEBUG_VOLUME_CALC:
                    _debug_log(f"[FIELD_INV_VOLUME] STEM: Using default 0.0 (missing coefficients)")

            # 2. Branch volume (हाँगाको आयतन)
            # Formula: Branch Volume = Stem Volume × Branch Ratio
            # Source: Forest Regulation 2079, Table 2
            # Based on Sharma and Pukala, 1990
            # s = small (sano), m = medium (machilo), bg = big (bara)
            s = coef.get('s')
            m = coef.get('m')
            bg = coef.get('bg')
            
            if s is not None and m is not None and bg is not None:
                # Use interpolation formula based on DBH class
                if dbh_cm < 10:
                    branch_ratio = float(s)
                elif dbh_cm <= 40:
                    branch_ratio = ((dbh_cm - 10) * float(m) + (40 - dbh_cm) * float(s)) / 30.0
                elif dbh_cm <= 70:
                    branch_ratio = ((dbh_cm - 40) * float(bg) + (70 - dbh_cm) * float(m)) / 30.0
                else:
                    branch_ratio = float(bg)
                branch_volume = stem_volume * branch_ratio
            elif s is not None and m is not None:
                branch_ratio = (float(s) + float(m)) / 2.0
                branch_volume = stem_volume * branch_ratio
            elif coef.get('b') is not None:
                branch_ratio = abs(float(coef['b'])) * 0.1
                branch_volume = stem_volume * branch_ratio
            else:
                branch_ratio = 0.2
                branch_volume = stem_volume * 0.2

            _debug_log(f"[FIELD_INV_VOLUME] BRANCH: s={s}, m={m}, bg={bg}, ratio={branch_ratio}, branch_vol={branch_volume}")

            # 3. Total tree volume (रुखको आयतन)
            # Formula: Tree Volume = Stem Volume + Branch Volume
            # Source: Forest Regulation 2079, Section 3(ii)
            tree_volume = stem_volume + branch_volume

            # 4. Gross timber volume (काठको मूल आयतन)
            # Formula: Gross Timber = Stem Volume - 10cm Top Stem Volume
            # Source: Forest Regulation 2079, Section 4
            # NOTE: Gross timber comes ONLY from stem, branches go to firewood
            if coef['a1'] is not None and coef['b1'] is not None:
                cm10_dia_ratio = math.exp(coef['a1'] + coef['b1'] * math.log(dbh_cm))
                cm10_top_volume = stem_volume * cm10_dia_ratio  # Use stem_volume (not tree_volume)
                gross_volume = stem_volume - cm10_top_volume   # Use stem_volume (not tree_volume)
                
                if DEBUG_VOLUME_CALC:
                    _debug_log(f"[FIELD_INV_VOLUME] GROSS: a1={coef['a1']}, b1={coef['b1']}, cm10_ratio={cm10_dia_ratio}, cm10_vol={cm10_top_volume}, gross_vol={gross_volume}")
            else:
                gross_volume = stem_volume * 0.85
                if DEBUG_VOLUME_CALC:
                    _debug_log(f"[FIELD_INV_VOLUME] GROSS: Using fallback 0.85, gross_vol={gross_volume}")

            # 5. Net timber volume (काठको नेट आयतन)
            # Apply waste factors based on tree class (दर्जा)
            # Source: Forest Regulation 2079, Section 5
            # Handle multiple class formats: 1,2,3,4 or i,ii,iii,iv or A,B,C,D or a,b,c,d
            # Also handle float format from Excel: "1.0", "2.0", etc.

            # Convert class value to string, handling float format from Excel CSV
            tree_class_raw = measurement.tree_class or '2'
            try:
                # Try to convert to float then int to handle "1.0" → 1
                tree_class = str(int(float(tree_class_raw)))
            except (ValueError, TypeError):
                # If conversion fails, use as string (for 'i', 'ii', 'a', 'b', etc.)
                tree_class = str(tree_class_raw).strip().lower()

            # Normalize class values
            class_mapping = {
                '1': 1, 'i': 1, 'a': 1,
                '2': 2, 'ii': 2, 'b': 2,
                '3': 3, 'iii': 3, 'c': 3,
                '4': 4, 'iv': 4, 'd': 4,
            }
            normalized_class = class_mapping.get(tree_class, 2)
            
            if normalized_class == 1:
                net_volume = gross_volume * 0.80  # Class 1: 20% waste
                waste_factor = 0.80
            elif normalized_class == 2:
                net_volume = gross_volume * 0.60  # Class 2: 40% waste
                waste_factor = 0.60
            elif normalized_class == 3:
                net_volume = gross_volume * 0.30  # Class 3: 70% waste
                waste_factor = 0.30
            elif normalized_class == 4:
                net_volume = 0.0  # Class 4: All firewood
                waste_factor = 0.0
            else:
                net_volume = gross_volume * 0.60  # Default: Class 2
                waste_factor = 0.60

            _debug_log(f"NET: original_class={measurement.tree_class}, normalized_class={normalized_class}, waste_factor={waste_factor}, gross_vol={gross_volume}, net_vol={net_volume}")

            # 6. Firewood volume
            firewood_m3 = tree_volume - net_volume

            _debug_log(f"FIREWOOD: tree_vol={tree_volume}, net_vol={net_volume}, firewood={firewood_m3}")
            _debug_log(f"FINAL: stem={stem_volume}, branch={branch_volume}, tree={tree_volume}, gross={gross_volume}, net={net_volume}, firewood={firewood_m3}")

            # 7. Convert to cubic feet
            net_volume_cft = net_volume * 35.3147

            # 8. Firewood in chatta
            firewood_chatta = firewood_m3 / 0.267

            # Update measurement
            measurement.stem_volume = round(stem_volume, 6)
            measurement.branch_volume = round(branch_volume, 6)
            measurement.tree_volume = round(tree_volume, 6)
            measurement.gross_volume = round(gross_volume, 6)
            measurement.net_volume = round(net_volume, 6)
            measurement.net_volume_cft = round(net_volume_cft, 6)
            measurement.firewood_m3 = round(firewood_m3, 6)
            measurement.firewood_chatta = round(firewood_chatta, 6)

        self.db.commit()
        logger.info("[VOLUME_CALCULATION] Volume calculations complete")

    async def _calculate_per_hectare(
        self,
        field_inventory_id: UUID,
        field_inventory: FieldInventoryCalculation
    ) -> List[FieldInventoryBlockSummary]:
        """Calculate per-hectare extrapolation for each block"""
        logger.info("[PER_HECTARE] Calculating per-hectare extrapolation...")

        # Get all sample plots grouped by block
        query = text("""
            SELECT DISTINCT block_name
            FROM public.field_inventory_sample_plots
            WHERE field_inventory_calculation_id = :field_inventory_id
        """)
        blocks = self.db.execute(query, {"field_inventory_id": str(field_inventory_id)}).fetchall()

        block_summaries = []

        for (block_name,) in blocks:
            # Get sample plots in this block
            plots = self.db.query(FieldInventorySamplePlot).filter(
                FieldInventorySamplePlot.field_inventory_calculation_id == field_inventory_id,
                FieldInventorySamplePlot.block_name == block_name
            ).all()

            total_sample_plots = len(plots)

            # Get all measurements for this block
            plot_ids = [plot.id for plot in plots]

            # Calculate averages per stand type
            regen_stats = self._calculate_stand_averages('Regeneration', plot_ids, total_sample_plots)
            sapling_stats = self._calculate_stand_averages('Sapling', plot_ids, total_sample_plots)
            pole_stats = self._calculate_stand_averages('Pole', plot_ids, total_sample_plots)
            tree_stats = self._calculate_stand_averages('Tree', plot_ids, total_sample_plots)

            # Extrapolate to per-hectare (1 ha = 10,000 sqm)
            regen_area = float(field_inventory.regeneration_area_sqm)
            sapling_area = float(field_inventory.sapling_area_sqm)
            pole_area = float(field_inventory.pole_area_sqm)
            tree_area = float(field_inventory.tree_area_sqm)

            regen_per_ha = int((regen_stats['count'] / regen_area) * 10000) if regen_stats['count'] > 0 else 0
            sapling_per_ha = int((sapling_stats['count'] / sapling_area) * 10000) if sapling_stats['count'] > 0 else 0
            pole_per_ha = int((pole_stats['count'] / pole_area) * 10000) if pole_stats['count'] > 0 else 0
            tree_per_ha = int((tree_stats['count'] / tree_area) * 10000) if tree_stats['count'] > 0 else 0

            # Extrapolate volumes to per-hectare
            pole_timber_per_ha = (pole_stats['net_volume'] / pole_area) * 10000 if pole_stats['net_volume'] > 0 else 0
            pole_firewood_per_ha = (pole_stats['firewood'] / pole_area) * 10000 if pole_stats['firewood'] > 0 else 0
            tree_timber_per_ha = (tree_stats['net_volume'] / tree_area) * 10000 if tree_stats['net_volume'] > 0 else 0
            tree_firewood_per_ha = (tree_stats['firewood'] / tree_area) * 10000 if tree_stats['firewood'] > 0 else 0

            # Total growing stock (timber only)
            total_growing_stock = pole_timber_per_ha + tree_timber_per_ha

            # Calculate carbon metrics (IPCC/REDD+)
            carbon_metrics = self._calculate_carbon_metrics(
                plot_ids=plot_ids,
                pole_timber_per_ha=pole_timber_per_ha,
                tree_timber_per_ha=tree_timber_per_ha,
                total_growing_stock=total_growing_stock
            )

            # Calculate satellite-derived volume from AGB raster
            satellite_volume = None
            if field_inventory.calculation_id:
                satellite_volume = self._calculate_satellite_volume_for_block(
                    calculation_id=field_inventory.calculation_id,
                    block_name=block_name
                )

            # Calculate NTFP averages and per-hectare values
            # Average NTFP values across all plots in the block, then convert from 100 sqm to per hectare
            ntfp_firewood = 0.0
            ntfp_grass = 0.0
            ntfp_bedding = 0.0
            ntfp_ntfp = 0.0

            for plot in plots:
                if plot.firewood_kg_per_100sqm_per_year:
                    ntfp_firewood += float(plot.firewood_kg_per_100sqm_per_year)
                if plot.grass_kg_per_100sqm_per_year:
                    ntfp_grass += float(plot.grass_kg_per_100sqm_per_year)
                if plot.bedding_material_kg_per_100sqm_per_year:
                    ntfp_bedding += float(plot.bedding_material_kg_per_100sqm_per_year)
                if plot.ntfp_kg_per_100sqm_per_year:
                    ntfp_ntfp += float(plot.ntfp_kg_per_100sqm_per_year)

            # Calculate plot average (sum / number of plots)
            if total_sample_plots > 0:
                ntfp_firewood = ntfp_firewood / total_sample_plots
                ntfp_grass = ntfp_grass / total_sample_plots
                ntfp_bedding = ntfp_bedding / total_sample_plots
                ntfp_ntfp = ntfp_ntfp / total_sample_plots

            # Convert from per 100 sqm to per hectare (multiply by 100)
            # 1 hectare = 10,000 sqm = 100 × 100 sqm
            ntfp_firewood_per_ha = ntfp_firewood * 100
            ntfp_grass_per_ha = ntfp_grass * 100
            ntfp_bedding_per_ha = ntfp_bedding * 100
            ntfp_ntfp_per_ha = ntfp_ntfp * 100

            # Create block summary
            block_summary = FieldInventoryBlockSummary(
                field_inventory_calculation_id=field_inventory_id,
                block_name=block_name,
                total_sample_plots=total_sample_plots,
                regeneration_per_ha=regen_per_ha,
                sapling_per_ha=sapling_per_ha,
                pole_per_ha=pole_per_ha,
                tree_per_ha=tree_per_ha,
                pole_timber_m3_per_ha=round(pole_timber_per_ha, 6),
                pole_firewood_m3_per_ha=round(pole_firewood_per_ha, 6),
                tree_timber_m3_per_ha=round(tree_timber_per_ha, 6),
                tree_firewood_m3_per_ha=round(tree_firewood_per_ha, 6),
                total_growing_stock_m3_per_ha=round(total_growing_stock, 6),
                satellite_volume_m3_per_ha=satellite_volume,
                # Carbon metrics
                weighted_wood_density=carbon_metrics['weighted_density'],
                agb_t_per_ha=carbon_metrics['agb_t_per_ha'],
                bgb_t_per_ha=carbon_metrics['bgb_t_per_ha'],
                total_biomass_t_per_ha=carbon_metrics['total_biomass_t_per_ha'],
                carbon_stock_tc_per_ha=carbon_metrics['carbon_stock_tc_per_ha'],
                co2_equivalent_tco2_per_ha=carbon_metrics['co2_equivalent_tco2_per_ha'],
                # NTFP metrics (kg per hectare per year)
                firewood_kg_per_ha=round(ntfp_firewood_per_ha, 6) if ntfp_firewood_per_ha > 0 else None,
                grass_kg_per_ha=round(ntfp_grass_per_ha, 6) if ntfp_grass_per_ha > 0 else None,
                bedding_material_kg_per_ha=round(ntfp_bedding_per_ha, 6) if ntfp_bedding_per_ha > 0 else None,
                ntfp_kg_per_ha=round(ntfp_ntfp_per_ha, 6) if ntfp_ntfp_per_ha > 0 else None
            )

            self.db.add(block_summary)
            block_summaries.append(block_summary)

            logger.info(f"[PER_HECTARE] Block '{block_name}': Regen={regen_per_ha}/ha, Sapling={sapling_per_ha}/ha, Growing stock={total_growing_stock:.2f} m³/ha")

        self.db.flush()
        logger.info(f"[PER_HECTARE] Per-hectare calculation complete for {len(block_summaries)} blocks")
        return block_summaries

    def _calculate_stand_averages(self, stand_type: str, plot_ids: List[UUID], total_plots: int) -> Dict[str, float]:
        """Calculate average counts and volumes per plot for a stand type"""
        measurements = self.db.query(FieldInventoryMeasurement).filter(
            FieldInventoryMeasurement.sample_plot_id.in_(plot_ids),
            FieldInventoryMeasurement.stand_type == stand_type
        ).all()

        if not measurements:
            return {'count': 0, 'net_volume': 0, 'firewood': 0}

        # Sum counts and volumes
        total_count = sum(m.count for m in measurements)
        total_net_volume = sum(float(m.net_volume or 0) for m in measurements)
        total_firewood = sum(float(m.firewood_m3 or 0) for m in measurements)

        # Calculate averages per plot
        avg_count = total_count / total_plots
        avg_net_volume = total_net_volume / total_plots
        avg_firewood = total_firewood / total_plots

        return {
            'count': avg_count,
            'net_volume': avg_net_volume,
            'firewood': avg_firewood
        }

    def _calculate_carbon_metrics(
        self,
        plot_ids: List[UUID],
        pole_timber_per_ha: float,
        tree_timber_per_ha: float,
        total_growing_stock: float
    ) -> Dict[str, float]:
        """
        Calculate carbon metrics using IPCC/REDD+ methodology

        Formula:
        - AGB (Above-Ground Biomass) = Volume × Wood Density × BEF
        - BGB (Below-Ground Biomass) = AGB × Root-to-Shoot Ratio
        - Total Biomass = AGB + BGB
        - Carbon Stock = Total Biomass × Carbon Fraction
        - CO2 Equivalent = Carbon Stock × 3.67

        IPCC Constants:
        - BEF (Biomass Expansion Factor): 1.40 (tropical broadleaf forests)
        - Root-to-Shoot Ratio: 0.24 (24% of AGB)
        - Carbon Fraction: 0.47 (47% of biomass is carbon)
        - CO2/C Ratio: 3.67 (molecular weight ratio)

        Args:
            plot_ids: List of sample plot UUIDs
            pole_timber_per_ha: Pole timber volume (m³/ha)
            tree_timber_per_ha: Tree timber volume (m³/ha)
            total_growing_stock: Total timber volume (m³/ha)

        Returns:
            Dictionary with carbon metrics
        """
        # IPCC default constants
        BEF = 1.40  # Biomass Expansion Factor (tropical broadleaf)
        ROOT_SHOOT_RATIO = 0.24  # Below-ground / Above-ground ratio
        CARBON_FRACTION = 0.47  # 47% of biomass is carbon
        CO2_TO_C_RATIO = 3.67  # Molecular weight ratio (44/12)

        # If no volume, return zeros
        if total_growing_stock <= 0:
            return {
                'weighted_density': 0.0,
                'agb_t_per_ha': 0.0,
                'bgb_t_per_ha': 0.0,
                'total_biomass_t_per_ha': 0.0,
                'carbon_stock_tc_per_ha': 0.0,
                'co2_equivalent_tco2_per_ha': 0.0
            }

        # Get measurements for Pole and Tree only (they have volume data)
        measurements = self.db.query(FieldInventoryMeasurement).filter(
            FieldInventoryMeasurement.sample_plot_id.in_(plot_ids),
            FieldInventoryMeasurement.stand_type.in_(['Pole', 'Tree']),
            FieldInventoryMeasurement.net_volume.isnot(None),
            FieldInventoryMeasurement.net_volume > 0
        ).all()

        # Calculate volume-weighted wood density
        total_volume_in_plots = 0.0
        weighted_density_sum = 0.0

        for m in measurements:
            species_name = m.species_scientific
            volume = float(m.net_volume or 0)

            # Get wood density for this species
            wood_density = 0.65  # Default if species not found
            if species_name in self.species_coefficients:
                wood_density = self.species_coefficients[species_name].get('wood_density', 0.65)

            total_volume_in_plots += volume
            weighted_density_sum += volume * wood_density

        # Calculate weighted average density (in t/m³, which equals g/cm³)
        if total_volume_in_plots > 0:
            weighted_density = weighted_density_sum / total_volume_in_plots
        else:
            weighted_density = 0.65  # Default tropical forest average

        # Calculate carbon metrics using per-hectare volume
        # Volume is already in m³/ha, density is in t/m³
        agb_t_per_ha = total_growing_stock * weighted_density * BEF
        bgb_t_per_ha = agb_t_per_ha * ROOT_SHOOT_RATIO
        total_biomass_t_per_ha = agb_t_per_ha + bgb_t_per_ha
        carbon_stock_tc_per_ha = total_biomass_t_per_ha * CARBON_FRACTION
        co2_equivalent_tco2_per_ha = carbon_stock_tc_per_ha * CO2_TO_C_RATIO

        logger.info(
            f"[CARBON] Volume={total_growing_stock:.2f} m³/ha, "
            f"Density={weighted_density:.3f} t/m³, "
            f"AGB={agb_t_per_ha:.2f} t/ha, "
            f"CO2e={co2_equivalent_tco2_per_ha:.2f} tCO2/ha"
        )

        return {
            'weighted_density': round(weighted_density, 3),
            'agb_t_per_ha': round(agb_t_per_ha, 6),
            'bgb_t_per_ha': round(bgb_t_per_ha, 6),
            'total_biomass_t_per_ha': round(total_biomass_t_per_ha, 6),
            'carbon_stock_tc_per_ha': round(carbon_stock_tc_per_ha, 6),
            'co2_equivalent_tco2_per_ha': round(co2_equivalent_tco2_per_ha, 6)
        }

    def _calculate_satellite_volume_for_block(self, calculation_id: UUID, block_name: str) -> Optional[float]:
        """
        Calculate satellite-derived volume (m³/ha) for a block using AGB 2022 Nepal raster

        Formula: Volume (m³/ha) = AGB (Mg/ha) × 0.67 (wood density conversion)

        Args:
            calculation_id: The calculation ID containing the block geometry
            block_name: Name of the block to calculate volume for

        Returns:
            Volume in m³/ha, or None if calculation fails
        """
        try:
            # Get the block geometry from the calculation's result_data
            query = text("""
                SELECT jsonb_array_elements(result_data->'blocks') AS block
                FROM public.calculations
                WHERE id = :calc_id
            """)

            result = self.db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

            # Find the block with matching name
            block_wkt = None
            for (block_json,) in result:
                if block_json.get('block_name') == block_name or block_json.get('ward') == block_name:
                    block_wkt = block_json.get('wkt')
                    break

            if not block_wkt:
                logger.warning(f"[SATELLITE_VOLUME] No geometry found for block '{block_name}'")
                return None

            # Query AGB raster for this block geometry
            agb_query = text("""
                SELECT
                    (stats).mean as agb_mean
                FROM (
                    SELECT ST_SummaryStats(
                        ST_Clip(rast, 1, ST_GeomFromText(:wkt, 4326)),
                        1,  -- band 1
                        true  -- exclude nodata
                    ) as stats
                    FROM rasters.agb_2022_nepal
                    WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                    LIMIT 1
                ) as subquery
            """)

            agb_result = self.db.execute(agb_query, {"wkt": block_wkt}).first()

            if agb_result and agb_result.agb_mean and agb_result.agb_mean > 0:
                # Convert AGB (Mg/ha) to Volume (m³/ha) using 0.67 conversion factor
                # This matches the conversion used in User Group Map analysis
                volume_m3_per_ha = float(agb_result.agb_mean) * 0.67
                logger.info(f"[SATELLITE_VOLUME] Block '{block_name}': AGB={agb_result.agb_mean:.2f} Mg/ha, Volume={volume_m3_per_ha:.2f} m³/ha")
                return round(volume_m3_per_ha, 6)
            else:
                logger.warning(f"[SATELLITE_VOLUME] No AGB data found for block '{block_name}'")
                return None

        except Exception as e:
            logger.error(f"[SATELLITE_VOLUME] Error calculating satellite volume for block '{block_name}': {e}")
            return None

    async def _assess_forest_condition(self, block_summaries: List[FieldInventoryBlockSummary]):
        """Assess forest condition for each block"""
        logger.info("[FOREST_CONDITION] Assessing forest condition...")

        for block in block_summaries:
            # 1. Assess regeneration condition (AND logic)
            regen_per_ha = block.regeneration_per_ha or 0
            sapling_per_ha = block.sapling_per_ha or 0

            if regen_per_ha >= 5000 and sapling_per_ha >= 2000:
                regen_condition = 'Good'
            elif regen_per_ha >= 2000 and sapling_per_ha >= 800:
                regen_condition = 'Moderate'
            else:
                regen_condition = 'Weak'

            block.regeneration_condition = regen_condition

            # 2. Assess overall forest condition (based on growing stock + regeneration)
            growing_stock = float(block.total_growing_stock_m3_per_ha or 0)

            if growing_stock > 200:
                if regen_condition == 'Good':
                    forest_condition = 'Good'
                elif regen_condition == 'Moderate':
                    forest_condition = 'Good'
                else:
                    forest_condition = 'Moderate'
            elif growing_stock >= 50:
                if regen_condition == 'Good':
                    forest_condition = 'Good'
                elif regen_condition == 'Moderate':
                    forest_condition = 'Moderate'
                else:
                    forest_condition = 'Weak'
            else:  # < 50
                if regen_condition == 'Good':
                    forest_condition = 'Moderate'
                elif regen_condition == 'Moderate':
                    forest_condition = 'Weak'
                else:
                    forest_condition = 'Weak'

            block.forest_condition = forest_condition

            logger.info(f"[FOREST_CONDITION] Block '{block.block_name}': Regen={regen_condition}, Forest={forest_condition}, Growing stock={growing_stock:.2f} m³/ha")

        self.db.commit()
        logger.info("[FOREST_CONDITION] Forest condition assessment complete")

    async def _calculate_mai(self, block_summaries: List[FieldInventoryBlockSummary], field_inventory_id: UUID):
        """Calculate Mean Annual Increment for each block"""
        logger.info("[MAI] Calculating Mean Annual Increment...")

        for block in block_summaries:
            # Get dominant species growth rate in this block
            dominant_growth_rate = await self._get_dominant_growth_rate(field_inventory_id, block.block_name)

            block.dominant_growth_rate = dominant_growth_rate

            # Calculate MAI based on forest condition + growth rate
            forest_condition = block.forest_condition
            mai_matrix = {
                ('Fast', 'Good'): 5.0,
                ('Fast', 'Moderate'): 4.0,
                ('Fast', 'Weak'): 3.0,
                ('Moderate', 'Good'): 4.0,
                ('Moderate', 'Moderate'): 3.0,
                ('Moderate', 'Weak'): 2.0,
                ('Slow', 'Good'): 3.0,
                ('Slow', 'Moderate'): 2.0,
                ('Slow', 'Weak'): 1.0,
            }

            mai = mai_matrix.get((dominant_growth_rate, forest_condition), 2.0)
            block.mai_percent = round(mai, 2)

            logger.info(f"[MAI] Block '{block.block_name}': Growth rate={dominant_growth_rate}, MAI={mai}%")

        self.db.commit()
        logger.info("[MAI] MAI calculation complete")

    async def _get_dominant_growth_rate(self, field_inventory_id: UUID, block_name: str) -> str:
        """Get dominant growth rate for species in this block"""
        # Get all measurements in this block
        query = text("""
            SELECT m.species_scientific, COUNT(*) as count
            FROM public.field_inventory_measurements m
            JOIN public.field_inventory_sample_plots p ON m.sample_plot_id = p.id
            WHERE p.field_inventory_calculation_id = :field_inventory_id
              AND p.block_name = :block_name
              AND m.stand_type IN ('Pole', 'Tree')
            GROUP BY m.species_scientific
            ORDER BY count DESC
            LIMIT 5
        """)

        result = self.db.execute(query, {
            "field_inventory_id": str(field_inventory_id),
            "block_name": block_name
        }).fetchall()

        # Count growth rates
        growth_rate_counts = {'Fast': 0, 'Moderate': 0, 'Slow': 0}

        for (species, count) in result:
            coef = self.species_coefficients.get(species, {})
            growth_rate = coef.get('growth_rate', 'Moderate')

            if growth_rate in growth_rate_counts:
                growth_rate_counts[growth_rate] += count

        # Find dominant
        dominant = max(growth_rate_counts, key=growth_rate_counts.get)
        return dominant
