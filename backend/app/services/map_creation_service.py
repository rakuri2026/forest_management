from typing import Dict, List, Any, Tuple
from shapely.geometry import shape, mapping
from shapely.wkt import dumps as wkt_dumps
from geoalchemy2.shape import from_shape
import json
import logging

# Configure logging for geometry validation
logger = logging.getLogger(__name__)

# Geometry validation tolerance constants
TOLERANCE_DEGREES = 1e-8  # ~1mm at equator
AREA_RATIO_THRESHOLD = 0.9999  # 99.99% of block must be inside boundary


def geojson_to_wkt(geojson_geometry: Dict[str, Any]) -> str:
    """
    Convert GeoJSON geometry to WKT format for PostGIS storage

    Args:
        geojson_geometry: GeoJSON geometry dict (e.g., {"type": "Polygon", "coordinates": [...]})

    Returns:
        WKT string with SRID prefix
    """
    try:
        # Convert GeoJSON to Shapely geometry
        geom = shape(geojson_geometry)

        # Convert to WKT
        wkt = wkt_dumps(geom)

        # Add SRID prefix for PostGIS (WGS84 = 4326)
        return f'SRID=4326;{wkt}'
    except Exception as e:
        raise ValueError(f"Failed to convert GeoJSON to WKT: {str(e)}")


