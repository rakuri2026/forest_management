"""
Synthetic Tree Distribution Model Generator

Generates individual tree points (GPKG) from canopy height raster data
combined with species proportions and forestry standards for Nepal.

Algorithm Version: v1.0_prototype
Author: Community Forest Management System
Date: February 18, 2026
"""

import logging
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

# Debug logging for volume calculation comparison
DEBUG_VOLUME_CALC = os.environ.get('DEBUG_VOLUME_CALC', 'false').lower() == 'true'

def _debug_log(msg: str):
    """Print debug message if DEBUG_VOLUME_CALC is enabled"""
    if DEBUG_VOLUME_CALC:
        print(f"[TREE_MODEL_VOLUME] {msg}")
from ..core.config import settings


# Configuration Constants (Nepal-specific standards)
MIN_DBH_CM = 10.0          # Commercial inventory threshold
MIN_HEIGHT_M = 5.0         # Minimum tree height
MAX_TREES_PER_HA = 500     # Upper cap on density
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


def get_tree_density(canopy_height: float, forest_type: str, max_density: int = MAX_TREES_PER_HA) -> int:
    """
    Get trees per hectare for given canopy height and forest type

    Args:
        canopy_height: Canopy height in meters
        forest_type: Forest type classification string
        max_density: Maximum trees per hectare cap (user-configurable)

    Returns:
        Trees per hectare (integer)
    """
    # Select appropriate lookup table
    lookup = TREE_DENSITY_BY_FOREST_TYPE.get(forest_type, TREE_DENSITY_DEFAULT)

    # Find matching height range
    for (min_h, max_h), density in lookup.items():
        if min_h <= canopy_height < max_h:
            return min(density, max_density)  # Use user's max_density, not hardcoded constant

    # Fallback for heights outside defined ranges
    fallback = 150 if canopy_height >= 5 else 0
    return min(fallback, max_density)


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


