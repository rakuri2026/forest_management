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


@router.get("/calculations/{calculation_id}/potential-activities", response_model=List[PotentialActivityResponse])
async def get_calculation_potential_activities(
    calculation_id: UUID,
    project_name: Optional[str] = Query(None),
    program: Optional[str] = Query(None),
    is_default: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List potential activities for a specific calculation.
    Returns all active potential activities that can be proposed for this forest.
    """
    query = db.query(PotentialActivity).filter(PotentialActivity.is_active == is_active)

    if project_name:
        query = query.filter(PotentialActivity.project_name == project_name)
    if program:
        query = query.filter(PotentialActivity.progarms == program)
    if is_default:
        query = query.filter(PotentialActivity.is_default == is_default)

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
    ).order_by(ActivityDrawnFeature.created_at).all()
    
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
    
    print(f"[create_drawn_feature] feature_data.properties: {feature_data.properties}")
    
    activity = db.query(ProposedYearlyActivity).filter(ProposedYearlyActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    geojson = json.loads(feature_data.geometry)
    coords = geojson["coordinates"]
    if feature_data.feature_type == "point":
        geom = shapely.Point(coords)
    elif feature_data.feature_type == "line":
        if len(coords) < 2:
            raise HTTPException(status_code=400, detail="Line requires at least 2 points")
        geom = shapely.LineString(coords)
    else:
        ring = coords[0] if coords and coords[0] and isinstance(coords[0][0], list) else coords
        if len(ring) < 4:
            raise HTTPException(status_code=400, detail="Polygon must have at least 4 points (including closing)")
        geom = shapely.Polygon(ring)
    
    feature = ActivityDrawnFeature(
        proposed_activity_id=activity_id,
        feature_type=feature_data.feature_type,
        geometry=geom.wkt,
        properties=feature_data.properties
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    
    print(f"[create_drawn_feature] feature.properties after save: {feature.properties}")
    
    try:
        feat_geom = to_shape(feature.geometry)
        geom_json = shapely_mapping(feat_geom)
    except Exception as e:
        print(f"Error mapping geometry: {e}")
        geom_json = {"type": feature_data.feature_type, "coordinates": []}
    
    response = DrawnFeatureResponse(
        id=feature.id,
        proposed_activity_id=feature.proposed_activity_id,
        feature_type=feature.feature_type,
        geometry=json.dumps(geom_json),
        properties=feature.properties,
        created_at=feature.created_at,
        updated_at=feature.updated_at
    )
    print(f"[create_drawn_feature] returning response.properties: {response.properties}")
    return response


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
        print(f"[update_drawn_feature] geometry: {feature_data.geometry}")
        coords = geojson["coordinates"]
        print(f"[update_drawn_feature] coords: {coords}, type: {feature_data.feature_type}")
        if feature_data.feature_type == "point":
            if coords and len(coords) >= 2 and coords[0] is not None and coords[1] is not None:
                geom = shapely.Point(coords)
            else:
                geom = shapely.Point(coords)
        elif feature_data.feature_type == "line":
            valid_coords = [c for c in coords if isinstance(c, list) and len(c) >= 2 and c[0] is not None and c[1] is not None]
            if len(valid_coords) < 2:
                raise HTTPException(status_code=400, detail="Line requires at least 2 valid points")
            geom = shapely.LineString(valid_coords)
        elif feature_data.feature_type == "polygon":
            ring = coords[0] if coords and coords[0] and isinstance(coords[0][0], list) else coords
            valid_ring = [c for c in ring if isinstance(c, list) and len(c) >= 2 and c[0] is not None and c[1] is not None]
            if len(valid_ring) < 3:
                raise HTTPException(status_code=400, detail="Polygon must have at least 3 valid coordinates")
            geom = shapely.Polygon(valid_ring)
        else:
            if coords and len(coords) >= 2 and coords[0] is not None and coords[1] is not None:
                geom = shapely.Point(coords)
            else:
                raise HTTPException(status_code=400, detail="Point requires valid coordinates")
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


@router.post("/proposed-activities/{activity_id}/drawn-features/{feature_id}/copy", response_model=DrawnFeatureResponse)
async def copy_drawn_feature(
    activity_id: UUID,
    feature_id: UUID,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Copy a drawn feature to a different year"""
    from shapely.geometry import mapping as shapely_mapping
    from geoalchemy2.shape import to_shape
    
    # Get the source feature
    source_feature = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.id == feature_id,
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).first()
    if not source_feature:
        raise HTTPException(status_code=404, detail="Source feature not found")
    
    target_year = request.get('target_year')
    if not target_year:
        raise HTTPException(status_code=400, detail="target_year is required")
    
    # Check if feature with same geometry already exists for target year
    existing = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.proposed_activity_id == activity_id,
        ActivityDrawnFeature.geometry == source_feature.geometry,
        ActivityDrawnFeature.properties['year'] == target_year
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Feature already exists for year {target_year}")
    
    # Create new feature
    new_feature = ActivityDrawnFeature(
        proposed_activity_id=activity_id,
        feature_type=source_feature.feature_type,
        geometry=source_feature.geometry,
        properties={
            **source_feature.properties,
            'year': target_year,
            'copied_from': str(source_feature.id)
        }
    )
    
    db.add(new_feature)
    db.commit()
    db.refresh(new_feature)
    
    try:
        feat_geom = to_shape(new_feature.geometry)
        geom_json = shapely_mapping(feat_geom)
    except Exception as e:
        print(f"Error mapping geometry: {e}")
        geom_json = {"type": source_feature.feature_type, "coordinates": []}
    
    return DrawnFeatureResponse(
        id=new_feature.id,
        proposed_activity_id=new_feature.proposed_activity_id,
        feature_type=new_feature.feature_type,
        geometry=json.dumps(geom_json),
        properties=new_feature.properties,
        created_at=new_feature.created_at,
        updated_at=new_feature.updated_at
    )


