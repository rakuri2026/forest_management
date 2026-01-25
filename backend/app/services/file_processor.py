"""
File processor for uploaded geospatial files
Handles Shapefile, KML, and GeoJSON formats (no GDAL required)
"""
import os
import tempfile
import zipfile
from typing import Tuple, Dict, Any, Optional
from pathlib import Path
import shapefile  # pyshp - no GDAL required
import geojson
from shapely.geometry import shape, mapping, Point, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union, transform
from pyproj import CRS, Transformer
from fastapi import UploadFile, HTTPException
import xml.etree.ElementTree as ET

from ..core.config import settings


async def process_uploaded_file(file: UploadFile) -> Tuple[str, Dict[str, Any]]:
    """
    Process uploaded geospatial file and extract geometry

    Args:
        file: Uploaded file (Shapefile, KML, GeoJSON, or GPKG)

    Returns:
        Tuple of (WKT geometry string in SRID 4326, metadata dict)

    Raises:
        ValueError: If file format is not supported or contains invalid geometry
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: {file_ext}. "
            f"Supported formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Create temporary directory for file processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / file.filename

        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Handle ZIP files (likely Shapefile)
        if file_ext == ".zip":
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find .shp file
            shp_files = list(Path(temp_dir).glob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found in ZIP archive")

            file_to_process = str(shp_files[0])
        else:
            file_to_process = str(temp_path)

        # Read file based on extension
        try:
            if file_ext == ".zip" or file_to_process.endswith(".shp"):
                # Read Shapefile
                geometries, attributes, crs = read_shapefile(file_to_process)
            elif file_ext == ".geojson" or file_ext == ".json":
                # Read GeoJSON
                geometries, attributes, crs = read_geojson(file_to_process)
            elif file_ext == ".kml":
                # Read KML
                geometries, attributes, crs = read_kml(file_to_process)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        except Exception as e:
            raise ValueError(f"Error reading file: {str(e)}")

        if not geometries:
            raise ValueError("File contains no features")

        # Process geometry based on type
        geometry, metadata = process_geometry_list(geometries, attributes)

        # Ensure geometry is in SRID 4326
        geometry_4326 = transform_to_4326(geometry, crs)

        # Convert to WKT for PostGIS
        wkt = geometry_4326.wkt

        return wkt, metadata


def read_shapefile(filepath: str) -> Tuple[list, list, CRS]:
    """Read shapefile and return geometries, attributes, and CRS"""
    sf = shapefile.Reader(filepath)

    geometries = []
    attributes = []

    for shapeRec in sf.shapeRecords():
        # Convert shapefile shape to shapely geometry
        geom = shape(shapeRec.shape.__geo_interface__)
        geometries.append(geom)

        # Get attributes
        attrs = {}
        for i, field in enumerate(sf.fields[1:]):  # Skip DeletionFlag
            attrs[field[0]] = shapeRec.record[i]
        attributes.append(attrs)

    # Get CRS from .prj file if exists
    prj_file = filepath.replace('.shp', '.prj')
    crs = None
    if os.path.exists(prj_file):
        with open(prj_file, 'r') as f:
            prj_text = f.read()
            try:
                crs = CRS.from_wkt(prj_text)
            except:
                crs = CRS.from_epsg(4326)  # Default to WGS84
    else:
        crs = CRS.from_epsg(4326)

    return geometries, attributes, crs


def read_geojson(filepath: str) -> Tuple[list, list, CRS]:
    """Read GeoJSON and return geometries, attributes, and CRS"""
    with open(filepath, 'r') as f:
        data = geojson.load(f)

    geometries = []
    attributes = []

    if data['type'] == 'FeatureCollection':
        features = data['features']
    elif data['type'] == 'Feature':
        features = [data]
    else:
        features = [{'geometry': data, 'properties': {}}]

    for feature in features:
        geom = shape(feature['geometry'])
        geometries.append(geom)
        attributes.append(feature.get('properties', {}))

    # GeoJSON uses WGS84 by default
    crs = CRS.from_epsg(4326)

    return geometries, attributes, crs


def read_kml(filepath: str) -> Tuple[list, list, CRS]:
    """Read KML and return geometries, attributes, and CRS"""
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Handle KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    geometries = []
    attributes = []

    # Find all Placemark elements
    for placemark in root.findall('.//kml:Placemark', ns):
        name = placemark.find('kml:name', ns)
        name_text = name.text if name is not None else "Unnamed"

        # Get coordinates from Point, LineString, or Polygon
        coords_elem = None
        geom_type = None

        for geom_tag in ['Point', 'LineString', 'Polygon']:
            elem = placemark.find(f'.//kml:{geom_tag}//kml:coordinates', ns)
            if elem is not None:
                coords_elem = elem
                geom_type = geom_tag
                break

        if coords_elem is not None:
            coords_text = coords_elem.text.strip()
            coords = []
            for coord_str in coords_text.split():
                parts = coord_str.split(',')
                if len(parts) >= 2:
                    coords.append((float(parts[0]), float(parts[1])))

            # Create shapely geometry
            if geom_type == 'Point' and coords:
                geom = Point(coords[0])
            elif geom_type == 'LineString' and len(coords) >= 2:
                geom = LineString(coords)
            elif geom_type == 'Polygon' and len(coords) >= 3:
                geom = Polygon(coords)
            else:
                continue

            geometries.append(geom)
            attributes.append({'name': name_text})

    # KML uses WGS84
    crs = CRS.from_epsg(4326)

    return geometries, attributes, crs


def process_geometry_list(geometries: list, attributes: list) -> Tuple[Any, Dict[str, Any]]:
    """
    Process geometry list based on type (Point, LineString, or Polygon)

    Processing logic per requirements:
    - Lines: Convert to polygons using "Feature to Polygon" operation
    - Points: Use for attribute assignment via Spatial Join (Point-in-Polygon) to label geometries
    - Polygons: Accept as-is. Support for multi-feature files (multiple blocks)

    Args:
        geometries: List of shapely geometry objects
        attributes: List of attribute dictionaries

    Returns:
        Tuple of (processed geometry or MultiPolygon, metadata dict)
    """
    metadata = {}

    if not geometries:
        raise ValueError("No geometries to process")

    # Separate geometries by type with their indices
    polygon_data = []  # (index, geom, attrs)
    line_data = []
    point_data = []

    for i, geom in enumerate(geometries):
        attrs = attributes[i] if i < len(attributes) else {}
        geom_type = geom.geom_type

        if "Polygon" in geom_type:
            polygon_data.append((i, geom, attrs))
        elif "LineString" in geom_type or "Line" in geom_type:
            line_data.append((i, geom, attrs))
        elif "Point" in geom_type:
            point_data.append((i, geom, attrs))

    # Build list of all polygon geometries
    all_polygons = []

    # 1. Add existing polygons
    for idx, geom, attrs in polygon_data:
        all_polygons.append(geom)

    # 2. Convert CLOSED lines to polygons
    closed_line_polygons = []
    division_lines = []

    if line_data:
        lines = [geom for idx, geom, attrs in line_data]

        # Separate closed lines (can be converted to polygons) from division lines
        for line in lines:
            coords = list(line.coords)
            if len(coords) >= 4 and coords[0] == coords[-1]:
                # Closed line - convert to polygon
                try:
                    poly = Polygon(coords)
                    if poly.is_valid and poly.area > 0:
                        closed_line_polygons.append(poly)
                except Exception:
                    pass
            else:
                # Open line - potential division line
                division_lines.append(line)

        # Add closed line polygons to polygon list
        all_polygons.extend(closed_line_polygons)

    # 3. Compartment Boundary Partitioning (if we have division lines)
    if division_lines and all_polygons:
        # Find the largest polygon (outer boundary)
        # Calculate areas using a projected CRS for accuracy
        largest_polygon = max(all_polygons, key=lambda p: p.area)

        # Filter division lines that intersect/are contained in the largest polygon
        relevant_lines = []
        for line in division_lines:
            if largest_polygon.contains(line) or largest_polygon.intersects(line):
                relevant_lines.append(line)

        if relevant_lines:
            # Partition the largest polygon using division lines
            partitioned_blocks = partition_polygon_with_lines(largest_polygon, relevant_lines)

            # Replace the largest polygon with partitioned blocks
            all_polygons.remove(largest_polygon)
            all_polygons.extend(partitioned_blocks)

            metadata['partitioned'] = True
            metadata['partition_info'] = {
                'division_lines_used': len(relevant_lines),
                'blocks_created': len(partitioned_blocks)
            }

    if not all_polygons:
        raise ValueError("No polygon geometries found or created from lines")

    # 3. Use points for spatial join labeling (if available)
    block_names = {}
    if point_data:
        # Perform point-in-polygon spatial join for naming
        block_names = perform_spatial_join_labeling(all_polygons, point_data)

    # 4. Create blocks list with metadata for each block
    blocks = []
    for idx, poly in enumerate(all_polygons):
        block_name = block_names.get(idx)
        if not block_name:
            # Try to get name from attributes if available
            if idx < len(polygon_data):
                attrs = polygon_data[idx][2]
                block_name = extract_name_from_attrs(attrs)
            if not block_name:
                block_name = f"Block {idx + 1}"

        # Calculate accurate area using UTM projection
        area_sqm, area_ha = calculate_polygon_area_utm(poly)

        blocks.append({
            'index': idx,
            'name': block_name,
            'geometry': poly,
            'area_sqm': area_sqm,
            'area_hectares': area_ha,
            'centroid': poly.centroid
        })

    # Store blocks info in metadata
    metadata['blocks'] = blocks
    metadata['block_count'] = len(blocks)

    # 5. Return merged geometry for database storage + blocks metadata
    if len(all_polygons) == 1:
        geometry = all_polygons[0]
    else:
        geometry = MultiPolygon(all_polygons)
        metadata['note'] = f"Multi-block file with {len(all_polygons)} blocks"

    return geometry, metadata


def process_points_list(geometries: list, attributes: list, metadata: Dict[str, Any]) -> Polygon:
    """
    Process point geometries
    Creates a small buffer around the first point for demonstration
    """
    # Get first point
    point = geometries[0]

    # Create 100m buffer (approximate, will be refined by projection)
    buffer_geometry = point.buffer(0.001)  # ~100m in degrees

    # Store point attributes in metadata
    if attributes and len(attributes) > 0:
        for key, value in attributes[0].items():
            if value is not None:
                metadata[key] = value

    return buffer_geometry


def partition_polygon_with_lines(polygon: Polygon, division_lines: list) -> list:
    """
    Partition a polygon using division lines (compartment boundary splitting)

    This implements the 'Feature to Polygon' operation using lines as dividers.

    Args:
        polygon: Outer boundary polygon to partition
        division_lines: List of LineString geometries to use as dividers

    Returns:
        List of Polygon geometries created by partitioning
    """
    from shapely.ops import split, unary_union, linemerge
    from shapely.geometry import MultiPolygon, GeometryCollection

    if not division_lines:
        return [polygon]

    # Start with the original polygon
    current_geoms = [polygon]

    # Extend lines to ensure they touch the boundary
    extended_lines = []
    for line in division_lines:
        # Check if line is within or intersects the polygon
        if polygon.contains(line) or polygon.intersects(line):
            # Extend line slightly to ensure it crosses the boundary
            coords = list(line.coords)
            if len(coords) >= 2:
                # Extend both ends slightly
                from shapely.geometry import LineString
                start = coords[0]
                end = coords[-1]

                # Calculate extension direction
                dx_start = coords[1][0] - coords[0][0]
                dy_start = coords[1][1] - coords[0][1]
                dx_end = coords[-1][0] - coords[-2][0]
                dy_end = coords[-1][1] - coords[-2][1]

                # Extend by small amount (0.0001 degrees ~ 10m)
                extend_dist = 0.0001
                new_start = (start[0] - dx_start * extend_dist, start[1] - dy_start * extend_dist)
                new_end = (end[0] + dx_end * extend_dist, end[1] + dy_end * extend_dist)

                extended_line = LineString([new_start] + coords + [new_end])
                extended_lines.append(extended_line)
        else:
            extended_lines.append(line)

    # Split polygon iteratively with each line
    for line in extended_lines:
        new_geoms = []
        for geom in current_geoms:
            try:
                # Attempt to split the geometry with the line
                result = split(geom, line)

                # Extract all polygon parts from the result
                if isinstance(result, GeometryCollection):
                    for part in result.geoms:
                        if isinstance(part, Polygon) and part.is_valid and part.area > 0:
                            new_geoms.append(part)
                        elif isinstance(part, MultiPolygon):
                            for poly in part.geoms:
                                if poly.is_valid and poly.area > 0:
                                    new_geoms.append(poly)
                elif isinstance(result, Polygon) and result.is_valid and result.area > 0:
                    new_geoms.append(result)
                elif isinstance(result, MultiPolygon):
                    for poly in result.geoms:
                        if poly.is_valid and poly.area > 0:
                            new_geoms.append(poly)
                else:
                    # Split didn't work, keep original
                    new_geoms.append(geom)
            except Exception:
                # If split fails, keep original geometry
                new_geoms.append(geom)

        # Update current geometries for next iteration
        if new_geoms:
            current_geoms = new_geoms

    return current_geoms if current_geoms else [polygon]


def convert_lines_to_polygons(lines: list) -> list:
    """
    Convert closed line geometries to polygons

    Only converts lines that form closed loops (first point == last point)

    Args:
        lines: List of LineString geometries

    Returns:
        List of Polygon geometries created from closed lines
    """
    from shapely.ops import polygonize

    if not lines:
        return []

    polygons = []
    for line in lines:
        coords = list(line.coords)
        # Check if line is closed (first point == last point)
        if len(coords) >= 4 and coords[0] == coords[-1]:
            try:
                poly = Polygon(coords)
                if poly.is_valid and poly.area > 0:
                    polygons.append(poly)
            except Exception:
                continue

    return polygons


def perform_spatial_join_labeling(polygons: list, point_data: list) -> dict:
    """
    Perform Point-in-Polygon spatial join to label polygons with point attributes

    Args:
        polygons: List of Polygon geometries
        point_data: List of tuples (index, Point geometry, attributes)

    Returns:
        Dict mapping polygon index to name from point within it
    """
    from shapely.geometry import Point

    block_names = {}

    for poly_idx, polygon in enumerate(polygons):
        # Find points within this polygon
        for pt_idx, point_geom, point_attrs in point_data:
            if polygon.contains(point_geom) or polygon.intersects(point_geom):
                # Extract name from point attributes
                name = None
                # Priority: 'name' field (case-insensitive)
                for key in point_attrs.keys():
                    if key.lower() == 'name':
                        name = str(point_attrs[key])
                        break

                # If no name field, use first string attribute
                if not name:
                    for key, value in point_attrs.items():
                        if value and isinstance(value, str):
                            name = str(value)
                            break

                if name:
                    block_names[poly_idx] = name
                    break  # Found label for this polygon

    return block_names


def process_lines_list(geometries: list, metadata: Dict[str, Any]) -> Polygon:
    """
    Process line geometries - convert to polygon using polygonize
    """
    from shapely.ops import polygonize

    # Merge all lines
    merged_lines = unary_union(geometries)

    # Try to create polygon from lines
    try:
        polygons = list(polygonize([merged_lines]))
        if polygons:
            # Use largest polygon if multiple
            geometry = max(polygons, key=lambda p: p.area)
        else:
            # If polygonize fails, create buffer around lines
            geometry = merged_lines.buffer(0.0001)
    except Exception:
        # Fallback: buffer around lines
        geometry = merged_lines.buffer(0.0001)

    return geometry


def process_polygons_list(geometries: list, metadata: Dict[str, Any]) -> Polygon:
    """
    Process polygon geometries - merge if multiple features
    """
    if len(geometries) == 1:
        # Single feature - return as-is
        geometry = geometries[0]
    else:
        # Multiple features - merge into single polygon
        geometry = unary_union(geometries)

    # Handle MultiPolygon - convert to single Polygon
    if isinstance(geometry, MultiPolygon):
        if len(geometry.geoms) == 1:
            # Single polygon in MultiPolygon - extract it
            geometry = list(geometry.geoms)[0]
        else:
            # Multiple polygons - use the largest one
            geometry = max(geometry.geoms, key=lambda p: p.area)
            metadata["note"] = f"Multiple polygons found, using largest ({len(geometry.geoms)} total)"

    return geometry


def extract_name_from_attrs(attrs: dict) -> Optional[str]:
    """
    Extract name from a single attribute dictionary

    Args:
        attrs: Dictionary of attributes

    Returns:
        Extracted name or None
    """
    if not attrs:
        return None

    # Try to find "name" attribute (case-insensitive)
    for key in attrs.keys():
        if key.lower() == "name":
            if attrs[key] is not None:
                return str(attrs[key])

    # Try first string attribute
    for key, value in attrs.items():
        if value is not None and isinstance(value, str) and value.strip():
            return str(value)

    return None


def extract_block_name_from_attrs(attributes: list, metadata: Dict[str, Any]) -> None:
    """
    Extract block name using priority order:
    1. Attribute explicitly named "Name" or "name"
    2. First detected string attribute
    3. Default name
    """
    if not attributes or len(attributes) == 0:
        metadata["name"] = "Block_0"
        return

    first_attrs = attributes[0]

    # Try to find "name" attribute (case-insensitive)
    for key in first_attrs.keys():
        if key.lower() == "name":
            if first_attrs[key] is not None:
                metadata["name"] = str(first_attrs[key])
                return

    # Try first string attribute
    for key, value in first_attrs.items():
        if value is not None and isinstance(value, str):
            metadata["name"] = str(value)
            return

    # Fallback to default
    metadata["name"] = "Block_0"


def transform_to_4326(geometry: Any, source_crs: Optional[CRS]) -> Any:
    """
    Transform geometry to SRID 4326 (WGS84)

    Args:
        geometry: Shapely geometry object
        source_crs: Source CRS

    Returns:
        Transformed geometry in EPSG:4326
    """
    if source_crs is None or source_crs.to_epsg() == 4326:
        return geometry

    # Create transformer
    transformer = Transformer.from_crs(
        source_crs,
        CRS.from_epsg(4326),
        always_xy=True
    )

    # Transform geometry
    from shapely.ops import transform
    return transform(transformer.transform, geometry)


def calculate_polygon_area_utm(polygon: Polygon) -> Tuple[float, float]:
    """
    Calculate accurate area of a polygon using UTM projection

    Args:
        polygon: Shapely Polygon in EPSG:4326 (WGS84)

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    # Get centroid to determine UTM zone
    centroid = polygon.centroid

    # Determine UTM zone for Nepal (32644 or 32645)
    # Nepal spans approximately 80°E to 88°E
    # Use 32644 (UTM Zone 44N) for longitude < 84°E
    # Use 32645 (UTM Zone 45N) for longitude >= 84°E
    utm_epsg = 32645 if centroid.x >= 84 else 32644

    # Create transformer from WGS84 to UTM
    transformer = Transformer.from_crs(
        CRS.from_epsg(4326),  # WGS84
        CRS.from_epsg(utm_epsg),  # UTM
        always_xy=True
    )

    # Transform polygon to UTM
    polygon_utm = transform(transformer.transform, polygon)

    # Calculate area in square meters
    area_sqm = polygon_utm.area
    area_hectares = area_sqm / 10000.0

    return area_sqm, area_hectares


def calculate_area_utm(geometry: Any, crs: Optional[CRS]) -> Tuple[float, float]:
    """
    Calculate accurate area in square meters using UTM projection

    Args:
        geometry: Shapely geometry in EPSG:4326
        crs: Source CRS

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    # Get centroid to determine UTM zone
    centroid = geometry.centroid

    # Determine UTM zone for Nepal (32644 or 32645)
    # Nepal spans approximately 80°E to 88°E
    # Use 32644 (UTM Zone 44N) for central Nepal
    # Use 32645 (UTM Zone 45N) for eastern Nepal
    utm_epsg = 32645 if centroid.x > 84 else 32644

    # Transform to UTM
    transformer = Transformer.from_crs(
        CRS.from_epsg(4326),
        CRS.from_epsg(utm_epsg),
        always_xy=True
    )

    from shapely.ops import transform
    geometry_utm = transform(transformer.transform, geometry)

    # Calculate area
    area_sqm = geometry_utm.area
    area_hectares = area_sqm / 10000.0

    return area_sqm, area_hectares


