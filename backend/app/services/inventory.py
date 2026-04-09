"""
Inventory service - Tree volume calculations and mother tree selection
Based on allometric equations for Nepal tree species
"""
import math
import pandas as pd
from typing import Dict, Any, Tuple, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
from datetime import datetime
import sys
import io
import logging

# Set stdout to UTF-8 immediately
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

# Create a silent logger
class SilentHandler(logging.Handler):
    def emit(self, record):
        pass

logging.basicConfig(level=logging.WARNING, handlers=[SilentHandler()])
logger = logging.getLogger('inventory')

# Override print to handle encoding issues gracefully
import builtins
_original_print = builtins.print

def _safe_print(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except UnicodeEncodeError:
        # Convert all args to safe strings
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Encode to bytes then decode to replace invalid chars
                safe_args.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
            else:
                safe_args.append(str(arg))
        _original_print(*safe_args, **kwargs)

builtins.print = _safe_print

from ..models.inventory import (
    InventoryCalculation,
    InventoryTree,
    TreeSpeciesCoefficient
)
from ..models.forest_block import ForestBlock
from ..utils.diameter_classifier import DiameterClassifier


class InventoryService:
    """
    Main inventory processing service
    Handles volume calculations and mother tree selection
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.species_coefficients = self._load_species_coefficients()

    def _load_species_coefficients(self) -> Dict[str, Dict]:
        """Load species coefficients from database"""
        query = text("""
            SELECT scientific_name, a, b, c, a1, b1, s, m, bg, local_name
            FROM public.tree_species_coefficients
            WHERE is_active = TRUE
        """)
        result = self.db.execute(query).fetchall()

        coefficients = {}
        for row in result:
            coefficients[row[0]] = {
                'a': row[1],
                'b': row[2],
                'c': row[3],
                'a1': row[4],
                'b1': row[5],
                's': row[6],
                'm': row[7],
                'bg': row[8],
                'local_name': row[9]
            }

        return coefficients

    async def process_inventory(
        self,
        inventory_id: UUID,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        species_col: str,
        diameter_col: str,
        height_col: str = None,
        class_col: str = None,
        crs_epsg: int = 4326
    ) -> Dict[str, Any]:
        """
        Process complete inventory: volumes and mother trees

        Args:
            inventory_id: UUID of inventory calculation
            df: Validated DataFrame with tree data
            x_col: Longitude/X column name
            y_col: Latitude/Y column name
            species_col: Species column name
            diameter_col: Diameter column name
            height_col: Height column name (optional)
            class_col: Tree class column name (optional)
            crs_epsg: EPSG code for coordinates

        Returns:
            Processing summary dict
        """
        start_time = time.time()

        # Get inventory calculation record
        inventory = self.db.query(InventoryCalculation).filter(
            InventoryCalculation.id == inventory_id
        ).first()

        if not inventory:
            raise ValueError(f"Inventory calculation {inventory_id} not found")

        try:
            # Update status
            inventory.status = 'processing'
            self.db.commit()

            # 1. Calculate volumes for all trees
            df = self.calculate_tree_volumes(df, species_col, diameter_col, height_col, class_col)

            # 2. Create GeoDataFrame with coordinates
            df['geometry'] = df.apply(
                lambda row: Point(row[x_col], row[y_col]),
                axis=1
            )
            trees_gdf = gpd.GeoDataFrame(df, geometry='geometry', crs=f'EPSG:{crs_epsg}')

            # Transform to WGS84 if needed
            if crs_epsg != 4326:
                trees_gdf = trees_gdf.to_crs('EPSG:4326')

            # 3. Identify mother trees using grid
            trees_gdf = await self.identify_mother_trees(
                trees_gdf,
                inventory.grid_spacing_meters,
                inventory.projection_epsg
            )

            # 4. Store trees in database
            await self._store_trees(inventory_id, trees_gdf, species_col, diameter_col, height_col, class_col)

            # 5. Calculate summary statistics
            summary = self._calculate_summary_statistics(trees_gdf)

            # 6. Update inventory record
            inventory.total_trees = summary['total_trees']
            inventory.mother_trees_count = summary['mother_trees_count']
            inventory.felling_trees_count = summary['felling_trees_count']
            inventory.seedling_count = summary['seedling_count']
            inventory.total_volume_m3 = summary['total_volume_m3']
            inventory.total_net_volume_m3 = summary['total_net_volume_m3']
            inventory.total_net_volume_cft = summary['total_net_volume_cft']
            inventory.total_firewood_m3 = summary['total_firewood_m3']
            inventory.total_firewood_chatta = summary['total_firewood_chatta']
            inventory.status = 'completed'
            inventory.processing_time_seconds = int(time.time() - start_time)
            self.db.commit()

            return summary

        except UnicodeEncodeError as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[UNICODE_ERROR] {str(e)}")
            print(f"[UNICODE_TRACE] {tb}")
            inventory.status = 'failed'
            inventory.error_message = "Unicode encoding error during processing"
            self.db.commit()
            raise Exception(f"Unicode encoding error: {str(e)}")
        except Exception as e:
            inventory.status = 'failed'
            error_msg = str(e)
            try:
                error_msg.encode('utf-8')
            except UnicodeEncodeError:
                error_msg = "Processing error (Unicode characters in data)"
            inventory.error_message = error_msg
            self.db.commit()
            raise

    async def _convert_species_to_scientific(
        self,
        df: pd.DataFrame,
        species_col: str,
        calculation_id: UUID = None
    ) -> pd.DataFrame:
        """
        Convert species codes and local names to scientific names + local names

        Args:
            df: DataFrame with tree data
            species_col: Name of the species column
            calculation_id: Optional calculation ID for physiographic zone detection

        Returns:
            DataFrame with converted species names and added local_name column
        """
        from ..services.validators.species_code_validator import SpeciesCodeValidator

        # Initialize validator
        validator = SpeciesCodeValidator(self.db)

        # Determine physiographic zone (disabled for performance - defaults to Hill spp)
        physiographic_zone = None

        # Add local_name column if it doesn't exist
        if 'local_name' not in df.columns:
            df['local_name'] = ''

        # Convert each species value
        converted_count = 0
        for idx, row in df.iterrows():
            original_species = row[species_col]

            # Convert code/local name to scientific name
            scientific_name, species_code, method, confidence, warning = validator.validate_species_value(
                original_species,
                physiographic_zone
            )

            # Update the species column with scientific name
            if scientific_name != original_species:
                df.at[idx, species_col] = scientific_name
                converted_count += 1
                print(f"[SPECIES] Row {idx+1}: '{original_species}' -> '{scientific_name}' (method: {method})")

            # Get local name from species_by_code
            local_name = None
            if species_code and species_code in validator.species_by_code:
                local_name = validator.species_by_code[species_code]['local_name']

            if local_name:
                df.at[idx, 'local_name'] = local_name

        print(f"[SPECIES] Converted {converted_count} species codes/local names to scientific names")
        return df

    def calculate_tree_volumes(
        self,
        df: pd.DataFrame,
        species_col: str,
        diameter_col: str,
        height_col: str = None,
        class_col: str = None
    ) -> pd.DataFrame:
        """
        Calculate volumes for all trees using allometric equations

        Args:
            df: DataFrame with tree data
            species_col: Species column name
            diameter_col: Diameter column name
            height_col: Height column name (optional)
            class_col: Tree class column name (optional)

        Returns:
            DataFrame with calculated volumes
        """
        # Add calculated columns
        df['stem_volume'] = 0.0
        df['branch_volume'] = 0.0
        df['tree_volume'] = 0.0
        df['gross_volume'] = 0.0
        df['net_volume'] = 0.0
        df['net_volume_cft'] = 0.0
        df['firewood_m3'] = 0.0
        df['firewood_chatta'] = 0.0

        for idx, row in df.iterrows():
            species = row[species_col]
            dbh_cm = row[diameter_col]

            # REGENERATION: Skip volume calculation for trees < 10 cm (too small for commercial use)
            if dbh_cm < 10:
                # All volumes remain 0.0 (already initialized)
                continue

            # Get species coefficients
            if species not in self.species_coefficients:
                # Skip if species not found (should not happen after validation)
                continue

            coef = self.species_coefficients[species]

            # Get or estimate height (avoid Series ambiguity)
            height_val = None
            if height_col and height_col in df.columns:
                height_val = row[height_col]

            if height_val and pd.notna(height_val):
                height_m = float(height_val)
            else:
                # Estimate height using default H/D ratio
                height_m = dbh_cm * 0.8  # Default ratio for missing heights

            # 1. Calculate stem volume (काण्डको आयतन)
            # Formula: V = exp(a + b*ln(DBH) + c*ln(H)) / 1000
            # Source: Forest Regulation 2079, Table 1
            if coef['a'] is not None and coef['b'] is not None and coef['c'] is not None:
                stem_volume = math.exp(
                    coef['a'] +
                    coef['b'] * math.log(dbh_cm) +
                    coef['c'] * math.log(height_m)
                ) / 1000.0  # Convert to m³
            else:
                # Use generic formula for species without coefficients
                stem_volume = 0.0

            # 2. Calculate branch volume (हाँगाको आयतन)
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
                branch_volume = stem_volume * 0.2

            # 3. Total tree volume (रुखको आयतन)
            # Formula: Tree Volume = Stem Volume + Branch Volume
            # Source: Forest Regulation 2079, Section 3(ii)
            tree_volume = stem_volume + branch_volume

            # 4. Calculate gross timber volume (काठको मूल आयतन)
            # Formula: Gross Timber = Stem Volume - 10cm Top Diameter Stem Volume
            # Source: Forest Regulation 2079, Section 4 (काठको मूल आयतन)
            # NOTE: Gross timber comes ONLY from stem (trunk), not branches
            # Branches go directly to firewood category
            # Remove top portion of stem where diameter < 10 cm (non-merchantable)
            if coef['a1'] is not None and coef['b1'] is not None:
                # Calculate 10cm top diameter ratio
                cm10_dia_ratio = math.exp(
                    coef['a1'] + coef['b1'] * math.log(dbh_cm)
                )
                # Apply ratio to STEM volume (regulation uses stem, not tree)
                cm10_top_volume = stem_volume * cm10_dia_ratio
                gross_volume = stem_volume - cm10_top_volume
            else:
                # Fallback: Assume 85% of stem volume is merchantable
                gross_volume = stem_volume * 0.85

            # 5. Calculate net timber volume (काठको नेट आयतन)
            # Apply waste factors based on tree class (दर्जा)
            # Source: Forest Regulation 2079, Section 5 (दर्जा अनुसार नेट आयतन)

            # Get class value safely (avoid Series ambiguity)
            class_val = None
            if class_col is not None and class_col in df.columns:
                try:
                    class_val = row[class_col]
                    # Handle empty strings or NaN
                    if pd.isna(class_val) or (isinstance(class_val, str) and str(class_val).strip() == ''):
                        class_val = None
                except (KeyError, TypeError):
                    class_val = None

            # Use class for waste calculation (default to Class 2 if not provided)
            if class_val is not None:
                tree_class = str(class_val).strip()
            else:
                tree_class = '2'  # Default to Class 2 (moderate quality)

            # Apply waste factor based on class (Forest Regulation 2079)
            # Class 1 (पहिलो दर्जा): 80% net, 20% waste
            # Class 2 (दोस्रो दर्जा): 60% net, 40% waste
            # Class 3 (तेस्रो दर्जा): 30% net, 70% waste
            # Class 4 (चौथो दर्जा): 0% timber (all firewood)
            if tree_class == '1' or tree_class.upper() == 'A':
                net_volume = gross_volume * 0.80  # 20% waste
            elif tree_class == '2' or tree_class.upper() == 'B':
                net_volume = gross_volume * 0.60  # 40% waste
            elif tree_class == '3' or tree_class.upper() == 'C':
                net_volume = gross_volume * 0.30  # 70% waste
            elif tree_class == '4' or tree_class.upper() == 'D':
                net_volume = 0.0  # All firewood (100% waste)
            else:
                # Unknown class: default to Class 2 (moderate)
                net_volume = gross_volume * 0.60

            # 6. Convert net volume to cubic feet
            net_volume_cft = net_volume * 35.3147

            # 7. Calculate firewood volume
            firewood_m3 = tree_volume - net_volume

            # 8. Convert firewood to chatta (local unit)
            # 1 chatta ≈ 9.445 cubic feet ≈ 0.267 m³
            firewood_chatta = firewood_m3 / 0.267

            # Store in DataFrame
            df.at[idx, 'stem_volume'] = stem_volume
            df.at[idx, 'branch_volume'] = branch_volume
            df.at[idx, 'tree_volume'] = tree_volume
            df.at[idx, 'gross_volume'] = gross_volume
            df.at[idx, 'net_volume'] = net_volume
            df.at[idx, 'net_volume_cft'] = net_volume_cft
            df.at[idx, 'firewood_m3'] = firewood_m3
            df.at[idx, 'firewood_chatta'] = firewood_chatta

        return df

    async def identify_mother_trees(
        self,
        trees_gdf: gpd.GeoDataFrame,
        grid_spacing_meters: float,
        projection_epsg: int
    ) -> gpd.GeoDataFrame:
        """
        Identify mother trees using grid-based selection

        Args:
            trees_gdf: GeoDataFrame with trees (in EPSG:4326)
            grid_spacing_meters: Grid cell size in meters
            projection_epsg: UTM zone for grid creation

        Returns:
            GeoDataFrame with 'remark' column added
        """
        # First classify stand types
        if 'dia_cm' in trees_gdf.columns:
            trees_gdf['stand_type'] = trees_gdf['dia_cm'].apply(DiameterClassifier.classify_simple)

        # Initialize remark based on stand_type
        # - Regeneration/Sapling: 'Seedling'
        # - Pole: 'Pole' (cannot be felling or mother tree)
        # - Tree: 'Felling Tree' (default), will be updated to 'Mother Tree' by grid
        trees_gdf['remark'] = None
        trees_gdf['grid_cell_id'] = None

        # Mark based on stand_type
        stand_type = trees_gdf.get('stand_type')
        
        # Regeneration and Sapling: remark = 'Seedling'
        trees_gdf.loc[stand_type.isin(['Regeneration', 'Sapling']), 'remark'] = 'Seedling'
        
        # Pole: remark = 'Pole' (not for felling or mother tree)
        trees_gdf.loc[stand_type == 'Pole', 'remark'] = 'Pole'
        
        # Tree: can be 'Felling Tree' or 'Mother Tree' (default to Felling Tree)
        trees_gdf.loc[stand_type == 'Tree', 'remark'] = 'Felling Tree'

        # Filter to only Tree (DBH >= 30) for mother tree selection
        eligible_trees = trees_gdf[trees_gdf['dia_cm'] >= 30].copy()

        if len(eligible_trees) == 0:
            # No eligible trees (all are seedlings/saplings)
            return trees_gdf

        # Create bounding box
        xmin, ymin, xmax, ymax = eligible_trees.total_bounds
        bounding_polygon = box(xmin, ymin, xmax, ymax)
        bounding_gdf = gpd.GeoDataFrame(geometry=[bounding_polygon], crs='EPSG:4326')

        # Transform to projected CRS for accurate grid creation
        bounding_gdf_proj = bounding_gdf.to_crs(f'EPSG:{projection_epsg}')
        eligible_trees_proj = eligible_trees.to_crs(f'EPSG:{projection_epsg}')

        # Get bounds in projected CRS
        xmin_proj, ymin_proj, xmax_proj, ymax_proj = bounding_gdf_proj.total_bounds

        # Create grid cells
        grid_cells = []
        cell_id = 0

        x = xmin_proj
        while x < xmax_proj:
            y = ymin_proj
            while y < ymax_proj:
                # Create grid cell polygon
                cell = box(x, y, x + grid_spacing_meters, y + grid_spacing_meters)
                grid_cells.append({'geometry': cell, 'cell_id': cell_id})
                cell_id += 1
                y += grid_spacing_meters
            x += grid_spacing_meters

        # Create GeoDataFrame of grid cells
        grid_gdf = gpd.GeoDataFrame(grid_cells, crs=f'EPSG:{projection_epsg}')

        # Find grid cells that contain trees
        joined = gpd.sjoin(grid_gdf, eligible_trees_proj, how='inner', predicate='intersects')

        # For each cell with trees, find the tree nearest to cell centroid
        mother_tree_indices = []

        for cell_id in joined['cell_id'].unique():
            # Get this cell and its trees
            cell_geom = grid_gdf[grid_gdf['cell_id'] == cell_id].iloc[0]['geometry']
            cell_centroid = cell_geom.centroid

            # Get trees in this cell
            trees_in_cell_indices = joined[joined['cell_id'] == cell_id].index_right.unique()
            trees_in_cell = eligible_trees_proj.loc[trees_in_cell_indices]

            # Find nearest tree to centroid
            distances = trees_in_cell.geometry.distance(cell_centroid)
            nearest_idx = distances.idxmin()

            mother_tree_indices.append(nearest_idx)

            # Mark grid cell ID
            trees_gdf.at[nearest_idx, 'grid_cell_id'] = int(cell_id)

        # Mark mother trees (only for eligible trees - DBH >= 10)
        trees_gdf.loc[mother_tree_indices, 'remark'] = 'Mother Tree'

        return trees_gdf

    async def _store_trees(
        self,
        inventory_id: UUID,
        trees_gdf: gpd.GeoDataFrame,
        species_col: str,
        diameter_col: str,
        height_col: str = None,
        class_col: str = None
    ):
        """
        Store trees in database

        Args:
            inventory_id: UUID of inventory calculation
            trees_gdf: GeoDataFrame with processed trees
            species_col: Species column name
            diameter_col: Diameter column name
            height_col: Height column name (optional)
            class_col: Tree class column name (optional)
        """
        trees_to_insert = []

        for idx, row in trees_gdf.iterrows():
            # Get local name from species coefficients
            species = row[species_col]
            local_name = self.species_coefficients.get(species, {}).get('local_name')

            # Get coordinates
            lon, lat = row.geometry.x, row.geometry.y

            # Get height and class values
            height_val = row[height_col] if height_col else None
            class_val = row[class_col] if class_col else None

            # Convert empty strings to None for class (from class normalization)
            if isinstance(class_val, str) and class_val.strip() == '':
                class_val = None

            tree = InventoryTree(
                inventory_calculation_id=inventory_id,
                species=species,
                dia_cm=float(row[diameter_col]),
                height_m=float(height_val) if pd.notna(height_val) else None,
                tree_class=class_val if pd.notna(class_val) else None,
                location=f'SRID=4326;POINT({lon} {lat})',
                stem_volume=float(row['stem_volume']),
                branch_volume=float(row['branch_volume']),
                tree_volume=float(row['tree_volume']),
                gross_volume=float(row['gross_volume']),
                net_volume=float(row['net_volume']),
                net_volume_cft=float(row['net_volume_cft']),
                firewood_m3=float(row['firewood_m3']),
                firewood_chatta=float(row['firewood_chatta']),
                remark=row['remark'],
                grid_cell_id=int(row['grid_cell_id']) if pd.notna(row['grid_cell_id']) else None,
                local_name=local_name,
                row_number=idx + 2  # +2 for header and 0-indexing
            )

            trees_to_insert.append(tree)

        # Bulk insert
        self.db.bulk_save_objects(trees_to_insert)
        self.db.commit()

    def _calculate_summary_statistics(self, trees_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """
        Calculate summary statistics

        Args:
            trees_gdf: GeoDataFrame with processed trees

        Returns:
            Summary statistics dict
        """
        total_trees = len(trees_gdf)
        mother_trees = len(trees_gdf[trees_gdf['remark'] == 'Mother Tree'])
        felling_trees = len(trees_gdf[trees_gdf['remark'] == 'Felling Tree'])
        seedlings = len(trees_gdf[trees_gdf['remark'] == 'Seedling'])
        poles = len(trees_gdf[trees_gdf['remark'] == 'Pole'])

        # Sum volumes
        total_volume_m3 = trees_gdf['tree_volume'].sum()
        total_net_volume_m3 = trees_gdf['net_volume'].sum()
        total_net_volume_cft = trees_gdf['net_volume_cft'].sum()
        total_firewood_m3 = trees_gdf['firewood_m3'].sum()
        total_firewood_chatta = trees_gdf['firewood_chatta'].sum()

        return {
            'total_trees': total_trees,
            'mother_trees_count': mother_trees,
            'felling_trees_count': felling_trees,
            'seedling_count': seedlings,
            'pole_count': poles,
            'total_volume_m3': round(total_volume_m3, 3),
            'total_net_volume_m3': round(total_net_volume_m3, 3),
            'total_net_volume_cft': round(total_net_volume_cft, 3),
            'total_firewood_m3': round(total_firewood_m3, 3),
            'total_firewood_chatta': round(total_firewood_chatta, 3)
        }

    async def process_inventory_simple(
        self,
        inventory_id: UUID,
        df: pd.DataFrame,
        grid_spacing_meters: float = 20.0
    ) -> Dict[str, Any]:
        """
        Process inventory without GDAL dependencies (simplified version)
        - Calculates tree volumes
        - Stores trees in database
        - Uses PostGIS for mother tree selection (no GeoPandas needed)

        Args:
            inventory_id: UUID of inventory calculation
            df: DataFrame with validated tree data
            grid_spacing_meters: Grid spacing for mother tree selection

        Returns:
            Processing summary dict
        """
        import time
        
        # Wrap everything in a Unicode-safe try-catch
        try:
            return await self._process_inventory_internal(inventory_id, df, grid_spacing_meters)
        except UnicodeEncodeError as e:
            # This is the charmap error - get details from traceback
            import traceback
            tb = traceback.format_exc()
            print(f"[UNICODE_ERROR] {str(e)}")
            print(f"[UNICODE_TRACE] {tb}")
            # Get the original traceback to find where it happened
            raise Exception(f"Unicode encoding error: character at position {e.start} in '{e.object[e.start-10:e.end+10] if e.start > 0 else e.object[:e.end+10]}'")
        except Exception as e:
            # Try to sanitize error message for response
            error_msg = str(e)
            try:
                # Test if message can be encoded/decoded
                error_msg = error_msg.encode('utf-8').decode('utf-8')
            except:
                # If encoding fails, create a generic message
                error_msg = f"Processing error (original error type: {type(e).__name__})"
            raise Exception(error_msg)

    async def _process_inventory_internal(
        self,
        inventory_id: UUID,
        df: pd.DataFrame,
        grid_spacing_meters: float = 20.0
    ) -> Dict[str, Any]:
        import time
        start_time = time.time()

        # Get inventory calculation record
        inventory = self.db.query(InventoryCalculation).filter(
            InventoryCalculation.id == inventory_id
        ).first()

        if not inventory:
            raise ValueError(f"Inventory calculation {inventory_id} not found")

        try:
            # Update status
            inventory.status = 'processing'
            self.db.commit()
            print(f"[INVENTORY] Processing inventory {inventory_id} with {len(df)} trees")

            # Detect column names (case-insensitive)
            df.columns = df.columns.str.lower()
            print(f"[INVENTORY] Available columns: {list(df.columns)}")

            # Map possible column names
            species_col = next((col for col in df.columns if 'species' in col or 'scientific' in col), 'species')
            diameter_col = next((col for col in df.columns if 'dia' in col or 'dbh' in col), 'dia_cm')
            height_col = next((col for col in df.columns if 'height' in col), 'height_m')
            class_col = next((col for col in df.columns if 'class' in col or 'quality' in col), 'class')
            lon_col = next((col for col in df.columns if 'lon' in col or col == 'x'), 'longitude')
            lat_col = next((col for col in df.columns if 'lat' in col or col == 'y'), 'latitude')

            print(f"[INVENTORY] Column mapping: species={species_col}, dia={diameter_col}, height={height_col}, class={class_col}, lon={lon_col}, lat={lat_col}")

            # 1. Convert species codes and local names to scientific names
            print(f"[INVENTORY] Step 1/5: Converting species codes to scientific names...")
            df = await self._convert_species_to_scientific(df, species_col, inventory.calculation_id)
            print(f"[INVENTORY] Step 1/5: Species conversion completed")

            # 2. Calculate volumes for all trees
            print(f"[INVENTORY] Step 2/6: Calculating volumes...")
            df = self.calculate_tree_volumes(df, species_col, diameter_col, height_col, class_col)
            print(f"[INVENTORY] Step 2/6: Volumes calculated successfully")

            # 3. Initially mark all trees based on stand_type
            print(f"[INVENTORY] Step 3/7: Marking trees by stand type...")
            df['stand_type'] = df[diameter_col].apply(DiameterClassifier.classify_simple)
            df['remark'] = df['stand_type'].apply(
                lambda st: 'Seedling' if st in ['Regeneration', 'Sapling'] else ('Pole' if st == 'Pole' else 'Felling Tree')
            )
            df['grid_cell_id'] = None
            seedling_count = len(df[df['remark'] == 'Seedling'])
            pole_count = len(df[df['remark'] == 'Pole'])
            felling_count = len(df[df['remark'] == 'Felling Tree'])
            print(f"[INVENTORY] Step 3/7: Marked {seedling_count} seedlings, {pole_count} poles, {felling_count} felling trees")

            # 4. Add diameter classification (stand_type and dbh_class)
            print(f"[INVENTORY] Step 4/7: Classifying trees by diameter...")
            df['stand_type'] = df[diameter_col].apply(DiameterClassifier.classify_simple)
            df['dbh_class'] = df[diameter_col].apply(DiameterClassifier.classify_detailed)

            # Count trees by classification
            stand_type_counts = df['stand_type'].value_counts().to_dict()
            print(f"[INVENTORY] Step 4/7: Classified trees - Regeneration: {stand_type_counts.get('Regeneration', 0)}, Sapling: {stand_type_counts.get('Sapling', 0)}, Pole: {stand_type_counts.get('Pole', 0)}, Tree: {stand_type_counts.get('Tree', 0)}")

            # 5. Assign polygon boundary name to each tree
            print(f"[INVENTORY] Step 5/7: Assigning polygon boundaries...")
            # Get boundary geometry from calculation
            if inventory.calculation and inventory.calculation.boundary_geom:
                # Extract block name from calculation (if available)
                block_name = inventory.calculation.block_name or inventory.calculation.forest_name or 'Main Block'
                df['polygon_boundary'] = block_name
                print(f"[INVENTORY] Step 5/7: Assigned all trees to boundary '{block_name}'")
            else:
                df['polygon_boundary'] = 'Unknown'
                print(f"[INVENTORY] Step 5/7: Warning - No boundary geometry found, using 'Unknown'")

            # 6. Store trees in database FIRST (needed for PostGIS mother tree selection)
            print(f"[INVENTORY] Step 6/7: Storing {len(df)} trees in database...")
            await self._store_trees_simple(
                inventory_id, df, species_col, diameter_col, height_col,
                class_col, lon_col, lat_col
            )
            print(f"[INVENTORY] Step 6/7: Successfully stored {len(df)} trees")

            # 7. Identify mother trees using PostGIS
            print(f"[INVENTORY] Step 7/7: Identifying mother trees (grid: {grid_spacing_meters}m, EPSG: {inventory.projection_epsg})...")
            mother_tree_count = await self._identify_mother_trees_postgis(
                inventory_id,
                grid_spacing_meters,
                inventory.projection_epsg
            )
            print(f"[INVENTORY] Step 7/7: Identified {mother_tree_count} mother trees")

            # 8. Calculate summary statistics from database
            print(f"[INVENTORY] Step 7/7: Calculating summary statistics...")
            summary = await self._calculate_summary_from_db(inventory_id)
            print(f"[INVENTORY] Step 7/7: Summary calculated")

            # 6. Update inventory record (convert numpy types to Python types)
            inventory.total_trees = int(summary['total_trees'])
            inventory.mother_trees_count = int(summary['mother_trees_count'])
            inventory.felling_trees_count = int(summary['felling_trees_count'])
            inventory.seedling_count = int(summary['seedling_count'])
            inventory.pole_count = int(summary.get('pole_count', 0))
            inventory.total_volume_m3 = float(summary['total_volume_m3'])
            inventory.total_net_volume_m3 = float(summary['total_net_volume_m3'])
            inventory.total_net_volume_cft = float(summary['total_net_volume_cft'])
            inventory.total_firewood_m3 = float(summary['total_firewood_m3'])
            inventory.total_firewood_chatta = float(summary['total_firewood_chatta'])
            inventory.status = 'completed'
            inventory.completed_at = datetime.utcnow()
            inventory.processing_time_seconds = int(time.time() - start_time)
            self.db.commit()

            return summary

        except UnicodeEncodeError as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[UNICODE_ERROR] {str(e)}")
            print(f"[UNICODE_TRACE] {tb}")
            inventory.status = 'failed'
            inventory.error_message = "Unicode encoding error during processing"
            self.db.commit()
            raise Exception(f"Unicode encoding error: {str(e)}")
        except Exception as e:
            inventory.status = 'failed'
            error_msg = str(e)
            try:
                error_msg.encode('utf-8')
            except UnicodeEncodeError:
                error_msg = "Processing error (Unicode characters in data)"
            inventory.error_message = error_msg
            self.db.commit()
            raise

    async def _store_trees_simple(
        self,
        inventory_id: UUID,
        df: pd.DataFrame,
        species_col: str,
        diameter_col: str,
        height_col: str,
        class_col: str,
        lon_col: str,
        lat_col: str
    ):
        """
        Store trees in database (simplified without GeoPandas)

        Args:
            inventory_id: UUID of inventory calculation
            df: DataFrame with processed trees
            species_col: Species column name
            diameter_col: Diameter column name
            height_col: Height column name
            class_col: Tree class column name
            lon_col: Longitude column name
            lat_col: Latitude column name
        """
        trees_to_insert = []
        batch_size = 1000  # Insert in batches to avoid memory issues

        # Define known columns that are stored in specific fields
        known_columns = {
            species_col, diameter_col, height_col, class_col, lon_col, lat_col,
            'local_name', 'stem_volume', 'branch_volume', 'tree_volume',
            'gross_volume', 'net_volume', 'net_volume_cft', 'firewood_m3',
            'firewood_chatta', 'remark', 'grid_cell_id',
            'stand_type', 'dbh_class', 'polygon_boundary'  # New classification columns
        }

        # Identify ALL extra columns upfront (not row by row)
        extra_column_names = [col for col in df.columns if col not in known_columns and col.strip() != '']

        print(f"[EXTRA COLUMNS] All columns in DataFrame: {list(df.columns)}")
        print(f"[EXTRA COLUMNS] Known columns: {known_columns}")
        print(f"[EXTRA COLUMNS] Extra columns detected: {extra_column_names}")

        try:
            for idx, row in df.iterrows():
                # Get species and local name
                species = row[species_col]
                local_name = row.get('local_name', None) if 'local_name' in df.columns else None

                # Get coordinates
                lon = float(row[lon_col])
                lat = float(row[lat_col])

                # Capture extra columns (preserve even if NULL)
                extra_cols = {}
                for col in extra_column_names:
                    value = row[col]
                    # Convert numpy types to Python types for JSON serialization
                    if pd.notna(value):
                        if hasattr(value, 'item'):  # numpy types
                            value = value.item()
                        extra_cols[col] = value
                    else:
                        extra_cols[col] = None  # Preserve NULL values

                # Debug first row
                if idx == 0 and extra_cols:
                    print(f"[EXTRA COLUMNS] First row extra columns: {extra_cols}")

                # Get height and class values safely (avoid Series ambiguity)
                height_val = None
                if height_col and height_col in df.columns:
                    try:
                        height_val = row[height_col]
                        # Convert empty strings or NaN to None
                        if pd.isna(height_val) or (isinstance(height_val, str) and str(height_val).strip() == ''):
                            height_val = None
                    except (KeyError, TypeError):
                        height_val = None

                class_val = None
                if class_col and class_col in df.columns:
                    try:
                        class_val = row[class_col]
                        # Convert empty strings or NaN to None
                        if pd.isna(class_val) or (isinstance(class_val, str) and str(class_val).strip() == ''):
                            class_val = None
                    except (KeyError, TypeError):
                        class_val = None

                tree = InventoryTree(
                    inventory_calculation_id=inventory_id,
                    species=species,
                    dia_cm=float(row[diameter_col]),
                    height_m=float(height_val) if pd.notna(height_val) else None,
                    tree_class=class_val if pd.notna(class_val) else None,
                    location=f'SRID=4326;POINT({lon} {lat})',
                    stem_volume=float(row['stem_volume']),
                    branch_volume=float(row['branch_volume']),
                    tree_volume=float(row['tree_volume']),
                    gross_volume=float(row['gross_volume']),
                    net_volume=float(row['net_volume']),
                    net_volume_cft=float(row['net_volume_cft']),
                    firewood_m3=float(row['firewood_m3']),
                    firewood_chatta=float(row['firewood_chatta']),
                    remark=row['remark'],
                    grid_cell_id=int(row['grid_cell_id']) if pd.notna(row['grid_cell_id']) else None,
                    stand_type=row.get('stand_type'),  # NEW: Simple classification
                    dbh_class=row.get('dbh_class'),    # NEW: Detailed classification
                    local_name=local_name,
                    row_number=idx + 2,  # +2 for header and 0-indexing
                    extra_columns=extra_cols if extra_cols else None
                )

                trees_to_insert.append(tree)

                # Insert in batches
                if len(trees_to_insert) >= batch_size:
                    self.db.bulk_save_objects(trees_to_insert)
                    self.db.flush()  # Flush but don't commit yet
                    print(f"Inserted batch of {len(trees_to_insert)} trees")
                    trees_to_insert = []

            # Insert remaining trees
            if trees_to_insert:
                self.db.bulk_save_objects(trees_to_insert)
                self.db.flush()
                print(f"Inserted final batch of {len(trees_to_insert)} trees")

            # Commit all inserts
            self.db.commit()
            print("All trees committed to database")
            if extra_column_names:
                print(f"[EXTRA COLUMNS] Stored {len(extra_column_names)} extra columns: {extra_column_names}")

        except Exception as e:
            print(f"Error storing trees: {e}")
            self.db.rollback()
            raise Exception(f"Failed to store trees in database: {str(e)}")

    def _calculate_summary_statistics_simple(self, df: pd.DataFrame, diameter_col: str) -> Dict[str, Any]:
        """
        Calculate summary statistics (simplified without GeoPandas)

        Args:
            df: DataFrame with processed trees
            diameter_col: Diameter column name

        Returns:
            Summary statistics dict
        """
        total_trees = len(df)
        mother_trees = len(df[df['remark'] == 'Mother Tree'])
        felling_trees = len(df[df['remark'] == 'Felling Tree'])
        seedlings = len(df[df['remark'] == 'Seedling'])
        poles = len(df[df['remark'] == 'Pole'])

        # Sum volumes
        total_volume_m3 = df['tree_volume'].sum()
        total_net_volume_m3 = df['net_volume'].sum()
        total_net_volume_cft = df['net_volume_cft'].sum()
        total_firewood_m3 = df['firewood_m3'].sum()
        total_firewood_chatta = df['firewood_chatta'].sum()

        return {
            'total_trees': total_trees,
            'mother_trees_count': mother_trees,
            'felling_trees_count': felling_trees,
            'seedling_count': seedlings,
            'pole_count': poles,
            'total_volume_m3': round(total_volume_m3, 3),
            'total_net_volume_m3': round(total_net_volume_m3, 3),
            'total_net_volume_cft': round(total_net_volume_cft, 3),
            'total_firewood_m3': round(total_firewood_m3, 3),
            'total_firewood_chatta': round(total_firewood_chatta, 3)
        }

    async def _identify_mother_trees_postgis(
        self,
        inventory_id: UUID,
        grid_spacing_meters: float,
        projection_epsg: int
    ) -> int:
        """
        Identify mother trees using PostGIS (no GDAL/GeoPandas required)

        NEW ALGORITHM (v1.7.0):
        1. Find forest block based on majority of mapped trees falling inside it
        2. Create bounding box from forest block geometry
        3. Create fishnet grid based on user-specified grid size
        4. Join grid_id to trees (DBH > 30cm) based on intersection
        5. If grid has multiple trees, select the one with lowest diameter

        Args:
            inventory_id: UUID of inventory calculation
            grid_spacing_meters: Grid cell size in meters
            projection_epsg: EPSG code for UTM projection (e.g., 32644, 32645)

        Returns:
            Number of mother trees identified
        """
        try:
            # Step 1: Get inventory and find the forest block with majority of trees
            inventory = self.db.query(InventoryCalculation).filter(
                InventoryCalculation.id == inventory_id
            ).first()
            
            if not inventory or not inventory.calculation_id:
                print("No calculation linked to this inventory")
                return 0
            
            # Find which block has the majority of trees
            block_vote_query = text("""
                SELECT fb.id, fb.name, COUNT(t.id) as tree_count
                FROM forest_blocks fb
                JOIN inventory_trees t ON ST_Contains(fb.geometry, t.location::geometry)
                WHERE t.inventory_calculation_id = :inventory_id
                  AND fb.calculation_id = :calc_id
                  AND fb.parent_block_id IS NULL
                GROUP BY fb.id, fb.name
                ORDER BY tree_count DESC
                LIMIT 1
            """)
            block_result = self.db.execute(block_vote_query, {
                "inventory_id": str(inventory_id),
                "calc_id": str(inventory.calculation_id)
            }).first()
            
            if not block_result:
                print("No blocks found for tree assignment - falling back to tree bounds")
                # Fallback: Use bounding box of all trees
                block_id = None
                block_name = "Default Block"
            else:
                block_id = block_result[0]
                block_name = block_result[1]
                print(f"Selected block '{block_name}' with majority trees")
            
            # Step 2: Create bounding box from trees in WGS84
            # Tree locations are already in WGS84 (lat/lon degrees)
            xmin, ymin, xmax, ymax = None, None, None, None
            
            bounds_result = self.db.execute(text("""
                SELECT 
                    ST_XMin(ST_Extent(location::geometry)) AS xmin,
                    ST_YMin(ST_Extent(location::geometry)) AS ymin,
                    ST_XMax(ST_Extent(location::geometry)) AS xmax,
                    ST_YMax(ST_Extent(location::geometry)) AS ymax
                FROM inventory_trees
                WHERE inventory_calculation_id = :inventory_id
            """), {"inventory_id": str(inventory_id)}).first()
            
            if not bounds_result or bounds_result[0] is None:
                print("No trees found for mother tree selection")
                return 0
                
            xmin, ymin, xmax, ymax = bounds_result
            print(f"[BOUNDS] Tree bounds in WGS84: X({xmin:.6f} to {xmax:.6f}), Y({ymin:.6f} to {ymax:.6f})")
            
            # Validate bounds
            if xmax <= xmin or ymax <= ymin:
                raise Exception(f"Invalid tree bounds: X({xmin}, {xmax}), Y({ymin}, {ymax})")
            
            # Get UTM zone from inventory settings
            utm_epsg = projection_epsg  # Already stored: 32644 or 32645
            print(f"[GRID] Using UTM projection: EPSG:{utm_epsg}")
            
            # Transform bounds to UTM for accurate grid generation
            utm_bounds = self.db.execute(text("""
                SELECT 
                    ST_XMin(ST_Extent(ST_Transform(location::geometry, :epsg))) AS xmin_utm,
                    ST_YMin(ST_Extent(ST_Transform(location::geometry, :epsg))) AS ymin_utm,
                    ST_XMax(ST_Extent(ST_Transform(location::geometry, :epsg))) AS xmax_utm,
                    ST_YMax(ST_Extent(ST_Transform(location::geometry, :epsg))) AS ymax_utm
                FROM inventory_trees
                WHERE inventory_calculation_id = :inventory_id
            """), {"inventory_id": str(inventory_id), "epsg": utm_epsg}).first()
            
            if not utm_bounds or utm_bounds[0] is None:
                raise Exception("Failed to transform bounds to UTM")
            
            xmin_utm, ymin_utm, xmax_utm, ymax_utm = utm_bounds
            print(f"[BOUNDS] Tree bounds in UTM: X({xmin_utm:.2f} to {xmax_utm:.2f}), Y({ymin_utm:.2f} to {ymax_utm:.2f})")
            
            # Calculate grid dimensions in UTM (accurate meters)
            width_utm = xmax_utm - xmin_utm
            height_utm = ymax_utm - ymin_utm
            print(f"[BOUNDS] Approximate area in UTM: {width_utm:.1f}m x {height_utm:.1f}m")
            
            # Validate bounds before proceeding
            if xmin is None or ymin is None or xmax is None or ymax is None:
                raise Exception(f"Invalid bounds for grid generation: xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}")
            if xmax <= xmin or ymax <= ymin:
                raise Exception(f"Invalid bounds dimensions: X({xmin}, {xmax}), Y({ymin}, {ymax})")

            # Step 3: Create eligible trees table (DBH > 30 cm) - BEFORE generating grid
            self.db.execute(text("""
                DROP TABLE IF EXISTS temp_eligible_trees;
                CREATE TEMP TABLE temp_eligible_trees AS
                SELECT
                    id,
                    dia_cm,
                    location::geometry AS geom_wgs84
                FROM public.inventory_trees
                WHERE inventory_calculation_id = :inventory_id
                  AND dia_cm > 30
                  AND (remark IS NULL OR remark != 'Seedling');
            """), {
                "inventory_id": str(inventory_id)
            })
            
            # Count eligible trees
            eligible_count = self.db.execute(text("SELECT COUNT(*) FROM temp_eligible_trees")).scalar()
            print(f"Found {eligible_count} eligible trees (DBH > 30cm)")

            # Step 4: Generate fishnet grid - SIMPLIFIED APPROACH
            # Use the same logic as reference: create grid from tree bounds, clip to tree extent
            grid_created = False
            
            # Calculate grid dimensions
            grid_width_m = grid_spacing_meters
            grid_height_m = grid_spacing_meters
            
            print(f"[GRID] Creating grid with spacing: {grid_spacing_meters}m in UTM EPSG:{utm_epsg}")
            print(f"[GRID] Bounds (UTM): X({xmin_utm:.2f} to {xmax_utm:.2f}), Y({ymin_utm:.2f} to {ymax_utm:.2f})")
            
            # Calculate how many cells in each direction using UTM (exact meters)
            num_cols = max(1, int((xmax_utm - xmin_utm) / grid_spacing_meters) + 1)
            num_rows = max(1, int((ymax_utm - ymin_utm) / grid_spacing_meters) + 1)
            total_cells = num_cols * num_rows
            
            print(f"[GRID] Grid dimensions: {num_cols} cols x {num_rows} rows = {total_cells} cells")
            
            # Sanity check - limit grid size to prevent browser/server crashes
            MAX_CELLS = 10000
            
            # If too many cells, adjust grid size
            if total_cells > MAX_CELLS:
                area_utm = (xmax_utm - xmin_utm) * (ymax_utm - ymin_utm)
                new_cell_size = math.sqrt(area_utm / MAX_CELLS)
                grid_spacing_meters = new_cell_size
                num_cols = max(1, int((xmax_utm - xmin_utm) / grid_spacing_meters) + 1)
                num_rows = max(1, int((ymax_utm - ymin_utm) / grid_spacing_meters) + 1)
                total_cells = num_cols * num_rows
                print(f"[GRID] Reduced grid to fit limits: {num_cols}x{num_rows} cells (cell size: {grid_spacing_meters:.2f}m)")
            
            # Create grid in UTM, then transform to WGS84 for storage
            try:
                self.db.execute(text("""
                    DROP TABLE IF EXISTS temp_grid_cells;
                    CREATE TEMP TABLE temp_grid_cells AS
                    SELECT 
                        ROW_NUMBER() OVER () AS cell_id,
                        ST_Transform(
                            ST_SetSRID(
                                ST_MakeEnvelope(
                                    :xmin + (col_idx - 1) * :cell_size,
                                    :ymin + (row_idx - 1) * :cell_size,
                                    :xmin + col_idx * :cell_size,
                                    :ymin + row_idx * :cell_size
                                ),
                                :epsg
                            ),
                            4326
                        ) AS geom
                    FROM generate_series(1, :num_cols) AS col_idx,
                         generate_series(1, :num_rows) AS row_idx;
                """), {
                    "xmin": xmin_utm,
                    "ymin": ymin_utm,
                    "cell_size": grid_spacing_meters,
                    "epsg": utm_epsg,
                    "num_cols": num_cols,
                    "num_rows": num_rows
                })
                
                grid_check = self.db.execute(text("SELECT COUNT(*) FROM temp_grid_cells")).scalar()
                print(f"[GRID] Generated {grid_check} grid cells")
                
                if grid_check and grid_check > 0:
                    grid_created = True
                else:
                    print("[GRID] ERROR: No cells generated")
                    
            except Exception as e:
                print(f"[GRID] Error creating grid: {e}")
                grid_created = False
            
            if not grid_created:
                raise Exception(f"FAILED TO CREATE GRID: Could not generate {num_cols}x{num_rows} grid. Error: bounds may be invalid or too small")
            
            # NOTE: Do NOT commit here! Temp tables persist only within the transaction.
            # Committing would cause temp tables to be lost in some database configurations.
            
            # Save grid cells to persistent table for visualization
            # We need to use a separate transaction - commit grid, then start fresh transaction
            grid_saved = False
            try:
                print(f"[GRID] Saving {grid_check} grid cells to inventory_grid_cells table")
                # This commit will drop temp tables, so we need to recreate them
                self.db.execute(text("""
                    INSERT INTO inventory_grid_cells (id, inventory_calculation_id, cell_id, geom)
                    SELECT gen_random_uuid(), :inv_id, cell_id, geom
                    FROM temp_grid_cells
                    ON CONFLICT (inventory_calculation_id, cell_id) DO UPDATE SET geom = EXCLUDED.geom
                """), {"inv_id": str(inventory_id)})
                self.db.commit()
                print("[GRID] Grid cells saved to database")
                grid_saved = True
                print("[GRID] Temp tables will be recreated due to commit - this is expected")
            except Exception as e:
                print(f"[GRID] Warning: Could not save grid cells: {e}")
                # Don't rollback - just continue without the grid
                try:
                    self.db.rollback()
                except:
                    pass

            # Step 5: Join grid_id to all eligible trees based on intersection
            # Both tree and grid are in WGS84
            # The previous commit() destroyed our temp tables - need to recreate them
            
            # Recreate temp_eligible_trees (destroyed by previous commit)
            print("[RECOVERY] Recreating temp_eligible_trees table after commit")
            try:
                self.db.execute(text("""
                    CREATE TEMP TABLE temp_eligible_trees AS
                    SELECT
                        id,
                        dia_cm,
                        location::geometry AS geom_wgs84
                    FROM public.inventory_trees
                    WHERE inventory_calculation_id = :inventory_id
                      AND dia_cm > 30
                      AND (remark IS NULL OR remark != 'Seedling');
                """), {"inventory_id": str(inventory_id)})
                print("[RECOVERY] temp_eligible_trees recreated successfully")
            except Exception as e:
                print(f"[RECOVERY] Failed to recreate temp_eligible_trees: {e}")
                raise Exception(f"Could not recreate temp_eligible_trees: {e}")

            # Recreate temp_grid_cells (destroyed by previous commit)
            print("[RECOVERY] Recreating temp_grid_cells table after commit")
            try:
                self.db.execute(text("""
                    CREATE TEMP TABLE temp_grid_cells AS
                    SELECT 
                        ROW_NUMBER() OVER () AS cell_id,
                        ST_Transform(
                            ST_SetSRID(
                                ST_MakeEnvelope(
                                    :xmin + (col_idx - 1) * :cell_size,
                                    :ymin + (row_idx - 1) * :cell_size,
                                    :xmin + col_idx * :cell_size,
                                    :ymin + row_idx * :cell_size
                                ),
                                :epsg
                            ),
                            4326
                        ) AS geom
                    FROM generate_series(1, :num_cols) AS col_idx,
                         generate_series(1, :num_rows) AS row_idx;
                """), {
                    "xmin": xmin_utm,
                    "ymin": ymin_utm,
                    "cell_size": grid_spacing_meters,
                    "epsg": utm_epsg,
                    "num_cols": num_cols,
                    "num_rows": num_rows
                })
                print("[RECOVERY] temp_grid_cells recreated successfully")
            except Exception as e:
                print(f"[RECOVERY] Failed to recreate temp_grid_cells: {e}")
                raise Exception(f"Could not recreate temp_grid_cells: {e}")

            # Step 5: Join grid_id to all eligible trees based on intersection
            self.db.execute(text("""
                ALTER TABLE temp_eligible_trees ADD COLUMN IF NOT EXISTS grid_cell_id INTEGER;
                
                UPDATE temp_eligible_trees t
                SET grid_cell_id = g.cell_id
                FROM temp_grid_cells g
                WHERE ST_Intersects(g.geom, t.geom_wgs84);
            """))
            
            trees_with_grid = self.db.execute(text("SELECT COUNT(*) FROM temp_eligible_trees WHERE grid_cell_id IS NOT NULL")).scalar()
            print(f"[JOIN] Joined {trees_with_grid} trees to grid cells")

            # Step 6: For each grid cell, select the tree with LOWEST diameter (DBH)
            # This is the new algorithm: lower diameter = mother tree
            self.db.execute(text("""
                DROP TABLE IF EXISTS temp_mother_trees;
                CREATE TEMP TABLE temp_mother_trees AS
                SELECT DISTINCT ON (grid_cell_id)
                    grid_cell_id,
                    id AS tree_id,
                    dia_cm
                FROM temp_eligible_trees
                WHERE grid_cell_id IS NOT NULL
                ORDER BY grid_cell_id, dia_cm ASC;  -- LOWEST diameter first
            """))
            
            mother_candidates = self.db.execute(text("SELECT COUNT(*) FROM temp_mother_trees")).scalar()
            print(f"Found {mother_candidates} grid cells with trees (candidates for mother trees)")

            # Step 7: Update inventory_trees to mark mother trees
            self.db.execute(text("""
                UPDATE public.inventory_trees
                SET
                    remark = 'Mother Tree',
                    grid_cell_id = mt.grid_cell_id
                FROM temp_mother_trees mt
                WHERE inventory_trees.id = mt.tree_id;
            """))
            
            # Step 7b: Mark other trees in grid (>=30cm DBH that are not mother trees) as Felling Trees
            # These are trees in the same grid but with larger diameter
            self.db.execute(text("""
                UPDATE public.inventory_trees
                SET remark = 'Felling Tree'
                WHERE inventory_calculation_id = :inventory_id
                  AND remark != 'Mother Tree'
                  AND remark != 'Seedling'
                  AND remark != 'Pole'
                  AND grid_cell_id IS NOT NULL
            """), {"inventory_id": str(inventory_id)})
            
            # Step 8: Store grid metadata for frontend display
            # First verify the grid table still exists
            grid_bounds = None
            try:
                grid_check = self.db.execute(text("SELECT COUNT(*) FROM temp_grid_cells")).scalar()
                print(f"[GRID_META] Grid table exists with {grid_check} cells")
                if not grid_check or grid_check == 0:
                    print("[GRID_META] Warning - grid table empty, skipping metadata storage")
                else:
                    grid_bounds = self.db.execute(text("""
                        SELECT 
                            ST_XMin(ST_Extent(geom)) AS xmin,
                            ST_YMin(ST_Extent(geom)) AS ymin,
                            ST_XMax(ST_Extent(geom)) AS xmax,
                            ST_YMax(ST_Extent(geom)) AS ymax
                        FROM temp_grid_cells
                    """)).first()
            except Exception as e:
                print(f"[GRID_META] Error accessing grid table: {e}")
                # Rollback to recover from any transaction errors
                try:
                    self.db.rollback()
                except:
                    pass
                grid_bounds = None

            if grid_bounds and grid_bounds[0] is not None:
                gxmin, gymin, gxmax, gymax = grid_bounds
                
                # Convert bounds to UTM to calculate proper grid dimensions
                grid_bounds_utm = self.db.execute(text("""
                    SELECT 
                        ST_XMin(ST_Extent(ST_Transform(geom, :epsg))) AS xmin_utm,
                        ST_YMin(ST_Extent(ST_Transform(geom, :epsg))) AS ymin_utm,
                        ST_XMax(ST_Extent(ST_Transform(geom, :epsg))) AS xmax_utm,
                        ST_YMax(ST_Extent(ST_Transform(geom, :epsg))) AS ymax_utm
                    FROM temp_grid_cells
                """), {"epsg": utm_epsg}).first()
                
                if grid_bounds_utm and grid_bounds_utm[0] is not None:
                    xmin_u, ymin_u, xmax_u, ymax_u = grid_bounds_utm
                    num_cols = int(round((xmax_u - xmin_u) / grid_spacing_meters)) + 1
                    num_rows = int(round((ymax_u - ymin_u) / grid_spacing_meters)) + 1
                    print(f"[GRID_META] Grid in UTM: {xmin_u:.2f}x{ymin_u:.2f} to {xmax_u:.2f}x{ymax_u:.2f}, cols={num_cols}, rows={num_rows}")
                else:
                    num_cols = int(round((gxmax - gxmin) / grid_spacing_meters)) + 1
                    num_rows = int(round((gymax - gymin) / grid_spacing_meters)) + 1
                
                # Store WGS84 bounds for frontend display
                self.db.execute(text("""
                    UPDATE public.inventory_calculations
                    SET grid_origin_x = :gxmin,
                        grid_origin_y = :gymin,
                        grid_num_cols = :num_cols,
                        grid_num_rows = :num_rows
                    WHERE id = :inv_calc_id
                """), {
                    "gxmin": gxmin,
                    "gymin": gymin,
                    "num_cols": num_cols,
                    "num_rows": num_rows,
                    "inv_calc_id": str(inventory_id)
                })
                print(f"Stored grid metadata: origin=({gxmin:.2f}, {gymin:.2f}), cols={num_cols}, rows={num_rows}")

            # Step 9: Get count of mother trees
            # We already committed the grid save, so just query now
            try:
                mother_tree_count = self.db.execute(text("""
                    SELECT COUNT(*)
                    FROM public.inventory_trees
                    WHERE inventory_calculation_id = :inventory_id
                      AND remark = 'Mother Tree'
                """), {"inventory_id": str(inventory_id)}).scalar()
            except Exception as e:
                print(f"[MOTHER] Error counting mother trees: {e}")
                try:
                    self.db.rollback()
                except:
                    pass
                mother_tree_count = 0

            # Clean up temp tables (they should already be gone due to earlier commit)
            try:
                self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees, temp_grid_cells, temp_mother_trees"))
                self.db.commit()
            except:
                try:
                    self.db.rollback()
                except:
                    pass

            return mother_tree_count

        except Exception as e:
            print(f"Error in mother tree identification: {str(e)}")
            # Rollback and try to recover transaction
            try:
                self.db.rollback()
            except:
                pass
            try:
                self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees, temp_grid_cells, temp_mother_trees"))
                self.db.commit()
            except:
                pass
            raise Exception(f"Mother tree identification failed: {str(e)}")

    async def _calculate_summary_from_db(self, inventory_id: UUID) -> Dict[str, Any]:
        """
        Calculate summary statistics from database

        Args:
            inventory_id: UUID of inventory calculation

        Returns:
            Summary statistics dict (all values converted to native Python types)
        """
        summary_query = text("""
            SELECT
                COUNT(*) AS total_trees,
                COUNT(*) FILTER (WHERE remark = 'Mother Tree') AS mother_trees,
                COUNT(*) FILTER (WHERE remark = 'Felling Tree') AS felling_trees,
                COUNT(*) FILTER (WHERE remark = 'Pole') AS poles,
                COUNT(*) FILTER (WHERE remark = 'Seedling') AS seedlings,
                COALESCE(SUM(tree_volume), 0) AS total_volume_m3,
                COALESCE(SUM(net_volume), 0) AS total_net_volume_m3,
                COALESCE(SUM(net_volume_cft), 0) AS total_net_volume_cft,
                COALESCE(SUM(firewood_m3), 0) AS total_firewood_m3,
                COALESCE(SUM(firewood_chatta), 0) AS total_firewood_chatta,
                -- Stand type counts
                COUNT(*) FILTER (WHERE stand_type = 'Regeneration') AS regeneration_count,
                COUNT(*) FILTER (WHERE stand_type = 'Sapling') AS sapling_count,
                COUNT(*) FILTER (WHERE stand_type = 'Pole') AS stand_pole_count,
                COUNT(*) FILTER (WHERE stand_type = 'Tree') AS tree_count,
                -- Volume by tree category
                COALESCE(SUM(tree_volume) FILTER (WHERE remark = 'Felling Tree'), 0) AS felling_volume_m3,
                COALESCE(SUM(tree_volume) FILTER (WHERE remark = 'Mother Tree'), 0) AS mother_volume_m3,
                COALESCE(SUM(tree_volume) FILTER (WHERE remark = 'Pole'), 0) AS pole_volume_m3,
                -- Net timber volume (trees that can be used for timber)
                COALESCE(SUM(net_volume) FILTER (WHERE remark IN ('Felling Tree', 'Mother Tree')), 0) AS timber_volume_m3,
                COALESCE(SUM(net_volume_cft) FILTER (WHERE remark IN ('Felling Tree', 'Mother Tree')), 0) AS timber_volume_cft
            FROM public.inventory_trees
            WHERE inventory_calculation_id = :inventory_id
        """)

        result = self.db.execute(summary_query, {"inventory_id": str(inventory_id)}).first()

        # Convert all values to native Python types (avoid numpy types)
        return {
            'total_trees': int(result[0]) if result[0] is not None else 0,
            'mother_trees_count': int(result[1]) if result[1] is not None else 0,
            'felling_trees_count': int(result[2]) if result[2] is not None else 0,
            'pole_count': int(result[3]) if result[3] is not None else 0,
            'seedling_count': int(result[4]) if result[4] is not None else 0,
            'total_volume_m3': round(float(result[5]), 3) if result[5] is not None else 0.0,
            'total_net_volume_m3': round(float(result[6]), 3) if result[6] is not None else 0.0,
            'total_net_volume_cft': round(float(result[7]), 3) if result[7] is not None else 0.0,
            'total_firewood_m3': round(float(result[8]), 3) if result[8] is not None else 0.0,
            'total_firewood_chatta': round(float(result[9]), 3) if result[9] is not None else 0.0,
            # Stand type counts
            'regeneration_count': int(result[10]) if result[10] is not None else 0,
            'sapling_count': int(result[11]) if result[11] is not None else 0,
            'stand_pole_count': int(result[12]) if result[12] is not None else 0,
            'tree_count': int(result[13]) if result[13] is not None else 0,
            # Volumes by category
            'felling_volume_m3': round(float(result[14]), 3) if result[14] is not None else 0.0,
            'mother_volume_m3': round(float(result[15]), 3) if result[15] is not None else 0.0,
            'pole_volume_m3': round(float(result[16]), 3) if result[16] is not None else 0.0,
            # Timber volume
            'timber_volume_m3': round(float(result[17]), 3) if result[17] is not None else 0.0,
            'timber_volume_cft': round(float(result[18]), 3) if result[18] is not None else 0.0
        }

    async def export_inventory(
        self,
        inventory_id: UUID,
        export_format: str
    ) -> Tuple[bytes, str]:
        """
        Export inventory results

        Args:
            inventory_id: UUID of inventory calculation
            export_format: 'csv', 'shapefile', or 'geojson'

        Returns:
            Tuple of (file_content, filename)
        """
        # Clear any pending transaction state
        self.db.rollback()
        
        # Get trees from database
        trees = self.db.query(InventoryTree).filter(
            InventoryTree.inventory_calculation_id == inventory_id
        ).all()

        if not trees:
            raise ValueError("No trees found for this inventory")

        # Get tree IDs for batch coordinate query
        tree_ids = [tree.id for tree in trees]
        
        # Batch query all coordinates at once
        tree_coords = {}
        try:
            coords_result = self.db.execute(
                text("""
                    SELECT id, ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat 
                    FROM public.inventory_trees 
                    WHERE id = ANY(:ids)
                """),
                {"ids": tree_ids}
            ).fetchall()
            tree_coords = {row[0]: (row[1], row[2]) for row in coords_result}
        except Exception as e:
            print(f"[EXPORT] Failed to batch get coordinates: {e}")
            tree_coords = {}

        # Get inventory to find calculation_id
        inventory = self.db.query(InventoryCalculation).filter(
            InventoryCalculation.id == inventory_id
        ).first()

        # Get compartments and build lookup using a single efficient query
        # Get all child blocks under this calculation (compartments)
        comp_lookup = {}
        if inventory and inventory.calculation_id:
            from ..models.forest_block import ForestBlock
            # Get all child blocks under the calculation's blocks
            comps = self.db.execute(
                text("""
                    SELECT fb.id, COALESCE(fb.compartment_code, fb.name) as comp_name
                    FROM forest_blocks fb
                    WHERE fb.parent_block_id IN (
                        SELECT id FROM forest_blocks WHERE calculation_id = :calc_id
                    )
                """),
                {"calc_id": inventory.calculation_id}
            ).fetchall()
            
            for comp in comps:
                comp_lookup[comp[0]] = comp[1]

        # Create DataFrame
        data = []
        extra_cols_found = 0
        
        # If we have compartments, do a spatial join for all trees at once
        tree_comp_map = {}
        if comp_lookup and inventory and inventory.calculation_id:
            try:
                # Query to find which compartment each tree belongs to
                # Cast location from geography to geometry for ST_Contains
                query = text("""
                    SELECT t.id as tree_id, fb.id as comp_id, COALESCE(fb.compartment_code, fb.name) as comp_name
                    FROM inventory_trees t
                    JOIN forest_blocks fb ON ST_Contains(fb.geometry, t.location::geometry)
                    WHERE fb.parent_block_id IN (
                        SELECT id FROM forest_blocks WHERE calculation_id = :calc_id
                    )
                    AND t.inventory_calculation_id = :inv_id
                """)
                print(f"[EXPORT] Running spatial join query with calc_id={inventory.calculation_id}, inv_id={inventory_id}")
                tree_compartments = self.db.execute(query, {"calc_id": inventory.calculation_id, "inv_id": inventory_id}).fetchall()
                print(f"[EXPORT] Spatial join returned {len(tree_compartments)} results")
                
                # Build tree -> compartment mapping
                tree_comp_map = {row[0]: {'id': row[1], 'name': row[2]} for row in tree_compartments}
                print(f"[EXPORT] Built tree_comp_map with {len(tree_comp_map)} entries")
            except Exception as e:
                import traceback
                print(f"[EXPORT] Spatial join failed: {e}")
                print(f"[EXPORT] Traceback: {traceback.format_exc()}")
                tree_comp_map = {}
                self.db.rollback()  # Reset transaction state after error
        
        for tree in trees:
            # Get coordinates from batch result
            lon, lat = tree_coords.get(tree.id, (None, None))

            # Get compartment from mapping
            comp_info = tree_comp_map.get(tree.id, {})
            comp_id = str(comp_info.get('id')) if comp_info.get('id') else None
            comp_name = comp_info.get('name')

            row_data = {
                'species': tree.species,
                'local_name': tree.local_name,
                'dia_cm': tree.dia_cm,
                'height_m': tree.height_m,
                'tree_class': tree.tree_class,
                'stand_type': tree.stand_type,
                'dbh_class': tree.dbh_class,
                'longitude': lon,
                'latitude': lat,
                'stem_volume': tree.stem_volume,
                'branch_volume': tree.branch_volume,
                'tree_volume': tree.tree_volume,
                'gross_volume': tree.gross_volume,
                'net_volume': tree.net_volume,
                'net_volume_cft': tree.net_volume_cft,
                'firewood_m3': tree.firewood_m3,
                'firewood_chatta': tree.firewood_chatta,
                'remark': tree.remark,
                'grid_cell_id': tree.grid_cell_id,
                'compartment_id': comp_id or (str(tree.compartment_id) if tree.compartment_id else None),
                'compartment_name': comp_name or (tree.compartment.name if tree.compartment_id and tree.compartment else None)
            }

            # Add extra columns if they exist
            if tree.extra_columns:
                row_data.update(tree.extra_columns)
                extra_cols_found += 1
                if extra_cols_found == 1:
                    print(f"[EXPORT] First tree with extra columns: {tree.extra_columns}")

            data.append(row_data)

        if extra_cols_found > 0:
            print(f"[EXPORT] Found {extra_cols_found} trees with extra columns")
        else:
            print(f"[EXPORT] No trees with extra columns found")

        df = pd.DataFrame(data)
        print(f"[EXPORT] DataFrame columns: {list(df.columns)}")

        # Get forest name for filename
        forest_name = 'inventory'
        try:
            if inventory and inventory.calculation:
                forest_name = inventory.calculation.forest_name or inventory.calculation.block_name or 'inventory'
            elif inventory and inventory.calculation_id:
                # Fetch calculation separately if relationship not loaded
                from ..models.calculation import Calculation
                calc = self.db.query(Calculation).filter(Calculation.id == inventory.calculation_id).first()
                if calc:
                    forest_name = calc.forest_name or calc.block_name or 'inventory'
        except Exception as e:
            print(f"[EXPORT] Error getting forest name: {e}")
            forest_name = 'inventory'
        
        # Clean up forest name for filename - use ASCII-safe transliteration
        import re
        import unicodedata
        
        # Normalize unicode and convert to ASCII
        forest_name_normalized = unicodedata.normalize('NFKD', str(forest_name))
        forest_name_ascii = forest_name_normalized.encode('ascii', 'ignore').decode('ascii')
        forest_name = re.sub(r'[^\w_-]', '', forest_name_ascii)  # Keep only word chars, underscores, hyphens
        forest_name = re.sub(r'\s+', '_', forest_name)  # Replace spaces with underscores
        forest_name = forest_name.strip('_')
        
        # Fallback if empty
        if not forest_name:
            forest_name = 'inventory'
        
        # Add date to filename
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        
        filename_base = f"{forest_name}_Tree_Mapping_Summary_{date_str}"

        if export_format == 'csv':
            csv_content = df.to_csv(index=False)
            # Ensure UTF-8 encoding
            return csv_content.encode('utf-8'), f'{filename_base}.csv'

        elif export_format == 'excel':
            # Create Excel file with pandas
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main tree data sheet
                df.to_excel(writer, sheet_name='Tree Data', index=False)
                
                # Summary by compartment and remark
                summary_data = []
                for (comp_name, remark), group in df.groupby(['compartment_name', 'remark']):
                    summary_data.append({
                        'compartment_name': comp_name,
                        'remark': remark,
                        'tree_count': len(group),
                        'net_volume_m3': group['net_volume'].sum(),
                        'net_volume_cft': group['net_volume_cft'].sum(),
                        'firewood_m3': group['firewood_m3'].sum(),
                        'firewood_chatta': group['firewood_chatta'].sum()
                    })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Species distribution
                species_data = df.groupby('species').agg({
                    'compartment_name': 'count',
                    'net_volume': 'sum'
                }).reset_index()
                species_data.columns = ['species', 'count', 'total_volume_m3']
                species_data.to_excel(writer, sheet_name='Species', index=False)
            
            output.seek(0)
            return output.getvalue(), f'{filename_base}.xlsx'

        elif export_format == 'geojson':
            # Create GeoJSON manually without GeoPandas
            import json

            features = []
            for _, row in df.iterrows():
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row['longitude'], row['latitude']]
                    },
                    "properties": {
                        'species': row['species'],
                        'local_name': row['local_name'],
                        'dia_cm': float(row['dia_cm']) if pd.notna(row['dia_cm']) else None,
                        'height_m': float(row['height_m']) if pd.notna(row['height_m']) else None,
                        'tree_class': row['tree_class'],
                        'stand_type': row['stand_type'],      # NEW: Simple classification
                        'dbh_class': row['dbh_class'],        # NEW: Detailed classification
                        'stem_volume': float(row['stem_volume']) if pd.notna(row['stem_volume']) else None,
                        'branch_volume': float(row['branch_volume']) if pd.notna(row['branch_volume']) else None,
                        'tree_volume': float(row['tree_volume']) if pd.notna(row['tree_volume']) else None,
                        'gross_volume': float(row['gross_volume']) if pd.notna(row['gross_volume']) else None,
                        'net_volume': float(row['net_volume']) if pd.notna(row['net_volume']) else None,
                        'net_volume_cft': float(row['net_volume_cft']) if pd.notna(row['net_volume_cft']) else None,
                        'firewood_m3': float(row['firewood_m3']) if pd.notna(row['firewood_m3']) else None,
                        'firewood_chatta': float(row['firewood_chatta']) if pd.notna(row['firewood_chatta']) else None,
                        'remark': row['remark'],
                        'grid_cell_id': int(row['grid_cell_id']) if pd.notna(row['grid_cell_id']) else None,
                        'compartment_id': row['compartment_id'],
                        'compartment_name': row['compartment_name']
                    }
                }
                features.append(feature)

            geojson = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": "EPSG:4326"}
                },
                "features": features
            }

            geojson_content = json.dumps(geojson, indent=2)
            return geojson_content.encode('utf-8'), f'{filename_base}.geojson'

        elif export_format == 'shapefile':
            # For shapefile, would need to create zip with .shp, .shx, .dbf, .prj
            # This requires additional implementation
            raise NotImplementedError("Shapefile export not yet implemented")

        else:
            raise ValueError(f"Unsupported export format: {export_format}")