# ===== YEAR DETAILS =====

@router.get("/proposed-activities/{activity_id}/year-details", response_model=List[YearDetailResponse])
async def list_year_details(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all year details for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == activity_id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    details = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id == activity_id
    ).order_by(ActivityYearDetail.year_number).all()
    
    return [YearDetailResponse.from_orm(d) for d in details]


@router.post("/proposed-activities/{activity_id}/year-details", response_model=YearDetailResponse)
async def create_year_detail(
    activity_id: UUID,
    detail_data: YearDetailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a year detail for a proposed activity"""
    activity = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == activity_id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    # Check if year detail already exists
    existing = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id == activity_id,
        ActivityYearDetail.year_number == detail_data.year_number
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Year detail for year {detail_data.year_number} already exists")
    
    detail = ActivityYearDetail(
        proposed_activity_id=activity_id,
        year_number=detail_data.year_number,
        quantity=detail_data.quantity,
        yearly_budget=detail_data.yearly_budget,
        target_completion_month=detail_data.target_completion_month,
        actual_quantity=detail_data.actual_quantity,
        actual_budget=detail_data.actual_budget,
        status=detail_data.status or 'planned',
        notes=detail_data.notes
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
    """Update a year detail"""
    detail = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.id == detail_id,
        ActivityYearDetail.proposed_activity_id == activity_id
    ).first()
    
    if not detail:
        raise HTTPException(status_code=404, detail="Year detail not found")
    
    # Update fields
    if detail_data.quantity is not None:
        detail.quantity = detail_data.quantity
    if detail_data.yearly_budget is not None:
        detail.yearly_budget = detail_data.yearly_budget
    if detail_data.target_completion_month is not None:
        detail.target_completion_month = detail_data.target_completion_month
    if detail_data.actual_quantity is not None:
        detail.actual_quantity = detail_data.actual_quantity
    if detail_data.actual_budget is not None:
        detail.actual_budget = detail_data.actual_budget
    if detail_data.status is not None:
        detail.status = detail_data.status
    if detail_data.notes is not None:
        detail.notes = detail_data.notes
    
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
    """Delete a year detail"""
    detail = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.id == detail_id,
        ActivityYearDetail.proposed_activity_id == activity_id
    ).first()
    
    if not detail:
        raise HTTPException(status_code=404, detail="Year detail not found")
    
    db.delete(detail)
    db.commit()
    
    return {"message": "Year detail deleted"}


@router.get("/calculations/{calculation_id}/blocks-with-subareas")
async def get_blocks_with_subareas(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blocks with their sub-areas for a calculation"""
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
    
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    
    result = []
    
    # 1. Return the forest boundary as "boundary" type (for map display)
    try:
        if calculation.boundary_geom:
            shp = to_shape(calculation.boundary_geom)
            geom_dict = mapping(shp)
            
            result.append({
                "id": f"{str(calculation.id)[:8]}-boundary",
                "name": calculation.forest_name or "Forest Boundary",
                "type": "boundary",
                "geometry": geom_dict
            })
    except Exception as e:
        print(f"[DEBUG] Boundary Error: {e}")
    
    # 2. Return blocks from result_data (for map display)
    try:
        if calculation.result_data and calculation.result_data.get('blocks'):
            blocks = calculation.result_data.get('blocks', [])
            for i, block in enumerate(blocks):
                block_geom = block.get('geometry')
                if block_geom:
                    result.append({
                        "id": block.get('id') or f"block-{i}",
                        "name": block.get('block_name') or block.get('name') or f"Block {i + 1}",
                        "type": "block",
                        "area_hectares": block.get('area_hectares') or block.get('area') or 0,
                        "geometry": block_geom
                    })
    except Exception as e:
        print(f"[DEBUG] Blocks Error: {e}")
    
    # 3. Return sub-areas from forest_sub_areas table (filtered by result_data for sync)
    try:
        from app.models.forest_sub_area import ForestSubArea
        from app.models.forest_block import ForestBlock
        
        # Get valid sub-area IDs from result_data
        valid_sub_area_ids = set()
        if calculation.result_data and calculation.result_data.get('sub_areas'):
            for sa in calculation.result_data.get('sub_areas', []):
                valid_sub_area_ids.add(sa.get('id'))
        
        # Get sub-areas from table with block info using JOIN
        sub_areas = db.query(
            ForestSubArea,
            ForestBlock.name.label('block_name')
        ).outerjoin(
            ForestBlock, ForestBlock.id == ForestSubArea.block_id
        ).filter(
            ForestSubArea.calculation_id == calculation_id
        ).all()
        
        for sub_area, block_name in sub_areas:
            # Only include if it exists in result_data (sync filter)
            if sub_area.geometry and (str(sub_area.id) in valid_sub_area_ids or not valid_sub_area_ids):
                shp = to_shape(sub_area.geometry)
                geom_dict = mapping(shp)
                
                result.append({
                    "id": str(sub_area.id),
                    "name": sub_area.name or f"Sub-Area",
                    "type": "sub_area",
                    "category": sub_area.category,
                    "area_hectares": sub_area.area_hectares or 0,
                    "block_id": str(sub_area.block_id) if sub_area.block_id else None,
                    "block_name": block_name or "",
                    "geometry": geom_dict
                })
    except Exception as e:
        print(f"[DEBUG] SubAreas Error: {e}")
    
    return result


# ===== EXPORT SPATIAL FEATURES =====

@router.get("/proposed-activities/{activity_id}/export/kml")
async def export_spatial_features_kml(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export drawn spatial features to KML format.
    """
    from xml.etree import ElementTree as ET
    from fastapi.responses import StreamingResponse
    from geoalchemy2.shape import to_shape
    import io
    
    activity = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == activity_id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    calc = db.query(Calculation).filter(Calculation.id == activity.calculation_id).first()
    if not calc or calc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    features = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).all()
    
    # Allow export even if no features (just reference layers)
    # if not features:
    #     raise HTTPException(status_code=404, detail="No spatial features to export")
    
    activity_name = "Spatial Features"
    if activity.potential_activity:
        activity_name = activity.potential_activity.activities or activity_name
    
    kml = ET.Element('kml', {'xmlns': 'http://www.opengis.net/kml/2.2'})
    document = ET.SubElement(kml, 'Document')
    
    ET.SubElement(document, 'name').text = f'{activity_name} - Spatial Features'
    ET.SubElement(document, 'description').text = (
        f'Exported from Community Forest Management System. '
        f'Activity: {activity_name}. '
        f'Total features: {len(features)}.'
    )
    
    # Add features folder (only drawn spatial features)
    features_folder = ET.SubElement(document, 'Folder')
    ET.SubElement(features_folder, 'name').text = f'Drawn Features ({len(features)})'
    
    style_map = {}
    
    for idx, feature in enumerate(features):
        from geoalchemy2.shape import to_shape
        from shapely.geometry import mapping as shapely_mapping
        
        try:
            geom = to_shape(feature.geometry)
        except Exception as e:
            print(f"Error mapping geometry: {e}")
            continue
        
        feature_type = feature.feature_type
        feature_name = feature.properties.get('name', f'Feature {idx + 1}') if feature.properties else f'Feature {idx + 1}'
        feature_year = feature.properties.get('year', 'N/A') if feature.properties else 'N/A'
        
        if feature_type not in style_map:
            style_id = f'style_{feature_type}'
            style = ET.SubElement(document, 'Style', {'id': style_id})
            
            if feature_type == 'point':
                icon_style = ET.SubElement(style, 'IconStyle')
                ET.SubElement(icon_style, 'scale').text = '1.2'
                icon = ET.SubElement(icon_style, 'Icon')
                ET.SubElement(icon, 'href').text = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
            elif feature_type == 'line':
                line_style = ET.SubElement(style, 'LineStyle')
                ET.SubElement(line_style, 'color').text = 'ff00ff00'
                ET.SubElement(line_style, 'width').text = '3'
            elif feature_type == 'polygon':
                poly_style = ET.SubElement(style, 'PolygonStyle')
                ET.SubElement(poly_style, 'color').text = '8000ff00'
                ET.SubElement(poly_style, 'outline').text = '1'
            
            style_map[feature_type] = style_id
        
        placemark = ET.SubElement(features_folder, 'Placemark')
        ET.SubElement(placemark, 'name').text = feature_name
        ET.SubElement(placemark, 'styleUrl').text = f'#{style_map[feature_type]}'
        
        desc = f'<b>{feature_name}</b><br/>'
        desc += f'Type: {feature_type.capitalize()}<br/>'
        desc += f'Year: {feature_year}<br/>'
        if feature.properties:
            for key, value in feature.properties.items():
                if key not in ['name', 'year']:
                    desc += f'{key}: {value}<br/>'
        
        ET.SubElement(placemark, 'description').text = desc
        
        if feature_type == 'point':
            coords = f'{geom.x:.7f},{geom.y:.7f},0'
            point_elem = ET.SubElement(placemark, 'Point')
            ET.SubElement(point_elem, 'coordinates').text = coords
        elif feature_type == 'line':
            coords_list = ' '.join([f'{p[0]:.7f},{p[1]:.7f},0' for p in geom.coords])
            ls_elem = ET.SubElement(placemark, 'LineString')
            ET.SubElement(ls_elem, 'tessellate').text = '1'
            ET.SubElement(ls_elem, 'coordinates').text = coords_list
        elif feature_type == 'polygon':
            ext_coords = ' '.join([f'{p[0]:.7f},{p[1]:.7f},0' for p in geom.exterior.coords])
            poly_elem = ET.SubElement(placemark, 'Polygon')
            outer = ET.SubElement(poly_elem, 'outerBoundaryIs')
            ls = ET.SubElement(outer, 'LinearRing')
            ET.SubElement(ls, 'coordinates').text = ext_coords
    
    ET.indent(kml)
    kml_bytes = ET.tostring(kml, encoding='unicode').encode('utf-8')
    
    # Use forest name and date in filename with proper Unicode encoding
    from datetime import datetime
    from urllib.parse import quote
    forest_name = calc.forest_name if calc.forest_name else 'Forest'
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"{forest_name}_yearly_activities_{date_str}.kml"
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        io.BytesIO(kml_bytes),
        media_type='application/vnd.google-earth.kml+xml',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


@router.get("/proposed-activities/{activity_id}/export/gpkg")
async def export_spatial_features_gpkg(
    activity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export drawn spatial features to GPKG format.
    """
    from fastapi.responses import StreamingResponse
    import io
    import tempfile
    import os
    
    activity = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.id == activity_id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Proposed activity not found")
    
    calc = db.query(Calculation).filter(Calculation.id == activity.calculation_id).first()
    if not calc or calc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    features = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.proposed_activity_id == activity_id
    ).all()
    
    # Allow export even if no features (just reference layers)
    # if not features:
    #     raise HTTPException(status_code=404, detail="No spatial features to export")
    
    activity_name = "Spatial Features"
    if activity.potential_activity:
        activity_name = activity.potential_activity.activities or activity_name
    
    try:
        import geopandas as gpd
        from shapely.geometry import mapping
        from geoalchemy2.shape import to_shape
        import pandas as pd
        
        all_records = []
        
        # Add drawn features only
        for idx, feature in enumerate(features):
            try:
                geom = to_shape(feature.geometry)
                all_records.append({
                    'id': str(feature.id),
                    'name': feature.properties.get('name', f'Feature {idx + 1}') if feature.properties else f'Feature {idx + 1}',
                    'feature_type': feature.feature_type,
                    'year': feature.properties.get('year', '') if feature.properties else '',
                    'properties_json': json.dumps(feature.properties) if feature.properties else '{}',
                    'created_at': str(feature.created_at) if feature.created_at else '',
                    'geometry': geom
                })
            except Exception as e:
                print(f"Error processing feature {feature.id}: {e}")
        
        if not all_records:
            raise HTTPException(status_code=404, detail="Failed to process any features")
        
        gdf = gpd.GeoDataFrame(all_records, crs='EPSG:4326')
        
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Write all records to GPKG with layer column
            gdf.to_file(tmp_path, layer='spatial_data', driver='GPKG')
            
            with open(tmp_path, 'rb') as f:
                gpkg_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        # Use forest name and date in filename with proper Unicode encoding
        from urllib.parse import quote
        from datetime import datetime
        forest_name = calc.forest_name if calc.forest_name else 'Forest'
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{forest_name}_yearly_activities_{date_str}.gpkg"
        encoded_filename = quote(filename)
        
        return StreamingResponse(
            io.BytesIO(gpkg_bytes),
            media_type='application/octet-stream',
            headers={'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"}
        )
        
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Required library not installed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
