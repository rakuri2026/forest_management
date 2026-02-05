"""
Inventory API endpoints
Handles tree inventory upload, validation, and processing
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from uuid import UUID
import pandas as pd
import numpy as np
import io

from ..core.database import get_db
from ..models.user import User
from ..models.inventory import (
    InventoryCalculation,
    InventoryTree,
    TreeSpeciesCoefficient
)
from ..schemas.inventory import (
    TreeSpeciesCoefficientResponse,
    ValidationReportResponse,
    InventoryCalculationResponse,
    InventoryTreeResponse,
    InventoryTreesListResponse,
    InventorySummaryResponse,
    MyInventoriesResponse
)
from ..utils.auth import get_current_active_user
from ..services.inventory_validator import InventoryValidator
from ..services.inventory import InventoryService


router = APIRouter()


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to Python native types for JSON serialization
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    else:
        return obj


@router.get("/species", response_model=List[TreeSpeciesCoefficientResponse])
async def list_species(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all available tree species with coefficients
    """
    species = db.query(TreeSpeciesCoefficient).filter(
        TreeSpeciesCoefficient.is_active == True
    ).order_by(TreeSpeciesCoefficient.scientific_name).all()

    return species


@router.get("/template")
async def download_template(
    current_user: User = Depends(get_current_active_user)
):
    """
    Download CSV template for tree inventory
    """
    # Read template file
    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'templates',
        'TreeInventory_Template.csv'
    )

    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template file not found")

    with open(template_path, 'r') as f:
        content = f.read()

    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=TreeInventory_Template.csv"
        }
    )


@router.post("/upload", response_model=dict)
async def upload_inventory(
    file: UploadFile = File(...),
    calculation_id: Optional[str] = Form(None),
    grid_spacing_meters: float = Form(20.0),
    projection_epsg: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload and validate tree inventory CSV file

    Returns validation report
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    # Read CSV file
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading CSV file: {str(e)}"
        )

    # Validate data
    validator = InventoryValidator(db)
    validation_report = await validator.validate_inventory_file(
        df,
        user_specified_crs=projection_epsg
    )

    # If validation passed, create inventory calculation record
    if validation_report['summary'].get('ready_for_processing'):
        # Determine CRS
        detected_crs = validation_report['data_detection'].get('crs', {}).get('epsg')
        if detected_crs == 'UNKNOWN':
            detected_crs = projection_epsg or 4326
        elif isinstance(detected_crs, str):
            detected_crs = 4326

        # Determine projection CRS for grid creation
        # If user specified a UTM zone, use it
        # Otherwise, auto-detect UTM zone based on data longitude
        if projection_epsg and projection_epsg >= 32600:
            # User specified UTM zone
            final_projection_epsg = projection_epsg
        elif detected_crs == 4326 or detected_crs == 'WGS84':
            # Data is in lat/lon - auto-detect UTM zone
            # Get longitude column to determine UTM zone
            coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
            x_col = coord_cols.get('x')
            if x_col and x_col in df.columns:
                # Calculate mean longitude (convert to Python float)
                mean_lon = float(df[x_col].mean())

                # Nepal is in Northern Hemisphere
                # UTM Zone 44N: 78°E to 84°E (EPSG:32644) - Western/Central Nepal
                # UTM Zone 45N: 84°E to 90°E (EPSG:32645) - Eastern Nepal
                if mean_lon < 84.0:
                    final_projection_epsg = 32644  # UTM 44N
                    validation_report['info'] = validation_report.get('info', [])
                    validation_report['info'].append({
                        'type': 'auto_utm_detection',
                        'message': f'Auto-detected UTM Zone 44N (EPSG:32644) based on longitude {mean_lon:.2f}°E (< 84°E)'
                    })
                else:
                    final_projection_epsg = 32645  # UTM 45N
                    validation_report['info'] = validation_report.get('info', [])
                    validation_report['info'].append({
                        'type': 'auto_utm_detection',
                        'message': f'Auto-detected UTM Zone 45N (EPSG:32645) based on longitude {mean_lon:.2f}°E (≥ 84°E)'
                    })
            else:
                # Default to UTM 45N for Nepal
                final_projection_epsg = 32645
        else:
            # Use detected/specified CRS
            final_projection_epsg = projection_epsg or detected_crs

        inventory = InventoryCalculation(
            user_id=current_user.id,
            calculation_id=UUID(calculation_id) if calculation_id else None,
            uploaded_filename=file.filename,
            grid_spacing_meters=grid_spacing_meters,
            projection_epsg=final_projection_epsg,
            status='validated'
        )
        db.add(inventory)
        db.commit()
        db.refresh(inventory)

        validation_report['inventory_id'] = str(inventory.id)
        validation_report['next_step'] = 'POST /api/inventory/{inventory_id}/process'

    # Convert numpy types to native Python types for JSON serialization
    return convert_numpy_types(validation_report)


