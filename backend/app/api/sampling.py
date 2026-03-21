"""
Sampling design API endpoints for forest inventory sampling.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID
import io

from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.calculation import Calculation
from app.models.sampling import SamplingDesign
from app.schemas.sampling import (
    SamplingDesignCreate,
    SamplingDesignUpdate,
    SamplingDesign as SamplingDesignSchema,
    SamplingGenerateResponse,
    SamplingPointsGeoJSON,
    SamplingExportFormat
)
from app.services.sampling import create_sampling_design, get_sampling_points_geojson
from app.services.export import (
    export_sampling_csv,
    export_sampling_gpx,
    export_sampling_kml
)
from app.utils.geospatial import extract_elevation_at_point
from app.utils.geospatial_vector import find_nearest_topographic_feature_vector
from app.utils.geospatial_vector_optimized import (
    preclip_topographic_features,
    find_nearest_topographic_feature_optimized
)
from app.services.tree_cover_analysis import extract_accessible_forest_mask
from fastapi.responses import StreamingResponse, JSONResponse
import io
import json

router = APIRouter()


@router.post("/calculations/{calculation_id}/sampling/create", response_model=SamplingGenerateResponse)
async def create_sampling(
    calculation_id: UUID,
    request: SamplingDesignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a sampling design for a calculation with PER-BLOCK sampling.

    Generates sampling points based on:
    - Systematic: Regular grid pattern (preferred for forestry)
    - Random: Random points with optional minimum distance
    - Stratified: Random points within grid strata

    NEW APPROACH:
    - Uses sampling_intensity_percent (% of block area) instead of grid spacing
    - Enforces minimum samples per block (default: 5 for blocks ≥1ha, 2 for <1ha)
    - Calculates grid spacing automatically for systematic sampling
    - Ensures each block is adequately sampled for statistical validity
    """
    # Verify calculation exists and belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    if not calculation.boundary_geom:
        raise HTTPException(status_code=400, detail="Calculation has no boundary geometry")

    # Check if a sampling design already exists for this calculation
    existing_design = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id
    ).first()

    if existing_design:
        raise HTTPException(
            status_code=400,
            detail=f"A sampling design already exists for this calculation. Please delete the existing design (ID: {existing_design.id}) before creating a new one."
        )

    try:
        # Convert block_overrides from Pydantic models to dicts if present
        block_overrides_dict = None
        if request.block_overrides:
            block_overrides_dict = {}
            for block_name, override in request.block_overrides.items():
                if hasattr(override, 'model_dump'):
                    block_overrides_dict[block_name] = override.model_dump(exclude_none=True)
                elif hasattr(override, 'dict'):
                    block_overrides_dict[block_name] = override.dict(exclude_none=True)
                else:
                    block_overrides_dict[block_name] = override

        # Create sampling design with new intensity-based approach
        summary = create_sampling_design(
            db=db,
            calculation_id=calculation_id,
            sampling_type=request.sampling_type,
            sampling_intensity_percent=request.sampling_intensity_percent,
            min_samples_per_block=request.min_samples_per_block or 5,
            min_samples_small_blocks=request.min_samples_small_blocks or 2,
            boundary_buffer_meters=request.boundary_buffer_meters or 50.0,
            # Accessible forest filtering parameters (Phase 2 - NEW)
            filter_tree_cover=request.filter_tree_cover if request.filter_tree_cover is not None else True,
            filter_slope=request.filter_slope if request.filter_slope is not None else False,
            max_slope_degrees=request.max_slope_degrees or 45.0,
            intensity_per_hectare=request.intensity_per_hectare,  # Deprecated fallback
            grid_spacing_meters=request.grid_spacing_meters,  # Deprecated
            min_distance_meters=request.min_distance_meters,
            plot_shape=request.plot_shape or "circular",
            plot_radius_meters=request.plot_radius_meters,
            plot_length_meters=request.plot_length_meters,
            plot_width_meters=request.plot_width_meters,
            notes=request.notes,
            block_overrides=block_overrides_dict
        )

        db.commit()

        return summary

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Sampling design creation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create sampling design: {str(e)}")


