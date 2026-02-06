"""
Sampling design API endpoints for forest inventory sampling.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

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
        # Create sampling design with new intensity-based approach
        summary = create_sampling_design(
            db=db,
            calculation_id=calculation_id,
            sampling_type=request.sampling_type,
            sampling_intensity_percent=request.sampling_intensity_percent,
            min_samples_per_block=request.min_samples_per_block or 5,
            min_samples_small_blocks=request.min_samples_small_blocks or 2,
            intensity_per_hectare=request.intensity_per_hectare,  # Deprecated fallback
            grid_spacing_meters=request.grid_spacing_meters,  # Deprecated
            min_distance_meters=request.min_distance_meters,
            plot_shape=request.plot_shape or "circular",
            plot_radius_meters=request.plot_radius_meters,
            plot_length_meters=request.plot_length_meters,
            plot_width_meters=request.plot_width_meters,
            notes=request.notes
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

    # Return GeoJSON by default
    geojson_data = get_sampling_points_geojson(db, design_id)
    return JSONResponse(content=geojson_data)


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
