"""
API endpoints for yearly activities management with spatial integration
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
import json

from ..core.database import get_db
from ..utils.auth import get_current_user
from ..models.user import User
from ..models.calculation import Calculation
from ..models.yearly_activities import PotentialActivity, ProposedYearlyActivity, ActivityYearDetail, ActivitySpatialAssignment, ActivityDrawnFeature
from ..models.forest_block import ForestBlock
from ..models.forest_sub_area import ForestSubArea
from ..schemas.yearly_activities import (
    PotentialActivityResponse,
    ProposedActivityCreate,
    ProposedActivityUpdate,
    ProposedActivityResponse,
    ProposedActivityWithYears,
    ProposedActivityEnhancedResponse,
    YearDetailCreate,
    YearDetailUpdate,
    YearDetailResponse,
    ActivitySummary,
    ActivityLocationSummary,
    BulkProposedActivityCreate,
    DefaultActivitiesRequest,
    SpatialAssignmentCreate,
    SpatialAssignmentResponse,
    DrawnFeatureCreate,
    DrawnFeatureUpdate,
    DrawnFeatureResponse,
    BlockWithSubAreasResponse
)

router = APIRouter(prefix="/api/yearly-activities", tags=["yearly_activities"])


# ===== POTENTIAL ACTIVITIES (Master List) =====

@router.get("/potential-activities", response_model=List[PotentialActivityResponse])
async def list_potential_activities(
    project_name: Optional[str] = Query(None),
    program: Optional[str] = Query(None),
    is_default: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all potential activities from master list.
    Used to populate the activity selection table.
    """
    query = db.query(PotentialActivity).filter(PotentialActivity.is_active == is_active)

    if project_name:
        query = query.filter(PotentialActivity.project_name == project_name)
    if program:
        query = query.filter(PotentialActivity.progarms == program)  # Note: typo in column name
    if is_default:
        query = query.filter(PotentialActivity.is_default == is_default)

    # Return as stored in database (by id, not alphabetical)
    query = query.order_by(PotentialActivity.id)
    activities = query.all()
    return [PotentialActivityResponse.from_orm(act) for act in activities]


# ===== PROPOSED ACTIVITIES (Per Forest) =====

