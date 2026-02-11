"""
Forest boundary analysis service
Performs raster and vector analysis on uploaded forest boundaries
"""
import time
from typing import Dict, Any, Tuple, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime

from ..models.calculation import Calculation


async def analyze_forest_boundary(calculation_id: UUID, db: Session, options: Optional[Dict[str, bool]] = None) -> Tuple[Dict[str, Any], int]:
    """
    Perform comprehensive analysis on forest boundary
    Now analyzes each block separately and adds analysis results to each block

    Args:
        calculation_id: UUID of calculation record
        db: Database session
        options: Dict of boolean flags to enable/disable specific analyses
                 If None, all analyses run (backward compatible)

    Returns:
        Tuple of (result_data dict, processing_time_seconds)
    """
    # Default options: run everything if not specified
    if options is None:
        options = {}

    # Helper function to check if analysis should run
    def should_run(analysis_name: str) -> bool:
        return options.get(analysis_name, True)  # Default True for backward compatibility
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
    for i, block in enumerate(blocks):
        print(f"Analyzing block {i+1}/{len(blocks)}: {block.get('block_name', f'Block {i+1}')}", flush=True)

        try:
            block_analysis = await analyze_block_geometry(
                block['geometry'],
                calculation_id,
                db,
                options
            )
            # Merge analysis results into block data
            analyzed_block = {**block, **block_analysis}
            print(f"Block {i+1} analysis completed successfully", flush=True)

        except Exception as block_error:
            print(f"Error analyzing block {i+1}: {block_error}")
            db.rollback()  # Rollback failed block transaction

            # Commit to clear transaction state for next block
            try:
                db.commit()
                print(f"Transaction reset after block {i+1} error")
            except Exception as commit_error:
                print(f"Warning: Could not commit after block error: {commit_error}")

            # Continue with minimal data for this block
            analyzed_block = {**block, "analysis_error": str(block_error)[:200]}

        analyzed_blocks.append(analyzed_block)

        # ALWAYS commit after each block to ensure clean transaction state for next block
        try:
            db.commit()
            print(f"Block {i+1} transaction committed")
        except Exception as commit_error:
            print(f"Warning: Could not commit after block {i+1}: {commit_error}")
            db.rollback()

    # Store analyzed blocks
    results['blocks'] = analyzed_blocks

    # Commit block results to clear any transaction issues
    print(f"Committing block analysis results...")
    try:
        db.commit()
        print("Block analysis committed successfully")
    except Exception as commit_error:
        print(f"Warning: Could not commit block results: {commit_error}")
        db.rollback()

    # Also calculate whole-area statistics for summary
    # 1. Calculate area (using UTM projection for accuracy)
    print("Starting whole-forest analysis...")
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

    # 2. Raster analysis on whole boundary (if enabled)
    if should_run('run_raster_analysis'):
        raster_results = await analyze_rasters(calculation_id, db)
        results.update(raster_results)

    # 3. Vector analysis (if enabled)
    if should_run('run_proximity'):
        vector_results = await analyze_vectors(calculation_id, db)
        results.update(vector_results)

    # 3b. Get administrative location for whole forest
    whole_geom_query = text("""
        SELECT ST_AsText(boundary_geom) as wkt
        FROM public.calculations
        WHERE id = :calc_id
    """)
    whole_geom = db.execute(whole_geom_query, {"calc_id": str(calculation_id)}).first()
    if whole_geom:
        whole_location = get_administrative_location(whole_geom.wkt, db)
        # Prefix keys with "whole_" to distinguish from block-level data
        results["whole_province"] = whole_location.get("province")
        results["whole_district"] = whole_location.get("district")
        results["whole_municipality"] = whole_location.get("municipality")
        results["whole_ward"] = whole_location.get("ward")
        results["whole_watershed"] = whole_location.get("watershed")
        results["whole_major_river_basin"] = whole_location.get("major_river_basin")

    # 3c. Geology analysis for whole forest
    if whole_geom:
        whole_geology = analyze_geology_geometry(whole_geom.wkt, db)
        results["whole_geology_percentages"] = whole_geology.get("geology_percentages")

    # 3d. Access information for whole forest
    if whole_geom:
        whole_access = calculate_access_info(whole_geom.wkt, db)
        results["whole_access_info"] = whole_access.get("access_info")

    # 3e. Nearby features for whole forest
    if whole_geom:
        whole_features = analyze_nearby_features(whole_geom.wkt, db)
        results["whole_features_north"] = whole_features.get("features_north")
        results["whole_features_east"] = whole_features.get("features_east")
        results["whole_features_south"] = whole_features.get("features_south")
        results["whole_features_west"] = whole_features.get("features_west")

    # 3f. Physiography for whole forest
    if whole_geom:
        print("Analyzing whole forest physiography...", flush=True)
        try:
            whole_physio = analyze_physiography_geometry(whole_geom.wkt, db)
            results["whole_physiography_percentages"] = whole_physio.get("physiography_percentages")
            print(f"Whole forest physiography: {whole_physio.get('physiography_percentages')}", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest physiography: {e}")
            results["whole_physiography_percentages"] = None

    # 3g. Ecoregion for whole forest
    if whole_geom:
        print("Analyzing whole forest ecoregion...", flush=True)
        try:
            whole_ecoregion = analyze_ecoregion_geometry(whole_geom.wkt, db)
            results["whole_ecoregion_percentages"] = whole_ecoregion.get("ecoregion_percentages")
            print(f"Whole forest ecoregion: {whole_ecoregion.get('ecoregion_percentages')}", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest ecoregion: {e}")
            results["whole_ecoregion_percentages"] = None

    # 3h. NASA Forest 2020 for whole forest
    if whole_geom:
        print("Analyzing whole forest NASA forest 2020...", flush=True)
        try:
            whole_nasa = analyze_nasa_forest_2020_geometry(whole_geom.wkt, db)
            results["whole_nasa_forest_2020_percentages"] = whole_nasa.get("nasa_forest_2020_percentages")
            results["whole_nasa_forest_2020_dominant"] = whole_nasa.get("nasa_forest_2020_dominant")
            print(f"Whole forest NASA forest 2020: {whole_nasa.get('nasa_forest_2020_percentages')}", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest NASA forest 2020: {e}")
            results["whole_nasa_forest_2020_percentages"] = None
            results["whole_nasa_forest_2020_dominant"] = None

    # 3i. Landcover 1984 for whole forest (Historical baseline)
    if whole_geom and should_run('run_landcover_1984'):
        print("Analyzing whole forest landcover 1984...", flush=True)
        try:
            whole_lc1984 = analyze_landcover_1984_geometry(whole_geom.wkt, db)
            results["landcover_1984_dominant"] = whole_lc1984.get("landcover_1984_dominant")
            results["landcover_1984_percentages"] = whole_lc1984.get("landcover_1984_percentages")
            print(f"Whole forest landcover 1984 dominant: {whole_lc1984.get('landcover_1984_dominant')}", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest landcover 1984: {e}")
            results["landcover_1984_dominant"] = None
            results["landcover_1984_percentages"] = None

    # 3j. Hansen 2000 for whole forest (Forest classification)
    if whole_geom and should_run('run_hansen2000'):
        print("Analyzing whole forest hansen 2000...", flush=True)
        try:
            whole_hansen2000 = analyze_hansen2000_geometry(whole_geom.wkt, db)
            results["hansen2000_dominant"] = whole_hansen2000.get("hansen2000_dominant")
            results["hansen2000_percentages"] = whole_hansen2000.get("hansen2000_percentages")
            print(f"Whole forest hansen 2000 dominant: {whole_hansen2000.get('hansen2000_dominant')}", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest hansen 2000: {e}")
            results["hansen2000_dominant"] = None
            results["hansen2000_percentages"] = None

    # 3k. Temperature for whole forest
    if whole_geom and should_run('run_temperature'):
        print("Analyzing whole forest temperature...", flush=True)
        try:
            whole_temp = analyze_temperature_geometry(whole_geom.wkt, db)
            results["temperature_mean_c"] = whole_temp.get("temperature_mean_c")
            results["temperature_min_c"] = whole_temp.get("temperature_min_c")
            print(f"Whole forest temperature: {whole_temp.get('temperature_mean_c')}°C (mean), {whole_temp.get('temperature_min_c')}°C (min)", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest temperature: {e}")
            results["temperature_mean_c"] = None
            results["temperature_min_c"] = None

    # 3l. Precipitation for whole forest
    if whole_geom and should_run('run_precipitation'):
        print("Analyzing whole forest precipitation...", flush=True)
        try:
            whole_precip = analyze_precipitation_geometry(whole_geom.wkt, db)
            results["precipitation_mean_mm"] = whole_precip.get("precipitation_mean_mm")
            print(f"Whole forest precipitation: {whole_precip.get('precipitation_mean_mm')} mm/year", flush=True)
        except Exception as e:
            print(f"Error analyzing whole forest precipitation: {e}")
            results["precipitation_mean_mm"] = None

    # 4. Administrative boundaries
    admin_results = await analyze_admin_boundaries(calculation_id, db)
    results.update(admin_results)

    processing_time = int(time.time() - start_time)

    # Commit all analysis results to ensure clean transaction state
    print("Committing final analysis results...")
    try:
        db.commit()
        print("Analysis transaction committed successfully")
    except Exception as commit_error:
        print(f"Warning: Could not commit analysis: {commit_error}")
        db.rollback()

    return results, processing_time


async def analyze_block_geometry(geojson_geometry: Dict, calculation_id: UUID, db: Session, options: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """
    Analyze a single block's geometry

    Args:
        geojson_geometry: Block geometry in GeoJSON format
        calculation_id: UUID of parent calculation (for context)
        db: Database session
        options: Dict of boolean flags to enable/disable specific analyses

    Returns:
        Dict with analysis results for this block
    """
    # Default options: run everything if not specified
    if options is None:
        options = {}

    # Helper function to check if analysis should run
    def should_run(analysis_name: str) -> bool:
        # First check if raster analysis is globally disabled
        if analysis_name != 'run_raster_analysis' and not options.get('run_raster_analysis', True):
            return False
        return options.get(analysis_name, True)  # Default True for backward compatibility
    import json

    # Convert GeoJSON to WKT for PostGIS
    geojson_str = json.dumps(geojson_geometry)

    try:
        # Create a temporary geometry from GeoJSON
        geom_query = text("""
            SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson)) as wkt
        """)
        wkt_result = db.execute(geom_query, {"geojson": geojson_str}).first()
        block_wkt = wkt_result.wkt
    except Exception as e:
        print(f"Error converting GeoJSON to WKT: {e}")
        print(f"GeoJSON string (first 500 chars): {geojson_str[:500]}")
        # CRITICAL: Rollback the failed transaction before raising
        db.rollback()
        raise ValueError(f"Invalid geometry format: {str(e)}")

    block_results = {}

    # Store WKT for future reanalysis
    block_results['wkt'] = block_wkt

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

    # Run raster analyses conditionally based on options
    # 1. DEM - Elevation
    if should_run('run_elevation'):
        dem_results = analyze_dem_geometry(block_wkt, db)
        block_results.update(dem_results)

    # 2. Slope
    if should_run('run_slope'):
        slope_results = analyze_slope_geometry(block_wkt, db)
        block_results.update(slope_results)

    # 3. Aspect
    if should_run('run_aspect'):
        aspect_results = analyze_aspect_geometry(block_wkt, db)
        block_results.update(aspect_results)

    # 4. Canopy Height
    if should_run('run_canopy'):
        canopy_results = analyze_canopy_height_geometry(block_wkt, db)
        block_results.update(canopy_results)

    # 5. AGB (Biomass)
    if should_run('run_biomass'):
        agb_results = analyze_agb_geometry(block_wkt, db)
        block_results.update(agb_results)

    # 6. Forest Health
    if should_run('run_forest_health'):
        health_results = analyze_forest_health_geometry(block_wkt, db)
        block_results.update(health_results)

    # 7. Forest Type
    if should_run('run_forest_type'):
        forest_type_results = analyze_forest_type_geometry(block_wkt, db)
        block_results.update(forest_type_results)

        # 7.1 Potential Tree Species (based on forest type)
        if forest_type_results.get('forest_type_percentages'):
            species_results = analyze_potential_tree_species(
                forest_type_results['forest_type_percentages'],
                db
            )
            block_results.update(species_results)

    # 7A. Historical Land Cover (1984 - Vector)
    if should_run('run_landcover_1984'):
        landcover_1984_results = analyze_landcover_1984_geometry(block_wkt, db)
        block_results.update(landcover_1984_results)

    # 7B. Hansen 2000 Forest Classification (Raster)
    if should_run('run_hansen2000'):
        hansen2000_results = analyze_hansen2000_geometry(block_wkt, db)
        block_results.update(hansen2000_results)

    # 8. Land Cover (ESA WorldCover - Current)
    if should_run('run_landcover'):
        landcover_results = analyze_landcover_geometry(block_wkt, db)
        block_results.update(landcover_results)

    # 9. Forest Loss
    if should_run('run_forest_loss'):
        loss_results = analyze_forest_loss_geometry(block_wkt, db)
        block_results.update(loss_results)

    # 10. Forest Gain
    if should_run('run_forest_gain'):
        gain_results = analyze_forest_gain_geometry(block_wkt, db)
        block_results.update(gain_results)

    # 11. Fire Loss
    if should_run('run_fire_loss'):
        fire_results = analyze_fire_loss_geometry(block_wkt, db)
        block_results.update(fire_results)

    # 12. Temperature
    if should_run('run_temperature'):
        temp_results = analyze_temperature_geometry(block_wkt, db)
        block_results.update(temp_results)

    # 13. Precipitation
    if should_run('run_precipitation'):
        precip_results = analyze_precipitation_geometry(block_wkt, db)
        block_results.update(precip_results)

    # 14. Soil Texture
    if should_run('run_soil'):
        soil_results = analyze_soil_geometry(block_wkt, db)
        block_results.update(soil_results)

    # 15. Administrative Location (Province, District, Municipality, Ward, Watershed)
    location_results = get_administrative_location(block_wkt, db)
    block_results.update(location_results)

    # 16. Geology Analysis
    geology_results = analyze_geology_geometry(block_wkt, db)
    block_results.update(geology_results)

    # 17. Access Information
    access_results = calculate_access_info(block_wkt, db)
    block_results.update(access_results)

    # 18. Nearby Features (within 100m, by direction)
    print("  Calling analyze_nearby_features...", flush=True)
    try:
        nearby_results = analyze_nearby_features(block_wkt, db)
        print(f"  analyze_nearby_features returned: {list(nearby_results.keys())}", flush=True)
        print(f"  Features: N={nearby_results.get('features_north', 'MISSING')}, E={nearby_results.get('features_east', 'MISSING')}, S={nearby_results.get('features_south', 'MISSING')}, W={nearby_results.get('features_west', 'MISSING')}", flush=True)
        block_results.update(nearby_results)
        print(f"  After update, block_results has keys: {list(block_results.keys())}", flush=True)
    except Exception as e:
        print(f"  ERROR in analyze_nearby_features: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Add empty features to avoid crashes
        block_results.update({
            'features_north': None,
            'features_east': None,
            'features_south': None,
            'features_west': None
        })

    # 19. Physiography Analysis
    print("  Analyzing physiography...", flush=True)
    try:
        physio_results = analyze_physiography_geometry(block_wkt, db)
        block_results.update(physio_results)
        print(f"  Physiography analysis complete: {list(physio_results.keys())}", flush=True)
    except Exception as e:
        print(f"  ERROR in physiography analysis: {e}", flush=True)
        block_results.update({'physiography_percentages': None})

    # 20. Ecoregion Analysis
    print("  Analyzing ecoregion...", flush=True)
    try:
        ecoregion_results = analyze_ecoregion_geometry(block_wkt, db)
        block_results.update(ecoregion_results)
        print(f"  Ecoregion analysis complete: {list(ecoregion_results.keys())}", flush=True)
    except Exception as e:
        print(f"  ERROR in ecoregion analysis: {e}", flush=True)
        block_results.update({'ecoregion_percentages': None})

    # 21. NASA Forest 2020 Classification
    print("  Analyzing NASA forest 2020...", flush=True)
    try:
        nasa_forest_results = analyze_nasa_forest_2020_geometry(block_wkt, db)
        block_results.update(nasa_forest_results)
        print(f"  NASA forest 2020 analysis complete: {list(nasa_forest_results.keys())}", flush=True)
    except Exception as e:
        print(f"  ERROR in NASA forest 2020 analysis: {e}", flush=True)
        block_results.update({
            'nasa_forest_2020_percentages': None,
            'nasa_forest_2020_dominant': None
        })

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

    # 7.1 Potential Tree Species (based on forest type)
    if forest_type_results.get('forest_type_percentages'):
        species_results = analyze_potential_tree_species(
            forest_type_results['forest_type_percentages'],
            db
        )
        results.update(species_results)

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
    """Analyze aspect raster - categorical codes (1-8)

    Aspect classes from raster:
    0 = No data (excluded from analysis)
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
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 8
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

                # Track dominant aspect
                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_aspect = direction

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
    26 = Data Not Available
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
            26: "Data Not Available"
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

                # Find dominant (excluding "Data Not Available" if possible)
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
            WHERE (pvc).value IS NOT NULL AND (pvc).value > 0
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


def classify_usda_texture(clay_pct: float, sand_pct: float, silt_pct: float) -> str:
    """
    Classify soil texture using USDA 12-class system
    Based on clay, sand, and silt percentages
    """
    if clay_pct >= 40:
        if sand_pct >= 45:
            return "Sandy Clay"
        elif silt_pct >= 40:
            return "Silty Clay"
        else:
            return "Clay"
    elif clay_pct >= 27:
        if sand_pct >= 20 and sand_pct < 45:
            return "Clay Loam"
        elif sand_pct >= 45:
            return "Sandy Clay Loam"
        else:
            return "Silty Clay Loam"
    elif clay_pct >= 7:
        if sand_pct >= 52:
            if sand_pct >= 80:
                return "Loamy Sand"
            else:
                return "Sandy Loam"
        elif silt_pct >= 50:
            return "Silt Loam"
        elif silt_pct >= 80:
            return "Silt"
        else:
            return "Loam"
    else:  # clay < 7%
        if sand_pct >= 85:
            return "Sand"
        else:
            return "Loamy Sand"


def calculate_carbon_stock(soc_dg_kg: float, bulk_density_cg_cm3: float, depth_cm: float = 30) -> float:
    """
    Calculate soil organic carbon stock in topsoil

    Formula: Carbon Stock (t/ha) = SOC (%) × Bulk Density (g/cm³) × Depth (cm) × 10

    Args:
        soc_dg_kg: Soil organic carbon in dg/kg (from SoilGrids)
        bulk_density_cg_cm3: Bulk density in cg/cm³ (from SoilGrids)
        depth_cm: Soil depth in cm (default 30cm for topsoil)

    Returns:
        Carbon stock in tonnes per hectare
    """
    if not soc_dg_kg or not bulk_density_cg_cm3:
        return None

    # Convert units
    soc_percent = soc_dg_kg / 1000  # dg/kg to % (1 dg/kg = 0.1%)
    bulk_density_g_cm3 = bulk_density_cg_cm3 / 100  # cg/cm³ to g/cm³

    # Calculate carbon stock
    carbon_stock = soc_percent * bulk_density_g_cm3 * depth_cm * 10

    return round(carbon_stock, 2)


def assess_fertility(ph: float, soc_dg_kg: float, nitrogen_cg_kg: float, cec_mmol_kg: float) -> dict:
    """
    Assess soil fertility based on multiple parameters

    Returns:
        dict with fertility_class, score (0-100), and limiting_factors
    """
    score = 0
    limiting_factors = []

    # pH assessment (optimal 5.5-7.0 for most forest species)
    if ph:
        if 5.5 <= ph <= 7.0:
            score += 25
        elif 5.0 <= ph < 5.5 or 7.0 < ph <= 7.5:
            score += 15
            limiting_factors.append("pH slightly outside optimal range")
        elif ph < 5.0:
            score += 5
            limiting_factors.append("Low pH (acidic) limits nutrient availability")
        else:  # pH > 7.5
            score += 5
            limiting_factors.append("High pH (alkaline) may cause micronutrient deficiency")

    # Soil Organic Carbon assessment
    if soc_dg_kg:
        soc_percent = soc_dg_kg / 1000
        if soc_percent >= 2.0:
            score += 25
        elif soc_percent >= 1.0:
            score += 15
        else:
            score += 5
            limiting_factors.append("Low organic carbon content")

    # Nitrogen assessment
    if nitrogen_cg_kg:
        nitrogen_percent = nitrogen_cg_kg / 1000  # cg/kg to %
        if nitrogen_percent >= 0.15:
            score += 25
        elif nitrogen_percent >= 0.10:
            score += 15
        else:
            score += 5
            limiting_factors.append("Low nitrogen content")

    # CEC assessment (cation exchange capacity)
    if cec_mmol_kg:
        if cec_mmol_kg >= 150:
            score += 25
        elif cec_mmol_kg >= 80:
            score += 15
        else:
            score += 5
            limiting_factors.append("Low CEC (poor nutrient retention)")

    # Determine fertility class
    if score >= 80:
        fertility_class = "Very High"
    elif score >= 60:
        fertility_class = "High"
    elif score >= 40:
        fertility_class = "Medium"
    elif score >= 20:
        fertility_class = "Low"
    else:
        fertility_class = "Very Low"

    return {
        "fertility_class": fertility_class,
        "fertility_score": score,
        "limiting_factors": limiting_factors if limiting_factors else ["None identified"]
    }


def assess_compaction(bulk_density_cg_cm3: float) -> dict:
    """
    Assess soil compaction based on bulk density

    Returns:
        dict with compaction_status and compaction_alert
    """
    if not bulk_density_cg_cm3:
        return {"compaction_status": "Unknown", "compaction_alert": None}

    bulk_density_g_cm3 = bulk_density_cg_cm3 / 100

    if bulk_density_g_cm3 < 1.3:
        return {
            "compaction_status": "Not compacted",
            "compaction_alert": None
        }
    elif bulk_density_g_cm3 < 1.6:
        return {
            "compaction_status": "Slight compaction",
            "compaction_alert": "Monitor compaction levels, especially in high-traffic areas"
        }
    elif bulk_density_g_cm3 < 1.8:
        return {
            "compaction_status": "Moderate compaction",
            "compaction_alert": "Compaction may limit root growth. Consider soil amendments or reduced machinery use"
        }
    else:
        return {
            "compaction_status": "Severe compaction",
            "compaction_alert": "CRITICAL: Severe compaction detected. Root penetration severely limited. Intervention required"
        }


def analyze_soil(calculation_id: UUID, db: Session) -> Dict[str, Any]:
    """Analyze soil properties (ISRIC SoilGrids) with enhanced analysis

    Phase 1 Enhanced Features:
    1. USDA 12-class texture classification
    2. Soil carbon stock calculation
    3. Fertility assessment
    4. Compaction alert

    8 bands from soilgrids_isric:
    Band 1 = clay_g_kg (Clay content in g/kg)
    Band 2 = sand_g_kg (Sand content in g/kg)
    Band 3 = silt_g_kg (Silt content in g/kg)
    Band 4 = ph_h2o (Soil pH in H2O)
    Band 5 = soc_dg_kg (Soil organic carbon in dg/kg)
    Band 6 = nitrogen_cg_kg (Nitrogen content in cg/kg)
    Band 7 = bdod_cg_cm3 (Bulk density in cg/cm3)
    Band 8 = cec_mmol_kg (Cation exchange capacity in mmol/kg)

    NOTE: TEMPORARILY DISABLED - Soil analysis causes PostgreSQL crashes
    """
    # TEMPORARILY DISABLED: Soil analysis crashes PostgreSQL
    # Return empty results to allow other analyses to complete
    print("Soil analysis skipped (temporarily disabled to prevent database crashes)")
    return {
        "soil_texture": None,
        "soil_texture_system": "USDA 12-class (disabled)",
        "carbon_stock_t_ha": None,
        "fertility_class": None,
        "fertility_score": None,
        "limiting_factors": ["Soil analysis temporarily disabled to prevent database crashes"],
        "compaction_status": None,
        "compaction_alert": None,
        "soil_properties": {}
    }


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




def get_administrative_location(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Get administrative location by intersecting geometry centroid with admin boundaries

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with: province, district, municipality, ward, watershed, major_river_basin
    """
    location = {}

    # Query for province
    province_query = text("""
        SELECT p.province
        FROM admin.province p
        WHERE ST_Intersects(
            p.shape,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    province_result = db.execute(province_query, {"wkt": geometry_wkt}).first()
    location["province"] = province_result.province if province_result else None

    # Query for municipality (includes district)
    municipality_query = text("""
        SELECT m.district, m.gapa_napa as municipality
        FROM admin.municipality m
        WHERE ST_Intersects(
            m.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    municipality_result = db.execute(municipality_query, {"wkt": geometry_wkt}).first()
    if municipality_result:
        location["district"] = municipality_result.district
        location["municipality"] = municipality_result.municipality
    else:
        location["district"] = None
        location["municipality"] = None

    # Query for ward
    ward_query = text("""
        SELECT w.ward
        FROM admin.ward w
        WHERE ST_Intersects(
            w.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    ward_result = db.execute(ward_query, {"wkt": geometry_wkt}).first()
    location["ward"] = str(ward_result.ward) if ward_result else None

    # Query for watershed
    watershed_query = text("""
        SELECT w."watershed name" as watershed_name, w."major river basin" as major_river_basin
        FROM admin."watershed_Nepal" w
        WHERE ST_Intersects(
            w.geom,
            ST_Centroid(ST_GeomFromText(:wkt, 4326))
        )
        LIMIT 1
    """)
    watershed_result = db.execute(watershed_query, {"wkt": geometry_wkt}).first()
    if watershed_result:
        location["watershed"] = watershed_result.watershed_name
        location["major_river_basin"] = watershed_result.major_river_basin
    else:
        location["watershed"] = None
        location["major_river_basin"] = None

    return location




def analyze_geology_geometry(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze geology classes that intersect with the geometry
    Returns percentage coverage for each geology class

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with geology_percentages: {class_name: percentage}
    """
    geology_query = text("""
        WITH input_geom AS (
            SELECT ST_GeomFromText(:wkt, 4326) as geom
        ),
        total_area AS (
            SELECT ST_Area(ST_Transform(geom, 32645)) as area
            FROM input_geom
        ),
        geology_intersections AS (
            SELECT
                g."geology class" as geology_class,
                ST_Area(
                    ST_Transform(
                        ST_Intersection(g.geom, i.geom),
                        32645
                    )
                ) as intersection_area
            FROM geology.geology g, input_geom i
            WHERE ST_Intersects(g.geom, i.geom)
            AND g."geology class" IS NOT NULL
            AND g."geology class" != 'No Data'
        )
        SELECT
            geology_class,
            (intersection_area / (SELECT area FROM total_area)) * 100 as percentage
        FROM geology_intersections
        WHERE intersection_area > 0
        ORDER BY percentage DESC
    """)

    try:
        result = db.execute(geology_query, {"wkt": geometry_wkt})
        geology_data = {}

        for row in result:
            if row.geology_class and row.percentage:
                geology_data[row.geology_class] = round(float(row.percentage), 2)

        return {
            "geology_percentages": geology_data if geology_data else None
        }
    except Exception as e:
        print(f"Geology analysis error: {e}")
        return {"geology_percentages": None}


def calculate_access_info(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Calculate access information: distance and direction to nearest district headquarters

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with access_info: "Location Direction (degrees°) distance km"
    """
    access_query = text("""
        WITH input_geom AS (
            SELECT
                ST_GeomFromText(:wkt, 4326) as geom,
                ST_Centroid(ST_GeomFromText(:wkt, 4326)) as centroid
        ),
        nearest_hq AS (
            SELECT
                dh."head quarter" as name,
                ST_Distance(
                    ST_Transform(i.centroid, 32645),
                    ST_Transform(dh.geom, 32645)
                ) / 1000.0 as distance_km,
                degrees(
                    ST_Azimuth(
                        i.centroid,
                        dh.geom
                    )
                ) as azimuth_degrees
            FROM admin."district Headquarter" dh, input_geom i
            WHERE dh."head quarter" IS NOT NULL
            ORDER BY ST_Distance(i.centroid, dh.geom)
            LIMIT 1
        )
        SELECT
            name,
            distance_km,
            azimuth_degrees,
            CASE
                WHEN azimuth_degrees >= 337.5 OR azimuth_degrees < 22.5 THEN 'North'
                WHEN azimuth_degrees >= 22.5 AND azimuth_degrees < 67.5 THEN 'Northeast'
                WHEN azimuth_degrees >= 67.5 AND azimuth_degrees < 112.5 THEN 'East'
                WHEN azimuth_degrees >= 112.5 AND azimuth_degrees < 157.5 THEN 'Southeast'
                WHEN azimuth_degrees >= 157.5 AND azimuth_degrees < 202.5 THEN 'South'
                WHEN azimuth_degrees >= 202.5 AND azimuth_degrees < 247.5 THEN 'Southwest'
                WHEN azimuth_degrees >= 247.5 AND azimuth_degrees < 292.5 THEN 'West'
                ELSE 'Northwest'
            END as direction
        FROM nearest_hq
    """)

    try:
        result = db.execute(access_query, {"wkt": geometry_wkt}).first()

        if result and result.name:
            access_str = f"{result.name} {result.direction} ({int(result.azimuth_degrees)}°) {result.distance_km:.1f} km"
            return {"access_info": access_str}
        else:
            return {"access_info": None}
    except Exception as e:
        print(f"Access calculation error: {e}")
        return {"access_info": None}


def analyze_nearby_features(geometry_wkt: str, db: Session) -> Dict[str, Any]:
    """
    Find natural and infrastructure features within 100m of boundary
    Reports features by direction: North, East, South, West

    NEW IMPLEMENTATION: Uses PostgreSQL function for efficiency and reliability
    Single database call returns all 4 directions at once

    Args:
        geometry_wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with features_north, features_east, features_south, features_west
    """

    print("  Calling PostgreSQL analyze_nearby_features function...")

    # Use savepoint for transaction isolation (based on E:\CF_application working implementation)
    savepoint = db.begin_nested()

    try:
        # Call PostgreSQL function - returns all 4 directions in single query
        query = text("""
            SELECT analyze_nearby_features(:wkt)
        """)

        result = db.execute(query, {"wkt": geometry_wkt}).scalar()

        # Commit savepoint (keeps outer transaction intact)
        savepoint.commit()

        # Convert JSONB result to Python dict
        if result:
            # result is already a dict from JSONB
            result_dict = {
                'features_north': result.get('features_north'),
                'features_east': result.get('features_east'),
                'features_south': result.get('features_south'),
                'features_west': result.get('features_west')
            }

            # Debug logging
            print(f"  PostgreSQL function returned all 4 directions:")
            for direction in ['north', 'east', 'south', 'west']:
                key = f'features_{direction}'
                val = result_dict.get(key)
                val_preview = val[:50] if val else None
                print(f"    {key}: {val_preview}")

            return result_dict
        else:
            # Function returned NULL
            print("  WARNING: PostgreSQL function returned NULL")
            return {
                'features_north': None,
                'features_east': None,
                'features_south': None,
                'features_west': None
            }

    except Exception as e:
        # Rollback savepoint only (preserves outer transaction)
        savepoint.rollback()
        print(f"  ERROR calling PostgreSQL function: {e}")
        import traceback
        traceback.print_exc()

        # Return empty result on error
        return {
            'features_north': None,
            'features_east': None,
            'features_south': None,
            'features_west': None
        }


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
    0 = No data (excluded from analysis), 1 = N, 2 = NE, 3 = E, 4 = SE, 5 = S, 6 = SW, 7 = W, 8 = NW
    """
    try:
        # Mapping from raster values to direction names
        aspect_map = {
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
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 8
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
                # Find dominant aspect
                dominant = max(percentages.items(), key=lambda x: x[1])[0]

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
            26: "Data Not Available"
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
    """Analyze ESA WorldCover land cover for a specific geometry (WKT)

    ESA WorldCover classes:
    0 = No data (excluded from analysis)
    10-100 = Valid land cover classes
    """
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
            WHERE (pvc).value IS NOT NULL AND (pvc).value > 0
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
    """Analyze soil properties for a specific geometry (WKT) with enhanced analysis

    Phase 1 Enhanced Features:
    1. USDA 12-class texture classification
    2. Soil carbon stock calculation
    3. Fertility assessment
    4. Compaction alert

    NOTE: TEMPORARILY DISABLED - Soil analysis causes PostgreSQL crashes
    """
    # TEMPORARILY DISABLED: Soil analysis crashes PostgreSQL
    # Return empty results to allow other analyses to complete
    return {
        "soil_texture": None,
        "soil_texture_system": "USDA 12-class (disabled)",
        "carbon_stock_t_ha": None,
        "fertility_class": None,
        "fertility_score": None,
        "limiting_factors": ["Soil analysis temporarily disabled"],
        "compaction_status": None,
        "compaction_alert": None,
        "soil_properties": {}
    }


def analyze_physiography_geometry(wkt: str, db: Session) -> Dict[str, Any]:
        # Process bands individually to prevent database crash from memory overload
        # Get clay content (band 1)
        clay_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 1, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as clay_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        clay_result = db.execute(clay_query, {"wkt": wkt}).first()
        clay_mean = clay_result.clay_mean if clay_result else None

        # Get sand content (band 2)
        sand_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 2, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as sand_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        sand_result = db.execute(sand_query, {"wkt": wkt}).first()
        sand_mean = sand_result.sand_mean if sand_result else None

        # Get silt content (band 3)
        silt_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 3, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as silt_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        silt_result = db.execute(silt_query, {"wkt": wkt}).first()
        silt_mean = silt_result.silt_mean if silt_result else None

        # Get pH (band 4)
        ph_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 4, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as ph_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        ph_result = db.execute(ph_query, {"wkt": wkt}).first()
        ph_mean = ph_result.ph_mean if ph_result else None

        # Get SOC (band 5)
        soc_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 5, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as soc_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        soc_result = db.execute(soc_query, {"wkt": wkt}).first()
        soc_mean = soc_result.soc_mean if soc_result else None

        # Get nitrogen (band 6)
        nitrogen_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 6, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as nitrogen_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        nitrogen_result = db.execute(nitrogen_query, {"wkt": wkt}).first()
        nitrogen_mean = nitrogen_result.nitrogen_mean if nitrogen_result else None

        # Get bulk density (band 7)
        bdod_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 7, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as bdod_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        bdod_result = db.execute(bdod_query, {"wkt": wkt}).first()
        bdod_mean = bdod_result.bdod_mean if bdod_result else None

        # Get CEC (band 8)
        cec_query = text("""
            SELECT AVG((ST_SummaryStats(ST_Clip(rast, 8, ST_GeomFromText(:wkt, 4326)), 1, true)).mean) as cec_mean
            FROM rasters.soilgrids_isric
            WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
        """)
        cec_result = db.execute(cec_query, {"wkt": wkt}).first()
        cec_mean = cec_result.cec_mean if cec_result else None

        if clay_mean or sand_mean or silt_mean:
            # Convert to percentages for texture classification
            clay_pct = clay_mean / 10 if clay_mean else 0
            sand_pct = sand_mean / 10 if sand_mean else 0
            silt_pct = silt_mean / 10 if silt_mean else 0

            # USDA 12-class texture classification
            soil_texture = classify_usda_texture(clay_pct, sand_pct, silt_pct)

            # Calculate carbon stock
            carbon_stock = calculate_carbon_stock(soc_mean, bdod_mean)

            # Assess fertility
            fertility_data = assess_fertility(ph_mean, soc_mean, nitrogen_mean, cec_mean)

            # Assess compaction
            compaction_data = assess_compaction(bdod_mean)

            return {
                "soil_texture": soil_texture,
                "soil_texture_system": "USDA 12-class",
                "carbon_stock_t_ha": carbon_stock,
                "fertility_class": fertility_data["fertility_class"],
                "fertility_score": fertility_data["fertility_score"],
                "limiting_factors": fertility_data["limiting_factors"],
                "compaction_status": compaction_data["compaction_status"],
                "compaction_alert": compaction_data["compaction_alert"],
                "soil_properties": {
                    "clay_g_kg": round(clay_mean, 1) if clay_mean else None,
                    "sand_g_kg": round(sand_mean, 1) if sand_mean else None,
                    "silt_g_kg": round(silt_mean, 1) if silt_mean else None,
                    "ph_h2o": round(ph_mean, 2) if ph_mean else None,
                    "soc_dg_kg": round(soc_mean, 1) if soc_mean else None,
                    "nitrogen_cg_kg": round(nitrogen_mean, 1) if nitrogen_mean else None,
                    "bulk_density_cg_cm3": round(bdod_mean, 1) if bdod_mean else None,
                    "cec_mmol_kg": round(cec_mean, 1) if cec_mean else None
                }
            }
    # except Exception as e:
    #     print(f"Error analyzing soil for geometry: {e}")
    #
    # return {
    #     "soil_texture": None,
    #     "soil_texture_system": "USDA 12-class",
    #     "carbon_stock_t_ha": None,
    #     "fertility_class": None,
    #     "fertility_score": None,
    #     "limiting_factors": [],
    #     "compaction_status": None,
    #     "compaction_alert": None,
    #     "soil_properties": {}
    # }


def analyze_physiography_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze physiographic zones that intersect with geometry
    Returns percentage coverage for each zone (sum = 100%)
    Uses UTM projection for accurate area calculation

    Args:
        wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with physiography_percentages: {zone_name: percentage}
    """
    try:
        # Determine UTM zone from centroid longitude
        centroid_query = text("""
            SELECT ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) as lon
        """)
        centroid_result = db.execute(centroid_query, {"wkt": wkt}).first()
        utm_srid = 32645 if centroid_result.lon > 84 else 32644

        # Calculate intersection areas in UTM projection
        query = text(f"""
            WITH input_geom AS (
                SELECT ST_GeomFromText(:wkt, 4326) as geom
            ),
            total_area AS (
                SELECT ST_Area(ST_Transform(geom, {utm_srid})) as area
                FROM input_geom
            ),
            intersections AS (
                SELECT
                    p."physiography Zone" as zone_name,
                    ST_Area(
                        ST_Transform(
                            ST_Intersection(p.geom, i.geom),
                            {utm_srid}
                        )
                    ) as intersection_area
                FROM admin.physiography p, input_geom i
                WHERE ST_Intersects(p.geom, i.geom)
                AND p."physiography Zone" IS NOT NULL
            )
            SELECT
                zone_name,
                (intersection_area / (SELECT area FROM total_area)) * 100 as percentage
            FROM intersections
            WHERE intersection_area > 0
            ORDER BY percentage DESC
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            percentages = {}
            for r in results:
                percentages[r.zone_name] = round(float(r.percentage), 2)

            return {"physiography_percentages": percentages}
    except Exception as e:
        print(f"Error analyzing physiography: {e}")
        import traceback
        traceback.print_exc()

    return {"physiography_percentages": None}


def analyze_ecoregion_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze ecoregions that intersect with geometry
    Returns percentage coverage for each ecoregion (sum = 100%)
    Uses UTM projection for accurate area calculation

    Args:
        wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with ecoregion_percentages: {eco_name: percentage}
    """
    try:
        # Determine UTM zone from centroid longitude
        centroid_query = text("""
            SELECT ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) as lon
        """)
        centroid_result = db.execute(centroid_query, {"wkt": wkt}).first()
        utm_srid = 32645 if centroid_result.lon > 84 else 32644

        # Calculate intersection areas in UTM projection
        query = text(f"""
            WITH input_geom AS (
                SELECT ST_GeomFromText(:wkt, 4326) as geom
            ),
            total_area AS (
                SELECT ST_Area(ST_Transform(geom, {utm_srid})) as area
                FROM input_geom
            ),
            intersections AS (
                SELECT
                    e.eco_name as ecoregion_name,
                    ST_Area(
                        ST_Transform(
                            ST_Intersection(e.geom, i.geom),
                            {utm_srid}
                        )
                    ) as intersection_area
                FROM ecology.ecoregion e, input_geom i
                WHERE ST_Intersects(e.geom, i.geom)
                AND e.eco_name IS NOT NULL
            )
            SELECT
                ecoregion_name,
                (intersection_area / (SELECT area FROM total_area)) * 100 as percentage
            FROM intersections
            WHERE intersection_area > 0
            ORDER BY percentage DESC
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            percentages = {}
            for r in results:
                percentages[r.ecoregion_name] = round(float(r.percentage), 2)

            return {"ecoregion_percentages": percentages}
    except Exception as e:
        print(f"Error analyzing ecoregion: {e}")
        import traceback
        traceback.print_exc()

    return {"ecoregion_percentages": None}


def analyze_nasa_forest_2020_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze NASA forest 2020 classification
    Returns pixel count and percentage for each forest type (sum = 100%)

    Forest types:
    0 = no data (excluded from analysis)
    1 = primary_forest
    2 = young_secondary_forest
    3 = old_secondary_forest

    Args:
        wkt: WKT string of geometry
        db: Database session

    Returns:
        Dict with nasa_forest_2020_percentages and nasa_forest_2020_dominant
    """
    try:
        forest_type_map = {
            1: "primary_forest",
            2: "young_secondary_forest",
            3: "old_secondary_forest"
        }

        query = text("""
            SELECT
                (pvc).value as forest_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.nasa_forest_2020
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 1 AND 3
            GROUP BY forest_class
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if results:
            total_pixels = sum(r.pixel_count for r in results)
            percentages = {}
            dominant = None
            max_pct = 0

            for r in results:
                class_code = int(r.forest_class)
                if class_code in forest_type_map:
                    pct = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                    class_name = forest_type_map[class_code]
                    percentages[class_name] = round(pct, 2)

                    if pct > max_pct:
                        max_pct = pct
                        dominant = class_name

            return {
                "nasa_forest_2020_percentages": percentages,
                "nasa_forest_2020_dominant": dominant
            }
    except Exception as e:
        print(f"Error analyzing NASA forest 2020: {e}")
        import traceback
        traceback.print_exc()

    return {
        "nasa_forest_2020_percentages": None,
        "nasa_forest_2020_dominant": None
    }


def analyze_landcover_1984_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze 1984 landcover using vector polygon intersection

    This analyzes historical land cover from 1984 vector data (landcover schema)
    Uses spatial intersection to calculate area of each landcover type within boundary

    Returns:
        landcover_1984_dominant: Most common landcover type by area
        landcover_1984_percentages: Percentage breakdown by landcover type
    """
    try:
        # Detect UTM zone for accurate area calculation
        centroid_query = text("""
            SELECT ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) as longitude
        """)
        centroid_result = db.execute(centroid_query, {"wkt": wkt}).first()

        if not centroid_result:
            return {"landcover_1984_dominant": None, "landcover_1984_percentages": {}}

        longitude = centroid_result.longitude
        utm_zone = int((longitude + 180) / 6) + 1
        utm_srid = 32600 + utm_zone if longitude >= 0 else 32700 + utm_zone

        # Calculate intersection areas for each landcover type
        query = text(f"""
            WITH input_geom AS (
                SELECT ST_GeomFromText(:wkt, 4326) as geom
            ),
            total_area AS (
                SELECT ST_Area(ST_Transform(geom, {utm_srid})) as area
                FROM input_geom
            ),
            intersections AS (
                SELECT
                    lc.landuse_yr1984 as landcover_type,
                    ST_Area(
                        ST_Transform(
                            ST_Intersection(lc.geom, i.geom),
                            {utm_srid}
                        )
                    ) as intersection_area
                FROM landcover.landcover_1984 lc, input_geom i
                WHERE ST_Intersects(lc.geom, i.geom)
                AND lc.landuse_yr1984 IS NOT NULL
            )
            SELECT
                landcover_type,
                intersection_area,
                (intersection_area / (SELECT area FROM total_area)) * 100 as percentage
            FROM intersections
            WHERE intersection_area > 0
            ORDER BY percentage DESC
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if not results:
            return {"landcover_1984_dominant": None, "landcover_1984_percentages": {}}

        landcover_percentages = {}
        dominant_type = None
        max_percentage = 0

        for r in results:
            landcover_type = r.landcover_type.strip() if r.landcover_type else "Unknown"
            percentage = float(r.percentage)
            landcover_percentages[landcover_type] = round(percentage, 2)

            if percentage > max_percentage:
                max_percentage = percentage
                dominant_type = landcover_type

        return {
            "landcover_1984_dominant": dominant_type,
            "landcover_1984_percentages": landcover_percentages
        }

    except Exception as e:
        print(f"Error analyzing landcover 1984 for geometry: {e}")
        import traceback
        traceback.print_exc()

    return {"landcover_1984_dominant": None, "landcover_1984_percentages": {}}


def analyze_hansen2000_geometry(wkt: str, db: Session) -> Dict[str, Any]:
    """
    Analyze Hansen 2000 forest classification (raster)

    Hansen 2000 Classified Forest Data from rasters.hansen2000_classified
    Legend:
        0 = Non forest
        1 = Bush/Shrub
        2 = Poor forest
        3 = Moderate forest
        4 = Good forest

    Returns:
        hansen2000_dominant: Most common forest class by pixel count
        hansen2000_percentages: Percentage breakdown by forest class
    """
    try:
        forest_class_map = {
            0: "Non forest",
            1: "Bush/Shrub",
            2: "Poor forest",
            3: "Moderate forest",
            4: "Good forest"
        }

        query = text("""
            SELECT
                (pvc).value as forest_class,
                SUM((pvc).count) as pixel_count
            FROM (
                SELECT ST_ValueCount(ST_Clip(rast, ST_GeomFromText(:wkt, 4326))) as pvc
                FROM rasters.hansen2000_classified
                WHERE ST_Intersects(rast, ST_GeomFromText(:wkt, 4326))
            ) as subquery
            WHERE (pvc).value IS NOT NULL AND (pvc).value BETWEEN 0 AND 4
            GROUP BY forest_class
            ORDER BY pixel_count DESC
        """)

        results = db.execute(query, {"wkt": wkt}).fetchall()

        if not results:
            return {"hansen2000_dominant": None, "hansen2000_percentages": {}}

        total_pixels = sum(r.pixel_count for r in results)
        percentages = {}
        dominant_class = None
        max_percentage = 0

        for r in results:
            class_code = int(r.forest_class)
            if class_code in forest_class_map:
                percentage = (r.pixel_count / total_pixels * 100) if total_pixels > 0 else 0
                class_name = forest_class_map[class_code]
                percentages[class_name] = round(percentage, 2)

                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_class = class_name

        return {
            "hansen2000_dominant": dominant_class,
            "hansen2000_percentages": percentages
        }

    except Exception as e:
        print(f"Error analyzing Hansen 2000 for geometry: {e}")
        import traceback
        traceback.print_exc()

    return {"hansen2000_dominant": None, "hansen2000_percentages": {}}


def analyze_potential_tree_species(forest_type_percentages: Dict[str, float], db: Session) -> Dict[str, Any]:
    """
    Analyze potential tree species based on forest type distribution

    Uses forest_type → species associations to suggest likely species for a block/forest
    Orders species by:
    1. Availability rank (Dominant > Co-dominant > Associate > Occasional)
    2. Economic value (high-value timber species prioritized)
    3. Frequency in the forest type

    Args:
        forest_type_percentages: Dict of {forest_type_name: percentage}
        db: Database session

    Returns:
        {
            "potential_species": [
                {
                    "scientific_name": str,
                    "local_name": str,
                    "role": str (Dominant/Co-dominant/Associate/Occasional),
                    "availability_rank": int (1-4),
                    "forest_types": [str] (which forest types this species is found in),
                    "combined_score": float (for ranking),
                    "economic_value": str (High/Medium/Low)
                }
            ],
            "species_count": int
        }
    """
    try:
        if not forest_type_percentages:
            return {"potential_species": [], "species_count": 0}

        # Define high-value timber species in Nepal
        HIGH_VALUE_SPECIES = {
            'Shorea robusta', 'Dalbergia sissoo', 'Tectona grandis', 'Acacia catechu',
            'Cedrus deodara', 'Pinus roxburghii', 'Alnus nepalensis', 'Juglans regia',
            'Cedrela toona', 'Michelia champaca'
        }

        MEDIUM_VALUE_SPECIES = {
            'Schima wallichii', 'Castanopsis indica', 'Terminalia spp', 'Albizia spp',
            'Bombax ceiba', 'Adina cardifolia', 'Lagerstroemia parviflora'
        }

        # Get forest type names and normalize them
        # Database has " Forest" suffix, but analysis may not
        forest_type_names = []
        for ft_name in forest_type_percentages.keys():
            # Add " Forest" suffix if not already present
            if not ft_name.endswith(" Forest") and not ft_name.endswith(" forest"):
                forest_type_names.append(ft_name + " Forest")
            else:
                forest_type_names.append(ft_name)

        query = text("""
            SELECT
                ft.forest_type_name,
                tsc.scientific_name,
                tsc.local_name,
                fsa.availability_rank,
                fsa.role,
                fsa.frequency_percent,
                fsa.canopy_coverage_percent
            FROM forest_species_association fsa
            JOIN forest_types ft ON fsa.forest_type_id = ft.id
            JOIN tree_species_coefficients tsc ON fsa.species_id = tsc.id
            WHERE ft.forest_type_name = ANY(:forest_types)
            ORDER BY fsa.availability_rank, fsa.frequency_percent DESC NULLS LAST
        """)

        results = db.execute(query, {"forest_types": forest_type_names}).fetchall()

        results = db.execute(query, {"forest_types": forest_type_names}).fetchall()

        if not results:
            return {"potential_species": [], "species_count": 0}

        # Aggregate species data across all forest types
        species_data = {}

        for r in results:
            scientific_name = r.scientific_name

            if scientific_name not in species_data:
                # Determine economic value
                if any(scientific_name.startswith(hvs.split()[0]) for hvs in HIGH_VALUE_SPECIES):
                    economic_value = "High"
                    value_score = 3
                elif any(scientific_name.startswith(mvs.split()[0]) for mvs in MEDIUM_VALUE_SPECIES):
                    economic_value = "Medium"
                    value_score = 2
                else:
                    economic_value = "Low"
                    value_score = 1

                species_data[scientific_name] = {
                    "scientific_name": scientific_name,
                    "local_name": r.local_name or "Unknown",
                    "role": r.role,
                    "availability_rank": r.availability_rank,
                    "economic_value": economic_value,
                    "forest_types": [r.forest_type_name],
                    "frequency_percent": r.frequency_percent or 0,
                    "value_score": value_score
                }
            else:
                # Species appears in multiple forest types - update
                if r.forest_type_name not in species_data[scientific_name]["forest_types"]:
                    species_data[scientific_name]["forest_types"].append(r.forest_type_name)

                # Use the best (lowest) availability rank
                if r.availability_rank < species_data[scientific_name]["availability_rank"]:
                    species_data[scientific_name]["availability_rank"] = r.availability_rank
                    species_data[scientific_name]["role"] = r.role

        # Calculate combined score for sorting
        # Lower score = higher priority
        # Score = availability_rank * 10 - value_score * 3 - (frequency_percent/10)
        for species in species_data.values():
            species["combined_score"] = (
                species["availability_rank"] * 10  # Lower rank = better (10-40)
                - species["value_score"] * 3  # Higher value = better (-9 to -3)
                - (species["frequency_percent"] / 10)  # Higher frequency = better (-10 to 0)
            )

        # Sort by combined score (lower is better)
        sorted_species = sorted(species_data.values(), key=lambda x: x["combined_score"])

        # Remove internal scoring fields from output
        for species in sorted_species:
            del species["value_score"]
            del species["combined_score"]
            del species["frequency_percent"]

        return {
            "potential_species": sorted_species,
            "species_count": len(sorted_species)
        }

    except Exception as e:
        print(f"Error analyzing potential tree species: {e}")
        import traceback
        traceback.print_exc()
        return {"potential_species": [], "species_count": 0}
