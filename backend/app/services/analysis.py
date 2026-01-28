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
    Now analyzes each block separately and adds analysis results to each block

    Args:
        calculation_id: UUID of calculation record
        db: Database session

    Returns:
        Tuple of (result_data dict, processing_time_seconds)
    """
    # Per-block analysis enabled
    start_time = time.time()

    # Get calculation record
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise ValueError(f"Calculation {calculation_id} not found")

    results = {}

    # Get existing result_data with blocks
    existing_data = calculation.result_data or {}
    blocks = existing_data.get('blocks', [])

    # Analyze each block separately
    analyzed_blocks = []
    for block in blocks:
        block_analysis = await analyze_block_geometry(
            block['geometry'],
            calculation_id,
            db
        )
        # Merge analysis results into block data
        analyzed_block = {**block, **block_analysis}
        analyzed_blocks.append(analyzed_block)

    # Store analyzed blocks
    results['blocks'] = analyzed_blocks

    # Also calculate whole-area statistics for summary
    # 1. Calculate area (using UTM projection for accuracy)
    area_data = calculate_area(calculation_id, db)
    results.update(area_data)

    # 1b. Calculate whole forest extent (bounding box)
    extent_query = text("""
        SELECT
            ST_YMax(ST_Envelope(boundary_geom)) as north,
            ST_YMin(ST_Envelope(boundary_geom)) as south,
            ST_XMax(ST_Envelope(boundary_geom)) as east,
            ST_XMin(ST_Envelope(boundary_geom)) as west
        FROM calculations WHERE id = :calc_id
    """)
    whole_extent = db.execute(extent_query, {"calc_id": str(calculation_id)}).first()
    if whole_extent:
        results["whole_forest_extent"] = {
            "N": round(float(whole_extent.north), 7),
            "S": round(float(whole_extent.south), 7),
            "E": round(float(whole_extent.east), 7),
            "W": round(float(whole_extent.west), 7)
        }

    # 2. Raster analysis on whole boundary
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


async def analyze_block_geometry(geojson_geometry: Dict, calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """
    Analyze a single block's geometry

    Args:
        geojson_geometry: Block geometry in GeoJSON format
        calculation_id: UUID of parent calculation (for context)
        db: Database session

    Returns:
        Dict with analysis results for this block
    """
    import json

    # Convert GeoJSON to WKT for PostGIS
    geojson_str = json.dumps(geojson_geometry)

    # Create a temporary geometry from GeoJSON
    geom_query = text("""
        SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson)) as wkt
    """)
    wkt_result = db.execute(geom_query, {"geojson": geojson_str}).first()
    block_wkt = wkt_result.wkt

    block_results = {}

    # Calculate bounding box extent for this block
    extent_query = text("""
        SELECT
            ST_YMax(ST_Envelope(ST_GeomFromText(:wkt, 4326))) as north,
            ST_YMin(ST_Envelope(ST_GeomFromText(:wkt, 4326))) as south,
            ST_XMax(ST_Envelope(ST_GeomFromText(:wkt, 4326))) as east,
            ST_XMin(ST_Envelope(ST_GeomFromText(:wkt, 4326))) as west
    """)
    extent_result = db.execute(extent_query, {"wkt": block_wkt}).first()
    if extent_result:
        block_results["extent"] = {
            "N": round(float(extent_result.north), 7),
            "S": round(float(extent_result.south), 7),
            "E": round(float(extent_result.east), 7),
            "W": round(float(extent_result.west), 7)
        }

    # Run all raster analyses on this block's geometry
    # 1. DEM - Elevation
    dem_results = analyze_dem_geometry(block_wkt, db)
    block_results.update(dem_results)

    # 2. Slope
    slope_results = analyze_slope_geometry(block_wkt, db)
    block_results.update(slope_results)

    # 3. Aspect
    aspect_results = analyze_aspect_geometry(block_wkt, db)
    block_results.update(aspect_results)

    # 4. Canopy Height
    canopy_results = analyze_canopy_height_geometry(block_wkt, db)
    block_results.update(canopy_results)

    # 5. AGB (Biomass)
    agb_results = analyze_agb_geometry(block_wkt, db)
    block_results.update(agb_results)

    # 6. Forest Health
    health_results = analyze_forest_health_geometry(block_wkt, db)
    block_results.update(health_results)

    # 7. Forest Type
    forest_type_results = analyze_forest_type_geometry(block_wkt, db)
    block_results.update(forest_type_results)

    # 8. Land Cover (ESA WorldCover)
    landcover_results = analyze_landcover_geometry(block_wkt, db)
    block_results.update(landcover_results)

    # 9. Forest Loss
    loss_results = analyze_forest_loss_geometry(block_wkt, db)
    block_results.update(loss_results)

    # 10. Forest Gain
    gain_results = analyze_forest_gain_geometry(block_wkt, db)
    block_results.update(gain_results)

    # 11. Fire Loss
    fire_results = analyze_fire_loss_geometry(block_wkt, db)
    block_results.update(fire_results)

    # 12. Temperature
    temp_results = analyze_temperature_geometry(block_wkt, db)
    block_results.update(temp_results)

    # 13. Precipitation
    precip_results = analyze_precipitation_geometry(block_wkt, db)
    block_results.update(precip_results)

    # 14. Soil Texture
    soil_results = analyze_soil_geometry(block_wkt, db)
    block_results.update(soil_results)

    return block_results


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

    # 11. Soil properties (temporarily disabled - complex multi-band query)
    # soil_results = analyze_soil(calculation_id, db)
    # results.update(soil_results)
    results.update({"soil_texture": None, "soil_properties": {}})

    return results


def analyze_dem(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze DEM raster - min, max, mean elevation

    DEM NoData value is -32768 but not registered in PostGIS metadata.
    We must explicitly exclude it by filtering pixel values.
    """
    try:
        query = text("""
            WITH clipped_raster AS (
                SELECT ST_Clip(rast, boundary_geom) as rast
                FROM rasters.dem, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
                LIMIT 1
            ),
            pixel_values AS (
                SELECT (ST_PixelAsPolygons(rast)).val as elevation
                FROM clipped_raster
            )
            SELECT
                MIN(elevation) as elevation_min,
                MAX(elevation) as elevation_max,
                AVG(elevation) as elevation_mean
            FROM pixel_values
            WHERE elevation > -32000  -- Exclude NoData values (-32768)
              AND elevation >= 0       -- Nepal minimum elevation
              AND elevation <= 9000    -- Nepal maximum elevation
        """)

        result = db.execute(query, {"calc_id": str(calculation_id)}).first()

        if result and result.elevation_mean is not None:
            return {
                "elevation_min_m": round(result.elevation_min, 1) if result.elevation_min else None,
                "elevation_max_m": round(result.elevation_max, 1) if result.elevation_max else None,
                "elevation_mean_m": round(result.elevation_mean, 1) if result.elevation_mean else None,
            }
    except Exception as e:
        print(f"Error analyzing DEM: {e}")

    return {"elevation_min_m": None, "elevation_max_m": None, "elevation_mean_m": None}