def calculate_tree_volumes(
    dbh: float,
    height: float,
    tree_class: int,
    species_coefficients: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate tree volumes using Forest Regulation 2079 formulas

    Args:
        dbh: Diameter at breast height in centimeters
        height: Tree height in meters
        tree_class: Tree class (1, 2, 3, or 4)
        species_coefficients: Dictionary with species coefficients (a, b, c, s, m, a1, b1)

    Returns:
        Dictionary with volume components:
        - stem_volume: Stem volume in m³
        - branch_volume: Branch volume in m³
        - tree_volume: Total tree volume in m³
        - gross_volume: Gross timber volume in m³ (from stem only)
        - net_volume: Net timber volume in m³ (after waste)
        - firewood_m3: Firewood volume in m³
    """
    # Debug logging
    _debug_log(f"INPUT: dbh={dbh}, height={height}, tree_class={tree_class}")
    _debug_log(f"SPECIES_COEFFS: {species_coefficients.get('scientific_name', 'unknown')}")
    _debug_log(f"COEFFS: a={species_coefficients.get('a')}, b={species_coefficients.get('b')}, c={species_coefficients.get('c')}, a1={species_coefficients.get('a1')}, b1={species_coefficients.get('b1')}, s={species_coefficients.get('s')}, m={species_coefficients.get('m')}, bg={species_coefficients.get('bg')}")
    
    # Skip if regeneration (DBH < 10 cm)
    if dbh < 10:
        return {
            'stem_volume': 0.0,
            'branch_volume': 0.0,
            'tree_volume': 0.0,
            'gross_volume': 0.0,
            'net_volume': 0.0,
            'firewood_m3': 0.0
        }

    coef = species_coefficients

    # 1. Calculate stem volume (Forest Regulation 2079, Table 1)
    # Formula: V = exp(a + b*ln(DBH) + c*ln(H)) / 1000
    if coef.get('a') is not None and coef.get('b') is not None and coef.get('c') is not None:
        log_dbh = math.log(dbh)
        log_height = math.log(height)
        exp_value = coef['a'] + coef['b'] * log_dbh + coef['c'] * log_height
        stem_volume = math.exp(exp_value) / 1000.0  # Convert to m³
        
        _debug_log(f"STEM: log(dbh)={log_dbh}, log(height)={log_height}, exp={exp_value}, stem_vol={stem_volume}")
    else:
        stem_volume = 0.0
        _debug_log("STEM: Using default 0.0 (missing coefficients)")

    # 2. Calculate branch volume (Forest Regulation 2079, Table 2)
    # Formula: Branch Volume = Stem Volume × Branch Ratio
    # Based on Sharma and Pukala, 1990
    # s = small (sano), m = medium (machilo), bg = big (bara)
    s = coef.get('s')
    m = coef.get('m')
    bg = coef.get('bg')
    
    if s is not None and m is not None and bg is not None:
        # Use interpolation formula based on DBH class
        if dbh < 10:
            # Small trees: use s coefficient
            branch_ratio = float(s)
        elif dbh <= 40:
            # 10-40 cm: linear interpolation between s and m
            branch_ratio = ((dbh - 10) * float(m) + (40 - dbh) * float(s)) / 30.0
        elif dbh <= 70:
            # 40-70 cm: linear interpolation between m and bg
            branch_ratio = ((dbh - 40) * float(bg) + (70 - dbh) * float(m)) / 30.0
        else:
            # >70 cm: use bg coefficient
            branch_ratio = float(bg)
        branch_volume = stem_volume * branch_ratio
    elif s is not None and m is not None:
        # Fallback: use average of s and m
        branch_ratio = (float(s) + float(m)) / 2.0
        branch_volume = stem_volume * branch_ratio
    elif coef.get('b') is not None:
        # Fallback: approximate from b coefficient
        branch_ratio = abs(float(coef['b'])) * 0.1
        branch_volume = stem_volume * branch_ratio
    else:
        # Final fallback: 20% default
        branch_ratio = 0.2
        branch_volume = stem_volume * 0.2

    if DEBUG_VOLUME_CALC:
        _debug_log(f"BRANCH: s={s}, m={m}, bg={bg}, ratio={branch_ratio}, branch_vol={branch_volume}")

    # 3. Total tree volume
    tree_volume = stem_volume + branch_volume

    # 4. Calculate gross timber volume (Forest Regulation 2079, Section 4)
    # Formula: Gross Timber = Stem Volume - 10cm Top Stem Volume
    # NOTE: Gross timber comes ONLY from stem, branches go to firewood
    if coef.get('a1') is not None and coef.get('b1') is not None:
        cm10_dia_ratio = math.exp(coef['a1'] + coef['b1'] * math.log(dbh))
        cm10_top_volume = stem_volume * cm10_dia_ratio  # From stem only
        gross_volume = stem_volume - cm10_top_volume
        
        _debug_log(f"GROSS: a1={coef.get('a1')}, b1={coef.get('b1')}, cm10_ratio={cm10_dia_ratio}, cm10_vol={cm10_top_volume}, gross_vol={gross_volume}")
    else:
        gross_volume = stem_volume * 0.85  # Fallback: 85% merchantable
        _debug_log(f"GROSS: Using fallback 0.85, gross_vol={gross_volume}")

    # 5. Calculate net timber volume (Forest Regulation 2079, Section 5)
    # Apply waste factors based on tree class
    # Class 1: 80% net (20% waste)
    # Class 2: 60% net (40% waste)
    # Class 3: 30% net (70% waste)
    # Class 4: 0% net (100% firewood)
    if tree_class == 1:
        net_volume = gross_volume * 0.80
        waste_factor = 0.80
    elif tree_class == 2:
        net_volume = gross_volume * 0.60
        waste_factor = 0.60
    elif tree_class == 3:
        net_volume = gross_volume * 0.30
        waste_factor = 0.30
    elif tree_class == 4:
        net_volume = 0.0
        waste_factor = 0.0
    else:
        net_volume = gross_volume * 0.60  # Default to class 2
        waste_factor = 0.60

    if DEBUG_VOLUME_CALC:
        _debug_log(f"[TREE_MODEL_VOLUME] NET: class={tree_class}, waste_factor={waste_factor}, gross_vol={gross_volume}, net_vol={net_volume}")

    # 6. Calculate firewood volume
    # Firewood = All branches + Stem waste
    firewood_m3 = tree_volume - net_volume

    if DEBUG_VOLUME_CALC:
        _debug_log(f"[TREE_MODEL_VOLUME] FIREWOOD: tree_vol={tree_volume}, net_vol={net_volume}, firewood={firewood_m3}")
        _debug_log(f"[TREE_MODEL_VOLUME] FINAL: stem={stem_volume}, branch={branch_volume}, tree={tree_volume}, gross={gross_volume}, net={net_volume}, firewood={firewood_m3}")

    return {
        'stem_volume': round(stem_volume, 6),
        'branch_volume': round(branch_volume, 6),
        'tree_volume': round(tree_volume, 6),
        'gross_volume': round(gross_volume, 6),
        'net_volume': round(net_volume, 6),
        'firewood_m3': round(firewood_m3, 6)
    }


def calculate_tree_biomass(dbh: float, height: Optional[float], species: Dict[str, Any]) -> float:
    """
    Calculate above-ground biomass (AGB) for a single tree using allometric equations.

    Uses Nepal-appropriate allometric equations:
    1. Generic equation: AGB (kg) = 0.0673 × (DBH^2.7395)  [Chave et al. 2005]
    2. If height available: height adjustment for large trees

    Args:
        dbh: Diameter at breast height in centimeters
        height: Tree height in meters (optional)
        species: Species dictionary (for future species-specific coefficients)

    Returns:
        Above-ground biomass in megagrams (Mg) = metric tons
    """
    if dbh < 1.0:
        return 0.0  # Regeneration has negligible biomass

    # Calculate biomass in kilograms using Chave et al. (2005) equation
    # AGB (kg) = 0.0673 × (DBH^2.7395)
    agb_kg = 0.0673 * (dbh ** 2.7395)

    # Optional: Adjust for height if available and tree is large
    if height and height > 10 and dbh > 30:
        # Height adjustment factor (empirical for Nepal)
        height_factor = 1.0 + (height - 15) * 0.02  # +2% per meter above 15m
        height_factor = max(0.8, min(1.3, height_factor))  # Constrain to 0.8-1.3
        agb_kg *= height_factor

    # Convert kg to Mg (megagrams = metric tons)
    agb_mg = agb_kg / 1000.0

    return round(agb_mg, 4)  # 4 decimal places for precision


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
    Uses ST_Clip to clip raster to polygon boundary BEFORE extracting pixels.

    PERFORMANCE FIX: Previous version processed 99.6% wasted pixels from bounding box extent.
    New version clips raster first, reducing processing by 100x for elongated polygons.

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
        clipped_rasters AS (
            -- CRITICAL FIX: Clip raster tiles to polygon boundary FIRST
            -- This eliminates pixels outside the polygon before extraction
            SELECT ST_Clip(rast, boundary.geom, true) AS clipped_rast
            FROM rasters.canopy_height, boundary
            WHERE ST_Intersects(rast, boundary.geom)
        ),
        pixels AS (
            -- Extract pixels only from clipped rasters (already within boundary)
            SELECT (ST_PixelAsCentroids(clipped_rast, 1)).*
            FROM clipped_rasters
            WHERE clipped_rast IS NOT NULL
        )
        SELECT
            x, y, val AS height,
            ST_XMin(geom) AS min_x,
            ST_YMin(geom) AS min_y,
            ST_XMax(geom) AS max_x,
            ST_YMax(geom) AS max_y
        FROM pixels
        WHERE val IS NOT NULL
          AND val > 0
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


def assign_block_names_to_trees(
    trees: List[Dict[str, Any]],
    result_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Assign correct block names to trees via spatial join.

    Uses blocks from result_data['blocks'] with WKT geometries.
    Block name priority: block['name'] if exists, otherwise use index (Block_1, Block_2, etc.)

    Args:
        trees: List of tree dictionaries with geometry (x, y)
        result_data: Calculation result_data with 'blocks' array

    Returns:
        Trees list with correct block_name assigned
    """
    from shapely import wkt

    # Extract blocks from result_data
    blocks_data = result_data.get('blocks', [])
    if not blocks_data:
        return trees  # No blocks defined - keep existing block_name

    # Parse block polygons and names
    from shapely.geometry import shape

    block_polygons = []
    for idx, block in enumerate(blocks_data):
        # Get geometry from GeoJSON format (stored in result_data)
        block_geojson = block.get('geometry')
        if not block_geojson:
            continue

        try:
            # Convert GeoJSON to Shapely geometry
            block_geom = shape(block_geojson)

            # Use block['block_name'] if exists (from database), otherwise use index
            block_name = block.get('block_name', f"Block_{idx+1}")

            block_polygons.append({
                'geometry': block_geom,
                'name': block_name,
                'index': idx
            })
        except Exception as e:
            print(f"Warning: Could not parse block {idx}: {e}")
            continue

    if not block_polygons:
        return trees  # No valid block geometries

    # Spatial join: Assign block names to trees
    for tree in trees:
        tree_point = Point(tree['geometry'])

        # Check which block contains this tree
        for block in block_polygons:
            if block['geometry'].contains(tree_point):
                tree['block_name'] = block['name']
                break
        # If no block contains tree, keep existing block_name

    return trees


def assign_sample_plots_to_trees(
    trees: List[Dict[str, Any]],
    sampling_design: 'SamplingDesign',
    buffer_meters: float,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Assign sample plot numbers to trees and KEEP ONLY trees within plot buffers.

    Trees outside all plot buffers are discarded (not exported).
    This is because field teams only measure trees within sample plots.

    Args:
        trees: List of tree dictionaries with geometry (x, y)
        sampling_design: SamplingDesign object with sample points
        buffer_meters: Buffer distance around each plot (default: 25m)
        db: Database session

    Returns:
        FILTERED trees list - only trees within plot buffers, with sample_plot_number assigned
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

    # Assign plot numbers to each tree AND filter to keep only trees within buffers
    filtered_trees = []

    for tree in trees:
        tree_point = Point(tree['geometry'])
        intersecting_plots = []

        # Check which plot buffers this tree intersects
        for plot in plot_buffers:
            if plot['geometry'].contains(tree_point):
                intersecting_plots.append(str(plot['plot_number']))

        # Only keep trees that fall within at least one plot buffer
        if intersecting_plots:
            # Multiple plots: comma-separated
            tree['sample_plot_number'] = ','.join(intersecting_plots)
            filtered_trees.append(tree)
        # Trees outside all plot buffers are discarded (not added to filtered_trees)

    return filtered_trees


def generate_regeneration_entries(
    sampling_design: 'SamplingDesign',
    species_list: List[Dict[str, Any]],
    buffer_meters: float,
    tree_id_start: int
) -> List[Dict[str, Any]]:
    """
    Generate regeneration entries (1-9.9 cm DBH) for each sample plot.

    Per sample plot:
    - Unestablished regeneration (1-3.9 cm DBH): 2-5 species
    - Established regeneration/sapling (4-9.9 cm DBH): 1-4 species

    Regeneration entries do NOT have height_m or tree_class (field verification needed).

    Args:
        sampling_design: SamplingDesign object with sample points
        species_list: List of species dictionaries
        buffer_meters: Buffer distance around each plot
        tree_id_start: Starting tree_id number

    Returns:
        List of regeneration tree dictionaries
    """
    from geoalchemy2.shape import to_shape

    if not sampling_design.points_geometry:
        return []

    # Get sample plot points
    sample_points_geom = to_shape(sampling_design.points_geometry)
    plot_assignments = sampling_design.points_block_assignment or []

    # Create list of plot locations
    plot_locations = []
    if hasattr(sample_points_geom, 'geoms'):
        # MultiPoint
        for idx, point in enumerate(sample_points_geom.geoms):
            plot_info = next(
                (p for p in plot_assignments if p.get('point_index') == idx),
                None
            )
            plot_number = plot_info.get('plot_number', idx + 1) if plot_info else idx + 1
            plot_locations.append({
                'plot_number': plot_number,
                'center': (point.x, point.y)
            })
    else:
        # Single Point
        plot_locations.append({
            'plot_number': 1,
            'center': (sample_points_geom.x, sample_points_geom.y)
        })

    # Generate regeneration entries
    regeneration_trees = []
    tree_id = tree_id_start

    for plot in plot_locations:
        plot_number = str(plot['plot_number'])
        center_x, center_y = plot['center']

        # 1. Unestablished Regeneration (1-3.9 cm DBH): 2-5 species
        num_unestablished = random.randint(2, 5)
        for _ in range(num_unestablished):
            species = weighted_random_choice(species_list)

            # Random position within plot buffer
            angle = random.uniform(0, 2 * 3.14159)
            distance = random.uniform(0, buffer_meters / 111320.0)  # Convert to degrees
            x = center_x + distance * math.cos(angle)
            y = center_y + distance * math.sin(angle)

            regeneration_trees.append({
                'tree_id': tree_id,
                'geometry': (x, y),
                'species_scientific': species.get('scientific_name'),
                'species_local': species.get('local_name'),
                'dbh_cm': round(random.uniform(1.0, 3.9), 1),
                'height_m': None,  # Not measured for regeneration
                'tree_class': None,  # Not applicable
                'block_name': '',  # Will be assigned via spatial join
                'sample_plot_number': plot_number,
                'generated_date': datetime.now().isoformat(),
                'model_version': 'v1.0',
                'notes': 'REGENERATION (1-3.9cm DBH) - Field verification required',
            })
            tree_id += 1

        # 2. Established Regeneration/Sapling (4-9.9 cm DBH): 1-4 species
        num_established = random.randint(1, 4)
        for _ in range(num_established):
            species = weighted_random_choice(species_list)

            # Random position within plot buffer
            angle = random.uniform(0, 2 * 3.14159)
            distance = random.uniform(0, buffer_meters / 111320.0)
            x = center_x + distance * math.cos(angle)
            y = center_y + distance * math.sin(angle)

            regeneration_trees.append({
                'tree_id': tree_id,
                'geometry': (x, y),
                'species_scientific': species.get('scientific_name'),
                'species_local': species.get('local_name'),
                'dbh_cm': round(random.uniform(4.0, 9.9), 1),
                'height_m': None,  # Not measured for regeneration
                'tree_class': None,  # Not applicable
                'block_name': '',  # Will be assigned via spatial join
                'sample_plot_number': plot_number,
                'generated_date': datetime.now().isoformat(),
                'model_version': 'v1.0',
                'notes': 'SAPLING (4-9.9cm DBH) - Field verification required',
            })
            tree_id += 1

    return regeneration_trees


def export_to_gpkg(
    trees: List[Dict[str, Any]],
    calculation_id: uuid.UUID,
    output_dir: str = "exports"
) -> Tuple[str, float]:
    """
    Export trees to GPKG file using GeoPandas in REGULATION FORMAT

    Forest Regulation 2079 - Standard Format
    16 columns organized by size class with count columns

    Size Classes (based on DBH):
    - Regeneration: 1 cm <= DBH < 4 cm
    - Sapling: 4 cm <= DBH < 10 cm
    - Pole: 10 cm <= DBH < 30 cm
    - Tree: DBH >= 30 cm

    Each tree populates only its size class columns.
    Count columns default to 1 (one individual tree per row).

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
    filename = f"tree_model_{calculation_id}_{timestamp}.gpkg"
    filepath = os.path.join(output_dir, filename)

    # Create list of records - REGULATION FORMAT (16 columns)
    records = []
    fid = 1

    for tree in trees:
        dbh = tree['dbh_cm']
        species_sci = tree.get('species_scientific', '')
        height = tree.get('height_m')
        tree_class = tree.get('tree_class')

        # Get volumes (Forest Regulation 2079)
        stem_vol = tree.get('stem_volume', 0.0)
        branch_vol = tree.get('branch_volume', 0.0)
        tree_vol = tree.get('tree_volume', 0.0)
        gross_vol = tree.get('gross_volume', 0.0)
        net_vol = tree.get('net_volume', 0.0)
        firewood_vol = tree.get('firewood_m3', 0.0)

        # Initialize all columns as None
        record = {
            'fid': fid,
            'block_name': tree.get('block_name', ''),
            'sample_plot_number': tree.get('sample_plot_number', ''),
            # Regeneration columns
            'regen_species_scientific': None,
            'regen_dbh': None,
            'regen_count': None,
            # Sapling columns
            'sapling_species_scientific': None,
            'sapling_dbh_cm': None,
            'sapling_count': None,
            # Pole columns
            'pole_species_scientific': None,
            'pole_dbh_cm': None,
            'pole_height_m': None,
            'pole_class': None,
            'pole_stem_volume_m3': None,
            'pole_branch_volume_m3': None,
            'pole_tree_volume_m3': None,
            'pole_gross_volume_m3': None,
            'pole_net_volume_m3': None,
            'pole_firewood_m3': None,
            # Tree columns
            'tree_species_scientific': None,
            'tree_dbh_cm': None,
            'tree_height_m': None,
            'tree_class': None,
            'tree_stem_volume_m3': None,
            'tree_branch_volume_m3': None,
            'tree_tree_volume_m3': None,
            'tree_gross_volume_m3': None,
            'tree_net_volume_m3': None,
            'tree_firewood_m3': None,
            # Geometry
            'geometry': Point(tree['geometry'])
        }

        # Populate appropriate columns based on DBH (size class)
        # FIXED: Correct DBH thresholds for regeneration (1-3.99) and sapling (4-9.99)
        if dbh < 4:
            # Regeneration (1-3.99 cm DBH - unestablished regeneration)
            record['regen_species_scientific'] = species_sci
            record['regen_dbh'] = dbh
            record['regen_count'] = 1
        elif dbh < 10:
            # Sapling (4-9.99 cm DBH - established regeneration)
            record['sapling_species_scientific'] = species_sci
            record['sapling_dbh_cm'] = dbh
            record['sapling_count'] = 1
        elif dbh < 20:
            # Small Pole (10-19.99 cm DBH - with volumes)
            record['pole_species_scientific'] = species_sci
            record['pole_dbh_cm'] = dbh
            record['pole_height_m'] = height
            record['pole_class'] = tree_class
            record['pole_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['pole_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['pole_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['pole_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['pole_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['pole_firewood_m3'] = firewood_vol if firewood_vol > 0 else None
        elif dbh < 30:
            # Large Pole (20-29.99 cm DBH - with volumes)
            record['pole_species_scientific'] = species_sci
            record['pole_dbh_cm'] = dbh
            record['pole_height_m'] = height
            record['pole_class'] = tree_class
            record['pole_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['pole_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['pole_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['pole_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['pole_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['pole_firewood_m3'] = firewood_vol if firewood_vol > 0 else None
        else:
            # Tree (>=30 cm DBH - with volumes)
            record['tree_species_scientific'] = species_sci
            record['tree_dbh_cm'] = dbh
            record['tree_height_m'] = height
            record['tree_class'] = tree_class
            record['tree_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['tree_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['tree_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['tree_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['tree_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['tree_firewood_m3'] = firewood_vol if firewood_vol > 0 else None

        records.append(record)
        fid += 1

    # Create GeoDataFrame with regulation column order
    gdf = gpd.GeoDataFrame(records, crs='EPSG:4326')

    # Ensure column order matches regulation format (with volume columns)
    column_order = [
        'fid',
        'block_name',
        'sample_plot_number',
        'regen_species_scientific',
        'regen_dbh',
        'regen_count',
        'sapling_species_scientific',
        'sapling_dbh_cm',
        'sapling_count',
        'pole_species_scientific',
        'pole_dbh_cm',
        'pole_height_m',
        'pole_class',
        'pole_stem_volume_m3',
        'pole_branch_volume_m3',
        'pole_tree_volume_m3',
        'pole_gross_volume_m3',
        'pole_net_volume_m3',
        'pole_firewood_m3',
        'tree_species_scientific',
        'tree_dbh_cm',
        'tree_height_m',
        'tree_class',
        'tree_stem_volume_m3',
        'tree_branch_volume_m3',
        'tree_tree_volume_m3',
        'tree_gross_volume_m3',
        'tree_net_volume_m3',
        'tree_firewood_m3',
        'geometry'
    ]
    gdf = gdf[column_order]

    # Write to GPKG
    gdf.to_file(filepath, driver='GPKG', layer='tree_model')

    # Calculate file size
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    return filepath, file_size_mb


def export_to_excel(
    trees: List[Dict[str, Any]],
    calculation_id: uuid.UUID,
    db: Session = None,
    output_dir: str = "exports"
) -> Tuple[str, float]:
    """
    Export trees to Excel file (.xlsx) in REGULATION FORMAT

    Same structure as GPKG export but in Excel format for field teams.
    Includes lat/lon columns for easy coordinate reference.

    Forest Regulation 2079 - Standard Format
    16 columns + latitude/longitude for convenience

    Args:
        trees: List of tree dictionaries
        calculation_id: UUID of calculation
        db: Database session (optional, for validation enhancement)
        output_dir: Directory to save Excel files

    Returns:
        Tuple of (filepath, file_size_mb)
    """
    # Create output directory if needed
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tree_model_{calculation_id}_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)

    # Get sample plot center coordinates from sampling design
    plot_coordinates = {}
    if db is not None:
        try:
            sampling_design = db.query(SamplingDesign).filter(
                SamplingDesign.calculation_id == calculation_id
            ).first()
            
            if sampling_design and sampling_design.points_geometry:
                # Extract coordinates from MULTIPOINT geometry
                # Query uses ST_DumpPoints to get each point with its index
                query = text("""
                    SELECT 
                        (ST_DumpPoints(points_geometry)).path[1] - 1 as point_index,
                        ST_X((ST_DumpPoints(points_geometry)).geom) as lon,
                        ST_Y((ST_DumpPoints(points_geometry)).geom) as lat
                    FROM sampling_designs
                    WHERE id = :design_id
                """)
                result = db.execute(query, {"design_id": sampling_design.id})
                for row in result:
                    # point_index is 0-based, plot numbers are typically 1-based
                    plot_number = str(row[0] + 1)
                    plot_coordinates[plot_number] = (row[1], row[2])
                
                print(f"[Excel Export] Loaded {len(plot_coordinates)} plot coordinates from sampling design")
        except Exception as e:
            print(f"[Excel Export] Warning: Could not load plot coordinates: {e}")

    # Create list of records - REGULATION FORMAT (16 columns + lat/lon)
    records = []
    fid = 1

    for tree in trees:
        dbh = tree['dbh_cm']
        species_sci = tree.get('species_scientific', '')
        species_role = tree.get('species_role', 'associate')  # Get role for sorting
        height = tree.get('height_m')
        tree_class = tree.get('tree_class')
        
        # Get sample plot number for coordinate lookup
        sample_plot_num = str(tree.get('sample_plot_number', ''))
        
        # Use sample plot center coordinates instead of individual tree coordinates
        if sample_plot_num and sample_plot_num in plot_coordinates:
            lon, lat = plot_coordinates[sample_plot_num]
        else:
            # Fallback to tree's own coordinates if plot not found
            lon, lat = tree['geometry']

        # Get volumes (Forest Regulation 2079)
        stem_vol = tree.get('stem_volume', 0.0)
        branch_vol = tree.get('branch_volume', 0.0)
        tree_vol = tree.get('tree_volume', 0.0)
        gross_vol = tree.get('gross_volume', 0.0)
        net_vol = tree.get('net_volume', 0.0)
        firewood_vol = tree.get('firewood_m3', 0.0)

        # Initialize all columns
        record = {
            'fid': fid,
            'block_name': tree.get('block_name', ''),
            'block_number': tree.get('block_number', 0),
            'sample_plot_number': tree.get('sample_plot_number', ''),
            'total_sample_plots': tree.get('total_sample_plots', 0),
            # Hidden sorting column (removed before export)
            'species_role': species_role,
            # Regeneration columns
            'regen_species_scientific': None,
            'regen_dbh': None,
            'regen_count': None,
            # Sapling columns
            'sapling_species_scientific': None,
            'sapling_dbh_cm': None,
            'sapling_count': None,
            # Pole columns
            'pole_species_scientific': None,
            'pole_dbh_cm': None,
            'pole_height_m': None,
            'pole_class': None,
            'pole_stem_volume_m3': None,
            'pole_branch_volume_m3': None,
            'pole_tree_volume_m3': None,
            'pole_gross_volume_m3': None,
            'pole_net_volume_m3': None,
            'pole_firewood_m3': None,
            # Tree columns
            'tree_species_scientific': None,
            'tree_dbh_cm': None,
            'tree_height_m': None,
            'tree_class': None,
            'tree_stem_volume_m3': None,
            'tree_branch_volume_m3': None,
            'tree_tree_volume_m3': None,
            'tree_gross_volume_m3': None,
            'tree_net_volume_m3': None,
            'tree_firewood_m3': None,
            # Coordinates (for Excel convenience)
            'longitude': lon,
            'latitude': lat
        }

        # Populate appropriate columns based on DBH (size class)
        # FIXED: Correct DBH thresholds for regeneration (1-3.99) and sapling (4-9.99)
        if dbh < 4:
            # Regeneration (1-3.99 cm DBH - unestablished regeneration)
            record['regen_species_scientific'] = species_sci
            record['regen_dbh'] = dbh
            record['regen_count'] = 1
        elif dbh < 10:
            # Sapling (4-9.99 cm DBH - established regeneration)
            record['sapling_species_scientific'] = species_sci
            record['sapling_dbh_cm'] = dbh
            record['sapling_count'] = 1
        elif dbh < 20:
            # Small Pole (10-19.99 cm DBH - with volumes)
            record['pole_species_scientific'] = species_sci
            record['pole_dbh_cm'] = dbh
            record['pole_height_m'] = height
            record['pole_class'] = tree_class
            record['pole_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['pole_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['pole_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['pole_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['pole_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['pole_firewood_m3'] = firewood_vol if firewood_vol > 0 else None
        elif dbh < 30:
            # Large Pole (20-29.99 cm DBH - with volumes)
            record['pole_species_scientific'] = species_sci
            record['pole_dbh_cm'] = dbh
            record['pole_height_m'] = height
            record['pole_class'] = tree_class
            record['pole_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['pole_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['pole_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['pole_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['pole_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['pole_firewood_m3'] = firewood_vol if firewood_vol > 0 else None
        else:
            # Tree (>=30 cm DBH - with volumes)
            record['tree_species_scientific'] = species_sci
            record['tree_dbh_cm'] = dbh
            record['tree_height_m'] = height
            record['tree_class'] = tree_class
            record['tree_stem_volume_m3'] = stem_vol if stem_vol > 0 else None
            record['tree_branch_volume_m3'] = branch_vol if branch_vol > 0 else None
            record['tree_tree_volume_m3'] = tree_vol if tree_vol > 0 else None
            record['tree_gross_volume_m3'] = gross_vol if gross_vol > 0 else None
            record['tree_net_volume_m3'] = net_vol if net_vol > 0 else None
            record['tree_firewood_m3'] = firewood_vol if firewood_vol > 0 else None

        records.append(record)
        fid += 1

    # Create DataFrame with regulation column order
    df = pd.DataFrame(records)

    # SORTING LOGIC - Sort by importance before export
    # Convert sample_plot_number to numeric for proper sorting (1, 2, 3... not 1, 10, 11, 2)
    df['sample_plot_number_numeric'] = pd.to_numeric(df['sample_plot_number'], errors='coerce').fillna(999999)

    # Add serial numbers (SN) for each category that reset per sample plot
    # Initialize SN columns
    df['regen_sn'] = None
    df['sapling_sn'] = None
    df['pole_sn'] = None
    df['tree_sn'] = None

    # Calculate serial numbers per plot per category
    for plot_num in df['sample_plot_number'].unique():
        plot_mask = df['sample_plot_number'] == plot_num

        # Regeneration SN (reset per plot)
        regen_mask = plot_mask & df['regen_species_scientific'].notna()
        if regen_mask.any():
            df.loc[regen_mask, 'regen_sn'] = range(1, regen_mask.sum() + 1)

        # Sapling SN (reset per plot)
        sapling_mask = plot_mask & df['sapling_species_scientific'].notna()
        if sapling_mask.any():
            df.loc[sapling_mask, 'sapling_sn'] = range(1, sapling_mask.sum() + 1)

        # Pole SN (reset per plot)
        pole_mask = plot_mask & df['pole_species_scientific'].notna()
        if pole_mask.any():
            df.loc[pole_mask, 'pole_sn'] = range(1, pole_mask.sum() + 1)

        # Tree SN (reset per plot)
        tree_mask = plot_mask & df['tree_species_scientific'].notna()
        if tree_mask.any():
            df.loc[tree_mask, 'tree_sn'] = range(1, tree_mask.sum() + 1)

    # Define species role priority (dominant first, rare last)
    role_priority = {
        'dominant': 1,
        'co-dominant': 2,
        'associate': 3,
        'occasional': 4,
        'rare': 5
    }
    df['role_priority'] = df['species_role'].map(role_priority).fillna(3)  # Default to associate

    # Get species columns for sorting (whichever is not None)
    df['species_for_sorting'] = (
        df['tree_species_scientific'].fillna('') +
        df['pole_species_scientific'].fillna('') +
        df['sapling_species_scientific'].fillna('') +
        df['regen_species_scientific'].fillna('')
    )

    # COMPACT FORMAT: Sort BEFORE merge by sample_plot_number, then regen_sn, sapling_sn, pole_sn, tree_sn
    # This groups rows so that after merge, they consolidate properly
    # Use numeric sorting to match Excel's "Sort anything that looks like a number, as a number"
    df['_s1'] = pd.to_numeric(df['sample_plot_number'], errors='coerce').fillna(999999)
    df['_s2'] = pd.to_numeric(df['regen_sn'], errors='coerce').fillna(999999)
    df['_s3'] = pd.to_numeric(df['sapling_sn'], errors='coerce').fillna(999999)
    df['_s4'] = pd.to_numeric(df['pole_sn'], errors='coerce').fillna(999999)
    df['_s5'] = pd.to_numeric(df['tree_sn'], errors='coerce').fillna(999999)
    
    df = df.sort_values(by=['_s1', '_s2', '_s3', '_s4', '_s5'])
    df = df.drop(columns=['_s1', '_s2', '_s3', '_s4', '_s5'])

    # Use min_sn as merge key to combine different size classes with same SN
    df['min_sn'] = df[['tree_sn', 'pole_sn', 'sapling_sn', 'regen_sn']].min(axis=1)
    df['merge_key'] = df['sample_plot_number'].astype(str) + '_' + df['min_sn'].astype(str)
    
    # Define aggregation functions - take first non-null value for each column
    agg_dict = {
        'fid': 'first',  # Will reassign later
        'block_name': 'first',
        'sample_plot_number': 'first',
        'block_number': 'first',
        'total_sample_plots': 'first',
        'longitude': 'first',
        'latitude': 'first',
        # Regeneration columns
        'regen_sn': 'first',
        'regen_species_scientific': 'first',
        'regen_dbh': 'first',
        'regen_count': 'first',
        # Sapling columns
        'sapling_sn': 'first',
        'sapling_species_scientific': 'first',
        'sapling_dbh_cm': 'first',
        'sapling_count': 'first',
        # Pole columns
        'pole_sn': 'first',
        'pole_species_scientific': 'first',
        'pole_dbh_cm': 'first',
        'pole_height_m': 'first',
        'pole_class': 'first',
        # Pole volumes
        'pole_stem_volume_m3': 'first',
        'pole_branch_volume_m3': 'first',
        'pole_tree_volume_m3': 'first',
        'pole_gross_volume_m3': 'first',
        'pole_net_volume_m3': 'first',
        'pole_firewood_m3': 'first',
        # Tree columns
        'tree_sn': 'first',
        'tree_species_scientific': 'first',
        'tree_dbh_cm': 'first',
        'tree_height_m': 'first',
        'tree_class': 'first',
        # Tree volumes
        'tree_stem_volume_m3': 'first',
        'tree_branch_volume_m3': 'first',
        'tree_tree_volume_m3': 'first',
        'tree_gross_volume_m3': 'first',
        'tree_net_volume_m3': 'first',
        'tree_firewood_m3': 'first',
    }
    
    # Group by merge_key and aggregate
    df = df.groupby('merge_key', as_index=False).agg(agg_dict)
    
    # FINAL SORT: After groupby, sort by sample_plot_number, regen_sn, sapling_sn, pole_sn, tree_sn numerically
    df['_s1'] = pd.to_numeric(df['sample_plot_number'], errors='coerce').fillna(999999)
    df['_s2'] = pd.to_numeric(df['regen_sn'], errors='coerce').fillna(999999)
    df['_s3'] = pd.to_numeric(df['sapling_sn'], errors='coerce').fillna(999999)
    df['_s4'] = pd.to_numeric(df['pole_sn'], errors='coerce').fillna(999999)
    df['_s5'] = pd.to_numeric(df['tree_sn'], errors='coerce').fillna(999999)
    df = df.sort_values(by=['_s1', '_s2', '_s3', '_s4', '_s5']).drop(columns=['_s1', '_s2', '_s3', '_s4', '_s5'])
    
    # Drop temporary columns (use errors='ignore' in case column doesn't exist)
    cols_to_drop = [col for col in ['merge_key', 'sample_plot_number_numeric'] if col in df.columns]
    df = df.drop(columns=cols_to_drop)

    # Reset index and reassign fid sequentially
    df = df.reset_index(drop=True)
    df['fid'] = range(1, len(df) + 1)

    # Column order for Tree Model sheet (original format - NO volume columns)
    tree_model_column_order = [
        'fid',
        'block_name',
        'sample_plot_number',
        'longitude',
        'latitude',
        'regen_sn',
        'regen_species_scientific',
        'regen_dbh',
        'regen_count',
        'sapling_sn',
        'sapling_species_scientific',
        'sapling_dbh_cm',
        'sapling_count',
        'pole_sn',
        'pole_species_scientific',
        'pole_dbh_cm',
        'pole_height_m',
        'pole_class',
        'tree_sn',
        'tree_species_scientific',
        'tree_dbh_cm',
        'tree_height_m',
        'tree_class',
    ]
    
    # REMOVE EMPTY ROWS (rows with no species data in any category)
    # A row is empty if all species columns are None/NaN
    has_species_data = (
        df['regen_species_scientific'].notna() |
        df['sapling_species_scientific'].notna() |
        df['pole_species_scientific'].notna() |
        df['tree_species_scientific'].notna()
    )
    df = df[has_species_data].reset_index(drop=True)

    # Reassign FID after removing empty rows
    df['fid'] = range(1, len(df) + 1)

    # DBH columns - keep full precision for Field Inventory recalculation
    # Round DBH and Height to 6 decimal places (preserves precision for volume calculation)
    # DBH and Height columns - keep original precision from tree generation
    # Tree Model calculates these with full precision (DBH rounded to 1 decimal, height to 1 decimal)
    # Field Inventory will use pre-calculated volume columns from Excel instead of recalculating
    
    # Filter to only include columns that exist in df
    tree_model_column_order = [col for col in tree_model_column_order if col in df.columns]
    df_tree_model = df[tree_model_column_order]

    # Column order for Volumes sheet (includes block_number and total_sample_plots)
    volumes_column_order = [
        'fid',
        'block_name',
        'block_number',
        'sample_plot_number',
        'total_sample_plots',
        'pole_species_scientific',
        'pole_dbh_cm',
        'pole_height_m',
        'pole_class',
        'pole_stem_volume_m3',
        'pole_branch_volume_m3',
        'pole_tree_volume_m3',
        'pole_gross_volume_m3',
        'pole_net_volume_m3',
        'pole_firewood_m3',
        'tree_species_scientific',
        'tree_dbh_cm',
        'tree_height_m',
        'tree_class',
        'tree_stem_volume_m3',
        'tree_branch_volume_m3',
        'tree_tree_volume_m3',
        'tree_gross_volume_m3',
        'tree_net_volume_m3',
        'tree_firewood_m3',
    ]
    
    volumes_column_order = [col for col in volumes_column_order if col in df.columns]
    df_volumes = df[volumes_column_order]
    
    # Write to Excel - optimized for speed
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Sheet 1: Tree Model (original format)
        df_tree_model.to_excel(writer, sheet_name='Tree Model', index=False)
        
        # Sheet 2: Volumes (for verification) - includes block_number and total_sample_plots
        df_volumes.to_excel(writer, sheet_name='Volumes', index=False)
    
    # Set fixed column widths for faster processing
    from openpyxl import load_workbook
    wb = load_workbook(filepath)
    
    # Set fixed column widths (faster than calculating)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for col in ws.columns:
            col_letter = col[0].column_letter
            # Use reasonable fixed widths
            ws.column_dimensions[col_letter].width = 15
    
    wb.save(filepath)

    # Calculate file size
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    # Add validation enhancement if database session provided
    if db is not None:
        try:
            from .excel_validator import add_validation_to_excel
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Adding validation to Excel file...")
            filepath, file_size_mb = add_validation_to_excel(filepath, db)
            logger.info(f"Validation added successfully! New size: {file_size_mb:.2f} MB")
        except Exception as e:
            # Log error but don't fail the export
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to add validation to Excel: {e}")
            logger.error(traceback.format_exc())
            print(f"ERROR: Could not add validation to Excel: {e}")
            traceback.print_exc()
            # Continue with basic Excel export
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Database session not provided - skipping Excel validation enhancement")

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
        'plot_buffer_meters': 12.62  # Default buffer for sample plot assignment (radius for 500m² plot)
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

    # FILTER: Only use tree species (exclude herbs, shrubs, non-woody plants)
    # Tree species have wood/timber/fuel/fodder uses
    tree_species_only = [
        sp for sp in species_list
        if sp.get('is_tree_species', True)  # Default TRUE for backward compatibility
    ]

    if not tree_species_only:
        raise ValueError(
            f"No tree species found in calculation. "
            f"Found {len(species_list)} total species, but none are classified as trees. "
            f"Tree species must have wood, timber, fuel, or fodder uses."
        )

    # Log species filtering for transparency
    if len(tree_species_only) < len(species_list):
        non_tree_count = len(species_list) - len(tree_species_only)
        print(f"INFO: Filtered out {non_tree_count} non-tree species (herbs, shrubs). "
              f"Using {len(tree_species_only)} tree species for model generation.")

    # Use filtered tree species for tree model generation
    species_list = tree_species_only

    forest_type = result_data.get('forest_type', {}).get('dominant_type', 'Unknown')
    area_hectares = result_data.get('area', {}).get('hectares', 0)

    # Step 1.2: Load species coefficients for volume calculations
    report(11, "Loading species coefficients")
    species_coefficients = {}

    # Load species coefficients from database
    from sqlalchemy import text as sql_text
    coef_query = sql_text("""
        SELECT scientific_name, a, b, c, s, m, a1, b1
        FROM tree_species_coefficients
    """)
    coef_result = db.execute(coef_query)
    for row in coef_result:
        species_coefficients[row.scientific_name] = {
            'a': row.a,
            'b': row.b,
            'c': row.c,
            's': row.s,
            'm': row.m,
            'a1': row.a1,
            'b1': row.b1
        }

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

        # Determine trees per hectare (use user's configured max density)
        trees_per_ha = get_tree_density(canopy_height, forest_type, config['max_trees_per_ha'])
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

            # Calculate volumes using Forest Regulation 2079 formulas
            volumes = {'stem_volume': 0.0, 'branch_volume': 0.0, 'tree_volume': 0.0,
                      'gross_volume': 0.0, 'net_volume': 0.0, 'firewood_m3': 0.0}

            scientific_name = species.get('scientific_name')
            if scientific_name and scientific_name in species_coefficients:
                volumes = calculate_tree_volumes(
                    dbh=dbh,
                    height=tree_height,
                    tree_class=tree_class,
                    species_coefficients=species_coefficients[scientific_name]
                )

            # Create tree record
            trees.append({
                'tree_id': tree_id,
                'geometry': (x, y),
                'species_code': species.get('species_code'),
                'species_scientific': scientific_name,
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
                'sample_plot_number': None,  # Will be assigned later
                # Volume calculations (Forest Regulation 2079)
                'stem_volume': volumes['stem_volume'],
                'branch_volume': volumes['branch_volume'],
                'tree_volume': volumes['tree_volume'],
                'gross_volume': volumes['gross_volume'],
                'net_volume': volumes['net_volume'],
                'firewood_m3': volumes['firewood_m3']
            })
            tree_id += 1

    if not trees:
        raise ValueError("No trees generated within sample plot buffers - try increasing buffer distance or check sampling design")

    # Step 3.5: Spatial join - Assign correct block names to trees
    report(75, "Assigning block names via spatial join")
    trees = assign_block_names_to_trees(trees, result_data)

    # Step 4: Assign sample plot numbers to trees and FILTER (keep only trees within buffers)
    report(80, "Filtering trees to sample plots")
    total_trees_generated = len(trees)

    trees = assign_sample_plots_to_trees(
        trees=trees,
        sampling_design=sampling_design,
        buffer_meters=config['plot_buffer_meters'],
        db=db
    )

    trees_in_plots = len(trees)
    report(85, f"Kept {trees_in_plots} trees from {total_trees_generated} generated (within plot buffers)")

    # Step 4.5: Generate regeneration entries (1-10 cm DBH) for each sample plot
    report(87, "Generating regeneration entries")
    regeneration_entries = generate_regeneration_entries(
        sampling_design=sampling_design,
        species_list=species_list,
        buffer_meters=config['plot_buffer_meters'],
        tree_id_start=tree_id
    )

    # Assign block names to regeneration entries
    regeneration_entries = assign_block_names_to_trees(regeneration_entries, result_data)

    # Add regeneration to main tree list
    regeneration_count = len(regeneration_entries)
    trees.extend(regeneration_entries)
    report(88, f"Added {regeneration_count} regeneration entries to sample plots")

    # Step 5: Export to GPKG and Excel
    report(90, "Exporting to GPKG file")
    gpkg_filepath, gpkg_size_mb = export_to_gpkg(trees, calculation_id)

    # Add block number and total sample plots to each tree for Excel export
    # Get unique blocks and assign block numbers
    unique_blocks = list(dict.fromkeys(t.get('block_name', '') for t in trees if t.get('block_name')))
    block_to_number = {block: idx + 1 for idx, block in enumerate(unique_blocks)}
    
    # Count plots per block
    plots_per_block = {}
    for tree in trees:
        block_name = tree.get('block_name', 'Unknown')
        plot_num = tree.get('sample_plot_number')
        if plot_num and block_name:
            if block_name not in plots_per_block:
                plots_per_block[block_name] = set()
            for pn in str(plot_num).split(','):
                plots_per_block[block_name].add(pn.strip())
    
    # Add block_number and total_sample_plots to each tree
    for tree in trees:
        block_name = tree.get('block_name', '')
        tree['block_number'] = block_to_number.get(block_name, 0)
        tree['total_sample_plots'] = len(plots_per_block.get(block_name, set()))

    report(93, "Exporting to Excel file")
    excel_filepath, excel_size_mb = export_to_excel(trees, calculation_id, db=db)

    # Step 6: Calculate statistics (separate mature trees from regeneration)
    report(97, "Calculating statistics")

    # Separate mature trees (DBH >= 10cm) from regeneration (DBH < 10cm)
    mature_trees = [t for t in trees if t['dbh_cm'] >= 10]
    regeneration_trees = [t for t in trees if t['dbh_cm'] < 10]
    unestablished = [t for t in regeneration_trees if t['dbh_cm'] < 4]
    established = [t for t in regeneration_trees if t['dbh_cm'] >= 4]

    # Calculate effective sampling area (plot buffer area × number of plots)
    plot_area_m2 = 3.14159 * (config['plot_buffer_meters'] ** 2)  # π * r²
    total_plot_area_ha = (plot_area_m2 * sampling_design.total_points) / 10000.0

    # Statistics for mature trees only (heights only measured for mature trees)
    dbhs_mature = [t['dbh_cm'] for t in mature_trees] if mature_trees else [0]
    heights_mature = [t['height_m'] for t in mature_trees if t.get('height_m') is not None]
    if not heights_mature:
        heights_mature = [0]

    # DBH Class distribution per forest block
    # Group trees by block_name
    trees_by_block = {}
    for tree in trees:
        block_name = tree.get('block_name', 'Unknown')
        if block_name not in trees_by_block:
            trees_by_block[block_name] = []
        trees_by_block[block_name].append(tree)

    # Count plots per block (from sample_plot_number assignments)
    plots_per_block = {}
    for tree in trees:
        block_name = tree.get('block_name', 'Unknown')
        plot_num = tree.get('sample_plot_number')
        if plot_num:
            if block_name not in plots_per_block:
                plots_per_block[block_name] = set()
            # Handle comma-separated plot numbers
            for pn in str(plot_num).split(','):
                plots_per_block[block_name].add(pn.strip())

    # Calculate DBH class distribution per block
    block_dbh_distribution = {}
    for block_name, block_trees in trees_by_block.items():
        num_plots_in_block = len(plots_per_block.get(block_name, set())) or 1  # Avoid division by zero

        dbh_counts = {
            'unestablished_regen': len([t for t in block_trees if 1 <= t['dbh_cm'] < 4]),
            'established_regen': len([t for t in block_trees if 4 <= t['dbh_cm'] < 10]),
            'small_pole': len([t for t in block_trees if 10 <= t['dbh_cm'] < 20]),
            'large_pole': len([t for t in block_trees if 20 <= t['dbh_cm'] < 30]),
            'small_tree': len([t for t in block_trees if 30 <= t['dbh_cm'] < 40]),
            'medium_tree': len([t for t in block_trees if 40 <= t['dbh_cm'] < 50]),
            'large_tree': len([t for t in block_trees if 50 <= t['dbh_cm'] < 60]),
            'very_large_tree': len([t for t in block_trees if t['dbh_cm'] >= 60]),
        }

        # Average per plot for this block
        avg_regen = dbh_counts['unestablished_regen'] / num_plots_in_block
        avg_sapling = dbh_counts['established_regen'] / num_plots_in_block
        avg_pole = (dbh_counts['small_pole'] + dbh_counts['large_pole']) / num_plots_in_block
        avg_tree = (dbh_counts['small_tree'] + dbh_counts['medium_tree'] +
                    dbh_counts['large_tree'] + dbh_counts['very_large_tree']) / num_plots_in_block

        # Simplified 4-class system with per-hectare conversion
        # Expansion factors: Regeneration×1000, Sapling×400, Pole×100, Tree×20
        dbh_per_ha = {
            'regeneration_1_4cm': round(avg_regen * 1000, 1),  # Regeneration per ha
            'sapling_4_10cm': round(avg_sapling * 400, 1),      # Sapling per ha
            'pole_10_30cm': round(avg_pole * 100, 1),           # Pole per ha
            'tree_above_30cm': round(avg_tree * 20, 1),         # Tree per ha
        }

        # Calculate volumes per block (Forest Regulation 2079)
        # Separate pole (DBH 10-30cm) and tree (DBH >30cm) volumes
        pole_trees = [t for t in block_trees if 10 <= t.get('dbh_cm', 0) < 30]
        tree_trees = [t for t in block_trees if t.get('dbh_cm', 0) >= 30]

        # Pole volumes
        pole_net_volume = sum(t.get('net_volume', 0.0) for t in pole_trees)
        pole_firewood = sum(t.get('firewood_m3', 0.0) for t in pole_trees)
        
        # Tree volumes
        tree_net_volume = sum(t.get('net_volume', 0.0) for t in tree_trees)
        tree_firewood = sum(t.get('firewood_m3', 0.0) for t in tree_trees)

        # Total volumes
        total_stem_volume = sum(t.get('stem_volume', 0.0) for t in block_trees)
        total_branch_volume = sum(t.get('branch_volume', 0.0) for t in block_trees)
        total_tree_volume = sum(t.get('tree_volume', 0.0) for t in block_trees)
        total_gross_volume = sum(t.get('gross_volume', 0.0) for t in block_trees)
        total_net_volume = sum(t.get('net_volume', 0.0) for t in block_trees)
        total_firewood = sum(t.get('firewood_m3', 0.0) for t in block_trees)

        # Calculate per-hectare using plot factors (matching field inventory method)
        # Pole: plot factor 100, Tree: plot factor 20
        # Formula: volume_per_ha = (total_volume / num_plots) * plot_factor
        if num_plots_in_block > 0:
            # Calculate average per plot first, then multiply by factor
            pole_timber_per_ha = (pole_net_volume / num_plots_in_block) * 100
            pole_firewood_per_ha = (pole_firewood / num_plots_in_block) * 100
            tree_timber_per_ha = (tree_net_volume / num_plots_in_block) * 20
            tree_firewood_per_ha = (tree_firewood / num_plots_in_block) * 20
            
            # Legacy calculation for comparison
            plot_buffer_m = config.get('plot_buffer_meters', 10)
            plot_area_ha = (3.14159 * (plot_buffer_m ** 2)) / 10000.0
            total_sampled_area_ha = plot_area_ha * num_plots_in_block
            
            stem_volume_per_ha = total_stem_volume / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
            branch_volume_per_ha = total_branch_volume / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
            tree_volume_per_ha = total_tree_volume / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
            gross_volume_per_ha = total_gross_volume / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
            net_volume_per_ha = total_net_volume / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
            firewood_per_ha = total_firewood / total_sampled_area_ha if total_sampled_area_ha > 0 else 0
        else:
            pole_timber_per_ha = 0.0
            pole_firewood_per_ha = 0.0
            tree_timber_per_ha = 0.0
            tree_firewood_per_ha = 0.0
            stem_volume_per_ha = 0.0
            branch_volume_per_ha = 0.0
            tree_volume_per_ha = 0.0
            gross_volume_per_ha = 0.0
            net_volume_per_ha = 0.0
            firewood_per_ha = 0.0

        # Total growing stock (timber only) = pole timber + tree timber
        total_growing_stock = pole_timber_per_ha + tree_timber_per_ha
        
        # Total volume (timber + firewood)
        total_volume_per_ha = pole_timber_per_ha + pole_firewood_per_ha + tree_timber_per_ha + tree_firewood_per_ha

        block_dbh_distribution[block_name] = {
            'total_trees': len(block_trees),
            'num_plots': num_plots_in_block,
            'dbh_per_ha': dbh_per_ha,  # Per hectare values
            # Volume totals (Forest Regulation 2079)
            'stem_volume_m3': round(total_stem_volume, 2),
            'branch_volume_m3': round(total_branch_volume, 2),
            'tree_volume_m3': round(total_tree_volume, 2),
            'gross_volume_m3': round(total_gross_volume, 2),
            'net_volume_m3': round(total_net_volume, 2),
            'firewood_m3': round(total_firewood, 2),
            # Per-hectare values (legacy method - total volume / sampled area)
            'stem_volume_per_ha': round(stem_volume_per_ha, 2),
            'branch_volume_per_ha': round(branch_volume_per_ha, 2),
            'tree_volume_per_ha': round(tree_volume_per_ha, 2),
            'gross_volume_per_ha': round(gross_volume_per_ha, 2),
            'net_volume_per_ha': round(net_volume_per_ha, 2),
            'firewood_per_ha': round(firewood_per_ha, 2),
            # Per-hectare values (matching field inventory method - plot factor)
            'pole_timber_m3_per_ha': round(pole_timber_per_ha, 2),
            'pole_firewood_m3_per_ha': round(pole_firewood_per_ha, 2),
            'tree_timber_m3_per_ha': round(tree_timber_per_ha, 2),
            'tree_firewood_m3_per_ha': round(tree_firewood_per_ha, 2),
            # Total growing stock (pole timber + tree timber)
            'total_growing_stock_m3_per_ha': round(total_growing_stock, 2),
            # Total volume (timber + firewood) - for UI display
            'volume_per_ha': round(total_volume_per_ha, 2),
        }

    # Calculate overall volume totals (Forest Regulation 2079)
    # Calculate overall volume totals with pole/tree breakdown
    pole_trees_all = [t for t in trees if 10 <= t.get('dbh_cm', 0) < 30]
    tree_trees_all = [t for t in trees if t.get('dbh_cm', 0) >= 30]
    
    total_stem_volume_all = sum(t.get('stem_volume', 0.0) for t in trees)
    total_branch_volume_all = sum(t.get('branch_volume', 0.0) for t in trees)
    total_tree_volume_all = sum(t.get('tree_volume', 0.0) for t in trees)
    total_gross_volume_all = sum(t.get('gross_volume', 0.0) for t in trees)
    total_net_volume_all = sum(t.get('net_volume', 0.0) for t in trees)
    total_firewood_all = sum(t.get('firewood_m3', 0.0) for t in trees)
    
    # Pole/tree breakdown using plot factor method
    total_pole_net = sum(t.get('net_volume', 0.0) for t in pole_trees_all)
    total_pole_firewood = sum(t.get('firewood_m3', 0.0) for t in pole_trees_all)
    total_tree_net = sum(t.get('net_volume', 0.0) for t in tree_trees_all)
    total_tree_firewood = sum(t.get('firewood_m3', 0.0) for t in tree_trees_all)
    
    # Calculate per hectare using plot factors
    if sampling_design.total_points > 0:
        avg_pole_net_per_plot = total_pole_net / sampling_design.total_points
        avg_pole_firewood_per_plot = total_pole_firewood / sampling_design.total_points
        avg_tree_net_per_plot = total_tree_net / sampling_design.total_points
        avg_tree_firewood_per_plot = total_tree_firewood / sampling_design.total_points
        
        pole_timber_per_ha_all = avg_pole_net_per_plot * 100
        pole_firewood_per_ha_all = avg_pole_firewood_per_plot * 100
        tree_timber_per_ha_all = avg_tree_net_per_plot * 20
        tree_firewood_per_ha_all = avg_tree_firewood_per_plot * 20
    else:
        pole_timber_per_ha_all = 0
        pole_firewood_per_ha_all = 0
        tree_timber_per_ha_all = 0
        tree_firewood_per_ha_all = 0
    
    total_growing_stock_all = pole_timber_per_ha_all + tree_timber_per_ha_all
    total_volume_per_ha_all = pole_timber_per_ha_all + pole_firewood_per_ha_all + tree_timber_per_ha_all + tree_firewood_per_ha_all

    statistics = {
        'total_trees': len(trees),
        'total_trees_generated': total_trees_generated,  # Before filtering
        'trees_filtered_out': total_trees_generated - len(trees),
        'mature_trees': len(mature_trees),  # DBH >= 10cm
        'regeneration_total': len(regeneration_trees),  # DBH < 10cm
        'regeneration_unestablished': len(unestablished),  # 1-4cm
        'regeneration_established': len(established),  # 4-10cm
        'area_hectares': area_hectares,  # Total forest area
        'sampling_area_hectares': total_plot_area_ha,  # Area within plot buffers
        'trees_per_hectare': len(mature_trees) / total_plot_area_ha if total_plot_area_ha > 0 else 0,
        'regeneration_per_hectare': len(regeneration_trees) / total_plot_area_ha if total_plot_area_ha > 0 else 0,
        'min_dbh_cm': min(dbhs_mature),
        'max_dbh_cm': max(dbhs_mature),
        'mean_dbh_cm': sum(dbhs_mature) / len(dbhs_mature) if dbhs_mature else 0,
        'min_height_m': min(heights_mature),
        'max_height_m': max(heights_mature),
        'mean_height_m': sum(heights_mature) / len(heights_mature) if heights_mature else 0,
        'species_count': len(set(t['species_scientific'] for t in trees if t.get('species_scientific'))),
        'plot_buffer_meters': config['plot_buffer_meters'],
        'total_sample_plots': sampling_design.total_points,
        # Volume totals (Forest Regulation 2079)
        'total_stem_volume_m3': round(total_stem_volume_all, 2),
        'total_branch_volume_m3': round(total_branch_volume_all, 2),
        'total_tree_volume_m3': round(total_tree_volume_all, 2),
        'total_gross_volume_m3': round(total_gross_volume_all, 2),
        'total_net_volume_m3': round(total_net_volume_all, 2),
        'total_firewood_m3': round(total_firewood_all, 2),
        # Per-hectare values (legacy method - total volume / sampled area)
        'stem_volume_per_ha': round(total_stem_volume_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        'branch_volume_per_ha': round(total_branch_volume_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        'tree_volume_per_ha': round(total_tree_volume_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        'gross_volume_per_ha': round(total_gross_volume_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        'net_volume_per_ha': round(total_net_volume_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        'firewood_per_ha': round(total_firewood_all / total_plot_area_ha, 2) if total_plot_area_ha > 0 else 0,
        # Per-hectare values (matching field inventory method - plot factor)
        'pole_timber_m3_per_ha': round(pole_timber_per_ha_all, 2),
        'pole_firewood_m3_per_ha': round(pole_firewood_per_ha_all, 2),
        'tree_timber_m3_per_ha': round(tree_timber_per_ha_all, 2),
        'tree_firewood_m3_per_ha': round(tree_firewood_per_ha_all, 2),
        # Total growing stock (pole timber + tree timber)
        'total_growing_stock_m3_per_ha': round(total_growing_stock_all, 2),
        # Total volume (timber + firewood)
        'volume_per_ha': round(total_volume_per_ha_all, 2),
        'block_dbh_distribution': block_dbh_distribution,  # Block-wise DBH class distribution
    }

    processing_time = (datetime.now() - start_time).total_seconds()

    report(100, "Complete")

    return {
        'gpkg_filepath': gpkg_filepath,
        'gpkg_filename': os.path.basename(gpkg_filepath),
        'gpkg_size_mb': gpkg_size_mb,
        'excel_filepath': excel_filepath,
        'excel_filename': os.path.basename(excel_filepath),
        'excel_size_mb': excel_size_mb,
        # Legacy compatibility (points to GPKG)
        'filepath': gpkg_filepath,
        'filename': os.path.basename(gpkg_filepath),
        'file_size_mb': gpkg_size_mb,
        'statistics': statistics,
        'processing_time_seconds': int(processing_time),
        'config': config
    }
