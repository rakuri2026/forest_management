from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.schemas.user_group import (
    ExtentResponse,
    AnalysisResponse,
    UserGroupResults,
    POIResponse,
    ManualExtentRequest,
    LandCoverAnalysisResponse
)
from app.services.user_group_analysis import UserGroupAnalysisService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/calculations/{calculation_id}/user-group/upload", response_model=ExtentResponse)
async def upload_extent_boundary(
    calculation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload extent boundary file (KML, KMZ, Shapefile, GPX, GeoJSON, CSV)
    """
    try:
        service = UserGroupAnalysisService(db)
        extent = await service.process_uploaded_boundary(
            calculation_id=calculation_id,
            file=file,
            user_id=current_user.id
        )
        return ExtentResponse(
            extent_id=extent.id,
            message="Extent boundary uploaded successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading extent boundary: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload extent boundary")


@router.post("/calculations/{calculation_id}/user-group/manual", response_model=ExtentResponse)
async def create_manual_extent(
    calculation_id: str,
    request: ManualExtentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create extent from manually digitized polygon
    """
    try:
        service = UserGroupAnalysisService(db)
        extent = await service.create_manual_extent(
            calculation_id=calculation_id,
            geometry=request.geometry,
            user_id=current_user.id
        )
        return ExtentResponse(
            extent_id=extent.id,
            message="Manual extent created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating manual extent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create manual extent")


@router.post("/calculations/{calculation_id}/user-group/auto-buffer", response_model=ExtentResponse)
async def create_auto_buffer_extent(
    calculation_id: str,
    buffer_distance: int = Query(default=1000, ge=100, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create auto-buffer extent (default 1000m from forest boundary)
    """
    try:
        service = UserGroupAnalysisService(db)
        extent = await service.create_auto_buffer(
            calculation_id=calculation_id,
            buffer_distance_m=buffer_distance,
            user_id=current_user.id
        )
        return ExtentResponse(
            extent_id=extent.id,
            message=f"Auto-buffer extent created ({buffer_distance}m)"
        )
    except Exception as e:
        logger.error(f"Error creating auto-buffer extent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create auto-buffer extent")


@router.post("/calculations/{calculation_id}/user-group/analyze", response_model=AnalysisResponse)
async def analyze_user_group(
    calculation_id: str,
    extent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run spatial analysis: clip buildings/settlements, calculate statistics
    """
    try:
        service = UserGroupAnalysisService(db)
        results = await service.analyze_user_group(
            calculation_id=calculation_id,
            extent_id=extent_id
        )

        total_buildings = sum(r.get('building_count', 0) for r in results)

        return AnalysisResponse(
            message="Analysis completed successfully",
            settlements_analyzed=len(results),
            total_buildings=total_buildings
        )
    except Exception as e:
        logger.error(f"Error analyzing user group: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/calculations/{calculation_id}/user-group/results", response_model=UserGroupResults)
async def get_user_group_results(
    calculation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get analysis results for visualization
    """
    try:
        service = UserGroupAnalysisService(db)
        results = await service.get_results(calculation_id)

        if not results:
            raise HTTPException(status_code=404, detail="No user group analysis found for this calculation")

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user group results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get results")


@router.get("/calculations/{calculation_id}/user-group/poi", response_model=POIResponse)
async def get_poi_layers(
    calculation_id: str,
    layer_type: str = Query(default="all", regex="^(all|poi|education|health|rivers)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get optional POI layers for map visualization
    """
    try:
        service = UserGroupAnalysisService(db)
        poi_data = await service.get_poi_layers(calculation_id, layer_type)
        return poi_data
    except Exception as e:
        logger.error(f"Error getting POI layers: {e}")
        raise HTTPException(status_code=500, detail="Failed to get POI layers")


@router.delete("/calculations/{calculation_id}/user-group")
async def delete_user_group_extent(
    calculation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete user group extent and all related analysis data
    """
    try:
        service = UserGroupAnalysisService(db)
        deleted_count = service._delete_existing_extents(calculation_id)

        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="No user group extent found")

        return {
            "message": f"Successfully deleted user group extent and analysis data",
            "deleted_extents": deleted_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user group extent: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user group extent")


@router.get("/calculations/{calculation_id}/user-group/land-cover", response_model=LandCoverAnalysisResponse)
async def analyze_land_cover(
    calculation_id: str,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze land cover and biomass for user group extent

    This endpoint performs comprehensive spatial analysis including:
    - Land use classification (ESA World Cover 10m)
    - Biomass estimation (AGB 2022 Nepal 100m)
    - Community forest overlap exclusion
    - Timber volume calculation

    **Caching:** Results are automatically cached in database for fast retrieval.
    Use `force_refresh=true` to re-run the analysis.

    **Prerequisites:**
    1. Community forest boundary must be uploaded (Analysis tab)
    2. User group extent must be created (Forest User Map tab)

    **Returns:**
    - Area summary (user group, forest overlap, net analysis area)
    - Land cover breakdown by class
    - Biomass and volume statistics
    """
    try:
        service = UserGroupAnalysisService(db)
        results = await service.analyze_land_cover(calculation_id, force_refresh=force_refresh)
        return results
    except ValueError as e:
        # User-friendly error messages
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing land cover: {e}")
        raise HTTPException(status_code=500, detail=f"Land cover analysis failed: {str(e)}")


@router.get("/user-group/{extent_id}/export")
async def export_user_group_map(
    extent_id: int,
    format: str = Query(default="pdf", regex="^(pdf|gpkg|geojson|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export user group map and statistics
    """
    try:
        service = UserGroupAnalysisService(db)

        if format == "pdf":
            file_path = await service.generate_pdf_report(extent_id)
            media_type = "application/pdf"
        elif format == "gpkg":
            file_path = await service.export_to_gpkg(extent_id)
            media_type = "application/geopackage+sqlite3"
        elif format == "geojson":
            file_path = await service.export_to_geojson(extent_id)
            media_type = "application/geo+json"
        elif format == "csv":
            file_path = await service.export_to_csv(extent_id)
            media_type = "text/csv"
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=f"user_group_map.{format}"
        )
    except Exception as e:
        logger.error(f"Error exporting user group map: {e}")
        raise HTTPException(status_code=500, detail="Export failed")
