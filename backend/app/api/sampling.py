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
from fastapi.responses import StreamingResponse, JSONResponse
import io

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get sampling points for a design.

    Optionally export in CSV, GPX, KML, or GeoJSON format.
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
            "distance_from_boundary": float(f"{distance_from_boundary:.2f}") if distance_from_boundary else None
        }
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
