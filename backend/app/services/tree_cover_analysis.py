"""
Tree cover analysis functions for accessible forest area calculation and sampling.

Uses ESA WorldCover raster data to identify tree-covered areas.
Calculates slope from DEM raster using PostGIS ST_Slope() function.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def calculate_accessible_forest_area(
    db: Session,
    geometry_wkt: str,
    filter_tree_cover: bool = True,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0
) -> dict:
    """
    Calculate accessible forest area with flexible filtering.

    Uses:
        - ESA WorldCover for tree cover (pixel value = 10)
        - DEM to calculate slope on-the-fly using ST_Slope()

    Args:
        db: Database session
        geometry_wkt: WKT string of boundary polygon
        filter_tree_cover: If True, only count tree cover pixels (ESA = 10)
        filter_slope: If True, exclude steep slopes
        max_slope_degrees: Maximum slope threshold if filtering (default 45°)

    Returns:
        Dictionary with:
            - total_boundary_area_ha: Total boundary area
            - accessible_forest_area_ha: Tree cover + slope OK (effective sampling area)
            - inaccessible_steep_forest_ha: Tree cover but too steep
            - non_forest_area_ha: Non-forested areas
            - Percentages and pixel counts
    """
    try:
        if filter_tree_cover and filter_slope:
            # Full filtering: tree cover (ESA = 10) + slope ≤ threshold (from DEM)
            logger.info(
                f"Calculating accessible forest area: "
                f"tree cover + slope ≤{max_slope_degrees}°"
            )

            query = text("""
                WITH boundary AS (
                    SELECT ST_GeomFromText(:wkt, 4326) as geom
                ),
                -- Step 1: Clip ESA WorldCover raster to boundary
                clipped_rasters AS (
                    SELECT ST_Clip(rast, b.geom, 0.0, true) as clipped_rast
                    FROM rasters.esa_world_cover, boundary b
                    WHERE ST_Intersects(rast, b.geom)
                ),
                -- Step 2: Get pixel values and counts
                esa_pixels AS (
                    SELECT value, count
                    FROM (
                        SELECT (ST_ValueCount(clipped_rast, 1, true)).*
                        FROM clipped_rasters
                        WHERE clipped_rast IS NOT NULL
                    ) vc
                    WHERE value > 0
                ),
                -- Step 3: Extract tree pixel coordinates from original raster
                tree_pixel_coords AS (
                    SELECT
                        ST_X(ST_Centroid(geom)) as lon,
                        ST_Y(ST_Centroid(geom)) as lat,
                        geom
                    FROM (
                        SELECT (ST_PixelAsPolygons(
                            ST_Clip(rast, b.geom, 0.0, true), 1
                        )).*
                        FROM rasters.esa_world_cover, boundary b
                        WHERE ST_Intersects(rast, b.geom)
                    ) pixels
                    WHERE val = 10 AND ST_Within(ST_Centroid(geom), (SELECT geom FROM boundary))
                ),
                -- Step 4: Calculate slope for tree pixels
                tree_with_slope AS (
                    SELECT
                        t.geom,
                        ST_Value(
                            ST_Slope(d.rast, 1, '32BF'),
                            ST_Centroid(t.geom)
                        ) as slope_degrees
                    FROM tree_pixel_coords t
                    CROSS JOIN LATERAL (
                        SELECT rast
                        FROM rasters.dem
                        WHERE ST_Intersects(rast, t.geom)
                        LIMIT 1
                    ) d
                )
                SELECT
                    -- Accessible forest (tree + slope OK)
                    COUNT(*) FILTER (WHERE slope_degrees IS NOT NULL AND slope_degrees <= :max_slope) as accessible_pixels,
                    -- Steep forest (tree + too steep)
                    COUNT(*) FILTER (WHERE slope_degrees IS NOT NULL AND slope_degrees > :max_slope) as steep_pixels,
                    -- Total tree pixels
                    COUNT(*) as total_tree_pixels,
                    -- Non-forest pixels
                    COALESCE((SELECT SUM(count) FROM esa_pixels WHERE value != 10), 0) as non_forest_pixels,

                    -- Convert to hectares (10m x 10m = 100 m²)
                    COUNT(*) FILTER (WHERE slope_degrees IS NOT NULL AND slope_degrees <= :max_slope) * 100.0 / 10000.0 as accessible_ha,
                    COUNT(*) FILTER (WHERE slope_degrees IS NOT NULL AND slope_degrees > :max_slope) * 100.0 / 10000.0 as steep_ha,
                    COUNT(*) * 100.0 / 10000.0 as tree_cover_ha,
                    COALESCE((SELECT SUM(count) FROM esa_pixels WHERE value != 10), 0) * 100.0 / 10000.0 as non_forest_ha
                FROM tree_with_slope
            """)

            result = db.execute(query, {
                "wkt": geometry_wkt,
                "max_slope": max_slope_degrees
            }).first()

            if not result:
                logger.warning("No data found for geometry")
                return {
                    "total_boundary_area_ha": 0.0,
                    "accessible_forest_area_ha": 0.0,
                    "inaccessible_steep_forest_ha": 0.0,
                    "non_forest_area_ha": 0.0
                }

            total_area_ha = (
                (result.accessible_ha or 0) +
                (result.steep_ha or 0) +
                (result.non_forest_ha or 0)
            )

            accessible_pct = (result.accessible_ha / total_area_ha * 100) if total_area_ha > 0 else 0.0
            steep_pct = (result.steep_ha / total_area_ha * 100) if total_area_ha > 0 else 0.0
            non_forest_pct = (result.non_forest_ha / total_area_ha * 100) if total_area_ha > 0 else 0.0
            tree_cover_pct = (result.tree_cover_ha / total_area_ha * 100) if total_area_ha > 0 else 0.0

            return {
                "total_boundary_area_ha": round(total_area_ha, 4),
                "accessible_forest_area_ha": round(result.accessible_ha or 0, 4),
                "accessible_forest_percentage": round(accessible_pct, 2),
                "inaccessible_steep_forest_ha": round(result.steep_ha or 0, 4),
                "inaccessible_steep_percentage": round(steep_pct, 2),
                "non_forest_area_ha": round(result.non_forest_ha or 0, 4),
                "non_forest_percentage": round(non_forest_pct, 2),
                "total_tree_cover_ha": round(result.tree_cover_ha or 0, 4),
                "tree_cover_percentage": round(tree_cover_pct, 2),
                "accessible_pixels": result.accessible_pixels or 0,
                "steep_pixels": result.steep_pixels or 0,
                "total_tree_pixels": result.total_tree_pixels or 0,
                "non_forest_pixels": result.non_forest_pixels or 0,
                "filter_tree_cover": True,
                "filter_slope": True,
                "max_slope_degrees": max_slope_degrees
            }

        elif filter_tree_cover and not filter_slope:
            # Tree cover only, no slope filtering
            logger.info("Calculating forest area: tree cover only (no slope filter)")

            query = text("""
                WITH boundary AS (
                    SELECT ST_GeomFromText(:wkt, 4326) as geom
                ),
                clipped_rasters AS (
                    SELECT ST_Clip(rast, b.geom, 0.0, true) as clipped_rast
                    FROM rasters.esa_world_cover, boundary b
                    WHERE ST_Intersects(rast, b.geom)
                ),
                pixel_counts AS (
                    SELECT (ST_ValueCount(clipped_rast, 1, true)).*
                    FROM clipped_rasters
                    WHERE clipped_rast IS NOT NULL
                )
                SELECT
                    SUM(count) FILTER (WHERE value = 10) as tree_pixels,
                    SUM(count) FILTER (WHERE value > 0 AND value != 10) as non_forest_pixels,
                    SUM(count) FILTER (WHERE value = 10) * 100.0 / 10000.0 as tree_ha,
                    SUM(count) FILTER (WHERE value > 0 AND value != 10) * 100.0 / 10000.0 as non_forest_ha
                FROM pixel_counts
            """)

            result = db.execute(query, {"wkt": geometry_wkt}).first()

            if not result:
                return {
                    "total_boundary_area_ha": 0.0,
                    "accessible_forest_area_ha": 0.0,
                    "non_forest_area_ha": 0.0
                }

            total_area_ha = (result.tree_ha or 0) + (result.non_forest_ha or 0)

            return {
                "total_boundary_area_ha": round(total_area_ha, 4),
                "accessible_forest_area_ha": round(result.tree_ha or 0, 4),
                "accessible_forest_percentage": round(
                    (result.tree_ha / total_area_ha * 100) if total_area_ha > 0 else 0, 2
                ),
                "non_forest_area_ha": round(result.non_forest_ha or 0, 4),
                "non_forest_percentage": round(
                    (result.non_forest_ha / total_area_ha * 100) if total_area_ha > 0 else 0, 2
                ),
                "total_tree_cover_ha": round(result.tree_ha or 0, 4),
                "tree_cover_percentage": round(
                    (result.tree_ha / total_area_ha * 100) if total_area_ha > 0 else 0, 2
                ),
                "accessible_pixels": result.tree_pixels or 0,
                "non_forest_pixels": result.non_forest_pixels or 0,
                "filter_tree_cover": True,
                "filter_slope": False
            }

        else:
            # No filtering - just return total boundary area
            logger.info("Calculating total boundary area (no filters)")

            query = text("""
                SELECT
                    ST_Area(ST_Transform(
                        ST_GeomFromText(:wkt, 4326),
                        CASE
                            WHEN ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) < 84.0 THEN 32644
                            ELSE 32645
                        END
                    )) / 10000.0 as area_ha
            """)

            result = db.execute(query, {"wkt": geometry_wkt}).first()

            total_area = result.area_ha if result else 0.0

            return {
                "total_boundary_area_ha": round(total_area, 4),
                "accessible_forest_area_ha": round(total_area, 4),
                "accessible_forest_percentage": 100.0,
                "filter_tree_cover": False,
                "filter_slope": False
            }

    except Exception as e:
        logger.error(f"Error calculating accessible forest area: {e}")
        return {
            "total_boundary_area_ha": 0.0,
            "accessible_forest_area_ha": 0.0,
            "inaccessible_steep_forest_ha": 0.0,
            "non_forest_area_ha": 0.0,
            "error": str(e)
        }


def extract_accessible_forest_mask(
    db: Session,
    geometry_wkt: str,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0,
    simplify_tolerance: float = 0.00001
) -> Optional[str]:
    """
    Extract accessible forest mask as polygon.

    Filters to tree cover (ESA = 10) first, then optionally filters by slope
    calculated from DEM using ST_Slope().

    Args:
        db: Database session
        geometry_wkt: WKT string of boundary polygon
        filter_slope: If True, exclude areas with slope > max_slope_degrees
        max_slope_degrees: Maximum slope threshold (default 45°)
        simplify_tolerance: Tolerance for polygon simplification (degrees, ~1m default)

    Returns:
        WKT of MultiPolygon/Polygon containing accessible forest areas, or None if no forest
    """
    try:
        if not filter_slope:
            # Simple case: just tree cover, no slope filtering
            logger.info("Extracting tree cover mask (no slope filter)...")

            query = text("""
                WITH tree_pixels AS (
                    SELECT (ST_DumpAsPolygons(
                        ST_Clip(rast, ST_GeomFromText(:wkt, 4326)), 1
                    )).*
                    FROM rasters.esa_world_cover
                    WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                )
                SELECT
                    ST_AsText(
                        ST_SimplifyPreserveTopology(
                            ST_Union(geom),
                            :tolerance
                        )
                    ) as forest_wkt,
                    COUNT(*) as pixel_count
                FROM tree_pixels
                WHERE val = 10  -- Tree cover only
            """)

            result = db.execute(query, {
                "wkt": geometry_wkt,
                "tolerance": simplify_tolerance
            }).first()

            if not result or not result.forest_wkt:
                logger.warning("No tree cover found in boundary")
                return None

            logger.info(f"Tree cover mask extracted: {result.pixel_count} pixels")
            return result.forest_wkt

        else:
            # With slope filter: tree cover + slope calculated from DEM
            logger.info(f"Extracting accessible forest mask (tree cover + slope ≤{max_slope_degrees}°)...")

            query = text("""
                WITH tree_pixels AS (
                    -- Extract ESA WorldCover pixels
                    SELECT (ST_DumpAsPolygons(
                        ST_Clip(rast, ST_GeomFromText(:wkt, 4326)), 1
                    )).*
                    FROM rasters.esa_world_cover
                    WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                ),
                tree_only AS (
                    -- FIRST: Filter to ONLY tree cover (value = 10)
                    SELECT geom
                    FROM tree_pixels
                    WHERE val = 10
                ),
                accessible_tree AS (
                    -- SECOND: Calculate slope from DEM and filter by threshold
                    SELECT t.geom
                    FROM tree_only t
                    CROSS JOIN LATERAL (
                        SELECT
                            ST_Value(
                                ST_Slope(rast, 1, '32BF'),  -- Calculate slope from DEM
                                ST_Centroid(t.geom)
                            ) as slope_degrees
                        FROM rasters.dem
                        WHERE ST_Intersects(rast, t.geom)
                        LIMIT 1
                    ) s
                    WHERE s.slope_degrees IS NOT NULL
                      AND s.slope_degrees <= :max_slope
                )
                SELECT
                    ST_AsText(
                        ST_SimplifyPreserveTopology(
                            ST_Union(geom),
                            :tolerance
                        )
                    ) as accessible_wkt,
                    COUNT(*) as pixel_count
                FROM accessible_tree
            """)

            result = db.execute(query, {
                "wkt": geometry_wkt,
                "max_slope": max_slope_degrees,
                "tolerance": simplify_tolerance
            }).first()

            if not result or not result.accessible_wkt:
                logger.warning(f"No accessible forest found (slope ≤{max_slope_degrees}°)")
                return None

            logger.info(
                f"Accessible forest mask extracted: {result.pixel_count} pixels "
                f"(tree cover + slope ≤{max_slope_degrees}°)"
            )

            return result.accessible_wkt

    except Exception as e:
        logger.error(f"Error extracting accessible forest mask: {e}")
        return None


def extract_tree_cover_pixel_centers(
    db: Session,
    geometry_wkt: str,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0,
    min_tree_cover_percent: float = 0.0
) -> list:
    """
    Extract tree cover pixel centers as candidate sample plot locations.

    NEW APPROACH: Instead of creating polygons, work directly with pixel centers.
    Each 10m x 10m tree cover pixel can be a potential sample plot location.

    Args:
        db: Database session
        geometry_wkt: WKT string of boundary polygon
        filter_slope: If True, exclude pixels with slope > max_slope_degrees
        max_slope_degrees: Maximum slope threshold (default 45°)
        min_tree_cover_percent: Minimum tree cover percentage (currently not used - ESA is binary)

    Returns:
        List of tuples: [(lon, lat, slope_degrees), ...]
    """
    try:
        if not filter_slope:
            # Simple: Just extract tree cover pixel centers
            logger.info("Extracting tree cover pixel centers (no slope filter)...")

            query = text("""
                WITH tree_pixels AS (
                    -- Extract all ESA WorldCover pixels within boundary
                    SELECT (ST_DumpAsPolygons(
                        ST_Clip(rast, ST_GeomFromText(:wkt, 4326)), 1
                    )).*
                    FROM rasters.esa_world_cover
                    WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                ),
                tree_centers AS (
                    -- Get pixel centers for tree cover only (value = 10)
                    SELECT
                        ST_X(ST_Centroid(geom)) as lon,
                        ST_Y(ST_Centroid(geom)) as lat
                    FROM tree_pixels
                    WHERE val = 10
                )
                SELECT lon, lat, NULL as slope_degrees
                FROM tree_centers
            """)

            results = db.execute(query, {"wkt": geometry_wkt}).fetchall()

            pixel_centers = [(row.lon, row.lat, row.slope_degrees) for row in results]
            logger.info(f"Extracted {len(pixel_centers)} tree cover pixel centers")
            return pixel_centers

        else:
            # With slope filter: tree cover + slope check
            logger.info(f"Extracting tree cover pixel centers (slope ≤{max_slope_degrees}°)...")

            query = text("""
                WITH tree_pixels AS (
                    -- Extract all ESA WorldCover pixels within boundary
                    SELECT (ST_DumpAsPolygons(
                        ST_Clip(rast, ST_GeomFromText(:wkt, 4326)), 1
                    )).*
                    FROM rasters.esa_world_cover
                    WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                ),
                tree_only AS (
                    -- Filter to tree cover only (value = 10)
                    SELECT geom, val
                    FROM tree_pixels
                    WHERE val = 10
                ),
                tree_with_slope AS (
                    -- Calculate slope for each tree pixel
                    SELECT
                        ST_X(ST_Centroid(t.geom)) as lon,
                        ST_Y(ST_Centroid(t.geom)) as lat,
                        ST_Value(
                            ST_Slope(d.rast, 1, '32BF'),
                            ST_Centroid(t.geom)
                        ) as slope_degrees
                    FROM tree_only t
                    CROSS JOIN LATERAL (
                        SELECT rast
                        FROM rasters.dem
                        WHERE ST_Intersects(rast, t.geom)
                        LIMIT 1
                    ) d
                )
                SELECT lon, lat, slope_degrees
                FROM tree_with_slope
                WHERE slope_degrees IS NOT NULL
                  AND slope_degrees <= :max_slope
            """)

            results = db.execute(query, {
                "wkt": geometry_wkt,
                "max_slope": max_slope_degrees
            }).fetchall()

            pixel_centers = [(row.lon, row.lat, row.slope_degrees) for row in results]
            logger.info(
                f"Extracted {len(pixel_centers)} accessible tree pixel centers "
                f"(slope ≤{max_slope_degrees}°)"
            )
            return pixel_centers

    except Exception as e:
        logger.error(f"Error extracting tree pixel centers: {e}")
        return []


def point_in_accessible_forest(
    db: Session,
    lon: float,
    lat: float,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0
) -> bool:
    """
    Check if a point is within accessible forest area.

    Args:
        db: Database session
        lon: Longitude
        lat: Latitude
        filter_slope: If True, also check slope from DEM
        max_slope_degrees: Maximum slope threshold

    Returns:
        True if point is in accessible forest, False otherwise
    """
    try:
        if not filter_slope:
            # Just check tree cover
            query = text("""
                SELECT ST_Value(rast, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) as landcover
                FROM rasters.esa_world_cover
                WHERE ST_Intersects(rast, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                LIMIT 1
            """)

            result = db.execute(query, {"lon": lon, "lat": lat}).first()
            return result and result.landcover == 10  # Tree cover

        else:
            # Check tree cover AND slope
            query = text("""
                WITH point_geom AS (
                    SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) as geom
                )
                SELECT
                    (SELECT ST_Value(rast, p.geom)
                     FROM rasters.esa_world_cover, point_geom p
                     WHERE ST_Intersects(rast, p.geom)
                     LIMIT 1) as landcover,
                    (SELECT ST_Value(ST_Slope(rast, 1, '32BF'), p.geom)
                     FROM rasters.dem, point_geom p
                     WHERE ST_Intersects(rast, p.geom)
                     LIMIT 1) as slope_degrees
            """)

            result = db.execute(query, {"lon": lon, "lat": lat}).first()

            if not result:
                return False

            is_tree_cover = result.landcover == 10
            slope_ok = result.slope_degrees is not None and result.slope_degrees <= max_slope_degrees

            return is_tree_cover and slope_ok

    except Exception as e:
        logger.error(f"Error checking point in accessible forest: {e}")
        return False
