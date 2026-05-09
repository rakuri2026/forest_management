from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ExtentUploadRequest(BaseModel):
    source_type: str = "uploaded"


class ManualExtentRequest(BaseModel):
    geometry: Dict[str, Any]


class AutoBufferRequest(BaseModel):
    buffer_distance: int = 1000


class AnalysisRequest(BaseModel):
    extent_id: int


class SettlementStatistics(BaseModel):
    settlement_id: Optional[int] = None
    settlement_name: str
    building_count: int
    total_area_m2: float
    small_buildings: int = 0
    medium_buildings: int = 0
    large_buildings: int = 0
    avg_building_size_m2: float = 0
    direction_from_forest: str
    lat: Optional[float] = None
    lon: Optional[float] = None

    class Config:
        from_attributes = True


class BuildingPoint(BaseModel):
    lat: float
    lon: float
    area: Optional[float] = None


class UserGroupResults(BaseModel):
    extent_id: int
    extent_geometry: Dict[str, Any]
    forest_boundary: Dict[str, Any]
    settlements: List[SettlementStatistics]
    buildings: List[BuildingPoint]


class ExtentResponse(BaseModel):
    extent_id: int
    message: str


class AnalysisResponse(BaseModel):
    message: str
    settlements_analyzed: int
    total_buildings: int


class POILayer(BaseModel):
    name: str
    lon: float
    lat: float
    type: Optional[str] = None


class POIResponse(BaseModel):
    poi: Optional[List[POILayer]] = []
    education: Optional[List[POILayer]] = []
    health: Optional[List[POILayer]] = []
    rivers: Optional[List[Dict[str, Any]]] = []


# ============================================================================
# Land Cover Analysis Schemas
# ============================================================================

class LandCoverClass(BaseModel):
    """Individual land cover class statistics"""
    class_code: int
    class_name: str
    area_ha: float
    percentage: float
    avg_biomass_mg_per_ha: float
    min_biomass_mg_per_ha: float
    max_biomass_mg_per_ha: float
    total_biomass_mg: float
    avg_volume_m3_per_ha: float
    total_volume_m3: float
    pixel_count: int


class LandCoverAnalysisResponse(BaseModel):
    """Complete land cover analysis results"""
    # Area summary
    user_group_area_ha: float
    forest_overlap_area_ha: float
    net_analysis_area_ha: float

    # Land cover breakdown
    land_cover_classes: List[LandCoverClass]

    # Overall biomass summary
    total_biomass_mg: float
    total_volume_m3: float
    avg_biomass_mg_per_ha: float
    avg_volume_m3_per_ha: float

    # Metadata
    analysis_date: datetime
    has_forest_overlap: bool

    class Config:
        from_attributes = True
