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
    uploaded_filename: Optional[str] = None  # Nullable for drafts
    forest_name: Optional[str]
    block_name: Optional[str]
    status: CalculationStatus
    processing_time_seconds: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None  # Added for drafts
    completed_at: Optional[datetime]
    is_draft: Optional[bool] = False  # Added for drafts
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


class ReanalysisRequest(BaseModel):
    """Schema for re-running analysis with different options"""
    # Analysis options (all optional, if not provided will use stored defaults)
    run_raster_analysis: Optional[bool] = None
    run_elevation: Optional[bool] = None
    run_slope: Optional[bool] = None
    run_aspect: Optional[bool] = None
    run_canopy: Optional[bool] = None
    run_biomass: Optional[bool] = None
    run_forest_health: Optional[bool] = None
    run_forest_type: Optional[bool] = None
    run_landcover: Optional[bool] = None
    run_forest_loss: Optional[bool] = None
    run_forest_gain: Optional[bool] = None
    run_fire_loss: Optional[bool] = None
    run_temperature: Optional[bool] = None
    run_precipitation: Optional[bool] = None
    run_soil: Optional[bool] = None
    run_proximity: Optional[bool] = None


class GenerateMapsRequest(BaseModel):
    """Schema for requesting map generation"""
    # Map types to generate (all optional, at least one should be True)
    generate_boundary_map: bool = False
    generate_topographic_map: bool = False
    generate_slope_map: bool = False
    generate_aspect_map: bool = False
    generate_forest_type_map: bool = False
    generate_canopy_height_map: bool = False
    generate_landcover_change_map: bool = False
    generate_soil_map: bool = False
    generate_forest_health_map: bool = False


class AddSpeciesRequest(BaseModel):
    """Schema for adding a species to a calculation"""
    species_id: int = Field(..., description="ID of species from tree_species_coefficients table")
    role: str = Field("Associate", description="Role of the species (Dominant, Co-dominant, Associate, Occasional, Rare)")
    availability_rank: int = Field(3, ge=1, le=4, description="Availability rank (1=Dominant, 2=Co-dominant, 3=Associate, 4=Occasional/Rare)")


class GeometryUpdateRequest(BaseModel):
    """Schema for updating calculation boundary geometry"""
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry for the new boundary")
    reanalyze: bool = Field(True, description="Whether to re-run analysis after geometry update")


class SubAreaCategory(str):
    """Valid sub-area categories"""
    PROTECTED = "protected"
    PLANTATION = "plantation"
    PRO_POOR = "pro-poor"
    RELIGIOUS = "religious"
    BIODIVERSITY = "biodiversity"
    TOURIST = "tourist"
    OFFICE = "office"
    PRIVATE_LAND = "private_land"

    @classmethod
    def valid_categories(cls) -> List[str]:
        return [cls.PROTECTED, cls.PLANTATION, cls.PRO_POOR, cls.RELIGIOUS, cls.BIODIVERSITY, cls.TOURIST, cls.OFFICE, cls.PRIVATE_LAND]


class BlockBreakdownItem(BaseModel):
    """Schema for block breakdown item"""
    blockId: str = Field(..., description="Block ID")
    blockName: str = Field(..., description="Block name")
    area: float = Field(..., description="Area in hectares in this block")
    percentage: float = Field(..., description="Percentage of sub-area in this block")

    class Config:
        # Allow field names to be used directly (camelCase from frontend)
        populate_by_name = True


class SubAreaCreateRequest(BaseModel):
    """Schema for creating a sub-area"""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., description="Sub-area category")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry")
    block_id: Optional[str] = Field(None, description="Primary block ID (for single-block sub-areas)")
    block_name: Optional[str] = Field(None, description="Primary block name (for single-block sub-areas)")
    block_breakdown: Optional[List[BlockBreakdownItem]] = Field(None, description="Block-wise breakdown for cross-block sub-areas")
    is_excluded: bool = Field(False, description="Whether this area is excluded from forest (e.g., private land)")
    area_hectares: Optional[float] = Field(None, description="Area in hectares (optional - will be calculated if not provided)")

    def validate_category(self):
        if self.category not in SubAreaCategory.valid_categories():
            raise ValueError(f"Invalid category. Must be one of: {', '.join(SubAreaCategory.valid_categories())}")