def analyze_slope(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze slope raster - categorical codes (0-4)

    Slope classes from raster:
    0 = No data / Water (excluded from analysis)
    1 = <10° (Gentle/Flat)
    2 = 10-20° (Moderate)
    3 = 20-30° (Steep)
    4 = >30° (Very Steep)
    """
    try:
        # Mapping from raster categorical codes to class names
        slope_map = {
            1: "gentle",
            2: "moderate",
            3: "steep",
            4: "very_steep"
        }

        query = text("""
            SELECT
                (pvc).value as slope_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.slope, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL
              AND (pvc).value > 0
              AND (pvc).value <= 4
            GROUP BY slope_code
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"slope_dominant_class": None, "slope_percentages": {}}

        total_pixels = sum(r.pixel_count for r in results)
        slope_percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            code = int(r.slope_code)
            if code in slope_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                class_name = slope_map[code]
                slope_percentages[class_name] = round(percentage, 2)

                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_class = class_name

        return {
            "slope_dominant_class": dominant_class,
            "slope_percentages": slope_percentages
        }
    except Exception as e:
        print(f"Error analyzing slope: {e}")

    return {"slope_dominant_class": None, "slope_percentages": {}}


def analyze_aspect(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze aspect raster - categorical codes (0-8)

    Aspect classes from raster:
    0 = Flat (slope < 2°) - excluded from dominant calculation
    1 = N (337.5° - 22.5°)
    2 = NE (22.5° - 67.5°)
    3 = E (67.5° - 112.5°)
    4 = SE (112.5° - 157.5°)
    5 = S (157.5° - 202.5°)
    6 = SW (202.5° - 247.5°)
    7 = W (247.5° - 292.5°)
    8 = NW (292.5° - 337.5°)
    """
    try:
        # Mapping from raster categorical codes to direction names
        aspect_map = {
            0: "Flat",
            1: "N",
            2: "NE",
            3: "E",
            4: "SE",
            5: "S",
            6: "SW",
            7: "W",
            8: "NW"
        }

        query = text("""
            SELECT
                (pvc).value as aspect_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.aspect, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 0 AND 8
            GROUP BY aspect_code
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"aspect_dominant": None, "aspect_percentages": {}}

        total_pixels = sum(r.pixel_count for r in results)
        aspect_percentages = {}
        dominant_aspect = None
        max_percentage = 0

        for r in results:
            code = int(r.aspect_code)
            if code in aspect_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                direction = aspect_map[code]
                aspect_percentages[direction] = round(percentage, 2)

                # Exclude "Flat" from dominant calculation
                if code != 0 and percentage > max_percentage:
                    max_percentage = percentage
                    dominant_aspect = direction

        # If no non-flat aspects found, use Flat
        if dominant_aspect is None and "Flat" in aspect_percentages:
            dominant_aspect = "Flat"

        return {
            "aspect_dominant": dominant_aspect,
            "aspect_percentages": aspect_percentages
        }
    except Exception as e:
        print(f"Error analyzing aspect: {e}")

    return {"aspect_dominant": None, "aspect_percentages": {}}


def analyze_canopy_height(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze canopy height raster - actual height values in meters

    Canopy height raster contains height values 0-41m:
    0m = Non-forest (agricultural land, open areas, water, etc.)
    1-5m = Bush or shrub land
    6-15m = Pole sized forest
    >15m = High forest
    """
    try:
        query = text("""
            SELECT
                CASE
                    WHEN (pvc).value = 0 THEN 'non_forest'
                    WHEN (pvc).value > 0 AND (pvc).value <= 5 THEN 'bush_regenerated'
                    WHEN (pvc).value > 5 AND (pvc).value <= 15 THEN 'pole_trees'
                    WHEN (pvc).value > 15 THEN 'high_forest'
                END as canopy_class,
                SUM((pvc).count) as pixel_count,
                AVG((pvc).value) as avg_height
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.canopy_height, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL
              AND (pvc).value >= 0
              AND (pvc).value <= 50
            GROUP BY canopy_class
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"canopy_dominant_class": None, "canopy_percentages": {}, "canopy_mean_m": None}

        total_pixels = sum(r.pixel_count for r in results)
        canopy_percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            class_name = r.canopy_class
            percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
            canopy_percentages[class_name] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_class = class_name

        # Calculate weighted mean height (including all pixels)
        total_weighted_height = sum(r.avg_height * r.pixel_count for r in results)
        canopy_mean_m = round(total_weighted_height / total_pixels, 1) if total_pixels > 0 else None

        return {
            "canopy_dominant_class": dominant_class,
            "canopy_percentages": canopy_percentages,
            "canopy_mean_m": canopy_mean_m
        }
    except Exception as e:
        print(f"Error analyzing canopy height: {e}")

    return {"canopy_dominant_class": None, "canopy_percentages": {}, "canopy_mean_m": None}


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

        if result and result.agb_mean and result.agb_mean > 0:
            # Convert AGB to carbon (carbon is approximately 50% of AGB)
            carbon_stock = result.agb_total * 0.5 if result.agb_total and result.agb_total > 0 else 0

            return {
                "agb_mean_mg_ha": round(result.agb_mean, 2) if result.agb_mean > 0 else 0,
                "agb_total_mg": round(result.agb_total, 2) if result.agb_total and result.agb_total > 0 else 0,
                "carbon_stock_mg": round(carbon_stock, 2) if carbon_stock > 0 else 0
            }
    except Exception as e:
        print(f"Error analyzing AGB: {e}")

    return {"agb_mean_mg_ha": None, "agb_total_mg": None, "carbon_stock_mg": None}


