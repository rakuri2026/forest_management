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
from ..utils.column_mapper import ColumnMapper
from ..utils.column_mapping_helpers import (
    merge_auto_mapping_with_preferences,
    save_user_column_preferences,
    validate_and_prepare_dataframe
)

import logging

logger = logging.getLogger(__name__)


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


@router.post("/preview-mapping")
async def preview_column_mapping(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Preview automatic column mapping for uploaded CSV file.

    Analyzes the CSV column names and returns:
    - Automatic mapping suggestions
    - Confidence scores
    - Sample data preview (first 5 rows)
    - Missing required columns
    - Duplicate mappings
    - User's saved preferences (if any)

    Use this endpoint BEFORE uploading inventory data to confirm column mapping.
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    # Read CSV file (first 10 rows for preview)
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), nrows=10)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading CSV file: {str(e)}"
        )

    if len(df) == 0:
        raise HTTPException(
            status_code=400,
            detail="CSV file is empty"
        )

    # Get automatic mapping merged with user preferences
    try:
        mapping_result = merge_auto_mapping_with_preferences(
            db, current_user.id, df.columns.tolist()
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing columns: {str(e)}"
        )

    # Prepare sample data (first 5 rows)
    sample_data = df.head(5).replace({np.nan: None}).to_dict('records')

    # Determine if user input is needed
    needs_user_input = (
        len(mapping_result["missing_required"]) > 0 or
        len(mapping_result["duplicates"]) > 0 or
        any(score < 85 for score in mapping_result["confidence"].values())
    )

    response = {
        "success": True,
        "filename": file.filename,
        "total_rows": len(df),
        "csv_columns": df.columns.tolist(),
        "sample_data": sample_data,
        "mapping": mapping_result["mapped"],
        "confidence": mapping_result["confidence"],
        "unmapped_columns": mapping_result["unmapped"],
        "suggestions": mapping_result["suggestions"],
        "missing_required": mapping_result["missing_required"],
        "duplicates": mapping_result["duplicates"],
        "needs_user_input": needs_user_input,
        "required_columns": ["species", "dia_cm", "height_m", "LONGITUDE", "LATITUDE"],
        "optional_columns": ["class"]
    }

    return convert_numpy_types(response)