@router.post("/{inventory_id}/process", response_model=InventoryCalculationResponse)
async def process_inventory(
    inventory_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process validated inventory: calculate volumes and store trees

    Requires re-uploading the CSV file for processing
    """
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    if inventory.status not in ['validated', 'failed']:
        raise HTTPException(
            status_code=400,
            detail=f"Inventory cannot be processed. Current status: {inventory.status}"
        )

    # Read CSV file
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading CSV file: {str(e)}"
        )

    # Process with simplified service (no GDAL required)
    service = InventoryService(db)

    try:
        result = await service.process_inventory_simple(
            inventory_id=inventory_id,
            df=df,
            grid_spacing_meters=inventory.grid_spacing_meters
        )

        return inventory

    except Exception as e:
        inventory.status = 'failed'
        inventory.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/{inventory_id}/status", response_model=InventoryCalculationResponse)
async def get_inventory_status(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get processing status of inventory calculation
    """
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    return inventory


@router.get("/{inventory_id}/summary", response_model=InventorySummaryResponse)
async def get_inventory_summary(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get inventory summary statistics
    """
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # Get species distribution
    from sqlalchemy import text
    species_query = db.execute(
        text("""
        SELECT species, COUNT(*) as count
        FROM public.inventory_trees
        WHERE inventory_calculation_id = :inventory_id
        GROUP BY species
        ORDER BY count DESC
        """),
        {"inventory_id": str(inventory_id)}
    )
    species_distribution = {row[0]: row[1] for row in species_query.fetchall()}

    # Get DBH classes
    dbh_query = db.execute(
        text("""
        SELECT
            CASE
                WHEN dia_cm < 10 THEN 'Seedling (<10cm)'
                WHEN dia_cm < 20 THEN 'Sapling (10-20cm)'
                WHEN dia_cm < 40 THEN 'Pole (20-40cm)'
                ELSE 'Mature (>40cm)'
            END as dbh_class,
            COUNT(*) as count
        FROM public.inventory_trees
        WHERE inventory_calculation_id = :inventory_id
        GROUP BY dbh_class
        """),
        {"inventory_id": str(inventory_id)}
    )
    dbh_classes = {row[0]: row[1] for row in dbh_query.fetchall()}

    return {
        'inventory_id': inventory.id,
        'total_trees': inventory.total_trees or 0,
        'mother_trees_count': inventory.mother_trees_count or 0,
        'felling_trees_count': inventory.felling_trees_count or 0,
        'seedling_count': inventory.seedling_count or 0,
        'total_volume_m3': inventory.total_volume_m3 or 0,
        'total_net_volume_m3': inventory.total_net_volume_m3 or 0,
        'total_net_volume_cft': inventory.total_net_volume_cft or 0,
        'total_firewood_m3': inventory.total_firewood_m3 or 0,
        'total_firewood_chatta': inventory.total_firewood_chatta or 0,
        'species_distribution': species_distribution,
        'dbh_classes': dbh_classes,
        'status': inventory.status,
        'created_at': inventory.created_at,
        'completed_at': inventory.completed_at,
        'processing_time_seconds': inventory.processing_time_seconds
    }


@router.get("/{inventory_id}/trees", response_model=InventoryTreesListResponse)
async def list_inventory_trees(
    inventory_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    remark: Optional[str] = Query(None, description="Filter by remark (Mother Tree, Felling Tree, Seedling)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List trees in inventory with pagination
    """
    # Verify ownership
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # Build query
    query = db.query(InventoryTree).filter(
        InventoryTree.inventory_calculation_id == inventory_id
    )

    # Apply filters
    if remark:
        query = query.filter(InventoryTree.remark == remark)

    # Get total count
    total_count = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    trees = query.offset(offset).limit(page_size).all()

    # Convert to response format (with lon/lat)
    tree_responses = []
    for tree in trees:
        # Extract coordinates from geography
        from sqlalchemy import text
        result = db.execute(
            text("SELECT ST_X(location::geometry), ST_Y(location::geometry) FROM public.inventory_trees WHERE id = :id"),
            {"id": tree.id}
        ).first()

        lon, lat = result[0], result[1]

        tree_responses.append(InventoryTreeResponse(
            id=tree.id,
            species=tree.species,
            local_name=tree.local_name,
            dia_cm=tree.dia_cm,
            height_m=tree.height_m,
            tree_class=tree.tree_class,
            stem_volume=tree.stem_volume,
            branch_volume=tree.branch_volume,
            tree_volume=tree.tree_volume,
            gross_volume=tree.gross_volume,
            net_volume=tree.net_volume,
            net_volume_cft=tree.net_volume_cft,
            firewood_m3=tree.firewood_m3,
            firewood_chatta=tree.firewood_chatta,
            remark=tree.remark,
            grid_cell_id=tree.grid_cell_id,
            longitude=lon,
            latitude=lat
        ))

    has_more = (offset + len(trees)) < total_count

    return {
        'trees': tree_responses,
        'total_count': total_count,
        'page': page,
        'page_size': page_size,
        'has_more': has_more
    }


@router.get("/{inventory_id}/export")
async def export_inventory(
    inventory_id: UUID,
    format: str = Query('csv', regex="^(csv|geojson)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export inventory results (CSV or GeoJSON)
    """
    # Verify ownership
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    # Get inventory service
    service = InventoryService(db)

    try:
        content, filename = await service.export_inventory(inventory_id, format)

        media_type = "text/csv" if format == "csv" else "application/geo+json"

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{inventory_id}")
async def delete_inventory(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete inventory calculation and all associated trees
    """
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    db.delete(inventory)
    db.commit()

    return {"message": "Inventory deleted successfully"}


@router.get("/my-inventories", response_model=MyInventoriesResponse)
async def list_my_inventories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all inventories for current user
    """
    inventories = db.query(InventoryCalculation).filter(
        InventoryCalculation.user_id == current_user.id
    ).order_by(InventoryCalculation.created_at.desc()).all()

    return {
        'inventories': inventories,
        'total_count': len(inventories)
    }
