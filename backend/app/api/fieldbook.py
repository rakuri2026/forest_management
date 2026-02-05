"""
Fieldbook API endpoints for boundary vertex extraction and 20m interpolation.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.calculation import Calculation
from app.models.fieldbook import Fieldbook
from app.schemas.fieldbook import (
    FieldbookGenerateRequest,
    FieldbookGenerateResponse,
    FieldbookListResponse,
    FieldbookPoint,
    FieldbookPointUpdate,
    FieldbookExportFormat
)
from app.services.fieldbook import (
    generate_fieldbook_points,
    update_utm_and_elevation,
    get_elevation_stats
)
from app.services.export import (
    export_fieldbook_csv,
    export_fieldbook_excel,
    export_fieldbook_gpx,
    export_fieldbook_geojson
)
from fastapi.responses import StreamingResponse, JSONResponse
import io

router = APIRouter()


@router.post("/{calculation_id}/fieldbook/generate", response_model=FieldbookGenerateResponse)
async def generate_fieldbook(
    calculation_id: UUID,
    request: FieldbookGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate fieldbook from calculation boundary.

    Extracts vertices and creates interpolated points at specified intervals.
    Optionally extracts elevation from DEM raster.
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

    # Check if fieldbook already exists
    existing = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Fieldbook already exists for this calculation. Delete it first to regenerate."
        )

    try:
        # Generate fieldbook points (includes elevation extraction if requested)
        summary = generate_fieldbook_points(
            db=db,
            calculation_id=calculation_id,
            interpolation_distance=request.interpolation_distance_meters,
            extract_elevation=request.extract_elevation
        )

        db.commit()

        return summary

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate fieldbook: {str(e)}")


@router.get("/{calculation_id}/fieldbook")
async def list_fieldbook_points(
    calculation_id: UUID,
    format: Optional[str] = Query(None, description="Export format: csv, excel, gpx, geojson"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all fieldbook points for a calculation.

    Optionally export in CSV, Excel, GPX, or GeoJSON format.
    """
    # Verify calculation exists and belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Handle export formats
    if format:
        try:
            if format == "csv":
                csv_data = export_fieldbook_csv(db, calculation_id)
                return StreamingResponse(
                    io.BytesIO(csv_data),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=fieldbook_{calculation_id}.csv"}
                )

            elif format == "excel":
                excel_data = export_fieldbook_excel(db, calculation_id)
                return StreamingResponse(
                    io.BytesIO(excel_data),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=fieldbook_{calculation_id}.xlsx"}
                )

            elif format == "gpx":
                gpx_data = export_fieldbook_gpx(db, calculation_id)
                return StreamingResponse(
                    io.BytesIO(gpx_data),
                    media_type="application/gpx+xml",
                    headers={"Content-Disposition": f"attachment; filename=fieldbook_{calculation_id}.gpx"}
                )

            elif format == "geojson":
                geojson_data = export_fieldbook_geojson(db, calculation_id)
                return JSONResponse(content=geojson_data)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

    # Return JSON list
    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        return FieldbookListResponse(points=[], total_count=0)

    return FieldbookListResponse(
        points=[FieldbookPoint.model_validate(p) for p in points],
        total_count=len(points)
    )


@router.get("/{calculation_id}/fieldbook/{point_number}", response_model=FieldbookPoint)
async def get_fieldbook_point(
    calculation_id: UUID,
    point_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific fieldbook point by point number.
    """
    # Verify calculation belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    point = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id,
        Fieldbook.point_number == point_number
    ).first()

    if not point:
        raise HTTPException(status_code=404, detail="Point not found")

    return FieldbookPoint.model_validate(point)


@router.patch("/{calculation_id}/fieldbook/{point_number}", response_model=FieldbookPoint)
async def update_fieldbook_point(
    calculation_id: UUID,
    point_number: int,
    update_data: FieldbookPointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update fieldbook point (remarks, verification status).
    """
    # Verify calculation belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    point = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id,
        Fieldbook.point_number == point_number
    ).first()

    if not point:
        raise HTTPException(status_code=404, detail="Point not found")

    # Update fields
    if update_data.remarks is not None:
        point.remarks = update_data.remarks
    if update_data.is_verified is not None:
        point.is_verified = update_data.is_verified

    try:
        db.commit()
        db.refresh(point)
        return FieldbookPoint.model_validate(point)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.delete("/{calculation_id}/fieldbook")
async def delete_fieldbook(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all fieldbook points for a calculation.
    """
    # Verify calculation belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    try:
        deleted_count = db.query(Fieldbook).filter(
            Fieldbook.calculation_id == calculation_id
        ).delete()

        db.commit()

        return {
            "success": True,
            "message": f"Deleted {deleted_count} fieldbook points",
            "deleted_count": deleted_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
