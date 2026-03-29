"""
Forest management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, text, select
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import json

from ..core.database import get_db
from ..models.user import User
from ..models.community_forest import CommunityForest
from ..models.forest_manager import ForestManager
from ..models.calculation import Calculation, CalculationStatus
from ..models.forest_block import ForestBlock
from ..models.synthetic_tree_model import SyntheticTreeModel
from ..schemas.forest import (
    CommunityForestResponse,
    ForestManagerCreate,
    ForestManagerResponse,
    CalculationResponse,
    MyForestsResponse,
    ReanalysisRequest,
    GenerateMapsRequest,
    AddSpeciesRequest,
    GeometryUpdateRequest,
    SubAreaCreateRequest,
    SubAreaUpdateRequest,
    SubAreaResponse,
    SubAreaListResponse,
    BlockPolygonResponse,
    BlockPolygonListResponse,
    BlockCreateRequest,
    BlockCreateListRequest,
    BlockResponse,
    BlockListResponse,
    DraftSaveRequest,
    DraftResponse,
    DraftDetailResponse,
    ConvertDraftRequest,
)
from ..schemas.map_creation import MapCreationRequest
from ..schemas.tree_model import (
    GenerateTreeModelRequest,
    TreeModelResponse,
    TreeModelListResponse,
    TreeModelConfigBase,
)
from ..utils.auth import get_current_active_user, require_super_admin
try:
    from ..services.file_processor import process_uploaded_file
    FILE_UPLOAD_AVAILABLE = True
except ImportError as e:
    print(f"Warning: File upload disabled due to import error: {e}")
    FILE_UPLOAD_AVAILABLE = False
from ..services.analysis import analyze_forest_boundary
from ..services.fieldbook import generate_fieldbook_points
from ..services.sampling import create_sampling_design
from ..services.map_generator import get_map_generator
from ..services.tree_cover_analysis import calculate_accessible_forest_area, calculate_block_tree_cover_areas
from ..services.map_creation_service import (
    geojson_to_wkt,
    process_map_creation_data,
    validate_map_creation_data,
    prepare_block_analysis_data,
)
from shapely.geometry import mapping, shape
from shapely import wkb
from fastapi.responses import StreamingResponse
import io


router = APIRouter()


def calculate_total_excluded_area(sub_areas: List[Dict]) -> float:
    """
    Calculate total excluded area from all sub-areas.

    Args:
        sub_areas: List of sub-area dictionaries

    Returns:
        Total excluded area in hectares
    """
    total_excluded = 0.0

    for sa in sub_areas:
        is_excluded = sa.get("is_excluded") or sa.get("isExcluded")
        if is_excluded:
            area = sa.get("area_hectares", 0)
            total_excluded += area

    return total_excluded


def calculate_block_excluded_areas(blocks: List[Dict], sub_areas: List[Dict]) -> Dict[str, float]:
    """
    Calculate excluded area for each block, considering sub-areas that span multiple blocks.

    Args:
        blocks: List of block dictionaries with block_id/block_name
        sub_areas: List of sub-area dictionaries with blockBreakdown (optional)

    Returns:
        Dictionary mapping block_id to excluded area in hectares
    """
    block_excluded = {}

    # Initialize all blocks with 0
    for block in blocks:
        block_id = block.get("block_id")
        if block_id:
            block_excluded[block_id] = 0.0

    # Calculate excluded areas
    for sa in sub_areas:
        is_excluded = sa.get("is_excluded") or sa.get("isExcluded")
        if not is_excluded:
            continue

        # Check if sub-area has blockBreakdown (cross-block sub-area)
        block_breakdown = sa.get("blockBreakdown")

        if block_breakdown and len(block_breakdown) > 0:
            # Use blockBreakdown to distribute area across blocks
            for item in block_breakdown:
                block_id = item.get("blockId")
                area = item.get("area", 0)
                if block_id in block_excluded:
                    block_excluded[block_id] += area
                    print(f"  [calc] Block {item.get('blockName')}: +{area:.4f} ha from cross-block sub-area '{sa.get('name')}'")
        else:
            # Fallback: use single block_id (old behavior)
            block_id = sa.get("block_id") or sa.get("blockId")
            area = sa.get("area_hectares", 0)
            if block_id and block_id in block_excluded:
                block_excluded[block_id] += area
                print(f"  [calc] Block {block_id}: +{area:.4f} ha from single-block sub-area '{sa.get('name')}'")

    return block_excluded


@router.get("/community-forests", response_model=List[CommunityForestResponse])
async def list_community_forests(
    search: Optional[str] = None,
    regime: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List community forests from the database

    - **search**: Search by name (case-insensitive)
    - **regime**: Filter by regime type (CF, CFM, etc.)
    - **limit**: Number of results to return (max 1000)
    - **offset**: Number of results to skip for pagination
    """
    query = db.query(CommunityForest)

    # Apply filters
    if search:
        query = query.filter(CommunityForest.name.ilike(f"%{search}%"))
    if regime:
        query = query.filter(CommunityForest.regime == regime)

    # Apply pagination
    query = query.limit(min(limit, 1000)).offset(offset)

    forests = query.all()

    # Convert to response format
    results = []
    for forest in forests:
        results.append({
            "id": forest.id,
            "name": forest.name,
            "code": forest.code,
            "regime": forest.regime,
            "area_hectares": forest.area_hectares,
            "geometry": None  # Don't include full geometry in list view
        })

    return results


@router.get("/community-forests/{forest_id}", response_model=CommunityForestResponse)
async def get_community_forest(forest_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific community forest

    Returns forest metadata and boundary geometry as GeoJSON
    """
    forest = db.query(CommunityForest).filter(CommunityForest.id == forest_id).first()

    if not forest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Community forest with ID {forest_id} not found"
        )

    # Get geometry as GeoJSON
    geojson_query = db.query(
        func.ST_AsGeoJSON(CommunityForest.geom).label("geojson")
    ).filter(CommunityForest.id == forest_id).first()

    geometry = json.loads(geojson_query.geojson) if geojson_query and geojson_query.geojson else None

    return {
        "id": forest.id,
        "name": forest.name,
        "code": forest.code,
        "regime": forest.regime,
        "area_hectares": forest.area_hectares,
        "geometry": geometry
    }


@router.get("/my-forests", response_model=MyForestsResponse)
async def get_my_forests(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get forests assigned to current user

    Returns list of community forests the user manages
    """
    # Query forests assigned to user
    query = db.query(
        CommunityForest,
        ForestManager.role
    ).join(
        ForestManager,
        ForestManager.community_forest_id == CommunityForest.id
    ).filter(
        ForestManager.user_id == current_user.id,
        ForestManager.is_active == True
    )

    results = query.all()

    forests = []
    total_area = 0.0

    for forest, role in results:
        forests.append({
            "id": forest.id,
            "name": forest.name,
            "code": forest.code,
            "regime": forest.regime,
            "area_hectares": forest.area_hectares,
            "role": role
        })
        total_area += forest.area_hectares

    return {
        "forests": forests,
        "total_count": len(forests),
        "total_area_hectares": total_area
    }


@router.post("/assign-manager", response_model=ForestManagerResponse)
async def assign_forest_manager(
    assignment: ForestManagerCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Assign a user to manage a community forest

    Requires super admin privileges
    """
    # Verify user exists
    user = db.query(User).filter(User.id == assignment.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify forest exists
    forest = db.query(CommunityForest).filter(
        CommunityForest.id == assignment.community_forest_id
    ).first()
    if not forest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community forest not found"
        )

    # Check if assignment already exists
    existing = db.query(ForestManager).filter(
        ForestManager.user_id == assignment.user_id,
        ForestManager.community_forest_id == assignment.community_forest_id
    ).first()

    if existing:
        # Update existing assignment
        existing.role = assignment.role
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    # Create new assignment
    new_assignment = ForestManager(
        user_id=assignment.user_id,
        community_forest_id=assignment.community_forest_id,
        role=assignment.role
    )

    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)

    return new_assignment


@router.post("/upload", response_model=CalculationResponse, status_code=status.HTTP_201_CREATED)
async def upload_forest_boundary(
    file: UploadFile = File(...),
    forest_name: str = Form(...),
    block_name: Optional[str] = Form(None),
    # Analysis options (all optional, default True for backward compatibility)
    run_raster_analysis: bool = Form(True),
    run_elevation: bool = Form(True),
    run_slope: bool = Form(True),
    run_aspect: bool = Form(True),
    run_canopy: bool = Form(True),
    run_biomass: bool = Form(True),
    run_forest_health: bool = Form(True),
    run_forest_type: bool = Form(True),
    run_landcover: bool = Form(True),
    run_forest_loss: bool = Form(True),
    run_forest_gain: bool = Form(True),
    run_fire_loss: bool = Form(True),
    run_temperature: bool = Form(True),
    run_precipitation: bool = Form(True),
    run_soil: bool = Form(True),
    run_proximity: bool = Form(True),
    auto_generate_fieldbook: bool = Form(True),
    auto_generate_sampling: bool = Form(True),
    # Map generation options (all optional, default False for on-demand generation)
    generate_boundary_map: bool = Form(False),
    generate_topographic_map: bool = Form(False),
    generate_slope_map: bool = Form(False),
    generate_aspect_map: bool = Form(False),
    generate_forest_type_map: bool = Form(False),
    generate_canopy_height_map: bool = Form(False),
    generate_landcover_change_map: bool = Form(False),
    generate_soil_map: bool = Form(False),
    generate_forest_health_map: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload forest boundary file for analysis

    Supported formats: Shapefile (.shp/.zip), KML, GeoJSON

    The file will be processed to extract geometry and prepare for analysis

    - **forest_name**: Required - Name of the forest (mandatory)
    - **block_name**: Optional - Name of the block

    Analysis Options (all default to True):
    - **run_raster_analysis**: Run all raster analyses (if False, skips all raster)
    - **run_elevation, run_slope, run_aspect**: Terrain analyses
    - **run_canopy, run_biomass, run_forest_health**: Forest structure
    - **run_forest_type, run_landcover**: Classification
    - **run_forest_loss, run_forest_gain, run_fire_loss**: Change detection
    - **run_temperature, run_precipitation, run_soil**: Climate & soil
    - **run_proximity**: Vector proximity analysis
    - **auto_generate_fieldbook, auto_generate_sampling**: Auto-generation

    Map Generation Options (all default to False for on-demand):
    - **generate_boundary_map**: Boundary map with context
    - **generate_topographic_map**: Elevation contours map
    - **generate_slope_map**: Slope classification map
    - **generate_aspect_map**: Aspect/direction map
    - **generate_forest_type_map**: Forest type classification map
    - **generate_canopy_height_map**: Canopy height structure map
    - **generate_landcover_change_map**: Land cover change map
    - **generate_soil_map**: Soil texture map
    - **generate_forest_health_map**: Forest health map
    """
    # Check if file upload is available
    if not FILE_UPLOAD_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="File upload functionality is temporarily disabled due to missing dependencies (GDAL/pyproj). Please contact support."
        )

    # Process uploaded file
    try:
        wkt, metadata = await process_uploaded_file(file)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )

    # Prepare blocks data for JSONB storage
    blocks_data = []
    if 'blocks' in metadata:
        for block in metadata['blocks']:
            blocks_data.append({
                'block_index': block['index'],
                'block_name': block['name'],
                'area_sqm': block['area_sqm'],
                'area_hectares': block['area_hectares'],
                'geometry': mapping(block['geometry']),  # Convert to GeoJSON
                'centroid': {
                    'lon': block['centroid'].x,
                    'lat': block['centroid'].y
                }
            })

    # Prepare result_data with blocks information
    result_data = {
        'total_blocks': metadata.get('block_count', 1),
        'blocks': blocks_data,
        'processing_info': {
            'partitioned': metadata.get('partitioned', False),
            'partition_info': metadata.get('partition_info', {})
        }
    }

    # Build analysis options dict (for saving to database)
    analysis_options_dict = {
        'run_raster_analysis': run_raster_analysis,
        'run_elevation': run_elevation,
        'run_slope': run_slope,
        'run_aspect': run_aspect,
        'run_canopy': run_canopy,
        'run_biomass': run_biomass,
        'run_forest_health': run_forest_health,
        'run_forest_type': run_forest_type,
        'run_landcover': run_landcover,
        'run_forest_loss': run_forest_loss,
        'run_forest_gain': run_forest_gain,
        'run_fire_loss': run_fire_loss,
        'run_temperature': run_temperature,
        'run_precipitation': run_precipitation,
        'run_soil': run_soil,
        'run_proximity': run_proximity,
        'auto_generate_fieldbook': auto_generate_fieldbook,
        'auto_generate_sampling': auto_generate_sampling,
    }

    # Build map options dict (for saving to database)
    map_options_dict = {
        'generate_boundary_map': generate_boundary_map,
        'generate_topographic_map': generate_topographic_map,
        'generate_slope_map': generate_slope_map,
        'generate_aspect_map': generate_aspect_map,
        'generate_forest_type_map': generate_forest_type_map,
        'generate_canopy_height_map': generate_canopy_height_map,
        'generate_landcover_change_map': generate_landcover_change_map,
        'generate_soil_map': generate_soil_map,
        'generate_forest_health_map': generate_forest_health_map,
    }

    # Create calculation record with WKT geometry and user options
    # Always set to PENDING to let user review/finalize blocks and sub-areas before analysis
    # User can skip block naming for single polygons, but still has the option to add sub-areas
    initial_status = CalculationStatus.PENDING
    
    calculation = Calculation(
        user_id=current_user.id,
        uploaded_filename=file.filename,
        boundary_geom=func.ST_GeomFromText(wkt, 4326),
        forest_name=forest_name,  # Now mandatory from form
        block_name=block_name or (blocks_data[0]['block_name'] if blocks_data else "Block 1"),
        status=initial_status,
        result_data=result_data,
        analysis_options=analysis_options_dict,
        map_options=map_options_dict
    )

    db.add(calculation)
    db.commit()
    db.refresh(calculation)

    # Get the calculation ID
    calc_id = calculation.id

    # Note: Analysis is NOT started here - it should be triggered separately from Analysis page
    # User will configure blocks first, then trigger analysis when ready

    # Re-query calculation to ensure we have fresh data
    calculation = db.query(Calculation).filter(Calculation.id == calc_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found after processing"
        )

    # Get geometry as GeoJSON
    geometry_json = None
    try:
        # First check if geometry is valid
        validity_check = db.query(
            func.ST_IsValid(Calculation.boundary_geom).label("is_valid")
        ).filter(Calculation.id == calc_id).first()
        
        if validity_check and not validity_check.is_valid:
            print(f"WARNING: Geometry for calculation {calc_id} is invalid in database")
        
        geojson_query = db.query(
            func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
        ).filter(Calculation.id == calc_id).first()

        if geojson_query and geojson_query.geojson:
            geometry_json = json.loads(geojson_query.geojson)
            print(f"Successfully converted geometry to GeoJSON for calculation {calc_id}")
        else:
            print(f"WARNING: No geometry found for calculation {calc_id}")
    except Exception as e:
        print(f"ERROR: Failed to convert geometry to GeoJSON for calculation {calc_id}: {e}")

    # Filter out removed species from potential_species
    result_data = calculation.result_data or {}
    if result_data:
        # Make a copy to avoid modifying the database object
        result_data = dict(result_data)

        # Get list of removed species
        removed_species = result_data.get("removed_species", [])

        # Filter potential_species to exclude removed ones
        if "potential_species" in result_data and removed_species:
            result_data["potential_species"] = [
                sp for sp in result_data["potential_species"]
                if sp.get("scientific_name") not in removed_species
            ]
            # Update count
            result_data["species_count"] = len(result_data["potential_species"])

    return CalculationResponse(
        id=calculation.id,
        user_id=calculation.user_id,
        uploaded_filename=calculation.uploaded_filename,
        forest_name=calculation.forest_name,
        block_name=calculation.block_name,
        status=calculation.status,
        processing_time_seconds=calculation.processing_time_seconds,
        error_message=calculation.error_message,
        created_at=calculation.created_at,
        completed_at=calculation.completed_at,
        geometry=geometry_json,
        result_data=result_data
    )


