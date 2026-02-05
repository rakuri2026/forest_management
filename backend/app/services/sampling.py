"""
Sampling design service for forest inventory
Implements systematic, random, and stratified sampling algorithms
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
from app.schemas.sampling import SamplingGenerateResponse

logger = logging.getLogger(__name__)


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


def generate_systematic_grid(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    grid_spacing_meters: int,
    polygon_wkt: str
) -> List[Tuple[float, float]]:
    """
    Generate systematic grid of points within polygon.

    Args:
        min_lon, min_lat, max_lon, max_lat: Bounding box
        grid_spacing_meters: Grid spacing in meters
        polygon_wkt: WKT of polygon to constrain points

    Returns:
        List of (lon, lat) tuples
    """
    # Convert grid spacing to approximate degrees
    # At Nepal's latitude (~28°), 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(28°) ≈ 98 km
    meters_per_degree_lat = 111000.0
    meters_per_degree_lon = 98000.0

    spacing_lat = grid_spacing_meters / meters_per_degree_lat
    spacing_lon = grid_spacing_meters / meters_per_degree_lon

    # Load polygon for intersection testing
    polygon = wkt.loads(polygon_wkt)

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
    min_distance_meters: Optional[int] = None
) -> List[Tuple[float, float]]:
    """
    Generate random points within polygon.

    Args:
        polygon_wkt: WKT of polygon
        num_points: Number of points to generate
        min_distance_meters: Minimum distance between points (optional)

    Returns:
        List of (lon, lat) tuples
    """
    polygon = wkt.loads(polygon_wkt)
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
    num_strata: int = 4
) -> List[Tuple[float, float]]:
    """
    Generate stratified random points within polygon.
    Divides polygon into grid strata and samples from each.

    Args:
        polygon_wkt: WKT of polygon
        num_points: Total number of points to generate
        num_strata: Number of strata (grid cells) to divide polygon into

    Returns:
        List of (lon, lat) tuples
    """
    polygon = wkt.loads(polygon_wkt)
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
                stratum_points = generate_random_points(stratum_wkt, n_points)
                points.extend(stratum_points)

            except Exception as e:
                logger.warning(f"Error processing stratum: {str(e)}")
                continue

    logger.info(f"Generated {len(points)} stratified random points")
    return points


def create_sampling_design(
    db: Session,
    calculation_id: UUID,
    sampling_type: str,
    intensity_per_hectare: Optional[Decimal] = None,
    grid_spacing_meters: Optional[int] = None,
    min_distance_meters: Optional[int] = None,
    plot_shape: Optional[str] = None,
    plot_radius_meters: Optional[Decimal] = None,
    plot_length_meters: Optional[Decimal] = None,
    plot_width_meters: Optional[Decimal] = None,
    notes: Optional[str] = None
) -> SamplingGenerateResponse:
    """
    Create sampling design and generate sampling points.

    Args:
        db: Database session
        calculation_id: Calculation ID
        sampling_type: 'systematic', 'random', or 'stratified'
        intensity_per_hectare: Points per hectare (for random/stratified)
        grid_spacing_meters: Grid spacing (for systematic)
        min_distance_meters: Minimum distance between points
        plot_shape: 'circular', 'square', or 'rectangular'
        plot_radius_meters: Plot radius (for circular)
        plot_length_meters: Plot length (for rectangular)
        plot_width_meters: Plot width (for rectangular)
        notes: Design notes

    Returns:
        SamplingGenerateResponse with summary statistics
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    # Get boundary geometry as WKT
    geom_query = text("""
        SELECT
            ST_AsText(boundary_geom) as wkt,
            ST_Area(ST_Transform(boundary_geom,
                CASE
                    WHEN ST_X(ST_Centroid(boundary_geom)) < 84.0 THEN 32644
                    ELSE 32645
                END
            )) / 10000.0 as area_hectares
        FROM public.calculations
        WHERE id = :calc_id
    """)
    result = db.execute(geom_query, {"calc_id": str(calculation_id)}).first()
    if not result:
        raise ValueError("Failed to retrieve geometry")

    geom_wkt = result.wkt
    area_hectares = float(result.area_hectares)

    logger.info(f"Generating {sampling_type} sampling for {area_hectares:.2f} hectares")

    # Generate sampling points based on type
    if sampling_type == "systematic":
        if not grid_spacing_meters:
            raise ValueError("grid_spacing_meters required for systematic sampling")

        bounds = get_polygon_bounds(geom_wkt)
        points = generate_systematic_grid(
            bounds[0], bounds[1], bounds[2], bounds[3],
            grid_spacing_meters,
            geom_wkt
        )

    elif sampling_type == "random":
        if not intensity_per_hectare:
            raise ValueError("intensity_per_hectare required for random sampling")

        num_points = int(float(intensity_per_hectare) * area_hectares)
        points = generate_random_points(geom_wkt, num_points, min_distance_meters)

    elif sampling_type == "stratified":
        if not intensity_per_hectare:
            raise ValueError("intensity_per_hectare required for stratified sampling")

        num_points = int(float(intensity_per_hectare) * area_hectares)
        points = generate_stratified_points(geom_wkt, num_points)

    else:
        raise ValueError(f"Invalid sampling_type: {sampling_type}")

    if not points:
        raise ValueError("No sampling points generated - check polygon and parameters")

    # Calculate plot area
    plot_area_sqm = None
    if plot_shape == "circular" and plot_radius_meters:
        plot_area_sqm = math.pi * float(plot_radius_meters) ** 2
    elif plot_shape in ["square", "rectangular"] and plot_length_meters and plot_width_meters:
        plot_area_sqm = float(plot_length_meters) * float(plot_width_meters)

    # Create MultiPoint geometry WKT
    points_wkt = "MULTIPOINT(" + ", ".join([f"{lon} {lat}" for lon, lat in points]) + ")"

    # Create sampling design record
    sampling_design = SamplingDesign(
        calculation_id=calculation_id,
        sampling_type=sampling_type,
        intensity_per_hectare=intensity_per_hectare,
        grid_spacing_meters=grid_spacing_meters,
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

    # Assign blocks to sampling points
    assign_blocks_to_sampling(db, sampling_design.id, calculation_id)

    db.commit()

    # Calculate statistics
    actual_intensity = Decimal(str(len(points) / area_hectares))
    total_sampled_area_hectares = None
    sampling_percentage = None

    if plot_area_sqm:
        total_sampled_area_sqm = plot_area_sqm * len(points)
        total_sampled_area_hectares = Decimal(str(total_sampled_area_sqm / 10000.0))
        sampling_percentage = Decimal(str((total_sampled_area_sqm / (area_hectares * 10000.0)) * 100))

    return SamplingGenerateResponse(
        sampling_design_id=sampling_design.id,
        calculation_id=calculation_id,
        sampling_type=sampling_type,
        total_points=len(points),
        forest_area_hectares=Decimal(str(round(area_hectares, 4))),
        actual_intensity_per_hectare=actual_intensity,
        plot_area_sqm=Decimal(str(round(plot_area_sqm, 2))) if plot_area_sqm else None,
        total_sampled_area_hectares=total_sampled_area_hectares,
        sampling_percentage=sampling_percentage
    )


def get_sampling_points_geojson(db: Session, design_id: UUID) -> dict:
    """
    Get sampling points as GeoJSON.

    Args:
        db: Database session
        design_id: Sampling design ID

    Returns:
        GeoJSON FeatureCollection
    """
    query = text("""
        SELECT
            ST_AsGeoJSON(points_geometry) as geojson,
            sampling_type,
            total_points
        FROM public.sampling_designs
        WHERE id = :design_id
    """)

    result = db.execute(query, {"design_id": str(design_id)}).first()

    if not result:
        raise ValueError(f"Sampling design {design_id} not found")

    import json
    geojson_data = json.loads(result.geojson)

    # Convert to FeatureCollection with individual points
    features = []
    if geojson_data['type'] == 'MultiPoint':
        for i, coord in enumerate(geojson_data['coordinates'], 1):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": coord
                },
                "properties": {
                    "plot_number": i,
                    "sampling_type": result.sampling_type
                }
            }
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }


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
