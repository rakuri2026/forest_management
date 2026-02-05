"""
Fieldbook service for boundary vertex extraction and interpolation
"""
import math
from typing import List, Tuple, Optional
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from shapely import wkt
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import logging

from app.models.calculation import Calculation
from app.models.fieldbook import Fieldbook
from app.schemas.fieldbook import FieldbookGenerateResponse

logger = logging.getLogger(__name__)


def calculate_azimuth(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate azimuth (bearing) from point 1 to point 2 in degrees.

    Args:
        lon1, lat1: Coordinates of first point (WGS84)
        lon2, lat2: Coordinates of second point (WGS84)

    Returns:
        Azimuth in degrees (0-360, where 0 is North)
    """
    # Convert to radians
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)

    # Calculate difference
    dlon = lon2_rad - lon1_rad

    # Calculate azimuth
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)

    azimuth_rad = math.atan2(x, y)
    azimuth_deg = math.degrees(azimuth_rad)

    # Normalize to 0-360
    azimuth_deg = (azimuth_deg + 360) % 360

    return round(azimuth_deg, 2)


def calculate_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.

    Args:
        lon1, lat1: Coordinates of first point (WGS84)
        lon2, lat2: Coordinates of second point (WGS84)

    Returns:
        Distance in meters
    """
    # Earth radius in meters
    R = 6371000.0

    # Convert to radians
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    distance = R * c
    return round(distance, 2)


def interpolate_point(lon1: float, lat1: float, lon2: float, lat2: float, fraction: float) -> Tuple[float, float]:
    """
    Interpolate a point along a great circle path between two points.

    Args:
        lon1, lat1: Start point (WGS84)
        lon2, lat2: End point (WGS84)
        fraction: Fraction of distance (0.0 to 1.0)

    Returns:
        Tuple of (longitude, latitude) of interpolated point
    """
    # Convert to radians
    lon1_rad = math.radians(lon1)
    lat1_rad = math.radians(lat1)
    lon2_rad = math.radians(lon2)
    lat2_rad = math.radians(lat2)

    # Calculate angular distance
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    d = 2 * math.asin(math.sqrt(a))

    # Interpolate
    a_val = math.sin((1-fraction) * d) / math.sin(d)
    b_val = math.sin(fraction * d) / math.sin(d)

    x = a_val * math.cos(lat1_rad) * math.cos(lon1_rad) + b_val * math.cos(lat2_rad) * math.cos(lon2_rad)
    y = a_val * math.cos(lat1_rad) * math.sin(lon1_rad) + b_val * math.cos(lat2_rad) * math.sin(lon2_rad)
    z = a_val * math.sin(lat1_rad) + b_val * math.sin(lat2_rad)

    lat_interp = math.atan2(z, math.sqrt(x**2 + y**2))
    lon_interp = math.atan2(y, x)

    return (math.degrees(lon_interp), math.degrees(lat_interp))


def convert_to_utm(lon: float, lat: float) -> Tuple[float, float, int]:
    """
    Convert WGS84 coordinates to UTM.

    Nepal uses UTM zones 44N and 45N.
    Zone 44N: 78°E to 84°E
    Zone 45N: 84°E to 90°E

    Args:
        lon, lat: WGS84 coordinates

    Returns:
        Tuple of (easting, northing, utm_zone)
    """
    # Determine UTM zone for Nepal
    if lon < 84.0:
        utm_zone = 44
        srid = 32644
    else:
        utm_zone = 45
        srid = 32645

    return (0.0, 0.0, utm_zone)  # Placeholder - will use PostGIS for actual conversion


def extract_boundary_vertices(geom_wkt: str) -> List[Tuple[float, float]]:
    """
    Extract vertices from polygon boundary.

    Args:
        geom_wkt: WKT string of polygon or multipolygon

    Returns:
        List of (lon, lat) tuples representing vertices
    """
    try:
        geom = wkt.loads(geom_wkt)
        vertices = []

        if isinstance(geom, Polygon):
            # Extract exterior ring vertices (exclude last duplicate point)
            coords = list(geom.exterior.coords)[:-1]
            vertices.extend(coords)
        elif isinstance(geom, MultiPolygon):
            # Extract from all polygons
            for polygon in geom.geoms:
                coords = list(polygon.exterior.coords)[:-1]
                vertices.extend(coords)
        else:
            raise ValueError(f"Unsupported geometry type: {type(geom)}")

        return vertices

    except Exception as e:
        logger.error(f"Error extracting vertices: {str(e)}")
        raise ValueError(f"Failed to extract vertices: {str(e)}")


def extract_boundary_vertices_with_blocks(geom_wkt: str) -> List[Tuple[float, float, int]]:
    """
    Extract vertices from polygon boundary with block information.

    Args:
        geom_wkt: WKT string of polygon or multipolygon

    Returns:
        List of (lon, lat, block_number) tuples representing vertices
    """
    try:
        geom = wkt.loads(geom_wkt)
        vertices_with_blocks = []

        if isinstance(geom, Polygon):
            # Single polygon - all vertices belong to block 1
            coords = list(geom.exterior.coords)[:-1]
            for coord in coords:
                vertices_with_blocks.append((coord[0], coord[1], 1))
        elif isinstance(geom, MultiPolygon):
            # Multiple polygons - assign block numbers
            for block_num, polygon in enumerate(geom.geoms, start=1):
                coords = list(polygon.exterior.coords)[:-1]
                for coord in coords:
                    vertices_with_blocks.append((coord[0], coord[1], block_num))
        else:
            raise ValueError(f"Unsupported geometry type: {type(geom)}")

        return vertices_with_blocks

    except Exception as e:
        logger.error(f"Error extracting vertices with blocks: {str(e)}")
        raise ValueError(f"Failed to extract vertices with blocks: {str(e)}")


def generate_fieldbook_points(
    db: Session,
    calculation_id: UUID,
    interpolation_distance: float = 20.0,
    extract_elevation: bool = True
) -> FieldbookGenerateResponse:
    """
    Generate fieldbook points from calculation boundary.

    1. Extract vertices from polygon
    2. Interpolate points every N meters between vertices
    3. Calculate azimuth and distance to next point
    4. Extract elevation from DEM
    5. Convert to UTM coordinates
    6. Save to database

    Args:
        db: Database session
        calculation_id: ID of calculation
        interpolation_distance: Distance between interpolated points (meters)
        extract_elevation: Whether to extract elevation from DEM

    Returns:
        FieldbookGenerateResponse with summary statistics
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    # Clear existing fieldbook points
    db.query(Fieldbook).filter(Fieldbook.calculation_id == calculation_id).delete()
    db.commit()

    # Get boundary geometry as WKT and check if it's multi-polygon
    geom_wkt_query = text("""
        SELECT
            ST_AsText(boundary_geom) as wkt,
            ST_GeometryType(boundary_geom) as geom_type,
            ST_NumGeometries(boundary_geom) as num_blocks
        FROM public.calculations
        WHERE id = :calc_id
    """)
    result = db.execute(geom_wkt_query, {"calc_id": str(calculation_id)}).first()
    if not result:
        raise ValueError("Failed to retrieve geometry")

    geom_wkt = result.wkt
    is_multipolygon = result.geom_type == 'ST_MultiPolygon'
    num_blocks = result.num_blocks if is_multipolygon else 1

    logger.info(f"Processing {result.geom_type} with {num_blocks} block(s)")

    # Extract vertices (this will handle both Polygon and MultiPolygon)
    vertices = extract_boundary_vertices(geom_wkt)
    if len(vertices) < 3:
        raise ValueError("Polygon must have at least 3 vertices")

    logger.info(f"Extracted {len(vertices)} vertices from boundary")

    # Generate fieldbook points
    fieldbook_points = []
    point_number = 1
    total_perimeter = 0.0
    vertex_count = 0
    interpolated_count = 0

    # Process each edge
    for i in range(len(vertices)):
        v1 = vertices[i]
        v2 = vertices[(i + 1) % len(vertices)]  # Wrap around to first vertex

        lon1, lat1 = v1
        lon2, lat2 = v2

        # Calculate distance between vertices
        edge_distance = calculate_distance(lon1, lat1, lon2, lat2)
        total_perimeter += edge_distance

        # Add first vertex
        fieldbook_points.append({
            'point_number': point_number,
            'point_type': 'vertex',
            'longitude': lon1,
            'latitude': lat1,
        })
        vertex_count += 1
        point_number += 1

        # Interpolate points if distance > interpolation_distance
        if edge_distance > interpolation_distance:
            num_intervals = int(edge_distance / interpolation_distance)
            for j in range(1, num_intervals + 1):
                fraction = (j * interpolation_distance) / edge_distance
                if fraction < 1.0:  # Don't duplicate the end vertex
                    lon_interp, lat_interp = interpolate_point(lon1, lat1, lon2, lat2, fraction)
                    fieldbook_points.append({
                        'point_number': point_number,
                        'point_type': 'interpolated',
                        'longitude': lon_interp,
                        'latitude': lat_interp,
                    })
                    interpolated_count += 1
                    point_number += 1

    logger.info(f"Generated {len(fieldbook_points)} total points ({vertex_count} vertices + {interpolated_count} interpolated)")

    # Calculate azimuth, distance, elevation, and UTM for each point
    for i in range(len(fieldbook_points)):
        current = fieldbook_points[i]
        next_point = fieldbook_points[(i + 1) % len(fieldbook_points)]

        lon1 = float(current['longitude'])
        lat1 = float(current['latitude'])
        lon2 = float(next_point['longitude'])
        lat2 = float(next_point['latitude'])

        # Calculate azimuth and distance to next point
        current['azimuth_to_next'] = calculate_azimuth(lon1, lat1, lon2, lat2)
        current['distance_to_next'] = calculate_distance(lon1, lat1, lon2, lat2)

        # UTM conversion (placeholder - will use PostGIS in bulk)
        _, _, utm_zone = convert_to_utm(lon1, lat1)
        current['utm_zone'] = utm_zone

    # Bulk insert to database
    if fieldbook_points:
        # Convert to Fieldbook objects
        fieldbook_objects = []
        for point in fieldbook_points:
            fb_point = Fieldbook(
                calculation_id=calculation_id,
                point_number=point['point_number'],
                point_type=point['point_type'],
                longitude=Decimal(str(point['longitude'])),
                latitude=Decimal(str(point['latitude'])),
                azimuth_to_next=Decimal(str(point['azimuth_to_next'])),
                distance_to_next=Decimal(str(point['distance_to_next'])),
                utm_zone=point['utm_zone'],
            )
            fieldbook_objects.append(fb_point)

        db.bulk_save_objects(fieldbook_objects)
        db.commit()

        # Update with PostGIS-calculated UTM and elevation
        if extract_elevation:
            update_utm_and_elevation(db, calculation_id)

        # Assign block numbers to points based on spatial intersection
        assign_blocks_to_fieldbook(db, calculation_id)

    # Calculate summary statistics
    elevation_stats = get_elevation_stats(db, calculation_id) if extract_elevation else None

    return FieldbookGenerateResponse(
        calculation_id=calculation_id,
        total_vertices=vertex_count,
        interpolated_points=interpolated_count,
        total_points=len(fieldbook_points),
        total_perimeter_meters=Decimal(str(round(total_perimeter, 2))),
        avg_elevation_meters=elevation_stats['avg'] if elevation_stats else None,
        min_elevation_meters=elevation_stats['min'] if elevation_stats else None,
        max_elevation_meters=elevation_stats['max'] if elevation_stats else None,
    )


def update_utm_and_elevation(db: Session, calculation_id: UUID):
    """
    Update fieldbook points with UTM coordinates and elevation using PostGIS.

    Args:
        db: Database session
        calculation_id: Calculation ID
    """
    # Update UTM coordinates using PostGIS
    utm_update_query = text("""
        UPDATE public.fieldbook
        SET
            point_geometry = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
            easting_utm = CASE
                WHEN longitude < 84.0 THEN ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 32644))
                ELSE ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 32645))
            END,
            northing_utm = CASE
                WHEN longitude < 84.0 THEN ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 32644))
                ELSE ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 32645))
            END,
            utm_zone = CASE
                WHEN longitude < 84.0 THEN 44
                ELSE 45
            END
        WHERE calculation_id = :calc_id
    """)
    db.execute(utm_update_query, {"calc_id": str(calculation_id)})

    # Extract elevation from DEM
    elevation_update_query = text("""
        UPDATE public.fieldbook fb
        SET elevation = (
            SELECT ST_Value(rast, fb.point_geometry)
            FROM rasters.dem
            WHERE ST_Intersects(rast, fb.point_geometry)
            LIMIT 1
        )
        WHERE fb.calculation_id = :calc_id
        AND fb.point_geometry IS NOT NULL
    """)
    db.execute(elevation_update_query, {"calc_id": str(calculation_id)})

    db.commit()
    logger.info(f"Updated UTM coordinates and elevation for fieldbook {calculation_id}")


def assign_blocks_to_fieldbook(db: Session, calculation_id: UUID):
    """
    Assign block numbers and names to fieldbook points using spatial intersection.

    Filters out points that are not within the actual forest boundary or within 2m of it.
    Uses user-defined block names from result_data.blocks[].block_name if available.

    For multi-polygon geometries, this determines which block (polygon) each point belongs to.
    For single polygon, all points are assigned to block 1.

    Args:
        db: Database session
        calculation_id: Calculation ID
    """
    # First, check if this is a multi-polygon and get block names
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
    # blocks_data is a list with block_index and block_name
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

        # Assign all points within or near (2m) the boundary to block 1
        # Filter out points that are outside
        simple_update_query = text("""
            UPDATE public.fieldbook fb
            SET
                block_number = 1,
                block_name = :block_name
            FROM public.calculations c
            WHERE fb.calculation_id = :calc_id
            AND c.id = :calc_id
            AND fb.point_geometry IS NOT NULL
            AND (
                ST_Intersects(fb.point_geometry, c.boundary_geom)
                OR ST_DWithin(fb.point_geometry::geography, c.boundary_geom::geography, 2)
            )
        """)
        db.execute(simple_update_query, {
            "calc_id": str(calculation_id),
            "block_name": block_name
        })

        # Delete points that are NOT within boundary or 2m buffer
        delete_query = text("""
            DELETE FROM public.fieldbook fb
            USING public.calculations c
            WHERE fb.calculation_id = :calc_id
            AND c.id = :calc_id
            AND fb.point_geometry IS NOT NULL
            AND NOT (
                ST_Intersects(fb.point_geometry, c.boundary_geom)
                OR ST_DWithin(fb.point_geometry::geography, c.boundary_geom::geography, 2)
            )
        """)
        deleted_result = db.execute(delete_query, {"calc_id": str(calculation_id)})
        db.commit()
        logger.info(f"Assigned all fieldbook points to '{block_name}' (single polygon), deleted {deleted_result.rowcount} points outside boundary")
        return

    # Multi-polygon - use spatial intersection to assign blocks
    # Build SQL with block names directly embedded (safe since we control the data)
    import json

    # Build CASE statement for block names
    if block_names_map:
        block_name_cases = []
        for block_num, block_name in block_names_map.items():
            # Escape single quotes in block name
            escaped_name = block_name.replace("'", "''")
            block_name_cases.append(f"WHEN {block_num} THEN '{escaped_name}'")
        block_name_expression = f"CASE pp.block_number {' '.join(block_name_cases)} ELSE 'Block ' || pp.block_number END"
    else:
        block_name_expression = "'Block ' || pp.block_number"

    block_assignment_query = text(f"""
        WITH polygon_parts AS (
            SELECT
                (ST_Dump(boundary_geom)).path[1] as block_number,
                (ST_Dump(boundary_geom)).geom as block_geom
            FROM public.calculations
            WHERE id = :calc_id
        )
        UPDATE public.fieldbook fb
        SET
            block_number = pp.block_number,
            block_name = {block_name_expression}
        FROM polygon_parts pp
        WHERE fb.calculation_id = :calc_id
        AND fb.point_geometry IS NOT NULL
        AND (
            ST_Intersects(fb.point_geometry, pp.block_geom)
            OR ST_DWithin(fb.point_geometry::geography, pp.block_geom::geography, 2)
        )
    """)

    db.execute(block_assignment_query, {
        "calc_id": str(calculation_id)
    })

    # Delete points that are NOT within any block boundary or 2m buffer
    delete_query = text("""
        DELETE FROM public.fieldbook fb
        USING public.calculations c
        WHERE fb.calculation_id = :calc_id
        AND c.id = :calc_id
        AND fb.point_geometry IS NOT NULL
        AND NOT (
            ST_Intersects(fb.point_geometry, c.boundary_geom)
            OR ST_DWithin(fb.point_geometry::geography, c.boundary_geom::geography, 2)
        )
    """)

    deleted_result = db.execute(delete_query, {"calc_id": str(calculation_id)})
    db.commit()
    logger.info(f"Assigned fieldbook points to blocks using spatial intersection, deleted {deleted_result.rowcount} points outside boundaries")


def get_elevation_stats(db: Session, calculation_id: UUID) -> Optional[dict]:
    """
    Get elevation statistics for fieldbook points.

    Args:
        db: Database session
        calculation_id: Calculation ID

    Returns:
        Dict with min, max, avg elevation
    """
    stats_query = text("""
        SELECT
            MIN(elevation) as min_elevation,
            MAX(elevation) as max_elevation,
            AVG(elevation) as avg_elevation
        FROM public.fieldbook
        WHERE calculation_id = :calc_id
        AND elevation IS NOT NULL
    """)

    result = db.execute(stats_query, {"calc_id": str(calculation_id)}).first()

    if result and result.avg_elevation:
        return {
            'min': Decimal(str(round(float(result.min_elevation), 2))),
            'max': Decimal(str(round(float(result.max_elevation), 2))),
            'avg': Decimal(str(round(float(result.avg_elevation), 2))),
        }

    return None
