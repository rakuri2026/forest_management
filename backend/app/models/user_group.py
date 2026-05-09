from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from geoalchemy2 import Geometry
from app.core.database import Base
from datetime import datetime


class UserGroupExtent(Base):
    """
    User Group Extent - stores the boundary polygon defining the user group area
    Can be created by: upload, manual digitization, or auto-buffer
    """
    __tablename__ = "user_group_extents"
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=False)
    extent_geometry = Column(Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=False)
    source_type = Column(String(50))  # 'uploaded', 'manual', 'auto_buffer'
    buffer_distance_m = Column(Integer, nullable=True)  # only for auto_buffer type
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


class UserGroupBuilding(Base):
    """
    User Group Building Statistics - stores analysis results per settlement
    Includes building count, total area, and direction from forest centroid
    """
    __tablename__ = "user_group_buildings"
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    extent_id = Column(Integer, ForeignKey("public.user_group_extents.id", ondelete="CASCADE"), nullable=False)
    settlement_id = Column(Integer, nullable=True)  # Reference to admin.settlement
    settlement_name = Column(String(255))
    building_count = Column(Integer)
    total_building_area_m2 = Column(Numeric(12, 2))
    direction_from_forest = Column(String(20))  # N, NE, E, SE, S, SW, W, NW
    buildings_geojson = Column(JSONB)  # Store building centroids as GeoJSON
    settlement_location = Column(Geometry(geometry_type='POINT', srid=4326))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
