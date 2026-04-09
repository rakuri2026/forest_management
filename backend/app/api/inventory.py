"""
Inventory API endpoints
Handles tree inventory upload, validation, and processing
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from uuid import UUID
import uuid
import json
import pandas as pd
import numpy as np
import io

from ..core.database import get_db
from sqlalchemy import text
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


@router.get("/{inventory_id}/grid-cells")
async def get_grid_cells(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get grid cells as GeoJSON for visualization on map
    
    Uses the forest block bounds for consistent grid with mother tree identification:
    1. Find forest block with majority of trees
    2. Use block geometry bounds for grid
    3. If no block found, fallback to tree bounds
    """
    logger.info(f"[get_grid_cells] Getting grid cells for inventory {inventory_id}")
    
    # Verify ownership
    inventory = db.query(InventoryCalculation).filter(
        InventoryCalculation.id == inventory_id,
        InventoryCalculation.user_id == current_user.id
    ).first()
    
    if not inventory:
        logger.error(f"Inventory {inventory_id} not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    # Get projection and grid settings
    projection_epsg = inventory.projection_epsg or 32644
    grid_size = inventory.grid_spacing_meters or 20.0
    
    # Use TREE bounds (same as service that creates the grid)
    # This ensures fishnet cell IDs match tree grid_cell_ids
    result = db.execute(text("""
        SELECT 
            ST_XMin(ST_Extent(ST_Transform(location::geometry, :epsg))) AS xmin,
            ST_YMin(ST_Extent(ST_Transform(location::geometry, :epsg))) AS ymin,
            ST_XMax(ST_Extent(ST_Transform(location::geometry, :epsg))) AS xmax,
            ST_YMax(ST_Extent(ST_Transform(location::geometry, :epsg))) AS ymax
        FROM public.inventory_trees
        WHERE inventory_calculation_id = :inv_id
    """), {"epsg": projection_epsg, "inv_id": str(inventory_id)}).first()
    
    block_geom_wkt = None
    block_result = None
    
    # Get block for clipping only (not for bounds)
    if inventory.calculation_id:
        block_vote_query = text("""
            SELECT fb.id, fb.name
            FROM forest_blocks fb
            JOIN inventory_trees t ON ST_Contains(fb.geometry, t.location::geometry)
            WHERE t.inventory_calculation_id = :inventory_id
              AND fb.calculation_id = :calc_id
              AND fb.parent_block_id IS NULL
            GROUP BY fb.id, fb.name
            ORDER BY COUNT(t.id) DESC
            LIMIT 1
        """)
        block_result = db.execute(block_vote_query, {
            "inventory_id": str(inventory_id),
            "calc_id": str(inventory.calculation_id)
        }).first()
        
        if block_result:
            # Get block geometry for clipping
            block_geom_result = db.execute(text("""
                SELECT ST_AsText(ST_Transform(geometry, :epsg))
                FROM forest_blocks
                WHERE id = :block_id
            """), {"epsg": projection_epsg, "block_id": str(block_result[0])}).first()
            if block_geom_result:
                block_geom_wkt = block_geom_result[0]
    
    xmin, ymin = None, None
    num_cols, num_rows = None, None
    
    if result and result[0]:
        xmin, ymin, xmax, ymax = result
        num_cols = int(round((xmax - xmin) / grid_size)) + 1
        num_rows = int(round((ymax - ymin) / grid_size)) + 1
        logger.info(f"[get_grid_cells] Grid from block: origin=({xmin}, {ymin}), size=({xmax-xmin}, {ymax-ymin}), cols={num_cols}, rows={num_rows}")
    else:
        logger.warning(f"[get_grid_cells] No bounds found for inventory {inventory_id}")
    
    if xmin is None:
        return {
            "type": "FeatureCollection", 
            "features": [],
            "metadata": {}
        }
    
    # Get grid metadata
    grid_metadata = {
        "origin_x": xmin,
        "origin_y": ymin,
        "num_cols": num_cols,
        "num_rows": num_rows,
        "spacing_meters": grid_size,
        "projection_epsg": projection_epsg
    }
    
    # Get grid cells from persistent storage (same cells used for tree assignment)
    existing_cells = db.execute(text("""
        SELECT COUNT(*) FROM inventory_grid_cells 
        WHERE inventory_calculation_id = :inv_id
    """), {"inv_id": str(inventory_id)}).scalar()

    if existing_cells and existing_cells > 0:
        logger.info(f"[get_grid_cells] Using {existing_cells} grid cells from database")
        grid_cells_result = db.execute(text("""
            SELECT 
                cell_id,
                ST_AsGeoJSON(geom) as geom_wgs84
            FROM inventory_grid_cells
            WHERE inventory_calculation_id = :inv_id
            ORDER BY cell_id
        """), {"inv_id": str(inventory_id)}).fetchall()
        
        features = []
        for row in grid_cells_result:
            cell_id = row[0]
            geom_wgs84 = json.loads(row[1]) if row[1] else None
            
            if geom_wgs84:
                features.append({
                    "type": "Feature",
                    "id": cell_id,
                    "properties": {
                        "cell_id": cell_id
                    },
                    "geometry": geom_wgs84
                })
    else:
        logger.warning(f"[get_grid_cells] No stored grid cells found, generating from scratch")
        
        features = []
        for row_idx in range(num_rows):
            for col_idx in range(num_cols):
                cell_id = row_idx * num_cols + col_idx + 1
                
                cell_xmin = xmin + col_idx * grid_size
                cell_ymin = ymin + row_idx * grid_size
                cell_xmax = cell_xmin + grid_size
                cell_ymax = cell_ymin + grid_size
                
                result = db.execute(text("""
                    SELECT ST_AsGeoJSON(ST_Transform(
                        ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), :epsg),
                        4326
                    ))
                """), {"xmin": cell_xmin, "ymin": cell_ymin, "xmax": cell_xmax, "ymax": cell_ymax, "epsg": projection_epsg}).scalar()
                
                if result:
                    geom = json.loads(result)
                    features.append({
                        "type": "Feature",
                        "id": cell_id,
                        "properties": {
                            "cell_id": cell_id,
                            "row": row_idx + 1,
                            "col": col_idx + 1
                        },
                        "geometry": geom
                    })
    
    logger.info(f"[get_grid_cells] First 5 cell IDs: {[f['properties']['cell_id'] for f in features[:5]]}")
    logger.info(f"[get_grid_cells] Last 5 cell IDs: {[f['properties']['cell_id'] for f in features[-5:]]}")
    logger.info(f"[get_grid_cells] Returning {len(features)} grid cells")
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": grid_metadata
    }


