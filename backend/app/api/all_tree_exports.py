"""
All Tree Export API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import os
import threading
import logging
from datetime import datetime

from ..core.database import get_db
from ..core.config import settings
from ..models.user import User
from ..models.calculation import Calculation
from ..models.all_tree_export import AllTreeExport
from ..schemas.all_tree_export import (
    GenerateAllTreesRequest,
    AllTreeExportResponse,
    AllTreeExportListResponse,
)
from ..utils.auth import get_current_active_user
from ..services.tree_distribution import generate_full_extent_trees


router = APIRouter()


def background_all_tree_generation(
    export_id: UUID,
    calculation_id: UUID,
    config: dict,
    db_url: str,
):
    """
    Background task for all-tree generation
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        logger.info(f"Background task started for export {export_id}")
        export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
        if not export:
            logger.warning(f"Export {export_id} not found")
            return

        def update_progress(percent: int, step: str):
            export.progress_percent = percent
            export.current_step = step
            db.commit()

        update_progress(5, "Initializing")
        logger.info(f"Export {export_id}: Starting generation")
        result = generate_full_extent_trees(
            calculation_id=calculation_id,
            db=db,
            config=config,
            progress_callback=update_progress,
        )

        stats = result['statistics']

        export.status = "completed"
        export.total_trees = stats['total_trees']
        export.area_hectares = stats['area_hectares']
        export.trees_per_hectare = stats['trees_per_hectare']
        export.min_dbh_cm = stats['min_dbh_cm']
        export.max_dbh_cm = stats['max_dbh_cm']
        export.min_height_m = stats['min_height_m']
        export.max_height_m = stats['max_height_m']

        export.gpkg_filename = result.get('gpkg_filename')
        export.gpkg_size_mb = result.get('gpkg_size_mb')
        export.gpkg_path = result.get('gpkg_filepath')
        # Excel and CSV exports are no longer generated

        export.processing_time_seconds = result['processing_time_seconds']
        export.completed_at = datetime.utcnow()
        export.progress_percent = 100
        export.current_step = "Complete"

        # Store statistics in algorithm_config for frontend display
        config_with_stats = dict(export.algorithm_config or {})
        config_with_stats['statistics'] = stats
        export.algorithm_config = config_with_stats

        db.commit()

    except Exception as e:
        import traceback
        logger.error(f"Background task failed for export {export_id}: {e}\n{traceback.format_exc()}")
        export.status = "failed"
        export.error_message = str(e)
        export.progress_percent = 0
        export.current_step = "Failed"
        db.commit()

    finally:
        db.close()
        engine.dispose()
        logger.info(f"Background task finished for export {export_id}")