class SubAreaUpdateRequest(BaseModel):
    """Schema for updating a sub-area"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, description="Sub-area category")
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry")
    block_id: Optional[str] = Field(None, description="Associated block ID")
    block_name: Optional[str] = Field(None, description="Associated block name")
    is_excluded: Optional[bool] = Field(None, description="Whether this area is excluded from forest")


class SubAreaResponse(BaseModel):
    """Schema for sub-area response"""
    id: str
    name: str
    category: str
    geometry: Dict[str, Any]
    area_hectares: float
    block_id: Optional[str] = None
    block_name: Optional[str] = None
    block_breakdown: Optional[List[BlockBreakdownItem]] = None
    is_excluded: bool = False


class SubAreaListResponse(BaseModel):
    """Schema for sub-area list response"""
    sub_areas: List[SubAreaResponse]
    total_count: int
    total_area_hectares: float


class BlockPolygonResponse(BaseModel):
    """Schema for individual polygon extracted from boundary geometry"""
    index: int
    geometry: Dict[str, Any]
    area_hectares: float
    current_name: Optional[str] = None


class BlockPolygonListResponse(BaseModel):
    """Schema for list of polygons from a calculation"""
    polygons: List[BlockPolygonResponse]
    total_count: int


class BlockCreateRequest(BaseModel):
    """Schema for creating a forest block from polygon mapping"""
    polygon_index: int
    name: str


class BlockCreateListRequest(BaseModel):
    """Schema for creating multiple forest blocks"""
    blocks: List[BlockCreateRequest]
    # REMOVED: run_analysis parameter - analysis is now triggered separately from Analysis page


class BlockResponse(BaseModel):
    """Schema for forest block response"""
    id: str
    name: str
    geometry: Dict[str, Any]
    area_hectares: float
    index: int
    created_at: datetime

    class Config:
        from_attributes = True


class BlockListResponse(BaseModel):
    """Schema for block list response"""
    blocks: List[BlockResponse]
    total_count: int
    total_area_hectares: float


class DraftSaveRequest(BaseModel):
    """Schema for saving work-in-progress polygon creation (islands) as draft"""
    forest_name: str = Field(..., min_length=1, max_length=255, description="Name of the forest")
    islands: List[Dict[str, Any]] = Field(..., description="Array of island objects with geometry and area")
    mode: str = Field(..., pattern="^(auto|manual)$", description="Creation mode (auto or manual)")
    draft_id: Optional[UUID] = Field(None, description="Existing draft ID to update, if resuming")

    class Config:
        json_schema_extra = {
            "example": {
                "forest_name": "Community Forest ABC",
                "islands": [
                    {
                        "id": "island-1234567890",
                        "geometry": {"type": "Polygon", "coordinates": [[[85.0, 27.0], [85.1, 27.0], [85.1, 27.1], [85.0, 27.1], [85.0, 27.0]]]},
                        "area": 12.5
                    }
                ],
                "mode": "manual",
                "draft_id": None
            }
        }


class DraftResponse(BaseModel):
    """Schema for draft data response"""
    id: UUID
    forest_name: str
    islands_count: int
    total_area: float
    mode: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DraftDetailResponse(BaseModel):
    """Schema for detailed draft response including full data"""
    id: UUID
    forest_name: str
    draft_data: Dict[str, Any]  # Contains islands array and mode
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConvertDraftRequest(BaseModel):
    """Schema for converting draft to calculation"""
    outer_boundary: Dict[str, Any] = Field(..., description="GeoJSON geometry object")
    
    class Config:
        extra = "allow"  # Allow additional fields