def analyze_forest_health(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze forest health classes - categorical codes (1-5)

    Forest health classes (Sentinel-2 NDVI):
    1 = Stressed (NDVI < 0.2)
    2 = Poor (NDVI 0.2 - 0.4)
    3 = Moderate (NDVI 0.4 - 0.6)
    4 = Healthy (NDVI 0.6 - 0.8)
    5 = Excellent (NDVI > 0.8)
    """
    try:
        # Correct mapping from table comments
        health_labels = {
            1: "stressed",
            2: "poor",
            3: "moderate",
            4: "healthy",
            5: "excellent"
        }

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
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 5
            GROUP BY health_class
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"forest_health_dominant": None, "forest_health_percentages": {}}

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
    """Analyze forest type distribution - categorical codes (1-26)

    Forest type classes (FRTC, Kathmandu):
    1 = Shorea robusta Forest
    2 = Tropical Mixed Broadleaved Forest
    3 = Subtropical Mixed Broadleaved Forest
    ... (26 total classes)
    26 = Non forest
    """
    try:
        # Mapping from codes to forest type names
        forest_type_map = {
            1: "Shorea robusta",
            2: "Tropical Mixed Broadleaved",
            3: "Subtropical Mixed Broadleaved",
            4: "Shorea robusta-Mixed Broadleaved",
            5: "Abies Mixed",
            6: "Upper Temperate Coniferous",
            7: "Cool Temperate Mixed Broadleaved",
            8: "Castanopsis Lower Temperate Mixed Broadleaved",
            9: "Pinus roxburghii",
            10: "Alnus",
            11: "Schima",
            12: "Pinus roxburghii-Mixed Broadleaved",
            13: "Pinus wallichiana",
            14: "Warm Temperate Mixed Broadleaved",
            15: "Upper Temperate Quercus",
            16: "Rhododendron arboreum",
            17: "Temperate Rhododendron Mixed Broadleaved",
            18: "Dalbergia sissoo-Senegalia catechu",
            19: "Terminalia-Tropical Mixed Broadleaved",
            20: "Temperate Mixed Broadleaved",
            21: "Tropical Deciduous Indigenous Riverine",
            22: "Tropical Riverine",
            23: "Lower Temperate Mixed robusta",
            24: "Pinus roxburghii-Shorea robusta",
            25: "Lower Temperate Pinus roxburghii-Quercus",
            26: "Non forest"
        }

        query = text("""
            SELECT
                (pvc).value as forest_type_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.forest_type, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 26
            GROUP BY forest_type_code
            ORDER BY pixel_count DESC
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"forest_type_dominant": None, "forest_type_percentages": {}}

        total_pixels = sum(r.pixel_count for r in results)
        forest_type_percentages = {}
        dominant_type = None
        max_percentage = 0

        for r in results:
            code = int(r.forest_type_code)
            if code in forest_type_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                type_name = forest_type_map[code]
                forest_type_percentages[type_name] = round(percentage, 2)

                # Find dominant (excluding "Non forest" if possible)
                if code != 26 and percentage > max_percentage:
                    max_percentage = percentage
                    dominant_type = type_name
                elif code == 26 and dominant_type is None:
                    dominant_type = type_name

        return {
            "forest_type_dominant": dominant_type,
            "forest_type_percentages": forest_type_percentages
        }
    except Exception as e:
        print(f"Error analyzing forest type: {e}")

    return {"forest_type_dominant": None, "forest_type_percentages": {}}