@router.post("/create-from-map", response_model=CalculationResponse, status_code=status.HTTP_201_CREATED)
async def create_forest_from_map(
    request: MapCreationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create forest boundary through interactive map creation

    Allows users to create forest boundaries by:
    - Drawing on map directly
    - Auto-creating from GPS points
    - Splitting into blocks
    - Defining sub-areas

    The created boundary will be analyzed the same way as uploaded files.
    """
    import datetime

    # Validate map creation data
    validation_result = validate_map_creation_data(
        request.outer_boundary,
        [block.model_dump() for block in request.blocks]
    )

    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {'; '.join(validation_result['errors'])}"
        )

    # Process map creation data
    try:
        boundary_wkt, metadata = process_map_creation_data(
            request.outer_boundary,
            [block.model_dump() for block in request.blocks],
            gps_points=[point.model_dump() for point in request.gps_points] if request.gps_points else None,
            sub_areas=[area.model_dump() for area in request.sub_areas] if request.sub_areas else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Prepare blocks for analysis
    blocks_for_analysis = prepare_block_analysis_data(
        [block.model_dump() for block in request.blocks]
    )

    # Calculate total area from all blocks
    total_area_hectares = sum(block["area_hectares"] for block in blocks_for_analysis)

    # Create initial result_data with blocks
    initial_result_data = {
        "total_blocks": len(blocks_for_analysis),
        "blocks": blocks_for_analysis,
        "creation_method": "map_creation",
        "area_hectares": round(total_area_hectares, 4),
    }

    # Add GPS points and sub-areas to metadata
    if metadata.get("gps_points"):
        initial_result_data["gps_points"] = metadata["gps_points"]
        initial_result_data["gps_points_count"] = metadata["gps_points_count"]

    if metadata.get("sub_areas"):
        initial_result_data["sub_areas"] = metadata["sub_areas"]
        initial_result_data["sub_areas_count"] = metadata["sub_areas_count"]

        # DEBUG LOGGING: Track sub-area geometries
        print(f"\n{'='*60}")
        print(f"📍 SUB-AREAS RECEIVED: {metadata['sub_areas_count']} sub-areas")
        for idx, sub_area in enumerate(metadata["sub_areas"]):
            geom = sub_area.get("geometry", {})
            coords = geom.get("coordinates", [])
            area_ha = sub_area.get("area_hectares", 0)
            category = sub_area.get("category", "unknown")
            name = sub_area.get("name", f"SubArea {idx+1}")

            print(f"  Sub-area #{idx+1}: {name}")
            print(f"    Category: {category}")
            print(f"    Area: {area_ha:.4f} ha")
            print(f"    Geometry type: {geom.get('type', 'unknown')}")
            if coords:
                # Show first coordinate to verify it's not block coordinates
                first_ring = coords[0] if coords else []
                if first_ring and len(first_ring) > 0:
                    first_point = first_ring[0]
                    print(f"    First coordinate: [{first_point[0]:.6f}, {first_point[1]:.6f}]")
                    print(f"    Total points: {len(first_ring)}")
        print(f"{'='*60}\n")

        # Calculate excluded area from sub-areas (use helper for consistency)
        excluded_area = calculate_total_excluded_area(metadata["sub_areas"])
        initial_result_data["excluded_area_hectares"] = round(excluded_area, 4)
        initial_result_data["effective_area_hectares"] = round(total_area_hectares - excluded_area, 4)

        if excluded_area > 0:
            print(f"  Excluded area total: {excluded_area:.4f} ha")
            print(f"  Effective forest area: {initial_result_data['effective_area_hectares']:.4f} ha")

        # Calculate excluded area per block (handles cross-block sub-areas)
            print(f"\n[create-from-map] Calculating per-block excluded areas...")
            block_excluded_map = calculate_block_excluded_areas(blocks_for_analysis, metadata["sub_areas"])

            for block in blocks_for_analysis:
                block_id = block.get("block_id")
                block_name = block.get("block_name")
                block_excluded = block_excluded_map.get(block_id, 0.0)

                block["excluded_area_hectares"] = round(block_excluded, 4)
                original_area = block.get("area_hectares", 0)
                block["effective_area_hectares"] = round(original_area - block_excluded, 4)

                if block_excluded > 0:
                    print(f"  Block '{block_name}': {original_area:.2f} ha - {block_excluded:.2f} ha = {block['effective_area_hectares']:.2f} ha")
    else:
        # No sub-areas: set excluded to 0 and effective = total
        initial_result_data["excluded_area_hectares"] = 0.0
        initial_result_data["effective_area_hectares"] = round(total_area_hectares, 4)
        # Set effective_area_hectares for each block
        for block in blocks_for_analysis:
            block["excluded_area_hectares"] = 0
            block["effective_area_hectares"] = block.get("area_hectares", 0)

    # Create Calculation record
    calculation = Calculation(
        user_id=current_user.id,
        uploaded_filename="map_created_boundary.geojson",
        forest_name=request.forest_name,
        boundary_geom=boundary_wkt,
        status=CalculationStatus.PROCESSING,
        result_data=initial_result_data,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    db.add(calculation)
    db.commit()
    db.refresh(calculation)

    # Status is set to PENDING (ready for analysis to be triggered separately from Analysis page)
    # The calculation is already created with PENDING status
    # Just commit any pending changes to result_data
    print(f"[create-forest-from-map] Forest created with status PENDING. Analysis can be triggered from Analysis page.")
    flag_modified(calculation, "result_data")
    db.commit()
    db.refresh(calculation)

    # Prepare response
    geometry_json = None
    if calculation.boundary_geom:
        try:
            geom_wkb = db.execute(
                text("SELECT ST_AsEWKB(:geom) as geom"),
                {"geom": calculation.boundary_geom}
            ).scalar()
            if geom_wkb:
                geom = wkb.loads(bytes(geom_wkb))
                geometry_json = mapping(geom)
        except Exception as e:
            print(f"Error converting geometry: {e}")

    result_data = calculation.result_data or {}

    # Final verification before returning response
    from app.models.fieldbook import Fieldbook
    final_count = db.query(Fieldbook).filter(Fieldbook.calculation_id == calculation.id).count()
    print(f"✓ Final verification before response: {final_count} fieldbook points in database")

    return CalculationResponse(
        id=calculation.id,
        user_id=calculation.user_id,
        uploaded_filename=calculation.uploaded_filename,
        forest_name=calculation.forest_name,
        block_name=calculation.block_name,
        status=calculation.status,
        processing_time_seconds=calculation.processing_time_seconds,
        error_message=calculation.error_message,
        created_at=calculation.created_at,
        completed_at=calculation.completed_at,
        geometry=geometry_json,
        result_data=result_data
    )


@router.post("/calculations/{calculation_id}/reanalyze", response_model=CalculationResponse)
async def reanalyze_calculation(
    calculation_id: UUID,
    request: ReanalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Re-run analysis on an existing calculation with different options

    This allows users to re-analyze their boundary with different parameters
    without re-uploading the file. Useful for:
    - Enabling analyses that were initially skipped
    - Disabling expensive analyses to save processing time
    - Experimenting with different analysis combinations

    The boundary geometry and forest/block names are preserved.
    Only the analysis results are updated based on new options.
    """
    # Get existing calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership (users can only reanalyze their own calculations, except super admins)
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to reanalyze this calculation"
        )

    # Merge new options with stored options (new options override stored ones)
    stored_options = calculation.analysis_options or {}
    new_options = {}

    # Build analysis options from request (only include non-None values)
    if request.run_raster_analysis is not None:
        new_options['run_raster_analysis'] = request.run_raster_analysis
    if request.run_elevation is not None:
        new_options['run_elevation'] = request.run_elevation
    if request.run_slope is not None:
        new_options['run_slope'] = request.run_slope
    if request.run_aspect is not None:
        new_options['run_aspect'] = request.run_aspect
    if request.run_canopy is not None:
        new_options['run_canopy'] = request.run_canopy
    if request.run_biomass is not None:
        new_options['run_biomass'] = request.run_biomass
    if request.run_forest_health is not None:
        new_options['run_forest_health'] = request.run_forest_health
    if request.run_forest_type is not None:
        new_options['run_forest_type'] = request.run_forest_type
    if request.run_landcover is not None:
        new_options['run_landcover'] = request.run_landcover
    if request.run_forest_loss is not None:
        new_options['run_forest_loss'] = request.run_forest_loss
    if request.run_forest_gain is not None:
        new_options['run_forest_gain'] = request.run_forest_gain
    if request.run_fire_loss is not None:
        new_options['run_fire_loss'] = request.run_fire_loss
    if request.run_temperature is not None:
        new_options['run_temperature'] = request.run_temperature
    if request.run_precipitation is not None:
        new_options['run_precipitation'] = request.run_precipitation
    if request.run_soil is not None:
        new_options['run_soil'] = request.run_soil
    if request.run_proximity is not None:
        new_options['run_proximity'] = request.run_proximity

    # Merge with stored options (new options take precedence)
    analysis_options = {**stored_options, **new_options}

    # Update calculation status to PROCESSING
    calculation.status = CalculationStatus.PROCESSING
    calculation.error_message = None
    db.commit()

    # Run analysis with new options
    try:
        print(f"Starting re-analysis for calculation {calculation_id}")
        print(f"Analysis options: {analysis_options}")

        analysis_results, processing_time = await analyze_forest_boundary(
            calculation_id, db, options=analysis_options
        )
        print(f"Re-analysis completed with {len(analysis_results)} keys")

        # Preserve blocks data from original result_data
        blocks_data = calculation.result_data.get('blocks', []) if calculation.result_data else []
        total_blocks = calculation.result_data.get('total_blocks', 1) if calculation.result_data else 1
        processing_info = calculation.result_data.get('processing_info', {}) if calculation.result_data else {}

        # Merge with new analysis results
        updated_result_data = {
            'total_blocks': total_blocks,
            'blocks': blocks_data,
            'processing_info': processing_info,
            **analysis_results
        }

        # Sanitize data to remove NaN/Infinity values before JSON serialization
        from ..utils.json_utils import sanitize_for_json
        sanitized_result_data = sanitize_for_json(updated_result_data)
        sanitized_analysis_options = sanitize_for_json(analysis_options)

        # Update calculation with new results and options
        update_query = text("""
            UPDATE public.calculations
            SET
                result_data = CAST(:result_data AS jsonb),
                analysis_options = CAST(:analysis_options AS jsonb),
                processing_time_seconds = :processing_time,
                status = :status,
                completed_at = NOW()
            WHERE id = :calc_id
        """)

        db.execute(update_query, {
            "result_data": json.dumps(sanitized_result_data),
            "analysis_options": json.dumps(sanitized_analysis_options),
            "processing_time": processing_time,
            "status": "COMPLETED",
            "calc_id": str(calculation_id)
        })

        db.commit()
        print("Re-analysis update successful")

    except Exception as e:
        db.rollback()
        print(f"Re-analysis failed: {str(e)}")

        # Update status to FAILED
        try:
            calculation.status = CalculationStatus.FAILED
            calculation.error_message = f"Re-analysis failed: {str(e)[:500]}"
            db.commit()
        except Exception as commit_error:
            print(f"Failed to update error status: {commit_error}")
            db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Re-analysis failed: {str(e)}"
        )

    # Refresh calculation
    db.refresh(calculation)

    # Get geometry as GeoJSON
    geojson_query = db.query(
        func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
    ).filter(Calculation.id == calculation_id).first()

    geometry_json = json.loads(geojson_query.geojson) if geojson_query and geojson_query.geojson else None

    # Filter out removed species from potential_species
    result_data = calculation.result_data or {}
    if result_data:
        # Make a copy to avoid modifying the database object
        result_data = dict(result_data)

        # Get list of removed species
        removed_species = result_data.get("removed_species", [])

        # Filter potential_species to exclude removed ones
        if "potential_species" in result_data and removed_species:
            result_data["potential_species"] = [
                sp for sp in result_data["potential_species"]
                if sp.get("scientific_name") not in removed_species
            ]
            # Update count
            result_data["species_count"] = len(result_data["potential_species"])

    return CalculationResponse(
        id=calculation.id,
        user_id=calculation.user_id,
        uploaded_filename=calculation.uploaded_filename,
        forest_name=calculation.forest_name,
        block_name=calculation.block_name,
        status=calculation.status,
        processing_time_seconds=calculation.processing_time_seconds,
        error_message=calculation.error_message,
        created_at=calculation.created_at,
        completed_at=calculation.completed_at,
        geometry=geometry_json,
        result_data=result_data
    )


