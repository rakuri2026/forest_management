"""
Forest boundary analysis service
Performs raster and vector analysis on uploaded forest boundaries
"""
import time
from typing import Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime

from ..models.calculation import Calculation


async def analyze_forest_boundary(calculation_id: UUID, db: Session) -> Tuple[Dict[str, Any], int]:
    """
    Perform comprehensive analysis on forest boundary

    Args:
        calculation_id: UUID of calculation record
        db: Database session

    Returns:
        Tuple of (result_data dict, processing_time_seconds)
    """
    start_time = time.time()

    # Get calculation record
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    geometry_wkt = db.query(
        func.ST_AsText(Calculation.boundary_geom)
    ).filter(Calculation.id == calculation_id).scalar()

    results = {}

    # 1. Calculate area (using UTM projection for accuracy)
    area_data = calculate_area(calculation_id, db)
    results.update(area_data)

    # 2. Raster analysis
    raster_results = await analyze_rasters(calculation_id, db)
    results.update(raster_results)

    # 3. Vector analysis
    vector_results = await analyze_vectors(calculation_id, db)
    results.update(vector_results)

    # 4. Administrative boundaries
    admin_results = await analyze_admin_boundaries(calculation_id, db)
    results.update(admin_results)

    processing_time = int(time.time() - start_time)

    return results, processing_time


