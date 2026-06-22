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
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.calculation import Calculation
from app.models.sampling import SamplingDesign
from app.models.forest_block import ForestBlock
from app.schemas.sampling import (
    SamplingDesignCreate,
    SamplingDesignUpdate,
    SamplingDesign as SamplingDesignSchema,
    SamplingGenerateResponse,
    SamplingPointsGeoJSON,
    SamplingExportFormat,
    SamplingMethod,
    ProtectedZoneInfo
)
from app.services.sampling import (
    create_sampling_design,
    create_sampling_design_guideline_2061,
    get_sampling_points_geojson
)
from app.services.guideline_sampling import detect_protected_zones
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
    Create a sampling design with either Guideline-2061 or Manual method.

    **Guideline-2061 Method (Recommended):**
    - Nepal DoF standard sampling methodology
    - Sample counts determined by lookup tables based on block size
    - Supports 0.5%, 1%, or 0.1% intensity
    - Systematic sampling only
    - Automatic protected zone detection

    **Manual Method (Advanced):**
    - Full control over sampling parameters
    - Supports systematic, random, stratified algorithms
    - Intensity as percentage with min samples rules
    - Custom plot sizes and shapes
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
        if request.sampling_method == SamplingMethod.GUIDELINE_2061:
            # Use Guideline-2061 method
            logger.info(f"Creating Guideline-2061 sampling design for calculation {calculation_id}")

            # Calculate plot dimensions from plot_size_sqm
            plot_size_sqm = request.plot_size_sqm or 500
            if request.plot_shape == "circular":
                import math
                plot_radius_meters = math.sqrt(plot_size_sqm / math.pi)
            else:
                plot_side_meters = math.sqrt(plot_size_sqm)

            summary = create_sampling_design_guideline_2061(
                db=db,
                calculation_id=calculation_id,
                productive_intensity=float(request.productive_intensity.value) if request.productive_intensity else 0.5,
                sample_protected_zone=request.sample_protected_zone or False,
                plot_size_sqm=plot_size_sqm,
                plot_shape=request.plot_shape or "circular",
                filter_tree_cover=request.filter_tree_cover if request.filter_tree_cover is not None else True,
                filter_slope=request.filter_slope if request.filter_slope is not None else False,
                max_slope_degrees=request.max_slope_degrees or 45.0,
                boundary_buffer_meters=request.boundary_buffer_meters or 50.0,
                notes=request.notes
            )

        else:
            # Use existing manual method
            logger.info(f"Creating manual sampling design for calculation {calculation_id}")

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

            summary = create_sampling_design(
                db=db,
                calculation_id=calculation_id,
                sampling_type=request.sampling_type,
                sampling_intensity_percent=request.sampling_intensity_percent,
                min_samples_per_block=request.min_samples_per_block or 5,
                min_samples_small_blocks=request.min_samples_small_blocks or 2,
                boundary_buffer_meters=request.boundary_buffer_meters or 50.0,
                filter_tree_cover=request.filter_tree_cover if request.filter_tree_cover is not None else True,
                filter_slope=request.filter_slope if request.filter_slope is not None else False,
                max_slope_degrees=request.max_slope_degrees or 45.0,
                intensity_per_hectare=request.intensity_per_hectare,
                grid_spacing_meters=request.grid_spacing_meters,
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


@router.get("/calculations/{calculation_id}/protected-zones", response_model=ProtectedZoneInfo)
async def get_protected_zones(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get protected zone information for a calculation.

    Used to determine if protected zone sampling option should be shown
    in Guideline-2061 sampling method.

    Returns information about:
    - Whether protected zones exist
    - Total protected area
    - Names of protected zones
    - Productive (non-protected) area

    This endpoint is called by the frontend when user selects Guideline-2061
    method to display protected zone sampling checkbox if applicable.
    """
    # Verify calculation exists and belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Detect protected zones
    protected_info = detect_protected_zones(calculation)

    return ProtectedZoneInfo(**protected_info)


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

    from app.utils.file_export import build_disposition

    # Handle export formats
    if format:
        try:
            forest_name = calculation.forest_name

            if format == "csv":
                csv_data = export_sampling_csv(db, design_id)
                _, disposition = build_disposition(forest_name, "Sampling", "SamplePoints", "csv")
                return StreamingResponse(
                    io.BytesIO(csv_data),
                    media_type="text/csv",
                    headers={"Content-Disposition": disposition}
                )

            elif format == "gpx":
                gpx_data = export_sampling_gpx(db, design_id)
                _, disposition = build_disposition(forest_name, "Sampling", "SamplePoints", "gpx")
                return StreamingResponse(
                    io.BytesIO(gpx_data),
                    media_type="application/gpx+xml",
                    headers={"Content-Disposition": disposition}
                )

            elif format == "kml":
                kml_data = export_sampling_kml(db, design_id)
                _, disposition = build_disposition(forest_name, "Sampling", "SamplePoints", "kml")
                return StreamingResponse(
                    io.BytesIO(kml_data),
                    media_type="application/vnd.google-earth.kml+xml",
                    headers={"Content-Disposition": disposition}
                )

            elif format == "geojson":
                geojson_data = get_sampling_points_geojson(db, design_id)
                _, disposition = build_disposition(forest_name, "Sampling", "SamplePoints", "geojson")
                return JSONResponse(
                    content=geojson_data,
                    headers={"Content-Disposition": disposition}
                )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    # Return cached points if available (always — eliminates recomputation on tab switch / reload)
    if design.points_data:
        return design.points_data

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
    # Always compute on cache miss so cached data is complete
    clipped_features = None
    if boundary_wkt:
        clipped_features = preclip_topographic_features(
            db=db,
            boundary_wkt=boundary_wkt,
            buffer_meters=100.0
        )

    # Helper function to safely convert float to JSON-compatible value
    def safe_float(value, decimals=2):
        """Convert float to JSON-safe value, replacing NaN/inf with None"""
        if value is None:
            return None
        try:
            import math
            if math.isnan(value) or math.isinf(value):
                return None
            return float(f"{value:.{decimals}f}")
        except (TypeError, ValueError):
            return None

    def safe_int(value):
        """Convert to int, replacing NaN/None with None"""
        if value is None:
            return None
        try:
            import math
            if math.isnan(value) or math.isinf(value):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    # Build points array
    points = []
    for i, point in enumerate(multipoint.geoms):
        lon, lat = point.x, point.y

        # Find block assignment
        block_info = next((b for b in block_assignment if b.get('point_index') == i), None)
        block_number = block_info.get('block_number', 1) if block_info else 1
        block_name = block_info.get('block_name', f'Block {block_number}') if block_info else f'Block {block_number}'
        zone_type = block_info.get('zone_type', 'Productive') if block_info else 'Productive'

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

        # Extract elevation (ASLM - Above Sea Level Meter)
        # Always computed on cache miss so cached data is complete
        elevation_m = extract_elevation_at_point(db, lon, lat)

        # Find nearest topographic feature using OPTIMIZED pre-clipped data
        # Always computed on cache miss so cached data is complete
        topo_feature = None
        if clipped_features:
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
        topo_context = None
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
            "zone_type": zone_type,
            "longitude": safe_float(lon, 7),
            "latitude": safe_float(lat, 7),
            "utm_easting": safe_float(utm_easting, 2),
            "utm_northing": safe_float(utm_northing, 2),
            "utm_zone": f"{utm_zone}N",
            "distance_from_boundary": safe_float(distance_from_boundary, 2),
        }

        # Always include elevation and topographic context in cached response
        point_data["elevation_m"] = safe_int(elevation_m)
        point_data["topographic_context"] = topo_context
        point_data["nearest_feature_type"] = topo_feature.get("feature_type") if topo_feature else None
        point_data["nearest_feature_name"] = topo_feature.get("feature_name") if topo_feature else None
        point_data["nearest_feature_distance_m"] = safe_int(topo_feature.get("distance_meters", 0) if topo_feature else None)
        point_data["nearest_feature_direction"] = topo_feature.get("direction") if topo_feature else None
        point_data["nearest_feature_bearing"] = safe_int(topo_feature.get("bearing_degrees", 0) if topo_feature else None)

        points.append(point_data)

    result = {"points": points}

    # Cache computed points for instant loading on subsequent visits
    design.points_data = result
    db.add(design)
    db.commit()

    return result


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

    # Get forest blocks (blocks, compartments, sub-compartments)
    forest_blocks_geojson = None
    from sqlalchemy import func as sa_func
    blocks = db.query(
        ForestBlock.id,
        ForestBlock.name,
        ForestBlock.division_level,
        ForestBlock.area_hectares,
        sa_func.ST_AsGeoJSON(ForestBlock.geometry).label('geojson')
    ).filter(
        ForestBlock.calculation_id == design.calculation_id
    ).order_by(ForestBlock.division_level, ForestBlock.index).all()

    if blocks:
        block_features = []
        for block in blocks:
            block_geom = json.loads(block.geojson)
            block_features.append({
                "type": "Feature",
                "geometry": block_geom,
                "properties": {
                    "id": str(block.id),
                    "name": block.name,
                    "division_level": block.division_level,
                    "area_hectares": block.area_hectares,
                    "level_name": {0: "Block", 1: "Compartment", 2: "Sub-compartment"}.get(block.division_level, f"Level {block.division_level}")
                }
            })
        forest_blocks_geojson = {
            "type": "FeatureCollection",
            "features": block_features
        }

    # Get rivers clipped to forest boundary
    rivers_geojson = None
    try:
        river_query = text("""
            SELECT
                COALESCE(NULLIF(TRIM(r."river name"), ''), 'River') as name,
                ST_AsGeoJSON(ST_Intersection(r.shape, calc_geom.geom)) as geometry
            FROM river.river84 r,
                (SELECT boundary_geom as geom FROM public.calculations WHERE id = :calc_id) calc_geom
            WHERE ST_Intersects(r.shape, calc_geom.geom)
            LIMIT 50
        """)
        river_results = db.execute(river_query, {"calc_id": str(design.calculation_id)}).fetchall()
        if river_results:
            river_features = []
            for r in river_results:
                geom = json.loads(r.geometry)
                if geom and geom.get('type') and geom['type'] != 'GeometryCollection':
                    river_features.append({
                        "type": "Feature",
                        "geometry": geom,
                        "properties": {
                            "name": r.name or "River"
                        }
                    })
            if river_features:
                rivers_geojson = {
                    "type": "FeatureCollection",
                    "features": river_features
                }
    except Exception as e:
        logger.warning(f"Failed to query rivers: {e}")
        db.rollback()
        rivers_geojson = None

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
                zone_type = block_info.get('zone_type', 'Productive') if block_info else 'Productive'

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": coord
                    },
                    "properties": {
                        "plot_number": i + 1,
                        "block_name": block_name,
                        "zone_type": zone_type,
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
        "forest_blocks": forest_blocks_geojson,
        "rivers": rivers_geojson,
        "sampling_points": points_geojson,
        "filter_settings": filter_info,
        "calculation_id": str(design.calculation_id)
    }