@router.post("/calculations/{calculation_id}/generate-maps")
async def generate_maps(
    calculation_id: UUID,
    request: GenerateMapsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate maps on-demand for a calculation

    This endpoint generates the selected maps for an existing calculation.
    Maps are generated as A5 PNG files (1748×2480 pixels at 300 DPI) with:
    - Professional cartographic styling
    - Title, legend, scale bar, north arrow
    - Thematic colors and classifications

    Available maps:
    - Boundary Map: Forest boundary with surrounding context
    - Topographic Map: Elevation contours
    - Slope Map: Slope classification (Gentle, Moderate, Steep, Very Steep)
    - Aspect Map: 8-directional aspect distribution
    - Forest Type Map: Forest species classification
    - Canopy Height Map: Forest structure (Open, Medium, Dense, Very Dense)
    - Land Cover Change Map: Historical land cover changes
    - Soil Map: Soil texture classification
    - Forest Health Map: Forest health status (5 classes)

    The endpoint returns download URLs for each generated map.
    """
    # Get existing calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to generate maps for this calculation"
        )

    # Verify calculation is completed
    if calculation.status != CalculationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate maps for calculation with status: {calculation.status.value}. Analysis must be completed first."
        )

    # Verify at least one map type is selected
    map_types_selected = [
        request.generate_boundary_map,
        request.generate_topographic_map,
        request.generate_slope_map,
        request.generate_aspect_map,
        request.generate_forest_type_map,
        request.generate_canopy_height_map,
        request.generate_landcover_change_map,
        request.generate_soil_map,
        request.generate_forest_health_map,
    ]

    if not any(map_types_selected):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one map type must be selected"
        )

    # Build map generation results
    generated_maps = []
    failed_maps = []

    # Map generation functions mapping
    # NOTE: Some maps are not yet implemented
    map_functions = {
        'boundary': ('generate_boundary_map', request.generate_boundary_map),
        'slope': ('generate_slope_map', request.generate_slope_map),
        'aspect': ('generate_aspect_map', request.generate_aspect_map),
        'landcover': ('generate_landcover_map', request.generate_landcover_change_map),
        # TODO: Implement these 5 maps
        # 'topographic': ('generate_topographic_map', request.generate_topographic_map),
        # 'forest_type': ('generate_forest_type_map', request.generate_forest_type_map),
        # 'canopy_height': ('generate_canopy_height_map', request.generate_canopy_height_map),
        # 'soil': ('generate_soil_map', request.generate_soil_map),
        # 'forest_health': ('generate_forest_health_map', request.generate_forest_health_map),
    }

    # TODO: For maps not yet implemented, return "not implemented" status
    not_implemented = []
    if request.generate_topographic_map:
        not_implemented.append('topographic')
    if request.generate_forest_type_map:
        not_implemented.append('forest_type')
    if request.generate_canopy_height_map:
        not_implemented.append('canopy_height')
    if request.generate_soil_map:
        not_implemented.append('soil')
    if request.generate_forest_health_map:
        not_implemented.append('forest_health')

    # Generate requested maps
    for map_type, (function_name, should_generate) in map_functions.items():
        if not should_generate:
            continue

        try:
            print(f"Generating {map_type} map for calculation {calculation_id}")
            # Map is generated dynamically via existing endpoints
            # Maps are not stored but generated on-demand
            generated_maps.append({
                'map_type': map_type,
                'status': 'success',
                'download_url': f"/api/forests/calculations/{calculation_id}/maps/{map_type}"
            })
        except Exception as e:
            print(f"Failed to generate {map_type} map: {e}")
            failed_maps.append({
                'map_type': map_type,
                'status': 'failed',
                'error': str(e)
            })

    # Update map_options in calculation to track what user requested
    updated_map_options = {
        'generate_boundary_map': request.generate_boundary_map,
        'generate_topographic_map': request.generate_topographic_map,
        'generate_slope_map': request.generate_slope_map,
        'generate_aspect_map': request.generate_aspect_map,
        'generate_forest_type_map': request.generate_forest_type_map,
        'generate_canopy_height_map': request.generate_canopy_height_map,
        'generate_landcover_change_map': request.generate_landcover_change_map,
        'generate_soil_map': request.generate_soil_map,
        'generate_forest_health_map': request.generate_forest_health_map,
    }

    # Save updated map options
    calculation.map_options = updated_map_options
    flag_modified(calculation, "map_options")
    db.commit()

    return {
        'calculation_id': str(calculation_id),
        'status': 'success',
        'generated_maps': generated_maps,
        'failed_maps': failed_maps,
        'not_implemented': not_implemented,
        'message': f"Generated {len(generated_maps)} maps successfully. {len(failed_maps)} failed. {len(not_implemented)} not yet implemented."
    }


@router.post("/calculations/{calculation_id}/tree-cover-areas")
async def calculate_and_store_tree_cover_areas(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Calculate tree cover areas for all blocks and store in calculation result_data.

    Uses ratio-based approach to ensure consistency:
    1. Get authoritative boundary area from PostGIS geometry
    2. Count total pixels and tree pixels within boundary
    3. Calculate tree coverage ratio = tree_pixels / total_pixels
    4. Effective area = boundary_area × ratio

    This ensures pixel-based tree cover calculations align with geometry-based areas.

    **Returns:**
    - Block-wise tree cover statistics
    - Stores results in calculation.result_data['tree_cover_areas']
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    from ..models.user import UserRole
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    # Get blocks from result_data
    result_data = calculation.result_data or {}
    blocks = result_data.get("blocks", [])

    if not blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no blocks. Analysis may not be complete."
        )

    # Prepare blocks for tree cover calculation
    # Need to convert GeoJSON to WKT for the service function
    blocks_for_calc = []
    for block in blocks:
        # Try to get geometry in various formats
        block_geom = block.get("geometry_wkt") or block.get("geometry")

        if not block_geom:
            continue

        # Convert to WKT if it's GeoJSON
        try:
            if isinstance(block_geom, dict):
                # It's GeoJSON - convert to WKT
                geom_shape = shape(block_geom)
                block_geom_wkt = geom_shape.wkt
            elif isinstance(block_geom, str):
                # It's already WKT string
                block_geom_wkt = block_geom
            else:
                continue

            blocks_for_calc.append({
                "block_name": block.get("block_name", f"Block {block.get('block_number', '?')}"),
                "geometry": block_geom_wkt
            })
        except Exception as e:
            print(f"Error converting geometry for block {block.get('block_name')}: {e}")
            continue

    if not blocks_for_calc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No blocks with valid geometry found. Total blocks: {len(blocks)}"
        )

    # Calculate tree cover areas
    try:
        tree_cover_results = calculate_block_tree_cover_areas(db, blocks_for_calc)

        # Store in calculation result_data
        if result_data is None:
            result_data = {}

        result_data['tree_cover_areas'] = tree_cover_results
        calculation.result_data = result_data
        flag_modified(calculation, "result_data")
        db.commit()

        return {
            "calculation_id": str(calculation_id),
            "forest_name": calculation.forest_name,
            "total_blocks": len(tree_cover_results),
            "tree_cover_areas": tree_cover_results,
            "message": "Tree cover areas calculated and stored successfully"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating tree cover areas: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/accessible-area")
async def get_accessible_forest_area(
    calculation_id: UUID,
    filter_slope: bool = False,
    max_slope_degrees: float = 45.0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Calculate accessible forest area for calculation blocks.

    Returns area breakdown per block showing:
    - Accessible forest area (tree cover + slope OK)
    - Inaccessible steep forest (tree cover but too steep)
    - Non-forest area

    **Parameters:**
    - `filter_slope`: If True, exclude steep slopes (default: False)
    - `max_slope_degrees`: Maximum slope threshold in degrees (default: 45.0)

    **Note:** Tree cover filtering (ESA WorldCover value=10) is always enabled.
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    from ..models.user import UserRole
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    # Get blocks from result_data
    result_data = calculation.result_data or {}
    blocks = result_data.get("blocks", [])

    if not blocks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no blocks. Analysis may not be complete."
        )

    # Calculate accessible area for each block
    results = []
    for block in blocks:
        block_number = block.get("block_number")
        block_name = block.get("block_name", f"Block {block_number}")
        block_area_ha = block.get("area_hectares", 0)

        # Get block geometry
        block_geom_wkt = block.get("geometry_wkt")
        if not block_geom_wkt:
            # Skip blocks without geometry
            continue

        # Calculate accessible forest area
        try:
            area_info = calculate_accessible_forest_area(
                db=db,
                geometry_wkt=block_geom_wkt,
                filter_tree_cover=True,  # Always filter to tree cover
                filter_slope=filter_slope,
                max_slope_degrees=max_slope_degrees
            )

            results.append({
                "block_name": block_name,
                "block_number": block_number,
                "block_area_ha": block_area_ha,
                **area_info
            })
        except Exception as e:
            # Log error and continue with next block
            print(f"Error calculating accessible area for {block_name}: {e}")
            results.append({
                "block_name": block_name,
                "block_number": block_number,
                "block_area_ha": block_area_ha,
                "error": str(e)
            })

    return {
        "calculation_id": str(calculation_id),
        "forest_name": calculation.forest_name,
        "filter_slope": filter_slope,
        "max_slope_degrees": max_slope_degrees,
        "total_blocks": len(results),
        "blocks": results
    }


@router.get("/calculations/{calculation_id}", response_model=CalculationResponse)
async def get_calculation(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get calculation results by ID

    Users can only access their own calculations unless they are super admin
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    from ..models.user import UserRole
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    # Get geometry as GeoJSON
    geojson_query = db.query(
        func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
    ).filter(Calculation.id == calculation_id).first()

    geometry_json = json.loads(geojson_query.geojson) if geojson_query and geojson_query.geojson else None

    # Filter out removed species from potential_species
    result_data = calculation.result_data or {}
    if result_data:
        # Make a copy to avoid modifying the database object
        result_data = dict(result_data)

        # Get list of removed species
        removed_species = result_data.get("removed_species", [])

        # Filter potential_species to exclude removed ones
        if "potential_species" in result_data and removed_species:
            result_data["potential_species"] = [
                sp for sp in result_data["potential_species"]
                if sp.get("scientific_name") not in removed_species
            ]
            # Update count
            result_data["species_count"] = len(result_data["potential_species"])

    return CalculationResponse(
        id=calculation.id,
        user_id=calculation.user_id,
        uploaded_filename=calculation.uploaded_filename,
        forest_name=calculation.forest_name,
        block_name=calculation.block_name,
        status=calculation.status,
        processing_time_seconds=calculation.processing_time_seconds,
        error_message=calculation.error_message,
        created_at=calculation.created_at,
        updated_at=calculation.updated_at,
        completed_at=calculation.completed_at,
        is_draft=calculation.is_draft,
        geometry=geometry_json,
        result_data=result_data
    )


@router.get("/calculations", response_model=List[CalculationResponse])
async def list_calculations(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List user's calculations

    Returns all calculations for the current user
    """
    query = db.query(Calculation).filter(Calculation.user_id == current_user.id)
    query = query.order_by(Calculation.created_at.desc())
    query = query.limit(limit).offset(offset)

    calculations = query.all()

    results = []
    for calc in calculations:
        results.append(CalculationResponse(
            id=calc.id,
            user_id=calc.user_id,
            uploaded_filename=calc.uploaded_filename,
            forest_name=calc.forest_name,
            block_name=calc.block_name,
            status=calc.status,
            processing_time_seconds=calc.processing_time_seconds,
            error_message=calc.error_message,
            created_at=calc.created_at,
            updated_at=calc.updated_at,
            completed_at=calc.completed_at,
            is_draft=calc.is_draft,
            geometry=None,  # Don't include geometry in list view
            result_data=None  # Don't include full results in list view
        ))

    return results


@router.delete("/calculations/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calculation(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a calculation

    Users can only delete their own calculations
    Note: May be slow for calculations with many fieldbook points (uses ORM cascade)
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this calculation"
        )

    try:
        # Use ORM delete with cascade (slower but more reliable)
        db.delete(calculation)
        db.commit()
        print(f"Successfully deleted calculation {calculation_id}")
    except Exception as e:
        db.rollback()
        print(f"Error deleting calculation {calculation_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete calculation: {str(e)}"
        )

    return None

@router.patch("/calculations/{calculation_id}/result-data")
async def update_result_data(
    calculation_id: UUID,
    update_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update result_data fields for a calculation (field verification edits)

    Users can only update their own calculations.
    Accepts a JSON body with fields to update - merges into existing result_data.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    from ..models.user import UserRole
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this calculation"
        )

    # Merge update_data into existing result_data
    existing = calculation.result_data or {}
    existing.update(update_data)
    calculation.result_data = existing
    flag_modified(calculation, "result_data")

    db.commit()
    db.refresh(calculation)

    return {"status": "updated", "result_data": calculation.result_data}


# ============================================================================
# MAP GENERATION ENDPOINTS
# ============================================================================

@router.get("/calculations/{calculation_id}/maps/boundary")
async def generate_boundary_map(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate boundary map with contextual features (schools, roads, rivers, etc.)

    Returns PNG image (A5 size, 300 DPI)
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_boundary_map(
            geometry=geometry,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto',
            db_session=db,
            show_schools=True,
            show_poi=True,
            show_roads=True,
            show_rivers=True,
            show_ridges=True,
            show_esa_boundary=True,
            buffer_m=100.0
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=boundary_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating boundary map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/slope")
async def generate_slope_map(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate slope classification map

    Returns PNG image (A5 size, 300 DPI) with 5 slope classes
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_slope_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=slope_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating slope map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/aspect")
async def generate_aspect_map(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate aspect (slope direction) map with temperature-based colors

    Returns PNG image (A5 size, 300 DPI) with 9 aspect classes
    North = blue (cold), South = red (warm)
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_aspect_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=aspect_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating aspect map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/landcover")
async def generate_landcover_map(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate ESA WorldCover land cover classification map

    Returns PNG image (A5 size, 300 DPI) with ESA WorldCover classes
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_landcover_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=landcover_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating landcover map: {str(e)}"
        )
@router.get("/calculations/{calculation_id}/maps/topographic")
async def generate_topographic_map_endpoint(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate topographic map with elevation contours

    Returns PNG image (A5 size, 300 DPI) with elevation gradient
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_topographic_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=topographic_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating topographic map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/forest_type")
async def generate_forest_type_map_endpoint(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate forest type map showing species classification

    Returns PNG image (A5 size, 300 DPI) with forest species
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_forest_type_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=forest_type_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating forest type map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/canopy_height")
async def generate_canopy_height_map_endpoint(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate canopy height map showing forest structure

    Returns PNG image (A5 size, 300 DPI) with canopy height classes
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_canopy_height_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=canopy_height_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating canopy height map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/soil")
async def generate_soil_map_endpoint(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate soil texture map from SoilGrids

    Returns PNG image (A5 size, 300 DPI) with soil texture classes
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_soil_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=soil_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating soil map: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/maps/forest_health")
async def generate_forest_health_map_endpoint(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate forest health map showing vegetation health status

    Returns PNG image (A5 size, 300 DPI) with forest health classes
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this calculation"
        )

    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calculation has no boundary geometry"
        )

    try:
        # Convert boundary to GeoJSON
        geom_shape = wkb.loads(bytes(calculation.boundary_geom.data))
        geometry = mapping(geom_shape)

        # Generate map
        map_generator = get_map_generator()
        buffer = map_generator.generate_forest_health_map(
            geometry=geometry,
            db_session=db,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto'
        )

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=forest_health_map_{calculation_id}.png"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating forest health map: {str(e)}"
        )


@router.post("/calculations/{calculation_id}/add-species")
async def add_species_to_calculation(
    calculation_id: UUID,
    request: AddSpeciesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add a species to a calculation's species list

    This endpoint allows users to manually add species that may have been missed
    by the automatic analysis or to include species found during field surveys.

    The species will be added to the calculation's result_data.potential_species list
    with the specified role and availability rank.
    """
    # Get existing calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this calculation"
        )

    # Get species details from database
    species_query = text("""
        SELECT
            id,
            scientific_name,
            local_name,
            family,
            growth_rate,
            min_altitude_m,
            max_altitude_m,
            economic_value,
            main_uses,
            nitrogen_fixing,
            rarity_status,
            ecological_role
        FROM tree_species_coefficients
        WHERE id = :species_id
    """)

    species_result = db.execute(species_query, {"species_id": request.species_id}).fetchone()

    if not species_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Species with ID {request.species_id} not found"
        )

    # Create species data object
    new_species = {
        "scientific_name": species_result.scientific_name,
        "local_name": species_result.local_name or "Unknown",
        "role": request.role,
        "availability_rank": request.availability_rank,
        "economic_value": species_result.economic_value or "Medium",
        "growth_rate": species_result.growth_rate,
        "min_altitude_m": species_result.min_altitude_m,
        "max_altitude_m": species_result.max_altitude_m,
        "main_uses": species_result.main_uses,
        "nitrogen_fixing": species_result.nitrogen_fixing or False,
        "rarity_status": species_result.rarity_status or "Common",
        "family": species_result.family,
        "forest_types": ["User Added"],
        "manually_added": True  # Flag to indicate this was manually added
    }

    # Get current result_data
    result_data = calculation.result_data or {}

    # Initialize potential_species if it doesn't exist
    if "potential_species" not in result_data:
        result_data["potential_species"] = []

    # Check if species already exists
    existing_species = [
        s for s in result_data["potential_species"]
        if s.get("scientific_name") == new_species["scientific_name"]
    ]

    if existing_species:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Species {new_species['scientific_name']} already exists in this calculation"
        )

    # Add new species to the list
    result_data["potential_species"].append(new_species)
    result_data["species_count"] = len(result_data["potential_species"])

    # Update calculation
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")  # Mark JSONB column as modified
    db.commit()
    db.refresh(calculation)

    return {
        "success": True,
        "message": f"Successfully added {new_species['scientific_name']} ({new_species['local_name']}) to the species list",
        "species": new_species,
        "total_species": result_data["species_count"]
    }


@router.delete("/calculations/{calculation_id}/remove-species/{scientific_name}")
async def remove_species_from_calculation(
    calculation_id: UUID,
    scientific_name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Remove a species from the calculation's species list.

    This marks the species as removed by the user. It will not appear
    in future queries for this calculation's species list.

    For system-generated species: Adds to removed_species list
    For manually-added species: Removes from potential_species list
    """
    from datetime import datetime

    # Get calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this calculation"
        )

    # Initialize result_data if needed
    if not calculation.result_data:
        calculation.result_data = {}

    result_data = calculation.result_data

    # Initialize removed_species array if needed
    if "removed_species" not in result_data:
        result_data["removed_species"] = []

    # Check if this is a manually added species
    manually_added = False
    if "potential_species" in result_data:
        for species in result_data["potential_species"]:
            if species.get("scientific_name") == scientific_name:
                if species.get("manually_added"):
                    manually_added = True
                break

    if manually_added:
        # Remove manually-added species completely from the list
        result_data["potential_species"] = [
            sp for sp in result_data["potential_species"]
            if sp.get("scientific_name") != scientific_name
        ]
        result_data["species_count"] = len(result_data["potential_species"])
        message = f"Manually added species '{scientific_name}' removed completely"
    else:
        # For system-generated species, add to removed list
        if scientific_name not in result_data["removed_species"]:
            result_data["removed_species"].append(scientific_name)
        message = f"System-generated species '{scientific_name}' hidden from list"

    # Mark as modified
    result_data["species_list_modified"] = True
    result_data["species_last_modified"] = datetime.utcnow().isoformat()

    # Update calculation
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()
    db.refresh(calculation)

    return {
        "success": True,
        "message": message,
        "removed_species": result_data.get("removed_species", []),
        "manually_added_removed": manually_added
    }


@router.patch("/calculations/{calculation_id}/species/{scientific_name}/confirm")
async def toggle_species_confirmation(
    calculation_id: UUID,
    scientific_name: str,
    request_body: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Toggle species confirmation status.

    Supports block-specific confirmation:
    - If block_name is provided: Only confirms species in that specific block
    - If block_name is None/omitted: Confirms species at whole forest level (not in blocks)

    Confirmed species appear colorful in UI and are included in operational plans.
    Unconfirmed species appear grey and are excluded from final reports.
    """
    from datetime import datetime

    # Get confirmed value and optional block_name from request body
    confirmed = request_body.get("confirmed", False)
    block_name = request_body.get("block_name", None)  # NEW: Optional block identifier

    # Get calculation
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Get result_data
    result_data = calculation.result_data or {}

    # NEW: Block-specific confirmation logic
    if block_name is not None:
        # Confirm species in specific block only
        species_found = False
        if "blocks" in result_data:
            for block in result_data["blocks"]:
                if block.get("block_name") == block_name and "potential_species" in block:
                    for block_species in block["potential_species"]:
                        if block_species.get("scientific_name") == scientific_name:
                            block_species["confirmed"] = confirmed
                            species_found = True
                            break
                    if species_found:
                        break

        if not species_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Species '{scientific_name}' not found in block '{block_name}'"
            )

        # Mark as modified
        result_data["species_list_modified"] = True
        result_data["species_last_modified"] = datetime.utcnow().isoformat()

        # Save
        calculation.result_data = result_data
        flag_modified(calculation, "result_data")
        db.commit()
        db.refresh(calculation)

        return {
            "success": True,
            "message": f"Species '{scientific_name}' {'confirmed' if confirmed else 'unconfirmed'} in {block_name}",
            "confirmed": confirmed,
            "block_name": block_name,
            "scope": "block"
        }

    # Original: Whole forest confirmation (does NOT sync to blocks anymore)
    if "potential_species" not in result_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No species data found"
        )

    # Find and update species in whole forest list ONLY
    species_found = False
    for species in result_data["potential_species"]:
        if species.get("scientific_name") == scientific_name:
            species["confirmed"] = confirmed
            species_found = True
            break

    if not species_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Species not found in whole forest list"
        )

    # REMOVED: No longer syncs to blocks automatically
    # Each block maintains independent species confirmations

    # Mark as modified
    result_data["species_list_modified"] = True
    result_data["species_last_modified"] = datetime.utcnow().isoformat()

    # Save
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()
    db.refresh(calculation)

    # Count confirmed species (whole forest level)
    removed = result_data.get("removed_species", [])
    confirmed_count = sum(1 for sp in result_data["potential_species"]
                         if sp.get("confirmed", False) and
                         sp.get("scientific_name") not in removed)

    return {
        "success": True,
        "message": f"Species '{scientific_name}' {'confirmed' if confirmed else 'unconfirmed'} at whole forest level",
        "confirmed": confirmed,
        "confirmed_count": confirmed_count,
        "total_species": len([sp for sp in result_data["potential_species"]
                             if sp.get("scientific_name") not in removed]),
        "scope": "whole_forest"
    }


@router.post("/calculations/{calculation_id}/species/confirm-all")
async def confirm_all_species(
    calculation_id: UUID,
    request_body: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Confirm or unconfirm all species at once.
    Useful for 'Confirm All' or 'Clear All' buttons.
    """
    from datetime import datetime

    # Get confirmed value from request body
    confirmed = request_body.get("confirmed", False)

    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    result_data = calculation.result_data or {}

    if "potential_species" not in result_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No species data found"
        )

    # Update all species in whole forest list
    for species in result_data["potential_species"]:
        species["confirmed"] = confirmed

    # PHASE 1: Sync confirmation to all blocks
    blocks_updated = 0
    if "blocks" in result_data:
        for block in result_data["blocks"]:
            if "potential_species" in block:
                for block_species in block["potential_species"]:
                    block_species["confirmed"] = confirmed
                    blocks_updated += 1

    # Mark as modified
    result_data["species_list_modified"] = True
    result_data["species_last_modified"] = datetime.utcnow().isoformat()

    # Save
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()

    removed = result_data.get("removed_species", [])
    affected_count = len([sp for sp in result_data["potential_species"]
                         if sp.get("scientific_name") not in removed])

    return {
        "success": True,
        "message": f"{'Confirmed' if confirmed else 'Unconfirmed'} {affected_count} species",
        "count": affected_count
    }


@router.get("/calculations/{calculation_id}/species-summary")
async def get_species_summary(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get whole forest species summary auto-calculated from block-level confirmations.

    Returns:
    - Total species count
    - Species-by-species statistics (which blocks, coverage %, confirmed count)
    - Role distribution
    - Confirmation statistics
    """

    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    result_data = calculation.result_data or {}
    blocks = result_data.get("blocks", [])
    removed_species = result_data.get("removed_species", [])

    # Build species map from all blocks
    species_map = {}
    total_blocks = len(blocks)

    for block_idx, block in enumerate(blocks):
        block_species_list = block.get("potential_species", [])

        for species in block_species_list:
            scientific_name = species.get("scientific_name")

            # Skip removed species
            if scientific_name in removed_species:
                continue

            if scientific_name not in species_map:
                species_map[scientific_name] = {
                    "scientific_name": scientific_name,
                    "local_name": species.get("local_name"),
                    "family": species.get("family"),
                    "economic_value": species.get("economic_value"),
                    "growth_rate": species.get("growth_rate"),
                    "min_altitude_m": species.get("min_altitude_m"),
                    "max_altitude_m": species.get("max_altitude_m"),
                    "nitrogen_fixing": species.get("nitrogen_fixing"),
                    "blocks": [],
                    "block_indices": [],
                    "roles": set(),
                    "confirmed_in_blocks": 0,
                    "unconfirmed_in_blocks": 0
                }

            # Track which blocks this species appears in
            block_name = block.get("block_name", f"Block {block_idx + 1}")
            species_map[scientific_name]["blocks"].append(block_name)
            species_map[scientific_name]["block_indices"].append(block_idx)

            # Track roles
            role = species.get("role", "Associate")
            species_map[scientific_name]["roles"].add(role)

            # Track confirmation status per block
            if species.get("confirmed", False):
                species_map[scientific_name]["confirmed_in_blocks"] += 1
            else:
                species_map[scientific_name]["unconfirmed_in_blocks"] += 1

    # Convert to list with calculated statistics
    species_summary = []
    for species_data in species_map.values():
        present_in_blocks = len(species_data["blocks"])
        coverage_percentage = (present_in_blocks / total_blocks * 100) if total_blocks > 0 else 0

        species_summary.append({
            "scientific_name": species_data["scientific_name"],
            "local_name": species_data["local_name"],
            "family": species_data["family"],
            "economic_value": species_data["economic_value"],
            "growth_rate": species_data["growth_rate"],
            "min_altitude_m": species_data["min_altitude_m"],
            "max_altitude_m": species_data["max_altitude_m"],
            "nitrogen_fixing": species_data["nitrogen_fixing"],
            "blocks": species_data["blocks"],
            "block_indices": species_data["block_indices"],
            "present_in_blocks": present_in_blocks,
            "total_blocks": total_blocks,
            "coverage_percentage": round(coverage_percentage, 1),
            "roles": sorted(list(species_data["roles"])),
            "confirmed_in_blocks": species_data["confirmed_in_blocks"],
            "unconfirmed_in_blocks": species_data["unconfirmed_in_blocks"],
            "confirmed": species_data["confirmed_in_blocks"] > 0  # At least one block confirmed
        })

    # Sort by coverage percentage (descending)
    species_summary.sort(key=lambda x: x["coverage_percentage"], reverse=True)

    # Calculate statistics
    total_species = len(species_summary)
    confirmed_species = sum(1 for s in species_summary if s["confirmed"])
    unconfirmed_species = total_species - confirmed_species

    # Role distribution
    role_counts = {}
    for species in species_summary:
        for role in species["roles"]:
            role_counts[role] = role_counts.get(role, 0) + 1

    return {
        "total_species": total_species,
        "confirmed_species": confirmed_species,
        "unconfirmed_species": unconfirmed_species,
        "total_blocks": total_blocks,
        "species_details": species_summary,
        "role_distribution": role_counts,
        "confirmation_stats": {
            "confirmed": confirmed_species,
            "unconfirmed": unconfirmed_species,
            "percentage_confirmed": round((confirmed_species / total_species * 100) if total_species > 0 else 0, 1)
        }
    }


# ============================================================================
# GEOMETRY & SUB-AREA EDITING ENDPOINTS
# ============================================================================

@router.patch("/calculations/{calculation_id}/geometry")
async def update_calculation_geometry(
    calculation_id: UUID,
    request: GeometryUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update the boundary geometry of a calculation.

    This allows users to edit the forest boundary by:
    - Drawing new polygons
    - Modifying existing geometry
    - Uploading corrected boundary files

    Optionally triggers re-analysis after the geometry update.
    """
    from shapely.geometry import shape
    from shapely.validation import make_valid

    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    try:
        # Convert GeoJSON to Shapely geometry
        geom = shape(request.geometry)

        # Make geometry valid (fix self-intersections, etc.)
        if not geom.is_valid:
            geom = make_valid(geom)

        # Ensure it's a polygon/multipolygon
        if geom.geom_type == "LineString":
            geom = geom.buffer(0)
        elif geom.geom_type == "Point":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geometry must be a polygon or multipolygon"
            )

        # Convert back to GeoJSON and then to WKT for PostGIS
        geom_geojson = mapping(geom)

        # Calculate area
        area_sqm = geom.area
        area_hectares = area_sqm / 10000

        # Update boundary geometry in database
        update_query = text("""
            UPDATE public.calculations
            SET boundary_geom = ST_GeomFromText(:wkt, 4326)
            WHERE id = :calc_id
        """)

        db.execute(update_query, {
            "wkt": geom.wkt,
            "calc_id": str(calculation_id)
        })

        # Update result_data with new geometry info
        result_data = calculation.result_data or {}
        result_data["geometry_updated"] = True
        result_data["geometry_update_area_hectares"] = round(area_hectares, 4)
        calculation.result_data = result_data
        flag_modified(calculation, "result_data")

        # Update status to indicate geometry was modified
        calculation.status = CalculationStatus.COMPLETED  # Keep completed, but geometry is modified
        db.commit()

        # Optionally run re-analysis
        if request.reanalyze:
            # Set status to processing
            calculation.status = CalculationStatus.PROCESSING
            db.commit()

            # Get existing analysis options
            analysis_options = calculation.analysis_options or {}

            try:
                analysis_results, processing_time = await analyze_forest_boundary(
                    calculation_id, db, options=analysis_options
                )

                # Preserve sub-areas and blocks from original data
                blocks_data = result_data.get('blocks', [])
                sub_areas = result_data.get('sub_areas', [])

                # Merge analysis results
                updated_result_data = {
                    'blocks': blocks_data,
                    'sub_areas': sub_areas,
                    'geometry_updated': True,
                    'geometry_update_area_hectares': round(area_hectares, 4),
                    **analysis_results
                }

                # Update calculation
                update_result_query = text("""
                    UPDATE public.calculations
                    SET
                        result_data = CAST(:result_data AS jsonb),
                        processing_time_seconds = :processing_time,
                        status = :status,
                        completed_at = NOW()
                    WHERE id = :calc_id
                """)

                db.execute(update_result_query, {
                    "result_data": json.dumps(updated_result_data),
                    "processing_time": processing_time,
                    "status": "COMPLETED",
                    "calc_id": str(calculation_id)
                })

                db.commit()
                print(f"Re-analysis completed after geometry update for calculation {calculation_id}")

            except Exception as e:
                print(f"Re-analysis failed after geometry update: {e}")
                # Still return success, but include warning
                calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
                calculation.status = CalculationStatus.COMPLETED
                db.commit()

        # Get updated geometry as GeoJSON
        geojson_query = db.query(
            func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
        ).filter(Calculation.id == calculation_id).first()

        geometry_json = json.loads(geojson_query.geojson) if geojson_query and geojson_query.geojson else None

        return {
            "success": True,
            "message": "Geometry updated successfully" + (" and re-analysis completed" if request.reanalyze else ""),
            "calculation_id": str(calculation_id),
            "area_hectares": round(area_hectares, 4),
            "geometry": geometry_json
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update geometry: {str(e)}"
        )


@router.post("/calculations/{calculation_id}/sub-areas", response_model=SubAreaResponse)
async def add_sub_area(
    calculation_id: UUID,
    request: SubAreaCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add a sub-area to an existing calculation.

    Sub-areas are special zones within the forest boundary:
    - Protected Zone (protected)
    - Plantation Area (plantation)
    - Pro-Poor Income Generation (pro-poor)
    - Religious Area (religious)
    - Bio-diversity Rich (biodiversity)
    - Tourist Attraction (tourist)
    - Office Area (office)
    - Private Land (Excluded) (private_land)

    Private land is excluded from forest area calculations.
    """
    from datetime import datetime
    from shapely.geometry import shape
    from shapely.validation import make_valid
    import uuid

    # Debug logging
    print(f"\n[add_sub_area] Received request:")
    print(f"  name: {request.name}")
    print(f"  category: {request.category}")
    print(f"  block_id: {request.block_id}")
    print(f"  block_name: {request.block_name}")
    print(f"  block_breakdown: {request.block_breakdown}")
    print(f"  is_excluded: {request.is_excluded}")
    print(f"  area_hectares: {request.area_hectares}")
    if request.block_breakdown:
        print(f"  block_breakdown items: {len(request.block_breakdown)}")
        for item in request.block_breakdown:
            print(f"    - blockId: {item.blockId}, blockName: {item.blockName}, area: {item.area}, percentage: {item.percentage}")

    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Validate category
    valid_categories = ["protected", "plantation", "pro-poor", "religious", "biodiversity", "tourist", "office", "private_land"]
    if request.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    try:
        # Convert GeoJSON to Shapely geometry
        geom = shape(request.geometry)
        print(f"[add_sub_area] Input geometry type: {geom.geom_type}")
        print(f"[add_sub_area] Input geometry area: {geom.area}")

        # Make geometry valid
        if not geom.is_valid:
            geom = make_valid(geom)

        # Ensure it's a polygon
        if geom.geom_type == "MultiPolygon":
            geom = geom.buffer(0)
        elif geom.geom_type not in ["Polygon", "MultiPolygon"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geometry must be a polygon or multipolygon"
            )

        # Get the boundary geometry and clip the sub-area to it
        boundary_wkb = db.query(Calculation.boundary_geom).filter(Calculation.id == calculation_id).first()
        if boundary_wkb and boundary_wkb[0]:
            from shapely.wkb import loads as load_wkb
            boundary_geom = load_wkb(bytes(boundary_wkb[0].data))
            
            # Calculate original area before clipping
            original_area_sqm = geom.area
            
            # Clip sub-area to boundary (intersection)
            clipped_geom = geom.intersection(boundary_geom)
            
            if clipped_geom.is_empty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sub-area is outside the forest boundary"
                )
            
            # Replace original with clipped geometry
            geom = clipped_geom
            print(f"Sub-area clipped: original area={original_area_sqm/10000:.2f}ha, clipped={geom.area/10000:.2f}ha")

        # Calculate area (after clipping) using accurate geodesic calculation
        # Import the helper function
        from ..utils.geometry_utils import calculate_area_geodesic_from_shapely

        # Use provided area if available (from frontend calculation which may use turf.js)
        if request.area_hectares and request.area_hectares > 0:
            area_hectares = request.area_hectares
            area_sqm = area_hectares * 10000
            print(f"[add_sub_area] Using PROVIDED area: {area_hectares} ha (from request)")
        else:
            # Calculate using UTM projection for accuracy
            area_sqm, area_hectares = calculate_area_geodesic_from_shapely(geom)
            print(f"[add_sub_area] Using CALCULATED geodesic area: {area_hectares} ha")

        # Generate unique ID
        sub_area_id = str(uuid.uuid4())

        # Create sub-area object
        new_sub_area = {
            "id": sub_area_id,
            "name": request.name,
            "category": request.category,
            "geometry": mapping(geom),
            "area_sqm": round(area_sqm, 4),
            "area_hectares": round(area_hectares, 4),
            "blockId": request.block_id,
            "blockName": request.block_name,
            "blockBreakdown": [item.model_dump() for item in request.block_breakdown] if request.block_breakdown else None,
            "isExcluded": request.is_excluded,
            "created_at": datetime.now().isoformat()
        }

        # Get or initialize result_data
        result_data = calculation.result_data or {}

        # Initialize sub_areas array if needed
        if "sub_areas" not in result_data:
            result_data["sub_areas"] = []

        # Add new sub-area
        result_data["sub_areas"].append(new_sub_area)
        result_data["sub_areas_count"] = len(result_data["sub_areas"])

        print(f"[add_sub_area] Added sub-area {sub_area_id}, total now: {len(result_data['sub_areas'])}")

        # Recalculate total excluded area from scratch (avoids accumulation errors)
        excluded_total = calculate_total_excluded_area(result_data["sub_areas"])
        result_data["excluded_area_hectares"] = round(excluded_total, 4)

        # Recalculate effective_area_hectares at forest level
        total_area = result_data.get("area_hectares", 0)
        result_data["effective_area_hectares"] = round(total_area - excluded_total, 4)

        # Recalculate per-block excluded and effective areas (handles cross-block sub-areas)
        blocks = result_data.get("blocks", [])
        block_excluded_map = calculate_block_excluded_areas(blocks, result_data["sub_areas"])

        for block in blocks:
            block_id = block.get("block_id")
            block_excluded = block_excluded_map.get(block_id, 0.0)

            block["excluded_area_hectares"] = round(block_excluded, 4)
            original_area = block.get("area_hectares", 0)
            block["effective_area_hectares"] = round(original_area - block_excluded, 4)

        result_data["blocks"] = blocks

        # Update calculation
        calculation.result_data = result_data
        flag_modified(calculation, "result_data")
        db.commit()
        db.refresh(calculation)

        print(f"[add_sub_area] Updated totals - excluded: {excluded_total:.4f} ha, effective: {result_data['effective_area_hectares']:.4f} ha")

        return SubAreaResponse(
            id=sub_area_id,
            name=request.name,
            category=request.category,
            geometry=mapping(geom),
            area_hectares=round(area_hectares, 4),
            block_id=request.block_id,
            block_name=request.block_name,
            block_breakdown=request.block_breakdown,
            is_excluded=request.is_excluded
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        db.rollback()
        print(f"[add_sub_area] ERROR: {str(e)}")
        print(f"[add_sub_area] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add sub-area: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/sub-areas", response_model=SubAreaListResponse)
async def list_sub_areas(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all sub-areas for a calculation.
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Get sub-areas from result_data
    result_data = calculation.result_data or {}
    sub_areas = result_data.get("sub_areas", [])
    
    print(f"[list_sub_areas] Calculation {calculation_id}: found {len(sub_areas)} sub-areas in result_data")
    if sub_areas:
        print(f"[list_sub_areas] First sub-area keys: {sub_areas[0].keys()}")
        print(f"[list_sub_areas] First sub-area area_hectares: {sub_areas[0].get('area_hectares')}")
        print(f"[list_sub_areas] First sub-area full: {sub_areas[0]}")

    # Convert to response format
    sub_area_responses = []
    total_area = 0

    for sa in sub_areas:
        # Convert geometry to GeoJSON if it's stored as Shapely mapping
        geom = sa.get("geometry")
        geometry_json = {}
        sa_area = sa.get("area_hectares", 0)
        
        if geom:
            from shapely.geometry import mapping as shapely_mapping
            from shapely.wkb import loads as load_wkb
            
            # Check if it's WKB (bytes) or already GeoJSON
            if isinstance(geom, bytes):
                try:
                    shapely_geom = load_wkb(geom)
                    geometry_json = shapely_mapping(shapely_geom)
                except:
                    geometry_json = {}
            elif isinstance(geom, dict):
                geometry_json = geom
            else:
                geometry_json = {}
            
            # If area is 0 or very small, recalculate from geometry
            if sa_area < 0.001 and geometry_json:
                try:
                    from shapely.geometry import shape
                    from shapely.ops import transform
                    import pyproj
                    
                    # Get geometry and calculate centroid for UTM zone
                    geom_obj = shape(geometry_json)
                    if not geom_obj.is_empty:
                        centroid = geom_obj.centroid
                        utm_srid = 32644 if centroid.x < 84 else 32645
                        
                        # Project to UTM and calculate area
                        project = pyproj.Transformer.from_crs(
                            "EPSG:4326", 
                            f"EPSG:{utm_srid}", 
                            always_xy=True
                        ).transform
                        geom_utm = transform(project, geom_obj)
                        sa_area = geom_utm.area / 10000
                        print(f"[list_sub_areas] Recalculated area for {sa.get('name')}: {sa_area:.4f} ha")
                except Exception as e:
                    print(f"[list_sub_areas] Error recalculating area: {e}")
        
        # Get blockBreakdown if exists
        block_breakdown = sa.get("blockBreakdown")
        block_breakdown_items = None
        if block_breakdown:
            from ..schemas.forest import BlockBreakdownItem
            block_breakdown_items = [
                BlockBreakdownItem(**item) if isinstance(item, dict) else item
                for item in block_breakdown
            ]

        sub_area_responses.append(SubAreaResponse(
            id=sa.get("id", ""),
            name=sa.get("name", ""),
            category=sa.get("category", ""),
            geometry=geometry_json,
            area_hectares=round(sa_area, 4),
            block_id=sa.get("blockId"),
            block_name=sa.get("blockName"),
            block_breakdown=block_breakdown_items,
            is_excluded=sa.get("isExcluded", False)
        ))
        total_area += sa_area

    return SubAreaListResponse(
        sub_areas=sub_area_responses,
        total_count=len(sub_area_responses),
        total_area_hectares=round(total_area, 4)
    )


@router.patch("/calculations/{calculation_id}/sub-areas/{sub_area_id}")
async def update_sub_area(
    calculation_id: UUID,
    sub_area_id: str,
    request: SubAreaUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a sub-area's properties (name, category, etc.)

    Note: Geometry update is not supported via this endpoint.
    Use geometry update endpoint to change the shape.
    """
    from datetime import datetime
    
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Get sub-areas from result_data
    result_data = calculation.result_data or {}
    sub_areas = result_data.get("sub_areas", [])

    # Find the sub-area
    sub_area_found = False
    for i, sa in enumerate(sub_areas):
        if sa.get("id") == sub_area_id:
            sub_area_found = True

            # Update fields
            if request.name is not None:
                sub_areas[i]["name"] = request.name
            if request.category is not None:
                valid_categories = ["protected", "plantation", "pro-poor", "religious", "biodiversity", "tourist", "office", "private_land"]
                if request.category not in valid_categories:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
                    )
                sub_areas[i]["category"] = request.category
            if request.block_id is not None:
                sub_areas[i]["blockId"] = request.block_id
            if request.block_name is not None:
                sub_areas[i]["blockName"] = request.block_name
            if request.is_excluded is not None:
                sub_areas[i]["isExcluded"] = request.is_excluded

            sub_areas[i]["updated_at"] = datetime.now().isoformat()
            break

    if not sub_area_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sub-area with ID {sub_area_id} not found"
        )

    # Save updated result_data
    result_data["sub_areas"] = sub_areas

    # Recalculate total excluded area from scratch (avoids accumulation errors)
    excluded_total = calculate_total_excluded_area(sub_areas)
    result_data["excluded_area_hectares"] = round(excluded_total, 4)

    # Recalculate effective_area_hectares at forest level
    total_area = result_data.get("area_hectares", 0)
    result_data["effective_area_hectares"] = round(total_area - excluded_total, 4)

    # Recalculate per-block excluded and effective areas (handles cross-block sub-areas)
    blocks = result_data.get("blocks", [])
    block_excluded_map = calculate_block_excluded_areas(blocks, sub_areas)

    for block in blocks:
        block_id = block.get("block_id")
        block_excluded = block_excluded_map.get(block_id, 0.0)

        block["excluded_area_hectares"] = round(block_excluded, 4)
        original_area = block.get("area_hectares", 0)
        block["effective_area_hectares"] = round(original_area - block_excluded, 4)

    result_data["blocks"] = blocks
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()
    db.refresh(calculation)

    return {
        "success": True,
        "message": "Sub-area updated successfully",
        "sub_area": sub_areas[[i for i, sa in enumerate(sub_areas) if sa.get("id") == sub_area_id][0]]
    }


@router.delete("/calculations/{calculation_id}/sub-areas/{sub_area_id}")
async def delete_sub_area(
    calculation_id: UUID,
    sub_area_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a sub-area from a calculation.
    """
    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Get sub-areas from result_data
    result_data = calculation.result_data or {}
    sub_areas = result_data.get("sub_areas", [])

    # Find and remove the sub-area
    sub_area_found = False
    new_sub_areas = []

    for sa in sub_areas:
        if sa.get("id") == sub_area_id:
            sub_area_found = True
        else:
            new_sub_areas.append(sa)

    if not sub_area_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sub-area with ID {sub_area_id} not found"
        )

    # Save updated result_data
    result_data["sub_areas"] = new_sub_areas
    result_data["sub_areas_count"] = len(new_sub_areas)

    # Recalculate total excluded area from scratch (avoids accumulation errors)
    excluded_total = calculate_total_excluded_area(new_sub_areas)
    result_data["excluded_area_hectares"] = round(excluded_total, 4)

    # Recalculate effective_area_hectares at forest level
    total_area = result_data.get("area_hectares", 0)
    result_data["effective_area_hectares"] = round(total_area - excluded_total, 4)

    # Recalculate per-block excluded and effective areas (handles cross-block sub-areas)
    blocks = result_data.get("blocks", [])
    block_excluded_map = calculate_block_excluded_areas(blocks, new_sub_areas)

    for block in blocks:
        block_id = block.get("block_id")
        block_excluded = block_excluded_map.get(block_id, 0.0)

        block["excluded_area_hectares"] = round(block_excluded, 4)
        original_area = block.get("area_hectares", 0)
        block["effective_area_hectares"] = round(original_area - block_excluded, 4)

    result_data["blocks"] = blocks
    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()
    db.refresh(calculation)

    print(f"[delete_sub_area] Deleted sub-area, new excluded total: {excluded_total:.4f} ha, effective: {result_data['effective_area_hectares']:.4f} ha")

    return {
        "success": True,
        "message": f"Sub-area deleted successfully. Removed {round(deleted_area, 4)} hectares."
    }


@router.post("/calculations/{calculation_id}/edit-boundary")
async def edit_boundary_interactive(
    calculation_id: UUID,
    request: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Interactive boundary editing endpoint.

    Accepts operations to modify the boundary geometry:
    - add_polygon: Add a new polygon to the boundary
    - remove_polygon: Remove a polygon from the boundary
    - merge_polygons: Merge multiple polygons into one
    - split_polygon: Split a polygon by a line

    Request format:
    {
        "operation": "add_polygon|remove_polygon|merge|split",
        "features": [...],  // GeoJSON features to add/modify
        "target_index": 0,  // Index of polygon to modify (for remove/merge/split)
        "reanalyze": true   // Whether to re-run analysis
    }
    """
    from shapely.geometry import shape, mapping, MultiPolygon, Polygon
    from shapely.ops import unary_union

    # Get calculation
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()

    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check permissions
    if calculation.user_id != current_user.id and current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    operation = request.get("operation", "add_polygon")
    features = request.get("features", [])
    reanalyze = request.get("reanalyze", True)

    try:
        # Get current boundary geometry
        if calculation.boundary_geom:
            geom_wkb = db.execute(
                text("SELECT ST_AsEWKB(:geom) as geom"),
                {"geom": calculation.boundary_geom}
            ).scalar()
            if geom_wkb:
                current_geom = wkb.loads(bytes(geom_wkb))
            else:
                current_geom = None
        else:
            current_geom = None

        if current_geom is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No boundary geometry found for this calculation"
            )

        # Process based on operation
        if operation == "add_polygon":
            # Add new polygon(s) to the boundary
            new_geoms = []
            for feature in features:
                if "geometry" in feature:
                    geom = shape(feature["geometry"])
                    new_geoms.append(geom)

            if new_geoms:
                if current_geom.geom_type == "MultiPolygon":
                    new_polygons = list(current_geom.geoms) + new_geoms
                    current_geom = MultiPolygon(new_polygons)
                else:
                    new_polygons = [current_geom] + new_geoms
                    current_geom = MultiPolygon(new_polygons)

        elif operation == "remove_polygon":
            target_index = request.get("target_index", 0)
            if current_geom.geom_type == "MultiPolygon":
                polygons = list(current_geom.geoms)
                if 0 <= target_index < len(polygons):
                    polygons.pop(target_index)
                    if len(polygons) == 1:
                        current_geom = polygons[0]
                    else:
                        current_geom = MultiPolygon(polygons)
            elif target_index == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove single polygon - use update_geometry instead"
                )

        elif operation == "merge":
            # Merge all polygons into one
            if current_geom.geom_type == "MultiPolygon":
                current_geom = unary_union(current_geom)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown operation: {operation}"
            )

        # Make geometry valid
        if not current_geom.is_valid:
            current_geom = current_geom.buffer(0)

        # Calculate new area
        area_sqm = current_geom.area
        area_hectares = area_sqm / 10000

        # Update boundary geometry in database
        update_query = text("""
            UPDATE public.calculations
            SET boundary_geom = ST_GeomFromText(:wkt, 4326)
            WHERE id = :calc_id
        """)

        db.execute(update_query, {
            "wkt": current_geom.wkt,
            "calc_id": str(calculation_id)
        })

        # Update result_data
        result_data = calculation.result_data or {}
        result_data["boundary_edited"] = True
        result_data["boundary_edit_operation"] = operation
        result_data["new_area_hectares"] = round(area_hectares, 4)
        calculation.result_data = result_data
        flag_modified(calculation, "result_data")

        db.commit()

        # Optionally run re-analysis
        if reanalyze:
            calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
            calculation.status = CalculationStatus.PROCESSING
            db.commit()

            analysis_options = calculation.analysis_options or {}

            try:
                analysis_results, processing_time = await analyze_forest_boundary(
                    calculation_id, db, options=analysis_options
                )

                # Preserve blocks and sub-areas
                blocks_data = result_data.get('blocks', [])
                sub_areas = result_data.get('sub_areas', [])

                updated_result_data = {
                    'blocks': blocks_data,
                    'sub_areas': sub_areas,
                    'boundary_edited': True,
                    'boundary_edit_operation': operation,
                    'new_area_hectares': round(area_hectares, 4),
                    **analysis_results
                }

                update_result_query = text("""
                    UPDATE public.calculations
                    SET
                        result_data = CAST(:result_data AS jsonb),
                        processing_time_seconds = :processing_time,
                        status = :status,
                        completed_at = NOW()
                    WHERE id = :calc_id
                """)

                db.execute(update_result_query, {
                    "result_data": json.dumps(updated_result_data),
                    "processing_time": processing_time,
                    "status": "COMPLETED",
                    "calc_id": str(calculation_id)
                })

                db.commit()
            except Exception as e:
                print(f"Re-analysis failed after boundary edit: {e}")
                calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
                calculation.status = CalculationStatus.COMPLETED
                db.commit()

        # Get updated geometry
        geojson_query = db.query(
            func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
        ).filter(Calculation.id == calculation_id).first()

        geometry_json = json.loads(geojson_query.geojson) if geojson_query and geojson_query.geojson else None

        return {
            "success": True,
            "message": f"Boundary {operation} completed" + (" and re-analysis done" if reanalyze else ""),
            "calculation_id": str(calculation_id),
            "new_area_hectares": round(area_hectares, 4),
            "geometry": geometry_json
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to edit boundary: {str(e)}"
        )


@router.get("/calculations/{calculation_id}/polygons", response_model=BlockPolygonListResponse)
async def get_calculation_polygons(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of individual polygons from a calculation's boundary geometry.
    
    This extracts each polygon from the boundary (which could be MultiPolygon)
    and returns them as individual polygons that the user can name as blocks.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )
    
    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )
    
    # Check if boundary geometry exists
    if not calculation.boundary_geom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No boundary geometry found for this calculation"
        )
    
    # Get existing blocks from result_data (if any) - database table may not have blocks yet
    existing_blocks = {}
    if calculation.result_data and 'blocks' in calculation.result_data:
        for block in calculation.result_data.get('blocks', []):
            existing_blocks[block.get('block_index', 0)] = block.get('block_name', '')
    
    # Extract individual polygons from the boundary geometry
    # First check the geometry type
    geom_type_query = db.execute(
        text("SELECT ST_GeometryType(boundary_geom) as geom_type, ST_NumGeometries(boundary_geom) as num_geoms FROM calculations WHERE id = :calc_id"),
        {"calc_id": str(calculation_id)}
    ).first()
    
    print(f"Boundary geometry type: {geom_type_query.geom_type}, num_geometries: {geom_type_query.num_geoms}")
    
    # Debug: check if boundary_geom exists and is valid
    boundary_check = db.execute(
        text("SELECT boundary_geom IS NOT NULL as has_geom, ST_IsValid(boundary_geom) as is_valid FROM calculations WHERE id = :calc_id"),
        {"calc_id": str(calculation_id)}
    ).first()
    print(f"Boundary check - has_geom: {boundary_check.has_geom}, is_valid: {boundary_check.is_valid}")
    
    # Try to get valid geometries - check result_data first
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    result_data = calculation.result_data or {}
    
    # If blocks exist in result_data with valid geometry, use those
    blocks_in_result = result_data.get('blocks', [])
    if blocks_in_result and len(blocks_in_result) > 0:
        print(f"Found {len(blocks_in_result)} blocks in result_data")
        
        polygons = []
        for i, block in enumerate(blocks_in_result):
            block_geom = block.get('geometry')
            block_area = block.get('area_hectares', 0)
            block_name = block.get('block_name', f"Block {i+1}")
            
            print(f"Block {i+1} in result_data: area = {block_area}")
            
            if block_geom:
                polygons.append(BlockPolygonResponse(
                    index=i,
                    geometry=block_geom,
                    area_hectares=round(block_area, 4) if block_area else 0,
                    current_name=block_name
                ))
        
        if polygons:
            print(f"Using {len(polygons)} blocks from result_data")
            return BlockPolygonListResponse(
                polygons=polygons,
                total_count=len(polygons)
            )
    
    # Otherwise try to extract from boundary_geom
    num_geoms = geom_type_query.num_geoms or 1
    
    # Get centroid to determine UTM zone for Nepal
    # Nepal uses UTM 44N (32644) for western (longitude < 84) and 45N (32645) for eastern
    try:
        centroid_query = db.execute(
            text("""
                SELECT ST_X(ST_Centroid(boundary_geom)) as centroid_lon
                FROM calculations
                WHERE id = :calc_id
            """),
            {"calc_id": str(calculation_id)}
        ).first()
        
        centroid_lon = centroid_query.centroid_lon if centroid_query else 85.0
        utm_srid = 32644 if centroid_lon < 84.0 else 32645
        print(f"Using UTM zone {utm_srid} (lon: {centroid_lon})")
    except Exception as e:
        print(f"Error getting centroid: {e}")
        utm_srid = 32645  # Default to eastern Nepal
        centroid_lon = 85.0
    
    # For each geometry, get its area and geometry separately (using UTM for accurate area)
    polygons = []
    for i in range(1, num_geoms + 1):
        try:
            # Extract the i-th geometry from the collection and transform to UTM for accurate area
            single_geom_query = db.execute(
                text("""
                    SELECT 
                        ST_Area(ST_Transform(ST_GeometryN(boundary_geom, :idx), :utm_srid)) / 10000.0 as area_hectares,
                        ST_AsGeoJSON(ST_GeometryN(boundary_geom, :idx)) as geometry
                    FROM calculations
                    WHERE id = :calc_id
                """),
                {"calc_id": str(calculation_id), "idx": i, "utm_srid": utm_srid}
            ).first()
            
            if single_geom_query and single_geom_query.geometry:
                geom_json = json.loads(single_geom_query.geometry)
                print(f"Polygon {i}: area_hectares = {single_geom_query.area_hectares}")
                polygons.append(BlockPolygonResponse(
                    index=i - 1,
                    geometry=geom_json,
                    area_hectares=round(single_geom_query.area_hectares, 4) if single_geom_query.area_hectares else 0,
                    current_name=existing_blocks.get(i - 1, f"Block {i}")
                ))
        except Exception as e:
            print(f"Error extracting polygon {i}: {e}")
            continue
    
    print(f"Extracted {len(polygons)} polygons from calculation {calculation_id}")
    
    return BlockPolygonListResponse(
        polygons=polygons,
        total_count=len(polygons)
    )


@router.post("/calculations/{calculation_id}/create-single-block", response_model=BlockResponse)
async def create_single_default_block(
    calculation_id: UUID,
    block_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a single default block from the calculation's boundary geometry.
    Used when user chooses "Single Block" option in Block Naming or Map Creation.

    Args:
        calculation_id: The calculation UUID
        block_name: Optional custom name (default: "{forest_name} - Block 1")

    Returns:
        Created block data with geometry and area
    """
    # 1. Get calculation and verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # 2. Delete existing blocks if any
    deleted_count = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id
    ).delete()

    if deleted_count > 0:
        print(f"Deleted {deleted_count} existing blocks for calculation {calculation_id}")

    # 3. Get boundary geometry as WKT
    boundary_wkt = db.scalar(
        select(func.ST_AsText(calculation.boundary_geom))
    )

    if not boundary_wkt:
        raise HTTPException(status_code=400, detail="Calculation has no boundary geometry")

    # 4. Calculate area in hectares (using UTM projection 32645 for Nepal)
    area_hectares = db.scalar(
        select(func.ST_Area(func.ST_Transform(calculation.boundary_geom, 32645)) / 10000)
    )

    # 5. Create default block name if not provided
    if not block_name:
        block_name = f"{calculation.forest_name} - Block 1" if calculation.forest_name else "Block 1"

    print(f"Creating single block '{block_name}' for calculation {calculation_id}")

    # 6. Create ForestBlock record
    forest_block = ForestBlock(
        id=uuid4(),
        calculation_id=calculation_id,
        name=block_name,
        geometry=func.ST_GeomFromText(boundary_wkt, 4326),
        area_hectares=area_hectares,
        index=0,
        created_at=datetime.utcnow()
    )
    db.add(forest_block)

    # 7. Update calculation result_data with block info
    block_geojson = db.scalar(
        select(func.ST_AsGeoJSON(func.ST_GeomFromText(boundary_wkt, 4326)))
    )

    result_data = calculation.result_data or {}
    result_data['blocks'] = [{
        'block_index': 0,
        'block_name': block_name,
        'area_hectares': float(area_hectares) if area_hectares else 0,
        'geometry': json.loads(block_geojson)
    }]
    result_data['total_blocks'] = 1

    calculation.result_data = result_data
    calculation.status = CalculationStatus.PENDING  # Ready for analysis

    db.commit()
    db.refresh(forest_block)

    print(f"Successfully created single block with ID {forest_block.id}")

    # 8. Return block response
    return BlockResponse(
        id=str(forest_block.id),
        name=forest_block.name,
        geometry=json.loads(block_geojson),
        area_hectares=float(forest_block.area_hectares),
        index=forest_block.index,
        created_at=forest_block.created_at
    )


@router.post("/calculations/{calculation_id}/blocks", response_model=BlockListResponse)
async def create_blocks_from_polygons(
    calculation_id: UUID,
    request: BlockCreateListRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create forest blocks from polygon mapping.
    
    User provides a list of polygon indices and their names. Each polygon
    from the boundary geometry becomes a forest block.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )
    
    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )
    
    # Delete existing blocks
    db.query(ForestBlock).filter(ForestBlock.calculation_id == calculation_id).delete()
    
    # Create new blocks
    created_blocks = []
    total_area = 0.0
    
    for block_req in request.blocks:
        # Get the polygon geometry for this index
        # Use ST_Area(geography()) for accurate geodesic calculation
        polygon_query = db.execute(
            text("""
                SELECT
                    (ST_Dump(boundary_geom)).geom as polygon_geom,
                    ST_Area(geography((ST_Dump(boundary_geom)).geom)) / 10000.0 as area_hectares
                FROM calculations
                WHERE id = :calc_id
                OFFSET :offset LIMIT 1
            """),
            {"calc_id": str(calculation_id), "offset": block_req.polygon_index}
        ).fetchone()
        
        if not polygon_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Polygon index {block_req.polygon_index} not found"
            )
        
        # Create block record
        block = ForestBlock(
            calculation_id=calculation_id,
            name=block_req.name,
            geometry=polygon_query.polygon_geom,
            area_hectares=polygon_query.area_hectares,
            index=block_req.polygon_index
        )
        db.add(block)
        created_blocks.append(block)
        total_area += polygon_query.area_hectares
    
    db.commit()
    
    # Save block geometries to result_data so frontend can display them
    blocks_for_result_data = []
    for block in created_blocks:
        geojson_result = db.query(
            func.ST_AsGeoJSON(block.geometry).label('geojson')
        ).first()
        
        block_data = {
            'block_index': block.index,
            'block_name': block.name,
            'area_hectares': round(block.area_hectares, 4),
            'geometry': json.loads(geojson_result.geojson) if geojson_result and geojson_result.geojson else None
        }
        blocks_for_result_data.append(block_data)
    
    # Update result_data with block geometries
    if calculation.result_data:
        calculation.result_data['blocks'] = blocks_for_result_data
        flag_modified(calculation, 'result_data')
        db.commit()

    # Set status to PENDING (ready for analysis to be triggered separately from Analysis page)
    calculation.status = CalculationStatus.PENDING
    db.commit()
    print(f"Blocks saved for calculation {calculation_id}. Status set to PENDING.")
    
    # Refresh to get IDs
    for block in created_blocks:
        db.refresh(block)
    
    # Build response
    block_responses = []
    for block in created_blocks:
        # Convert geometry to GeoJSON using proper SQLAlchemy
        geojson_result = db.query(
            func.ST_AsGeoJSON(block.geometry).label('geojson')
        ).first()
        
        block_responses.append(BlockResponse(
            id=str(block.id),
            name=block.name,
            geometry=json.loads(geojson_result.geojson) if geojson_result and geojson_result.geojson else {},
            area_hectares=round(block.area_hectares, 4),
            index=block.index,
            created_at=block.created_at
        ))
    
    return BlockListResponse(
        blocks=block_responses,
        total_count=len(block_responses),
        total_area_hectares=round(total_area, 4)
    )


@router.get("/calculations/{calculation_id}/blocks", response_model=BlockListResponse)
async def get_calculation_blocks(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all forest blocks for a calculation.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )
    
    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )
    
    blocks = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id
    ).order_by(ForestBlock.index).all()
    
    block_responses = []
    total_area = 0.0
    
    for block in blocks:
        geojson_result = db.query(
            func.ST_AsGeoJSON(block.geometry).label('geojson')
        ).first()
        
        block_responses.append(BlockResponse(
            id=str(block.id),
            name=block.name,
            geometry=json.loads(geojson_result.geojson) if geojson_result and geojson_result.geojson else {},
            area_hectares=round(block.area_hectares, 4),
            index=block.index,
            created_at=block.created_at
        ))
        total_area += block.area_hectares
    
    return BlockListResponse(
        blocks=block_responses,
        total_count=len(block_responses),
        total_area_hectares=round(total_area, 4)
    )


@router.patch("/calculations/{calculation_id}/blocks/{block_id}", response_model=BlockResponse)
async def update_block(
    calculation_id: UUID,
    block_id: UUID,
    name: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update a forest block's name.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )
    
    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )
    
    block = db.query(ForestBlock).filter(
        ForestBlock.id == block_id,
        ForestBlock.calculation_id == calculation_id
    ).first()
    
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found"
        )
    
    block.name = name
    db.commit()
    db.refresh(block)
    
    geojson_result = db.query(
        func.ST_AsGeoJSON(block.geometry).label('geojson')
    ).first()
    
    return BlockResponse(
        id=str(block.id),
        name=block.name,
        geometry=json.loads(geojson_result.geojson) if geojson_result and geojson_result.geojson else {},
        area_hectares=round(block.area_hectares, 4),
        index=block.index,
        created_at=block.created_at
    )


@router.delete("/calculations/{calculation_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    calculation_id: UUID,
    block_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a forest block.
    """
    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )
    
    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )
    
    block = db.query(ForestBlock).filter(
        ForestBlock.id == block_id,
        ForestBlock.calculation_id == calculation_id
    ).first()
    
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found"
        )
    
    db.delete(block)
    db.commit()