@router.get("/{inventory_id}/export-grid")
async def export_grid(
    inventory_id: UUID,
    format: str = Query("geojson", regex="^(geojson|kml)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export grid cells as GeoJSON or KML file
    """
    from fastapi.responses import StreamingResponse
    from datetime import datetime
    
    logger.info(f"[export_grid] Exporting grid for inventory {inventory_id} as {format}")
    
    try:
        inventory = db.query(InventoryCalculation).filter(
            InventoryCalculation.id == inventory_id,
            InventoryCalculation.user_id == current_user.id
        ).first()
        
        if not inventory:
            raise HTTPException(status_code=404, detail="Inventory not found")
        
        logger.info(f"[export_grid] Inventory status: {inventory.status}")
        
        grid_cells_result = db.execute(text("""
            SELECT 
                gc.cell_id,
                ST_AsGeoJSON(gc.geom) as geom_wgs84,
                COUNT(t.id) as tree_count,
                COUNT(CASE WHEN t.remark = 'Mother Tree' THEN 1 END) as mother_count,
                COUNT(CASE WHEN t.remark = 'Felling Tree' THEN 1 END) as felling_count,
                COUNT(CASE WHEN t.remark = 'Pole' THEN 1 END) as pole_count,
                COUNT(CASE WHEN t.remark = 'Seedling' THEN 1 END) as seedling_count,
                COALESCE(SUM(t.net_volume), 0) as total_net_volume
            FROM inventory_grid_cells gc
            LEFT JOIN inventory_trees t ON t.grid_cell_id = gc.cell_id 
                AND t.inventory_calculation_id = gc.inventory_calculation_id
            WHERE gc.inventory_calculation_id = :inv_id
            GROUP BY gc.cell_id, gc.geom
            ORDER BY gc.cell_id
        """), {"inv_id": str(inventory_id)}).fetchall()
        
        logger.info(f"[export_grid] Found {len(grid_cells_result) if grid_cells_result else 0} grid cells")
        
        if not grid_cells_result:
            raise HTTPException(
                status_code=404, 
                detail=f"No grid cells found. Inventory status: {inventory.status}. Please re-process the inventory."
            )
        
        forest_name = "inventory"
        if inventory.calculation_id:
            calc = db.execute(text("""
                SELECT forest_name FROM calculations WHERE id = :calc_id
            """), {"calc_id": str(inventory.calculation_id)}).scalar()
            if calc:
                import unicodedata
                forest_name = unicodedata.normalize('NFKD', str(calc)).encode('ascii', 'ignore').decode('ascii').replace(' ', '_')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "kml":
            import tempfile
            import os
            
            kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Grid Cells - {forest_name}</name>
    <description>Grid cells from tree inventory</description>
    <Style id="gridCell">
      <LineStyle>
        <color>ff3b82f6</color>
        <width>2</width>
      </LineStyle>
      <PolyStyle>
        <color>1a3b82f6</color>
        <fill>1</fill>
        <outline>1</outline>
      </PolyStyle>
    </Style>
'''.format(forest_name=forest_name)
            
            for row in grid_cells_result:
                cell_id = row[0]
                geom_dict = json.loads(row[1]) if row[1] else None
                
                if geom_dict and geom_dict.get('type') == 'Polygon':
                    coords = geom_dict['coordinates'][0]
                    coord_str = ' '.join([f"{c[0]},{c[1]},0" for c in coords])
                    
                    kml_content += f'''    <Placemark>
      <name>Cell {cell_id}</name>
      <styleUrl>#gridCell</styleUrl>
      <ExtendedData>
        <Data name="cell_id"><value>{cell_id}</value></Data>
        <Data name="tree_count"><value>{row[2] or 0}</value></Data>
        <Data name="mother_count"><value>{row[3] or 0}</value></Data>
        <Data name="felling_count"><value>{row[4] or 0}</value></Data>
        <Data name="pole_count"><value>{row[5] or 0}</value></Data>
        <Data name="seedling_count"><value>{row[6] or 0}</value></Data>
        <Data name="net_vol_m3"><value>{float(row[7]) if row[7] else 0.0:.3f}</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coord_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
'''
            
            kml_content += '''  </Document>
</kml>'''
            
            logger.info(f"[export_grid] KML exported successfully")
            
            return StreamingResponse(
                iter([kml_content]),
                media_type='application/vnd.google-earth.kml+xml',
                headers={'Content-Disposition': f'attachment; filename="{forest_name}_grid_{timestamp}.kml"'}
            )
        
        else:  # GeoJSON format
            features = []
            for row in grid_cells_result:
                try:
                    cell_id = int(row[0])
                    geom_json = row[1]
                    
                    if geom_json:
                        geom_dict = json.loads(geom_json) if isinstance(geom_json, str) else geom_json
                        
                        def to_int(val):
                            if val is None:
                                return 0
                            if isinstance(val, (int, np.integer)):
                                return int(val)
                            return int(val) if val else 0
                        
                        def to_float(val):
                            if val is None:
                                return 0.0
                            if isinstance(val, (float, np.floating)):
                                return round(float(val), 3)
                            try:
                                return round(float(val), 3)
                            except:
                                return 0.0
                        
                        features.append({
                            "type": "Feature",
                            "id": cell_id,
                            "geometry": geom_dict,
                            "properties": {
                                "cell_id": cell_id,
                                "tree_count": to_int(row[2]),
                                "mother_count": to_int(row[3]),
                                "felling_count": to_int(row[4]),
                                "pole_count": to_int(row[5]),
                                "seedling_count": to_int(row[6]),
                                "net_vol_m3": to_float(row[7])
                            }
                        })
                except Exception as feat_err:
                    logger.error(f"[export_grid] Error processing cell {row[0]}: {feat_err}")
                    continue
            
            logger.info(f"[export_grid] GeoJSON: {len(features)} features processed")
            
            geojson_data = {
                "type": "FeatureCollection",
                "features": features
            }
            
            geojson_str = json.dumps(geojson_data, ensure_ascii=False)
            
            logger.info(f"[export_grid] GeoJSON exported with {len(features)} features, size: {len(geojson_str)} bytes")
            
            return StreamingResponse(
                iter([geojson_str]),
                media_type='application/json',
                headers={'Content-Disposition': f'attachment; filename="{forest_name}_grid_{timestamp}.geojson"'}
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[export_grid] Export failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


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

    with open(template_path, 'r', encoding='utf-8') as f:
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
    correction_strategy: str = Form("nearest_tree"),  # "nearest_tree" or "boundary_edge"
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

    # IMPORTANT: Check boundary FIRST if calculation_id provided
    # This gives fast feedback if >20% outside, before expensive validation
    boundary_check_result = None
    if calculation_id:
        print(f"[BOUNDARY] Checking boundary first (fast fail for >20%)...")
        try:
            from app.services.boundary_validator import validate_inventory_boundary

            # Get coordinate columns from mapping
            # Find longitude/latitude columns
            x_col = None
            y_col = None
            for csv_col, std_col in mapping_dict.items():
                if std_col.upper() == 'LONGITUDE':
                    x_col = std_col
                elif std_col.upper() == 'LATITUDE':
                    y_col = std_col

            if x_col and y_col and x_col in df_renamed.columns and y_col in df_renamed.columns:
                # Quick boundary check BEFORE full validation
                tree_points = [
                    (float(row[x_col]), float(row[y_col]), idx + 1)
                    for idx, row in df_renamed.iterrows()
                    if pd.notna(row[x_col]) and pd.notna(row[y_col])
                ]

                boundary_check_result = validate_inventory_boundary(
                    db,
                    UUID(calculation_id),
                    tree_points,
                    tolerance_percent=20.0
                )

                print(f"[BOUNDARY] Quick check: {boundary_check_result['out_of_boundary_percentage']}% outside, tolerance: {boundary_check_result['within_tolerance']}")

                # If >20% outside, return error IMMEDIATELY (before full validation)
                if not boundary_check_result['within_tolerance']:
                    print(f"[BOUNDARY] REJECTED: {boundary_check_result['out_of_boundary_percentage']}% exceeds 20% tolerance")
                    error_response = {
                        'success': False,
                        'summary': {
                            'total_rows': len(df_renamed),
                            'ready_for_processing': False,
                            'has_critical_errors': True
                        },
                        'boundary_check': {
                            'total_points': boundary_check_result['total_points'],
                            'out_of_boundary_count': boundary_check_result['out_of_boundary_count'],
                            'out_of_boundary_percentage': boundary_check_result['out_of_boundary_percentage'],
                            'within_tolerance': False,
                            'needs_correction': False,
                            'correction_strategy': correction_strategy
                        },
                        'errors': [{
                            'type': 'boundary_error',
                            'severity': 'error',
                            'message': boundary_check_result.get('error_message', 'Too many trees outside boundary')
                        }],
                        'warnings': [],
                        'data_detection': {},
                        'corrections': []
                    }
                    print(f"[BOUNDARY] Returning error response with {len(error_response['errors'])} errors")
                    return convert_numpy_types(error_response)
        except Exception as e:
            print(f"[BOUNDARY] Quick check failed: {str(e)}")
            # Continue with normal validation if boundary check fails
            pass

    # Validate data with renamed columns (only if boundary check passed or not applicable)
    print(f"[VALIDATION] Starting full inventory validation for {len(df_renamed)} rows...")
    validator = InventoryValidator(db)
    validation_report = await validator.validate_inventory_file(
        df_renamed,
        user_specified_crs=projection_epsg,
        calculation_id=calculation_id
    )
    print(f"[VALIDATION] Inventory validation complete. Ready for processing: {validation_report['summary'].get('ready_for_processing')}")

    # Add boundary check to validation report if we already have it from quick check
    if boundary_check_result and calculation_id and validation_report['summary'].get('ready_for_processing'):
        print(f"[BOUNDARY] Adding boundary check to validation report...")
        validation_report['boundary_check'] = {
            'total_points': boundary_check_result['total_points'],
            'out_of_boundary_count': boundary_check_result['out_of_boundary_count'],
            'out_of_boundary_percentage': boundary_check_result['out_of_boundary_percentage'],
            'within_tolerance': boundary_check_result['within_tolerance'],
            'needs_correction': boundary_check_result['needs_correction'],
            'correction_strategy': correction_strategy
        }

        # Generate correction preview if corrections are needed (already checked tolerance in quick check)
        if boundary_check_result['needs_correction']:
            try:
                # Get coordinate columns for correction generation
                coord_cols = validation_report['data_detection'].get('coordinate_columns', {})
                x_col = coord_cols.get('x')
                y_col = coord_cols.get('y')

                if correction_strategy == "nearest_tree":
                    # Use tree-to-tree correction
                    from app.services.tree_to_tree_corrector import TreeToTreeCorrector

                    corrector = TreeToTreeCorrector(db)
                    corrections_result = corrector.generate_corrections(
                        df_renamed[[x_col, y_col, 'row_number'] if 'row_number' in df_renamed.columns else df_renamed[[x_col, y_col]].assign(row_number=range(1, len(df_renamed)+1))].rename(columns={x_col: 'longitude', y_col: 'latitude'}),
                        boundary_check_result['boundary_wkt'],
                        str(UUID(calculation_id))
                    )

                    validation_report['boundary_check']['corrections'] = corrections_result['corrections']
                    validation_report['boundary_check']['correction_summary'] = corrections_result['correction_summary']
                    validation_report['boundary_check']['correctable'] = corrections_result['correctable']
                    validation_report['boundary_check']['uncorrectable'] = corrections_result['uncorrectable']
                    validation_report['boundary_check']['recommendation'] = corrections_result['recommendation']

                else:
                    # Use boundary edge correction (existing method)
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

            except Exception as e:
                # Log correction generation error but don't fail upload
                import logging
                logging.error(f"Correction generation failed: {str(e)}")
                print(f"[BOUNDARY] Correction generation failed: {str(e)}")
                validation_report['warnings'].append({
                    'type': 'correction_generation_error',
                    'severity': 'warning',
                    'message': f'Could not generate correction preview: {str(e)}'
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
                        'message': f'Auto-detected UTM Zone 45N (EPSG:32645) based on longitude {mean_lon:.2f}°E (>= 84°E)'
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
                        'message': f'Auto-detected UTM Zone 45N (EPSG:32645) based on longitude {mean_lon:.2f}°E (>= 84°E)'
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
        import traceback
        # Safely get error message
        try:
            error_detail = f"Processing failed: {str(e)}"
        except UnicodeEncodeError:
            error_detail = "Processing failed: Unicode encoding error"
        
        # Try to get traceback safely
        try:
            tb = traceback.format_exc()
            print(f"[PROCESS_ERROR] {error_detail}")
            print(f"[PROCESS_TRACE] {tb}")
        except:
            pass
            
        inventory.status = 'failed'
        inventory.error_message = error_detail
        db.commit()
        
        # Return safe error to client
        raise HTTPException(status_code=500, detail=error_detail)


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

    # Get enhanced summary statistics from database
    try:
        service = InventoryService(db)
        summary_stats = await service._calculate_summary_from_db(inventory_id)
    except Exception as e:
        import traceback
        print(f"[SUMMARY] Error calculating summary: {e}")
        print(f"[SUMMARY] Traceback: {traceback.format_exc()}")
        # Fall back to inventory table values
        summary_stats = {
            'total_trees': inventory.total_trees or 0,
            'mother_trees_count': inventory.mother_trees_count or 0,
            'felling_trees_count': inventory.felling_trees_count or 0,
            'pole_count': 0,
            'seedling_count': inventory.seedling_count or 0,
            'total_volume_m3': inventory.total_volume_m3 or 0,
            'total_net_volume_m3': inventory.total_net_volume_m3 or 0,
            'total_net_volume_cft': inventory.total_net_volume_cft or 0,
            'total_firewood_m3': inventory.total_firewood_m3 or 0,
            'total_firewood_chatta': inventory.total_firewood_chatta or 0,
            'regeneration_count': 0,
            'sapling_count': 0,
            'stand_pole_count': 0,
            'tree_count': 0,
            'felling_volume_m3': 0,
            'mother_volume_m3': 0,
            'pole_volume_m3': 0,
            'timber_volume_m3': 0,
            'timber_volume_cft': 0
        }
    
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
                WHEN dia_cm < 4 THEN 'Regeneration (0.1-4)'
                WHEN dia_cm < 10 THEN 'Sapling (4-10)'
                WHEN dia_cm < 30 THEN 'Pole (10-30)'
                ELSE 'Tree (>30)'
            END as dbh_class,
            COUNT(*) as count
        FROM public.inventory_trees
        WHERE inventory_calculation_id = :inventory_id
        GROUP BY CASE
                WHEN dia_cm < 4 THEN 'Regeneration (0.1-4)'
                WHEN dia_cm < 10 THEN 'Sapling (4-10)'
                WHEN dia_cm < 30 THEN 'Pole (10-30)'
                ELSE 'Tree (>30)'
            END
        """),
        {"inventory_id": str(inventory_id)}
    )
    dbh_classes = {row[0]: row[1] for row in dbh_query.fetchall()}

    # Get compartment-wise breakdown with tree category counts and volumes
    # Also get forest name and block name from the calculation
    try:
        calc_id = inventory.calculation_id if inventory else None
        print(f"[SUMMARY] Inventory ID: {inventory_id}, calculation_id: {calc_id}")
        
        # First get forest and block info from calculation
        forest_name = None
        block_name = None
        if calc_id:
            calc_query = db.execute(
                text("""
                    SELECT c.forest_name, c.block_name 
                    FROM calculations c 
                    WHERE c.id = :calc_id
                """),
                {"calc_id": str(calc_id)}
            ).first()
            if calc_query:
                forest_name = calc_query[0]
                block_name = calc_query[1]
                print(f"[SUMMARY] Forest: {forest_name}, Block: {block_name}")
        
        # Get compartment breakdown using spatial join
        # Get all child blocks (compartments) under this calculation
        if calc_id:
            compartment_query = db.execute(
                text("""
                    SELECT 
                        COALESCE(fb.compartment_code, fb.name) as comp_name,
                        it.remark,
                        COUNT(*) as tree_count,
                        COALESCE(SUM(it.net_volume), 0) as net_volume_m3,
                        COALESCE(SUM(it.net_volume_cft), 0) as net_volume_cft,
                        COALESCE(SUM(it.firewood_m3), 0) as firewood_m3,
                        COALESCE(SUM(it.firewood_chatta), 0) as firewood_chatta
                    FROM public.inventory_trees it
                    LEFT JOIN LATERAL (
                        SELECT fb.id, fb.compartment_code, fb.name
                        FROM public.forest_blocks fb
                        WHERE fb.parent_block_id IN (
                            SELECT id FROM public.forest_blocks WHERE calculation_id = :calc_id
                        )
                        AND ST_Contains(fb.geometry, it.location::geometry)
                        LIMIT 1
                    ) fb ON true
                    WHERE it.inventory_calculation_id = :inventory_id
                    GROUP BY COALESCE(fb.compartment_code, fb.name), it.remark
                    ORDER BY COALESCE(fb.compartment_code, fb.name), 
                        CASE it.remark 
                            WHEN 'Seedling' THEN 1 
                            WHEN 'Pole' THEN 2 
                            WHEN 'Felling Tree' THEN 3 
                            WHEN 'Mother Tree' THEN 4 
                        END
                """),
                {"inventory_id": str(inventory_id), "calc_id": str(calc_id)}
            )
            
            compartment_breakdown = []
            for row in compartment_query.fetchall():
                compartment_breakdown.append({
                    'forest_name': forest_name or 'Unknown',
                    'block_name': block_name or 'Unknown',
                    'compartment_name': row[0] or 'Unassigned',
                    'remark': row[1],
                    'tree_count': row[2],
                    'net_volume_m3': round(float(row[3]), 3) if row[3] else 0,
                    'net_volume_cft': round(float(row[4]), 3) if row[4] else 0,
                    'firewood_m3': round(float(row[5]), 3) if row[5] else 0,
                    'firewood_chatta': round(float(row[6]), 3) if row[6] else 0
                })
            
            print(f"[SUMMARY] Compartment breakdown rows: {len(compartment_breakdown)}")
        else:
            compartment_breakdown = []
        
        # Get species breakdown with volumes
        try:
            species_query = db.execute(
                text("""
                    SELECT 
                        it.species,
                        it.local_name,
                        it.remark,
                        COUNT(*) as tree_count,
                        COALESCE(SUM(it.net_volume), 0) as net_volume_m3,
                        COALESCE(SUM(it.net_volume_cft), 0) as net_volume_cft,
                        COALESCE(SUM(it.firewood_m3), 0) as firewood_m3,
                        COALESCE(SUM(it.firewood_chatta), 0) as firewood_chatta
                    FROM public.inventory_trees it
                    WHERE it.inventory_calculation_id = :inventory_id
                    GROUP BY it.species, it.local_name, it.remark
                    ORDER BY it.species, 
                        CASE it.remark 
                            WHEN 'Seedling' THEN 1 
                            WHEN 'Pole' THEN 2 
                            WHEN 'Felling Tree' THEN 3 
                            WHEN 'Mother Tree' THEN 4 
                        END
                """),
                {"inventory_id": str(inventory_id)}
            )
            
            species_breakdown = []
            for row in species_query.fetchall():
                species_breakdown.append({
                    'species': row[0],
                    'local_name': row[1],
                    'remark': row[2],
                    'tree_count': row[3],
                    'net_volume_m3': round(float(row[4]), 3) if row[4] else 0,
                    'net_volume_cft': round(float(row[5]), 3) if row[5] else 0,
                    'firewood_m3': round(float(row[6]), 3) if row[6] else 0,
                    'firewood_chatta': round(float(row[7]), 3) if row[7] else 0
                })
            
            print(f"[SUMMARY] Species breakdown rows: {len(species_breakdown)}")
        except Exception as e:
            import traceback
            print(f"[SUMMARY] Species query error: {e}")
            print(f"[SUMMARY] Traceback: {traceback.format_exc()}")
            species_breakdown = []
        
    except Exception as e:
        import traceback
        print(f"[SUMMARY] Compartment query error: {e}")
        print(f"[SUMMARY] Traceback: {traceback.format_exc()}")
        compartment_breakdown = []
        species_breakdown = []

    return {
        'inventory_id': inventory.id,
        **summary_stats,  # Include all enhanced stats from database query
        'species_distribution': species_distribution,
        'dbh_classes': dbh_classes,
        'compartment_breakdown': compartment_breakdown,
        'species_breakdown': species_breakdown,
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
    remark: Optional[str] = Query(None, description="Filter by remark (Mother Tree, Felling Tree, Seedling, Pole)"),
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

    calculation_id = inventory.calculation_id

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

        # Auto-assign compartment based on spatial intersection if not already assigned
        compartment_name = None
        if not tree.compartment_id and calculation_id:
            # Find compartments for this calculation
            comp_result = db.execute(
                text("""
                    SELECT fb.id, COALESCE(fb.compartment_code, fb.name) as comp_name
                    FROM forest_blocks fb
                    JOIN forest_blocks parent ON fb.parent_block_id = parent.id
                    WHERE parent.calculation_id = :calc_id AND fb.is_compartment = true
                    AND ST_Contains(fb.geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    LIMIT 1
                """),
                {"calc_id": calculation_id, "lon": lon, "lat": lat}
            ).first()
            if comp_result:
                compartment_name = comp_result[1]  # comp_name column
        elif tree.compartment_id:
            from ..models.forest_block import ForestBlock
            comp = db.query(ForestBlock).filter(ForestBlock.id == tree.compartment_id).first()
            if comp:
                compartment_name = comp.compartment_code or comp.name

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
            compartment_id=tree.compartment_id,
            compartment_name=compartment_name,
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
    format: str = Query('csv', regex="^(csv|geojson|excel)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export inventory results (CSV, GeoJSON, or Excel)
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

        if format == 'csv':
            media_type = "text/csv; charset=utf-8"
        elif format == 'excel':
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            media_type = "application/geo+json; charset=utf-8"
        
        # Ensure filename is ASCII-safe for Content-Disposition header
        import unicodedata
        ascii_filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
        if not ascii_filename:
            ascii_filename = "tree_mapping_export"
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={ascii_filename}"
            }
        )
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


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

    # Validate boundary with updated 20% tolerance
    try:
        boundary_check = validate_inventory_boundary(
            db,
            inventory.calculation_id,
            tree_points,
            tolerance_percent=20.0
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
                detail=f"Too many trees outside boundary ({boundary_check['out_of_boundary_percentage']}% > 20%). "
                       f"Please check your data: verify coordinates, EPSG code, and boundary selection. "
                       f"Automatic correction is only available when <20% of trees are outside the boundary."
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
