"""
Geometry utility functions for accurate area calculations
"""
from typing import Tuple
from shapely.geometry import shape, mapping
from shapely.ops import transform
from pyproj import CRS, Transformer
from sqlalchemy import text
from sqlalchemy.orm import Session


def calculate_utm_epsg(lon: float, lat: float) -> int:
    """
    Calculate the appropriate UTM EPSG code for given coordinates.

    Uses standard UTM zone calculation that works globally:
    - Zone number = floor((longitude + 180) / 6) + 1
    - Northern hemisphere: EPSG 326XX (where XX is zone number)
    - Southern hemisphere: EPSG 327XX (where XX is zone number)

    Args:
        lon: Longitude in decimal degrees (WGS84)
        lat: Latitude in decimal degrees (WGS84)

    Returns:
        EPSG code for the appropriate UTM zone

    Examples:
        >>> calculate_utm_epsg(85.3, 27.7)  # Kathmandu, Nepal
        32645  # UTM Zone 45N
        >>> calculate_utm_epsg(-122.4, 37.8)  # San Francisco, USA
        32610  # UTM Zone 10N
        >>> calculate_utm_epsg(151.2, -33.9)  # Sydney, Australia
        32756  # UTM Zone 56S
    """
    # Calculate UTM zone number (1-60)
    zone = int((lon + 180) / 6) + 1

    # Determine hemisphere and calculate EPSG code
    if lat >= 0:
        # Northern hemisphere: 32601-32660
        epsg = 32600 + zone
    else:
        # Southern hemisphere: 32701-32760
        epsg = 32700 + zone

    return epsg


def calculate_area_geodesic(geometry_geojson: dict) -> Tuple[float, float]:
    """
    Calculate accurate geodesic area of a geometry using UTM projection.

    Args:
        geometry_geojson: GeoJSON geometry dict (must be in EPSG:4326)

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    from shapely.geometry import shape

    # Convert GeoJSON to Shapely geometry
    geom = shape(geometry_geojson)

    return calculate_area_geodesic_from_shapely(geom)


def calculate_area_geodesic_from_shapely(geom) -> Tuple[float, float]:
    """
    Calculate accurate geodesic area of a Shapely geometry using UTM projection.

    Automatically selects the correct UTM zone based on the geometry's location.
    Works globally for any coordinates.

    Args:
        geom: Shapely geometry in EPSG:4326 (WGS84)

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    # Get centroid to determine appropriate UTM zone
    centroid = geom.centroid

    # Calculate the correct UTM EPSG code for this location
    utm_epsg = calculate_utm_epsg(centroid.x, centroid.y)

    # Create transformer from WGS84 to UTM
    transformer = Transformer.from_crs(
        CRS.from_epsg(4326),  # WGS84
        CRS.from_epsg(utm_epsg),  # Automatically calculated UTM zone
        always_xy=True
    )

    # Transform geometry to UTM
    geom_utm = transform(transformer.transform, geom)

    # Calculate area in square meters
    area_sqm = geom_utm.area
    area_hectares = area_sqm / 10000.0

    return area_sqm, area_hectares


def calculate_area_from_wkb_postgis(db: Session, geometry_wkb) -> Tuple[float, float]:
    """
    Calculate accurate geodesic area using PostGIS ST_Area(geography).

    This method uses PostGIS's built-in geodesic calculations which are
    highly accurate for WGS84 coordinates.

    Args:
        db: Database session
        geometry_wkb: WKB geometry from PostGIS (in EPSG:4326)

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    # Use PostGIS geography type for accurate geodesic area calculation
    result = db.execute(
        text("SELECT ST_Area(ST_GeogFromWKB(:geom_wkb)) as area_sqm"),
        {"geom_wkb": bytes(geometry_wkb.data)}
    ).fetchone()

    area_sqm = result.area_sqm if result else 0.0
    area_hectares = area_sqm / 10000.0

    return area_sqm, area_hectares


def calculate_polygon_area_from_geom_column(db: Session, table_name: str, id_value: str, id_column: str = "id", geom_column: str = "geometry") -> Tuple[float, float]:
    """
    Calculate area directly from a PostGIS geometry column using geography cast.

    Args:
        db: Database session
        table_name: Table name (with schema if needed)
        id_value: ID value to filter
        id_column: Name of ID column (default: "id")
        geom_column: Name of geometry column (default: "geometry")

    Returns:
        Tuple of (area_sqm, area_hectares)
    """
    query = text(f"""
        SELECT ST_Area(geography({geom_column})) as area_sqm
        FROM {table_name}
        WHERE {id_column} = :id_val
    """)

    result = db.execute(query, {"id_val": id_value}).fetchone()

    area_sqm = result.area_sqm if result else 0.0
    area_hectares = area_sqm / 10000.0

    return area_sqm, area_hectares