@router.post("/confirm-mapping")
async def confirm_and_upload_with_mapping(
    file: UploadFile = File(...),
    mapping: str = Form(...),  # JSON string of {csv_col: std_col}
    save_preference: bool = Form(False),
    calculation_id: Optional[str] = Form(None),
    grid_spacing_meters: float = Form(20.0),
    projection_epsg: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Confirm column mapping and upload inventory CSV.

    This endpoint:
    1. Validates the confirmed mapping
    2. Applies column renaming to the uploaded CSV
    3. Saves user preferences (if requested)
    4. Processes the inventory upload (same as /upload endpoint)

    Args:
        file: CSV file to upload
        mapping: JSON string of column mapping {csv_col: standard_col}
        save_preference: Whether to save this mapping for future uploads
        calculation_id: Optional link to boundary calculation
        grid_spacing_meters: Grid spacing for plot creation
        projection_epsg: Optional projection EPSG code
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported"
        )

    # Parse mapping JSON
    import json
    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid mapping JSON format"
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

    # Validate and apply mapping
    try:
        mapper = ColumnMapper()
        validation = mapper.validate_mapping(mapping_dict)

        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "warnings": validation.get("warnings", [])
            }

        # Apply mapping to dataframe
        result = mapper.apply_mapping(df, mapping_dict)
        df_renamed = result["df"]

        logger.info(f"Applied column mapping. Renamed columns: {result['renamed_columns']}")
        logger.info(f"Preserved columns: {result['preserved_columns']}")

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error applying column mapping: {str(e)}"
        )

    # Save user preferences if requested
    if save_preference:
        try:
            save_user_column_preferences(
                db, current_user.id, mapping_dict
            )
            logger.info(f"Saved column mapping preferences for user {current_user.id}")
        except Exception as e:
            logger.warning(f"Failed to save user preferences: {str(e)}")
            # Don't fail the upload if preference saving fails

    # Store column mapping in calculation metadata
    column_mapping_metadata = {
        "original_columns": list(mapping_dict.keys()),
        "mapped": mapping_dict,
        "confidence": {},  # Will be populated if we have confidence data
        "preserved_columns": result["preserved_columns"]
    }

    # Now proceed with normal inventory upload validation
    # (Re-use existing validation logic from /upload endpoint)

    # Check if tree mapping already exists for this calculation
    if calculation_id:
        existing_mapping = db.query(InventoryCalculation).filter(
            InventoryCalculation.calculation_id == UUID(calculation_id),
            InventoryCalculation.user_id == current_user.id
        ).first()

        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail="Tree mapping already exists for this calculation. Please delete the existing tree mapping first."
            )

    # Validate data with renamed columns
    validator = InventoryValidator(db)
    validation_report = await validator.validate_inventory_file(
        df_renamed,
        user_specified_crs=projection_epsg
    )

    # Check boundary if calculation_id is provided
    boundary_check_result = None
    if calculation_id and validation_report['summary'].get('ready_for_processing'):
        try:
            from app.services.boundary_validator import validate_inventory_boundary

            # Get coordinate columns
            coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
            x_col = coord_cols.get('x')
            y_col = coord_cols.get('y')

            if x_col and y_col and x_col in df_renamed.columns and y_col in df_renamed.columns:
                # Extract tree points (lon, lat, row_number)
                tree_points = [
                    (float(row[x_col]), float(row[y_col]), idx + 1)
                    for idx, row in df_renamed.iterrows()
                    if pd.notna(row[x_col]) and pd.notna(row[y_col])
                ]

                # Validate boundary
                boundary_check_result = validate_inventory_boundary(
                    db,
                    UUID(calculation_id),
                    tree_points,
                    tolerance_percent=5.0
                )

                # Add boundary check to validation report
                validation_report['boundary_check'] = {
                    'total_points': boundary_check_result['total_points'],
                    'out_of_boundary_count': boundary_check_result['out_of_boundary_count'],
                    'out_of_boundary_percentage': boundary_check_result['out_of_boundary_percentage'],
                    'within_tolerance': boundary_check_result['within_tolerance'],
                    'needs_correction': boundary_check_result['needs_correction']
                }

                # Generate correction preview if corrections are needed
                if boundary_check_result['needs_correction']:
                    from app.services.boundary_corrector import generate_correction_preview

                    species_col = validation_report['data_detection'].get('species_column', 'Species')

                    corrections_preview = generate_correction_preview(
                        df_renamed,
                        boundary_check_result['boundary_wkt'],
                        boundary_check_result['out_of_boundary_points'],
                        x_col,
                        y_col,
                        species_col
                    )

                    validation_report['boundary_check']['corrections'] = corrections_preview['corrections']
                    validation_report['boundary_check']['correction_summary'] = corrections_preview['summary']

                # If too many points outside boundary, fail validation
                if not boundary_check_result['within_tolerance']:
                    validation_report['summary']['ready_for_processing'] = False
                    validation_report['errors'].append({
                        'type': 'boundary_error',
                        'severity': 'error',
                        'message': boundary_check_result.get('error_message', 'Too many trees outside boundary')
                    })

        except Exception as e:
            # Log boundary check error but don't fail upload
            import logging
            logging.error(f"Boundary check failed: {str(e)}")
            validation_report['warnings'].append({
                'type': 'boundary_check_error',
                'severity': 'warning',
                'message': f'Could not validate boundary: {str(e)}'
            })

    # If validation passed, create inventory calculation record
    if validation_report['summary'].get('ready_for_processing'):
        # Determine CRS
        detected_crs = validation_report['data_detection'].get('crs', {}).get('epsg')
        if detected_crs == 'UNKNOWN':
            detected_crs = projection_epsg or 4326
        elif isinstance(detected_crs, str):
            detected_crs = 4326

        # Determine projection CRS for grid creation
        if projection_epsg and projection_epsg >= 32600:
            final_projection_epsg = projection_epsg
        elif detected_crs == 4326 or detected_crs == 'WGS84':
            # Data is in lat/lon - auto-detect UTM zone
            coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
            x_col = coord_cols.get('x')
            if x_col and x_col in df_renamed.columns:
                mean_lon = float(df_renamed[x_col].mean())

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
                final_projection_epsg = 32645
        else:
            final_projection_epsg = projection_epsg or detected_crs

        inventory = InventoryCalculation(
            user_id=current_user.id,
            calculation_id=UUID(calculation_id) if calculation_id else None,
            uploaded_filename=file.filename,
            grid_spacing_meters=grid_spacing_meters,
            projection_epsg=final_projection_epsg,
            column_mapping=mapping_dict,  # Store column mapping for processing
            status='validated'
        )
        db.add(inventory)

        try:
            db.commit()
            db.refresh(inventory)
        except Exception as e:
            db.rollback()
            if 'uq_inventory_calculations_calculation_id' in str(e) or 'duplicate key value' in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Tree mapping already exists for this calculation. Please delete the existing tree mapping first."
                )
            raise

        validation_report['inventory_id'] = str(inventory.id)
        validation_report['next_step'] = 'POST /api/inventory/{inventory_id}/process'

    # Add column mapping info to report
    validation_report['column_mapping'] = column_mapping_metadata
    validation_report['mapping_applied'] = True

    return convert_numpy_types(validation_report)


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
    Upload and validate tree mapping CSV file

    Returns validation report
    """
    # Check if tree mapping already exists for this calculation
    if calculation_id:
        existing_mapping = db.query(InventoryCalculation).filter(
            InventoryCalculation.calculation_id == UUID(calculation_id),
            InventoryCalculation.user_id == current_user.id
        ).first()

        if existing_mapping:
            raise HTTPException(
                status_code=400,
                detail="Tree mapping already exists for this calculation. Please delete the existing tree mapping first."
            )

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

    # Check boundary if calculation_id is provided
    boundary_check_result = None
    if calculation_id and validation_report['summary'].get('ready_for_processing'):
        try:
            from app.services.boundary_validator import validate_inventory_boundary

            # Get coordinate columns
            coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
            x_col = coord_cols.get('x')
            y_col = coord_cols.get('y')

            if x_col and y_col and x_col in df.columns and y_col in df.columns:
                # Extract tree points (lon, lat, row_number)
                tree_points = [
                    (float(row[x_col]), float(row[y_col]), idx + 1)
                    for idx, row in df.iterrows()
                    if pd.notna(row[x_col]) and pd.notna(row[y_col])
                ]

                # Validate boundary
                boundary_check_result = validate_inventory_boundary(
                    db,
                    UUID(calculation_id),
                    tree_points,
                    tolerance_percent=5.0
                )

                # Add boundary check to validation report
                validation_report['boundary_check'] = {
                    'total_points': boundary_check_result['total_points'],
                    'out_of_boundary_count': boundary_check_result['out_of_boundary_count'],
                    'out_of_boundary_percentage': boundary_check_result['out_of_boundary_percentage'],
                    'within_tolerance': boundary_check_result['within_tolerance'],
                    'needs_correction': boundary_check_result['needs_correction']
                }

                # Generate correction preview if corrections are needed
                if boundary_check_result['needs_correction']:
                    from app.services.boundary_corrector import generate_correction_preview

                    species_col = validation_report['data_detection'].get('species_column', 'Species')

                    corrections_preview = generate_correction_preview(
                        df,
                        boundary_check_result['boundary_wkt'],
                        boundary_check_result['out_of_boundary_points'],
                        x_col,
                        y_col,
                        species_col
                    )

                    validation_report['boundary_check']['corrections'] = corrections_preview['corrections']
                    validation_report['boundary_check']['correction_summary'] = corrections_preview['summary']

                # If too many points outside boundary, fail validation
                if not boundary_check_result['within_tolerance']:
                    validation_report['summary']['ready_for_processing'] = False
                    validation_report['errors'].append({
                        'type': 'boundary_error',
                        'severity': 'error',
                        'message': boundary_check_result.get('error_message', 'Too many trees outside boundary')
                    })

        except Exception as e:
            # Log boundary check error but don't fail upload
            import logging
            logging.error(f"Boundary check failed: {str(e)}")
            validation_report['warnings'].append({
                'type': 'boundary_check_error',
                'severity': 'warning',
                'message': f'Could not validate boundary: {str(e)}'
            })

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

        try:
            db.commit()
            db.refresh(inventory)
        except Exception as e:
            db.rollback()
            # Check if it's a unique constraint violation
            if 'uq_inventory_calculations_calculation_id' in str(e) or 'duplicate key value' in str(e):
                raise HTTPException(
                    status_code=400,
                    detail="Tree mapping already exists for this calculation. Please delete the existing tree mapping first."
                )
            # Re-raise other errors
            raise

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
    import logging
    logger = logging.getLogger(__name__)

    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    if inventory.status not in ['validated', 'failed', 'corrections_applied']:
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

    # Apply column mapping if it was saved during upload
    if inventory.column_mapping:
        logger.info(f"Applying saved column mapping: {inventory.column_mapping}")
        try:
            from ..utils.column_mapper import ColumnMapper
            mapper = ColumnMapper()
            result = mapper.apply_mapping(df, inventory.column_mapping)
            df = result["df"]
            logger.info(f"Column mapping applied. Renamed columns: {result['renamed_columns']}")
        except Exception as e:
            logger.error(f"Failed to apply column mapping: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error applying column mapping: {str(e)}"
            )

    # Check if corrections were applied and need to be used
    from app.models.inventory import TreeCorrectionLog
    import logging
    logger = logging.getLogger(__name__)

    corrections = db.query(TreeCorrectionLog).filter(
        TreeCorrectionLog.inventory_calculation_id == inventory_id
    ).all()

    if corrections and len(corrections) > 0:
        logger.info(f"Found {len(corrections)} corrections to apply")

        # Detect coordinate columns by looking for common column names
        x_col = None
        y_col = None

        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ['x', 'longitude', 'lon', 'long', 'easting']:
                x_col = col
            if col_lower in ['y', 'latitude', 'lat', 'northing']:
                y_col = col

        if x_col and y_col:
            # Convert coordinate columns to float to avoid dtype errors
            # (CSV may have read them as integers)
            logger.info(f"Converting coordinate columns to float: {x_col}={df[x_col].dtype}, {y_col}={df[y_col].dtype}")
            df[x_col] = df[x_col].astype(float)
            df[y_col] = df[y_col].astype(float)
            logger.info(f"Converted to: {x_col}={df[x_col].dtype}, {y_col}={df[y_col].dtype}")

            # Apply each correction
            correction_map = {c.tree_row_number: c for c in corrections}

            for idx in range(len(df)):
                row_num = idx + 1  # CSV rows are 1-indexed (first data row is 1)
                if row_num in correction_map:
                    correction = correction_map[row_num]
                    df.at[idx, x_col] = correction.corrected_x
                    df.at[idx, y_col] = correction.corrected_y
                    logger.debug(f"Applied correction to row {row_num}")

            logger.info(f"Applied {len(corrections)} boundary corrections to dataframe")
        else:
            logger.warning(f"Could not detect coordinate columns. Found: {df.columns.tolist()}")

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


@router.get("/by-calculation/{calculation_id}", response_model=InventoryCalculationResponse)
async def get_tree_mapping_by_calculation(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get tree mapping for a specific calculation
    Returns tree mapping if it exists, otherwise 404
    """
    tree_mapping = db.query(InventoryCalculation).filter(
        InventoryCalculation.calculation_id == calculation_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not tree_mapping:
        raise HTTPException(
            status_code=404,
            detail="No tree mapping found for this calculation"
        )

    return tree_mapping


@router.delete("/{inventory_id}")
async def delete_inventory(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete tree mapping calculation and all associated trees
    """
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Tree mapping not found")

    db.delete(inventory)
    db.commit()

    return {"message": "Tree mapping deleted successfully"}


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


@router.get("/{inventory_id}/correction-preview")
async def get_correction_preview(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get preview of boundary corrections for out-of-boundary trees

    Returns proposed corrections without applying them
    """
    from app.services.boundary_validator import get_boundary_from_calculation
    from app.services.boundary_corrector import generate_correction_preview
    from app.models.inventory import TreeCorrectionLog

    # Verify ownership
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    if inventory.status != 'validated':
        raise HTTPException(
            status_code=400,
            detail=f"Inventory must be in 'validated' status. Current status: {inventory.status}"
        )

    if not inventory.calculation_id:
        raise HTTPException(
            status_code=400,
            detail="Inventory not linked to a calculation boundary"
        )

    # Check if already corrected
    existing_corrections = db.query(TreeCorrectionLog).filter(
        TreeCorrectionLog.inventory_calculation_id == inventory_id
    ).first()

    if existing_corrections:
        raise HTTPException(
            status_code=400,
            detail="Corrections already applied to this inventory"
        )

    # Re-read the uploaded file to get tree data
    # Note: In production, you might want to cache this data
    try:
        import os
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
        # For now, we'll need to re-upload or store the dataframe
        # This is a simplified version - in production, consider storing validated data
        raise HTTPException(
            status_code=501,
            detail="Correction preview requires re-upload. Use process endpoint with corrections enabled."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{inventory_id}/accept-corrections")
async def accept_corrections(
    inventory_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Apply boundary corrections and proceed with processing

    Requires re-uploading the CSV file
    """
    from app.services.boundary_validator import validate_inventory_boundary, get_boundary_from_calculation
    from app.services.boundary_corrector import generate_correction_preview, apply_corrections_to_dataframe
    from app.models.inventory import TreeCorrectionLog
    from app.services.inventory_validator import InventoryValidator

    logger.info(f"Accepting corrections for inventory {inventory_id}")

    # Verify ownership
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()

    if not inventory:
        logger.error(f"Inventory {inventory_id} not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Inventory not found")

    logger.info(f"Inventory status: {inventory.status}, calculation_id: {inventory.calculation_id}")

    if inventory.status != 'validated':
        logger.error(f"Invalid status for corrections: {inventory.status}")
        raise HTTPException(
            status_code=400,
            detail=f"Inventory must be in 'validated' status. Current status: {inventory.status}. "
                   f"Cannot apply corrections to inventories that are already processed or have corrections applied."
        )

    if not inventory.calculation_id:
        logger.error(f"Inventory {inventory_id} not linked to calculation")
        raise HTTPException(
            status_code=400,
            detail="Inventory not linked to a calculation boundary. Please ensure you uploaded the file with a calculation_id."
        )

    # Read CSV
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        logger.info(f"CSV read successfully: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        logger.error(f"Error reading CSV: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")

    # Validate again
    validator = InventoryValidator(db)
    validation_report = await validator.validate_inventory_file(df)

    if not validation_report['summary'].get('ready_for_processing'):
        logger.error(f"File validation failed: {validation_report}")
        raise HTTPException(
            status_code=400,
            detail=f"File validation failed. Please check the file format and required columns."
        )

    # Get coordinate columns
    coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
    x_col = coord_cols.get('x')
    y_col = coord_cols.get('y')
    species_col = 'Species'  # Adjust if different

    if not x_col or not y_col:
        logger.error(f"Could not detect coordinates. Found columns: {list(df.columns)}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect coordinate columns. Found columns: {list(df.columns)}"
        )

    logger.info(f"Detected coordinate columns: X={x_col}, Y={y_col}")

    # Extract tree points
    tree_points = [
        (float(row[x_col]), float(row[y_col]), idx + 1)
        for idx, row in df.iterrows()
        if pd.notna(row[x_col]) and pd.notna(row[y_col])
    ]

    # Validate boundary
    try:
        boundary_check = validate_inventory_boundary(
            db,
            inventory.calculation_id,
            tree_points,
            tolerance_percent=5.0
        )
    except Exception as e:
        logger.error(f"Boundary validation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Boundary validation error: {str(e)}"
        )

    # Provide specific error messages
    if not boundary_check['needs_correction']:
        # Check why correction is not needed
        if boundary_check['out_of_boundary_count'] == 0:
            raise HTTPException(
                status_code=400,
                detail="All trees are already within the boundary. No corrections needed."
            )
        elif not boundary_check['within_tolerance']:
            raise HTTPException(
                status_code=400,
                detail=f"Too many trees outside boundary ({boundary_check['out_of_boundary_percentage']}% > 5%). "
                       f"Please check your data: verify coordinates, EPSG code, and boundary selection. "
                       f"Automatic correction is only available when <5% of trees are outside the boundary."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Boundary correction not available for this dataset"
            )

    # Generate corrections
    try:
        logger.info(f"Generating corrections for {len(boundary_check['out_of_boundary_points'])} trees")
        corrections_data = generate_correction_preview(
            df,
            boundary_check['boundary_wkt'],
            boundary_check['out_of_boundary_points'],
            x_col,
            y_col,
            species_col
        )
        logger.info(f"Generated {len(corrections_data['corrections'])} corrections")
    except Exception as e:
        logger.error(f"Error generating corrections: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate corrections: {str(e)}"
        )

    # Apply corrections to dataframe (not used directly, just for validation)
    try:
        df_corrected = apply_corrections_to_dataframe(
            df,
            corrections_data['corrections'],
            x_col,
            y_col
        )
    except Exception as e:
        logger.error(f"Error applying corrections to dataframe: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply corrections: {str(e)}"
        )

    # Log corrections to database
    try:
        for correction in corrections_data['corrections']:
            correction_log = TreeCorrectionLog(
                inventory_calculation_id=inventory_id,
                tree_row_number=correction['row_number'],
                species=correction['species'],
                original_x=correction['original_x'],
                original_y=correction['original_y'],
                corrected_x=correction['corrected_x'],
                corrected_y=correction['corrected_y'],
                distance_moved_meters=correction['distance_moved_meters'],
                correction_reason='out_of_boundary'
            )
            db.add(correction_log)

        # Update inventory status
        inventory.status = 'corrections_applied'
        db.commit()
        logger.info(f"Successfully saved {len(corrections_data['corrections'])} corrections to database")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving corrections to database: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save corrections: {str(e)}"
        )

    return {
        'message': 'Corrections applied successfully',
        'corrections_count': len(corrections_data['corrections']),
        'summary': corrections_data['summary'],
        'next_step': 'POST /api/inventory/{inventory_id}/process with corrected file'
    }
