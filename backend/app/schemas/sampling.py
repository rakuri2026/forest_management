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
    sampling_intensity_percent: Optional[Decimal] = Field(
        default=Decimal("0.5"),
        ge=0.1,
        le=10.0,
        description="Sampling intensity as percentage of block area (default 0.5%)"
    )
    intensity_per_hectare: Optional[Decimal] = Field(
        None,
        ge=0.01,
        le=10.0,
        description="[DEPRECATED] Sampling intensity (points per hectare) - use sampling_intensity_percent instead"
    )
    grid_spacing_meters: Optional[int] = Field(
        None,
        ge=10,
        le=1000,
        description="[DEPRECATED] Grid spacing for systematic sampling - calculated from intensity"
    )
    min_samples_per_block: Optional[int] = Field(
        default=5,
        ge=2,
        le=10,
        description="Minimum samples per block (for blocks >= 1 ha). Default: 5"
    )
    min_samples_small_blocks: Optional[int] = Field(
        default=2,
        ge=1,
        le=5,
        description="Minimum samples for blocks < 1 hectare. Default: 2"
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
        default="circular",
        description="Sample plot shape (default: circular)"
    )
    plot_radius_meters: Optional[Decimal] = Field(
        default=Decimal("12.6156"),
        ge=1.0,
        le=50.0,
        description="Plot radius for circular plots (default: 12.62m for 500m² plot)"
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

    @field_validator('plot_radius_meters')
    @classmethod
    def validate_plot_radius(cls, v, info):
        """Validate plot radius for circular plots"""
        if info.data.get('plot_shape') == 'circular' and v is None:
            # Default to 12.6156m (500m² plot)
            return Decimal("12.6156")
        return v

    @field_validator('plot_length_meters', 'plot_width_meters')
    @classmethod
    def validate_rectangular_dimensions(cls, v, info):
        """Validate dimensions for rectangular plots"""
        if info.data.get('plot_shape') in ['square', 'rectangular']:
            if v is None:
                raise ValueError(f"plot_length_meters and plot_width_meters required for {info.data.get('plot_shape')} plots")
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


class BlockSamplingInfo(BaseModel):
    """Information about sampling in one block"""
    block_number: int
    block_name: str
    block_area_hectares: Decimal
    samples_generated: int
    minimum_enforced: bool = Field(
        ...,
        description="Whether minimum sample rule was applied"
    )
    actual_intensity_percent: Decimal = Field(
        ...,
        description="Actual sampling intensity achieved for this block"
    )

    model_config = ConfigDict(from_attributes=True)


class SamplingGenerateResponse(BaseModel):
    """Response schema for sampling design generation"""
    sampling_design_id: UUID
    calculation_id: UUID
    sampling_type: str
    total_points: int
    total_blocks: int = Field(..., description="Number of forest blocks")
    forest_area_hectares: Decimal
    requested_intensity_percent: Decimal = Field(
        ...,
        description="Requested sampling intensity percentage"
    )
    actual_intensity_per_hectare: Decimal = Field(
        ...,
        description="Actual sampling intensity achieved (points per hectare)"
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
    blocks_info: list[BlockSamplingInfo] = Field(
        default_factory=list,
        description="Per-block sampling details"
    )


class SamplingExportFormat(str):
    """Export format options"""
    CSV = "csv"
    GPX = "gpx"
    GEOJSON = "geojson"
    KML = "kml"
