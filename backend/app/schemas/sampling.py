"""
Pydantic schemas for Sampling Design API
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class SamplingDesignBase(BaseModel):
    """Base schema for sampling design"""
    sampling_type: Literal["systematic", "random", "stratified"] = Field(
        ...,
        description="Sampling methodology"
    )
    intensity_per_hectare: Optional[Decimal] = Field(
        None,
        ge=0.01,
        le=10.0,
        description="Sampling intensity (points per hectare)"
    )
    grid_spacing_meters: Optional[int] = Field(
        None,
        ge=10,
        le=1000,
        description="Grid spacing for systematic sampling"
    )
    min_distance_meters: Optional[int] = Field(
        None,
        ge=5,
        le=500,
        description="Minimum distance between points"
    )
    num_strata: Optional[int] = Field(
        None,
        ge=4,
        le=100,
        description="Number of strata for stratified sampling"
    )
    plot_shape: Optional[Literal["circular", "square", "rectangular"]] = Field(
        None,
        description="Sample plot shape"
    )
    plot_radius_meters: Optional[Decimal] = Field(
        None,
        ge=1.0,
        le=50.0,
        description="Plot radius for circular plots"
    )
    plot_length_meters: Optional[Decimal] = Field(
        None,
        ge=1.0,
        le=100.0,
        description="Plot length for rectangular plots"
    )
    plot_width_meters: Optional[Decimal] = Field(
        None,
        ge=1.0,
        le=100.0,
        description="Plot width for rectangular plots"
    )
    notes: Optional[str] = Field(None, max_length=1000, description="Design notes")


class SamplingDesignCreate(SamplingDesignBase):
    """Schema for creating sampling design"""

    @field_validator('grid_spacing_meters')
    @classmethod
    def validate_grid_spacing(cls, v, info):
        """Validate grid spacing is provided for systematic sampling"""
        if info.data.get('sampling_type') == 'systematic' and v is None:
            raise ValueError("grid_spacing_meters required for systematic sampling")
        return v

    @field_validator('intensity_per_hectare')
    @classmethod
    def validate_intensity(cls, v, info):
        """Validate intensity is provided for random/stratified sampling"""
        sampling_type = info.data.get('sampling_type')
        if sampling_type in ['random', 'stratified'] and v is None:
            raise ValueError(f"intensity_per_hectare required for {sampling_type} sampling")
        return v

    model_config = ConfigDict(extra='forbid')


class SamplingDesignUpdate(BaseModel):
    """Schema for updating sampling design"""
    notes: Optional[str] = Field(None, max_length=1000)

    model_config = ConfigDict(extra='forbid')


class SamplingDesign(SamplingDesignBase):
    """Schema for sampling design response"""
    id: UUID
    calculation_id: UUID
    total_points: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SamplingPointGeoJSON(BaseModel):
    """GeoJSON feature for a sampling point"""
    type: Literal["Feature"] = "Feature"
    geometry: dict = Field(..., description="GeoJSON Point geometry")
    properties: dict = Field(..., description="Point properties (plot number, etc.)")


class SamplingPointsGeoJSON(BaseModel):
    """GeoJSON FeatureCollection for sampling points"""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SamplingPointGeoJSON]


class SamplingGenerateResponse(BaseModel):
    """Response schema for sampling design generation"""
    sampling_design_id: UUID
    calculation_id: UUID
    sampling_type: str
    total_points: int
    forest_area_hectares: Decimal
    actual_intensity_per_hectare: Decimal = Field(
        ...,
        description="Actual sampling intensity achieved"
    )
    plot_area_sqm: Optional[Decimal] = Field(None, description="Individual plot area")
    total_sampled_area_hectares: Optional[Decimal] = Field(
        None,
        description="Total area covered by all plots"
    )
    sampling_percentage: Optional[Decimal] = Field(
        None,
        description="Percentage of forest area sampled"
    )


class SamplingExportFormat(str):
    """Export format options"""
    CSV = "csv"
    GPX = "gpx"
    GEOJSON = "geojson"
    KML = "kml"
