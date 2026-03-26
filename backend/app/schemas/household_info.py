"""
Pydantic schemas for Household Information
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID


# Base schema with common fields
class HouseholdInfoBase(BaseModel):
    """Base household information fields"""
    house_no: int = Field(..., description="House number", ge=1)
    surname: str = Field(..., min_length=1, max_length=100, description="Surname (थर)")
    household_head_male: Optional[str] = Field(None, max_length=200, description="Male household head name")
    household_head_female: Optional[str] = Field(None, max_length=200, description="Female household head name")
    address_tole: Optional[str] = Field(None, max_length=200, description="Address tole")
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90, description="Latitude")
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180, description="Longitude")

    # Population
    female_count: int = Field(0, ge=0, description="Number of females")
    male_count: int = Field(0, ge=0, description="Number of males")

    # Land & Occupation
    land_area: Optional[Decimal] = Field(None, ge=0, description="Land area")
    land_unit: Optional[str] = Field(None, description="Land unit (ropani/kaththa)")
    forest_based_occupation: bool = Field(False, description="Forest-based occupation")
    other_occupation: bool = Field(False, description="Other occupation")

    # Livestock
    cow_ox_count: int = Field(0, ge=0, description="Number of cows/oxen")
    buffalo_count: int = Field(0, ge=0, description="Number of buffaloes")
    goat_sheep_count: int = Field(0, ge=0, description="Number of goats/sheep")

    # Forest Product Demands
    timber_demand_cft: Decimal = Field(5, ge=0, description="Timber demand in cubic feet")
    pole_demand: int = Field(5, ge=0, description="Pole demand")
    firewood_demand_bhari: Optional[Decimal] = Field(None, ge=0, description="Firewood demand in bhari")
    grass_demand_bhari: Optional[Decimal] = Field(None, ge=0, description="Grass demand in bhari")
    bedding_demand_bhari: Optional[Decimal] = Field(None, ge=0, description="Bedding material demand in bhari")

    # Flags
    firewood_auto_calculated: bool = Field(True, description="Firewood auto-calculated flag")
    grass_auto_calculated: bool = Field(True, description="Grass auto-calculated flag")
    bedding_auto_calculated: bool = Field(True, description="Bedding auto-calculated flag")

    # Classification
    caste_classification_ne: Optional[str] = Field(None, max_length=100, description="Caste classification (Nepali)")
    caste_classification_en: Optional[str] = Field(None, max_length=100, description="Caste classification (English)")
    caste_classification_manual: bool = Field(False, description="Manual classification override flag")

    # Other Info
    other_group_membership: Optional[bool] = Field(None, description="Other group membership")
    prosperity_level: str = Field('मध्यम', description="Prosperity level")
    prosperity_auto_suggested: bool = Field(True, description="Prosperity auto-suggested flag")
    remarks: Optional[str] = Field(None, description="Remarks")

    @validator('land_unit')
    def validate_land_unit(cls, v):
        if v and v not in ['ropani', 'kaththa']:
            raise ValueError("Land unit must be 'ropani' or 'kaththa'")
        return v

    @validator('prosperity_level')
    def validate_prosperity_level(cls, v):
        valid_levels = ['सम्पन्न', 'मध्यम', 'विपन्न', 'अति विपन्न']
        if v not in valid_levels:
            raise ValueError(f"Prosperity level must be one of: {', '.join(valid_levels)}")
        return v


# Schema for creating household info
class HouseholdInfoCreate(HouseholdInfoBase):
    """Schema for creating household information"""
    pass


# Schema for updating household info
class HouseholdInfoUpdate(BaseModel):
    """Schema for updating household information (all fields optional)"""
    house_no: Optional[int] = Field(None, ge=1)
    surname: Optional[str] = Field(None, min_length=1, max_length=100)
    household_head_male: Optional[str] = Field(None, max_length=200)
    household_head_female: Optional[str] = Field(None, max_length=200)
    address_tole: Optional[str] = Field(None, max_length=200)
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    female_count: Optional[int] = Field(None, ge=0)
    male_count: Optional[int] = Field(None, ge=0)
    land_area: Optional[Decimal] = Field(None, ge=0)
    land_unit: Optional[str] = None
    forest_based_occupation: Optional[bool] = None
    other_occupation: Optional[bool] = None
    cow_ox_count: Optional[int] = Field(None, ge=0)
    buffalo_count: Optional[int] = Field(None, ge=0)
    goat_sheep_count: Optional[int] = Field(None, ge=0)
    timber_demand_cft: Optional[Decimal] = Field(None, ge=0)
    pole_demand: Optional[int] = Field(None, ge=0)
    firewood_demand_bhari: Optional[Decimal] = Field(None, ge=0)
    grass_demand_bhari: Optional[Decimal] = Field(None, ge=0)
    bedding_demand_bhari: Optional[Decimal] = Field(None, ge=0)
    firewood_auto_calculated: Optional[bool] = None
    grass_auto_calculated: Optional[bool] = None
    bedding_auto_calculated: Optional[bool] = None
    caste_classification_ne: Optional[str] = Field(None, max_length=100)
    caste_classification_en: Optional[str] = Field(None, max_length=100)
    caste_classification_manual: Optional[bool] = None
    other_group_membership: Optional[bool] = None
    prosperity_level: Optional[str] = None
    prosperity_auto_suggested: Optional[bool] = None
    remarks: Optional[str] = None


# Schema for response (includes computed fields and metadata)
class HouseholdInfoResponse(HouseholdInfoBase):
    """Schema for household information response"""
    id: UUID
    calculation_id: UUID
    total_population: int = Field(..., description="Total population (computed)")
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    class Config:
        from_attributes = True


# Schema for bulk upload validation result
class HouseholdUploadValidation(BaseModel):
    """Validation result for a single household row"""
    row_number: int
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    data: Optional[dict] = None


class HouseholdUploadResponse(BaseModel):
    """Response for household upload"""
    success: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    records_imported: int
    records_updated: int = 0  # Number of existing records updated
    validations: List[HouseholdUploadValidation]


# Schema for household summary statistics
class HouseholdSummary(BaseModel):
    """Summary statistics for household data"""
    total_households: int
    total_population: int
    total_male: int
    total_female: int
    total_cow_ox: int
    total_buffalo: int
    total_goat_sheep: int
    total_timber_demand_cft: Decimal
    total_pole_demand: int
    total_firewood_demand_bhari: Decimal
    total_grass_demand_bhari: Decimal
    total_bedding_demand_bhari: Decimal
    avg_land_area: Optional[Decimal] = None
    caste_distribution: dict  # {classification: count}
    prosperity_distribution: dict  # {level: count}
    forest_dependent_households: int


# Schema for caste lookup
class CasteClassificationResponse(BaseModel):
    """Response for caste classification lookup"""
    classification_ne: str
    classification_en: Optional[str] = None
    caste_ne: str
    caste_en: Optional[str] = None
    surname_ne: str
    surname_en: Optional[str] = None

    class Config:
        from_attributes = True


# Schema for surname suggestions
class SurnameSuggestion(BaseModel):
    """Surname suggestion for autocomplete"""
    surname_ne: str
    surname_en: Optional[str] = None
    classification_ne: str
    caste_ne: str


# Schema for template download options
class TemplateDownloadOptions(BaseModel):
    """Options for downloading household template"""
    land_unit: str = Field('ropani', description="Land unit (ropani/kaththa)")
    include_coordinates: bool = Field(False, description="Include coordinate columns")

    @validator('land_unit')
    def validate_land_unit(cls, v):
        if v not in ['ropani', 'kaththa']:
            raise ValueError("Land unit must be 'ropani' or 'kaththa'")
        return v
