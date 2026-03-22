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
