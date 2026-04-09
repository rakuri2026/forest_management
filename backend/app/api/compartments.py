"""
Compartment management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from uuid import UUID
from shapely.geometry import mapping
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime

from ..core.database import get_db
from ..utils.auth import get_current_user
from ..models.user import User
from ..models.forest_block import ForestBlock
from ..models.compartment import CompartmentSplitHistory
from ..models.inventory import InventoryTree
from ..schemas.compartment import (
    SplitPreviewRequest,
    SplitPreviewResponse,
    ExecuteSplitRequest,
    ExecuteSplitResponse,
    SplitDirection,
    AvailableBlock,
    TreeReassignmentRequest,
    TreeReassignmentResponse,
    CompartmentPreview,
    SplitValidation
)
from ..services.compartment_splitter import CompartmentSplitter
from ..services.tree_reassignment import (
    get_trees_needing_assignment,
    auto_assign_trees_by_location,
    manual_assign_trees
)
from ..services.geometry_utils import (
    postgis_to_shapely,
    shapely_to_postgis,
    polygon_to_geojson,
    calculate_area_sqm,
    calculate_perimeter_m
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compartments", tags=["compartments"])


@router.get("/available-blocks/{calculation_id}", response_model=List[AvailableBlock])
async def get_available_blocks(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all forest blocks available for splitting

    Args:
        calculation_id: Calculation UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of forest blocks with metadata
    """
    try:
        from app.models.inventory import InventoryCalculation
        
        # Get total trees in calculation (through inventory_calculation)
        total_trees_in_calc = db.query(InventoryTree).join(
            InventoryCalculation, InventoryCalculation.id == InventoryTree.inventory_calculation_id
        ).filter(
            InventoryCalculation.calculation_id == calculation_id
        ).count()
        
        # Get parent blocks (not compartments)
        blocks = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == calculation_id,
            (ForestBlock.is_compartment == False) | (ForestBlock.is_compartment.is_(None))
        ).all()
        logger.info(f"Compartment API: {len(blocks)} parent blocks after filtering")

        result = []
        for block in blocks:
            # Count trees in this block (direct assignment)
            tree_count = db.query(InventoryTree).filter(
                InventoryTree.forest_block_id == block.id
            ).count()

            # Check if block already has compartments
            compartment_count = db.query(ForestBlock).filter(
                ForestBlock.parent_block_id == block.id,
                ForestBlock.is_compartment == True
            ).count()

            has_compartments = compartment_count > 0

            # Convert geometry to GeoJSON
            block_geom = postgis_to_shapely(block.geometry)
            geojson = polygon_to_geojson(block_geom)

            # Calculate area using PostGIS
            area_result = db.execute(
                text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                {"block_id": str(block.id)}
            ).scalar()
            area_sqm = float(area_result) if area_result else (block.area_sqm or 0)

            result.append({
                "id": block.id,
                "name": block.name,
                "area_sqm": area_sqm,
                "area_hectares": float(block.area_hectares or 0),
                "geometry": geojson,
                "has_compartments": has_compartments,
                "tree_count": tree_count,
                "total_trees_in_calculation": total_trees_in_calc,
                "compartment_count": compartment_count
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get available blocks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get blocks: {str(e)}")


@router.get("/calculation/{calculation_id}/all-blocks")
async def get_all_blocks_for_map(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all forest blocks and compartments for map display

    Args:
        calculation_id: Calculation UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of all forest blocks with metadata
    """
    try:
        # Get all blocks (both parent blocks and compartments)
        all_blocks = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == calculation_id
        ).order_by(ForestBlock.index).all()
        
        result = []
        for block in all_blocks:
            # Count trees in this block
            tree_count = db.query(InventoryTree).filter(
                InventoryTree.forest_block_id == block.id
            ).count()

            # Check if this is a compartment
            is_compartment = block.is_compartment or False
            
            # If it's a compartment, get compartment count from parent
            compartment_count = 0
            if is_compartment:
                compartment_count = db.query(ForestBlock).filter(
                    ForestBlock.parent_block_id == block.id
                ).count()
            
            # Check if parent block has compartments (for parent blocks)
            has_compartments = False
            if not is_compartment:
                child_count = db.query(ForestBlock).filter(
                    ForestBlock.parent_block_id == block.id,
                    ForestBlock.is_compartment == True
                ).count()
                has_compartments = child_count > 0

            # Convert geometry to GeoJSON
            block_geom = postgis_to_shapely(block.geometry)
            geojson = polygon_to_geojson(block_geom)

            # Calculate area using PostGIS
            area_result = db.execute(
                text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                {"block_id": str(block.id)}
            ).scalar()
            area_sqm = float(area_result) if area_result else (block.area_sqm or 0)

            # Get parent block name if compartment
            parent_block_name = None
            if block.parent_block_id:
                parent_block = db.query(ForestBlock).filter(
                    ForestBlock.id == block.parent_block_id
                ).first()
                if parent_block:
                    parent_block_name = parent_block.name

            result.append({
                "id": block.id,
                "name": block.name,
                "area_sqm": area_sqm,
                "area_hectares": float(block.area_hectares or 0),
                "geometry": geojson,
                "has_compartments": has_compartments,
                "tree_count": tree_count,
                "compartment_count": compartment_count,
                "is_compartment": is_compartment,
                "parent_block_name": parent_block_name,
                "compartment_code": block.compartment_code,
                "index": block.index
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get all blocks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get blocks: {str(e)}")

        result = []
        for block in blocks:
            # Count trees in this block
            tree_count = db.query(InventoryTree).filter(
                InventoryTree.forest_block_id == block.id
            ).count()

            # Check if block already has compartments
            compartment_count = db.query(ForestBlock).filter(
                ForestBlock.parent_block_id == block.id,
                ForestBlock.is_compartment == True
            ).count()

            has_compartments = compartment_count > 0

            # Convert geometry to GeoJSON
            block_geom = postgis_to_shapely(block.geometry)
            geojson = polygon_to_geojson(block_geom)

            # Calculate area using PostGIS for accurate geodesic calculation
            # First check if we have a stored area_sqm that matches area_hectares
            expected_sqm = (block.area_hectares or 0) * 10000 if block.area_hectares else None
            
            # Use stored area if it matches expected (within 1% tolerance)
            if block.area_sqm and expected_sqm:
                tolerance = expected_sqm * 0.01
                if abs(block.area_sqm - expected_sqm) <= tolerance:
                    area_sqm = block.area_sqm
                else:
                    # Stored value differs significantly, recalculate from geometry
                    area_sqm = db.execute(
                        text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                        {"block_id": str(block.id)}
                    ).scalar() or block.area_sqm
            else:
                # No stored value or no expected, calculate from geometry
                area_sqm = db.execute(
                    text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                    {"block_id": str(block.id)}
                ).scalar() or (block.area_sqm or 0)

            result.append(AvailableBlock(
                id=block.id,
                name=block.name,
                area_sqm=area_sqm,
                area_hectares=block.area_hectares,
                geometry=geojson,
                has_compartments=has_compartments,
                tree_count=tree_count,
                compartment_count=compartment_count
            ))

        return result

    except Exception as e:
        logger.error(f"Failed to get available blocks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get blocks: {str(e)}")


@router.get("/calculation/{calculation_id}/export-gpkg")
async def export_blocks_gpkg(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export all forest blocks and compartments to GPKG format

    Args:
        calculation_id: Calculation UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        GPKG file download
    """
    try:
        from shapely.geometry import shape
        from geoalchemy2.shape import to_shape
        
        # Get all blocks (both parent blocks and compartments)
        all_blocks = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == calculation_id
        ).all()

        if not all_blocks:
            raise HTTPException(status_code=404, detail="No blocks found for this calculation")

        # Get forest name for filename
        from app.models.calculation import Calculation
        calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
        forest_name = calculation.forest_name.replace(' ', '_') if calculation else "forest"

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{forest_name}_compartments_{timestamp}.gpkg"
        filepath = os.path.join(temp_dir, filename)

        # Prepare features
        features = []
        for block in all_blocks:
            try:
                # Convert geometry to shapely object
                geom_obj = to_shape(block.geometry)
                
                area_result = db.execute(
                    text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                    {"block_id": str(block.id)}
                ).scalar()
                
                perimeter_result = db.execute(
                    text("SELECT ST_Perimeter(geography(geometry)) as perimeter FROM forest_blocks WHERE id = :block_id"),
                    {"block_id": str(block.id)}
                ).scalar()
                
                tree_count = db.query(InventoryTree).filter(
                    InventoryTree.forest_block_id == block.id
                ).count()
                
                parent_name = None
                if block.parent_block_id:
                    parent_block = db.query(ForestBlock).filter(
                        ForestBlock.id == block.parent_block_id
                    ).first()
                    if parent_block:
                        parent_name = parent_block.name

                feature = {
                    "type": "Feature",
                    "geometry": mapping(geom_obj),
                    "properties": {
                        "id": str(block.id),
                        "block_name": block.name,
                        "parent_block_name": parent_name or "",
                        "is_compartment": 1 if block.is_compartment else 0,
                        "compartment_code": block.compartment_code or "",
                        "area_sqm": float(area_result) if area_result else (block.area_sqm or 0),
                        "area_hectares": float(block.area_hectares or 0),
                        "perimeter_m": float(perimeter_result) if perimeter_result else 0,
                        "tree_count": tree_count,
                        "index": block.index or 0,
                        "created_at": block.created_at.isoformat() if block.created_at else ""
                    }
                }
                features.append(feature)
            except Exception as geom_err:
                logger.error(f"Failed to process block {block.id}: {geom_err}")
                import traceback
                traceback.print_exc()
                continue

        if not features:
            raise HTTPException(status_code=500, detail="Failed to process any blocks. Check backend logs.")

        # Try to write as GPKG using fiona
        try:
            import fiona
            from fiona.crs import from_epsg
            
            schema = {
                'geometry': 'Polygon',
                'properties': {
                    'id': 'str',
                    'block_name': 'str',
                    'parent_bl': 'str',
                    'is_compart': 'int',
                    'comp_code': 'str',
                    'area_sqm': 'float',
                    'area_ha': 'float',
                    'perimeter_m': 'float',
                    'tree_count': 'int',
                    'index': 'int',
                    'created_at': 'str'
                }
            }
            
            with fiona.open(filepath, 'w', driver='GPKG', schema=schema, crs=from_epsg(4326)) as gpkg:
                for feature in features:
                    props = feature['properties']
                    gpkg.write({
                        'geometry': feature['geometry'],
                        'properties': {
                            'id': props['id'],
                            'block_name': props['block_name'],
                            'parent_bl': props['parent_block_name'],
                            'is_compart': props['is_compartment'],
                            'comp_code': props['compartment_code'],
                            'area_sqm': props['area_sqm'],
                            'area_ha': props['area_hectares'],
                            'perimeter_m': props['perimeter_m'],
                            'tree_count': props['tree_count'],
                            'index': props['index'],
                            'created_at': props['created_at']
                        }
                    })
            
            logger.info(f"Exported {len(features)} blocks to GPKG: {filepath}")
            
        except ImportError as e:
            logger.warning(f"Fiona not available: {e}. Exporting as GeoJSON instead.")
            filepath = os.path.join(temp_dir, f"{forest_name}_compartments_{timestamp}.geojson")
            import json
            with open(filepath, 'w') as f:
                json.dump({"type": "FeatureCollection", "features": features}, f)
            filename = filename.replace('.gpkg', '.geojson')
            
        except Exception as gpkg_err:
            logger.warning(f"GPKG export failed: {gpkg_err}. Exporting as GeoJSON instead.")
            filepath = os.path.join(temp_dir, f"{forest_name}_compartments_{timestamp}.geojson")
            import json
            with open(filepath, 'w') as f:
                json.dump({"type": "FeatureCollection", "features": features}, f)
            filename = filename.replace('.gpkg', '.geojson')
        
        return FileResponse(
            filepath,
            media_type='application/octet-stream',
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export GPKG: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/calculation/{calculation_id}/export-kml")
async def export_blocks_kml(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export all forest blocks and compartments to KML format

    Args:
        calculation_id: Calculation UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        KML file download
    """
    try:
        from shapely.geometry import shape
        from geoalchemy2.shape import to_shape
        
        # Get all blocks
        all_blocks = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == calculation_id
        ).all()

        if not all_blocks:
            raise HTTPException(status_code=404, detail="No blocks found for this calculation")

        # Get forest name for filename
        from app.models.calculation import Calculation
        calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
        forest_name = calculation.forest_name if calculation else "forest"

        # Build features data
        features_data = []
        for block in all_blocks:
            try:
                # Convert geometry to shapely object
                geom_obj = to_shape(block.geometry)
                
                # Get area using PostGIS
                area_result = db.execute(
                    text("SELECT ST_Area(geography(geometry)) as area FROM forest_blocks WHERE id = :block_id"),
                    {"block_id": str(block.id)}
                ).scalar()
                
                # Get perimeter
                perimeter_result = db.execute(
                    text("SELECT ST_Perimeter(geography(geometry)) as perimeter FROM forest_blocks WHERE id = :block_id"),
                    {"block_id": str(block.id)}
                ).scalar()
                
                # Count trees
                tree_count = db.query(InventoryTree).filter(
                    InventoryTree.forest_block_id == block.id
                ).count()
                
                # Get parent block name
                parent_name = None
                if block.parent_block_id:
                    parent_block = db.query(ForestBlock).filter(
                        ForestBlock.id == block.parent_block_id
                    ).first()
                    if parent_block:
                        parent_name = parent_block.name

                features_data.append({
                    'name': block.name,
                    'geometry': mapping(geom_obj),
                    'area_sqm': float(area_result) if area_result else (block.area_sqm or 0),
                    'area_hectares': float(block.area_hectares or 0),
                    'perimeter_m': float(perimeter_result) if perimeter_result else 0,
                    'tree_count': tree_count,
                    'is_compartment': block.is_compartment,
                    'compartment_code': block.compartment_code,
                    'parent_block_name': parent_name,
                    'index': block.index
                })
            except Exception as geom_err:
                logger.error(f"Failed to process block {block.id}: {geom_err}")
                import traceback
                traceback.print_exc()
                continue

        if not features_data:
            raise HTTPException(status_code=500, detail="Failed to process any blocks. Check backend logs.")

        # Generate KML
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{forest_name.replace(' ', '_')}_compartments_{timestamp}.kml"
        
        kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{forest_name}</name>
    <description>Forest Blocks and Compartments Export</description>
    <Style id="blockStyle">
      <LineStyle>
        <color>ff0000ff</color>
        <width>2</width>
      </LineStyle>
      <PolyStyle>
        <color>4d0099ff</color>
        <fill>1</fill>
      </PolyStyle>
    </Style>
    <Style id="compartmentStyle">
      <LineStyle>
        <color>ff00ff00</color>
        <width>2</width>
      </LineStyle>
      <PolyStyle>
        <color>4d00ff00</color>
        <fill>1</fill>
      </PolyStyle>
    </Style>
'''.format(forest_name=forest_name)

        for feature in features_data:
            geom = feature['geometry']
            coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates']
            
            # Format coordinates for KML (lon,lat,alt)
            coord_str = ' '.join([f"{c[0]},{c[1]},0" for c in coords])
            
            style_url = '#compartmentStyle' if feature['is_compartment'] else '#blockStyle'
            
            kml_content += f'''    <Placemark>
      <name>{feature['name']}</name>
      <styleUrl>{style_url}</styleUrl>
      <ExtendedData>
        <Data name="Area_sqm"><value>{feature['area_sqm']:,.2f}</value></Data>
        <Data name="Area_ha"><value>{feature['area_hectares']:.4f}</value></Data>
        <Data name="Perimeter_m"><value>{feature['perimeter_m']:,.2f}</value></Data>
        <Data name="Tree_count"><value>{feature['tree_count']}</value></Data>
        <Data name="Is_Compartment"><value>{'Yes' if feature['is_compartment'] else 'No'}</value></Data>
        <Data name="Compartment_Code"><value>{feature['compartment_code'] or ''}</value></Data>
        <Data name="Parent_Block"><value>{feature['parent_block_name'] or ''}</value></Data>
        <Data name="Index"><value>{feature['index']}</value></Data>
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

        # Write to temp file
        temp_dir = tempfile.mkdtemp()
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(kml_content)

        logger.info(f"Exported {len(features_data)} blocks to KML: {filepath}")

        return FileResponse(
            filepath,
            media_type='application/vnd.google-earth.kml+xml',
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export KML: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/preview-split", response_model=SplitPreviewResponse)
async def preview_split(
    request: SplitPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview compartment split without saving

    Args:
        request: Split preview request
        db: Database session
        current_user: Authenticated user

    Returns:
        Preview of compartments with validation
    """
    try:
        # Get forest block
        block = db.query(ForestBlock).filter(ForestBlock.id == request.block_id).first()
        if not block:
            raise HTTPException(status_code=404, detail="Forest block not found")

        # Check if THIS block already has compartments
        existing_compartments = db.query(ForestBlock).filter(
            ForestBlock.parent_block_id == block.id,
            ForestBlock.is_compartment == True
        ).count()

        if existing_compartments > 0:
            raise HTTPException(
                status_code=400,
                detail="This block already has compartments. Please delete them first or select a different block."
            )

        # Check if ANY other block in this calculation already has compartments
        other_blocks_with_compartments = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == block.calculation_id,
            ForestBlock.id != block.id,
            ForestBlock.is_compartment == False
        ).all()

        for other_block in other_blocks_with_compartments:
            other_compartment_count = db.query(ForestBlock).filter(
                ForestBlock.parent_block_id == other_block.id,
                ForestBlock.is_compartment == True
            ).count()
            if other_compartment_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot create compartments: Block '{other_block.name}' already has {other_compartment_count} compartments. You must delete existing compartments before creating new ones."
                )

        # Convert to Shapely polygon
        polygon = postgis_to_shapely(block.geometry)

        # Perform split based on method
        if request.method == "parallel":
            compartments = CompartmentSplitter.split_parallel_strips(
                polygon,
                request.parameters.get("direction_angle", 0),
                request.parameters.get("num_compartments"),
                request.parameters.get("target_area_sqm"),
                request.parameters.get("min_area_sqm", 1000)
            )
        elif request.method == "grid":
            compartments = CompartmentSplitter.split_grid(
                polygon,
                request.parameters.get("rows", 2),
                request.parameters.get("columns", 2),
                request.parameters.get("min_area_sqm", 1000)
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid split method")

        # Validate split
        validation_result = CompartmentSplitter.validate_split(
            compartments,
            request.parameters.get("min_area_sqm", 1000),
            request.parameters.get("max_deviation_percent", 10)
        )

        # Count trees in each compartment
        tree_counts = []
        for comp in compartments:
            count = CompartmentSplitter.count_trees_in_polygon(db, block.id, comp)
            tree_counts.append(count)

        # Generate preview response
        total_area = sum(c.area for c in compartments)
        target_area = total_area / len(compartments) if compartments else 0

        compartment_previews = []

        for i, comp in enumerate(compartments):
            # Calculate deviation
            deviation = abs((comp.area - target_area) / target_area * 100) if target_area > 0 else 0

            # Convert to square meters (approximate)
            comp_area_sqm = calculate_area_sqm(comp)
            comp_area_ha = comp_area_sqm / 10000

            # Calculate perimeter
            perimeter_m = calculate_perimeter_m(comp)

            compartment_previews.append(CompartmentPreview(
                index=i + 1,
                name=f"{block.name}-C{i+1}",
                geometry=mapping(comp),
                area_sqm=comp_area_sqm,
                area_hectares=comp_area_ha,
                area_deviation_percent=deviation,
                tree_count=tree_counts[i],
                perimeter_m=perimeter_m
            ))

        return SplitPreviewResponse(
            compartments=compartment_previews,
            validation=SplitValidation(**validation_result),
            total_area_sqm=validation_result["total_area_sqm"],
            parent_block_name=block.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview split: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/execute-split", response_model=ExecuteSplitResponse)
async def execute_split(
    request: ExecuteSplitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute compartment split and save to database

    Args:
        request: Split execution request
        db: Database session
        current_user: Authenticated user

    Returns:
        Result of split operation
    """
    try:
        # Get forest block
        block = db.query(ForestBlock).filter(ForestBlock.id == request.block_id).first()
        if not block:
            raise HTTPException(status_code=404, detail="Forest block not found")

        # Check if THIS block already has compartments
        existing_compartments = db.query(ForestBlock).filter(
            ForestBlock.parent_block_id == block.id,
            ForestBlock.is_compartment == True
        ).count()

        if existing_compartments > 0:
            raise HTTPException(
                status_code=400,
                detail="This block already has compartments. Please delete them first or select a different block."
            )

        # Check if ANY other block in this calculation already has compartments
        other_blocks_with_compartments = db.query(ForestBlock).filter(
            ForestBlock.calculation_id == block.calculation_id,
            ForestBlock.id != block.id,
            ForestBlock.is_compartment == False
        ).all()

        for other_block in other_blocks_with_compartments:
            other_compartment_count = db.query(ForestBlock).filter(
                ForestBlock.parent_block_id == other_block.id,
                ForestBlock.is_compartment == True
            ).count()
            if other_compartment_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot create compartments: Block '{other_block.name}' already has {other_compartment_count} compartments. You must delete existing compartments before creating new ones."
                )

        # Convert to Shapely polygon
        polygon = postgis_to_shapely(block.geometry)

        # Perform split
        if request.method == "parallel":
            compartments = CompartmentSplitter.split_parallel_strips(
                polygon,
                request.parameters.get("direction_angle", 0),
                request.parameters.get("num_compartments"),
                request.parameters.get("target_area_sqm"),
                request.parameters.get("min_area_sqm", 1000)
            )
        elif request.method == "grid":
            compartments = CompartmentSplitter.split_grid(
                polygon,
                request.parameters.get("rows", 2),
                request.parameters.get("columns", 2),
                request.parameters.get("min_area_sqm", 1000)
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid split method")

        if not compartments:
            raise HTTPException(status_code=400, detail="Split produced no valid compartments")

        # Create compartment records in database
        compartment_ids = []
        for i, comp_polygon in enumerate(compartments):
            # Generate compartment name
            naming_pattern = request.naming_pattern or "{block_name}-C{index}"
            comp_name = naming_pattern.replace("{block_name}", block.name).replace("{index}", str(i + 1))

            # Calculate area
            comp_area_sqm = calculate_area_sqm(comp_polygon)
            comp_area_ha = comp_area_sqm / 10000

            # Convert to PostGIS geometry
            comp_geom = shapely_to_postgis(comp_polygon)

            # Create ForestBlock record (compartment)
            compartment = ForestBlock(
                calculation_id=block.calculation_id,
                name=comp_name,
                geometry=comp_geom,
                area_hectares=comp_area_ha,
                index=i,
                is_compartment=True,
                parent_block_id=block.id,
                compartment_code=comp_name,
                area_sqm=comp_area_sqm
            )

            db.add(compartment)
            db.flush()  # Get the ID
            compartment_ids.append(compartment.id)

        # Create split history record
        split_history = CompartmentSplitHistory(
            parent_block_id=block.id,
            calculation_id=block.calculation_id,
            split_method=request.method,
            split_direction=request.parameters.get("direction_angle"),
            split_parameters=request.parameters,
            number_of_compartments=len(compartments),
            created_by=current_user.id,
            naming_pattern=request.naming_pattern,
            notes=request.notes
        )

        db.add(split_history)
        db.commit()

        # Reassign trees if requested
        trees_reassigned = 0
        if request.reassign_trees:
            try:
                # Get trees assigned to parent block
                trees_in_block = db.query(InventoryTree).filter(
                    InventoryTree.forest_block_id == block.id
                ).count()

                if trees_in_block > 0:
                    reassignment_result = await auto_assign_trees_by_location(db, block.id)
                    trees_reassigned = reassignment_result["total_assigned"]
            except Exception as e:
                logger.warning(f"Failed to auto-assign trees: {e}")

        return ExecuteSplitResponse(
            split_history_id=split_history.id,
            compartments_created=compartment_ids,
            trees_reassigned=trees_reassigned,
            success=True,
            message=f"Successfully created {len(compartments)} compartments"
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to execute split: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Split execution failed: {str(e)}")


@router.get("/split-directions", response_model=List[SplitDirection])
async def get_split_directions():
    """
    Get preset splitting directions

    Returns:
        List of predefined split directions
    """
    return [
        SplitDirection(name="North-South", angle=0, description="Vertical strips (0°)"),
        SplitDirection(name="East-West", angle=90, description="Horizontal strips (90°)"),
        SplitDirection(name="Northeast-Southwest", angle=45, description="Diagonal (45°)"),
        SplitDirection(name="Northwest-Southeast", angle=135, description="Diagonal (135°)"),
        SplitDirection(name="Optimal (auto)", angle=None, description="Auto-detect based on block shape")
    ]


@router.delete("/block/{block_id}/compartments")
async def delete_compartments_by_block(
    block_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete all compartments for a block and restore trees to parent block

    Args:
        block_id: Parent block UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    try:
        # Get parent block
        parent_block = db.query(ForestBlock).filter(
            ForestBlock.id == block_id
        ).first()

        if not parent_block:
            raise HTTPException(status_code=404, detail="Block not found")

        # Get compartments
        compartments = db.query(ForestBlock).filter(
            ForestBlock.parent_block_id == block_id,
            ForestBlock.is_compartment == True
        ).all()

        if not compartments:
            raise HTTPException(status_code=404, detail="No compartments found for this block")

        compartment_ids = [c.id for c in compartments]

        # Check if trees are associated with these compartments through inventory_calculation
        from app.models.inventory import InventoryCalculation
        
        # Trees in compartments
        trees_in_compartments = db.query(InventoryTree).filter(
            InventoryTree.compartment_id.in_(compartment_ids)
        ).count()

        # Trees through inventory_calculation relationship
        trees_through_inventory = db.query(InventoryTree).join(
            InventoryCalculation, InventoryCalculation.id == InventoryTree.inventory_calculation_id
        ).filter(
            InventoryCalculation.calculation_id == parent_block.calculation_id
        ).count()

        total_trees = trees_in_compartments + trees_through_inventory

        if total_trees > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete compartments: {total_trees} trees are associated with this block. Please delete the tree inventory upload first, then come back to delete the compartments."
            )

        # Delete split history for this block
        split_histories = db.query(CompartmentSplitHistory).filter(
            CompartmentSplitHistory.parent_block_id == block_id
        ).all()
        for history in split_histories:
            db.delete(history)

        # Delete compartments
        for compartment in compartments:
            db.delete(compartment)

        db.commit()

        return {
            "success": True,
            "block_id": str(block_id),
            "block_name": parent_block.name,
            "compartments_deleted": len(compartments)
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete compartments: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.delete("/split/{split_history_id}")
async def undo_split(
    split_history_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Undo a compartment split (delete compartments and restore trees)

    Args:
        split_history_id: Split history UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Success message
    """
    try:
        # Get split history
        split_history = db.query(CompartmentSplitHistory).filter(
            CompartmentSplitHistory.id == split_history_id
        ).first()

        if not split_history:
            raise HTTPException(status_code=404, detail="Split history not found")

        parent_block_id = split_history.parent_block_id

        # Get compartments created by this split
        compartments = db.query(ForestBlock).filter(
            ForestBlock.parent_block_id == parent_block_id,
            ForestBlock.is_compartment == True
        ).all()

        compartment_ids = [c.id for c in compartments]

        # Move trees back to parent block
        trees_moved = 0
        for comp_id in compartment_ids:
            trees = db.query(InventoryTree).filter(
                InventoryTree.compartment_id == comp_id
            ).all()

            for tree in trees:
                tree.forest_block_id = parent_block_id
                tree.compartment_id = None
                trees_moved += 1

        # Delete compartments
        for compartment in compartments:
            db.delete(compartment)

        # Delete split history
        db.delete(split_history)

        db.commit()

        return {
            "success": True,
            "restored_block_id": str(parent_block_id),
            "compartments_deleted": len(compartments),
            "trees_moved_back": trees_moved
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to undo split: {e}")
        raise HTTPException(status_code=500, detail=f"Undo failed: {str(e)}")


@router.get("/calculation/{calculation_id}/trees")
async def get_trees_for_map(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all trees for a calculation to display on map

    Args:
        calculation_id: Calculation UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        List of tree points with metadata
    """
    logger.info(f"[get_trees_for_map] Endpoint called for calculation {calculation_id}")
    
    try:
        from geoalchemy2.shape import to_shape
        from app.models.inventory import InventoryCalculation
        from app.models.field_inventory import FieldInventoryCalculation, FieldInventorySamplePlot, FieldInventoryMeasurement
        
        logger.info(f"[get_trees_for_map] Starting query for calculation {calculation_id}")
        
        tree_features = []
        
        # 1. Debug: Check what InventoryCalculations exist
        all_inv_calcs = db.query(InventoryCalculation).all()
        logger.info(f"[get_trees_for_map] Total InventoryCalculations in DB: {len(all_inv_calcs)}")
        
        for ic in all_inv_calcs:
            logger.info(f"[get_trees_for_map] InventoryCalculation: id={ic.id}, calc_id={ic.calculation_id}, status={ic.status}")
        
        # 1. Get trees from regular inventory (InventoryTree)
        inventory_calcs = db.query(InventoryCalculation).filter(
            InventoryCalculation.calculation_id == calculation_id
        ).all()
        logger.info(f"[get_trees_for_map] Found {len(inventory_calcs)} inventory_calculations for this calculation")
        
        if len(inventory_calcs) == 0:
            # Try without filter to see if calculation_id is being matched
            logger.warning(f"[get_trees_for_map] No inventory_calculations found for calculation_id={calculation_id}")
            # Check if calculation_id matches any
            for ic in all_inv_calcs:
                if str(ic.calculation_id) == str(calculation_id):
                    logger.info(f"[get_trees_for_map] Found match! InventoryCalculation id={ic.id}")
        
        inventory_trees = db.query(InventoryTree).join(
            InventoryCalculation, InventoryCalculation.id == InventoryTree.inventory_calculation_id
        ).filter(
            InventoryCalculation.calculation_id == calculation_id
        ).all()
        logger.info(f"[get_trees_for_map] Found {len(inventory_trees)} trees from regular inventory")
        
        for tree in inventory_trees:
            try:
                location = to_shape(tree.location)
                
                # Calculate DBH class based on diameter
                dbh = float(tree.dia_cm) if tree.dia_cm else 0
                if dbh < 4:
                    dbh_class = 'Regeneration (0.1-4)'
                elif dbh < 10:
                    dbh_class = 'Sapling (4-10)'
                elif dbh < 20:
                    dbh_class = 'Small pole (10-20)'
                elif dbh < 30:
                    dbh_class = 'Large pole (20-30)'
                elif dbh < 40:
                    dbh_class = 'Small tree (30-40)'
                elif dbh < 50:
                    dbh_class = 'Medium tree (40-50)'
                elif dbh < 60:
                    dbh_class = 'Large tree (50-60)'
                else:
                    dbh_class = 'Very large tree (>60)'
                
                tree_features.append({
                    "id": str(tree.id),
                    "latitude": location.y,
                    "longitude": location.x,
                    "species": tree.species or "Unknown",
                    "dbh_cm": float(tree.dia_cm) if tree.dia_cm else 0,
                    "height_m": float(tree.height_m) if tree.height_m else 0,
                    "volume_m3": float(tree.tree_volume) if tree.tree_volume else 0,
                    "dbh_class": dbh_class,
                    "compartment_id": str(tree.compartment_id) if tree.compartment_id else None,
                    "block_id": str(tree.forest_block_id) if tree.forest_block_id else None,
                    "remark": tree.remark,
                    "grid_cell_id": tree.grid_cell_id,
                    "source": "inventory"
                })
            except Exception as tree_err:
                logger.warning(f"[get_trees_for_map] Failed to process inventory tree {tree.id}: {tree_err}")
        
        # 2. Get trees from field inventory (FieldInventoryMeasurement)
        field_calcs = db.query(FieldInventoryCalculation).filter(
            FieldInventoryCalculation.calculation_id == calculation_id
        ).all()
        logger.info(f"[get_trees_for_map] Found {len(field_calcs)} field_inventory_calculations")
        
        if field_calcs:
            field_trees = db.query(FieldInventoryMeasurement).join(
                FieldInventorySamplePlot,
                FieldInventorySamplePlot.id == FieldInventoryMeasurement.sample_plot_id
            ).filter(
                FieldInventorySamplePlot.field_inventory_calculation_id.in_([fc.id for fc in field_calcs])
            ).all()
            logger.info(f"[get_trees_for_map] Found {len(field_trees)} trees from field inventory")
            
            for tree in field_trees:
                try:
                    # Get location from sample plot
                    plot = tree.sample_plot
                    if plot and plot.location:
                        plot_location = to_shape(plot.location)
                        
                        # Calculate DBH class
                        dbh = float(tree.dbh_cm) if tree.dbh_cm else 0
                        if dbh < 4:
                            dbh_class = 'Regeneration (0.1-4)'
                        elif dbh < 10:
                            dbh_class = 'Sapling (4-10)'
                        elif dbh < 20:
                            dbh_class = 'Small pole (10-20)'
                        elif dbh < 30:
                            dbh_class = 'Large pole (20-30)'
                        elif dbh < 40:
                            dbh_class = 'Small tree (30-40)'
                        elif dbh < 50:
                            dbh_class = 'Medium tree (40-50)'
                        elif dbh < 60:
                            dbh_class = 'Large tree (50-60)'
                        else:
                            dbh_class = 'Very large tree (>60)'
                        
                        tree_features.append({
                            "id": str(tree.id),
                            "latitude": plot_location.y,
                            "longitude": plot_location.x,
                            "species": tree.species_scientific or tree.species_local or "Unknown",
                            "dbh_cm": float(tree.dbh_cm) if tree.dbh_cm else 0,
                            "height_m": float(tree.height_m) if tree.height_m else 0,
                            "volume_m3": float(tree.tree_volume) if tree.tree_volume else 0,
                            "dbh_class": dbh_class,
                            "compartment_id": None,
                            "block_id": None,
                            "remark": None,
                            "source": "field_inventory"
                        })
                except Exception as tree_err:
                    logger.warning(f"[get_trees_for_map] Failed to process field tree {tree.id}: {tree_err}")
        
        logger.info(f"[get_trees_for_map] Total trees: {len(tree_features)}")
        
        # Get grid spacing from inventory calculations if available
        grid_spacing = None
        inventory_id = None
        if inventory_calcs:
            ic = inventory_calcs[0]
            grid_spacing = float(ic.grid_spacing_meters) if ic.grid_spacing_meters else None
            inventory_id = str(ic.id)
        
        return {
            "count": len(tree_features),
            "trees": tree_features,
            "grid_spacing_meters": grid_spacing,
            "inventory_id": inventory_id
        }
        
    except Exception as e:
        logger.error(f"[get_trees_for_map] Exception: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trees-needing-assignment/{block_id}")
async def get_trees_needing_assignment_endpoint(
    block_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get trees that need compartment assignment

    Args:
        block_id: Parent block UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Trees and compartments with suggestions
    """
    try:
        result = await get_trees_needing_assignment(db, block_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get trees needing assignment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reassign-trees", response_model=TreeReassignmentResponse)
async def reassign_trees(
    request: TreeReassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reassign trees from parent block to compartments

    Args:
        request: Reassignment request
        db: Database session
        current_user: Authenticated user

    Returns:
        Assignment statistics
    """
    try:
        if request.auto_assign:
            # Auto-assign based on GPS location
            result = await auto_assign_trees_by_location(db, request.block_id)
        elif request.manual_assignments:
            # Manual assignment
            result = await manual_assign_trees(db, request.manual_assignments)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must specify either auto_assign=true or provide manual_assignments"
            )

        return TreeReassignmentResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reassign trees: {e}")
        raise HTTPException(status_code=500, detail=f"Reassignment failed: {str(e)}")
