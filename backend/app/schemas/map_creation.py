from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class GPSPointSchema(BaseModel):
    """GPS Point input"""
    id: str
    latitude: float
    longitude: float
    name: Optional[str] = None
    elevation: Optional[float] = None
    order: Optional[int] = None


class BlockInputSchema(BaseModel):
    """Block input for map creation"""
    id: str
    name: str
    geometry: Dict[str, Any]  # GeoJSON geometry
    area: float  # in hectares


class SubAreaInputSchema(BaseModel):
    """Sub-area input for map creation"""
    id: str
    name: str
    category: str  # protected, plantation, pro-poor, private_land, etc.
    geometry: Dict[str, Any]  # GeoJSON geometry
    area: float  # in hectares
    blockId: Optional[str] = Field(None, alias='blockId')
    blockName: Optional[str] = Field(None, alias='blockName')
    is_excluded: Optional[bool] = Field(False, alias='isExcluded')  # Private land excluded from forest calculations

    class Config:
        populate_by_name = True


class MapCreationRequest(BaseModel):
    """Request schema for creating forest map interactively"""
    forest_name: str = Field(..., min_length=1, max_length=255)
    outer_boundary: Dict[str, Any]  # GeoJSON geometry
    gps_points: Optional[List[GPSPointSchema]] = []
    blocks: List[BlockInputSchema]
    sub_areas: Optional[List[SubAreaInputSchema]] = []

    # Analysis options (same as file upload)
    analysis_options: Optional[Dict[str, bool]] = None
    map_options: Optional[Dict[str, bool]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "forest_name": "Shivapuri Community Forest",
                "outer_boundary": {
                    "type": "Polygon",
                    "coordinates": [[[85.1, 27.5], [85.2, 27.5], [85.2, 27.6], [85.1, 27.6], [85.1, 27.5]]]
                },
                "gps_points": [
                    {
                        "id": "gps-1",
                        "latitude": 27.5,
                        "longitude": 85.1,
                        "name": "Corner 1",
                        "order": 0
                    }
                ],
                "blocks": [
                    {
                        "id": "block-1",
                        "name": "Block 1",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[85.1, 27.5], [85.15, 27.5], [85.15, 27.6], [85.1, 27.6], [85.1, 27.5]]]
                        },
                        "area": 45.2
                    }
                ],
                "sub_areas": [
                    {
                        "id": "subarea-1",
                        "name": "Protected Zone 1",
                        "category": "protected",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[85.1, 27.5], [85.12, 27.5], [85.12, 27.55], [85.1, 27.55], [85.1, 27.5]]]
                        },
                        "area": 12.5,
                        "blockId": "block-1",
                        "blockName": "Block 1"
                    }
                ]
            }
        }
