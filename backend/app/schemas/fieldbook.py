"""
Pydantic schemas for Fieldbook API
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class FieldbookPointBase(BaseModel):
    """Base schema for fieldbook point"""
    point_number: int = Field(..., description="Sequential point number")
    point_type: str = Field(..., description="Type: 'vertex' or 'interpolated'")
    longitude: Decimal = Field(..., description="WGS84 longitude")
    latitude: Decimal = Field(..., description="WGS84 latitude")
    easting_utm: Optional[Decimal] = Field(None, description="UTM Easting")
    northing_utm: Optional[Decimal] = Field(None, description="UTM Northing")
    utm_zone: Optional[int] = Field(None, description="UTM Zone (44 or 45 for Nepal)")
    azimuth_to_next: Optional[Decimal] = Field(None, description="Bearing to next point (degrees)")
    distance_to_next: Optional[Decimal] = Field(None, description="Distance to next point (meters)")
    elevation: Optional[Decimal] = Field(None, description="Elevation from DEM (meters)")
    remarks: Optional[str] = Field(None, description="Field remarks")
    is_verified: bool = Field(False, description="GPS verified in field")
    block_number: Optional[int] = Field(None, description="Block number (for multi-block forests)")
    block_name: Optional[str] = Field(None, description="Block name (e.g., 'Block 1', 'Ward 5')")


class FieldbookPointCreate(FieldbookPointBase):
    """Schema for creating fieldbook point"""
    pass


class FieldbookPointUpdate(BaseModel):
    """Schema for updating fieldbook point"""
    remarks: Optional[str] = None
    is_verified: Optional[bool] = None

    model_config = ConfigDict(extra='forbid')


class FieldbookPoint(FieldbookPointBase):
    """Schema for fieldbook point response"""
    id: UUID
    calculation_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FieldbookGenerateRequest(BaseModel):
    """Request schema for generating fieldbook"""
    interpolation_distance_meters: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Distance for interpolating points between vertices (meters)"
    )
    extract_elevation: bool = Field(
        default=True,
        description="Extract elevation from DEM for each point"
    )

    model_config = ConfigDict(extra='forbid')


class FieldbookGenerateResponse(BaseModel):
    """Response schema for fieldbook generation"""
    calculation_id: UUID
    total_vertices: int = Field(..., description="Number of original vertices")
    interpolated_points: int = Field(..., description="Number of interpolated points")
    total_points: int = Field(..., description="Total points in fieldbook")
    total_perimeter_meters: Decimal = Field(..., description="Total boundary perimeter")
    avg_elevation_meters: Optional[Decimal] = Field(None, description="Average elevation")
    min_elevation_meters: Optional[Decimal] = Field(None, description="Minimum elevation")
    max_elevation_meters: Optional[Decimal] = Field(None, description="Maximum elevation")


class FieldbookListResponse(BaseModel):
    """Response schema for listing fieldbook points"""
    points: list[FieldbookPoint]
    total_count: int


class FieldbookExportFormat(str):
    """Export format options"""
    CSV = "csv"
    EXCEL = "excel"
    GPX = "gpx"
    GEOJSON = "geojson"