@router.post("/calculations/{calculation_id}/recalculate-areas")
async def recalculate_areas(
    calculation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Recalculate all area values for blocks and sub-areas using accurate geodesic calculations.

    This endpoint will:
    1. Recalculate areas for all blocks using ST_Area(geography())
    2. Recalculate areas for all sub-areas using UTM projection
    3. Update the result_data with corrected values

    Use this endpoint to fix any area calculations that were done with the old (incorrect) method.
    """
    from ..utils.geometry_utils import calculate_area_geodesic_from_shapely
    from shapely import wkb

    calculation = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calculation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found"
        )

    # Check ownership
    if calculation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this calculation"
        )

    recalculated_blocks = 0
    recalculated_subareas = 0

    # Recalculate block areas
    blocks = db.query(ForestBlock).filter(ForestBlock.calculation_id == calculation_id).all()
    for block in blocks:
        # Use PostGIS geography for accurate calculation
        area_query = db.execute(
            text("SELECT ST_Area(geography(geometry)) / 10000.0 as area_ha FROM forest_blocks WHERE id = :block_id"),
            {"block_id": str(block.id)}
        ).fetchone()

        if area_query:
            new_area = round(area_query.area_ha, 4)
            old_area = block.area_hectares
            block.area_hectares = new_area
            recalculated_blocks += 1
            print(f"Block {block.name}: {old_area:.4f} ha -> {new_area:.4f} ha (diff: {abs(new_area - old_area):.4f} ha)")

    db.commit()

    # Recalculate sub-area areas in result_data
    result_data = calculation.result_data or {}
    sub_areas = result_data.get("sub_areas", [])

    for sa in sub_areas:
        if "geometry" in sa:
            try:
                # Calculate using geodesic method
                area_sqm, area_hectares = calculate_area_geodesic(sa["geometry"])
                old_area = sa.get("area_hectares", 0)
                sa["area_hectares"] = round(area_hectares, 4)
                sa["area_sqm"] = round(area_sqm, 4)
                recalculated_subareas += 1
                print(f"Sub-area {sa.get('name', 'Unknown')}: {old_area:.4f} ha -> {area_hectares:.4f} ha (diff: {abs(area_hectares - old_area):.4f} ha)")
            except Exception as e:
                print(f"Error recalculating sub-area {sa.get('name', 'Unknown')}: {e}")

    # Recalculate total excluded area
    excluded_total = sum(sa.get("area_hectares", 0) for sa in sub_areas if sa.get("isExcluded", False) or sa.get("is_excluded", False))
    result_data["excluded_area_hectares"] = round(excluded_total, 4)

    # Update blocks in result_data with new areas
    if "blocks" in result_data:
        for block_data in result_data["blocks"]:
            block_name = block_data.get("block_name")
            # Find corresponding ForestBlock
            for db_block in blocks:
                if db_block.name == block_name:
                    block_data["area_hectares"] = round(db_block.area_hectares, 4)
                    break

    # Recalculate block-level excluded areas
    if "blocks" in result_data:
        for block_data in result_data["blocks"]:
            block_name = block_data.get("block_name")
            block_excluded = sum(
                sa.get("area_hectares", 0)
                for sa in sub_areas
                if (sa.get("isExcluded", False) or sa.get("is_excluded", False))
                and sa.get("blockName") == block_name
            )
            block_data["excluded_area_hectares"] = round(block_excluded, 4)
            original_area = block_data.get("area_hectares", 0)
            block_data["effective_area_hectares"] = round(original_area - block_excluded, 4)

    # Recalculate whole forest effective area
    total_area = result_data.get("area_hectares", 0)
    result_data["effective_area_hectares"] = round(total_area - excluded_total, 4)

    calculation.result_data = result_data
    flag_modified(calculation, "result_data")
    db.commit()

    return {
        "success": True,
        "message": f"Recalculated areas for {recalculated_blocks} blocks and {recalculated_subareas} sub-areas",
        "blocks_updated": recalculated_blocks,
        "sub_areas_updated": recalculated_subareas,
        "total_excluded_area": round(excluded_total, 4)
    }


# ============================================
# DRAFT ENDPOINTS - Save work-in-progress
# ============================================

@router.post("/save-draft", response_model=DraftResponse, status_code=status.HTTP_200_OK)
async def save_draft(
    request: DraftSaveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Save work-in-progress polygon creation (islands) as a draft.

    Allows users to save their progress while creating forest boundaries with multiple islands.
    Drafts can be resumed later from any device.

    - **forest_name**: Name for the forest (required)
    - **islands**: Array of island objects with geometry and area
    - **mode**: Creation mode ('auto' or 'manual')
    - **draft_id**: Optional UUID of existing draft to update
    """
    try:
        # Calculate summary data
        total_area = sum(island.get('area', 0) for island in request.islands)
        islands_count = len(request.islands)

        # Prepare draft data
        draft_data = {
            "islands": request.islands,
            "mode": request.mode,
            "islands_count": islands_count,
            "total_area": total_area,
        }

        if request.draft_id:
            # Update existing draft by ID
            calculation = db.query(Calculation).filter(
                Calculation.id == request.draft_id,
                Calculation.user_id == current_user.id,
                Calculation.is_draft == True
            ).first()

            if not calculation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Draft not found or you don't have permission to update it"
                )

            calculation.forest_name = request.forest_name
            calculation.draft_data = draft_data
            calculation.updated_at = datetime.utcnow()

        else:
            # Check for existing draft with same forest name
            existing_draft = db.query(Calculation).filter(
                Calculation.user_id == current_user.id,
                Calculation.forest_name == request.forest_name,
                Calculation.is_draft == True
            ).first()

            if existing_draft:
                # Update existing draft instead of creating new one
                existing_draft.draft_data = draft_data
                existing_draft.updated_at = datetime.utcnow()
                
                db.commit()
                db.refresh(existing_draft)
                
                return DraftResponse(
                    id=existing_draft.id,
                    forest_name=existing_draft.forest_name,
                    islands_count=islands_count,
                    total_area=total_area,
                    mode=request.mode,
                    created_at=existing_draft.created_at,
                    updated_at=existing_draft.updated_at
                )
            
            # Create new draft - use placeholder values for required fields
            calculation = Calculation(
                user_id=current_user.id,
                forest_name=request.forest_name,
                status=CalculationStatus.PENDING,
                is_draft=True,
                draft_data=draft_data,
                result_data={"draft": True},  # Minimal result_data
                uploaded_filename="draft",  # Required field - placeholder for drafts
                boundary_geom=None,  # Will be set when draft is converted to final
            )
            db.add(calculation)

        db.commit()
        db.refresh(calculation)

        return DraftResponse(
            id=calculation.id,
            forest_name=calculation.forest_name,
            islands_count=islands_count,
            total_area=total_area,
            mode=request.mode,
            created_at=calculation.created_at,
            updated_at=calculation.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save draft: {str(e)}"
        )


