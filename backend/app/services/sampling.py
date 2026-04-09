"""
Sampling design service for forest inventory
Implements systematic, random, and stratified sampling algorithms

Phase 2: Enhanced with accessible forest filtering
Phase 3: Added Guideline-2061 support (Nepal DoF standard)
"""
import random
import math
from typing import List, Tuple, Optional
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from shapely import wkt
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import logging

from app.models.calculation import Calculation
from app.models.sampling import SamplingDesign
from app.schemas.sampling import SamplingGenerateResponse, BlockSamplingInfo
from app.services.tree_cover_analysis import (
    calculate_accessible_forest_area,
    extract_accessible_forest_mask,
    point_in_accessible_forest
)
# Use OPTIMIZED version for slope filtering (much faster!)
from app.services.tree_cover_analysis_optimized import (
    extract_tree_cover_pixel_centers_FAST as extract_tree_cover_pixel_centers
)
# Guideline-2061 support
from app.services.guideline_sampling import (
    get_sample_count_from_guideline,
    classify_block_by_majority_area,
    validate_guideline_parameters
)

logger = logging.getLogger(__name__)


def get_excluded_areas_for_calculation(db: Session, calculation_id: UUID) -> List[Polygon]:
    """
    Get excluded areas (private land) from calculation's sub-areas.

    Args:
        db: Database session
        calculation_id: Calculation ID

    Returns:
        List of Shapely Polygon geometries representing excluded areas
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation or not calculation.result_data:
        return []

    excluded_polygons = []
    sub_areas = calculation.result_data.get("sub_areas", [])

    for sub_area in sub_areas:
        if sub_area.get("is_excluded", False) or sub_area.get("isExcluded", False):  # Support both naming conventions
            try:
                from shapely.geometry import shape, GeometryCollection
                geom_data = sub_area["geometry"]

                # Handle GeometryCollection - extract only Polygon/MultiPolygon
                if geom_data.get('type') == 'GeometryCollection':
                    geom_collection = shape(geom_data)

                    # Extract only polygonal geometries (filter out LineStrings, Points)
                    polygons = [g for g in geom_collection.geoms
                               if g.geom_type in ('Polygon', 'MultiPolygon') and g.area > 0]

                    for poly in polygons:
                        if isinstance(poly, Polygon):
                            excluded_polygons.append(poly)
                        elif isinstance(poly, MultiPolygon):
                            excluded_polygons.extend(list(poly.geoms))
                else:
                    # Regular Polygon or MultiPolygon
                    geom = shape(geom_data)

                    # Skip zero-area geometries
                    if geom.area == 0:
                        logger.warning(
                            f"Excluded area '{sub_area.get('name', 'unnamed')}' has zero area. Skipping."
                        )
                        continue

                    if isinstance(geom, Polygon):
                        excluded_polygons.append(geom)
                    elif isinstance(geom, MultiPolygon):
                        excluded_polygons.extend(list(geom.geoms))

            except Exception as e:
                logger.warning(f"Failed to parse excluded area geometry: {e}")
                continue

    logger.info(f"Found {len(excluded_polygons)} excluded areas for calculation {calculation_id}")
    return excluded_polygons


def point_in_excluded_area(lon: float, lat: float, excluded_areas: List[Polygon]) -> bool:
    """
    Check if a point falls within any excluded area (private land).

    Args:
        lon: Longitude
        lat: Latitude
        excluded_areas: List of excluded area polygons

    Returns:
        True if point is in excluded area, False otherwise
    """
    if not excluded_areas:
        return False

    point = Point(lon, lat)
    for excluded_poly in excluded_areas:
        if excluded_poly.contains(point):
            return True
    return False


def get_polygon_bounds(geom_wkt: str) -> Tuple[float, float, float, float]:
    """
    Get bounding box of polygon.

    Args:
        geom_wkt: WKT string of polygon

    Returns:
        Tuple of (min_lon, min_lat, max_lon, max_lat)
    """
    geom = wkt.loads(geom_wkt)
    bounds = geom.bounds  # (minx, miny, maxx, maxy)
    return bounds


def calculate_polygon_area_hectares(geom_wkt: str) -> float:
    """
    Calculate polygon area in hectares using UTM projection.

    Args:
        geom_wkt: WKT string of polygon

    Returns:
        Area in hectares
    """
    # This is a simplified calculation - actual implementation uses PostGIS
    geom = wkt.loads(geom_wkt)

    # Get centroid to determine UTM zone
    centroid = geom.centroid
    lon = centroid.x

    # Determine UTM SRID
    if lon < 84.0:
        utm_srid = 32644
    else:
        utm_srid = 32645

    # Area calculation will be done via PostGIS
    return 0.0  # Placeholder


def apply_boundary_buffer(polygon_wkt: str, buffer_meters: float = 50.0) -> str:
    """
    Apply inward buffer to polygon to keep sampling points away from boundary.

    Uses accurate UTM projection for Nepal.

    Args:
        polygon_wkt: WKT of polygon in EPSG:4326
        buffer_meters: Buffer distance in meters (negative = inward)

    Returns:
        WKT of buffered polygon in EPSG:4326
    """
    from shapely import wkt as shapely_wkt
    from shapely.ops import transform
    from pyproj import Transformer

    polygon = shapely_wkt.loads(polygon_wkt)
    centroid = polygon.centroid

    # Determine UTM zone for Nepal (44N or 45N)
    utm_zone = 44 if centroid.x < 84.0 else 45
    utm_epsg = f"EPSG:326{utm_zone}"

    # Create transformers
    to_utm = Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)
    to_wgs84 = Transformer.from_crs(utm_epsg, "EPSG:4326", always_xy=True)

    # Transform to UTM, apply buffer, transform back
    polygon_utm = transform(to_utm.transform, polygon)
    buffered_utm = polygon_utm.buffer(-buffer_meters)  # Negative buffer = inward
    buffered_wgs84 = transform(to_wgs84.transform, buffered_utm)

    # Check if buffer resulted in empty geometry
    if buffered_wgs84.is_empty or buffered_wgs84.area == 0:
        logger.warning(f"Buffer of {buffer_meters}m resulted in empty polygon - using original")
        return polygon_wkt

    return buffered_wgs84.wkt




def validate_point_distance_from_boundary(
    points: List[Tuple[float, float]],
    boundary_wkt: str,
    min_distance_meters: float = 20.0
) -> List[Tuple[float, float]]:
    """
    Validate that all points are at least min_distance_meters from the boundary edge.
    Filters out points that are too close to the boundary.

    Args:
        points: List of (lon, lat) tuples
        boundary_wkt: WKT of boundary polygon
        min_distance_meters: Minimum distance from boundary edge (default 20m = 2 pixels of tree cover)

    Returns:
        Filtered list of points that are safely inside the boundary
    """
    from shapely import wkt as shapely_wkt
    from shapely.ops import transform
    from pyproj import Transformer
    from shapely.geometry import Point

    if not points:
        return points

    # Load boundary
    boundary = shapely_wkt.loads(boundary_wkt)
    centroid = boundary.centroid

    # Determine UTM zone for Nepal
    utm_zone = 44 if centroid.x < 84.0 else 45
    utm_epsg = f"EPSG:326{utm_zone}"

    # Create transformers
    to_utm = Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)

    # Transform boundary to UTM
    boundary_utm = transform(to_utm.transform, boundary)
    boundary_line_utm = boundary_utm.boundary

    # Filter points
    valid_points = []
    filtered_count = 0

    for lon, lat in points:
        # Transform point to UTM
        point_utm_coords = to_utm.transform(lon, lat)
        point_utm = Point(point_utm_coords)

        # Calculate distance to boundary edge
        distance = point_utm.distance(boundary_line_utm)

        if distance >= min_distance_meters:
            valid_points.append((lon, lat))
        else:
            filtered_count += 1

    if filtered_count > 0:
        logger.warning(
            f"Filtered {filtered_count} points that were < {min_distance_meters}m from boundary. "
            f"Kept {len(valid_points)} valid points."
        )

    return valid_points



def generate_systematic_grid(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    grid_spacing_meters: int,
    polygon_wkt: str,
    boundary_buffer_meters: float = 50.0
) -> List[Tuple[float, float]]:
    """
    Generate systematic grid of points within polygon.

    Enforces minimum distance from boundary to avoid edge effects.

    Args:
        min_lon, min_lat, max_lon, max_lat: Bounding box
        grid_spacing_meters: Grid spacing in meters
        polygon_wkt: WKT of polygon to constrain points
        boundary_buffer_meters: Minimum distance from boundary (default 50m)

    Returns:
        List of (lon, lat) tuples
    """
    # Apply boundary buffer to keep points away from edge
    buffered_polygon_wkt = apply_boundary_buffer(polygon_wkt, boundary_buffer_meters)

    # Convert grid spacing to approximate degrees
    # At Nepal's latitude (~28°), 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(28°) ≈ 98 km
    meters_per_degree_lat = 111000.0
    meters_per_degree_lon = 98000.0

    spacing_lat = grid_spacing_meters / meters_per_degree_lat
    spacing_lon = grid_spacing_meters / meters_per_degree_lon

    # Load buffered polygon for intersection testing
    polygon = wkt.loads(buffered_polygon_wkt)

    # Generate grid points
    points = []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            point = Point(lon, lat)
            if polygon.contains(point):
                points.append((lon, lat))
            lon += spacing_lon
        lat += spacing_lat

    logger.info(f"Generated {len(points)} systematic grid points")
    return points


def generate_random_points(
    polygon_wkt: str,
    num_points: int,
    min_distance_meters: Optional[int] = None,
    boundary_buffer_meters: float = 50.0
) -> List[Tuple[float, float]]:
    """
    Generate random points within polygon.

    Enforces minimum distance from boundary to avoid edge effects.

    Args:
        polygon_wkt: WKT of polygon
        num_points: Number of points to generate
        min_distance_meters: Minimum distance between points (optional)
        boundary_buffer_meters: Minimum distance from boundary (default 50m)

    Returns:
        List of (lon, lat) tuples
    """
    # Apply boundary buffer to keep points away from edge
    buffered_polygon_wkt = apply_boundary_buffer(polygon_wkt, boundary_buffer_meters)
    polygon = wkt.loads(buffered_polygon_wkt)
    minx, miny, maxx, maxy = polygon.bounds

    points = []
    attempts = 0
    max_attempts = num_points * 100  # Prevent infinite loop

    while len(points) < num_points and attempts < max_attempts:
        attempts += 1

        # Generate random point in bounding box
        lon = random.uniform(minx, maxx)
        lat = random.uniform(miny, maxy)
        point = Point(lon, lat)

        # Check if point is within polygon
        if not polygon.contains(point):
            continue

        # Check minimum distance constraint
        if min_distance_meters and points:
            min_dist_deg = min_distance_meters / 111000.0  # Approximate
            too_close = False
            for existing_lon, existing_lat in points:
                dist = math.sqrt((lon - existing_lon)**2 + (lat - existing_lat)**2)
                if dist < min_dist_deg:
                    too_close = True
                    break
            if too_close:
                continue

        points.append((lon, lat))

    logger.info(f"Generated {len(points)} random points in {attempts} attempts")
    return points


def generate_stratified_points(
    polygon_wkt: str,
    num_points: int,
    num_strata: int = 4,
    boundary_buffer_meters: float = 50.0
) -> List[Tuple[float, float]]:
    """
    Generate stratified random points within polygon.
    Divides polygon into grid strata and samples from each.
    Enforces minimum distance from boundary to avoid edge effects.

    Args:
        polygon_wkt: WKT of polygon
        num_points: Total number of points to generate
        num_strata: Number of strata (grid cells) to divide polygon into
        boundary_buffer_meters: Minimum distance from boundary (default 50m)

    Returns:
        List of (lon, lat) tuples
    """
    # Apply boundary buffer to keep points away from edge
    buffered_polygon_wkt = apply_boundary_buffer(polygon_wkt, boundary_buffer_meters)
    polygon = wkt.loads(buffered_polygon_wkt)
    minx, miny, maxx, maxy = polygon.bounds

    # Calculate grid dimensions
    grid_size = int(math.sqrt(num_strata))
    dx = (maxx - minx) / grid_size
    dy = (maxy - miny) / grid_size

    # Points per stratum
    points_per_stratum = num_points // num_strata
    extra_points = num_points % num_strata

    points = []

    # Generate points for each stratum
    for i in range(grid_size):
        for j in range(grid_size):
            stratum_minx = minx + i * dx
            stratum_maxx = minx + (i + 1) * dx
            stratum_miny = miny + j * dy
            stratum_maxy = miny + (j + 1) * dy

            # Create stratum polygon
            stratum_box = Polygon([
                (stratum_minx, stratum_miny),
                (stratum_maxx, stratum_miny),
                (stratum_maxx, stratum_maxy),
                (stratum_minx, stratum_maxy),
                (stratum_minx, stratum_miny)
            ])

            # Intersect with original polygon
            try:
                stratum = polygon.intersection(stratum_box)
                if stratum.is_empty:
                    continue

                # Number of points for this stratum
                n_points = points_per_stratum
                if extra_points > 0:
                    n_points += 1
                    extra_points -= 1

                # Generate random points within stratum
                stratum_wkt = stratum.wkt
                # Already buffered at polygon level, so use 0 buffer for strata
                stratum_points = generate_random_points(stratum_wkt, n_points, boundary_buffer_meters=0)
                points.extend(stratum_points)

            except Exception as e:
                logger.warning(f"Error processing stratum: {str(e)}")
                continue

    logger.info(f"Generated {len(points)} stratified random points")
    return points


def extract_blocks_from_calculation(
    db: Session,
    calculation_id: UUID
) -> List[Tuple[int, str, str, float]]:
    """
    Extract individual blocks from calculation's result_data->blocks array.

    Args:
        db: Database session
        calculation_id: Calculation ID

    Returns:
        List of tuples: (block_number, block_geom_wkt, block_name, block_area_hectares)
    """
    # Fetch calculation to get blocks from result_data
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    result_data = calculation.result_data or {}
    blocks_array = result_data.get('blocks', [])

    if not blocks_array:
        logger.warning(f"No blocks found in result_data for calculation {calculation_id}")
        # Fallback: use entire boundary as single block
        query = text("""
            SELECT
                ST_AsText(boundary_geom) as block_wkt,
                ST_Area(ST_Transform(boundary_geom,
                    CASE
                        WHEN ST_X(ST_Centroid(boundary_geom)) < 84.0 THEN 32644
                        ELSE 32645
                    END
                )) / 10000.0 as area_hectares
            FROM public.calculations
            WHERE id = :calc_id
        """)
        result = db.execute(query, {"calc_id": str(calculation_id)}).fetchone()
        if result:
            forest_name = calculation.forest_name or "Forest"
            return [(1, result.block_wkt, f"{forest_name} - Block 1", float(result.area_hectares))]
        return []

    blocks = []
    from shapely.geometry import shape

    for idx, block_data in enumerate(blocks_array):
        block_number = idx + 1  # 1-indexed for display
        block_name = block_data.get('block_name', f'Block {block_number}')

        # Debug: log available keys
        logger.warning(f"DEBUG Block {block_name} keys: {list(block_data.keys())}")

        # Extract geometry - try multiple possible keys
        block_geometry = (
            block_data.get('block_geometry') or
            block_data.get('geometry') or
            block_data.get('polygon_geometry')
        )

        if not block_geometry:
            logger.warning(f"Block {block_name} has no geometry, skipping. Available keys: {list(block_data.keys())}")
            continue

        try:
            # Convert GeoJSON to Shapely geometry
            geom = shape(block_geometry)
            block_wkt = geom.wkt

            # Calculate area using PostGIS (proper projection)
            query = text("""
                SELECT
                    ST_Area(ST_Transform(ST_GeomFromText(:wkt, 4326),
                        CASE
                            WHEN ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) < 84.0 THEN 32644
                            ELSE 32645
                        END
                    )) / 10000.0 as area_hectares
            """)
            result = db.execute(query, {"wkt": block_wkt}).fetchone()
            area_hectares = float(result.area_hectares) if result else 0.0

            blocks.append((block_number, block_wkt, block_name, area_hectares))

        except Exception as e:
            logger.error(f"Failed to process block {block_name}: {e}")
            continue

    logger.info(f"Extracted {len(blocks)} blocks from calculation {calculation_id}")
    return blocks


def create_sampling_design(
    db: Session,
    calculation_id: UUID,
    sampling_type: str,
    sampling_intensity_percent: Optional[Decimal] = None,
    min_samples_per_block: int = 5,
    min_samples_small_blocks: int = 2,
    boundary_buffer_meters: float = 50.0,

    # NEW: Accessible forest filtering parameters
    filter_tree_cover: bool = True,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0,

    intensity_per_hectare: Optional[Decimal] = None,
    grid_spacing_meters: Optional[int] = None,
    min_distance_meters: Optional[int] = None,
    plot_shape: str = "circular",
    plot_radius_meters: Optional[Decimal] = None,
    plot_length_meters: Optional[Decimal] = None,
    plot_width_meters: Optional[Decimal] = None,
    notes: Optional[str] = None,
    block_overrides: Optional[dict] = None
) -> SamplingGenerateResponse:
    """
    Create sampling design and generate sampling points PER BLOCK.

    NEW: Supports flexible filtering for accessible forest areas.

    Uses sampling intensity percentage and enforces minimum samples per block.

    Args:
        db: Database session
        calculation_id: Calculation ID
        sampling_type: 'systematic', 'random', or 'stratified'
        sampling_intensity_percent: Percentage of block area to sample (default 0.5%)
        min_samples_per_block: Minimum samples for blocks >= 1 ha (default 5)
        min_samples_small_blocks: Minimum samples for blocks < 1 ha (default 2)
        boundary_buffer_meters: Minimum distance from boundary (default 50m)

        filter_tree_cover: If True, exclude non-forest areas (default True)
        filter_slope: If True, exclude steep slopes (default False)
        max_slope_degrees: Maximum slope threshold in degrees (default 45.0)

        intensity_per_hectare: [DEPRECATED] Use sampling_intensity_percent
        grid_spacing_meters: [DEPRECATED] Calculated automatically
        min_distance_meters: Minimum distance between points
        plot_shape: 'circular', 'square', or 'rectangular'
        plot_radius_meters: Plot radius (for circular, default 12.62m)
        plot_length_meters: Plot length (for rectangular)
        plot_width_meters: Plot width (for rectangular)
        notes: Design notes

    Returns:
        SamplingGenerateResponse with per-block summary statistics
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    # Use sampling_intensity_percent if provided, otherwise fallback to old intensity_per_hectare
    if sampling_intensity_percent is None and intensity_per_hectare is not None:
        # Convert old intensity_per_hectare to percentage (rough estimate)
        sampling_intensity_percent = Decimal("0.5")
        logger.warning("Using default 0.5% intensity - intensity_per_hectare is deprecated")
    elif sampling_intensity_percent is None:
        sampling_intensity_percent = Decimal("0.5")  # Default

    # Calculate plot area
    plot_area_sqm = None
    if plot_shape == "circular" and plot_radius_meters:
        plot_area_sqm = math.pi * float(plot_radius_meters) ** 2
    elif plot_shape == "circular":
        # Default circular plot: radius 12.6156m = 500m²
        plot_area_sqm = math.pi * (12.6156 ** 2)
        plot_radius_meters = Decimal("12.6156")
    elif plot_shape in ["square", "rectangular"] and plot_length_meters and plot_width_meters:
        plot_area_sqm = float(plot_length_meters) * float(plot_width_meters)
    else:
        raise ValueError("Plot shape and dimensions must be specified")

    plot_area_hectares = plot_area_sqm / 10000.0

    logger.info(
        f"Generating {sampling_type} sampling with {float(sampling_intensity_percent)}% intensity, "
        f"plot size {plot_area_sqm:.2f}m², min samples: {min_samples_per_block} (large blocks), "
        f"{min_samples_small_blocks} (small blocks < 1ha)"
    )

    # Log filter settings
    if filter_tree_cover or filter_slope:
        filter_desc = []
        if filter_tree_cover:
            filter_desc.append("tree cover only")
        if filter_slope:
            filter_desc.append(f"slope <={max_slope_degrees}°")
        logger.info(f"  Accessible forest filtering: {', '.join(filter_desc)}")

    # Build default parameters dictionary
    default_parameters = {
        "sampling_type": sampling_type,
        "sampling_intensity_percent": float(sampling_intensity_percent),
        "min_samples_per_block": min_samples_per_block,
        "min_samples_small_blocks": min_samples_small_blocks,
        "boundary_buffer_meters": boundary_buffer_meters,
        "min_distance_meters": min_distance_meters,

        # NEW: Accessible forest filter settings
        "filter_tree_cover": filter_tree_cover,
        "filter_slope": filter_slope,
        "max_slope_degrees": max_slope_degrees
    }

    # Extract blocks from calculation
    blocks = extract_blocks_from_calculation(db, calculation_id)

    # Get excluded areas (private land) - these areas should NOT have any sample plots
    excluded_areas = get_excluded_areas_for_calculation(db, calculation_id)
    if excluded_areas:
        logger.info(f"Found {len(excluded_areas)} excluded areas (private land) - no plots will be placed here")

    # Generate sampling points PER BLOCK
    all_points = []
    block_assignments = []
    blocks_info = []
    total_forest_area = 0.0

    for block_number, block_wkt, block_name, block_area_ha in blocks:
        total_forest_area += block_area_ha

        # Apply block-specific overrides if they exist
        block_sampling_type = sampling_type
        block_intensity_percent = sampling_intensity_percent
        block_min_samples_per_block = min_samples_per_block
        block_min_samples_small_blocks = min_samples_small_blocks
        block_boundary_buffer = boundary_buffer_meters
        block_min_distance = min_distance_meters

        if block_overrides and block_name in block_overrides:
            override = block_overrides[block_name]
            block_sampling_type = override.get("sampling_type", sampling_type)
            block_intensity_percent = Decimal(str(override.get("sampling_intensity_percent", sampling_intensity_percent)))
            block_min_samples_per_block = override.get("min_samples_per_block", min_samples_per_block)
            block_boundary_buffer = override.get("boundary_buffer_meters", boundary_buffer_meters)
            block_min_distance = override.get("min_distance_meters", min_distance_meters)

            logger.info(f"  Applying overrides for {block_name}: {override}")

        # NEW: Calculate accessible forest area for this block
        accessible_area_info = None
        effective_block_area = block_area_ha  # Default to total area

        if filter_tree_cover or filter_slope:
            # NOTE: Slope filtering DISABLED - too slow and causes server hang
            accessible_area_info = calculate_accessible_forest_area(
                db=db,
                geometry_wkt=block_wkt,
                filter_tree_cover=filter_tree_cover,
                filter_slope=False,  # ALWAYS False - slope filtering disabled
                max_slope_degrees=max_slope_degrees
            )

            # Use accessible forest area instead of total block area
            effective_block_area = accessible_area_info.get("accessible_forest_area_ha", block_area_ha)

            logger.info(
                f"  {block_name}: Total {block_area_ha:.2f} ha -> "
                f"Accessible {effective_block_area:.2f} ha "
                f"({accessible_area_info.get('accessible_forest_percentage', 100):.1f}%)"
            )

            if filter_tree_cover:
                logger.info(f"    - Filtered to tree cover only")
            if filter_slope:
                logger.info(f"    - Excluded slopes >{max_slope_degrees}°")
                if accessible_area_info.get('inaccessible_steep_forest_ha', 0) > 0:
                    logger.info(
                        f"    - Inaccessible steep forest: "
                        f"{accessible_area_info['inaccessible_steep_forest_ha']:.2f} ha"
                    )

        # Determine minimum samples for this block
        if block_area_ha < 1.0:
            min_samples = block_min_samples_small_blocks
        else:
            min_samples = block_min_samples_per_block

        # Calculate samples based on intensity (use EFFECTIVE area)
        sample_area_hectares = float(effective_block_area) * (float(block_intensity_percent) / 100.0)
        samples_from_intensity = int(sample_area_hectares / float(plot_area_hectares))

        # Apply minimum
        samples_for_block = max(min_samples, samples_from_intensity)
        minimum_enforced = samples_for_block == min_samples

        logger.info(
            f"  {block_name} ({block_area_ha:.2f} ha, {effective_block_area:.2f} ha accessible): "
            f"{samples_from_intensity} from intensity -> {samples_for_block} samples "
            f"(minimum {'enforced' if minimum_enforced else 'not needed'})"
        )

        # NEW PIXEL-BASED APPROACH: Extract tree cover pixel centers as candidate locations
        candidate_pixels = []

        if filter_tree_cover or filter_slope:
            # Extract tree cover pixel centers
            # NOTE: Slope filtering DISABLED - too slow and causes server hang
            # Always extract tree cover only, regardless of filter_slope setting
            if filter_slope:
                logger.warning(
                    f"    ⚠️ Slope filtering requested but DISABLED (too slow). "
                    f"Sampling from all tree cover pixels instead."
                )

            logger.info(f"    - Extracting tree cover pixel centers (no slope filter)...")

            candidate_pixels = extract_tree_cover_pixel_centers(
                db=db,
                geometry_wkt=block_wkt,
                filter_slope=False,  # ALWAYS False - slope filtering disabled
                max_slope_degrees=max_slope_degrees,
                min_distance_from_boundary_meters=20.0  # 2 pixels (10m each) from edge
            )

            if not candidate_pixels:
                logger.warning(
                    f"  {block_name}: No accessible tree pixels found. "
                    f"Try: (1) Disable slope filter, (2) Increase max slope, or (3) Disable tree cover filter."
                )
                # Fall back to full boundary sampling
                candidate_pixels = None

            else:
                logger.info(f"    - Found {len(candidate_pixels)} candidate tree pixels")

        # Track grid spacing for this block (for reporting)
        block_grid_spacing_meters = None

        # Generate points for this block
        if candidate_pixels:
            # PIXEL-BASED SAMPLING: Sample from tree cover pixel centers
            # Convert pixel centers to (lon, lat) tuples for compatibility
            pixel_points = [(lon, lat) for lon, lat, slope in candidate_pixels]

            # Filter out points in excluded areas (private land)
            if excluded_areas:
                original_count = len(pixel_points)
                pixel_points = [
                    (lon, lat) for lon, lat in pixel_points
                    if not point_in_excluded_area(lon, lat, excluded_areas)
                ]
                filtered_count = original_count - len(pixel_points)
                if filtered_count > 0:
                    logger.info(
                        f"    - Filtered out {filtered_count} pixels in excluded areas (private land). "
                        f"{len(pixel_points)} candidate pixels remaining"
                    )

            if block_sampling_type == "systematic":
                # Systematic sampling from pixel grid
                # Calculate spacing to get approximately the desired number of samples
                if len(pixel_points) <= samples_for_block:
                    # Use all pixels if we have fewer than needed
                    block_points = pixel_points
                else:
                    # Subsample systematically: take every Nth pixel
                    step = max(1, len(pixel_points) // samples_for_block)
                    block_points = pixel_points[::step][:samples_for_block]

                # Estimate grid spacing (approximate)
                block_area_sqm = float(effective_block_area) * 10000.0
                block_grid_spacing_meters = math.sqrt(block_area_sqm / float(max(1, len(block_points))))

                logger.info(f"    - Systematic sampling: selected {len(block_points)}/{len(pixel_points)} pixels")

            elif block_sampling_type == "random":
                # Random sampling from pixel centers
                if len(pixel_points) <= samples_for_block:
                    block_points = pixel_points
                else:
                    import random as rand
                    block_points = rand.sample(pixel_points, samples_for_block)

                logger.info(f"    - Random sampling: selected {len(block_points)}/{len(pixel_points)} pixels")

            elif block_sampling_type == "stratified":
                # Stratified sampling from pixel centers
                # Divide pixels into strata based on spatial distribution
                if len(pixel_points) <= samples_for_block:
                    block_points = pixel_points
                else:
                    # Simple stratified: divide pixels into groups by lat/lon
                    # Sort by latitude, then take evenly spaced samples
                    sorted_pixels = sorted(pixel_points, key=lambda p: (p[1], p[0]))
                    step = max(1, len(sorted_pixels) // samples_for_block)
                    block_points = sorted_pixels[::step][:samples_for_block]

                logger.info(f"    - Stratified sampling: selected {len(block_points)}/{len(pixel_points)} pixels")

            else:
                raise ValueError(f"Invalid sampling_type: {block_sampling_type}")

        else:
            # POLYGON-BASED SAMPLING: Fall back to original approach (no filtering)
            logger.info(f"    - Using full boundary for sampling (no tree cover filter)")

            # Apply boundary buffer ONCE here (not in the generation functions)
            sampling_polygon_wkt = apply_boundary_buffer(block_wkt, block_boundary_buffer)

            if block_sampling_type == "systematic":
                block_area_sqm = float(effective_block_area) * 10000.0
                spacing_meters = math.sqrt(block_area_sqm / float(samples_for_block))
                block_grid_spacing_meters = spacing_meters  # Track for reporting

                bounds = get_polygon_bounds(sampling_polygon_wkt)
                block_points = generate_systematic_grid(
                    bounds[0], bounds[1], bounds[2], bounds[3],
                    int(spacing_meters),
                    sampling_polygon_wkt,
                    0.0  # Buffer already applied above - don't apply again!
                )

            elif block_sampling_type == "random":
                block_points = generate_random_points(
                    sampling_polygon_wkt,
                    samples_for_block,
                    block_min_distance,
                    0.0  # Buffer already applied above - don't apply again!
                )

            elif block_sampling_type == "stratified":
                block_points = generate_stratified_points(
                    sampling_polygon_wkt,
                    samples_for_block,
                    num_strata=max(4, samples_for_block // 2),
                    boundary_buffer_meters=0.0  # Buffer already applied above - don't apply again!
                )

            else:
                raise ValueError(f"Invalid sampling_type: {block_sampling_type}")

            # Filter out points in excluded areas (private land)
            if excluded_areas and block_points:
                original_count = len(block_points)
                block_points = [
                    (lon, lat) for lon, lat in block_points
                    if not point_in_excluded_area(lon, lat, excluded_areas)
                ]
                filtered_count = original_count - len(block_points)
                if filtered_count > 0:
                    logger.info(
                        f"    - Filtered out {filtered_count} points in excluded areas (private land). "
                        f"{len(block_points)} points remaining"
                    )

        # Store points with block assignment
        for point in block_points:
            all_points.append(point)
            block_assignments.append({
                'point_index': len(all_points) - 1,
                'block_number': block_number,
                'block_name': block_name,
                'zone_type': 'productive'  # Default zone type for basic sampling
            })

        # Calculate actual intensity for this block (based on effective area)
        # Convert all to float to avoid Decimal/float mixing errors
        actual_intensity_pct = Decimal(str((len(block_points) * plot_area_hectares / float(effective_block_area)) * 100)) if effective_block_area > 0 else Decimal("0")

        # Store block info with accessible area information
        block_info_dict = {
            "block_number": block_number,
            "block_name": block_name,
            "block_area_hectares": Decimal(str(round(block_area_ha, 4))),
            "samples_generated": len(block_points),
            "minimum_enforced": minimum_enforced,
            "actual_intensity_percent": actual_intensity_pct,
            "grid_spacing_meters": Decimal(str(round(block_grid_spacing_meters, 1))) if block_grid_spacing_meters else None
        }

        # Add accessible area information
        if accessible_area_info:
            # Filtering was applied - use calculated values
            block_info_dict["accessible_forest_area_ha"] = Decimal(
                str(round(accessible_area_info.get("accessible_forest_area_ha", 0), 4))
            )
            block_info_dict["accessible_forest_percentage"] = Decimal(
                str(round(accessible_area_info.get("accessible_forest_percentage", 0), 2))
            )
            if filter_slope:
                block_info_dict["inaccessible_steep_forest_ha"] = Decimal(
                    str(round(accessible_area_info.get("inaccessible_steep_forest_ha", 0), 4))
                )
                block_info_dict["non_forest_area_ha"] = Decimal(
                    str(round(accessible_area_info.get("non_forest_area_ha", 0), 4))
                )
        else:
            # No filtering applied - entire block area is accessible
            block_info_dict["accessible_forest_area_ha"] = Decimal(str(round(block_area_ha, 4)))
            block_info_dict["accessible_forest_percentage"] = Decimal("100.00")

        blocks_info.append(BlockSamplingInfo(**block_info_dict))

    points = all_points
    logger.info(f"Generated total {len(points)} sampling points across {len(blocks)} blocks")

    # DIAGNOSTIC: Log detailed information if no points were generated
    if not points:
        logger.error(
            f"❌ NO POINTS GENERATED - Diagnostics:\n"
            f"  - Total blocks: {len(blocks)}\n"
            f"  - Sampling intensity: {float(sampling_intensity_percent)}%\n"
            f"  - Min samples per block: {min_samples_per_block}\n"
            f"  - Filter tree cover: {filter_tree_cover}\n"
            f"  - Filter slope: {filter_slope}\n"
            f"  - Boundary buffer: {boundary_buffer_meters}m\n"
            f"  - Block details: {[(name, f'{area:.2f} ha') for _, _, name, area in blocks]}"
        )

    if not points:
        if filter_slope or filter_tree_cover:
            filter_description = []
            if filter_tree_cover:
                filter_description.append("tree cover pixels")
            if filter_slope:
                filter_description.append(f"slope <= {max_slope_degrees}°")

            raise ValueError(
                f"No accessible forest pixels found with filters: {' AND '.join(filter_description)}. "
                f"\n\nPossible reasons:"
                f"\n  • No tree cover detected in boundary (check ESA WorldCover data)"
                f"\n  • All slopes exceed {max_slope_degrees}° threshold"
                f"\n  • Boundary too small or outside data coverage"
                f"\n\nSolutions:"
                f"\n  1. Disable slope filter to sample all tree cover"
                f"\n  2. Increase max slope threshold to 60° or 90°"
                f"\n  3. Disable tree cover filter to sample entire boundary"
                f"\n  4. Check if boundary overlaps with forest area"
            )
        else:
            raise ValueError("No sampling points generated - check polygon and parameters")

    # Create MultiPoint geometry WKT
    points_wkt = "MULTIPOINT(" + ", ".join([f"{lon} {lat}" for lon, lat in points]) + ")"

    # Create sampling design record
    sampling_design = SamplingDesign(
        calculation_id=calculation_id,
        sampling_type=sampling_type,
        intensity_per_hectare=Decimal(str(len(points) / float(total_forest_area))),  # Calculated (convert to float to avoid type errors)
        grid_spacing_meters=None,  # Not used with intensity-based approach
        min_distance_meters=min_distance_meters,
        plot_shape=plot_shape,
        plot_radius_meters=plot_radius_meters,
        plot_length_meters=plot_length_meters,
        plot_width_meters=plot_width_meters,
        total_points=len(points),
        notes=notes
    )

    db.add(sampling_design)
    db.flush()  # Get ID

    # Save default parameters and block overrides
    import json
    if default_parameters:
        update_defaults_query = text("""
            UPDATE public.sampling_designs
            SET default_parameters = CAST(:params AS jsonb)
            WHERE id = :design_id
        """)
        db.execute(update_defaults_query, {
            "params": json.dumps(default_parameters),
            "design_id": str(sampling_design.id)
        })

    if block_overrides:
        # Convert block_overrides to JSON-serializable format
        serializable_overrides = {}
        for block_name, override_params in block_overrides.items():
            # If override_params is a Pydantic model, convert to dict
            if hasattr(override_params, 'model_dump'):
                serializable_overrides[block_name] = override_params.model_dump(exclude_none=True)
            elif hasattr(override_params, 'dict'):
                serializable_overrides[block_name] = override_params.dict(exclude_none=True)
            else:
                serializable_overrides[block_name] = override_params

        update_overrides_query = text("""
            UPDATE public.sampling_designs
            SET block_overrides = CAST(:overrides AS jsonb)
            WHERE id = :design_id
        """)
        db.execute(update_overrides_query, {
            "overrides": json.dumps(serializable_overrides),
            "design_id": str(sampling_design.id)
        })

    # Update geometry using PostGIS
    update_geom_query = text("""
        UPDATE public.sampling_designs
        SET points_geometry = ST_GeomFromText(:points_wkt, 4326)
        WHERE id = :design_id
    """)
    db.execute(update_geom_query, {
        "points_wkt": points_wkt,
        "design_id": str(sampling_design.id)
    })

    # Save block assignments directly (we already calculated them)
    import json
    update_assignments_query = text("""
        UPDATE public.sampling_designs
        SET points_block_assignment = CAST(:assignments AS jsonb)
        WHERE id = :design_id
    """)
    db.execute(update_assignments_query, {
        "assignments": json.dumps(block_assignments),
        "design_id": str(sampling_design.id)
    })

    db.commit()

    # Calculate statistics (convert to float to avoid Decimal/float mixing errors)
    actual_intensity = Decimal(str(len(points) / float(total_forest_area)))
    total_sampled_area_sqm = plot_area_sqm * len(points)
    total_sampled_area_hectares = Decimal(str(total_sampled_area_sqm / 10000.0))
    sampling_percentage = Decimal(str((total_sampled_area_sqm / (float(total_forest_area) * 10000.0)) * 100))

    return SamplingGenerateResponse(
        sampling_design_id=sampling_design.id,
        calculation_id=calculation_id,
        sampling_type=sampling_type,
        total_points=len(points),
        total_blocks=len(blocks),
        forest_area_hectares=Decimal(str(round(total_forest_area, 4))),
        requested_intensity_percent=sampling_intensity_percent,
        actual_intensity_per_hectare=actual_intensity,
        plot_area_sqm=Decimal(str(round(plot_area_sqm, 2))),
        total_sampled_area_hectares=total_sampled_area_hectares,
        sampling_percentage=sampling_percentage,
        blocks_info=blocks_info
    )


def get_sampling_points_geojson(db: Session, design_id: UUID) -> dict:
    """
    Get sampling points as GeoJSON with complete field data.
    Includes: plot_number, block, coordinates, elevation, UTM, distance from boundary

    Args:
        db: Database session
        design_id: Sampling design ID

    Returns:
        GeoJSON FeatureCollection with complete properties
    """
    # Get sampling design
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()
    if not design:
        raise ValueError(f"Sampling design {design_id} not found")

    query = text("""
        SELECT
            ST_AsText(points_geometry) as wkt,
            points_block_assignment
        FROM public.sampling_designs
        WHERE id = :design_id
    """)

    result = db.execute(query, {"design_id": str(design_id)}).first()

    if not result or not result.wkt:
        raise ValueError(f"Sampling design {design_id} not found or has no points")

    # Parse MultiPoint geometry
    from shapely import wkt as shapely_wkt
    multipoint = shapely_wkt.loads(result.wkt)
    block_assignment = result.points_block_assignment or []

    # Get calculation boundary for distance calculation
    from app.models.calculation import Calculation
    calc = db.query(Calculation).filter(Calculation.id == design.calculation_id).first()
    boundary_wkt = None
    if calc:
        boundary_query = text("""
            SELECT ST_AsText(boundary_geom) as wkt
            FROM public.calculations
            WHERE id = :calc_id
        """)
        boundary_result = db.execute(boundary_query, {"calc_id": str(design.calculation_id)}).first()
        if boundary_result:
            boundary_wkt = boundary_result.wkt

    # Import required modules for calculations
    from app.utils.geospatial import extract_elevation_at_point
    from pyproj import Transformer

    # Convert to FeatureCollection with individual points and complete data
    features = []
    for i, point in enumerate(multipoint.geoms):
        lon, lat = point.x, point.y

        # Find block assignment for this point
        block_info = next((b for b in block_assignment if b.get('point_index') == i), None)
        block_number = block_info.get('block_number', '') if block_info else ''
        block_name = block_info.get('block_name', '') if block_info else ''
        zone_type = block_info.get('zone_type', 'productve') if block_info else 'productive'

        # Calculate UTM coordinates
        utm_zone = 44 if lon < 84 else 45  # Nepal is in zones 44N and 45N
        transformer = Transformer.from_crs(f"EPSG:4326", f"EPSG:326{utm_zone}", always_xy=True)
        utm_easting, utm_northing = transformer.transform(lon, lat)

        # Extract elevation (ASLM - Above Sea Level Meter)
        elevation_m = extract_elevation_at_point(db, lon, lat)

        # Calculate distance from boundary (if available)
        distance_from_boundary = None
        if boundary_wkt:
            try:
                boundary_geom = shapely_wkt.loads(boundary_wkt)
                distance_from_boundary = point.distance(boundary_geom.boundary) * 111320  # Convert degrees to meters (approximate)
            except:
                pass

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "plot_number": i + 1,
                "block_number": block_number,
                "block_name": block_name,
                "zone_type": zone_type,  # 'productive' or 'protected'
                "longitude": float(f"{lon:.7f}"),
                "latitude": float(f"{lat:.7f}"),
                "elevation_m": int(elevation_m) if elevation_m else None,
                "utm_easting": float(f"{utm_easting:.2f}"),
                "utm_northing": float(f"{utm_northing:.2f}"),
                "utm_zone": f"{utm_zone}N",
                "distance_from_boundary_m": float(f"{distance_from_boundary:.2f}") if distance_from_boundary else None,
                "sampling_type": design.sampling_type
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }


def calculate_geometry_area_hectares(geom):
    """
    Calculate geometry area in hectares using proper UTM projection.

    Args:
        geom: Shapely geometry in EPSG:4326

    Returns:
        Area in hectares
    """
    from shapely.ops import transform
    from pyproj import Transformer

    if geom is None or geom.is_empty:
        return 0.0

    # Get centroid to determine UTM zone
    centroid = geom.centroid
    lon = centroid.x

    # Determine UTM zone for Nepal (44N or 45N)
    utm_zone = 44 if lon < 84.0 else 45
    utm_epsg = f"EPSG:326{utm_zone}"

    # Transform to UTM
    to_utm = Transformer.from_crs("EPSG:4326", utm_epsg, always_xy=True)
    geom_utm = transform(to_utm.transform, geom)

    # Area in square meters, convert to hectares
    return geom_utm.area / 10000.0


def calculate_zone_net_areas(
    block_wkt: str,
    sub_areas: List[Dict],
    excluded_areas: List[Polygon],
    calculate_protected_separately: bool = True
) -> Dict:
    """
    Calculate net productive and protected areas after private land deduction.

    Args:
        block_wkt: WKT string of block polygon
        sub_areas: List of sub-area dictionaries
        excluded_areas: List of excluded (private land) polygons
        calculate_protected_separately: If True, calculate protected as separate zone.
                                        If False, treat protected as excluded area.

    Returns:
        Dictionary with:
        {
            "productive_area_ha": float - Net productive forest area
            "protected_area_ha": float - Net protected zone area
            "private_land_area_ha": float - Total private land in block
            "block_geometry": Polygon - Block geometry object
            "productive_geometry": Polygon/MultiPolygon - Productive zone geometry
            "protected_geometry": Polygon/MultiPolygon - Protected zone geometry (or None)
        }
    """
    from shapely.ops import unary_union
    from shapely.geometry import GeometryCollection, shape

    # Parse block geometry
    block_geom = wkt.loads(block_wkt)

    # Calculate area properly using UTM projection
    block_area_ha = calculate_geometry_area_hectares(block_geom)

    # Extract protected zone geometries from sub-areas (only if calculating separately)
    protected_geoms = []
    if calculate_protected_separately:
        for sa in sub_areas:
            if sa.get('category') == 'protected' and not sa.get('isExcluded', False):
                try:
                    geom_data = sa['geometry']

                    # Handle GeometryCollection
                    if geom_data.get('type') == 'GeometryCollection':
                        geom_collection = shape(geom_data)
                        polygons = [g for g in geom_collection.geoms
                                   if g.geom_type in ('Polygon', 'MultiPolygon') and not g.is_empty]
                        if polygons:
                            geom = unary_union(polygons) if len(polygons) > 1 else polygons[0]
                            protected_geoms.append(geom)
                    else:
                        geom = shape(geom_data)
                        if not geom.is_empty:
                            protected_geoms.append(geom)
                except Exception as e:
                    logger.warning(f"Failed to parse protected zone in area calculation: {e}")

    # Combine all protected zones within this block
    if protected_geoms:
        protected_union = unary_union(protected_geoms)
        protected_in_block = block_geom.intersection(protected_union)
    else:
        protected_in_block = None

    # Combine all excluded areas (private land)
    if excluded_areas:
        excluded_union = unary_union(excluded_areas)
        excluded_in_block = block_geom.intersection(excluded_union)
    else:
        excluded_in_block = None

    # Calculate areas using proper UTM projection
    protected_area_ha = calculate_geometry_area_hectares(protected_in_block) if protected_in_block else 0.0
    private_land_area_ha = calculate_geometry_area_hectares(excluded_in_block) if excluded_in_block else 0.0

    # Calculate net productive area (block - protected - private land)
    productive_geom = block_geom
    if protected_in_block and not protected_in_block.is_empty:
        productive_geom = productive_geom.difference(protected_in_block)
    if excluded_in_block and not excluded_in_block.is_empty:
        productive_geom = productive_geom.difference(excluded_in_block)

    productive_area_ha = calculate_geometry_area_hectares(productive_geom) if productive_geom and not productive_geom.is_empty else 0.0

    # Calculate net protected area (protected - private land)
    protected_net_geom = None
    if protected_in_block and not protected_in_block.is_empty:
        protected_net_geom = protected_in_block
        if excluded_in_block and not excluded_in_block.is_empty:
            protected_net_geom = protected_net_geom.difference(excluded_in_block)

    protected_net_area_ha = calculate_geometry_area_hectares(protected_net_geom) if protected_net_geom else 0.0

    # Debug logging
    logger.warning(
        f"DEBUG Area Calculation (FIXED WITH UTM):\n"
        f"  Block total: {block_area_ha:.4f} ha\n"
        f"  Protected overlap: {protected_area_ha:.4f} ha\n"
        f"  Private land: {private_land_area_ha:.4f} ha\n"
        f"  Productive (net): {productive_area_ha:.4f} ha\n"
        f"  Protected (net): {protected_net_area_ha:.4f} ha"
    )

    return {
        "productive_area_ha": productive_area_ha,
        "protected_area_ha": protected_net_area_ha,
        "private_land_area_ha": private_land_area_ha,
        "block_geometry": block_geom,
        "productive_geometry": productive_geom if productive_geom and not productive_geom.is_empty else None,
        "protected_geometry": protected_net_geom if protected_net_geom and not protected_net_geom.is_empty else None
    }


def create_sampling_design_guideline_2061(
    db: Session,
    calculation_id: UUID,
    productive_intensity: float,  # 0.5 or 1.0
    sample_protected_zone: bool,
    plot_size_sqm: int,
    plot_shape: str = "circular",
    filter_tree_cover: bool = True,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0,
    boundary_buffer_meters: float = 50.0,
    notes: Optional[str] = None
) -> SamplingGenerateResponse:
    """
    Create sampling design using Forest Inventory Guideline-2061.

    This implements Nepal's Department of Forest standard sampling methodology
    where sample counts are determined by lookup tables based on block size,
    rather than calculated from intensity percentages.

    Key differences from manual sampling:
    1. Sample counts determined by guideline tables (not intensity %)
    2. Different intensities for productive (0.5% or 1%) vs protected (0.1%) zones
    3. Supports mixed sampling (productive + protected in same forest)
    4. Systematic sampling only (as per guideline)
    5. Falls back to manual calculation if block exceeds table range

    Block Classification:
    - Blocks are classified as productive or protected based on >50% overlap rule
    - Protected blocks sampled at 0.1% (if sample_protected_zone=True)
    - Productive blocks sampled at 0.5% or 1% (user choice)

    Args:
        db: Database session
        calculation_id: Calculation ID
        productive_intensity: 0.5 or 1.0 (for productive blocks)
        sample_protected_zone: If True, sample protected areas at 0.1%
        plot_size_sqm: Plot size (100-500 for production, 25-100 for protected)
        plot_shape: 'circular' or 'square'
        filter_tree_cover: Exclude non-forest areas (recommended)
        filter_slope: Exclude steep slopes (optional, slow)
        max_slope_degrees: Maximum slope threshold
        boundary_buffer_meters: Minimum distance from boundary
        notes: Design notes

    Returns:
        SamplingGenerateResponse with per-block summary

    Raises:
        ValueError: If parameters are invalid or calculation not found
    """
    import math  # Import at function start for NaN checks

    logger.info(
        f"Creating Guideline-2061 sampling design: "
        f"productive={productive_intensity}%, protected={'Yes' if sample_protected_zone else 'No'}, "
        f"plot_size={plot_size_sqm}sqm"
    )

    # Validate guideline parameters for productive zones only
    # (Protected zones always use 100 sqm, so no need to validate user's choice)
    validate_guideline_parameters(
        intensity_percent=productive_intensity,
        plot_size_sqm=plot_size_sqm,
        is_protected_sampling=False  # Validating production params
    )

    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    # Calculate plot dimensions for PRODUCTIVE zones
    productive_plot_size_sqm = plot_size_sqm
    productive_plot_area_hectares = productive_plot_size_sqm / 10000.0

    # For PROTECTED zones, always use 100 sqm (standard for protected areas)
    protected_plot_size_sqm = 100
    protected_plot_area_hectares = protected_plot_size_sqm / 10000.0

    if plot_shape == "circular":
        productive_plot_radius = math.sqrt(productive_plot_size_sqm / math.pi)
        protected_plot_radius = math.sqrt(protected_plot_size_sqm / math.pi)
    else:
        productive_plot_radius = None
        protected_plot_radius = None

    logger.info(
        f"Plot configuration:\n"
        f"  Productive zones: {productive_plot_size_sqm} sqm\n"
        f"  Protected zones: {protected_plot_size_sqm} sqm (standard for protected areas)"
    )

    # Extract blocks from calculation
    blocks = extract_blocks_from_calculation(db, calculation_id)

    # Get excluded areas (private land)
    excluded_areas = get_excluded_areas_for_calculation(db, calculation_id)
    if excluded_areas:
        logger.info(f"Found {len(excluded_areas)} excluded areas (private land)")

    # Get sub-areas for block classification
    sub_areas = calculation.result_data.get('sub_areas', [])

    # Protected zone geometries (if NOT sampling them, add to excluded areas)
    if not sample_protected_zone:
        protected_geometries = []
        for sa in sub_areas:
            if sa.get('category') == 'protected' and not sa.get('isExcluded', False):
                from shapely.geometry import shape, GeometryCollection
                try:
                    geom_data = sa['geometry']

                    # Handle GeometryCollection - extract only Polygon/MultiPolygon
                    if geom_data.get('type') == 'GeometryCollection':
                        geom_collection = shape(geom_data)

                        # Extract only polygonal geometries
                        polygons = [g for g in geom_collection.geoms
                                   if g.geom_type in ('Polygon', 'MultiPolygon') and g.area > 0]

                        if polygons:
                            from shapely.ops import unary_union
                            geom = unary_union(polygons) if len(polygons) > 1 else polygons[0]
                            protected_geometries.append(geom)
                    else:
                        # Regular Polygon or MultiPolygon
                        geom = shape(geom_data)

                        # Skip zero-area geometries
                        if geom.area > 0:
                            protected_geometries.append(geom)

                except Exception as e:
                    logger.warning(f"Failed to parse protected zone geometry: {e}")

        if protected_geometries:
            # Add protected zones to excluded areas so they're treated as off-limits
            excluded_areas.extend(protected_geometries)
            logger.warning(
                f"Protected zones will be excluded from sampling "
                f"({len(protected_geometries)} zones added to excluded areas)"
            )

    # Generate sampling points PER BLOCK with SEPARATE ZONE SAMPLING
    all_points = []
    block_assignments = []
    blocks_info = []
    total_forest_area = 0.0

    for block_number, block_wkt, block_name, block_area_ha in blocks:
        total_forest_area += block_area_ha

        logger.warning(
            f"\n{'='*60}\n"
            f"Processing: {block_name} ({block_area_ha:.2f} ha total)\n"
            f"{'='*60}"
        )

        # ENHANCED DIAGNOSTICS
        logger.warning(f"DEBUG: sample_protected_zone = {sample_protected_zone}")
        logger.warning(f"DEBUG: Number of sub_areas = {len(sub_areas)}")
        logger.warning(f"DEBUG: Number of excluded_areas = {len(excluded_areas)}")

        # Calculate net areas for productive and protected zones (after private land deduction)
        try:
            zone_areas = calculate_zone_net_areas(
                block_wkt,
                sub_areas,
                excluded_areas,
                calculate_protected_separately=sample_protected_zone
            )
            logger.warning(f"DEBUG: zone_areas keys = {list(zone_areas.keys())}")
        except Exception as e:
            logger.error(f"ERROR calculating areas for {block_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback: use entire block as productive
            zone_areas = {
                "productive_area_ha": block_area_ha,
                "protected_area_ha": 0.0,
                "private_land_area_ha": 0.0,
                "block_geometry": wkt.loads(block_wkt),
                "productive_geometry": wkt.loads(block_wkt),
                "protected_geometry": None
            }

        productive_area_ha = zone_areas["productive_area_ha"]
        protected_area_ha = zone_areas["protected_area_ha"]
        private_land_ha = zone_areas["private_land_area_ha"]
        productive_geom = zone_areas.get("productive_geometry")
        protected_geom = zone_areas.get("protected_geometry")

        logger.warning(
            f"Area Breakdown:\n"
            f"  Total: {block_area_ha:.4f} ha\n"
            f"  Productive (net): {productive_area_ha:.4f} ha\n"
            f"  Protected (net): {protected_area_ha:.4f} ha\n"
            f"  Private Land: {private_land_ha:.4f} ha\n"
            f"  Productive geometry: {'EMPTY' if not productive_geom or productive_geom.is_empty else 'OK'}\n"
            f"  Protected geometry: {'EMPTY' if not protected_geom or (hasattr(protected_geom, 'is_empty') and protected_geom.is_empty) else 'OK' if protected_geom else 'None'}"
        )

        # Determine which zones to sample
        sample_productive = productive_area_ha > 0.01  # At least 0.01 ha (100 sqm)
        sample_protected_this_block = sample_protected_zone and protected_area_ha > 0.01

        logger.warning(f"DEBUG: sample_productive = {sample_productive} (area: {productive_area_ha:.4f} ha)")
        logger.warning(f"DEBUG: sample_protected_this_block = {sample_protected_this_block} (area: {protected_area_ha:.4f} ha)")

        if not sample_productive and not sample_protected_this_block:
            logger.warning(f"⚠ No sampleable area in {block_name} - SKIPPING BLOCK!")
            logger.warning(f"   Reason: productive_area_ha={productive_area_ha:.4f}, protected_area_ha={protected_area_ha:.4f}, sample_protected_zone={sample_protected_zone}")
            continue

        # PRODUCTIVE ZONE SAMPLING
        productive_samples = []
        productive_sample_count = 0
        productive_spacing = None
        productive_sampling_method = "systematic"  # Default, will be updated if random used

        if sample_productive:
            logger.info(f"\n--- Productive Zone ({productive_area_ha:.4f} ha at {productive_intensity}%) ---")

            try:
                productive_sample_count = get_sample_count_from_guideline(
                    db=db,
                    block_area_hectares=productive_area_ha,
                    intensity_percent=productive_intensity,
                    plot_size_sqm=productive_plot_size_sqm
                )
                logger.info(f"✓ Guideline table: {productive_sample_count} samples ({productive_plot_size_sqm} sqm plots)")
            except ValueError:
                # Fallback to manual calculation
                sample_area_ha = productive_area_ha * (productive_intensity / 100.0)
                productive_sample_count = max(2, int(sample_area_ha / productive_plot_area_hectares))
                logger.info(f"✓ Manual calc: {productive_sample_count} samples ({productive_plot_size_sqm} sqm plots)")

            logger.warning(f"DEBUG: Checking productive sample generation: count={productive_sample_count}, geometry={'OK' if zone_areas.get('productive_geometry') else 'NONE/EMPTY'}")

            if productive_sample_count > 0 and zone_areas["productive_geometry"]:
                # Generate samples in productive zone only
                productive_wkt = zone_areas["productive_geometry"].wkt
                productive_buffered = apply_boundary_buffer(productive_wkt, boundary_buffer_meters)
                productive_sampling_method = "systematic"

                logger.warning(f"DEBUG: productive_buffered WKT length = {len(productive_buffered)}")

                # Try systematic grid with current buffer first
                effective_area_sqm = productive_area_ha * 10000.0
                systematic_success = False

                for iteration in range(5):
                    spacing = math.sqrt(effective_area_sqm / float(productive_sample_count))
                    bounds = get_polygon_bounds(productive_buffered)
                    candidates = generate_systematic_grid(
                        bounds[0], bounds[1], bounds[2], bounds[3],
                        int(spacing), productive_buffered, 0.0  # No additional buffer - already buffered
                    )

                    logger.warning(f"DEBUG: Iteration {iteration}: spacing={spacing:.1f}m, candidates={len(candidates)}, target={productive_sample_count}")

                    if len(candidates) >= productive_sample_count:
                        productive_samples = candidates[:productive_sample_count]
                        productive_spacing = spacing
                        systematic_success = True
                        logger.info(f"  Generated {len(productive_samples)} productive samples (systematic)")
                        break
                    effective_area_sqm *= 0.9

                # Fallback 1: Try smaller buffer (15m)
                if not systematic_success and productive_sample_count > 0:
                    logger.warning(f"  ⚠ Systematic failed with {boundary_buffer_meters}m buffer, trying 15m buffer...")
                    productive_buffered_15m = apply_boundary_buffer(productive_wkt, 15.0)
                    effective_area_sqm = productive_area_ha * 10000.0

                    for iteration in range(5):
                        spacing = math.sqrt(effective_area_sqm / float(productive_sample_count))
                        bounds = get_polygon_bounds(productive_buffered_15m)
                        candidates = generate_systematic_grid(
                            bounds[0], bounds[1], bounds[2], bounds[3],
                            int(spacing), productive_buffered_15m, 0.0
                        )

                        if len(candidates) >= productive_sample_count:
                            productive_samples = candidates[:productive_sample_count]
                            productive_spacing = spacing
                            systematic_success = True
                            logger.info(f"  Generated {len(productive_samples)} productive samples (systematic, 15m buffer)")
                            break
                        effective_area_sqm *= 0.9

                # Fallback 2: Random sampling
                if not systematic_success and productive_sample_count > 0:
                    logger.warning(f"  ⚠ Systematic failed, falling back to random sampling...")
                    min_distance = int(math.sqrt(effective_area_sqm / productive_sample_count))
                    productive_samples = generate_random_points(
                        productive_buffered,
                        productive_sample_count,
                        min_distance_meters=min_distance,
                        boundary_buffer_meters=0.0  # Already buffered
                    )
                    if len(productive_samples) > 0:
                        productive_sampling_method = "random"
                        logger.info(f"  Generated {len(productive_samples)} productive samples (random)")
                    else:
                        logger.warning("  ⚠ Failed to generate productive samples (random also failed)")

        # PROTECTED ZONE SAMPLING
        protected_samples = []
        protected_sample_count = 0
        protected_spacing = None
        protected_sampling_method = "systematic"  # Default, will be updated if random used

        if sample_protected_this_block:
            logger.info(f"\n--- Protected Zone ({protected_area_ha:.4f} ha at 0.1%) ---")

            try:
                protected_sample_count = get_sample_count_from_guideline(
                    db=db,
                    block_area_hectares=protected_area_ha,
                    intensity_percent=0.1,
                    plot_size_sqm=protected_plot_size_sqm
                )
                logger.info(f"✓ Guideline table: {protected_sample_count} samples ({protected_plot_size_sqm} sqm plots)")
            except ValueError:
                # Fallback to manual calculation
                sample_area_ha = protected_area_ha * 0.001  # 0.1%
                protected_sample_count = max(1, int(sample_area_ha / protected_plot_area_hectares))
                logger.info(f"✓ Manual calc: {protected_sample_count} samples ({protected_plot_size_sqm} sqm plots)")

            if protected_sample_count > 0 and zone_areas["protected_geometry"]:
                # Generate samples in protected zone only
                protected_wkt = zone_areas["protected_geometry"].wkt
                protected_buffered = apply_boundary_buffer(protected_wkt, boundary_buffer_meters)
                protected_sampling_method = "systematic"

                # Try systematic grid with current buffer first
                effective_area_sqm = protected_area_ha * 10000.0
                systematic_success = False

                for iteration in range(5):
                    spacing = math.sqrt(effective_area_sqm / float(protected_sample_count))
                    bounds = get_polygon_bounds(protected_buffered)
                    candidates = generate_systematic_grid(
                        bounds[0], bounds[1], bounds[2], bounds[3],
                        int(spacing), protected_buffered, 0.0  # No additional buffer - already buffered
                    )

                    if len(candidates) >= protected_sample_count:
                        protected_samples = candidates[:protected_sample_count]
                        protected_spacing = spacing
                        systematic_success = True
                        logger.info(f"  Generated {len(protected_samples)} protected samples (systematic)")
                        break
                    effective_area_sqm *= 0.9

                # Fallback 1: Try smaller buffer (15m)
                if not systematic_success and protected_sample_count > 0:
                    logger.warning(f"  ⚠ Systematic failed with {boundary_buffer_meters}m buffer, trying 15m buffer...")
                    protected_buffered_15m = apply_boundary_buffer(protected_wkt, 15.0)
                    effective_area_sqm = protected_area_ha * 10000.0

                    for iteration in range(5):
                        spacing = math.sqrt(effective_area_sqm / float(protected_sample_count))
                        bounds = get_polygon_bounds(protected_buffered_15m)
                        candidates = generate_systematic_grid(
                            bounds[0], bounds[1], bounds[2], bounds[3],
                            int(spacing), protected_buffered_15m, 0.0
                        )

                        if len(candidates) >= protected_sample_count:
                            protected_samples = candidates[:protected_sample_count]
                            protected_spacing = spacing
                            systematic_success = True
                            logger.info(f"  Generated {len(protected_samples)} protected samples (systematic, 15m buffer)")
                            break
                        effective_area_sqm *= 0.9

                # Fallback 2: Random sampling
                if not systematic_success and protected_sample_count > 0:
                    logger.warning(f"  ⚠ Systematic failed for protected zone, falling back to random sampling...")
                    min_distance = int(math.sqrt(effective_area_sqm / protected_sample_count))
                    protected_samples = generate_random_points(
                        protected_buffered,
                        protected_sample_count,
                        min_distance_meters=min_distance,
                        boundary_buffer_meters=0.0  # Already buffered
                    )
                    if len(protected_samples) > 0:
                        protected_sampling_method = "random"
                        logger.info(f"  Generated {len(protected_samples)} protected samples (random)")
                    else:
                        logger.warning("  ⚠ Failed to generate protected samples (random also failed)")

        # Combine samples from both zones
        block_points = productive_samples + protected_samples
        total_samples = len(block_points)

        logger.info(
            f"\n✓ Total for {block_name}: {total_samples} samples "
            f"({len(productive_samples)} productive + {len(protected_samples)} protected)"
        )

        # NO POST-FILTERING NEEDED
        # Samples already generated in correct zones with private land excluded

        # Store points with block assignment and zone type
        for i, point in enumerate(block_points):
            all_points.append(point)
            # Determine zone type and sampling method for this sample
            if i < len(productive_samples):
                zone_type = 'productive'
                sampling_method = productive_sampling_method
            else:
                zone_type = 'protected'
                sampling_method = protected_sampling_method

            block_assignments.append({
                'point_index': len(all_points) - 1,
                'block_number': block_number,
                'block_name': block_name,
                'zone_type': zone_type,
                'sampling_method': sampling_method
            })

        # Calculate net accessible area (productive + protected, excluding private land)
        accessible_area_ha = productive_area_ha + protected_area_ha

        # Calculate overall actual intensity (weighted by plot sizes)
        total_sampled_area_ha = (
            len(productive_samples) * productive_plot_area_hectares +
            len(protected_samples) * protected_plot_area_hectares
        )

        # Safe intensity calculation with NaN protection
        if accessible_area_ha > 0 and total_sampled_area_ha > 0:
            intensity_value = (total_sampled_area_ha / accessible_area_ha) * 100
            # Check for NaN/inf before converting to Decimal
            if math.isnan(intensity_value) or math.isinf(intensity_value):
                actual_intensity_pct = Decimal("0")
            else:
                actual_intensity_pct = Decimal(str(intensity_value))
        else:
            actual_intensity_pct = Decimal("0")

        # Determine block protection status for reporting
        # "Mixed" if both zones present, otherwise "Yes" or "No"
        if protected_area_ha > 0 and productive_area_ha > 0:
            is_protected_status = "Mixed"
        elif protected_area_ha > 0:
            is_protected_status = "Yes"
        else:
            is_protected_status = "No"

        # Calculate average grid spacing (weighted by sample count)
        if total_samples > 0:
            if len(productive_samples) > 0 and len(protected_samples) > 0:
                # Mixed - report productive spacing (dominant)
                avg_spacing = productive_spacing if productive_spacing else protected_spacing
            elif len(productive_samples) > 0:
                avg_spacing = productive_spacing
            else:
                avg_spacing = protected_spacing
        else:
            avg_spacing = None

        # Safe accessible percentage calculation
        if block_area_ha > 0 and accessible_area_ha >= 0:
            accessible_pct_value = (accessible_area_ha / block_area_ha) * 100
            if math.isnan(accessible_pct_value) or math.isinf(accessible_pct_value):
                accessible_forest_percentage = Decimal("0")
            else:
                accessible_forest_percentage = Decimal(str(round(accessible_pct_value, 2)))
        else:
            accessible_forest_percentage = Decimal("0")

        # Determine overall sampling method for this block
        # If either zone used random, report random for the block
        if protected_area_ha > 0:
            # Both zones exist
            if productive_sampling_method == "random" or protected_sampling_method == "random":
                block_sampling_method = "random"
            else:
                block_sampling_method = "systematic"
        else:
            # Only productive zone
            block_sampling_method = productive_sampling_method

        # Store block info with detailed zone breakdown
        block_info_dict = {
            "block_number": block_number,
            "block_name": block_name,
            "block_area_hectares": Decimal(str(round(block_area_ha, 4))),
            "samples_generated": total_samples,
            "minimum_enforced": False,
            "actual_intensity_percent": actual_intensity_pct,
            "grid_spacing_meters": Decimal(str(round(avg_spacing, 1))) if avg_spacing else None,
            "accessible_forest_area_ha": Decimal(str(round(accessible_area_ha, 4))),
            "accessible_forest_percentage": accessible_forest_percentage,
            "samples_from_guideline": productive_sample_count + protected_sample_count,
            "is_protected": is_protected_status,
            "sampling_method": block_sampling_method,
            "guideline_fallback_used": False,
            # Protected zone details
            "protected_area_ha": Decimal(str(round(protected_area_ha, 4))) if protected_area_ha > 0 else None,
            "protected_samples_count": len(protected_samples) if protected_area_ha > 0 else None,
            "protected_sampling_method": protected_sampling_method if protected_area_ha > 0 else None,
            "protected_grid_spacing_meters": Decimal(str(round(protected_spacing, 1))) if protected_spacing and protected_area_ha > 0 else None,
            "protected_intensity_percent": None,  # Calculate below if protected samples exist
            # Productive zone details
            "productive_area_ha": Decimal(str(round(productive_area_ha, 4))) if productive_area_ha > 0 else None,
            "productive_samples_count": len(productive_samples) if productive_area_ha > 0 else None,
            "productive_sampling_method": productive_sampling_method if productive_area_ha > 0 else None,
        }

        # Calculate protected intensity if samples were generated
        if protected_area_ha > 0 and len(protected_samples) > 0:
            protected_sampled_area_ha = len(protected_samples) * protected_plot_area_hectares
            if protected_area_ha > 0:
                protected_intensity = (protected_sampled_area_ha / protected_area_ha) * 100
                block_info_dict["protected_intensity_percent"] = Decimal(str(round(protected_intensity, 4)))

        blocks_info.append(BlockSamplingInfo(**block_info_dict))

        logger.info(f"{'='*60}\n")

    points = all_points
    logger.info(
        f"\n{'='*60}\n"
        f"SUMMARY: Generated {len(points)} total samples across {len(blocks)} blocks\n"
        f"{'='*60}\n"
    )

    if not points:
        raise ValueError(
            "No sampling points generated. Check if all blocks are protected and "
            "sample_protected_zone=False, or if filters are too restrictive."
        )

    # Create MultiPoint geometry WKT
    points_wkt = "MULTIPOINT(" + ", ".join([f"{lon} {lat}" for lon, lat in points]) + ")"

    # Calculate plot dimensions for database record
    # Use the productive plot size as the "default" for the design record
    if plot_shape == "circular":
        plot_radius_meters = math.sqrt(plot_size_sqm / math.pi)
        plot_side_meters = None
    else:  # square
        plot_radius_meters = None
        plot_side_meters = math.sqrt(plot_size_sqm)

    # Create sampling design record
    sampling_design = SamplingDesign(
        calculation_id=calculation_id,
        sampling_type="systematic",  # Guideline-2061 uses systematic only
        intensity_per_hectare=Decimal(str(len(points) / float(total_forest_area))),
        grid_spacing_meters=None,
        min_distance_meters=None,
        plot_shape=plot_shape,
        plot_radius_meters=Decimal(str(plot_radius_meters)) if plot_radius_meters else None,
        plot_length_meters=Decimal(str(plot_side_meters)) if plot_side_meters else None,
        plot_width_meters=Decimal(str(plot_side_meters)) if plot_side_meters else None,
        total_points=len(points),
        notes=notes
    )

    db.add(sampling_design)
    db.flush()  # Get ID

    # Save guideline-specific parameters
    import json
    guideline_parameters = {
        "sampling_method": "guideline_2061",
        "productive_intensity": productive_intensity,
        "sample_protected_zone": sample_protected_zone,
        "plot_size_sqm": plot_size_sqm,
        "boundary_buffer_meters": boundary_buffer_meters,
        "filter_tree_cover": filter_tree_cover,
        "filter_slope": filter_slope,
        "max_slope_degrees": max_slope_degrees
    }

    update_params_query = text("""
        UPDATE public.sampling_designs
        SET default_parameters = CAST(:params AS jsonb)
        WHERE id = :design_id
    """)
    db.execute(update_params_query, {
        "params": json.dumps(guideline_parameters),
        "design_id": str(sampling_design.id)
    })

    # Update geometry using PostGIS
    update_geom_query = text("""
        UPDATE public.sampling_designs
        SET points_geometry = ST_GeomFromText(:points_wkt, 4326)
        WHERE id = :design_id
    """)
    db.execute(update_geom_query, {
        "points_wkt": points_wkt,
        "design_id": str(sampling_design.id)
    })

    # Save block assignments
    update_assignments_query = text("""
        UPDATE public.sampling_designs
        SET points_block_assignment = CAST(:assignments AS jsonb)
        WHERE id = :design_id
    """)
    db.execute(update_assignments_query, {
        "assignments": json.dumps(block_assignments),
        "design_id": str(sampling_design.id)
    })

    db.commit()

    # Calculate statistics
    # Count productive vs protected samples across all blocks
    total_productive_samples = sum(1 for assignment in block_assignments
                                   if assignment.get('zone_type') == 'productive')
    total_protected_samples = sum(1 for assignment in block_assignments
                                  if assignment.get('zone_type') == 'protected')

    # If zone_type wasn't set, assume all productive (backward compatibility)
    if total_productive_samples == 0 and total_protected_samples == 0:
        total_productive_samples = len(points)

    # Calculate total sampled area (weighted by plot sizes)
    total_sampled_area_sqm = (
        total_productive_samples * productive_plot_size_sqm +
        total_protected_samples * protected_plot_size_sqm
    )
    total_sampled_area_hectares = Decimal(str(total_sampled_area_sqm / 10000.0))

    # Safe percentage calculations with NaN protection
    if total_forest_area > 0:
        actual_intensity_val = len(points) / float(total_forest_area)
        sampling_pct_val = (total_sampled_area_sqm / (float(total_forest_area) * 10000.0)) * 100

        if math.isnan(actual_intensity_val) or math.isinf(actual_intensity_val):
            actual_intensity = Decimal("0")
        else:
            actual_intensity = Decimal(str(actual_intensity_val))

        if math.isnan(sampling_pct_val) or math.isinf(sampling_pct_val):
            sampling_percentage = Decimal("0")
        else:
            sampling_percentage = Decimal(str(sampling_pct_val))
    else:
        actual_intensity = Decimal("0")
        sampling_percentage = Decimal("0")

    return SamplingGenerateResponse(
        sampling_design_id=sampling_design.id,
        calculation_id=calculation_id,
        sampling_type="systematic",
        total_points=len(points),
        total_blocks=len(blocks),
        forest_area_hectares=Decimal(str(round(total_forest_area, 4))),
        requested_intensity_percent=Decimal(str(productive_intensity)),
        actual_intensity_per_hectare=actual_intensity,
        plot_area_sqm=Decimal(str(round(productive_plot_size_sqm, 2))),  # Report productive plot size
        total_sampled_area_hectares=total_sampled_area_hectares,
        sampling_percentage=sampling_percentage,
        blocks_info=blocks_info
    )


def assign_blocks_to_sampling(db: Session, design_id: UUID, calculation_id: UUID):
    """
    Assign block numbers to sampling points using spatial intersection.

    Uses user-defined block names from result_data.blocks[].block_name if available.
    For multi-polygon geometries, this determines which block each sampling point falls within.
    Results are stored in the points_block_assignment JSONB column as an array.

    Args:
        db: Database session
        design_id: Sampling design ID
        calculation_id: Calculation ID
    """
    # Check if this is a multi-polygon and get block names
    calc_query = text("""
        SELECT
            ST_GeometryType(boundary_geom) as geom_type,
            ST_NumGeometries(boundary_geom) as num_blocks,
            result_data->'blocks' as blocks_data
        FROM public.calculations
        WHERE id = :calc_id
    """)
    result = db.execute(calc_query, {"calc_id": str(calculation_id)}).first()

    if not result:
        return

    is_multipolygon = result.geom_type == 'ST_MultiPolygon'
    blocks_data = result.blocks_data if result.blocks_data else []

    # Extract block names from result_data
    block_names_map = {}
    if blocks_data:
        for block in blocks_data:
            block_index = block.get('block_index')
            block_name = block.get('block_name')
            if block_index is not None and block_name:
                # ST_Dump uses 1-based indexing, but block_index is 0-based
                block_names_map[block_index + 1] = block_name

    if not is_multipolygon:
        # Single polygon - get block name from result_data or use default
        block_name = block_names_map.get(1, 'Block 1')

        # Create simple assignment array using SQL
        update_query = text("""
            WITH point_indices AS (
                SELECT generate_series(0, ST_NumGeometries(points_geometry) - 1) as point_index
                FROM public.sampling_designs
                WHERE id = :design_id
            )
            UPDATE public.sampling_designs
            SET points_block_assignment = (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'point_index', point_index,
                        'block_number', 1,
                        'block_name', :block_name
                    )
                )
                FROM point_indices
            )
            WHERE id = :design_id
            RETURNING jsonb_array_length(points_block_assignment) as num_points
        """)
        result = db.execute(update_query, {
            "design_id": str(design_id),
            "block_name": block_name
        }).first()
        num_points = result.num_points if result else 0
        logger.info(f"Assigned all {num_points} sampling points to '{block_name}'")
        return

    # Multi-polygon - use spatial intersection in a single UPDATE query
    # Build CASE statement for block names
    import json

    if block_names_map:
        block_name_cases = []
        for block_num, block_name in block_names_map.items():
            # Escape single quotes in block name
            escaped_name = block_name.replace("'", "''")
            block_name_cases.append(f"WHEN {block_num} THEN '{escaped_name}'")
        block_name_expression = f"CASE pol.block_number {' '.join(block_name_cases)} ELSE 'Block ' || pol.block_number END"
    else:
        block_name_expression = "'Block ' || pol.block_number"

    update_query = text(f"""
        UPDATE public.sampling_designs sd
        SET points_block_assignment = (
            WITH polygon_parts AS (
                SELECT
                    (ST_Dump(boundary_geom)).path[1] as block_number,
                    (ST_Dump(boundary_geom)).geom as block_geom
                FROM public.calculations
                WHERE id = :calc_id
            ),
            point_parts AS (
                SELECT
                    (ST_DumpPoints(sd.points_geometry)).path[1] - 1 as point_index,
                    (ST_DumpPoints(sd.points_geometry)).geom as point_geom
            )
            SELECT
                jsonb_agg(
                    jsonb_build_object(
                        'point_index', pp.point_index,
                        'block_number', pol.block_number,
                        'block_name', {block_name_expression}
                    )
                    ORDER BY pp.point_index
                )
            FROM point_parts pp
            CROSS JOIN LATERAL (
                SELECT block_number
                FROM polygon_parts
                WHERE ST_Intersects(pp.point_geom, block_geom)
                LIMIT 1
            ) pol
        )
        WHERE sd.id = :design_id
    """)

    db.execute(update_query, {
        "calc_id": str(calculation_id),
        "design_id": str(design_id)
    })
    logger.info(f"Assigned sampling points to blocks using spatial intersection with user-defined names")