def analyze_esa_worldcover(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze ESA WorldCover land cover - categorical codes

    Land cover classes (ESA/WorldCover/v200):
    10 = Tree cover
    20 = Shrubland
    30 = Grassland
    40 = Cropland
    50 = Built-up
    60 = Bare/sparse vegetation
    70 = Snow and ice
    80 = Permanent water bodies
    90 = Herbaceous wetland
    95 = Mangroves
    100 = Moss and lichen
    """
    try:
        # Mapping from codes to land cover names
        landcover_map = {
            10: "Tree cover",
            20: "Shrubland",
            30: "Grassland",
            40: "Cropland",
            50: "Built-up",
            60: "Bare/sparse vegetation",
            70: "Snow and ice",
            80: "Permanent water bodies",
            90: "Herbaceous wetland",
            95: "Mangroves",
            100: "Moss and lichen"
        }

        query = text("""
            SELECT
                (pvc).value as landcover_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.esa_world_cover, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL
            GROUP BY landcover_code
            ORDER BY pixel_count DESC
        """)

        results = db.execute(query, {"calc_id": str(calculation_id)}).fetchall()

        if not results:
            return {"landcover_dominant": None, "landcover_percentages": {}}

        total_pixels = sum(r.pixel_count for r in results)
        landcover_percentages = {}
        dominant_cover = None
        max_percentage = 0

        for r in results:
            code = int(r.landcover_code)
            if code in landcover_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                cover_name = landcover_map[code]
                landcover_percentages[cover_name] = round(percentage, 2)

                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_cover = cover_name

        return {
            "landcover_dominant": dominant_cover,
            "landcover_percentages": landcover_percentages
        }
    except Exception as e:
        print(f"Error analyzing ESA WorldCover: {e}")

    return {"landcover_dominant": None, "landcover_percentages": {}}


def analyze_climate(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze climate data (temperature and precipitation)

    WorldClim data:
    - annual_mean_temperature: Bio01, scale = 0.1, unit = deg C
    - min_temp_coldest_month: Bio06, scale = 0.1, unit = deg C
    - annual_precipitation: Bio12, unit = mm
    """
    try:
        # Temperature analysis (annual mean and min)
        temp_query = text("""
            SELECT
                (amt_stats).mean * 0.1 as temp_mean_c,
                (mint_stats).mean * 0.1 as temp_min_c
            FROM (
                SELECT
                    ST_SummaryStats(ST_Clip(amt.rast, calc.boundary_geom), 1, true) as amt_stats,
                    ST_SummaryStats(ST_Clip(mint.rast, calc.boundary_geom), 1, true) as mint_stats
                FROM rasters.annual_mean_temperature amt,
                     rasters.min_temp_coldest_month mint,
                     public.calculations calc
                WHERE calc.id = :calc_id
                  AND ST_Intersects(amt.rast, calc.boundary_geom)
                  AND ST_Intersects(mint.rast, calc.boundary_geom)
                LIMIT 1
            ) as subquery
        """)

        temp_result = db.execute(temp_query, {"calc_id": str(calculation_id)}).first()

        # Precipitation analysis
        precip_query = text("""
            SELECT
                (stats).mean as precip_mean_mm
            FROM (
                SELECT ST_SummaryStats(
                    ST_Clip(rast, boundary_geom),
                    1,
                    true
                ) as stats
                FROM rasters.annual_precipitation, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
                LIMIT 1
            ) as subquery
        """)

        precip_result = db.execute(precip_query, {"calc_id": str(calculation_id)}).first()

        # Filter out invalid values (None, NaN, Infinity)
        temp_mean = None
        temp_min = None
        precip_mean = None

        if temp_result and temp_result.temp_mean_c is not None:
            import math
            if not math.isinf(temp_result.temp_mean_c) and not math.isnan(temp_result.temp_mean_c):
                temp_mean = round(temp_result.temp_mean_c, 1)

        if temp_result and temp_result.temp_min_c is not None:
            import math
            if not math.isinf(temp_result.temp_min_c) and not math.isnan(temp_result.temp_min_c):
                temp_min = round(temp_result.temp_min_c, 1)

        if precip_result and precip_result.precip_mean_mm is not None:
            import math
            if not math.isinf(precip_result.precip_mean_mm) and not math.isnan(precip_result.precip_mean_mm):
                precip_mean = round(precip_result.precip_mean_mm, 1)

        return {
            "temperature_mean_c": temp_mean,
            "temperature_min_c": temp_min,
            "precipitation_mean_mm": precip_mean
        }
    except Exception as e:
        print(f"Error analyzing climate: {e}")

    return {
        "temperature_mean_c": None,
        "temperature_min_c": None,
        "precipitation_mean_mm": None
    }


def analyze_forest_change(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze forest loss and gain (Hansen Global Forest Change)

    nepal_lossyear: 0 = no loss, 1-24 = year of loss (2001-2024)
    nepal_gain: 0 = no gain, 1 = forest gain (2000-2012)
    forest_loss_fire: 0 = no fire loss, 1-24 = year of fire loss (2001-2024)
    """
    try:
        # Get area calculation for converting pixels to hectares
        area_query = text("""
            SELECT ST_Area(ST_Transform(boundary_geom, 32645)) / 10000.0 as area_hectares
            FROM public.calculations
            WHERE id = :calc_id
        """)
        area_result = db.execute(area_query, {"calc_id": str(calculation_id)}).first()
        total_area_ha = area_result.area_hectares if area_result else 0

        # Forest loss by year
        loss_query = text("""
            SELECT
                (pvc).value as loss_year_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.nepal_lossyear, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value > 0
            GROUP BY loss_year_code
            ORDER BY loss_year_code
        """)

        loss_results = db.execute(loss_query, {"calc_id": str(calculation_id)}).fetchall()

        # Forest gain
        gain_query = text("""
            SELECT
                SUM((pvc).count) as gain_pixels
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.nepal_gain, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value = 1
        """)

        gain_result = db.execute(gain_query, {"calc_id": str(calculation_id)}).first()

        # Forest loss from fire
        fire_query = text("""
            SELECT
                (pvc).value as fire_year_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
                FROM rasters.forest_loss_fire, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value > 0
            GROUP BY fire_year_code
        """)

        fire_results = db.execute(fire_query, {"calc_id": str(calculation_id)}).fetchall()

        # Calculate total pixels and percentages
        total_loss_pixels = sum(r.pixel_count for r in loss_results) if loss_results else 0
        gain_pixels = gain_result.gain_pixels if gain_result and gain_result.gain_pixels else 0
        total_fire_pixels = sum(r.pixel_count for r in fire_results) if fire_results else 0

        # Estimate hectares (30m pixel = 900 sqm = 0.09 ha)
        pixel_area_ha = 0.09
        loss_hectares = total_loss_pixels * pixel_area_ha
        gain_hectares = gain_pixels * pixel_area_ha
        fire_loss_hectares = total_fire_pixels * pixel_area_ha

        # Build year-by-year loss data
        forest_loss_by_year = {}
        for r in loss_results:
            year = 2000 + int(r.loss_year_code)
            forest_loss_by_year[str(year)] = round(r.pixel_count * pixel_area_ha, 2)

        # Build year-by-year fire loss data
        fire_loss_by_year = {}
        for r in fire_results:
            year = 2000 + int(r.fire_year_code)
            fire_loss_by_year[str(year)] = round(r.pixel_count * pixel_area_ha, 2)

        return {
            "forest_loss_hectares": round(loss_hectares, 2) if loss_hectares > 0 else 0,
            "forest_gain_hectares": round(gain_hectares, 2) if gain_hectares > 0 else 0,
            "fire_loss_hectares": round(fire_loss_hectares, 2) if fire_loss_hectares > 0 else 0,
            "forest_loss_by_year": forest_loss_by_year,
            "fire_loss_by_year": fire_loss_by_year
        }
    except Exception as e:
        print(f"Error analyzing forest change: {e}")

    return {
        "forest_loss_hectares": 0,
        "forest_gain_hectares": 0,
        "fire_loss_hectares": 0,
        "forest_loss_by_year": {},
        "fire_loss_by_year": {}
    }


def analyze_soil(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze soil properties (ISRIC SoilGrids)

    8 bands from soilgrids_isric:
    Band 1 = clay_g_kg (Clay content in g/kg)
    Band 2 = sand_g_kg (Sand content in g/kg)
    Band 3 = silt_g_kg (Silt content in g/kg)
    Band 4 = ph_h2o (Soil pH in H2O)
    Band 5 = soc_dg_kg (Soil organic carbon in dg/kg)
    Band 6 = nitrogen_cg_kg (Nitrogen content in cg/kg)
    Band 7 = bdod_cg_cm3 (Bulk density in cg/cm3)
    Band 8 = cec_mmol_kg (Cation exchange capacity in mmol/kg)
    """
    try:
        query = text("""
            SELECT
                (clay_stats).mean as clay_mean,
                (sand_stats).mean as sand_mean,
                (silt_stats).mean as silt_mean,
                (ph_stats).mean as ph_mean,
                (soc_stats).mean as soc_mean,
                (nitrogen_stats).mean as nitrogen_mean,
                (bdod_stats).mean as bdod_mean,
                (cec_stats).mean as cec_mean
            FROM (
                SELECT
                    ST_SummaryStats(ST_Clip(rast, 1, boundary_geom), 1, true) as clay_stats,
                    ST_SummaryStats(ST_Clip(rast, 2, boundary_geom), 1, true) as sand_stats,
                    ST_SummaryStats(ST_Clip(rast, 3, boundary_geom), 1, true) as silt_stats,
                    ST_SummaryStats(ST_Clip(rast, 4, boundary_geom), 1, true) as ph_stats,
                    ST_SummaryStats(ST_Clip(rast, 5, boundary_geom), 1, true) as soc_stats,
                    ST_SummaryStats(ST_Clip(rast, 6, boundary_geom), 1, true) as nitrogen_stats,
                    ST_SummaryStats(ST_Clip(rast, 7, boundary_geom), 1, true) as bdod_stats,
                    ST_SummaryStats(ST_Clip(rast, 8, boundary_geom), 1, true) as cec_stats
                FROM rasters.soilgrids_isric, public.calculations
                WHERE calculations.id = :calc_id
                  AND ST_Intersects(rast, boundary_geom)
                LIMIT 1
            ) as subquery
        """)

        result = db.execute(query, {"calc_id": str(calculation_id)}).first()

        if result:
            # Determine soil texture class based on clay/sand/silt percentages
            clay_pct = result.clay_mean / 10 if result.clay_mean else 0  # g/kg to %
            sand_pct = result.sand_mean / 10 if result.sand_mean else 0
            silt_pct = result.silt_mean / 10 if result.silt_mean else 0

            # Simple texture classification
            soil_texture = "Unknown"
            if clay_pct > 40:
                soil_texture = "Clay"
            elif sand_pct > 50:
                soil_texture = "Sandy"
            elif silt_pct > 40:
                soil_texture = "Silty"
            else:
                soil_texture = "Loam"

            return {
                "soil_texture": soil_texture,
                "soil_properties": {
                    "clay_g_kg": round(result.clay_mean, 1) if result.clay_mean else None,
                    "sand_g_kg": round(result.sand_mean, 1) if result.sand_mean else None,
                    "silt_g_kg": round(result.silt_mean, 1) if result.silt_mean else None,
                    "ph_h2o": round(result.ph_mean, 2) if result.ph_mean else None,
                    "soc_dg_kg": round(result.soc_mean, 1) if result.soc_mean else None,
                    "nitrogen_cg_kg": round(result.nitrogen_mean, 1) if result.nitrogen_mean else None,
                    "bulk_density_cg_cm3": round(result.bdod_mean, 1) if result.bdod_mean else None,
                    "cec_mmol_kg": round(result.cec_mean, 1) if result.cec_mean else None
                }
            }
    except Exception as e:
        print(f"Error analyzing soil: {e}")

    return {"soil_texture": None, "soil_properties": {}}


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


# ============================================================================
# GEOMETRY-BASED ANALYSIS FUNCTIONS (for individual blocks)
# ============================================================================

def analyze_dem_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze DEM raster for a specific geometry (WKT)

    DEM contains 16-bit signed integer values in meters.
    NoData value is -32768 but PostGIS doesn't know this (NoData=NULL in raster metadata).
    We must explicitly exclude -32768 values by filtering in the query.
    """
    try:
        # Use ST_PixelAsPolygons to get all pixel values, then filter and aggregate
        query = text("""
            WITH clipped_raster AS (
                SELECT ST_Clip(rast, ST_GeomFromText(:wkt, 4326)) as rast
                FROM rasters.dem
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                LIMIT 1
            ),
            pixel_values AS (
                SELECT (ST_PixelAsPolygons(rast)).val as elevation
                FROM clipped_raster
            )
            SELECT
                MIN(elevation) as elevation_min,
                MAX(elevation) as elevation_max,
                AVG(elevation) as elevation_mean
            FROM pixel_values
            WHERE elevation > -32000  -- Exclude NoData values (-32768)
              AND elevation >= 0       -- Nepal minimum elevation
              AND elevation <= 9000    -- Nepal maximum elevation
        """)

        result = db.execute(query, {"wkt": wkt}).first()

        if result and result.elevation_mean is not None:
            return {
                "elevation_min_m": round(result.elevation_min, 1) if result.elevation_min else None,
                "elevation_max_m": round(result.elevation_max, 1) if result.elevation_max else None,
                "elevation_mean_m": round(result.elevation_mean, 1) if result.elevation_mean else None
            }
    except Exception as e:
        print(f"Error analyzing DEM: {e}")

    return {"elevation_min_m": None, "elevation_max_m": None, "elevation_mean_m": None}


def analyze_slope_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze slope for a specific geometry

    Slope raster contains categorical codes (8-bit unsigned):
    0 = No data / Water (excluded)
    1 = Gentle (<10°)
    2 = Moderate (10-20°)
    3 = Steep (20-30°)
    4 = Very Steep (>30°)
    """
    try:
        # Mapping from raster values to class names (excluding 0)
        slope_map = {
            1: "gentle",
            2: "moderate",
            3: "steep",
            4: "very_steep"
        }

        query = text("""
            SELECT
                (pvc).value as slope_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.slope
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL
              AND (pvc).value > 0
              AND (pvc).value <= 4
            GROUP BY slope_code
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            total_pixels = sum(r.pixel_count for r in results)
            percentages = {}
            for r in results:
                code = int(r.slope_code)
                if code in slope_map:
                    percentages[slope_map[code]] = round((r.pixel_count / total_pixels) * 100, 2)

            if percentages:
                dominant = max(percentages.items(), key=lambda x: x[1])[0]
                return {
                    "slope_dominant_class": dominant,
                    "slope_percentages": percentages
                }
    except Exception as e:
        print(f"Error analyzing slope: {e}")

    return {"slope_dominant_class": None, "slope_percentages": {}}


def analyze_aspect_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze aspect for a specific geometry

    Aspect raster contains categorical codes (8-bit unsigned):
    0 = Flat (excluded from dominant), 1 = N, 2 = NE, 3 = E, 4 = SE, 5 = S, 6 = SW, 7 = W, 8 = NW
    """
    try:
        # Mapping from raster values to direction names
        aspect_map = {
            0: "Flat",
            1: "N",
            2: "NE",
            3: "E",
            4: "SE",
            5: "S",
            6: "SW",
            7: "W",
            8: "NW"
        }

        query = text("""
            SELECT
                (pvc).value as aspect_code,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.aspect
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 0 AND 8
            GROUP BY aspect_code
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            total_pixels = sum(r.pixel_count for r in results)
            percentages = {}
            for r in results:
                code = int(r.aspect_code)
                if code in aspect_map:
                    percentages[aspect_map[code]] = round((r.pixel_count / total_pixels) * 100, 2)

            if percentages:
                # Find dominant (excluding Flat if possible)
                non_flat = {k: v for k, v in percentages.items() if k != "Flat"}
                dominant = max(non_flat.items(), key=lambda x: x[1])[0] if non_flat else "Flat"

                return {
                    "aspect_dominant": dominant,
                    "aspect_percentages": percentages
                }
    except Exception as e:
        print(f"Error analyzing aspect: {e}")

    return {"aspect_dominant": None, "aspect_percentages": {}}


def analyze_canopy_height_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze canopy height for a specific geometry

    Canopy height raster contains actual height values in meters (0-41m):
    0m = Non-forest (agricultural land, open areas, water, etc.)
    1-5m = Bush or shrub land
    6-15m = Pole sized forest
    >15m = High forest (tree sized)

    Uses conservative pixel containment: only pixels whose center point
    is FULLY CONTAINED within the polygon boundary are counted.
    This matches QGIS zonal statistics behavior more closely.
    """
    try:
        # Use ST_PixelAsPolygons with geom parameter to get pixel center points
        # Filter to only include pixels where center is CONTAINED (not just intersects)
        query = text("""
            WITH boundary AS (
                SELECT ST_GeomFromText(:wkt, 4326) as geom
            ),
            all_pixels AS (
                SELECT
                    (pix).val as height,
                    (pix).geom as pixel_center
                FROM (
                    SELECT ST_PixelAsPolygons(rast) as pix
                    FROM rasters.canopy_height, boundary
                    WHERE ST_Intersects(rast, geom)
                ) as subq
            )
            SELECT
                CASE
                    WHEN height = 0 THEN 'non_forest'
                    WHEN height > 0 AND height <= 5 THEN 'bush_regenerated'
                    WHEN height > 5 AND height <= 15 THEN 'pole_trees'
                    WHEN height > 15 THEN 'high_forest'
                END as canopy_class,
                COUNT(*) as pixel_count,
                AVG(height) as avg_height
            FROM all_pixels, boundary
            WHERE ST_Contains(boundary.geom, ST_Centroid(pixel_center))
              AND height IS NOT NULL
              AND height >= 0
              AND height <= 50
            GROUP BY canopy_class
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            total_pixels = sum(r.pixel_count for r in results)
            percentages = {r.canopy_class: round((r.pixel_count / total_pixels) * 100, 2) for r in results}
            dominant = max(percentages.items(), key=lambda x: x[1])[0]

            # Calculate weighted mean height (including all pixels)
            total_weighted_height = sum(r.avg_height * r.pixel_count for r in results)
            canopy_mean_m = round(total_weighted_height / total_pixels, 1) if total_pixels > 0 else None

            return {
                "canopy_mean_m": canopy_mean_m,
                "canopy_dominant_class": dominant,
                "canopy_percentages": percentages
            }
    except Exception as e:
        print(f"Error analyzing canopy height: {e}")

    return {"canopy_mean_m": None, "canopy_dominant_class": None, "canopy_percentages": {}}


def analyze_agb_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze above-ground biomass for a specific geometry

    AGB raster (16-bit unsigned) has 2 bands:
    Band 1 = AGB estimate in Mg/ha, Band 2 = standard deviation
    """
    try:
        query = text("""
            SELECT
                (stats).mean as agb_mean,
                (stats).sum as agb_total
            FROM (
                SELECT ST_SummaryStats(
                    ST_Clip(rast, 1, ST_GeomFromText(:wkt, 4326)),
                    1,  -- band 1
                    true  -- exclude nodata
                ) as stats
                FROM rasters.agb_2022_nepal
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                LIMIT 1
            ) as subquery
        """)

        result = db.execute(query, {"wkt": wkt}).first()

        if result and result.agb_total:
            return {
                "agb_mean_mg_ha": round(result.agb_mean, 2) if result.agb_mean else None,
                "agb_total_mg": round(result.agb_total, 2) if result.agb_total else None,
                "carbon_stock_mg": round(result.agb_total * 0.5, 2) if result.agb_total else None
            }
    except Exception as e:
        print(f"Error analyzing AGB: {e}")

    return {"agb_mean_mg_ha": None, "agb_total_mg": None, "carbon_stock_mg": None}


def analyze_forest_health_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze forest health for a specific geometry

    Forest health classes (8-bit unsigned):
    1=Stressed, 2=Poor, 3=Moderate, 4=Healthy, 5=Excellent
    """
    try:
        # Correct mapping according to table comment
        health_map = {
            1: "stressed",
            2: "poor",
            3: "moderate",
            4: "healthy",
            5: "excellent"
        }

        query = text("""
            SELECT
                (pvc).value as health_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.nepal_forest_health
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 5
            GROUP BY health_class
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            total_pixels = sum(r.pixel_count for r in results)
            percentages = {}
            for r in results:
                class_val = int(r.health_class)
                if class_val in health_map:
                    percentages[health_map[class_val]] = round((r.pixel_count / total_pixels) * 100, 2)

            if percentages:
                dominant = max(percentages.items(), key=lambda x: x[1])[0]
                return {
                    "forest_health_dominant": dominant,
                    "forest_health_percentages": percentages
                }
    except Exception as e:
        print(f"Error analyzing forest health: {e}")

    return {"forest_health_dominant": None, "forest_health_percentages": {}}


def analyze_forest_type_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze forest type for a specific geometry (WKT)"""
    try:
        forest_type_map = {
            1: "Shorea robusta", 2: "Alnus nepalensis", 3: "Schima-Castanopsis",
            4: "Quercus semecarpifolia", 5: "Larix/Abies spectabilis",
            6: "Pinus wallichiana-Tsuga dumosa", 7: "Plantation (Pinus-Eucalyptus)",
            8: "Ficus-Other Tropical Riverine", 9: "Tropical Mixed Broadleaved",
            10: "Quercus-Pinus", 11: "Abies spectabilis",
            12: "Pinus roxburghii-Mixed Broadleaved", 13: "Pinus wallichiana",
            14: "Warm Temperate Mixed Broadleaved", 15: "Upper Temperate Quercus",
            16: "Rhododendron arboreum", 17: "Temperate Rhododendron Mixed Broadleaved",
            18: "Dalbergia sissoo-Senegalia catechu", 19: "Terminalia-Tropical Mixed Broadleaved",
            20: "Temperate Mixed Broadleaved", 21: "Tropical Deciduous Indigenous Riverine",
            22: "Tropical Riverine", 23: "Lower Temperate Mixed robusta",
            24: "Pinus roxburghii-Shorea robusta", 25: "Lower Temperate Pinus roxburghii-Quercus",
            26: "Non forest"
        }
        query = text("""
            SELECT (pvc).value as forest_type_code, SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.forest_type WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 26
            GROUP BY forest_type_code ORDER BY pixel_count DESC
        """)
        results = db.execute(query, {"wkt": wkt}).fetchall()
        if not results:
            return {"forest_type_dominant": None, "forest_type_percentages": {}}
        total_pixels = sum(r.pixel_count for r in results)
        forest_type_percentages = {}
        dominant_type = None
        max_percentage = 0
        for r in results:
            code = int(r.forest_type_code)
            if code in forest_type_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                type_name = forest_type_map[code]
                forest_type_percentages[type_name] = round(percentage, 2)
                if code != 26 and percentage > max_percentage:
                    max_percentage = percentage
                    dominant_type = type_name
                elif code == 26 and dominant_type is None:
                    dominant_type = type_name
        return {"forest_type_dominant": dominant_type, "forest_type_percentages": forest_type_percentages}
    except Exception as e:
        print(f"Error analyzing forest type for geometry: {e}")
    return {"forest_type_dominant": None, "forest_type_percentages": {}}


def analyze_landcover_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze ESA WorldCover land cover for a specific geometry (WKT)"""
    try:
        landcover_map = {
            10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
            50: "Built-up", 60: "Bare/sparse vegetation", 70: "Snow and ice",
            80: "Permanent water bodies", 90: "Herbaceous wetland", 95: "Mangroves",
            100: "Moss and lichen"
        }
        query = text("""
            SELECT (pvc).value as landcover_code, SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.esa_world_cover WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL
            GROUP BY landcover_code ORDER BY pixel_count DESC
        """)
        results = db.execute(query, {"wkt": wkt}).fetchall()
        if not results:
            return {"landcover_dominant": None, "landcover_percentages": {}}
        total_pixels = sum(r.pixel_count for r in results)
        landcover_percentages = {}
        dominant_cover = None
        max_percentage = 0
        for r in results:
            code = int(r.landcover_code)
            if code in landcover_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                cover_name = landcover_map[code]
                landcover_percentages[cover_name] = round(percentage, 2)
                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_cover = cover_name
        return {"landcover_dominant": dominant_cover, "landcover_percentages": landcover_percentages}
    except Exception as e:
        print(f"Error analyzing land cover for geometry: {e}")
    return {"landcover_dominant": None, "landcover_percentages": {}}


def analyze_forest_loss_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze Hansen forest loss (2001-2023) for a specific geometry"""
    try:
        query = text("""
            SELECT (pvc).value as loss_year, SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.nepal_lossyear WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 23
            GROUP BY loss_year ORDER BY loss_year
        """)
        results = db.execute(query, {"wkt": wkt}).fetchall()
        if not results:
            return {"forest_loss_hectares": 0, "forest_loss_by_year": {}}
        pixel_area_ha = 0.0009
        loss_by_year = {}
        total_loss_pixels = 0
        for r in results:
            year_code = int(r.loss_year)
            actual_year = 2000 + year_code
            loss_ha = r.pixel_count * pixel_area_ha
            loss_by_year[str(actual_year)] = round(loss_ha, 4)
            total_loss_pixels += r.pixel_count
        total_loss_ha = total_loss_pixels * pixel_area_ha
        return {"forest_loss_hectares": round(total_loss_ha, 4), "forest_loss_by_year": loss_by_year}
    except Exception as e:
        print(f"Error analyzing forest loss for geometry: {e}")
    return {"forest_loss_hectares": None, "forest_loss_by_year": {}}


def analyze_forest_gain_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze Hansen forest gain (2000-2012) for a specific geometry"""
    try:
        query = text("""
            SELECT SUM((pvc).count) as gain_pixels
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.nepal_gain WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value = 1
        """)
        result = db.execute(query, {"wkt": wkt}).first()
        if result and result.gain_pixels:
            pixel_area_ha = 0.0009
            gain_ha = result.gain_pixels * pixel_area_ha
            return {"forest_gain_hectares": round(gain_ha, 4)}
    except Exception as e:
        print(f"Error analyzing forest gain for geometry: {e}")
    return {"forest_gain_hectares": None}


def analyze_fire_loss_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze fire-related forest loss for a specific geometry"""
    try:
        query = text("""
            SELECT (pvc).value as fire_year, SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.forest_loss_fire WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 23
            GROUP BY fire_year ORDER BY fire_year
        """)
        results = db.execute(query, {"wkt": wkt}).fetchall()
        if not results:
            return {"fire_loss_hectares": 0, "fire_loss_by_year": {}}
        pixel_area_ha = 0.0009
        fire_by_year = {}
        total_fire_pixels = 0
        for r in results:
            year_code = int(r.fire_year)
            actual_year = 2000 + year_code
            fire_ha = r.pixel_count * pixel_area_ha
            fire_by_year[str(actual_year)] = round(fire_ha, 4)
            total_fire_pixels += r.pixel_count
        total_fire_ha = total_fire_pixels * pixel_area_ha
        return {"fire_loss_hectares": round(total_fire_ha, 4), "fire_loss_by_year": fire_by_year}
    except Exception as e:
        print(f"Error analyzing fire loss for geometry: {e}")
    return {"fire_loss_hectares": None, "fire_loss_by_year": {}}


def analyze_temperature_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze temperature data for a specific geometry"""
    try:
        query = text("""
            WITH clipped AS (
                SELECT ST_Clip(rast, ST_GeomFromText(:wkt, 4326)) as rast
                FROM rasters.annual_mean_temperature WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                LIMIT 1
            ), pixel_values AS (
                SELECT (ST_PixelAsPolygons(rast)).val as temp FROM clipped
            )
            SELECT AVG(temp) as temp_mean FROM pixel_values WHERE temp IS NOT NULL AND temp > -100 AND temp < 100
        """)
        result = db.execute(query, {"wkt": wkt}).first()
        temp_mean = None
        if result and result.temp_mean is not None:
            temp_mean = round(result.temp_mean, 2)

        query_min = text("""
            WITH clipped AS (
                SELECT ST_Clip(rast, ST_GeomFromText(:wkt, 4326)) as rast
                FROM rasters.min_temp_coldest_month WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                LIMIT 1
            ), pixel_values AS (
                SELECT (ST_PixelAsPolygons(rast)).val as temp FROM clipped
            )
            SELECT AVG(temp) as temp_min FROM pixel_values WHERE temp IS NOT NULL AND temp > -100 AND temp < 100
        """)
        result_min = db.execute(query_min, {"wkt": wkt}).first()
        temp_min = None
        if result_min and result_min.temp_min is not None:
            temp_min = round(result_min.temp_min, 2)

        return {"temperature_mean_c": temp_mean, "temperature_min_c": temp_min}
    except Exception as e:
        print(f"Error analyzing temperature for geometry: {e}")
    return {"temperature_mean_c": None, "temperature_min_c": None}


def analyze_precipitation_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze precipitation data for a specific geometry"""
    try:
        query = text("""
            WITH clipped AS (
                SELECT ST_Clip(rast, ST_GeomFromText(:wkt, 4326)) as rast
                FROM rasters.annual_precipitation WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
                LIMIT 1
            ), pixel_values AS (
                SELECT (ST_PixelAsPolygons(rast)).val as precip FROM clipped
            )
            SELECT AVG(precip) as precip_mean FROM pixel_values WHERE precip IS NOT NULL AND precip >= 0
        """)
        result = db.execute(query, {"wkt": wkt}).first()
        if result and result.precip_mean is not None:
            return {"precipitation_mean_mm": round(result.precip_mean, 1)}
    except Exception as e:
        print(f"Error analyzing precipitation for geometry: {e}")
    return {"precipitation_mean_mm": None}


def analyze_soil_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """Analyze soil texture for a specific geometry"""
    try:
        texture_map = {
            1: "Clay", 2: "Silty Clay", 3: "Sandy Clay", 4: "Clay Loam",
            5: "Silty Clay Loam", 6: "Sandy Clay Loam", 7: "Loam",
            8: "Silty Loam", 9: "Sandy Loam", 10: "Silt", 11: "Loamy Sand", 12: "Sand"
        }
        query = text("""
            SELECT (pvc).value as texture_code, SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.soilgrids_isric WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 12
            GROUP BY texture_code ORDER BY pixel_count DESC LIMIT 1
        """)
        result = db.execute(query, {"wkt": wkt}).first()
        if result:
            code = int(result.texture_code)
            if code in texture_map:
                return {"soil_texture": texture_map[code]}
    except Exception as e:
        print(f"Error analyzing soil for geometry: {e}")
    return {"soil_texture": None}
