"""
ForestBlock model - stores forest blocks within a calculation
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import uuid

from ..core.database import Base


class ForestBlock(Base):
    """
    ForestBlock model - stores individual forest blocks within a calculation.
    
    Each forest can have multiple blocks (e.g., North Block, South Block, etc.)
    Created from user-uploaded polygon files where each polygon becomes a block.
    """
    __tablename__ = "forest_blocks"
    __table_args__ = {"schema": "public"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    geometry = Column(Geometry(srid=4326), nullable=False)
    area_hectares = Column(Float, nullable=False)
    index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ForestBlock(id={self.id}, name={self.name}, calculation_id={self.calculation_id})>"