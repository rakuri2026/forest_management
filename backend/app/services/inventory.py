"""
Inventory service - Tree volume calculations and mother tree selection
Based on allometric equations for Nepal tree species
"""
import math
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
            # Update status to failed
            inventory.status = 'failed'
            inventory.error_message = str(e)
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

        for idx, row in df.iterrows():
            species = row[species_col]
            dbh_cm = row[diameter_col]

            # Get species coefficients
            if species not in self.species_coefficients:
                # Skip if species not found (should not happen after validation)
                continue

            coef = self.species_coefficients[species]

            # Get or estimate height
            if height_col and pd.notna(row[height_col]):
                height_m = row[height_col]
            else:
                # Estimate height using default H/D ratio
                height_m = dbh_cm * 0.8  # Default ratio for missing heights

            # For seedlings (DBH < 10 cm), use default H/D ratio
            if dbh_cm < 10:
                height_m = dbh_cm * 0.8

            # 1. Calculate stem volume
            # Formula: V = exp(a + b*ln(DBH) + c*ln(H)) / 1000
            if coef['a'] is not None and coef['b'] is not None and coef['c'] is not None:
                stem_volume = math.exp(
                    coef['a'] +
                    coef['b'] * math.log(dbh_cm) +
                    coef['c'] * math.log(height_m)
                ) / 1000.0  # Convert to m³
            else:
                # Use generic formula for species without coefficients
                stem_volume = 0.0

            # 2. Calculate branch volume
            branch_ratio = 0.1 if dbh_cm < 10 else 0.2
            branch_volume = stem_volume * branch_ratio

            # 3. Total tree volume
            tree_volume = stem_volume + branch_volume

            # 4. Calculate gross volume (merchantable)
            # Remove top portion (diameter < 10 cm)
            if coef['a1'] is not None and coef['b1'] is not None:
                cm10_dia_ratio = math.exp(
                    coef['a1'] + coef['b1'] * math.log(dbh_cm)
                )
                cm10_top_volume = stem_volume * cm10_dia_ratio
                gross_volume = stem_volume - cm10_top_volume
            else:
                gross_volume = stem_volume * 0.85  # Default 85% is merchantable

            # 5. Calculate net volume (after defects)
            tree_class = row[class_col] if class_col and pd.notna(row[class_col]) else 'B'
            if tree_class == 'A':
                net_volume = gross_volume * 0.9  # 10% defect
            else:
                net_volume = gross_volume * 0.8  # 20% defect

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

            tree = InventoryTree(
                inventory_calculation_id=inventory_id,
                species=species,
                dia_cm=float(row[diameter_col]),
                height_m=float(row[height_col]) if height_col and pd.notna(row[height_col]) else None,
                tree_class=row[class_col] if class_col and pd.notna(row[class_col]) else None,
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

            # 3. Initially mark all trees
            print(f"[INVENTORY] Step 3/6: Marking seedlings vs felling trees...")
            df['remark'] = df.apply(
                lambda row: 'Seedling' if row[diameter_col] < 10 else 'Felling Tree',
                axis=1
            )
            df['grid_cell_id'] = None
            print(f"[INVENTORY] Step 3/6: Marked {len(df[df['remark'] == 'Seedling'])} seedlings, {len(df[df['remark'] == 'Felling Tree'])} felling trees")

            # 4. Store trees in database FIRST (needed for PostGIS mother tree selection)
            print(f"[INVENTORY] Step 4/6: Storing {len(df)} trees in database...")
            await self._store_trees_simple(
                inventory_id, df, species_col, diameter_col, height_col,
                class_col, lon_col, lat_col
            )
            print(f"[INVENTORY] Step 4/6: Successfully stored {len(df)} trees")

            # 5. Identify mother trees using PostGIS
            print(f"[INVENTORY] Step 5/6: Identifying mother trees (grid: {grid_spacing_meters}m, EPSG: {inventory.projection_epsg})...")
            mother_tree_count = await self._identify_mother_trees_postgis(
                inventory_id,
                grid_spacing_meters,
                inventory.projection_epsg
            )
            print(f"[INVENTORY] Step 5/6: Identified {mother_tree_count} mother trees")

            # 6. Calculate summary statistics from database
            print(f"[INVENTORY] Step 6/6: Calculating summary statistics...")
            summary = await self._calculate_summary_from_db(inventory_id)
            print(f"[INVENTORY] Step 6/6: Summary calculated")

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
            # Update status to failed
            inventory.status = 'failed'
            inventory.error_message = str(e)
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
            'firewood_chatta', 'remark', 'grid_cell_id'
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

                tree = InventoryTree(
                    inventory_calculation_id=inventory_id,
                    species=species,
                    dia_cm=float(row[diameter_col]),
                    height_m=float(row[height_col]) if pd.notna(row.get(height_col)) else None,
                    tree_class=row[class_col] if pd.notna(row.get(class_col)) else None,
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
            # Step 1: Create temporary table with eligible trees (DBH >= 10 cm)
            # and transform to projected CRS
            self.db.execute(text("""
                DROP TABLE IF EXISTS temp_eligible_trees;
                CREATE TEMP TABLE temp_eligible_trees AS
                SELECT
                    id,
                    ST_Transform(location::geometry, :projection_epsg) AS geom_proj,
                    location::geometry AS geom_wgs84
                FROM public.inventory_trees
                WHERE inventory_calculation_id = :inventory_id
                  AND dia_cm >= 10
                  AND remark != 'Seedling';
            """), {
                "inventory_id": str(inventory_id),
                "projection_epsg": projection_epsg
            })

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

            # Step 3: Generate grid cells using PostGIS
            # ST_SquareGrid is available in PostGIS 3.1+
            # If not available, we'll use manual grid generation
            try:
                # Try using ST_SquareGrid (PostGIS 3.1+)
                grid_query = text("""
                    DROP TABLE IF EXISTS temp_grid_cells;
                    CREATE TEMP TABLE temp_grid_cells AS
                    WITH bounds AS (
                        SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), :projection_epsg) AS geom
                    ),
                    grid AS (
                        SELECT (ST_SquareGrid(:grid_size, geom)).*
                        FROM bounds
                    )
                    SELECT
                        row_number() OVER () AS cell_id,
                        geom,
                        ST_Centroid(geom) AS centroid
                    FROM grid;
                """)

                self.db.execute(grid_query, {
                    "xmin": xmin,
                    "ymin": ymin,
                    "xmax": xmax,
                    "ymax": ymax,
                    "projection_epsg": projection_epsg,
                    "grid_size": grid_spacing_meters
                })
                print(f"Generated grid using ST_SquareGrid")

            except Exception as e:
                print(f"ST_SquareGrid not available, using manual grid generation: {e}")

                # Fallback: Manual grid generation
                self.db.execute(text("""
                    DROP TABLE IF EXISTS temp_grid_cells;
                    CREATE TEMP TABLE temp_grid_cells AS
                    WITH RECURSIVE
                    x_series AS (
                        SELECT :xmin + generate_series(0, CAST((:xmax - :xmin) / :grid_size AS INTEGER)) * :grid_size AS x
                    ),
                    y_series AS (
                        SELECT :ymin + generate_series(0, CAST((:ymax - :ymin) / :grid_size AS INTEGER)) * :grid_size AS y
                    ),
                    grid AS (
                        SELECT
                            row_number() OVER () AS cell_id,
                            ST_SetSRID(
                                ST_MakeEnvelope(
                                    x, y,
                                    x + :grid_size, y + :grid_size
                                ),
                                :projection_epsg
                            ) AS geom
                        FROM x_series, y_series
                    )
                    SELECT
                        cell_id,
                        geom,
                        ST_Centroid(geom) AS centroid
                    FROM grid;
                """), {
                    "xmin": xmin,
                    "ymin": ymin,
                    "xmax": xmax,
                    "ymax": ymax,
                    "projection_epsg": projection_epsg,
                    "grid_size": grid_spacing_meters
                })
                print(f"Generated grid manually")

            # Step 4: Find grid cells that contain trees
            self.db.execute(text("""
                DROP TABLE IF EXISTS temp_cells_with_trees;
                CREATE TEMP TABLE temp_cells_with_trees AS
                SELECT DISTINCT g.cell_id, g.centroid
                FROM temp_grid_cells g
                JOIN temp_eligible_trees t ON ST_Intersects(g.geom, t.geom_proj);
            """))

            cell_count = self.db.execute(text("SELECT COUNT(*) FROM temp_cells_with_trees")).scalar()
            print(f"Found {cell_count} grid cells containing trees")

            # Step 5: For each cell, find the tree nearest to its centroid
            # and mark it as Mother Tree
            self.db.execute(text("""
                WITH nearest_trees AS (
                    SELECT DISTINCT ON (c.cell_id)
                        c.cell_id,
                        t.id AS tree_id
                    FROM temp_cells_with_trees c
                    CROSS JOIN LATERAL (
                        SELECT id, ST_Distance(c.centroid, geom_proj) AS distance
                        FROM temp_eligible_trees
                        ORDER BY ST_Distance(c.centroid, geom_proj)
                        LIMIT 1
                    ) t
                )
                UPDATE public.inventory_trees
                SET
                    remark = 'Mother Tree',
                    grid_cell_id = nt.cell_id
                FROM nearest_trees nt
                WHERE inventory_trees.id = nt.tree_id;
            """))

            self.db.commit()

            # Step 6: Get count of mother trees
            mother_tree_count = self.db.execute(text("""
                SELECT COUNT(*)
                FROM public.inventory_trees
                WHERE inventory_calculation_id = :inventory_id
                  AND remark = 'Mother Tree'
            """), {"inventory_id": str(inventory_id)}).scalar()

            # Clean up temp tables
            self.db.execute(text("DROP TABLE IF EXISTS temp_eligible_trees, temp_grid_cells, temp_cells_with_trees"))

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
        # Get trees from database
        trees = self.db.query(InventoryTree).filter(
            InventoryTree.inventory_calculation_id == inventory_id
        ).all()

        if not trees:
            raise ValueError("No trees found for this inventory")

        # Create DataFrame
        data = []
        extra_cols_found = 0
        for tree in trees:
            # Extract lon, lat from geography
            result = self.db.execute(
                text("SELECT ST_X(location::geometry), ST_Y(location::geometry) FROM public.inventory_trees WHERE id = :id"),
                {"id": tree.id}
            ).first()

            lon, lat = result[0], result[1]

            row_data = {
                'species': tree.species,
                'local_name': tree.local_name,
                'dia_cm': tree.dia_cm,
                'height_m': tree.height_m,
                'tree_class': tree.tree_class,
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
                'grid_cell_id': tree.grid_cell_id
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
