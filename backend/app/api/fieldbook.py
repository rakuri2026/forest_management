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
            extract_elevation=request.extract_elevation,
            calculate_reference=request.calculate_reference
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
    include_topographic: bool = Query(False, description="Include topographic features (ridge/river data)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all fieldbook points for a calculation.

    Optionally export in CSV, Excel, GPX, or GeoJSON format.
    Can include topographic features (nearest ridge/river) in JSON response.
    """
    # Verify calculation exists and belongs to user
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    from app.utils.file_export import build_disposition

    # Handle export formats
    if format:
        try:
            forest_name = calculation.forest_name
            ext_map = {"csv": "csv", "excel": "xlsx", "gpx": "gpx", "geojson": "geojson"}
            ext = ext_map.get(format, format)

            if format == "csv":
                csv_data = export_fieldbook_csv(db, calculation_id)
                _, disposition = build_disposition(forest_name, "Fieldbook", "FieldData", "csv")
                return StreamingResponse(
                    io.BytesIO(csv_data),
                    media_type="text/csv",
                    headers={"Content-Disposition": disposition}
                )

            elif format == "excel":
                excel_data = export_fieldbook_excel(db, calculation_id)
                _, disposition = build_disposition(forest_name, "Fieldbook", "FieldData", "xlsx")
                return StreamingResponse(
                    io.BytesIO(excel_data),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": disposition}
                )

            elif format == "gpx":
                gpx_data = export_fieldbook_gpx(db, calculation_id)
                _, disposition = build_disposition(forest_name, "Fieldbook", "FieldData", "gpx")
                return StreamingResponse(
                    io.BytesIO(gpx_data),
                    media_type="application/gpx+xml",
                    headers={"Content-Disposition": disposition}
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

    # Enrich points with topographic features if requested
    point_list = []
    if include_topographic and points:
        try:
            from sqlalchemy import text
            import logging
            logger = logging.getLogger(__name__)

            # Get boundary for pre-clipping
            boundary_query = text("""
                SELECT ST_AsText(boundary_geom) as wkt
                FROM public.calculations
                WHERE id = :calc_id
            """)
            boundary_result = db.execute(boundary_query, {"calc_id": str(calculation_id)}).first()

            clipped_features = None
            if boundary_result and boundary_result.wkt:
                # Pre-clip topographic features
                from app.utils.geospatial_vector_optimized import (
                    preclip_topographic_features,
                    find_nearest_topographic_feature_optimized
                )

                try:
                    db.rollback()  # Clear any stale transactions
                except:
                    pass

                clipped_features = preclip_topographic_features(
                    db=db,
                    boundary_wkt=boundary_result.wkt,
                    buffer_meters=100.0
                )

                if clipped_features:
                    logger.info(f"Pre-clipped topographic features for {len(points)} fieldbook points")

            # Process each point
            for point in points:
                point_dict = FieldbookPoint.model_validate(point).model_dump()

                # Add topographic features
                if clipped_features and point.longitude and point.latitude:
                    try:
                        topo_feature = find_nearest_topographic_feature_optimized(
                            db=db,
                            longitude=float(point.longitude),
                            latitude=float(point.latitude),
                            clipped_features=clipped_features,
                            search_radius_meters=100.0,
                            prefer_rivers=True,
                            min_distance_threshold=20.0
                        )

                        if topo_feature:
                            point_dict['nearest_feature'] = topo_feature.get("feature_name", None)
                            point_dict['feature_type'] = topo_feature.get("feature_type", None)
                            point_dict['distance_to_feature'] = topo_feature.get("distance_meters", None)
                            point_dict['direction_to_feature'] = topo_feature.get("direction", None)
                        else:
                            point_dict['nearest_feature'] = None
                            point_dict['feature_type'] = None
                            point_dict['distance_to_feature'] = None
                            point_dict['direction_to_feature'] = None
                    except Exception as e:
                        logger.warning(f"Failed to find topographic feature for point {point.point_number}: {e}")
                        point_dict['nearest_feature'] = None
                        point_dict['feature_type'] = None
                        point_dict['distance_to_feature'] = None
                        point_dict['direction_to_feature'] = None
                else:
                    point_dict['nearest_feature'] = None
                    point_dict['feature_type'] = None
                    point_dict['distance_to_feature'] = None
                    point_dict['direction_to_feature'] = None

                point_list.append(point_dict)

        except Exception as e:
            # If topographic calculation fails, return basic points
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to calculate topographic features: {e}")
            point_list = [FieldbookPoint.model_validate(p).model_dump() for p in points]
    else:
        # No topographic features requested
        point_list = [FieldbookPoint.model_validate(p).model_dump() for p in points]

    return {
        "points": point_list,
        "total_count": len(points)
    }


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
