"""
Inventory service - Tree volume calculations and mother tree selection
Based on allometric equations for Nepal tree species
"""
import pandas as pd
# import geopandas as gpd  # Temporarily disabled - requires GDAL
# from shapely.geometry import Point, Polygon, box  # Temporarily disabled
# from shapely.ops import nearest_points  # Temporarily disabled
# import pyproj  # Temporarily disabled
from typing import Dict, Any, Tuple, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
from datetime import datetime

from ..models.inventory import (
    InventoryCalculation,
    InventoryTree,
    TreeSpeciesCoefficient
)
from ..utils.diameter_classifier import DiameterClassifier
from .volume_calculator import calculate_tree_volumes as shared_calculate_volumes


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

        except Exception as e:
            # Delete entire inventory (and all trees via cascade) to prevent
            # orphaned data when processing fails partway through.
            inventory_id_for_cleanup = inventory.id
            try:
                self.db.delete(inventory)
                self.db.commit()
                print(f"[INVENTORY] Cleaned up failed inventory {inventory_id_for_cleanup}: {e}")
            except Exception as cleanup_err:
                print(f"[INVENTORY] Warning: cleanup failed for {inventory_id_for_cleanup}: {cleanup_err}")
                self.db.rollback()
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

        # Ensure species column can hold strings (not int64 from numeric codes)
        if df[species_col].dtype in ('int64', 'float64', 'Int64', 'Int32', 'int32'):
            df[species_col] = df[species_col].astype(str)

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
                print(f"[SPECIES] Row {idx+1}: '{original_species}' → '{scientific_name}' (method: {method})")

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

        # Normalize tree class to int (1-4) for the shared calculator
        _class_to_int = {'a': 1, 'b': 2, 'c': 3, 'd': 4}

        for idx, row in df.iterrows():
            species = row[species_col]
            dbh_cm = row[diameter_col]

            if dbh_cm < 10:
                continue

            if species not in self.species_coefficients:
                continue

            coef = self.species_coefficients[species]

            # Get or estimate height
            height_val = None
            if height_col and height_col in df.columns:
                height_val = row[height_col]
            height_m = float(height_val) if (height_val and pd.notna(height_val)) else dbh_cm * 0.8

            # Normalize tree class to int (1-4)
            class_val = None
            if class_col is not None and class_col in df.columns:
                try:
                    class_val = row[class_col]
                    if pd.isna(class_val) or (isinstance(class_val, str) and str(class_val).strip() == ''):
                        class_val = None
                except (KeyError, TypeError):
                    class_val = None

            if class_val is not None:
                tc_raw = str(class_val).strip()
                try:
                    tc_num = str(int(float(tc_raw)))
                    tc_letter = {'1': 'a', '2': 'b', '3': 'c', '4': 'd'}.get(tc_num, 'b')
                except (ValueError, TypeError):
                    tc_lower = tc_raw.lower()
                    tc_letter = {'i': 'a', 'ii': 'b', 'iii': 'c', 'iv': 'd',
                                 'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd'}.get(tc_lower, 'b')
            else:
                tc_letter = 'b'

            tree_class_int = _class_to_int.get(tc_letter, 2)

            # Call the shared volume calculator (single source of truth)
            volumes = shared_calculate_volumes(dbh_cm, height_m, tree_class_int, coef)

            # Additional conversions (cft, chatta)
            net_volume_cft = volumes['net_volume'] * 35.3147
            firewood_chatta = volumes['firewood_m3'] / 0.267

            df.at[idx, 'stem_volume'] = volumes['stem_volume']
            df.at[idx, 'branch_volume'] = volumes['branch_volume']
            df.at[idx, 'tree_volume'] = volumes['tree_volume']
            df.at[idx, 'gross_volume'] = volumes['gross_volume']
            df.at[idx, 'net_volume'] = volumes['net_volume']
            df.at[idx, 'net_volume_cft'] = net_volume_cft
            df.at[idx, 'firewood_m3'] = volumes['firewood_m3']
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
        # Initialize remark column
        trees_gdf['remark'] = 'Felling Tree'
        trees_gdf['grid_cell_id'] = None

        # Filter out seedlings (DBH < 10 cm) - they cannot be mother trees
        eligible_trees = trees_gdf[trees_gdf['dia_cm'] >= 10].copy()

        if len(eligible_trees) == 0:
            # All trees are seedlings
            trees_gdf.loc[trees_gdf['dia_cm'] < 10, 'remark'] = 'Seedling'
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

        # Mark mother trees
        trees_gdf.loc[mother_tree_indices, 'remark'] = 'Mother Tree'

        # Mark seedlings
        trees_gdf.loc[trees_gdf['dia_cm'] < 10, 'remark'] = 'Seedling'

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

            # Deduplicate columns — after lowercasing, two columns like "LATITUDE" and "latitude"
            # become identical, and df[col] returns a DataFrame/Series instead of a scalar.
            if df.columns.duplicated().any():
                dups = df.columns[df.columns.duplicated()].unique().tolist()
                print(f"[INVENTORY] Removing duplicate columns after lowercasing: {dups}")
                df = df.loc[:, ~df.columns.duplicated(keep='first')]

            print(f"[INVENTORY] Available columns: {list(df.columns)}")

            # Map possible column names
            # Prefer exact standard column names (from mapping) before substring matching
            # to avoid false positives like 'lat' in 'species_regulation'
            species_col = 'species' if 'species' in df.columns else next((col for col in df.columns if 'species' in col or 'scientific' in col), 'species')
            diameter_col = 'dia_cm' if 'dia_cm' in df.columns else next((col for col in df.columns if 'dia' in col or 'dbh' in col), 'dia_cm')
            height_col = 'height_m' if 'height_m' in df.columns else next((col for col in df.columns if 'height' in col and 'species' not in col and 'scientific' not in col), 'height_m')
            class_col = 'class' if 'class' in df.columns else next((col for col in df.columns if 'class' in col or 'quality' in col), 'class')
            lon_col = 'longitude' if 'longitude' in df.columns else next((col for col in df.columns if ('lon' in col or col == 'x') and 'species' not in col and 'scientific' not in col), 'longitude')
            lat_col = 'latitude' if 'latitude' in df.columns else next((col for col in df.columns if ('lat' in col or col == 'y') and 'species' not in col and 'scientific' not in col), 'latitude')

            print(f"[INVENTORY] Column mapping: species={species_col}, dia={diameter_col}, height={height_col}, class={class_col}, lon={lon_col}, lat={lat_col}")

            # DIAGNOSTIC: First-row values BEFORE species conversion
            if len(df) > 0:
                first = df.iloc[0]
                print(f"[DIAG_BEFORE] species({species_col})={repr(first.get(species_col, 'N/A'))}")
                print(f"[DIAG_BEFORE] dia({diameter_col})={repr(first.get(diameter_col, 'N/A'))}")
                print(f"[DIAG_BEFORE] height({height_col})={repr(first.get(height_col, 'N/A'))}")
                print(f"[DIAG_BEFORE] lon({lon_col})={repr(first.get(lon_col, 'N/A'))}")
                print(f"[DIAG_BEFORE] lat({lat_col})={repr(first.get(lat_col, 'N/A'))}")

            # 1. Convert species codes and local names to scientific names
            print(f"[INVENTORY] Step 1/5: Converting species codes to scientific names...")
            df = await self._convert_species_to_scientific(df, species_col, inventory.calculation_id)
            print(f"[INVENTORY] Step 1/5: Species conversion completed")

            # DIAGNOSTIC: First-row values AFTER species conversion
            if len(df) > 0:
                first = df.iloc[0]
                print(f"[DIAG_AFTER] species({species_col})={repr(first.get(species_col, 'N/A'))}")
                print(f"[DIAG_AFTER] dia({diameter_col})={repr(first.get(diameter_col, 'N/A'))}")
                print(f"[DIAG_AFTER] height({height_col})={repr(first.get(height_col, 'N/A'))}")
                print(f"[DIAG_AFTER] lon({lon_col})={repr(first.get(lon_col, 'N/A'))}")
                print(f"[DIAG_AFTER] lat({lat_col})={repr(first.get(lat_col, 'N/A'))}")

            # 2. Calculate volumes for all trees
            print(f"[INVENTORY] Step 2/6: Calculating volumes...")
            df = self.calculate_tree_volumes(df, species_col, diameter_col, height_col, class_col)
            print(f"[INVENTORY] Step 2/6: Volumes calculated successfully")

            # 3. Initially mark all trees
            print(f"[INVENTORY] Step 3/7: Marking seedlings vs felling trees...")
            df['remark'] = df.apply(
                lambda row: 'Seedling' if row[diameter_col] < 10 else 'Felling Tree',
                axis=1
            )
            df['grid_cell_id'] = None
            print(f"[INVENTORY] Step 3/7: Marked {len(df[df['remark'] == 'Seedling'])} seedlings, {len(df[df['remark'] == 'Felling Tree'])} felling trees")

            # 4. Add diameter classification (stand_type and dbh_class)
            print(f"[INVENTORY] Step 4/7: Classifying trees by diameter...")
            df['stand_type'] = df[diameter_col].apply(DiameterClassifier.classify_simple)
            df['dbh_class'] = df[diameter_col].apply(DiameterClassifier.classify_detailed)

            # Count trees by classification
            stand_type_counts = df['stand_type'].value_counts().to_dict()
            print(f"[INVENTORY] Step 4/7: Classified trees - Regeneration: {stand_type_counts.get('Regeneration', 0)}, Pole: {stand_type_counts.get('Pole', 0)}, Tree: {stand_type_counts.get('Tree', 0)}")

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

            # DIAGNOSTIC: Print first row values for critical columns
            if len(df) > 0:
                first = df.iloc[0]
                print(f"[DIAG] species_col={species_col}, diameter_col={diameter_col}, height_col={height_col}")
                print(f"[DIAG] lon_col={lon_col}, lat_col={lat_col}")
                for c in [species_col, diameter_col, height_col, lon_col, lat_col]:
                    if c in df.columns:
                        print(f"[DIAG] {c}: value={repr(first[c])}, type={type(first[c]).__name__}, dtype={df[c].dtype}")
                # Check for string values in numeric columns
                for c in [diameter_col, height_col, lon_col, lat_col]:
                    if c in df.columns and df[c].dtype == object:
                        non_numeric = df[pd.to_numeric(df[c], errors='coerce').isna()][c].dropna().unique()[:5]
                        if len(non_numeric) > 0:
                            print(f"[DIAG] WARNING: column '{c}' has non-numeric values: {list(non_numeric)}")

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

            # 8. Resolve spatial relationships (block, sub-area, compartment hierarchy)
            print(f"[INVENTORY] Step 8/8: Resolving spatial relationships...")
            if inventory.calculation_id:
                spatial_count = await self._update_tree_spatial_relationships(
                    inventory_id,
                    inventory.calculation_id
                )
                print(f"[INVENTORY] Step 8/8: Updated {spatial_count} spatial relationships")
            else:
                print(f"[INVENTORY] Step 8/8: Skipped - no calculation_id")

            # 9. Calculate summary statistics from database
            print(f"[INVENTORY] Step 9/9: Calculating summary statistics...")
            summary = await self._calculate_summary_from_db(inventory_id)
            print(f"[INVENTORY] Step 7/7: Summary calculated")

            # 6. Update inventory record (convert numpy types to Python types)
            inventory.total_trees = int(summary['total_trees'])
            inventory.mother_trees_count = int(summary['mother_trees_count'])
            inventory.felling_trees_count = int(summary['felling_trees_count'])
            inventory.seedling_count = int(summary['seedling_count'])
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

        except Exception as e:
            # Delete entire inventory (and all trees via cascade) to prevent
            # orphaned data when processing fails partway through.
            inventory_id_for_cleanup = inventory.id
            try:
                self.db.delete(inventory)
                self.db.commit()
                print(f"[INVENTORY] Cleaned up failed inventory {inventory_id_for_cleanup}: {e}")
            except Exception as cleanup_err:
                print(f"[INVENTORY] Warning: cleanup failed for {inventory_id_for_cleanup}: {cleanup_err}")
                self.db.rollback()
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
                # Diagnostic: print first-row values for critical columns
                if idx == 0:
                    print(f"[STORE] First row — cols: species={species_col}, dia={diameter_col}, height={height_col}, class={class_col}, lon={lon_col}, lat={lat_col}")
                    for c in [species_col, diameter_col, height_col, class_col, lon_col, lat_col]:
                        if c in df.columns:
                            print(f"[STORE] First row — {c} = {repr(row[c])} (type={type(row[c]).__name__})")
                    print(f"[STORE] First row — stem_volume={row.get('stem_volume', 'MISSING')}")

                # Get species and local name
                species = row[species_col]
                local_name = row.get('local_name', None) if 'local_name' in df.columns else None

                # Get coordinates with diagnostic on failure
                def _safe_float(val, col_name):
                    try:
                        return float(val)
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Cannot convert column '{col_name}' to float: value={repr(val)}, error={e}")

                lon = _safe_float(row[lon_col], lon_col)
                lat = _safe_float(row[lat_col], lat_col)

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

                # Resolve block_name from polygon_boundary column if available
                tree_block_name = row.get('polygon_boundary', None)
                if isinstance(tree_block_name, float) and pd.isna(tree_block_name):
                    tree_block_name = None
                elif tree_block_name is not None:
                    tree_block_name = str(tree_block_name)

                tree = InventoryTree(
                    inventory_calculation_id=inventory_id,
                    species=species,
                    dia_cm=_safe_float(row[diameter_col], diameter_col),
                    height_m=_safe_float(height_val, 'height_m') if pd.notna(height_val) else None,
                    tree_class={'1': 'a', '2': 'b', '3': 'c', '4': 'd'}.get(str(int(float(class_val))).strip()) if pd.notna(class_val) else None,
                    location=f'SRID=4326;POINT({lon} {lat})',
                    stem_volume=_safe_float(row['stem_volume'], 'stem_volume'),
                    branch_volume=_safe_float(row['branch_volume'], 'branch_volume'),
                    tree_volume=_safe_float(row['tree_volume'], 'tree_volume'),
                    gross_volume=_safe_float(row['gross_volume'], 'gross_volume'),
                    net_volume=_safe_float(row['net_volume'], 'net_volume'),
                    net_volume_cft=_safe_float(row['net_volume_cft'], 'net_volume_cft'),
                    firewood_m3=_safe_float(row['firewood_m3'], 'firewood_m3'),
                    firewood_chatta=_safe_float(row['firewood_chatta'], 'firewood_chatta'),
                    remark=row['remark'],
                    grid_cell_id=int(row['grid_cell_id']) if pd.notna(row['grid_cell_id']) else None,
                    stand_type=row.get('stand_type'),
                    dbh_class=row.get('dbh_class'),
                    local_name=local_name,
                    block_name=tree_block_name,
                    row_number=idx + 2,
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

        Uses grid-based selection algorithm:
        1. Create spatial grid over tree area
        2. Find centroid of each grid cell
        3. Select tree nearest to each centroid as mother tree

        Args:
            inventory_id: UUID of inventory calculation
            grid_spacing_meters: Grid cell size in meters
            projection_epsg: EPSG code for UTM projection (e.g., 32644, 32645)

        Returns:
            Number of mother trees identified
        """
        try:
            # Step 1: Create temporary table with eligible trees (DBH > 30 cm)
            # and transform to projected CRS
            self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees"))
            self.db.execute(text("""
                CREATE TEMP TABLE temp_eligible_trees AS
                SELECT
                    id,
                    ST_Transform(location::geometry, :projection_epsg) AS geom_proj,
                    location::geometry AS geom_wgs84
                FROM public.inventory_trees
                WHERE inventory_calculation_id = :inventory_id
                  AND dia_cm > 30
                  AND remark != 'Seedling';
            """), {
                "inventory_id": str(inventory_id),
                "projection_epsg": projection_epsg
            })

            # GiST index on projected geometry for KNN spatial index lookups
            self.db.execute(text("""
                CREATE INDEX idx_temp_eligible_geom_proj
                ON temp_eligible_trees USING gist (geom_proj);
            """))

            # Step 2: Get bounding box in projected CRS
            bounds_result = self.db.execute(text("""
                SELECT
                    ST_XMin(ST_Extent(geom_proj)) AS xmin,
                    ST_YMin(ST_Extent(geom_proj)) AS ymin,
                    ST_XMax(ST_Extent(geom_proj)) AS xmax,
                    ST_YMax(ST_Extent(geom_proj)) AS ymax
                FROM temp_eligible_trees;
            """)).first()

            if not bounds_result or bounds_result[0] is None:
                print("No eligible trees found for mother tree selection")
                return 0

            xmin, ymin, xmax, ymax = bounds_result
            print(f"Bounds in EPSG:{projection_epsg}: X({xmin:.2f}, {xmax:.2f}), Y({ymin:.2f}, {ymax:.2f})")

            # Save grid origin and dimensions to inventory_calculations record
            num_cols = int((xmax - xmin) / grid_spacing_meters) + 1
            num_rows = int((ymax - ymin) / grid_spacing_meters) + 1
            self.db.execute(text("""
                UPDATE public.inventory_calculations
                SET grid_origin_x = :origin_x,
                    grid_origin_y = :origin_y,
                    grid_num_cols = :num_cols,
                    grid_num_rows = :num_rows
                WHERE id = :inventory_id
            """), {
                "origin_x": xmin,
                "origin_y": ymin,
                "num_cols": num_cols,
                "num_rows": num_rows,
                "inventory_id": str(inventory_id)
            })

            # Step 3+4+5: Generate grid, find cells with trees, assign mother trees
            # Uses single CTE chain to avoid temp table persistence issues
            # Use SAVEPOINT so ST_SquareGrid failure doesn't poison the transaction
            self.db.execute(text("SAVEPOINT sp_grid"))
            try:
                self.db.execute(text("""
                    WITH grid_raw AS (
                        SELECT (ST_SquareGrid(:grid_size, ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), :projection_epsg))).*
                    ),
                    grid AS (
                        SELECT row_number() OVER () AS cell_id, geom, ST_Centroid(geom) AS centroid
                        FROM grid_raw
                    ),
                    cells_with_trees AS (
                        SELECT DISTINCT g.cell_id, g.centroid
                        FROM grid g
                        JOIN temp_eligible_trees t ON ST_Intersects(g.geom, t.geom_proj)
                    ),
                    nearest_trees AS (
                        SELECT DISTINCT ON (c.cell_id) c.cell_id, t.id AS tree_id
                        FROM cells_with_trees c
                        CROSS JOIN LATERAL (
                            SELECT id FROM temp_eligible_trees ORDER BY c.centroid <-> geom_proj LIMIT 1
                        ) t
                    )
                    UPDATE public.inventory_trees
                    SET remark = 'Mother Tree', grid_cell_id = nt.cell_id
                    FROM nearest_trees nt
                    WHERE inventory_trees.id = nt.tree_id
                """), {
                    "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                    "projection_epsg": projection_epsg,
                    "grid_size": grid_spacing_meters,
                })
                self.db.execute(text("RELEASE SAVEPOINT sp_grid"))
                print(f"Mother tree assignment via ST_SquareGrid")

            except Exception as e:
                self.db.execute(text("ROLLBACK TO SAVEPOINT sp_grid"))
                print(f"ST_SquareGrid not available, using manual grid generation: {e}")
                self.db.execute(text("""
                    WITH RECURSIVE
                    x_series AS (
                        SELECT :xmin + generate_series(0, CAST((:xmax - :xmin) / :grid_size AS INTEGER)) * :grid_size AS x
                    ),
                    y_series AS (
                        SELECT :ymin + generate_series(0, CAST((:ymax - :ymin) / :grid_size AS INTEGER)) * :grid_size AS y
                    ),
                    grid_raw AS (
                        SELECT ST_SetSRID(ST_MakeEnvelope(x, y, x + :grid_size, y + :grid_size), :projection_epsg) AS geom
                        FROM x_series, y_series
                    ),
                    grid AS (
                        SELECT row_number() OVER () AS cell_id, geom, ST_Centroid(geom) AS centroid
                        FROM grid_raw
                    ),
                    cells_with_trees AS (
                        SELECT DISTINCT g.cell_id, g.centroid
                        FROM grid g
                        JOIN temp_eligible_trees t ON ST_Intersects(g.geom, t.geom_proj)
                    ),
                    nearest_trees AS (
                        SELECT DISTINCT ON (c.cell_id) c.cell_id, t.id AS tree_id
                        FROM cells_with_trees c
                        CROSS JOIN LATERAL (
                            SELECT id FROM temp_eligible_trees ORDER BY c.centroid <-> geom_proj LIMIT 1
                        ) t
                    )
                    UPDATE public.inventory_trees
                    SET remark = 'Mother Tree', grid_cell_id = nt.cell_id
                    FROM nearest_trees nt
                    WHERE inventory_trees.id = nt.tree_id
                """), {
                    "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                    "projection_epsg": projection_epsg,
                    "grid_size": grid_spacing_meters,
                })
                print(f"Mother tree assignment via manual grid")

            self.db.commit()

            # Step 6: Get count of mother trees
            mother_tree_count = self.db.execute(text("""
                SELECT COUNT(*)
                FROM public.inventory_trees
                WHERE inventory_calculation_id = :inventory_id
                  AND remark = 'Mother Tree'
            """), {"inventory_id": str(inventory_id)}).scalar()

            # Clean up temp tables
            self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees"))

            return mother_tree_count

        except Exception as e:
            print(f"Error in mother tree identification: {str(e)}")
            # Rollback any changes
            self.db.rollback()
            # Clean up temp tables
            try:
                self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees, temp_grid_cells, temp_cells_with_trees"))
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
                COUNT(*) FILTER (WHERE remark = 'Seedling') AS seedlings,
                COALESCE(SUM(tree_volume), 0) AS total_volume_m3,
                COALESCE(SUM(net_volume), 0) AS total_net_volume_m3,
                COALESCE(SUM(net_volume_cft), 0) AS total_net_volume_cft,
                COALESCE(SUM(firewood_m3), 0) AS total_firewood_m3,
                COALESCE(SUM(firewood_chatta), 0) AS total_firewood_chatta
            FROM public.inventory_trees
            WHERE inventory_calculation_id = :inventory_id
        """)

        result = self.db.execute(summary_query, {"inventory_id": str(inventory_id)}).first()

        # Convert all values to native Python types (avoid numpy types)
        return {
            'total_trees': int(result[0]) if result[0] is not None else 0,
            'mother_trees_count': int(result[1]) if result[1] is not None else 0,
            'felling_trees_count': int(result[2]) if result[2] is not None else 0,
            'seedling_count': int(result[3]) if result[3] is not None else 0,
            'total_volume_m3': round(float(result[4]), 3) if result[4] is not None else 0.0,
            'total_net_volume_m3': round(float(result[5]), 3) if result[5] is not None else 0.0,
            'total_net_volume_cft': round(float(result[6]), 3) if result[6] is not None else 0.0,
            'total_firewood_m3': round(float(result[7]), 3) if result[7] is not None else 0.0,
            'total_firewood_chatta': round(float(result[8]), 3) if result[8] is not None else 0.0
        }

    async def _update_tree_spatial_relationships(
        self,
        inventory_id: UUID,
        calculation_id: UUID
    ) -> int:
        """
        Resolve block, sub-area, and compartment hierarchy for all trees
        using spatial intersection with forest_blocks and forest_sub_areas.

        This stores the resolved info directly on the InventoryTree records
        so export can read them without expensive spatial re-computation.

        Returns:
            Number of trees updated
        """
        inv_id_str = str(inventory_id)
        calc_id_str = str(calculation_id)
        total_updated = 0

        try:
            # 0. Clean up non-object extra_columns (e.g. list from previous bad merge)
            self.db.execute(text("""
                UPDATE public.inventory_trees
                SET extra_columns = NULL
                WHERE inventory_calculation_id = :inv_id
                  AND extra_columns IS NOT NULL
                  AND jsonb_typeof(extra_columns) != 'object'
            """), {"inv_id": inv_id_str})
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"[SPATIAL] Warning: cleanup step failed (non-critical): {e}")

        # 1. Resolve block info (division_level = 0) for trees missing block_name
        blocks_updated = 0
        try:
            block_result = self.db.execute(text("""
                UPDATE public.inventory_trees t
                SET block_id = fb.id,
                    block_name = fb.name
                FROM public.forest_blocks fb
                WHERE t.inventory_calculation_id = :inv_id
                  AND fb.calculation_id = :calc_id
                  AND fb.division_level = 0
                  AND ST_Intersects(t.location::geometry, fb.geometry)
                  AND (t.block_id IS NULL OR t.block_name IS NULL)
            """), {"inv_id": inv_id_str, "calc_id": calc_id_str})
            blocks_updated = block_result.rowcount
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"[SPATIAL] Warning: block resolution failed: {e}")
        print(f"[SPATIAL] Updated {blocks_updated} trees with block info")
        total_updated += blocks_updated

        # 2. Resolve sub-area info from calculation.result_data using jsonb_array_elements
        subareas_updated = 0
        try:
            result = self.db.execute(text("""
                UPDATE public.inventory_trees t
                SET sub_area_name = sa.value->>'name'
                FROM public.calculations c
                CROSS JOIN jsonb_array_elements(c.result_data->'sub_areas') sa
                WHERE c.id = :calc_id
                  AND t.inventory_calculation_id = :inv_id
                  AND t.sub_area_name IS NULL
                  AND ST_Intersects(
                      t.location::geometry,
                      ST_SetSRID(ST_GeomFromGeoJSON(sa.value->>'geometry'), 4326)
                  )
            """), {"calc_id": calc_id_str, "inv_id": inv_id_str})
            self.db.commit()
            subareas_updated = result.rowcount
        except Exception as e:
            self.db.rollback()
            print(f"[SPATIAL] Warning: sub-area resolution failed: {e}")
        print(f"[SPATIAL] Updated {subareas_updated} trees with sub-area info")
        total_updated += subareas_updated

        # 3. Resolve compartment hierarchy info into extra_columns
        comps_updated = 0
        try:
            comp_result = self.db.execute(text("""
                UPDATE public.inventory_trees t
                SET extra_columns = CASE
                    WHEN t.extra_columns IS NULL OR jsonb_typeof(t.extra_columns) = 'object'
                    THEN COALESCE(t.extra_columns, '{}'::jsonb) || jsonb_build_object(
                        'compartment_name', comp.name,
                        'sub_compartment_name', comp.sub_compartment_code,
                        'parent_compartment_name', comp.parent_name
                    )
                    ELSE jsonb_build_object(
                        'compartment_name', comp.name,
                        'sub_compartment_name', comp.sub_compartment_code,
                        'parent_compartment_name', comp.parent_name
                    )
                END
                FROM (
                    SELECT DISTINCT ON (it.id)
                        it.id AS tree_id,
                        fb.name,
                        fb.compartment_code AS sub_compartment_code,
                        parent.name AS parent_name
                    FROM public.inventory_trees it
                    JOIN public.forest_blocks fb ON ST_Intersects(it.location::geometry, fb.geometry)
                    LEFT JOIN public.forest_blocks parent ON fb.parent_block_id = parent.id
                    WHERE it.inventory_calculation_id = :inv_id
                      AND fb.calculation_id = :calc_id
                      AND fb.is_compartment = TRUE
                    ORDER BY it.id, fb.division_level DESC
                ) comp
                WHERE t.id = comp.tree_id
                  AND t.inventory_calculation_id = :inv_id
            """), {"inv_id": inv_id_str, "calc_id": calc_id_str})
            comps_updated = comp_result.rowcount
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"[SPATIAL] Warning: compartment resolution failed: {e}")
        print(f"[SPATIAL] Updated {comps_updated} trees with compartment hierarchy info")
        total_updated += comps_updated

        print(f"[SPATIAL] Spatial relationship update complete for inventory {inventory_id}")
        return total_updated

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
        # Get trees from database (including extra_columns for compartment info)
        trees = self.db.query(InventoryTree).filter(
            InventoryTree.inventory_calculation_id == inventory_id
        ).all()

        if not trees:
            raise ValueError("No trees found for this inventory")

        inventory = self.db.query(InventoryCalculation).filter(
            InventoryCalculation.id == inventory_id
        ).first()
        calculation_id = inventory.calculation_id if inventory else None

        print(f"[EXPORT] Exporting {len(trees)} trees for inventory {inventory_id}")

        # Resolve missing sub-area names on-the-fly using calculation's result_data
        if calculation_id:
            try:
                result = self.db.execute(text("""
                    UPDATE public.inventory_trees t
                    SET sub_area_name = sa.value->>'name'
                    FROM public.calculations c
                    CROSS JOIN jsonb_array_elements(c.result_data->'sub_areas') sa
                    WHERE c.id = :calc_id
                      AND t.inventory_calculation_id = :inv_id
                      AND t.sub_area_name IS NULL
                      AND ST_Intersects(
                          t.location::geometry,
                          ST_SetSRID(ST_GeomFromGeoJSON(sa.value->>'geometry'), 4326)
                      )
                """), {"calc_id": str(calculation_id), "inv_id": str(inventory_id)})
                self.db.commit()
                print(f"[EXPORT] Resolved {result.rowcount} sub-area assignments")
            except Exception as e:
                self.db.rollback()
                print(f"[EXPORT] Sub-area resolution skipped: {e}")

        # Create DataFrame directly from stored values
        data = []
        extra_cols_found = 0
        for tree in trees:
            # Extract lon, lat from geography
            result = self.db.execute(
                text("SELECT ST_X(location::geometry), ST_Y(location::geometry) FROM public.inventory_trees WHERE id = :id"),
                {"id": tree.id}
            ).first()

            lon, lat = result[0], result[1]

            # Read compartment info from extra_columns if available
            compartment_name = None
            sub_compartment_name = None
            parent_compartment_name = None
            extra_cols = tree.extra_columns
            if extra_cols and isinstance(extra_cols, dict):
                compartment_name = extra_cols.get('compartment_name')
                sub_compartment_name = extra_cols.get('sub_compartment_name')
                parent_compartment_name = extra_cols.get('parent_compartment_name')

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
                'block_name': tree.block_name,
                'sub_area_name': tree.sub_area_name,
                'compartment_name': compartment_name,
                'sub_compartment_name': sub_compartment_name,
                'parent_compartment_name': parent_compartment_name,
                'stem_volume': tree.stem_volume,
                'branch_volume': tree.branch_volume,
                'tree_volume': tree.tree_volume,
                'gross_volume': tree.gross_volume,
                'net_volume': tree.net_volume,
                'net_volume_cft': tree.net_volume_cft,
                'firewood_m3': tree.firewood_m3,
                'firewood_chatta': tree.firewood_chatta,
                'remark': tree.remark,
                'grid_cell_id': tree.grid_cell_id
            }

            # Add extra columns if they exist (excluding already-used compartment keys)
            if extra_cols and isinstance(extra_cols, dict):
                extra_for_row = {k: v for k, v in extra_cols.items()
                                 if k not in ('compartment_name', 'sub_compartment_name', 'parent_compartment_name')}
                if extra_for_row:
                    row_data.update(extra_for_row)
                    extra_cols_found += 1

            data.append(row_data)

        if extra_cols_found > 0:
            print(f"[EXPORT] Found {extra_cols_found} trees with extra columns")
        else:
            print(f"[EXPORT] No trees with extra columns found")

        df = pd.DataFrame(data)
        print(f"[EXPORT] DataFrame columns: {list(df.columns)}")

        if export_format == 'csv':
            csv_content = df.to_csv(index=False)
            return csv_content.encode('utf-8'), f'inventory_{inventory_id}.csv'

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
                        'block_name': row['block_name'],
                        'sub_area_name': row['sub_area_name'],
                        'compartment_name': row['compartment_name'],
                        'sub_compartment_name': row['sub_compartment_name'],
                        'parent_compartment_name': row['parent_compartment_name'],
                        'stem_volume': float(row['stem_volume']) if pd.notna(row['stem_volume']) else None,
                        'branch_volume': float(row['branch_volume']) if pd.notna(row['branch_volume']) else None,
                        'tree_volume': float(row['tree_volume']) if pd.notna(row['tree_volume']) else None,
                        'gross_volume': float(row['gross_volume']) if pd.notna(row['gross_volume']) else None,
                        'net_volume': float(row['net_volume']) if pd.notna(row['net_volume']) else None,
                        'net_volume_cft': float(row['net_volume_cft']) if pd.notna(row['net_volume_cft']) else None,
                        'firewood_m3': float(row['firewood_m3']) if pd.notna(row['firewood_m3']) else None,
                        'firewood_chatta': float(row['firewood_chatta']) if pd.notna(row['firewood_chatta']) else None,
                        'remark': row['remark'],
                        'grid_cell_id': int(row['grid_cell_id']) if pd.notna(row['grid_cell_id']) else None
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
            return geojson_content.encode('utf-8'), f'inventory_{inventory_id}.geojson'

        elif export_format == 'shapefile':
            # For shapefile, would need to create zip with .shp, .shx, .dbf, .prj
            # This requires additional implementation
            raise NotImplementedError("Shapefile export not yet implemented")

        else:
            raise ValueError(f"Unsupported export format: {export_format}")