@router.get("/calculations/{calculation_id}/sampling", response_model=List[SamplingDesignSchema])
async def list_sampling_designs(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all sampling designs for a calculation.
    """
    # Verify calculation belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    designs = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id
    ).order_by(SamplingDesign.created_at.desc()).all()

    return [SamplingDesignSchema.model_validate(d) for d in designs]


@router.get("/sampling/{design_id}", response_model=SamplingDesignSchema)
async def get_sampling_design(
    design_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific sampling design by ID.
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design:
        raise HTTPException(status_code=404, detail="Sampling design not found")

    # Verify user has access to this design's calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == design.calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=403, detail="Access denied")

    return SamplingDesignSchema.model_validate(design)


@router.get("/sampling/{design_id}/points")
async def get_sampling_points(
    design_id: UUID,
    format: Optional[str] = Query(None, description="Export format: csv, gpx, kml, geojson"),
    include_elevation: bool = Query(True, description="Include elevation (ASLM) data"),
    include_topographic_features: bool = Query(False, description="Include nearest ridge/valley info"),
    prefer_rivers: bool = Query(True, description="Prefer rivers/valleys over ridges for navigation"),
    min_feature_distance: float = Query(20.0, description="Minimum distance to report feature (meters)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get sampling points for a design.

    Optionally export in CSV, GPX, KML, or GeoJSON format.

    Navigation Enhancement Options:
    - include_elevation: Add elevation (ASLM) at each point (default: True)
    - include_topographic_features: Add nearest ridge/valley with distance and direction (default: False)
    - prefer_rivers: Prefer valleys/rivers over ridges when both are close (default: True)
    - min_feature_distance: Don't report features closer than this (default: 20m)
                           If < 20m, the point is likely ON the feature, not near it
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design:
        raise HTTPException(status_code=404, detail="Sampling design not found")

    # Verify user has access
    calculation = db.query(Calculation).filter(
        Calculation.id == design.calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=403, detail="Access denied")

    # Handle export formats
    if format:
        try:
            if format == "csv":
                csv_data = export_sampling_csv(db, design_id)
                return StreamingResponse(
                    io.BytesIO(csv_data),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=sampling_{design_id}.csv"}
                )

            elif format == "gpx":
                gpx_data = export_sampling_gpx(db, design_id)
                return StreamingResponse(
                    io.BytesIO(gpx_data),
                    media_type="application/gpx+xml",
                    headers={"Content-Disposition": f"attachment; filename=sampling_{design_id}.gpx"}
                )

            elif format == "kml":
                kml_data = export_sampling_kml(db, design_id)
                return StreamingResponse(
                    io.BytesIO(kml_data),
                    media_type="application/vnd.google-earth.kml+xml",
                    headers={"Content-Disposition": f"attachment; filename=sampling_{design_id}.kml"}
                )

            elif format == "geojson":
                geojson_data = get_sampling_points_geojson(db, design_id)
                return JSONResponse(content=geojson_data)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    # Return JSON array of points with detailed information
    from shapely import wkt as shapely_wkt
    from pyproj import Transformer

    # Get points geometry as WKT
    wkt_query = text("""
        SELECT ST_AsText(points_geometry) as wkt,
               points_block_assignment
        FROM public.sampling_designs
        WHERE id = :design_id
    """)
    result = db.execute(wkt_query, {"design_id": str(design_id)}).first()

    if not result or not result.wkt:
        return {"points": []}

    # Parse MultiPoint geometry
    multipoint = shapely_wkt.loads(result.wkt)
    block_assignment = result.points_block_assignment or []

    # Get calculation boundary for distance calculation
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

    # OPTIMIZATION: Pre-clip ridge/river data ONCE before the loop
    # This dramatically speeds up exports (20-100x faster!)
    clipped_features = None
    if include_topographic_features:
        clipped_features = preclip_topographic_features(
            db=db,
            boundary_wkt=boundary_wkt,
            buffer_meters=100.0
        )

    # Build points array
    points = []
    for i, point in enumerate(multipoint.geoms):
        lon, lat = point.x, point.y

        # Find block assignment
        block_info = next((b for b in block_assignment if b.get('point_index') == i), None)
        block_number = block_info.get('block_number', 1) if block_info else 1
        block_name = block_info.get('block_name', f'Block {block_number}') if block_info else f'Block {block_number}'

        # Calculate UTM coordinates
        utm_zone = 44 if lon < 84 else 45  # Nepal is in zones 44N and 45N
        transformer = Transformer.from_crs(f"EPSG:4326", f"EPSG:326{utm_zone}", always_xy=True)
        utm_easting, utm_northing = transformer.transform(lon, lat)

        # Calculate distance from boundary (if available)
        distance_from_boundary = None
        if boundary_wkt:
            try:
                boundary_geom = shapely_wkt.loads(boundary_wkt)
                distance_from_boundary = point.distance(boundary_geom.boundary) * 111320  # Convert degrees to meters (approximate)
            except:
                pass

        # Extract elevation (ASLM - Above Sea Level Meter) if requested
        elevation_m = None
        if include_elevation:
            elevation_m = extract_elevation_at_point(db, lon, lat)

        # Find nearest topographic feature using OPTIMIZED pre-clipped data
        topo_feature = None
        topo_context = None
        if include_topographic_features and clipped_features:
            topo_feature = find_nearest_topographic_feature_optimized(
                db=db,
                longitude=lon,
                latitude=lat,
                clipped_features=clipped_features,
                search_radius_meters=100.0,
                prefer_rivers=prefer_rivers,
                min_distance_threshold=min_feature_distance
            )

            # Build topographic context string for display with NAMES
            if topo_feature:
                feature_name = topo_feature.get("feature_name", "unnamed feature")
                distance = topo_feature.get("distance_meters", 0)
                direction = topo_feature.get("direction", "")
                # NEW: Include feature name!
                topo_context = f"{int(distance)}m {direction} of {feature_name}"

        point_data = {
            "id": f"{design_id}_{i}",
            "plot_number": i + 1,
            "block_number": block_number,
            "block_name": block_name,
            "longitude": float(f"{lon:.7f}"),
            "latitude": float(f"{lat:.7f}"),
            "utm_easting": float(f"{utm_easting:.2f}"),
            "utm_northing": float(f"{utm_northing:.2f}"),
            "utm_zone": f"{utm_zone}N",
            "distance_from_boundary": float(f"{distance_from_boundary:.2f}") if distance_from_boundary else None,
        }

        # Add elevation if calculated
        if include_elevation:
            point_data["elevation_m"] = int(elevation_m) if elevation_m else None

        # Add topographic context if calculated
        if include_topographic_features:
            point_data["topographic_context"] = topo_context
            point_data["nearest_feature_type"] = topo_feature.get("feature_type") if topo_feature else None
            point_data["nearest_feature_name"] = topo_feature.get("feature_name") if topo_feature else None  # NEW!
            point_data["nearest_feature_distance_m"] = int(topo_feature.get("distance_meters", 0)) if topo_feature else None
            point_data["nearest_feature_direction"] = topo_feature.get("direction") if topo_feature else None
            point_data["nearest_feature_bearing"] = int(topo_feature.get("bearing_degrees", 0)) if topo_feature else None

        points.append(point_data)

    return {"points": points}


@router.put("/sampling/{design_id}", response_model=SamplingDesignSchema)
async def update_sampling_design(
    design_id: UUID,
    update_data: SamplingDesignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update sampling design notes.
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design:
        raise HTTPException(status_code=404, detail="Sampling design not found")

    # Verify user has access
    calculation = db.query(Calculation).filter(
        Calculation.id == design.calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=403, detail="Access denied")

    # Update notes
    if update_data.notes is not None:
        design.notes = update_data.notes

    try:
        db.commit()
        db.refresh(design)
        return SamplingDesignSchema.model_validate(design)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.delete("/sampling/{design_id}")
async def delete_sampling_design(
    design_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a sampling design.
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design:
        raise HTTPException(status_code=404, detail="Sampling design not found")

    # Verify user has access
    calculation = db.query(Calculation).filter(
        Calculation.id == design.calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        db.delete(design)
        db.commit()

        return {
            "success": True,
            "message": "Sampling design deleted successfully",
            "design_id": str(design_id)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.post("/calculations/{calculation_id}/preview-accessible-forest")
async def preview_accessible_forest(
    calculation_id: UUID,
    filter_tree_cover: bool = Query(True, description="Filter to tree cover only"),
    filter_slope: bool = Query(False, description="Filter by slope accessibility"),
    max_slope_degrees: float = Query(45.0, description="Maximum slope threshold in degrees"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview accessible and protected forest areas BEFORE creating sampling design.

    Returns:
    - Boundary geometry
    - Accessible forest area (GREEN) - tree cover with acceptable slope
    - Protected forest area (RED) - tree cover with steep slope
    - Area statistics

    This allows users to visualize which areas will be sampled before generating the design.
    """
    # Verify calculation exists and belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    if not calculation.boundary_geom:
        raise HTTPException(status_code=400, detail="Calculation has no boundary geometry")

    try:
        # Set statement timeout to prevent long-running queries from hanging server
        # This will abort queries that take longer than 2 minutes
        db.execute(text("SET statement_timeout = '120000'"))  # 120 seconds = 2 minutes

        # Get boundary WKT
        boundary_wkt_query = text("""
            SELECT ST_AsText(boundary_geom) as wkt,
                   ST_AsGeoJSON(boundary_geom) as geojson
            FROM public.calculations
            WHERE id = :calc_id
        """)
        boundary_result = db.execute(boundary_wkt_query, {"calc_id": str(calculation_id)}).first()

        if not boundary_result:
            raise HTTPException(status_code=404, detail="Boundary not found")

        boundary_wkt = boundary_result.wkt
        boundary_geojson = json.loads(boundary_result.geojson)

        # Calculate area statistics
        # IMPORTANT: Slope visualization is too slow for preview
        # We show tree cover only, slope filtering happens during actual sampling
        from app.services.tree_cover_analysis import calculate_accessible_forest_area

        if filter_slope:
            # User requested slope filtering, but it's too slow for preview
            # Show tree cover only with a note
            import logging
            logging.warning(f"Slope filtering requested in preview - showing tree cover only for performance")

        area_stats = calculate_accessible_forest_area(
            db=db,
            geometry_wkt=boundary_wkt,
            filter_tree_cover=filter_tree_cover,
            filter_slope=False,  # Always False for preview - too slow
            max_slope_degrees=max_slope_degrees
        )

        # Add note if slope was requested but not applied
        if filter_slope:
            area_stats["preview_note"] = (
                "Preview shows tree cover only. Slope filtering will be applied during sampling design generation."
            )

        # Extract accessible forest mask (GREEN areas)
        # NOTE: Slope visualization removed for performance - too slow
        # Preview shows tree cover only, slope filtering happens during sampling
        accessible_forest_geojson = None
        if filter_tree_cover:
            # Always use tree cover only for preview (no slope - too slow)
            if False:  # DISABLED: Slope filtering too slow for preview
                # DISABLED: This was too slow and causing 0.00 ha results
                accessible_query = text("""
                    WITH boundary AS (
                        SELECT ST_GeomFromText(:wkt, 4326) as geom
                    ),
                    tree_pixels AS (
                        SELECT
                            val,
                            geom,
                            ST_Centroid(geom) as center
                        FROM (
                            SELECT (ST_PixelAsPolygons(
                                ST_Clip(rast, b.geom, 0.0, true), 1
                            )).*
                            FROM rasters.esa_world_cover, boundary b
                            WHERE ST_Intersects(rast, b.geom)
                        ) pixels
                        WHERE val = 10
                    ),
                    tree_in_boundary AS (
                        SELECT geom, center
                        FROM tree_pixels, boundary b
                        WHERE ST_Within(center, b.geom)
                    ),
                    dem_slope_tiles AS (
                        SELECT ST_Slope(rast, 1, '32BF') as slope_rast
                        FROM rasters.dem, boundary
                        WHERE ST_Intersects(rast, boundary.geom)
                    ),
                    accessible_forest AS (
                        SELECT t.geom
                        FROM tree_in_boundary t
                        LEFT JOIN LATERAL (
                            SELECT ST_Value(slope_rast, t.center) as slope_degrees
                            FROM dem_slope_tiles
                            WHERE ST_Intersects(slope_rast, t.center)
                            LIMIT 1
                        ) s ON true
                        WHERE s.slope_degrees IS NOT NULL
                          AND s.slope_degrees <= :max_slope
                    )
                    SELECT ST_AsGeoJSON(
                        ST_SimplifyPreserveTopology(
                            ST_Union(geom),
                            0.0001
                        )
                    ) as geojson
                    FROM accessible_forest
                    WHERE geom IS NOT NULL
                """)

                try:
                    accessible_result = db.execute(accessible_query, {
                        "wkt": boundary_wkt,
                        "max_slope": max_slope_degrees
                    }).first()

                    if accessible_result and accessible_result.geojson:
                        accessible_forest_geojson = json.loads(accessible_result.geojson)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to extract accessible forest mask: {str(e)}")
            else:
                # Tree cover only, no slope filtering
                accessible_mask_wkt = extract_accessible_forest_mask(
                    db=db,
                    geometry_wkt=boundary_wkt,
                    filter_slope=False,
                    max_slope_degrees=max_slope_degrees
                )

                if accessible_mask_wkt:
                    accessible_geojson_query = text("""
                        SELECT ST_AsGeoJSON(ST_GeomFromText(:wkt, 4326)) as geojson
                    """)
                    accessible_result = db.execute(accessible_geojson_query, {"wkt": accessible_mask_wkt}).first()

                    if accessible_result:
                        accessible_forest_geojson = json.loads(accessible_result.geojson)

        # Extract protected forest mask (RED areas - steep slopes)
        # DISABLED: Too slow for preview, causes 0.00 ha results
        # Slope filtering happens during actual sampling, not in preview
        protected_forest_geojson = None
        if False:  # DISABLED: filter_tree_cover and filter_slope - too slow
            # Get steep forest areas (tree cover with slope > threshold)
            # OPTIMIZED: Calculate slope once per DEM tile, then sample
            protected_query = text("""
                WITH boundary AS (
                    SELECT ST_GeomFromText(:wkt, 4326) as geom
                ),
                -- Extract tree pixels using optimized method
                tree_pixels AS (
                    SELECT
                        val,
                        geom,
                        ST_Centroid(geom) as center
                    FROM (
                        SELECT (ST_PixelAsPolygons(
                            ST_Clip(rast, b.geom, 0.0, true), 1
                        )).*
                        FROM rasters.esa_world_cover, boundary b
                        WHERE ST_Intersects(rast, b.geom)
                    ) pixels
                    WHERE val = 10  -- Tree cover only
                ),
                tree_in_boundary AS (
                    SELECT geom, center
                    FROM tree_pixels, boundary b
                    WHERE ST_Within(center, b.geom)
                ),
                -- OPTIMIZED: Pre-calculate slope for DEM tiles
                dem_slope_tiles AS (
                    SELECT ST_Slope(rast, 1, '32BF') as slope_rast
                    FROM rasters.dem, boundary
                    WHERE ST_Intersects(rast, boundary.geom)
                ),
                -- Sample slope at tree pixel centers
                tree_with_slope AS (
                    SELECT
                        t.geom,
                        ST_Value(dst.slope_rast, t.center) as slope_degrees
                    FROM tree_in_boundary t
                    LEFT JOIN LATERAL (
                        SELECT slope_rast
                        FROM dem_slope_tiles
                        WHERE ST_Intersects(slope_rast, t.center)
                        LIMIT 1
                    ) dst ON true
                ),
                steep_forest AS (
                    SELECT geom
                    FROM tree_with_slope
                    WHERE slope_degrees IS NOT NULL
                      AND slope_degrees > :max_slope
                )
                SELECT ST_AsGeoJSON(
                    ST_SimplifyPreserveTopology(
                        ST_Union(geom),
                        0.0001
                    )
                ) as geojson
                FROM steep_forest
                WHERE geom IS NOT NULL
            """)

            try:
                protected_result = db.execute(protected_query, {
                    "wkt": boundary_wkt,
                    "max_slope": max_slope_degrees
                }).first()

                if protected_result and protected_result.geojson:
                    protected_forest_geojson = json.loads(protected_result.geojson)
            except Exception as e:
                import logging
                logging.warning(f"Failed to extract protected forest mask: {str(e)}")
                # Continue without protected forest visualization

        return {
            "boundary": {
                "type": "Feature",
                "geometry": boundary_geojson,
                "properties": {
                    "name": calculation.forest_name or "Forest Boundary",
                    "layer_type": "boundary"
                }
            },
            "accessible_forest": {
                "type": "Feature",
                "geometry": accessible_forest_geojson,
                "properties": {
                    "layer_type": "accessible_forest",
                    "color": "green",
                    "description": "Resource Effective Area - Can be sampled and managed"
                }
            } if accessible_forest_geojson else None,
            "protected_forest": {
                "type": "Feature",
                "geometry": protected_forest_geojson,
                "properties": {
                    "layer_type": "protected_forest",
                    "color": "red",
                    "description": "Protected Area - Steep slopes, should be preserved"
                }
            } if protected_forest_geojson else None,
            "area_statistics": area_stats,
            "filter_settings": {
                "filter_tree_cover": filter_tree_cover,
                "filter_slope": filter_slope,
                "max_slope_degrees": max_slope_degrees
            }
        }

    except Exception as e:
        import logging
        logging.error(f"Preview accessible forest failed: {str(e)}", exc_info=True)

        # Check if it's a timeout error
        error_msg = str(e).lower()
        if 'timeout' in error_msg or 'statement timeout' in error_msg or 'canceling statement' in error_msg:
            raise HTTPException(
                status_code=408,
                detail=(
                    "Analysis timeout: This forest area is too large or complex for real-time preview. "
                    "Try: (1) Disable slope filter for faster preview, or "
                    "(2) Skip preview and create sampling design directly (slope filtering will still work during sampling)."
                )
            )
        else:
            raise HTTPException(status_code=500, detail=f"Failed to preview forest areas: {str(e)}")
    finally:
        # Reset statement timeout to default
        try:
            db.execute(text("RESET statement_timeout"))
        except:
            pass


@router.get("/sampling/{design_id}/map-layers")
async def get_sampling_map_layers(
    design_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get GeoJSON layers for sampling map visualization:
    - Block boundary
    - Accessible forest area (after tree cover + slope filtering)
    - Sampling points

    Returns GeoJSON FeatureCollection for map display.
    """
    # Get sampling design
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design:
        raise HTTPException(status_code=404, detail="Sampling design not found")

    # Verify user has access
    calculation = db.query(Calculation).filter(
        Calculation.id == design.calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get boundary geometry
    boundary_query = text("""
        SELECT ST_AsGeoJSON(boundary_geom) as boundary_geojson
        FROM public.calculations
        WHERE id = :calc_id
    """)
    boundary_result = db.execute(boundary_query, {"calc_id": str(design.calculation_id)}).first()

    if not boundary_result:
        raise HTTPException(status_code=404, detail="Boundary not found")

    boundary_geojson = json.loads(boundary_result.boundary_geojson)

    # Get accessible forest mask (if filters were applied)
    accessible_forest_geojson = None
    filter_info = design.default_parameters or {}

    if filter_info.get("filter_tree_cover") or filter_info.get("filter_slope"):
        # Get boundary WKT
        boundary_wkt_query = text("""
            SELECT ST_AsText(boundary_geom) as wkt
            FROM public.calculations
            WHERE id = :calc_id
        """)
        boundary_wkt_result = db.execute(boundary_wkt_query, {"calc_id": str(design.calculation_id)}).first()

        if boundary_wkt_result:
            accessible_mask_wkt = extract_accessible_forest_mask(
                db=db,
                geometry_wkt=boundary_wkt_result.wkt,
                filter_slope=filter_info.get("filter_slope", False),
                max_slope_degrees=filter_info.get("max_slope_degrees", 45.0)
            )

            if accessible_mask_wkt:
                # Convert WKT to GeoJSON
                accessible_geojson_query = text("""
                    SELECT ST_AsGeoJSON(ST_GeomFromText(:wkt, 4326)) as geojson
                """)
                accessible_result = db.execute(accessible_geojson_query, {"wkt": accessible_mask_wkt}).first()

                if accessible_result:
                    accessible_forest_geojson = json.loads(accessible_result.geojson)

    # Get sampling points
    points_query = text("""
        SELECT ST_AsGeoJSON(points_geometry) as points_geojson,
               points_block_assignment
        FROM public.sampling_designs
        WHERE id = :design_id
    """)
    points_result = db.execute(points_query, {"design_id": str(design_id)}).first()

    points_geojson = None
    if points_result and points_result.points_geojson:
        points_data = json.loads(points_result.points_geojson)
        block_assignments = points_result.points_block_assignment or []

        # Convert MultiPoint to FeatureCollection with individual point features
        features = []
        if points_data['type'] == 'MultiPoint':
            for i, coord in enumerate(points_data['coordinates']):
                # Find block assignment
                block_info = next((b for b in block_assignments if b.get('point_index') == i), None)
                block_name = block_info.get('block_name', f'Plot {i+1}') if block_info else f'Plot {i+1}'

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": coord
                    },
                    "properties": {
                        "plot_number": i + 1,
                        "block_name": block_name,
                        "plot_id": f"P{i+1}"
                    }
                }
                features.append(feature)

        points_geojson = {
            "type": "FeatureCollection",
            "features": features
        }

    return {
        "boundary": {
            "type": "Feature",
            "geometry": boundary_geojson,
            "properties": {
                "name": calculation.forest_name or "Forest Boundary",
                "layer_type": "boundary"
            }
        },
        "accessible_forest": {
            "type": "Feature",
            "geometry": accessible_forest_geojson,
            "properties": {
                "layer_type": "accessible_forest"
            }
        } if accessible_forest_geojson else None,
        "sampling_points": points_geojson,
        "filter_settings": filter_info
    }
