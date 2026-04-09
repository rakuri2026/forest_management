"""
Pydantic schemas for Sampling Design API

Supports two sampling methods:
1. Guideline-2061: Nepal DoF standard (sample counts from lookup tables)
2. Manual: Custom sampling with full control (existing method)
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class SamplingMethod(str, Enum):
    """Sampling methodology selection"""
    GUIDELINE_2061 = "guideline_2061"
    MANUAL = "manual"


class GuidelineIntensity(str, Enum):
    """Forest Inventory Guideline-2061 sampling intensities"""
    HALF_PERCENT = "0.5"      # Standard production forest
    ONE_PERCENT = "1.0"        # Detailed inventory
    TWO_PERCENT = "2.0"        # Sustainable production forest (calculated from area, no lookup table)
    POINT_ONE_PERCENT = "0.1"  # Protected zones only


class BlockOverride(BaseModel):
    """Per-block sampling parameter overrides"""
    sampling_type: Optional[Literal["systematic", "random", "stratified"]] = Field(
        None,
        description="Override sampling type for this block"
    )
    sampling_intensity_percent: Optional[Decimal] = Field(
        None,
        ge=0.1,
        le=10.0,
        description="Override sampling intensity for this block"
    )
    min_samples_per_block: Optional[int] = Field(
        None,
        ge=2,
        le=20,
        description="Override minimum samples for this block"
    )
    boundary_buffer_meters: Optional[float] = Field(
        None,
        ge=0.0,
        le=200.0,
        description="Override boundary buffer for this block"
    )
    min_distance_meters: Optional[int] = Field(
        None,
        ge=5,
        le=500,
        description="Override minimum distance between points for this block"
    )

    model_config = ConfigDict(extra='forbid')


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
    boundary_buffer_meters: Optional[float] = Field(
        default=50.0,
        ge=0.0,
        le=200.0,
        description="Minimum distance from boundary to avoid edge effects (default: 50m)"
    )

    # Accessible forest filtering parameters (NEW - Phase 2)
    filter_tree_cover: Optional[bool] = Field(
        default=True,
        description="Filter to ESA WorldCover tree pixels (value=10) - Recommended (default: True)"
    )
    filter_slope: Optional[bool] = Field(
        default=False,
        description="Filter by slope accessibility - Optional (default: False)"
    )
    max_slope_degrees: Optional[float] = Field(
        default=45.0,
        ge=0.0,
        le=90.0,
        description="Maximum slope threshold in degrees (default: 45.0)"
    )

    notes: Optional[str] = Field(None, max_length=1000, description="Design notes")
    block_overrides: Optional[Dict[str, BlockOverride]] = Field(
        None,
        description="Per-block parameter overrides. Key is block name (e.g., 'Block 1'), value is override parameters"
    )


class SamplingDesignCreate(SamplingDesignBase):
    """
    Schema for creating sampling design with either Guideline-2061 or Manual method.

    Guideline-2061 Method:
    - Sample counts determined by lookup tables based on block size
    - Supports 0.5%, 1%, or 0.1% intensity
    - Systematic sampling only
    - Plot size in sqm (100-500 for production, 25-100 for protected)

    Manual Method:
    - Existing flexible sampling system
    - Supports systematic, random, stratified
    - Intensity as percentage with min samples rules
    - Plot dimensions in meters
    """
    # Override sampling_type to be optional - it's required for Manual method but not for Guideline-2061
    sampling_type: Optional[Literal["systematic", "random", "stratified"]] = Field(
        default="systematic",
        description="Sampling methodology (optional for Guideline-2061, required for Manual)"
    )
    
    # Method selection
    sampling_method: SamplingMethod = Field(
        default=SamplingMethod.GUIDELINE_2061,
        description="Sampling methodology: guideline_2061 (recommended) or manual (advanced)"
    )

    # Guideline-2061 specific parameters
    productive_intensity: Optional[GuidelineIntensity] = Field(
        default=GuidelineIntensity.HALF_PERCENT,
        description="Sampling intensity for productive forest (0.5% or 1%) - Guideline-2061 only"
    )
    sample_protected_zone: Optional[bool] = Field(
        default=False,
        description="Include protected zone sampling at 0.1% intensity - Guideline-2061 only"
    )
    plot_size_sqm: Optional[int] = Field(
        default=500,
        description="Plot size in square meters - Guideline-2061 only. "
                   "Options: 500, 400, 300, 200, 100 (production); 25, 100 (protected)"
    )

    @field_validator('plot_size_sqm')
    @classmethod
    def validate_plot_size_sqm(cls, v, info):
        """Validate plot size for Guideline-2061 method

        When sampling protected zones, the user-specified plot size is for PRODUCTIVE zones.
        Protected zones will automatically use 100 sqm plots (standard for protected areas).
        """
        if info.data.get('sampling_method') == SamplingMethod.GUIDELINE_2061 and v is not None:
            valid_production_sizes = [100, 200, 300, 400, 500]

            # Plot size is for productive forests (or both if 100 sqm)
            if v not in valid_production_sizes:
                raise ValueError(
                    f"Plot size must be one of {valid_production_sizes} sqm. Got: {v}"
                )
        return v

    @field_validator('plot_radius_meters')
    @classmethod
    def validate_plot_radius(cls, v, info):
        """Validate plot radius for circular plots (Manual method)"""
        if info.data.get('sampling_method') == SamplingMethod.MANUAL:
            if info.data.get('plot_shape') == 'circular' and v is None:
                # Default to 12.6156m (500m² plot)
                return Decimal("12.6156")
        return v

    @field_validator('plot_length_meters', 'plot_width_meters')
    @classmethod
    def validate_rectangular_dimensions(cls, v, info):
        """Validate dimensions for rectangular plots (Manual method)"""
        if info.data.get('sampling_method') == SamplingMethod.MANUAL:
            if info.data.get('plot_shape') in ['square', 'rectangular']:
                if v is None:
                    raise ValueError(
                        f"plot_length_meters and plot_width_meters required for "
                        f"{info.data.get('plot_shape')} plots"
                    )
        return v

    @field_validator('sampling_type')
    @classmethod
    def validate_sampling_type(cls, v, info):
        """Ensure systematic sampling for Guideline-2061"""
        if info.data.get('sampling_method') == SamplingMethod.GUIDELINE_2061:
            if v and v != 'systematic':
                raise ValueError(
                    "Guideline-2061 method only supports systematic sampling. "
                    "For random/stratified, use manual method."
                )
            return 'systematic'  # Force systematic for guideline
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
    default_parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Default sampling parameters applied to all blocks"
    )
    block_overrides: Optional[Dict[str, Any]] = Field(
        None,
        description="Per-block parameter overrides"
    )

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
    grid_spacing_meters: Optional[Decimal] = Field(
        None,
        description="Grid spacing used for systematic sampling (meters)"
    )

    # Guideline-2061 specific fields
    samples_from_guideline: Optional[int] = Field(
        None,
        description="Sample count from Guideline-2061 table (if using guideline method)"
    )
    is_protected: Optional[str | bool] = Field(
        None,
        description="Protection status: 'Yes'/'No'/'Mixed' (string) or True/False (bool, legacy)"
    )
    guideline_fallback_used: Optional[bool] = Field(
        None,
        description="Whether manual calculation was used because block exceeded table range"
    )

    # Accessible forest area breakdown
    accessible_forest_area_ha: Optional[Decimal] = Field(
        None,
        description="Accessible forest area in hectares (tree cover + slope OK)"
    )
    inaccessible_steep_forest_ha: Optional[Decimal] = Field(
        None,
        description="Tree cover but too steep for sampling"
    )
    non_forest_area_ha: Optional[Decimal] = Field(
        None,
        description="Non-tree cover area (grassland, cropland, water, etc.)"
    )
    accessible_forest_percentage: Optional[Decimal] = Field(
        None,
        description="Percentage of block that is accessible forest"
    )
    sampling_method: Optional[str] = Field(
        None,
        description="Sampling method used: 'systematic' or 'random' (random used as fallback when systematic fails)"
    )
    protected_area_ha: Optional[Decimal] = Field(
        None,
        description="Protected area in hectares within this block"
    )
    protected_samples_count: Optional[int] = Field(
        None,
        description="Number of samples generated in protected area"
    )
    protected_sampling_method: Optional[str] = Field(
        None,
        description="Sampling method used for protected area: 'systematic' or 'random'"
    )
    protected_grid_spacing_meters: Optional[Decimal] = Field(
        None,
        description="Grid spacing used for protected area systematic sampling (meters)"
    )
    protected_intensity_percent: Optional[Decimal] = Field(
        None,
        description="Actual sampling intensity achieved for protected area"
    )
    productive_area_ha: Optional[Decimal] = Field(
        None,
        description="Productive (non-protected) forest area in hectares"
    )
    productive_samples_count: Optional[int] = Field(
        None,
        description="Number of samples generated in productive area"
    )
    productive_sampling_method: Optional[str] = Field(
        None,
        description="Sampling method used for productive area: 'systematic' or 'random'"
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


class ProtectedZoneInfo(BaseModel):
    """
    Information about protected zones in a calculation.
    Used to determine if protected zone sampling option should be shown.
    """
    has_protected: bool = Field(
        ...,
        description="Whether calculation has any protected zones"
    )
    protected_area_hectares: float = Field(
        ...,
        description="Total protected area in hectares"
    )
    protected_zone_names: list[str] = Field(
        default_factory=list,
        description="Names of protected zones"
    )
    protected_zone_count: int = Field(
        ...,
        description="Number of protected zones"
    )
    productive_area_hectares: float = Field(
        ...,
        description="Non-protected (productive) area in hectares"
    )
    total_area_hectares: float = Field(
        ...,
        description="Total forest area in hectares"
    )

    model_config = ConfigDict(from_attributes=True)
