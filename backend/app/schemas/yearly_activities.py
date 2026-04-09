"""
Pydantic schemas for yearly activities
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal


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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle field name mapping"""
        data = {
            "id": obj.id,
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

    # Include potential activity details
    potential_activity: Optional[PotentialActivityResponse] = None

    # Spatial details
    block_name: Optional[str] = None
    sub_area_name: Optional[str] = None  # NEW
    sub_area_category: Optional[str] = None  # NEW
    location_description: Optional[str] = None  # NEW: "Plantation Area (plantation), Block A"

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