@router.post("/calculations/{calculation_id}/generate-all-trees-sync", response_model=AllTreeExportResponse)
async def generate_all_trees_sync(
    calculation_id: UUID,
    request: GenerateAllTreesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    SYNCHRONOUS version for testing — blocks until generation completes.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")

    if not calculation.boundary_geom:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Calculation has no boundary geometry")

    config = request.config.model_dump() if request.config else {}

    export = AllTreeExport(
        calculation_id=calculation_id,
        user_id=current_user.id,
        model_type="full_extent",
        model_version="v1.0",
        algorithm_config=config,
        status="processing",
        progress_percent=0,
        current_step="Starting",
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    def update_progress(pct, step):
        export.progress_percent = pct
        export.current_step = step
        db.commit()

    from ..services.tree_distribution import generate_full_extent_trees
    result = generate_full_extent_trees(
        calculation_id=calculation_id,
        db=db,
        config=config,
        progress_callback=update_progress,
    )

    stats = result['statistics']
    export.status = "completed"
    export.total_trees = stats['total_trees']
    export.area_hectares = stats['area_hectares']
    export.trees_per_hectare = stats['trees_per_hectare']
    export.min_dbh_cm = stats['min_dbh_cm']
    export.max_dbh_cm = stats['max_dbh_cm']
    export.min_height_m = stats['min_height_m']
    export.max_height_m = stats['max_height_m']
    export.gpkg_filename = result.get('gpkg_filename')
    export.gpkg_size_mb = result.get('gpkg_size_mb')
    export.gpkg_path = result.get('gpkg_filepath')
    export.excel_filename = result.get('excel_filename')
    export.excel_size_mb = result.get('excel_size_mb')
    export.excel_path = result.get('excel_filepath')
    export.csv_filename = result.get('csv_filename')
    export.csv_size_mb = result.get('csv_size_mb')
    export.processing_time_seconds = result['processing_time_seconds']
    export.completed_at = datetime.utcnow()
    export.progress_percent = 100
    export.current_step = "Complete"
    db.commit()

    return export


@router.post("/calculations/{calculation_id}/generate-all-trees", response_model=AllTreeExportResponse)
async def generate_all_trees(
    calculation_id: UUID,
    request: GenerateAllTreesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate ALL trees within the forest boundary from canopy height raster.

    Unlike the regular tree model (which only creates trees in sample plots),
    this processes every valid pixel in the forest boundary.

    **Output:** GPKG + Excel (flat format: 1 row = 1 tree) + CSV
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")

    if calculation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if not calculation.boundary_geom:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Calculation has no boundary geometry")

    result_data = calculation.result_data or {}
    if not result_data.get('potential_species'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no species data. Run analysis first."
        )

    existing = db.query(AllTreeExport).filter(
        AllTreeExport.calculation_id == calculation_id,
        AllTreeExport.status == "processing",
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"All-tree generation already in progress (ID: {existing.id})",
        )

    config = request.config.model_dump() if request.config else {}

    export = AllTreeExport(
        calculation_id=calculation_id,
        user_id=current_user.id,
        model_type="full_extent",
        model_version="v1.0",
        algorithm_config=config,
        status="processing",
        progress_percent=0,
        current_step="Queued",
    )

    db.add(export)
    db.commit()
    db.refresh(export)

    thread = threading.Thread(
        target=background_all_tree_generation,
        args=(export.id, calculation_id, config, settings.DATABASE_URL),
        daemon=True,
    )
    thread.start()

    return export


@router.get("/all-tree-exports/{export_id}", response_model=AllTreeExportResponse)
async def get_all_tree_export(
    export_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get all-tree export status and statistics (polling)"""
    export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="All-tree export not found")

    if export.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return export


@router.get("/calculations/{calculation_id}/all-tree-exports", response_model=AllTreeExportListResponse)
async def list_all_tree_exports(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all all-tree exports for a calculation"""
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found")

    if calculation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    exports = (
        db.query(AllTreeExport)
        .filter(AllTreeExport.calculation_id == calculation_id)
        .order_by(AllTreeExport.created_at.desc())
        .all()
    )

    return {"exports": exports, "total_count": len(exports)}


def _cleanup_after_download(export_id: UUID, gpkg_path: str, db_url: str):
    """Delete GPKG file and DB record after successful download."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    logger = logging.getLogger(__name__)
    try:
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
            if export:
                # Delete file
                if gpkg_path and os.path.exists(gpkg_path):
                    os.remove(gpkg_path)
                    logger.info(f"Deleted GPKG after download: {gpkg_path}")
                # Delete DB record
                db.delete(export)
                db.commit()
                logger.info(f"Deleted all-tree export record {export_id} after download")
        finally:
            db.close()
            engine.dispose()
    except Exception as e:
        logger.error(f"Cleanup after download failed for {export_id}: {e}")


@router.get("/all-tree-exports/{export_id}/download")
async def download_all_tree_gpkg(
    export_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Download all-tree export GPKG file. File and DB record are auto-deleted after download."""
    export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    if export.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    if export.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Export not completed. Status: {export.status}")

    if not export.gpkg_path or not os.path.exists(export.gpkg_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GPKG file not found")

    calc = db.query(Calculation).filter(Calculation.id == export.calculation_id).first()
    forest_name = calc.forest_name if calc and calc.forest_name else "forest"
    from app.utils.file_export import build_disposition
    _, disposition = build_disposition(forest_name, "AllTrees", "GPKG", "gpkg")

    gpkg_path = export.gpkg_path
    cleanup = BackgroundTask(_cleanup_after_download, export_id, gpkg_path, settings.DATABASE_URL)

    return FileResponse(
        path=gpkg_path,
        filename=export.gpkg_filename,
        media_type="application/geopackage+sqlite3",
        headers={"Content-Disposition": disposition},
        background=cleanup,
    )


@router.delete("/all-tree-exports/{export_id}")
async def delete_all_tree_export(
    export_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete all-tree export and associated files"""
    export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    if export.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    for path_attr in ['gpkg_path', 'excel_path', 'csv_path']:
        filepath = getattr(export, path_attr, None)
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Warning: Could not delete {filepath}: {e}")

    db.delete(export)
    db.commit()

    return {"success": True, "message": "All-tree export deleted successfully"}


@router.post("/all-tree-exports/{export_id}/extract-sample-plots")
async def extract_all_tree_sample_plots(
    export_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Extract trees from the all-tree GPKG that fall within sample plot buffers.
    Returns a GPKG with only the trees inside sample plots, annotated with plot_number.
    """
    export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if export.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    if export.status != "completed" or not export.gpkg_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Export not completed or GPKG missing")

    if not os.path.exists(export.gpkg_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GPKG file not found on disk")

    from ..services.tree_distribution import extract_sample_plot_trees
    result = extract_sample_plot_trees(
        all_tree_gpkg_path=export.gpkg_path,
        calculation_id=export.calculation_id,
        db=db,
        output_dir=os.path.join(os.path.dirname(__file__), '..', '..', 'exports'),
        output_filename=f"sample_plots_{export_id}.gpkg",
    )

    return result


@router.get("/all-tree-exports/{export_id}/sample-plot-gpkg")
async def download_all_tree_sample_plots(
    export_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Download the sample-plot extracted GPKG derived from the all-tree export.
    """
    export = db.query(AllTreeExport).filter(AllTreeExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if export.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    if export.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Export not completed")

    filename = f"sample_plots_{export_id}.gpkg"
    filepath = os.path.join(os.path.dirname(__file__), '..', '..', 'exports', filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample plot GPKG not found. Run extract-sample-plots first.")

    calc = db.query(Calculation).filter(Calculation.id == export.calculation_id).first()
    forest_name = calc.forest_name if calc and calc.forest_name else "forest"
    from app.utils.file_export import build_disposition
    _, disposition = build_disposition(forest_name, "AllTrees_SamplePlots", "GPKG", "gpkg")
    download_name = f"{forest_name}_AllTrees_SamplePlots_{datetime.now().strftime('%Y%m%d')}.gpkg"

    return FileResponse(
        path=filepath,
        filename=download_name,
        media_type="application/geopackage+sqlite3",
        headers={"Content-Disposition": disposition},
    )


@router.post("/exports/cleanup")
async def cleanup_old_exports(
    retention_days: int = 7,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Delete old export files (GPKG, Excel, CSV) older than retention_days.
    Also cleans up orphaned files with no matching DB record.
    Only super_admin users can trigger this.
    """
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can trigger export cleanup",
        )

    from ..services.export_cleanup import run_full_cleanup
    export_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'exports')

    results = run_full_cleanup(db, export_dir, retention_days)

    total_cleaned = (
        results["old_tree_exports_deleted"]
        + results["old_tree_models_deleted"]
        + results["orphan_files_deleted"]
        + results["inventory_files_deleted"]
    )

    return {
        "success": True,
        "message": f"Cleanup complete: {total_cleaned} items removed",
        "details": results,
    }
