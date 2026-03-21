"""
Forest management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List
from uuid import UUID
import json

from ..core.database import get_db
from ..models.user import User
from ..models.community_forest import CommunityForest
from ..models.forest_manager import ForestManager
from ..models.calculation import Calculation, CalculationStatus
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

    geometry = json.loads(geojson_query.geojson) if geojson_query else None

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
    calculation = Calculation(
        user_id=current_user.id,
        uploaded_filename=file.filename,
        boundary_geom=func.ST_GeomFromText(wkt, 4326),
        forest_name=forest_name,  # Now mandatory from form
        block_name=block_name or (blocks_data[0]['block_name'] if blocks_data else "Block 1"),
        status=CalculationStatus.PROCESSING,
        result_data=result_data,
        analysis_options=analysis_options_dict,
        map_options=map_options_dict
    )

    db.add(calculation)
    db.commit()
    db.refresh(calculation)

    # Get the calculation ID before analysis
    calc_id = calculation.id

    # Start analysis in background
    try:
        # Run raster analysis on the uploaded boundary
        print(f"Starting analysis for calculation {calc_id}")

        # Get a fresh calculation reference with eager loading to avoid detached instance issues
        db.expire_all()  # Expire cached objects

        # Use the analysis_options_dict we already built (now stored in database)
        # Only include analysis parameters (not auto-generation flags) for the analysis service
        analysis_service_options = {
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
        }

        analysis_results, processing_time = await analyze_forest_boundary(calc_id, db, options=analysis_service_options)
        print(f"Analysis completed with {len(analysis_results)} keys")

        # Merge analysis results with existing block data using SQL JSONB operators
        # Use CAST syntax instead of :: to avoid parameter binding conflict
        update_query = text("""
            UPDATE public.calculations
            SET
                result_data = result_data || CAST(:analysis_data AS jsonb),
                processing_time_seconds = :processing_time,
                status = :status,
                completed_at = NOW()
            WHERE id = :calc_id
        """)

        print(f"Executing UPDATE with {len(json.dumps(analysis_results))} bytes of data")
        result = db.execute(update_query, {
            "analysis_data": json.dumps(analysis_results),
            "processing_time": processing_time,
            "status": "COMPLETED",
            "calc_id": str(calc_id)  # Use calc_id instead of calculation.id
        })
        print(f"UPDATE affected {result.rowcount} rows")

        db.commit()
        print("Commit successful")

        # Auto-generate fieldbook and sampling (OPTIONAL - controlled by user)
        if auto_generate_fieldbook:
            try:
                print(f"Auto-generating fieldbook with 50m interpolation for calculation {calc_id}")
                fieldbook_result = generate_fieldbook_points(
                    db=db,
                    calculation_id=calc_id,
                    interpolation_distance=100.0,
                    extract_elevation=True,
                    calculate_reference=False  # Never auto-calculate references (too slow)
                )
                print(f"Fieldbook auto-generated: {fieldbook_result.total_points} points")
            except Exception as fb_error:
                print(f"Warning: Fieldbook auto-generation failed: {fb_error}")
                # Don't fail the entire upload if fieldbook generation fails
        else:
            print(f"Skipping fieldbook auto-generation (user disabled)")

        if auto_generate_sampling:
            try:
                print(f"Auto-generating sampling design for calculation {calc_id}")
                sampling_result = create_sampling_design(
                    db=db,
                    calculation_id=calc_id,
                    sampling_type="systematic",
                    grid_spacing_meters=250,
                    plot_shape="circular",
                    plot_radius_meters=12.62  # 500 sqm circular plot = radius ~12.62m
                )
                print(f"Sampling auto-generated: {sampling_result.total_plots} plots")
            except Exception as sp_error:
                print(f"Warning: Sampling auto-generation failed: {sp_error}")
                # Don't fail the entire upload if sampling generation fails
        else:
            print(f"Skipping sampling auto-generation (user disabled)")

        # Refresh calculation object after commit
        calculation = db.query(Calculation).filter(Calculation.id == calc_id).first()
        if calculation and calculation.result_data:
            print(f"Refreshed calculation, result_data has {len(calculation.result_data)} keys")
        else:
            print(f"Warning: Could not refresh calculation or result_data is empty")

    except Exception as e:
        db.rollback()  # Rollback failed transaction first
        print(f"Analysis failed: {str(e)}")

        # Update status in a new transaction
        try:
            calculation.status = CalculationStatus.FAILED
            calculation.error_message = str(e)[:500]  # Limit error message length
            db.commit()
        except Exception as commit_error:
            print(f"Failed to update error status: {commit_error}")
            db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

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
        ).filter(Calculation.id == calculation_id).first()
        
        if validity_check and not validity_check.is_valid:
            print(f"WARNING: Geometry for calculation {calculation_id} is invalid in database")
        
        geojson_query = db.query(
            func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
        ).filter(Calculation.id == calculation_id).first()

        if geojson_query and geojson_query.geojson:
            geometry_json = json.loads(geojson_query.geojson)
            print(f"Successfully converted geometry to GeoJSON for calculation {calculation_id}")
        else:
            print(f"WARNING: No geometry found for calculation {calculation_id}")
    except Exception as e:
        print(f"ERROR: Failed to convert geometry to GeoJSON for calculation {calculation_id}: {e}")

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

    # Create initial result_data with blocks
    initial_result_data = {
        "total_blocks": len(blocks_for_analysis),
        "blocks": blocks_for_analysis,
        "creation_method": "map_creation",
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

        # Track excluded area (private land)
        if metadata.get("excluded_area_hectares"):
            initial_result_data["excluded_area_hectares"] = metadata["excluded_area_hectares"]
            print(f"  Excluded area total: {metadata['excluded_area_hectares']:.4f} ha")

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

    # Prepare analysis options
    analysis_options = request.analysis_options or {}
    map_options = request.map_options or {}

    # Run analysis
    try:
        result_data, processing_time_seconds = await analyze_forest_boundary(
            calculation.id,
            db,
            options=analysis_options
        )

        # Update calculation with results
        calculation.result_data = result_data
        calculation.status = CalculationStatus.COMPLETED
        calculation.completed_at = datetime.datetime.now(datetime.timezone.utc)
        calculation.processing_time_seconds = processing_time_seconds

        # DEBUG LOGGING: Verify sub-areas survived analysis
        if result_data.get("sub_areas"):
            print(f"\n✓ SUB-AREAS AFTER ANALYSIS: {result_data.get('sub_areas_count', len(result_data['sub_areas']))} sub-areas preserved")
            for idx, sub_area in enumerate(result_data["sub_areas"]):
                print(f"  ✓ {sub_area.get('name', f'SubArea {idx+1}')}: {sub_area.get('area_hectares', 0):.4f} ha")
        else:
            print(f"\n⚠️  WARNING: No sub-areas in result_data after analysis!")
            print(f"   Initial sub-areas count: {initial_result_data.get('sub_areas_count', 0)}")

        flag_modified(calculation, "result_data")
        db.commit()
        db.refresh(calculation)

        # Auto-generate fieldbook if requested
        if analysis_options.get('auto_generate_fieldbook', True):
            try:
                print(f"🔄 Auto-generating fieldbook for calculation {calculation.id}...")
                result = generate_fieldbook_points(  # No await - this is a sync function
                    db=db,                              # db FIRST (correct order)
                    calculation_id=calculation.id,       # calculation_id SECOND
                    interpolation_distance=100.0,
                    extract_elevation=True,
                    calculate_reference=False
                )
                print(f"✓ Fieldbook auto-generated: {result.total_points} points created")

                # Verify data is in database immediately after generation
                from app.models.fieldbook import Fieldbook
                verify_count = db.query(Fieldbook).filter(Fieldbook.calculation_id == calculation.id).count()
                print(f"✓ Verification in endpoint: {verify_count} fieldbook points in database")
            except Exception as e:
                print(f"⚠️  Warning: Fieldbook generation failed: {e}")
                import traceback
                traceback.print_exc()  # Show full error for debugging

        # Auto-generate sampling if requested
        if analysis_options.get('auto_generate_sampling', True):
            try:
                print(f"🔄 Auto-generating sampling design for calculation {calculation.id}...")
                result = create_sampling_design(  # No await - this is a sync function
                    db=db,                              # db FIRST
                    calculation_id=calculation.id,      # calculation_id SECOND
                    sampling_type="systematic",         # Correct parameter name
                    sampling_intensity_percent=Decimal("0.5"),  # 0.5% intensity
                    min_samples_per_block=5,
                    plot_shape="circular",
                    plot_radius_meters=Decimal("12.6156")  # 500 sqm circular plot
                )
                print(f"✓ Sampling auto-generated: {result.total_plots} plots created")

                # Verify data is in database immediately after generation
                from app.models.sampling import SamplingDesign
                verify_count = db.query(SamplingDesign).filter(SamplingDesign.calculation_id == calculation.id).count()
                print(f"✓ Verification in endpoint: {verify_count} sampling designs in database")
            except Exception as e:
                print(f"⚠️  Warning: Sampling generation failed: {e}")
                import traceback
                traceback.print_exc()  # Show full error for debugging

    except Exception as e:
        calculation.status = CalculationStatus.FAILED
        calculation.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

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
            "result_data": json.dumps(updated_result_data),
            "analysis_options": json.dumps(analysis_options),
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

    geometry_json = json.loads(geojson_query.geojson) if geojson_query else None

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

    geometry_json = json.loads(geojson_query.geojson) if geojson_query else None

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
            completed_at=calc.completed_at,
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
