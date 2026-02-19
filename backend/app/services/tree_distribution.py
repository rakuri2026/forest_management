"""
Synthetic Tree Distribution Model Generator

Generates individual tree points (GPKG) from canopy height raster data
combined with species proportions and forestry standards for Nepal.

Algorithm Version: v1.0_prototype
Author: Community Forest Management System
Date: February 18, 2026
"""

import random
import math
import os
import uuid
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.shape import to_shape
from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union
import geopandas as gpd
import pandas as pd

from ..models.calculation import Calculation
from ..models.synthetic_tree_model import SyntheticTreeModel
from ..models.sampling import SamplingDesign
from ..core.config import settings


# Configuration Constants (Nepal-specific standards)
MIN_DBH_CM = 10.0          # Commercial inventory threshold
MIN_HEIGHT_M = 5.0         # Minimum tree height
MAX_TREES_PER_HA = 1000    # Upper cap on density
CANOPY_HEIGHT_PIXEL_SIZE = 30  # meters
PIXEL_AREA_HA = 0.09       # 900m² = 0.09 hectares


# Tree Density Lookup Tables (trees per hectare by canopy height)
TREE_DENSITY_DEFAULT = {
    (0, 2): 0,           # Below 2m = no commercial trees
    (2, 5): 0,           # Below 5m = excluded (regeneration/poles)
    (5, 10): 600,        # Young timber
    (10, 15): 450,       # Maturing timber
    (15, 20): 320,       # Mature timber
    (20, 25): 250,       # Old growth
    (25, 30): 200,       # Very tall canopy
    (30, 100): 150,      # Exceptional heights
}

# Forest type-specific densities (override default)
TREE_DENSITY_BY_FOREST_TYPE = {
    'Tropical Mixed Deciduous Forest': {
        (0, 5): 0,
        (5, 10): 550,
        (10, 15): 420,
        (15, 20): 300,
        (20, 30): 230,
        (30, 100): 180,
    },
    'Lower Temperate Pine Forest': {
        (0, 5): 0,
        (5, 10): 300,
        (10, 15): 240,
        (15, 20): 200,
        (20, 30): 160,
        (30, 100): 130,
    },
    'Lower Temperate Mixed Broadleaved Forest': {
        (0, 5): 0,
        (5, 10): 500,
        (10, 15): 400,
        (15, 20): 300,
        (20, 30): 240,
        (30, 100): 180,
    },
    'Sal Forest': {
        (0, 5): 0,
        (5, 10): 450,
        (10, 15): 350,
        (15, 20): 280,
        (20, 30): 220,
        (30, 100): 170,
    },
}


def get_tree_density(canopy_height: float, forest_type: str) -> int:
    """
    Get trees per hectare for given canopy height and forest type

    Args:
        canopy_height: Canopy height in meters
        forest_type: Forest type classification string

    Returns:
        Trees per hectare (integer)
    """
    # Select appropriate lookup table
    lookup = TREE_DENSITY_BY_FOREST_TYPE.get(forest_type, TREE_DENSITY_DEFAULT)

    # Find matching height range
    for (min_h, max_h), density in lookup.items():
        if min_h <= canopy_height < max_h:
            return min(density, MAX_TREES_PER_HA)

    # Fallback for heights outside defined ranges
    return 150 if canopy_height >= 5 else 0


def generate_random_point_in_pixel(pixel_bounds: Tuple[float, float, float, float]) -> Tuple[float, float]:
    """
    Generate random point within pixel boundaries

    Args:
        pixel_bounds: (min_x, min_y, max_x, max_y) in EPSG:4326

    Returns:
        (longitude, latitude) tuple
    """
    min_x, min_y, max_x, max_y = pixel_bounds
    x = random.uniform(min_x, max_x)
    y = random.uniform(min_y, max_y)
    return (x, y)


