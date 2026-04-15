"""
Pydantic schemas for yearly activities
"""
from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal
import json


# ===== POTENTIAL ACTIVITIES (Master List) =====

class PotentialActivityBase(BaseModel):
    project_name: Optional[str] = None
    program: Optional[str] = None
    activity: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[str] = None  # Original varchar field
    yearly_budget: Optional[str] = None  # Original varchar field
    is_default: Optional[str] = None  # Original varchar field
    display_order: int = 0
    is_active: bool = True


class PotentialActivityResponse(BaseModel):
    id: int
    sn: Optional[str] = None
    project_name: Optional[str] = None
    program: Optional[str] = None  # Maps to progarms (with typo)
    activity: Optional[str] = None  # Maps to activities
    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[str] = None
    yearly_budget: Optional[str] = None
    is_default: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    requires_map: bool = False  # NEW: Map-able activities
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle field name mapping"""
        data = {
            "id": obj.id,
            "sn": obj.sn,
            "project_name": obj.project_name,
            "program": obj.progarms,  # Map progarms to program
            "activity": obj.activities,  # Map activities to activity
            "description": obj.description,
            "unit": obj.unit,
            "quantity": obj.quantity,
            "yearly_budget": obj.yearly_budget,
            "is_default": obj.is_default,
            "display_order": obj.display_order,
            "is_active": obj.is_active,
            "requires_map": getattr(obj, 'requires_map', False),
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


# ===== PROPOSED ACTIVITIES (Per Forest) =====

class ProposedActivityBase(BaseModel):
    potential_activity_id: int
    block_id: Optional[UUID] = None
    sub_area_id: Optional[UUID] = None  # NEW: Spatial integration
    default_quantity: Decimal = Field(..., gt=0)
    default_yearly_budget: Decimal = Field(..., gt=0)
    notes: Optional[str] = None
    status: str = 'proposed'

    @validator('sub_area_id')
    def validate_sub_area_requires_block(cls, v, values):
        """Sub-area can only be set if block is also set"""
        if v is not None and values.get('block_id') is None:
            raise ValueError('sub_area_id requires block_id to be set')
        return v


class ProposedActivityCreate(ProposedActivityBase):
    pass


class ProposedActivityUpdate(BaseModel):
    block_id: Optional[UUID] = None
    sub_area_id: Optional[UUID] = None  # NEW
    default_quantity: Optional[Decimal] = Field(None, gt=0)
    default_yearly_budget: Optional[Decimal] = Field(None, gt=0)
    notes: Optional[str] = None
    status: Optional[str] = None


class ProposedActivityResponse(ProposedActivityBase):
    id: UUID
    calculation_id: UUID
    created_at: datetime
    updated_at: datetime

    # Spatial assignment options (NEW)
    assign_to_all_blocks: bool = False
    use_custom_yearly_values: bool = False

    # Include potential activity details
    potential_activity: Optional[PotentialActivityResponse] = None

    # Spatial details
    block_name: Optional[str] = None
    sub_area_name: Optional[str] = None
    sub_area_category: Optional[str] = None
    location_description: Optional[str] = None

    class Config:
        from_attributes = True


# ===== YEAR DETAILS (Year-Specific Overrides) =====

class YearDetailBase(BaseModel):
    year_number: int = Field(..., ge=1, le=10)
    quantity: Optional[Decimal] = Field(None, gt=0)
    yearly_budget: Optional[Decimal] = Field(None, gt=0)
    target_completion_month: Optional[str] = None
    actual_quantity: Optional[Decimal] = None
    actual_budget: Optional[Decimal] = None
    status: str = 'planned'
    notes: Optional[str] = None


class YearDetailCreate(YearDetailBase):
    pass


class YearDetailUpdate(BaseModel):
    quantity: Optional[Decimal] = Field(None, gt=0)
    yearly_budget: Optional[Decimal] = Field(None, gt=0)
    target_completion_month: Optional[str] = None
    actual_quantity: Optional[Decimal] = None
    actual_budget: Optional[Decimal] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class YearDetailResponse(YearDetailBase):
    id: UUID
    proposed_activity_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== COMPOSITE SCHEMAS =====

class ProposedActivityWithYears(ProposedActivityResponse):
    """Proposed activity with all 10 years of data"""
    year_details: List[YearDetailResponse] = []

    # Computed fields
    total_budget_10_years: Decimal = Field(default=0)

    @validator('total_budget_10_years', always=True)
    def calculate_total_budget(cls, v, values):
        """Calculate total budget across 10 years"""
        default_budget = values.get('default_yearly_budget', 0)
        year_details = values.get('year_details', [])

        total = Decimal(0)
        for year in range(1, 11):
            # Find if there's a year-specific override
            year_detail = next((yd for yd in year_details if yd.year_number == year), None)
            if year_detail and year_detail.yearly_budget:
                total += year_detail.yearly_budget
            else:
                total += default_budget

        return total


class ActivitySummary(BaseModel):
    """Summary statistics for yearly activities"""
    total_activities: int
    total_budget_10_years: Decimal
    by_project: dict  # {project_name: count}
    by_program: dict  # {program: count}
    by_block: dict    # {block_name: count}
    by_year: dict     # {year_number: budget}
    by_status: dict   # {status: count}


# ===== NEW: SPATIAL SCHEMAS =====

class ActivityLocationSummary(BaseModel):
    """Summary of activities by spatial location"""
    by_block: dict  # {block_name: count}
    by_sub_area_category: dict  # {category: count}
    by_sub_area: dict  # {sub_area_name: count}
    whole_forest_count: int  # Activities not assigned to specific locations


# ===== BULK OPERATIONS =====

class BulkProposedActivityCreate(BaseModel):
    """Create multiple proposed activities at once"""
    activities: List[ProposedActivityCreate]


class DefaultActivitiesRequest(BaseModel):
    """Request to auto-select default activities"""
    override_existing: bool = False  # If true, replace existing activities


# ===== SPATIAL ASSIGNMENT SCHEMAS =====

class SpatialAssignmentBase(BaseModel):
    block_id: Optional[UUID] = None
    sub_area_id: Optional[UUID] = None
    assignment_type: str = Field(default="all_blocks", pattern="^(all_blocks|block|sub_area)$")

    @validator('sub_area_id')
    def validate_sub_area_requires_block(cls, v, values):
        if v is not None and values.get('block_id') is None:
            raise ValueError('sub_area_id requires block_id to be set')
        return v


class SpatialAssignmentCreate(SpatialAssignmentBase):
    pass


class SpatialAssignmentResponse(SpatialAssignmentBase):
    id: UUID
    proposed_activity_id: UUID
    created_at: datetime

    block_name: Optional[str] = None
    sub_area_name: Optional[str] = None

    class Config:
        from_attributes = True


# ===== DRAWN FEATURE SCHEMAS =====

class DrawnFeatureBase(BaseModel):
    feature_type: str = Field(..., pattern="^(point|line|polygon)$")
    geometry: str  # GeoJSON string
    properties: dict = {}


class DrawnFeatureCreate(DrawnFeatureBase):
    @model_validator(mode='after')
    def validate_spatial_data(self) -> 'DrawnFeatureCreate':
        """Validate geometry before creating a new feature"""
        try:
            geo_dict = json.loads(self.geometry)
        except json.JSONDecodeError:
            raise ValueError("Geometry must be a valid JSON string.")

        if "type" not in geo_dict or "coordinates" not in geo_dict:
            raise ValueError("Invalid GeoJSON format: missing 'type' or 'coordinates'.")

        coords = geo_dict["coordinates"]
        geom_type = geo_dict["type"].lower()

        # Cross-check geometry type with feature_type
        expected_type = "linestring" if self.feature_type == "line" else self.feature_type
        if geom_type != expected_type:
            raise ValueError(f"Geometry type '{geom_type}' does not match feature_type '{self.feature_type}'.")

        # Validate coordinate structures
        if geom_type == "point":
            if not isinstance(coords, list) or len(coords) != 2:
                raise ValueError("Point coordinates must be a list of two numbers [lng, lat].")
            if not all(isinstance(c, (int, float)) for c in coords):
                raise ValueError("Point coordinates must be numeric values.")

        elif geom_type == "linestring":
            if not isinstance(coords, list) or len(coords) < 2:
                raise ValueError("LineString must have at least two points to form a valid line.")
            for i, point in enumerate(coords):
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError(f"LineString point {i} must be a list of [lng, lat].")

        elif geom_type == "polygon":
            if not isinstance(coords, list) or not isinstance(coords[0], list):
                raise ValueError("Polygon coordinates must be a list of rings.")
            if len(coords[0]) < 4:
                raise ValueError("Polygon must have at least 4 points (including closing point).")
            
            # Ensure the polygon is closed (first and last points match)
            ring = coords[0]
            if ring[0] != ring[-1]:
                raise ValueError("Polygon linear ring must be closed (first and last coordinate pairs must match).")

        # Validate with Shapely
        self._validate_with_shapely(geo_dict, geom_type)

        return self

    def _validate_with_shapely(self, geo_dict: dict, geom_type: str):
        """Use Shapely to validate geometry validity"""
        try:
            from shapely.geometry import shape
            geom = shape(geo_dict)
            if not geom.is_valid:
                if geom_type == "polygon":
                    raise ValueError("Invalid polygon geometry (may be self-intersecting or have invalid orientation).")
                else:
                    raise ValueError(f"Invalid {geom_type} geometry.")
        except ImportError:
            # Shapely not available, skip this validation
            pass
        except Exception as e:
            if "Invalid" not in str(e):
                raise ValueError(f"Geometry validation failed: {str(e)}")
            raise


class DrawnFeatureUpdate(BaseModel):
    feature_type: Optional[str] = Field(None, pattern="^(point|line|polygon)$")
    geometry: Optional[str] = None
    properties: Optional[dict] = None

    @model_validator(mode='after')
    def validate_spatial_data(self) -> 'DrawnFeatureUpdate':
        """Validate geometry if it's being updated"""
        if not self.geometry:
            return self

        try:
            geo_dict = json.loads(self.geometry)
        except json.JSONDecodeError:
            raise ValueError("Geometry must be a valid JSON string.")

        if "type" not in geo_dict or "coordinates" not in geo_dict:
            raise ValueError("Invalid GeoJSON format: missing 'type' or 'coordinates'.")

        coords = geo_dict["coordinates"]
        geom_type = geo_dict["type"].lower()

        # Cross-check geometry type with feature_type (if provided)
        if self.feature_type:
            expected_type = "linestring" if self.feature_type == "line" else self.feature_type
            if geom_type != expected_type:
                raise ValueError(f"Geometry type '{geom_type}' does not match feature_type '{self.feature_type}'.")

        # Validate coordinate structures
        if geom_type == "point":
            if not isinstance(coords, list) or len(coords) != 2:
                raise ValueError("Point coordinates must be a list of two numbers [lng, lat].")

        elif geom_type == "linestring":
            if not isinstance(coords, list) or len(coords) < 2:
                raise ValueError("LineString must have at least two points to form a valid line.")

        elif geom_type == "polygon":
            if not isinstance(coords, list) or not isinstance(coords[0], list):
                raise ValueError("Polygon coordinates must be a list of rings.")
            if len(coords[0]) < 4:
                raise ValueError("Polygon must have at least 4 points (including closing point).")
            
            ring = coords[0]
            if ring[0] != ring[-1]:
                raise ValueError("Polygon linear ring must be closed (first and last coordinate pairs must match).")

        # Validate with Shapely
        self._validate_with_shapely(geo_dict, geom_type)

        return self

    def _validate_with_shapely(self, geo_dict: dict, geom_type: str):
        """Use Shapely to validate geometry validity"""
        try:
            from shapely.geometry import shape
            geom = shape(geo_dict)
            if not geom.is_valid:
                if geom_type == "polygon":
                    raise ValueError("Invalid polygon geometry (may be self-intersecting or have invalid orientation).")
                else:
                    raise ValueError(f"Invalid {geom_type} geometry.")
        except ImportError:
            pass
        except Exception as e:
            if "Invalid" not in str(e):
                raise ValueError(f"Geometry validation failed: {str(e)}")
            raise


class DrawnFeatureResponse(DrawnFeatureBase):
    id: UUID
    proposed_activity_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== ENHANCED PROPOSED ACTIVITY SCHEMA =====

class ProposedActivityEnhancedResponse(ProposedActivityResponse):
    """Enhanced proposed activity with spatial assignments and drawn features"""
    assign_to_all_blocks: bool = False
    use_custom_yearly_values: bool = False
    spatial_assignments: List[SpatialAssignmentResponse] = []
    drawn_features: List[DrawnFeatureResponse] = []


# ===== BLOCK WITH SUB-AREAS =====

class BlockWithSubAreasResponse(BaseModel):
    """Block info with its sub-areas"""
    block_id: str
    block_name: str
    sub_areas: List[Any] = []  # [{id, name, category}]