@router.get("/calculations/{calculation_id}/proposed-activities", response_model=List[ProposedActivityWithYears])
async def list_proposed_activities(
    calculation_id: UUID,
    block_id: Optional[UUID] = Query(None),
    sub_area_id: Optional[UUID] = Query(None),  # NEW: Spatial filtering
    sub_area_category: Optional[str] = Query(None),  # NEW: Filter by category
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all proposed activities for a specific forest.
    Includes spatial filtering by block, sub-area, or sub-area category.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Query with eager loading
    query = db.query(ProposedYearlyActivity).options(
        joinedload(ProposedYearlyActivity.potential_activity),
        joinedload(ProposedYearlyActivity.block),
        joinedload(ProposedYearlyActivity.sub_area),  # NEW
        joinedload(ProposedYearlyActivity.year_details),
        joinedload(ProposedYearlyActivity.spatial_assignments).joinedload(ActivitySpatialAssignment.block),
        joinedload(ProposedYearlyActivity.spatial_assignments).joinedload(ActivitySpatialAssignment.sub_area)
    ).filter(ProposedYearlyActivity.calculation_id == calculation_id)

    # Apply filters
    if block_id:
        query = query.filter(ProposedYearlyActivity.block_id == block_id)
    if sub_area_id:
        query = query.filter(ProposedYearlyActivity.sub_area_id == sub_area_id)
    if sub_area_category:
        # Join with ForestSubArea to filter by category
        query = query.join(ForestSubArea, ProposedYearlyActivity.sub_area_id == ForestSubArea.id).filter(
            ForestSubArea.category == sub_area_category
        )
    if status:
        query = query.filter(ProposedYearlyActivity.status == status)

    proposed_activities = query.all()

    # Format response with spatial details
    result = []
    for pa in proposed_activities:
        # Create base response
        pa_dict = {
            "id": pa.id,
            "calculation_id": pa.calculation_id,
            "potential_activity_id": pa.potential_activity_id,
            "block_id": pa.block_id,
            "sub_area_id": pa.sub_area_id,
            "default_quantity": pa.default_quantity,
            "default_yearly_budget": pa.default_yearly_budget,
            "notes": pa.notes,
            "status": pa.status,
            "created_at": pa.created_at,
            "updated_at": pa.updated_at,
        }

        # Add potential activity details
        if pa.potential_activity:
            pa_dict["potential_activity"] = PotentialActivityResponse.from_orm(pa.potential_activity)

        # Add spatial details
        if pa.block:
            pa_dict["block_name"] = pa.block.name

        if pa.sub_area:
            pa_dict["sub_area_name"] = pa.sub_area.name
            pa_dict["sub_area_category"] = pa.sub_area.category
            pa_dict["location_description"] = f"{pa.sub_area.name} ({pa.sub_area.category}), {pa.block.name}"
        elif pa.block:
            pa_dict["location_description"] = f"{pa.block.name} (entire block)"
        else:
            pa_dict["location_description"] = "Entire forest"

        # Add year details
        pa_dict["year_details"] = [YearDetailResponse.from_orm(yd) for yd in pa.year_details]

        # Add spatial assignments with names
        sa_list = []
        for sa in pa.spatial_assignments:
            sa_dict = {
                "id": sa.id,
                "proposed_activity_id": sa.proposed_activity_id,
                "block_id": sa.block_id,
                "sub_area_id": sa.sub_area_id,
                "assignment_type": sa.assignment_type,
                "created_at": sa.created_at,
                "block_name": None,
                "sub_area_name": None
            }
            # Load block name if block_id exists
            if sa.block_id and sa.block:
                sa_dict["block_name"] = sa.block.name
            # Load sub-area name if sub_area_id exists
            if sa.sub_area_id and sa.sub_area:
                sa_dict["sub_area_name"] = sa.sub_area.name
            sa_list.append(sa_dict)
        
        pa_dict["assign_to_all_blocks"] = pa.assign_to_all_blocks
        pa_dict["spatial_assignments"] = sa_list

        # Calculate total budget
        total_budget = Decimal(0)
        for year in range(1, 11):
            year_detail = next((yd for yd in pa.year_details if yd.year_number == year), None)
            if year_detail and year_detail.yearly_budget:
                total_budget += year_detail.yearly_budget
            else:
                total_budget += pa.default_yearly_budget
        pa_dict["total_budget_10_years"] = total_budget

        result.append(ProposedActivityWithYears(**pa_dict))

    return result


@router.post("/calculations/{calculation_id}/proposed-activities", response_model=ProposedActivityResponse)
async def create_proposed_activity(
    calculation_id: UUID,
    activity_data: ProposedActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a single activity to the forest's yearly plan.
    Supports spatial assignment to blocks and sub-areas.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Verify potential activity exists
    potential = db.query(PotentialActivity).filter(
        PotentialActivity.id == activity_data.potential_activity_id,
        PotentialActivity.is_active == True
    ).first()
    if not potential:
        raise HTTPException(status_code=404, detail="Potential activity not found")

    # Check for duplicates (same activity, same block, same sub-area)
    existing = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.calculation_id == calculation_id,
        ProposedYearlyActivity.potential_activity_id == activity_data.potential_activity_id,
        ProposedYearlyActivity.block_id == activity_data.block_id,
        ProposedYearlyActivity.sub_area_id == activity_data.sub_area_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Activity already added for this location")

    # Create proposed activity
    proposed = ProposedYearlyActivity(
        calculation_id=calculation_id,
        **activity_data.dict()
    )
    db.add(proposed)
    db.commit()
    db.refresh(proposed)

    # Load relationships
    db.refresh(proposed, ['potential_activity', 'block', 'sub_area'])

    # Format response
    response_dict = {
        "id": proposed.id,
        "calculation_id": proposed.calculation_id,
        "potential_activity_id": proposed.potential_activity_id,
        "block_id": proposed.block_id,
        "sub_area_id": proposed.sub_area_id,
        "default_quantity": proposed.default_quantity,
        "default_yearly_budget": proposed.default_yearly_budget,
        "notes": proposed.notes,
        "status": proposed.status,
        "created_at": proposed.created_at,
        "updated_at": proposed.updated_at,
    }

    if proposed.potential_activity:
        response_dict["potential_activity"] = PotentialActivityResponse.from_orm(proposed.potential_activity)
    if proposed.block:
        response_dict["block_name"] = proposed.block.name
    if proposed.sub_area:
        response_dict["sub_area_name"] = proposed.sub_area.name
        response_dict["sub_area_category"] = proposed.sub_area.category
        response_dict["location_description"] = f"{proposed.sub_area.name} ({proposed.sub_area.category}), {proposed.block.name}"
    elif proposed.block:
        response_dict["location_description"] = f"{proposed.block.name} (entire block)"
    else:
        response_dict["location_description"] = "Entire forest"

    return ProposedActivityResponse(**response_dict)


@router.patch("/proposed-activities/{proposed_activity_id}", response_model=ProposedActivityResponse)
async def update_proposed_activity(
    proposed_activity_id: UUID,
    activity_update: ProposedActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a proposed activity (e.g., change quantity, budget, block, sub-area assignment).
    """
    proposed = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == proposed_activity_id
    ).first()
    if not proposed:
        raise HTTPException(status_code=404, detail="Proposed activity not found")

    # Verify ownership
    calculation = db.query(Calculation).filter(Calculation.id == proposed.calculation_id).first()
    if calculation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update fields
    for field, value in activity_update.dict(exclude_unset=True).items():
        setattr(proposed, field, value)

    db.commit()
    db.refresh(proposed, ['potential_activity', 'block', 'sub_area'])

    # Format response
    response_dict = {
        "id": proposed.id,
        "calculation_id": proposed.calculation_id,
        "potential_activity_id": proposed.potential_activity_id,
        "block_id": proposed.block_id,
        "sub_area_id": proposed.sub_area_id,
        "default_quantity": proposed.default_quantity,
        "default_yearly_budget": proposed.default_yearly_budget,
        "notes": proposed.notes,
        "status": proposed.status,
        "created_at": proposed.created_at,
        "updated_at": proposed.updated_at,
    }

    if proposed.potential_activity:
        response_dict["potential_activity"] = PotentialActivityResponse.from_orm(proposed.potential_activity)
    if proposed.block:
        response_dict["block_name"] = proposed.block.name
    if proposed.sub_area:
        response_dict["sub_area_name"] = proposed.sub_area.name
        response_dict["sub_area_category"] = proposed.sub_area.category
        response_dict["location_description"] = f"{proposed.sub_area.name} ({proposed.sub_area.category}), {proposed.block.name}"
    elif proposed.block:
        response_dict["location_description"] = f"{proposed.block.name} (entire block)"
    else:
        response_dict["location_description"] = "Entire forest"

    return ProposedActivityResponse(**response_dict)


@router.delete("/proposed-activities/{proposed_activity_id}")
async def delete_proposed_activity(
    proposed_activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove an activity from the forest's yearly plan.
    """
    proposed = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == proposed_activity_id
    ).first()
    if not proposed:
        raise HTTPException(status_code=404, detail="Proposed activity not found")

    # Verify ownership
    calculation = db.query(Calculation).filter(Calculation.id == proposed.calculation_id).first()
    if calculation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(proposed)
    db.commit()

    return {"status": "deleted", "id": str(proposed_activity_id)}


# ===== NEW: SPATIAL ENDPOINTS =====

@router.get("/calculations/{calculation_id}/proposed-activities/spatial")
async def get_activities_with_geometry(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all proposed activities with their spatial geometries.
    Used for map visualization.

    Returns GeoJSON-like structure with activity details.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Query activities with spatial data
    query = db.query(
        ProposedYearlyActivity,
        PotentialActivity,
        ForestBlock,
        ForestSubArea,
        func.ST_AsGeoJSON(ForestSubArea.geometry).label('sub_area_geojson')
    ).join(
        PotentialActivity,
        ProposedYearlyActivity.potential_activity_id == PotentialActivity.id
    ).outerjoin(
        ForestBlock,
        ProposedYearlyActivity.block_id == ForestBlock.id
    ).outerjoin(
        ForestSubArea,
        ProposedYearlyActivity.sub_area_id == ForestSubArea.id
    ).filter(
        ProposedYearlyActivity.calculation_id == calculation_id
    )

    results = query.all()

    # Format for map display
    features = []
    for pa, pot, block, sub_area, geojson in results:
        if not sub_area:
            continue  # Skip activities without spatial geometry

        geometry = json.loads(geojson) if geojson else None

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "activity_id": str(pa.id),
                "activity_name": pot.activities,
                "project_name": pot.project_name,
                "program": pot.progarms,
                "sub_area_name": sub_area.name,
                "sub_area_category": sub_area.category,
                "block_name": block.name if block else None,
                "quantity": float(pa.default_quantity),
                "unit": pot.unit,
                "yearly_budget": float(pa.default_yearly_budget),
                "total_budget_10_years": float(pa.default_yearly_budget * 10),
                "status": pa.status,
                "location_description": f"{pot.activities} in {sub_area.name} ({sub_area.category})"
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.get("/calculations/{calculation_id}/location-summary", response_model=ActivityLocationSummary)
async def get_activity_location_summary(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of activities by spatial location.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Get all proposed activities with relationships
    proposed_activities = db.query(ProposedYearlyActivity).options(
        joinedload(ProposedYearlyActivity.block),
        joinedload(ProposedYearlyActivity.sub_area)
    ).filter(ProposedYearlyActivity.calculation_id == calculation_id).all()

    # Initialize counters
    by_block = {}
    by_sub_area_category = {}
    by_sub_area = {}
    whole_forest_count = 0

    for pa in proposed_activities:
        # Count by block
        if pa.block:
            block_name = pa.block.name
            by_block[block_name] = by_block.get(block_name, 0) + 1
        else:
            whole_forest_count += 1

        # Count by sub-area
        if pa.sub_area:
            sub_area_name = pa.sub_area.name
            category = pa.sub_area.category

            by_sub_area[sub_area_name] = by_sub_area.get(sub_area_name, 0) + 1
            by_sub_area_category[category] = by_sub_area_category.get(category, 0) + 1

    return ActivityLocationSummary(
        by_block=by_block,
        by_sub_area_category=by_sub_area_category,
        by_sub_area=by_sub_area,
        whole_forest_count=whole_forest_count
    )


# ===== SUMMARY & REPORTING =====

@router.get("/calculations/{calculation_id}/summary", response_model=ActivitySummary)
async def get_activity_summary(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary statistics for all proposed activities.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Get all proposed activities with relationships
    proposed_activities = db.query(ProposedYearlyActivity).options(
        joinedload(ProposedYearlyActivity.potential_activity),
        joinedload(ProposedYearlyActivity.block),
        joinedload(ProposedYearlyActivity.year_details)
    ).filter(ProposedYearlyActivity.calculation_id == calculation_id).all()

    # Initialize counters
    total_budget = Decimal(0)
    by_project = {}
    by_program = {}
    by_block = {}
    by_year = {year: Decimal(0) for year in range(1, 11)}
    by_status = {}

    for pa in proposed_activities:
        pot = pa.potential_activity

        # Count by project
        if pot and pot.project_name:
            by_project[pot.project_name] = by_project.get(pot.project_name, 0) + 1

        # Count by program
        if pot and pot.progarms:
            by_program[pot.progarms] = by_program.get(pot.progarms, 0) + 1

        # Count by block
        block_name = pa.block.name if pa.block else "Unassigned"
        by_block[block_name] = by_block.get(block_name, 0) + 1

        # Count by status
        by_status[pa.status] = by_status.get(pa.status, 0) + 1

        # Calculate budget by year
        for year in range(1, 11):
            year_detail = next((yd for yd in pa.year_details if yd.year_number == year), None)
            if year_detail and year_detail.yearly_budget:
                budget = year_detail.yearly_budget
            else:
                budget = pa.default_yearly_budget

            by_year[year] += budget
            total_budget += budget

    return ActivitySummary(
        total_activities=len(proposed_activities),
        total_budget_10_years=total_budget,
        by_project=by_project,
        by_program=by_program,
        by_block=by_block,
        by_year={str(k): float(v) for k, v in by_year.items()},
        by_status=by_status
    )


# ===== NEW: SPATIAL ASSIGNMENT ENDPOINTS =====

@router.get("/proposed-activities/{activity_id}/spatial", response_model=List[SpatialAssignmentResponse])
async def get_spatial_assignments(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all spatial assignments for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    assignments = db.query(ActivitySpatialAssignment).filter(
        ActivitySpatialAssignment.proposed_activity_id == activity_id
    ).all()
    
    result = []
    for a in assignments:
        data = {
            "id": a.id,
            "proposed_activity_id": a.proposed_activity_id,
            "block_id": a.block_id,
            "sub_area_id": a.sub_area_id,
            "assignment_type": a.assignment_type,
            "created_at": a.created_at,
            "block_name": a.block.name if a.block else None,
            "sub_area_name": a.sub_area.name if a.sub_area else None
        }
        result.append(SpatialAssignmentResponse(**data))
    
    return result


@router.post("/proposed-activities/{activity_id}/spatial", response_model=SpatialAssignmentResponse)
async def create_spatial_assignment(
    activity_id: UUID,
    assignment_data: SpatialAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add spatial assignment for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    assignment = ActivitySpatialAssignment(
        proposed_activity_id=activity_id,
        block_id=assignment_data.block_id,
        sub_area_id=assignment_data.sub_area_id,
        assignment_type=assignment_data.assignment_type
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return SpatialAssignmentResponse(
        id=assignment.id,
        proposed_activity_id=assignment.proposed_activity_id,
        block_id=assignment.block_id,
        sub_area_id=assignment.sub_area_id,
        assignment_type=assignment.assignment_type,
        created_at=assignment.created_at,
        block_name=assignment.block.name if assignment.block else None,
        sub_area_name=assignment.sub_area.name if assignment.sub_area else None
    )


@router.delete("/proposed-activities/{activity_id}/spatial/{assignment_id}")
async def delete_spatial_assignment(
    activity_id: UUID,
    assignment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove spatial assignment"""
    assignment = db.query(ActivitySpatialAssignment).filter(
        ActivitySpatialAssignment.id == assignment_id,
        ActivitySpatialAssignment.proposed_activity_id == activity_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Spatial assignment not found")
    
    db.delete(assignment)
    db.commit()
    
    return {"message": "Spatial assignment deleted"}


# ===== NEW: DRAWN FEATURES ENDPOINTS =====

@router.get("/proposed-activities/{activity_id}/drawn-features", response_model=List[DrawnFeatureResponse])
async def get_drawn_features(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all drawn features for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    features = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).all()
    
    result = []
    import shapely
    from shapely.geometry import mapping as shapely_mapping
    from geoalchemy2.shape import to_shape
    
    for f in features:
        try:
            feat_geom = to_shape(f.geometry)
            geom_json = shapely_mapping(feat_geom)
        except Exception as e:
            print(f"Error mapping geometry: {e}")
            geom_json = {"type": f.feature_type, "coordinates": []}
        
        result.append(DrawnFeatureResponse(
            id=f.id,
            proposed_activity_id=f.proposed_activity_id,
            feature_type=f.feature_type,
            geometry=json.dumps(geom_json),
            properties=f.properties,
            created_at=f.created_at,
            updated_at=f.updated_at
        ))
    
    return result


@router.post("/proposed-activities/{activity_id}/drawn-features", response_model=DrawnFeatureResponse)
async def create_drawn_feature(
    activity_id: UUID,
    feature_data: DrawnFeatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create drawn feature for a proposed activity"""
    import shapely
    from shapely.geometry import mapping as shapely_mapping
    from geoalchemy2.shape import to_shape
    
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    geojson = json.loads(feature_data.geometry)
    if feature_data.feature_type == "point":
        geom = shapely.Point(geojson["coordinates"])
    elif feature_data.feature_type == "line":
        geom = shapely.LineString(geojson["coordinates"])
    else:
        coords = geojson["coordinates"]
        if isinstance(coords[0][0], list):
            coords = coords[0]
        geom = shapely.Polygon(coords)
    
    feature = ActivityDrawnFeature(
        proposed_activity_id=activity_id,
        feature_type=feature_data.feature_type,
        geometry=geom.wkt,
        properties=feature_data.properties
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    
    try:
        feat_geom = to_shape(feature.geometry)
        geom_json = shapely_mapping(feat_geom)
    except Exception as e:
        print(f"Error mapping geometry: {e}")
        geom_json = {"type": feature_data.feature_type, "coordinates": []}
    
    return DrawnFeatureResponse(
        id=feature.id,
        proposed_activity_id=feature.proposed_activity_id,
        feature_type=feature.feature_type,
        geometry=json.dumps(geom_json),
        properties=feature.properties,
        created_at=feature.created_at,
        updated_at=feature.updated_at
    )


@router.patch("/proposed-activities/{activity_id}/drawn-features/{feature_id}", response_model=DrawnFeatureResponse)
async def update_drawn_feature(
    activity_id: UUID,
    feature_id: UUID,
    feature_data: DrawnFeatureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update drawn feature"""
    import shapely
    from shapely.geometry import mapping as shapely_mapping
    from geoalchemy2.shape import to_shape
    
    feature = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.id == feature_id,
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Drawn feature not found")
    
    if feature_data.feature_type:
        feature.feature_type = feature_data.feature_type
    if feature_data.geometry:
        geojson = json.loads(feature_data.geometry)
        coords = geojson["coordinates"]
        if feature_data.feature_type == "point":
            geom = shapely.Point(coords)
        elif feature_data.feature_type == "line":
            geom = shapely.LineString(coords)
        elif feature_data.feature_type == "polygon":
            # GeoJSON polygon has nested array: [[[x,y], ...]] - get first ring
            ring = coords[0] if coords[0] and isinstance(coords[0][0], list) else coords
            geom = shapely.Polygon(ring)
        else:
            geom = shapely.Point(coords)
        feature.geometry = geom.wkt
    if feature_data.properties:
        feature.properties = feature_data.properties
    
    db.commit()
    db.refresh(feature)
    
    try:
        feat_geom = to_shape(feature.geometry)
        geom_json = shapely_mapping(feat_geom)
    except Exception as e:
        print(f"Error mapping geometry: {e}")
        geom_json = {"type": feature.feature_type, "coordinates": []}
    
    return DrawnFeatureResponse(
        id=feature.id,
        proposed_activity_id=feature.proposed_activity_id,
        feature_type=feature.feature_type,
        geometry=json.dumps(geom_json),
        properties=feature.properties,
        created_at=feature.created_at,
        updated_at=feature.updated_at
    )


@router.delete("/proposed-activities/{activity_id}/drawn-features/{feature_id}")
async def delete_drawn_feature(
    activity_id: UUID,
    feature_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete drawn feature"""
    feature = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.id == feature_id,
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Drawn feature not found")
    
    db.delete(feature)
    db.commit()
    
    return {"message": "Drawn feature deleted"}


# ===== YEAR DETAILS ENDPOINTS =====

@router.get("/proposed-activities/{activity_id}/year-details", response_model=List[YearDetailResponse])
async def get_year_details(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all year details for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    details = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id == activity_id
    ).all()
    
    return [YearDetailResponse.from_orm(d) for d in details]


@router.post("/proposed-activities/{activity_id}/year-details", response_model=YearDetailResponse)
async def create_year_detail(
    activity_id: UUID,
    detail_data: YearDetailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update year detail for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    # Check if year detail already exists
    existing = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id == activity_id,
        ActivityYearDetail.year_number == detail_data.year_number
    ).first()
    
    if existing:
        existing.quantity = detail_data.quantity
        existing.yearly_budget = detail_data.yearly_budget
        existing.target_completion_month = detail_data.target_completion_month
        existing.notes = detail_data.notes
        existing.status = detail_data.status
        db.commit()
        db.refresh(existing)
        return YearDetailResponse.from_orm(existing)
    
    # Create new
    detail = ActivityYearDetail(
        proposed_activity_id=activity_id,
        year_number=detail_data.year_number,
        quantity=detail_data.quantity,
        yearly_budget=detail_data.yearly_budget,
        target_completion_month=detail_data.target_completion_month,
        notes=detail_data.notes,
        status=detail_data.status
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return YearDetailResponse.from_orm(detail)


@router.patch("/proposed-activities/{activity_id}/year-details/{detail_id}", response_model=YearDetailResponse)
async def update_year_detail(
    activity_id: UUID,
    detail_id: UUID,
    detail_data: YearDetailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update year detail"""
    detail = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.id == detail_id,
        ActivityYearDetail.proposed_activity_id == activity_id
    ).first()
    if not detail:
        raise HTTPException(status_code=404, detail="Year detail not found")
    
    for field, value in detail_data.dict(exclude_unset=True).items():
        setattr(detail, field, value)
    
    db.commit()
    db.refresh(detail)
    return YearDetailResponse.from_orm(detail)


@router.delete("/proposed-activities/{activity_id}/year-details/{detail_id}")
async def delete_year_detail(
    activity_id: UUID,
    detail_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete year detail"""
    detail = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.id == detail_id,
        ActivityYearDetail.proposed_activity_id == activity_id
    ).first()
    if not detail:
        raise HTTPException(status_code=404, detail="Year detail not found")
    
    db.delete(detail)
    db.commit()
    return {"message": "Year detail deleted"}


# ===== NEW: BLOCKS WITH SUB-AREAS =====

@router.get("/calculations/{calculation_id}/blocks-with-subareas")
async def get_blocks_with_subareas(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blocks with their sub-areas for a calculation"""
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    
    result = []
    
    # ALWAYS return the forest boundary as a block
    try:
        from geoalchemy2.shape import to_shape
        from shapely.geometry import mapping
        
        if calculation.outer_boundary:
            shp = to_shape(calculation.outer_boundary)
            geom_dict = mapping(shp)
            
            result.append({
                "id": str(calculation.id)[:8],
                "name": calculation.forest_name or "Forest",
                "type": "block",
                "geometry": geom_dict
            })
    except Exception as e:
        print(f"[DEBUG] Error: {e}")
    
    return result