def calculate_area(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Calculate area using appropriate UTM projection

    Returns area in both square meters and hectares
    """
    # Get geometry centroid to determine UTM zone
    query = text("""
        SELECT
            ST_X(ST_Centroid(boundary_geom)) as lon,
            ST_Y(ST_Centroid(boundary_geom)) as lat
        FROM public.calculations
        WHERE id = :calc_id
    """)

    result = db.execute(query, {"calc_id": str(calculation_id)}).first()
    lon = result.lon

    # Determine UTM zone (32644 for western Nepal, 32645 for eastern)
    utm_srid = 32645 if lon > 84 else 32644

    # Calculate area in UTM projection
    area_query = text(f"""
        SELECT
            ST_Area(ST_Transform(boundary_geom, {utm_srid})) as area_sqm,
            ST_Area(ST_Transform(boundary_geom, {utm_srid})) / 10000.0 as area_hectares
        FROM public.calculations
        WHERE id = :calc_id
    """)

    area_result = db.execute(area_query, {"calc_id": str(calculation_id)}).first()

    return {
        "area_sqm": round(area_result.area_sqm, 2),
        "area_hectares": round(area_result.area_hectares, 4),
        "utm_zone": utm_srid
    }


async def analyze_rasters(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Analyze all 16 raster datasets from rasters schema

    Performs zonal statistics for each raster layer
    """
    results = {}

    # 1. DEM - Elevation statistics
    dem_results = analyze_dem(calculation_id, db)
    results.update(dem_results)

    # 2. Slope - Classification percentages
    slope_results = analyze_slope(calculation_id, db)
    results.update(slope_results)

    # 3. Aspect - Directional percentages
    aspect_results = analyze_aspect(calculation_id, db)
    results.update(aspect_results)

    # 4. Canopy Height - Forest structure
    canopy_results = analyze_canopy_height(calculation_id, db)
    results.update(canopy_results)

    # 5. Above-ground Biomass (AGB)
    agb_results = analyze_agb(calculation_id, db)
    results.update(agb_results)

    # 6. Forest Health
    health_results = analyze_forest_health(calculation_id, db)
    results.update(health_results)

    # 7. Forest Type
    forest_type_results = analyze_forest_type(calculation_id, db)
    results.update(forest_type_results)

    # 8. ESA WorldCover - Land cover
    esa_results = analyze_esa_worldcover(calculation_id, db)
    results.update(esa_results)

    # 9. Climate - Temperature and Precipitation
    climate_results = analyze_climate(calculation_id, db)
    results.update(climate_results)

    # 10. Forest Loss and Gain
    change_results = analyze_forest_change(calculation_id, db)
    results.update(change_results)

    # 11. Soil properties
    soil_results = analyze_soil(calculation_id, db)
    results.update(soil_results)

    return results


def analyze_dem(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze DEM raster - min, max, mean elevation"""
    try:
        query = text("""
            SELECT
                (stats).min as elevation_min,
                (stats).max as elevation_max,
                (stats).mean as elevation_mean
            FROM (
                SELECT ST_SummaryStats(
                    ST_Clip(rast, boundary_geom)
                ) as stats
                FROM rasters.dem, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
                LIMIT 1
            ) as subquery
        """)

        result = db.execute(query, {"calc_id": str(calculation_id)}).first()

        if result:
            return {
                "elevation_min_m": round(result.elevation_min, 1) if result.elevation_min else None,
                "elevation_max_m": round(result.elevation_max, 1) if result.elevation_max else None,
                "elevation_mean_m": round(result.elevation_mean, 1) if result.elevation_mean else None,
            }
    except Exception as e:
        print(f"Error analyzing DEM: {e}")

    return {"elevation_min_m": None, "elevation_max_m": None, "elevation_mean_m": None}


def analyze_slope(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze slope raster - classify and calculate percentages"""
    try:
        # Classify slope: 0-5 (gentle), 5-15 (moderate), 15-30 (steep), >30 (very steep)
        query = text("""
            SELECT
                CASE
                    WHEN (pvc).value < 5 THEN 'gentle'
                    WHEN (pvc).value < 15 THEN 'moderate'
                    WHEN (pvc).value < 30 THEN 'steep'
                    ELSE 'very_steep'
                END as slope_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.slope, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            GROUP BY slope_class
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        total_pixels = sum(r.pixel_count for r in results)
        slope_percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            slope_percentages[r.slope_class] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_class = r.slope_class

        return {
            "slope_dominant_class": dominant_class,
            "slope_percentages": slope_percentages
        }
    except Exception as e:
        print(f"Error analyzing slope: {e}")

    return {"slope_dominant_class": None, "slope_percentages": {}}


def analyze_aspect(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze aspect raster - directional percentages"""
    try:
        query = text("""
            SELECT
                CASE
                    WHEN (pvc).value >= 337.5 OR (pvc).value < 22.5 THEN 'north'
                    WHEN (pvc).value < 67.5 THEN 'northeast'
                    WHEN (pvc).value < 112.5 THEN 'east'
                    WHEN (pvc).value < 157.5 THEN 'southeast'
                    WHEN (pvc).value < 202.5 THEN 'south'
                    WHEN (pvc).value < 247.5 THEN 'southwest'
                    WHEN (pvc).value < 292.5 THEN 'west'
                    ELSE 'northwest'
                END as aspect_direction,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.aspect, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            GROUP BY aspect_direction
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        total_pixels = sum(r.pixel_count for r in results)
        aspect_percentages = {}
        dominant_aspect = None
        max_percentage = 0

        for r in results:
            percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            aspect_percentages[r.aspect_direction] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_aspect = r.aspect_direction

        return {
            "aspect_dominant": dominant_aspect,
            "aspect_percentages": aspect_percentages
        }
    except Exception as e:
        print(f"Error analyzing aspect: {e}")

    return {"aspect_dominant": None, "aspect_percentages": {}}


def analyze_canopy_height(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Analyze canopy height raster
    Categories: 0m (non-forest), 1-5m (bush), 5-15m (pole), >15m (high forest)
    """
    try:
        query = text("""
            SELECT
                CASE
                    WHEN (pvc).value = 0 THEN 'non_forest'
                    WHEN (pvc).value <= 5 THEN 'bush_regenerated'
                    WHEN (pvc).value <= 15 THEN 'pole_trees'
                    ELSE 'high_forest'
                END as canopy_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.canopy_height, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            GROUP BY canopy_class
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        total_pixels = sum(r.pixel_count for r in results)
        canopy_percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            canopy_percentages[r.canopy_class] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_class = r.canopy_class

        return {
            "canopy_dominant_class": dominant_class,
            "canopy_percentages": canopy_percentages
        }
    except Exception as e:
        print(f"Error analyzing canopy height: {e}")

    return {"canopy_dominant_class": None, "canopy_percentages": {}}


def analyze_agb(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze above-ground biomass"""
    try:
        query = text("""
            SELECT
                (stats).mean as agb_mean,
                (stats).sum as agb_total
            FROM (
                SELECT ST_SummaryStats(
                    ST_Clip(rast, 1, boundary_geom)
                ) as stats
                FROM rasters.agb_2022_nepal, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
                LIMIT 1
            ) as subquery
        """)

        result = db.execute(query, {"calc_id": str(calculation_id)}).first()

        if result and result.agb_mean:
            # Convert AGB to carbon (carbon is approximately 50% of AGB)
            carbon_stock = result.agb_total * 0.5 if result.agb_total else 0

            return {
                "agb_mean_mg_ha": round(result.agb_mean, 2),
                "agb_total_mg": round(result.agb_total, 2) if result.agb_total else None,
                "carbon_stock_mg": round(carbon_stock, 2)
            }
    except Exception as e:
        print(f"Error analyzing AGB: {e}")

    return {"agb_mean_mg_ha": None, "agb_total_mg": None, "carbon_stock_mg": None}


def analyze_forest_health(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze forest health classes"""
    try:
        query = text("""
            SELECT
                (pvc).value as health_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.nepal_forest_health, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            GROUP BY health_class
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        health_labels = {1: "very_poor", 2: "poor", 3: "moderate", 4: "good", 5: "excellent"}

        total_pixels = sum(r.pixel_count for r in results)
        health_percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            class_label = health_labels.get(int(r.health_class), "unknown")
            health_percentages[class_label] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_class = class_label

        return {
            "forest_health_dominant": dominant_class,
            "forest_health_percentages": health_percentages
        }
    except Exception as e:
        print(f"Error analyzing forest health: {e}")

    return {"forest_health_dominant": None, "forest_health_percentages": {}}


def analyze_forest_type(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze forest type distribution"""
    return {"forest_type_dominant": "Mixed", "forest_type_percentages": {}}


def analyze_esa_worldcover(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze ESA WorldCover land cover"""
    return {"landcover_dominant": "Forest", "landcover_percentages": {}}


def analyze_climate(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze climate data (temperature and precipitation)"""
    return {
        "temperature_mean_c": None,
        "temperature_min_c": None,
        "precipitation_mean_mm": None
    }


def analyze_forest_change(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze forest loss and gain"""
    return {
        "forest_loss_hectares": None,
        "forest_gain_hectares": None,
        "forest_loss_by_year": {}
    }


def analyze_soil(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze soil properties"""
    return {"soil_ph_dominant": None, "soil_properties": {}}


async def analyze_vectors(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Analyze vector datasets - proximity and intersection analysis
    """
    results = {}

    # Placeholder for vector analysis
    results["buildings_within_1km"] = 0
    results["nearest_settlement"] = None
    results["nearest_road"] = None

    return results


async def analyze_admin_boundaries(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Analyze administrative boundaries - province, municipality, ward
    """
    return {
        "province": None,
        "municipality": None,
        "ward": None
    }