def process_map_creation_data(
    outer_boundary: Dict[str, Any],
    blocks: List[Dict[str, Any]],
    gps_points: List[Dict[str, Any]] = None,
    sub_areas: List[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Process map creation data and prepare for database storage

    Args:
        outer_boundary: GeoJSON geometry of outer boundary
        blocks: List of block definitions with geometries
        gps_points: Optional list of GPS points used
        sub_areas: Optional list of sub-area definitions

    Returns:
        Tuple of (WKT geometry string, metadata dict)
    """
    try:
        # Convert outer boundary to WKT
        boundary_wkt = geojson_to_wkt(outer_boundary)

        # Prepare metadata structure
        metadata = {
            "creation_method": "map_creation",
            "total_blocks": len(blocks),
            "blocks": [],
        }

        # Process blocks
        for block in blocks:
            block_geom = shape(block["geometry"])
            block_data = {
                "block_id": block["id"],
                "block_name": block["name"],
                "area_hectares": block["area"],
                "geometry": block["geometry"],  # Store as GeoJSON
                "centroid": {
                    "lon": block_geom.centroid.x,
                    "lat": block_geom.centroid.y,
                },
            }
            metadata["blocks"].append(block_data)

        # Store GPS points metadata if provided
        if gps_points:
            metadata["gps_points"] = gps_points
            metadata["gps_points_count"] = len(gps_points)

        # Store sub-areas metadata if provided
        if sub_areas:
            metadata["sub_areas"] = []
            excluded_area_total = 0
            for sub_area in sub_areas:
                is_excluded = sub_area.get("isExcluded", False) or sub_area.get("is_excluded", False)
                sub_area_data = {
                    "id": sub_area["id"],
                    "name": sub_area["name"],
                    "category": sub_area["category"],
                    "area_hectares": sub_area["area"],
                    "block_id": sub_area.get("blockId"),
                    "block_name": sub_area.get("blockName"),
                    "geometry": sub_area["geometry"],
                    "is_excluded": is_excluded,  # Track if this is excluded from forest calculations (private land)
                }
                metadata["sub_areas"].append(sub_area_data)

                # Track excluded area
                if is_excluded:
                    excluded_area_total += sub_area["area"]

            metadata["sub_areas_count"] = len(sub_areas)
            metadata["excluded_area_hectares"] = excluded_area_total

        return boundary_wkt, metadata

    except Exception as e:
        raise ValueError(f"Failed to process map creation data: {str(e)}")


def validate_map_creation_data(
    outer_boundary: Dict[str, Any],
    blocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Validate map creation data before processing

    Args:
        outer_boundary: GeoJSON geometry of outer boundary
        blocks: List of block definitions

    Returns:
        Validation result dict with 'valid' boolean and optional 'errors' list
    """
    errors = []

    try:
        # Validate outer boundary
        outer_geom = shape(outer_boundary)
        if not outer_geom.is_valid:
            errors.append("Outer boundary geometry is invalid")

        if outer_geom.area == 0:
            errors.append("Outer boundary has zero area")

        # Validate blocks
        if len(blocks) == 0:
            errors.append("At least one block is required")

        for i, block in enumerate(blocks):
            try:
                block_geom = shape(block["geometry"])

                if not block_geom.is_valid:
                    errors.append(f"Block '{block['name']}' has invalid geometry")

                if block_geom.area == 0:
                    errors.append(f"Block '{block['name']}' has zero area")

                # Check if block is within outer boundary with tolerance
                # Use multi-layer validation to handle floating-point precision issues
                is_valid = False
                validation_method = ""

                # Method 1: Strict containment (fastest)
                if block_geom.within(outer_geom):
                    is_valid = True
                    validation_method = "strict_within"
                else:
                    # Method 2: Area ratio comparison (handles microscopic overflow)
                    try:
                        intersection = block_geom.intersection(outer_geom)
                        if block_geom.area > 0:
                            area_ratio = intersection.area / block_geom.area
                            if area_ratio >= AREA_RATIO_THRESHOLD:
                                is_valid = True
                                validation_method = f"area_ratio ({area_ratio:.6f})"
                                logger.info(f"Block '{block['name']}' passed via area ratio: {area_ratio:.6f}")
                    except Exception as e:
                        logger.warning(f"Area ratio check failed for '{block['name']}': {e}")

                    # Method 3: Buffered tolerance check (last resort)
                    if not is_valid:
                        try:
                            # Create a slightly expanded outer boundary
                            buffered_outer = outer_geom.buffer(TOLERANCE_DEGREES)
                            if block_geom.within(buffered_outer):
                                # Double-check it's not significantly outside
                                outside_part = block_geom.difference(outer_geom)
                                if outside_part.area < 1e-6:  # Less than ~0.01 m²
                                    is_valid = True
                                    validation_method = "tolerance_buffer"
                                    logger.info(f"Block '{block['name']}' passed via buffer tolerance")
                        except Exception as e:
                            logger.warning(f"Buffer tolerance check failed for '{block['name']}': {e}")

                if not is_valid:
                    # Calculate how far outside it is for debugging
                    try:
                        outside_part = block_geom.difference(outer_geom)
                        outside_area = outside_part.area if hasattr(outside_part, 'area') else 0
                        logger.error(
                            f"Block '{block['name']}' validation failed - "
                            f"Area outside: {outside_area:.10f} sq degrees, "
                            f"Block area: {block_geom.area:.10f} sq degrees"
                        )
                    except:
                        pass
                    errors.append(f"Block '{block['name']}' extends outside outer boundary")

            except Exception as e:
                errors.append(f"Error validating block {i+1}: {str(e)}")

        # Check for block overlaps
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                try:
                    geom1 = shape(blocks[i]["geometry"])
                    geom2 = shape(blocks[j]["geometry"])

                    if geom1.intersects(geom2):
                        intersection = geom1.intersection(geom2)
                        if intersection.area > 0.0001:  # Tolerance
                            errors.append(
                                f"Blocks '{blocks[i]['name']}' and '{blocks[j]['name']}' overlap"
                            )
                except Exception:
                    pass

        return {
            "valid": len(errors) == 0,
            "errors": errors if errors else None,
        }

    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Validation failed: {str(e)}"],
        }


def prepare_block_analysis_data(
    blocks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Prepare block data in the format expected by the analysis service

    Args:
        blocks: List of block definitions from map creation

    Returns:
        List of block data dicts ready for analysis
    """
    prepared_blocks = []

    for index, block in enumerate(blocks):
        try:
            geom = shape(block["geometry"])

            prepared_block = {
                "block_index": index,
                "block_name": block["name"],
                "block_id": block["id"],
                "area_hectares": block["area"],
                "geometry": block["geometry"],  # GeoJSON
                "centroid": {
                    "lon": geom.centroid.x,
                    "lat": geom.centroid.y,
                },
            }

            prepared_blocks.append(prepared_block)

        except Exception as e:
            raise ValueError(f"Failed to prepare block '{block['name']}': {str(e)}")

    return prepared_blocks
