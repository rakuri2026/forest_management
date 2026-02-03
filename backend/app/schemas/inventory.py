"""
Inventory schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID


class TreeSpeciesCoefficientResponse(BaseModel):
    """Schema for tree species coefficient response"""
    id: int
    scientific_name: str
    local_name: Optional[str]
    max_dbh_cm: Optional[float]
    max_height_m: Optional[float]
    is_active: bool

    class Config:
        from_attributes = True


class InventoryUploadRequest(BaseModel):
    """Schema for inventory file upload metadata"""
    calculation_id: Optional[UUID] = Field(None, description="Optional link to boundary calculation")
    grid_spacing_meters: float = Field(20.0, ge=5.0, le=100.0, description="Grid spacing for mother tree selection")
    projection_epsg: Optional[int] = Field(None, description="Optional EPSG code if CRS cannot be auto-detected")


class ValidationReportResponse(BaseModel):
    """Schema for validation report"""
    summary: Dict[str, Any]
    data_detection: Dict[str, Any]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    info: List[Dict[str, Any]]
    corrections: List[Dict[str, Any]]


class InventoryCalculationCreate(BaseModel):
    """Schema for creating inventory calculation"""
    uploaded_filename: str
    calculation_id: Optional[UUID] = None
    grid_spacing_meters: float = 20.0
    projection_epsg: int = 32644


class InventoryCalculationResponse(BaseModel):
    """Schema for inventory calculation response"""
    id: UUID
    user_id: UUID
    uploaded_filename: str
    calculation_id: Optional[UUID]
    grid_spacing_meters: float
    projection_epsg: int
    status: str
    processing_time_seconds: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    # Summary statistics
    total_trees: Optional[int]
    mother_trees_count: Optional[int]
    felling_trees_count: Optional[int]
    seedling_count: Optional[int]
    total_volume_m3: Optional[float]
    total_net_volume_m3: Optional[float]
    total_net_volume_cft: Optional[float]
    total_firewood_m3: Optional[float]
    total_firewood_chatta: Optional[float]

    class Config:
        from_attributes = True


class InventoryTreeResponse(BaseModel):
    """Schema for individual tree response"""
    id: UUID
    species: str
    local_name: Optional[str]
    dia_cm: float
    height_m: Optional[float]
    tree_class: Optional[str]

    # Volumes
    stem_volume: Optional[float]
    branch_volume: Optional[float]
    tree_volume: Optional[float]
    gross_volume: Optional[float]
    net_volume: Optional[float]
    net_volume_cft: Optional[float]
    firewood_m3: Optional[float]
    firewood_chatta: Optional[float]

    # Mother tree info
    remark: Optional[str]
    grid_cell_id: Optional[int]

    # Coordinates (returned as lon, lat)
    longitude: Optional[float]
    latitude: Optional[float]

    class Config:
        from_attributes = True


class InventoryTreesListResponse(BaseModel):
    """Schema for paginated trees list"""
    trees: List[InventoryTreeResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class InventoryUpdateTreeRequest(BaseModel):
    """Schema for updating tree remark"""
    remark: str = Field(..., pattern="^(Mother Tree|Felling Tree|Seedling)$")


class InventorySummaryResponse(BaseModel):
    """Schema for inventory summary statistics"""
    inventory_id: UUID
    total_trees: int
    mother_trees_count: int
    felling_trees_count: int
    seedling_count: int

    # Volume summary
    total_volume_m3: float
    total_net_volume_m3: float
    total_net_volume_cft: float
    total_firewood_m3: float
    total_firewood_chatta: float

    # Species distribution
    species_distribution: Dict[str, int]

    # DBH classes
    dbh_classes: Dict[str, int]

    # Processing info
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    processing_time_seconds: Optional[int]


class MyInventoriesResponse(BaseModel):
    """Schema for user's inventory list"""
    inventories: List[InventoryCalculationResponse]
    total_count: int


class ExportFormat(str):
    """Export format enum"""
    CSV = "csv"
    SHAPEFILE = "shapefile"
    GEOJSON = "geojson"