def weighted_random_choice(species_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Select species based on weighted probabilities from availability_rank

    Args:
        species_list: List of species dictionaries with 'availability_rank'

    Returns:
        Selected species dictionary
    """
    if not species_list:
        raise ValueError("Species list is empty")

    # Calculate weights (higher rank = higher probability)
    # availability_rank: 1=dominant, 2=co-dominant, 3=associate, 4=occasional, 5=rare
    # Invert so dominant species get higher weight
    weights = []
    for species in species_list:
        rank = species.get('availability_rank', 3)
        # Weight formula: 6 - rank (so 1 becomes 5, 5 becomes 1)
        weight = max(1, 6 - rank)
        weights.append(weight)

    # Weighted random selection
    total_weight = sum(weights)
    r = random.uniform(0, total_weight)
    cumulative = 0
    for species, weight in zip(species_list, weights):
        cumulative += weight
        if r <= cumulative:
            return species

    # Fallback to last species
    return species_list[-1]


def assign_tree_height(canopy_height: float, species: Dict[str, Any], role: str) -> float:
    """
    Assign tree height based on canopy height, species, and vertical position

    Args:
        canopy_height: Pixel canopy height (meters)
        species: Species dictionary with max_height_m
        role: 'dominant', 'co-dominant', 'associate', 'occasional', 'rare'

    Returns:
        Tree height in meters
    """
    # Get species maximum height constraint
    max_species_height = species.get('max_height_m', 40)

    # Apply vertical stratification based on role
    if role == 'dominant':
        # Dominant species: 80-100% of canopy height
        height = canopy_height * random.uniform(0.80, 1.00)
    elif role == 'co-dominant':
        # Co-dominant: 60-85% of canopy height
        height = canopy_height * random.uniform(0.60, 0.85)
    elif role == 'associate':
        # Associate: 40-70% of canopy height
        height = canopy_height * random.uniform(0.40, 0.70)
    else:  # occasional/rare
        # Understory: 25-55% of canopy height
        height = canopy_height * random.uniform(0.25, 0.55)

    # Constrain to species maximum
    height = min(height, max_species_height)

    # Ensure meets minimum threshold
    height = max(height, MIN_HEIGHT_M)

    return round(height, 1)


def calculate_dbh_from_height(height: float, species: Dict[str, Any]) -> float:
    """
    Calculate DBH from height using species-specific relationships

    Priority order:
    1. H:D ratio from database (typical_hd_ratio)
    2. Allometric coefficients (a, b, c)
    3. Fallback: growth rate-based ratio

    Args:
        height: Tree height in meters
        species: Species dictionary with allometric data

    Returns:
        DBH in centimeters
    """
    # Option 1: Use H:D ratio if available
    hd_min = species.get('typical_hd_ratio_min')
    hd_max = species.get('typical_hd_ratio_max')

    if hd_min is not None and hd_max is not None and hd_min > 0 and hd_max > 0:
        hd_ratio = random.uniform(hd_min, hd_max)
        dbh = height / hd_ratio * 100  # Convert to cm

    # Option 2: Use allometric equation (if coefficients exist)
    elif species.get('a') is not None and species.get('b') is not None:
        a = species['a']
        b = species['b']
        c = species.get('c', 1.0)  # Default c=1 if not specified

        # Inverse of Height = a + b*DBH^c
        # Simplified for c=1: DBH = (Height - a) / b
        if c == 1.0 and b != 0:
            dbh = (height - a) / b
        else:
            # For other c values, use approximation
            dbh = height / 35  # Fallback

    # Option 3: Fallback - use growth rate-based ratio
    else:
        growth_rate = species.get('growth_rate', 'Moderate')

        if growth_rate == 'Fast':
            hd_ratio = random.uniform(0.25, 0.35)  # Fast growers: relatively thicker
        elif growth_rate == 'Moderate':
            hd_ratio = random.uniform(0.30, 0.40)
        else:  # Slow
            hd_ratio = random.uniform(0.35, 0.50)  # Slow growers: relatively thinner

        dbh = height / hd_ratio

    # Constrain to species maximum
    max_dbh = species.get('max_dbh_cm', 200)
    dbh = min(dbh, max_dbh)

    # Ensure meets minimum threshold
    dbh = max(dbh, MIN_DBH_CM)

    return round(dbh, 1)


def assign_tree_class(dbh: float, height: float, species: Dict[str, Any]) -> int:
    """
    Assign tree class (1=25%, 2=50%, 3=75%, 4=100% firewood potential)

    Nepal standard:
    - Class 4 (100%): Small trees, low economic value
    - Class 1 (25%): Large trees, high economic value
    - Class 2-3: Mid-range

    Args:
        dbh: DBH in centimeters
        height: Height in meters
        species: Species dictionary with economic_value

    Returns:
        Tree class (1-4)
    """
    # Base class on tree size
    if dbh < 15 or height < 8:
        base_class = 4  # Small = mostly firewood
    elif dbh < 25 or height < 12:
        base_class = 3
    elif dbh < 40 or height < 16:
        base_class = 2
    else:
        base_class = 1  # Large = mostly timber

    # Adjust by economic value
    econ_value = species.get('economic_value', 'Moderate')

    if econ_value in ['High', 'Very High']:
        base_class = max(1, base_class - 1)  # Shift towards timber
    elif econ_value == 'Low':
        base_class = min(4, base_class + 1)  # Shift towards firewood

    return base_class


def get_species_role(availability_rank: int) -> str:
    """
    Convert availability_rank to role string

    Args:
        availability_rank: 1=dominant, 2=co-dominant, 3=associate, 4=occasional, 5=rare

    Returns:
        Role string
    """
    rank_to_role = {
        1: 'dominant',
        2: 'co-dominant',
        3: 'associate',
        4: 'occasional',
        5: 'rare'
    }
    return rank_to_role.get(availability_rank, 'associate')


def extract_canopy_pixels(boundary_wkt: str, db: Session) -> List[Dict[str, Any]]:
    """
    Extract canopy height pixels within boundary from PostGIS raster.
    Only returns pixels whose CENTROIDS fall within the boundary polygon.

    Args:
        boundary_wkt: WKT string of boundary geometry (EPSG:4326)
        db: Database session

    Returns:
        List of pixel dictionaries with {height, bounds, center}
    """
    query = text("""
        WITH boundary AS (
            SELECT ST_GeomFromText(:boundary_wkt, 4326) AS geom
        ),
        pixels AS (
            SELECT
                (ST_PixelAsCentroids(rast, 1)).*
            FROM rasters.canopy_height, boundary
            WHERE ST_Intersects(rast, geom)
        )
        SELECT
            x, y, val AS height,
            ST_XMin(geom) AS min_x,
            ST_YMin(geom) AS min_y,
            ST_XMax(geom) AS max_x,
            ST_YMax(geom) AS max_y
        FROM pixels, boundary
        WHERE val IS NOT NULL
          AND val > 0
          AND ST_Within(geom, boundary.geom)  -- ✅ Only pixels INSIDE boundary
    """)

    result = db.execute(query, {"boundary_wkt": boundary_wkt})
    pixels = []

    for row in result:
        pixels.append({
            'height': float(row.height),
            'bounds': (row.min_x, row.min_y, row.max_x, row.max_y),
            'center': (row.x, row.y)
        })

    return pixels


def assign_sample_plots_to_trees(
    trees: List[Dict[str, Any]],
    sampling_design: 'SamplingDesign',
    buffer_meters: float,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Assign sample plot numbers to trees based on buffer intersection.

    Args:
        trees: List of tree dictionaries with geometry (x, y)
        sampling_design: SamplingDesign object with sample points
        buffer_meters: Buffer distance around each plot (default: 25m)
        db: Database session

    Returns:
        Updated trees list with sample_plot_number assigned
    """
    from geoalchemy2.shape import to_shape

    # Extract sample plot points from sampling design
    if not sampling_design.points_geometry:
        # No points - return trees unchanged
        return trees

    # Get sample plot points as Shapely geometry
    sample_points_geom = to_shape(sampling_design.points_geometry)

    # Get plot assignments (if available)
    plot_assignments = sampling_design.points_block_assignment or []

    # Create list of plot geometries with their plot numbers
    plot_buffers = []

    if hasattr(sample_points_geom, 'geoms'):
        # MultiPoint - iterate through individual points
        for idx, point in enumerate(sample_points_geom.geoms):
            # Try to get plot number from assignments, otherwise use index+1
            plot_info = next(
                (p for p in plot_assignments if p.get('point_index') == idx),
                None
            )
            plot_number = plot_info.get('plot_number', idx + 1) if plot_info else idx + 1

            # Create buffer around point (in degrees, approximate)
            # For better accuracy, should convert to UTM, but this is acceptable for 25m
            buffer_deg = buffer_meters / 111320.0  # Rough conversion: 1 degree ≈ 111.32 km
            buffered_plot = point.buffer(buffer_deg)

            plot_buffers.append({
                'plot_number': plot_number,
                'geometry': buffered_plot
            })
    else:
        # Single Point
        buffer_deg = buffer_meters / 111320.0
        buffered_plot = sample_points_geom.buffer(buffer_deg)
        plot_buffers.append({
            'plot_number': 1,
            'geometry': buffered_plot
        })

    # Assign plot numbers to each tree
    for tree in trees:
        tree_point = Point(tree['geometry'])
        intersecting_plots = []

        # Check which plot buffers this tree intersects
        for plot in plot_buffers:
            if plot['geometry'].contains(tree_point):
                intersecting_plots.append(str(plot['plot_number']))

        # Assign plot number(s)
        if intersecting_plots:
            # Multiple plots: comma-separated
            tree['sample_plot_number'] = ','.join(intersecting_plots)
        else:
            # No plot assignment
            tree['sample_plot_number'] = None

    return trees


def export_to_gpkg(
    trees: List[Dict[str, Any]],
    calculation_id: uuid.UUID,
    output_dir: str = "exports"
) -> Tuple[str, float]:
    """
    Export trees to GPKG file using GeoPandas

    Args:
        trees: List of tree dictionaries
        calculation_id: UUID of calculation
        output_dir: Directory to save GPKG files

    Returns:
        Tuple of (filepath, file_size_mb)
    """
    # Create output directory if needed
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"synthetic_trees_{calculation_id}_{timestamp}.gpkg"
    filepath = os.path.join(output_dir, filename)

    # Create list of records
    records = []
    for tree in trees:
        records.append({
            'tree_id': tree['tree_id'],
            'species_code': tree.get('species_code'),
            'species_scientific': tree.get('species_scientific'),
            'species_local': tree.get('species_local'),
            'species_role': tree.get('species_role'),
            'height_m': tree['height_m'],
            'dbh_cm': tree['dbh_cm'],
            'tree_class': tree['tree_class'],
            'canopy_height_source': tree['canopy_height_source'],
            'forest_type': tree.get('forest_type'),
            'block_name': tree.get('block_name'),
            'sample_plot_number': tree.get('sample_plot_number'),  # ✅ New column
            'generated_date': tree['generated_date'],
            'model_version': tree['model_version'],
            'notes': tree.get('notes', 'SYNTHETIC DATA - Not ground survey'),
            'geometry': Point(tree['geometry'])
        })

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(records, crs='EPSG:4326')

    # Write to GPKG
    gdf.to_file(filepath, driver='GPKG', layer='synthetic_trees')

    # Calculate file size
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    return filepath, file_size_mb


def generate_synthetic_trees(
    calculation_id: uuid.UUID,
    db: Session,
    config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Main algorithm: Generate synthetic tree distribution from canopy height raster

    Args:
        calculation_id: UUID of calculation with boundary
        db: Database session
        config: Optional configuration overrides
        progress_callback: Optional function(percent, step) to report progress

    Returns:
        Dictionary with generation results and statistics
    """
    start_time = datetime.now()

    # Default configuration
    default_config = {
        'min_dbh_cm': MIN_DBH_CM,
        'min_height_m': MIN_HEIGHT_M,
        'max_trees_per_ha': MAX_TREES_PER_HA,
        'spatial_distribution': 'random',
        'algorithm_version': 'v1.0',
        'plot_buffer_meters': 25.0  # Default buffer for sample plot assignment
    }
    config = {**default_config, **(config or {})}

    # Report progress
    def report(percent: int, step: str):
        if progress_callback:
            progress_callback(percent, step)

    # Step 1: Load calculation and data
    report(10, "Loading calculation data")
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    # Get boundary geometry
    boundary_shape = to_shape(calculation.boundary_geom)
    boundary_wkt = boundary_shape.wkt

    # Get species list from result_data
    result_data = calculation.result_data or {}
    species_list = result_data.get('potential_species', [])
    if not species_list:
        raise ValueError("No species data found in calculation")

    forest_type = result_data.get('forest_type', {}).get('dominant_type', 'Unknown')
    area_hectares = result_data.get('area', {}).get('hectares', 0)

    # Step 1.5: Check if sampling design exists (REQUIRED)
    report(12, "Checking for sampling design")
    sampling_design = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id
    ).first()

    if not sampling_design or not sampling_design.points_geometry:
        raise ValueError(
            "Sample plots are required before generating tree distribution. "
            "Please create a sampling design first from the Sampling tab."
        )

    # Step 2: Extract canopy height pixels
    report(20, "Extracting canopy height data")
    pixels = extract_canopy_pixels(boundary_wkt, db)

    if not pixels:
        raise ValueError("No canopy height data found within boundary")

    # Step 3: Generate trees
    report(30, "Generating individual trees")
    trees = []
    tree_id = 1

    for idx, pixel in enumerate(pixels):
        # Progress update every 10% of pixels
        if idx % max(1, len(pixels) // 5) == 0:
            progress = 30 + int((idx / len(pixels)) * 50)
            report(progress, f"Processing pixel {idx+1}/{len(pixels)}")

        canopy_height = pixel['height']

        # Determine trees per hectare
        trees_per_ha = get_tree_density(canopy_height, forest_type)
        if trees_per_ha == 0:
            continue  # Skip pixels with no trees (below threshold)

        # Calculate trees in this pixel
        num_trees = int(trees_per_ha * PIXEL_AREA_HA)
        if num_trees == 0:
            continue

        # Generate trees in this pixel
        for _ in range(num_trees):
            # Generate random point
            x, y = generate_random_point_in_pixel(pixel['bounds'])

            # ✅ Ensure point is actually within boundary polygon (double-check)
            tree_point = Point(x, y)
            if not boundary_shape.contains(tree_point):
                continue  # Skip points outside boundary

            # Select species
            species = weighted_random_choice(species_list)
            role = get_species_role(species.get('availability_rank', 3))

            # Assign height
            tree_height = assign_tree_height(canopy_height, species, role)

            # Calculate DBH
            dbh = calculate_dbh_from_height(tree_height, species)

            # Filter by thresholds
            if dbh < config['min_dbh_cm'] or tree_height < config['min_height_m']:
                continue  # Skip trees below threshold

            # Assign tree class
            tree_class = assign_tree_class(dbh, tree_height, species)

            # Create tree record
            trees.append({
                'tree_id': tree_id,
                'geometry': (x, y),
                'species_code': species.get('species_code'),
                'species_scientific': species.get('scientific_name'),
                'species_local': species.get('local_name'),
                'species_role': role,
                'height_m': tree_height,
                'dbh_cm': dbh,
                'tree_class': tree_class,
                'canopy_height_source': canopy_height,
                'forest_type': forest_type,
                'block_name': calculation.block_name or '',
                'generated_date': datetime.now().isoformat(),
                'model_version': config['algorithm_version'],
                'notes': 'SYNTHETIC DATA - Not ground survey',
                'sample_plot_number': None  # Will be assigned later
            })
            tree_id += 1

    if not trees:
        raise ValueError("No trees generated - all below threshold")

    # Step 4: Assign sample plot numbers to trees
    report(80, "Assigning trees to sample plots")
    trees = assign_sample_plots_to_trees(
        trees=trees,
        sampling_design=sampling_design,
        buffer_meters=config['plot_buffer_meters'],
        db=db
    )

    # Step 5: Export to GPKG
    report(90, "Exporting to GPKG file")
    filepath, file_size_mb = export_to_gpkg(trees, calculation_id)

    # Step 6: Calculate statistics
    report(97, "Calculating statistics")
    dbhs = [t['dbh_cm'] for t in trees]
    heights = [t['height_m'] for t in trees]

    statistics = {
        'total_trees': len(trees),
        'area_hectares': area_hectares,
        'trees_per_hectare': len(trees) / area_hectares if area_hectares > 0 else 0,
        'min_dbh_cm': min(dbhs),
        'max_dbh_cm': max(dbhs),
        'mean_dbh_cm': sum(dbhs) / len(dbhs),
        'min_height_m': min(heights),
        'max_height_m': max(heights),
        'mean_height_m': sum(heights) / len(heights),
        'species_count': len(set(t['species_scientific'] for t in trees)),
    }

    processing_time = (datetime.now() - start_time).total_seconds()

    report(100, "Complete")

    return {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'file_size_mb': file_size_mb,
        'statistics': statistics,
        'processing_time_seconds': int(processing_time),
        'config': config
    }
