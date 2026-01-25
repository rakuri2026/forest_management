"""
Forest management schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID

from ..models.calculation import CalculationStatus


class CommunityForestResponse(BaseModel):
    """Schema for community forest data response"""
    id: int
    name: Optional[str]
    code: Optional[str]
    regime: Optional[str]
    area_hectares: float
    geometry: Optional[Dict[str, Any]]  # GeoJSON

    class Config:
        from_attributes = True


class ForestManagerCreate(BaseModel):
    """Schema for creating forest manager assignment"""
    user_id: UUID
    community_forest_id: int
    role: str = Field(..., pattern="^(manager|chairman|secretary|member)$")


class ForestManagerResponse(BaseModel):
    """Schema for forest manager data response"""
    id: UUID
    user_id: UUID
    community_forest_id: int
    role: str
    assigned_date: datetime
    is_active: bool

    class Config:
        from_attributes = True


class CalculationCreate(BaseModel):
    """Schema for creating a new calculation"""
    forest_name: Optional[str] = None
    block_name: Optional[str] = None


class CalculationResponse(BaseModel):
    """Schema for calculation data response"""
    id: UUID
    user_id: UUID
    uploaded_filename: str
    forest_name: Optional[str]
    block_name: Optional[str]
    status: CalculationStatus
    processing_time_seconds: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    geometry: Optional[Dict[str, Any]]  # GeoJSON
    result_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class AnalysisResultResponse(BaseModel):
    """Schema for analysis results"""
    calculation_id: UUID
    status: CalculationStatus
    processing_time_seconds: Optional[int]

    # Area calculations
    area_hectares: Optional[float]
    area_sqm: Optional[float]

    # Elevation metrics
    elevation_min: Optional[float]
    elevation_max: Optional[float]
    elevation_mean: Optional[float]

    # Slope analysis
    slope_dominant_class: Optional[str]
    slope_percentages: Optional[Dict[str, float]]

    # Aspect analysis
    aspect_dominant: Optional[str]
    aspect_percentages: Optional[Dict[str, float]]

    # Canopy height
    canopy_dominant_class: Optional[str]
    canopy_percentages: Optional[Dict[str, float]]

    # Forest health
    forest_health_dominant: Optional[str]
    forest_health_percentages: Optional[Dict[str, float]]

    # Biomass and carbon
    agb_mean: Optional[float]
    agb_total: Optional[float]
    carbon_stock: Optional[float]

    # Climate
    temperature_mean: Optional[float]
    precipitation_mean: Optional[float]

    # Land cover
    landcover_dominant: Optional[str]
    landcover_percentages: Optional[Dict[str, float]]

    # Forest change
    forest_loss_hectares: Optional[float]
    forest_gain_hectares: Optional[float]
    forest_loss_by_year: Optional[Dict[str, float]]

    # Administrative location
    province: Optional[str]
    municipality: Optional[str]
    ward: Optional[str]

    # Proximity analysis
    nearest_settlement: Optional[Dict[str, Any]]
    nearest_road: Optional[Dict[str, Any]]
    nearest_river: Optional[Dict[str, Any]]
    buildings_within_1km: Optional[int]

    # Full JSONB data
    full_results: Optional[Dict[str, Any]]


class ForestListQuery(BaseModel):
    """Schema for querying forest list"""
    search: Optional[str] = None
    regime: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class MyForestsResponse(BaseModel):
    """Schema for user's assigned forests"""
    forests: List[Dict[str, Any]]
    total_count: int
    total_area_hectares: float