@router.get("/drafts", response_model=List[DraftResponse])
async def list_drafts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all drafts for the current user.

    Returns summary information for each draft including:
    - Forest name
    - Number of islands
    - Total area
    - Creation mode
    - Timestamps
    """
    try:
        drafts = db.query(Calculation).filter(
            Calculation.user_id == current_user.id,
            Calculation.is_draft == True
        ).order_by(Calculation.updated_at.desc()).all()

        response = []
        for draft in drafts:
            draft_data = draft.draft_data or {}
            response.append(DraftResponse(
                id=draft.id,
                forest_name=draft.forest_name or "Untitled Draft",
                islands_count=draft_data.get('islands_count', 0),
                total_area=draft_data.get('total_area', 0.0),
                mode=draft_data.get('mode', 'manual'),
                created_at=draft.created_at,
                updated_at=draft.updated_at
            ))

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list drafts: {str(e)}"
        )


@router.get("/drafts/{draft_id}", response_model=DraftDetailResponse)
async def get_draft(
    draft_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get full draft data including all islands and geometries.

    Used when resuming a draft to restore the exact state.
    """
    try:
        draft = db.query(Calculation).filter(
            Calculation.id == draft_id,
            Calculation.user_id == current_user.id,
            Calculation.is_draft == True
        ).first()

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found or you don't have permission to access it"
            )

        return DraftDetailResponse(
            id=draft.id,
            forest_name=draft.forest_name or "Untitled Draft",
            draft_data=draft.draft_data or {},
            created_at=draft.created_at,
            updated_at=draft.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get draft: {str(e)}"
        )


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a draft.

    Permanently removes the draft from the database.
    """
    try:
        draft = db.query(Calculation).filter(
            Calculation.id == draft_id,
            Calculation.user_id == current_user.id,
            Calculation.is_draft == True
        ).first()

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found or you don't have permission to delete it"
            )

        db.delete(draft)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete draft: {str(e)}"
        )


@router.post("/drafts/{draft_id}/convert", response_model=CalculationResponse)
async def convert_draft_to_calculation(
    draft_id: UUID,
    request: ConvertDraftRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Convert a draft into an actual calculation.

    Called when user completes the wizard after loading from draft.
    Updates the is_draft flag and saves the boundary geometry.
    """
    try:
        draft = db.query(Calculation).filter(
            Calculation.id == draft_id,
            Calculation.user_id == current_user.id,
            Calculation.is_draft == True
        ).first()

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found or you don't have permission to convert it"
            )

        # Get the outer boundary from the request
        outer_boundary = request.outer_boundary
        
        # Debug: Log what we received
        print(f"[convert_draft] Received outer_boundary type: {type(outer_boundary)}")
        print(f"[convert_draft] outer_boundary: {outer_boundary}")
        
        # Convert GeoJSON to WKT for PostGIS storage
        from ..services.map_creation_service import geojson_to_wkt
        boundary_wkt = geojson_to_wkt(outer_boundary)

        # Update calculation
        draft.is_draft = False
        draft.boundary_geom = func.ST_GeomFromText(boundary_wkt, 4326)
        draft.draft_data = None  # Clear draft data
        if not draft.uploaded_filename or draft.uploaded_filename == "draft":
            draft.uploaded_filename = f"{draft.forest_name or 'Forest'}.geojson"
        draft.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(draft)

        # Return as CalculationResponse
        return CalculationResponse(
            id=draft.id,
            user_id=draft.user_id,
            uploaded_filename=draft.uploaded_filename,
            forest_name=draft.forest_name,
            block_name=draft.block_name,
            status=draft.status,
            processing_time_seconds=draft.processing_time_seconds,
            error_message=draft.error_message,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            completed_at=draft.completed_at,
            is_draft=draft.is_draft,
            geometry=json.loads(db.scalar(func.ST_AsGeoJSON(draft.boundary_geom))) if draft.boundary_geom else None,
            result_data=draft.result_data
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert draft: {str(e)}"
        )

