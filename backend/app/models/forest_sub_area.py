"""
ForestSubArea model - stores sub-areas within forest blocks
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import uuid

from ..core.database import Base


class ForestSubArea(Base):
    """
    ForestSubArea model - stores sub-areas within forest blocks.
    
    Sub-areas include: Protected Zone, Plantation Area, Pro-Poor, Religious,
    Biodiversity, Tourist, Office, and Private Land (excluded).
    
    Private land sub-areas are excluded from calculations (treated as doughnut holes).
    Sub-areas can span multiple blocks (block_id can be null, with area tracked per block).
    """
    __tablename__ = "forest_sub_areas"
    __table_args__ = {"schema": "public"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    block_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_blocks.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)
    geometry = Column(Geometry(srid=4326), nullable=False)
    area_hectares = Column(Float, nullable=False)
    is_excluded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ForestSubArea(id={self.id}, name={self.name}, category={self.category})>"