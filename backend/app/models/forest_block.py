"""
ForestBlock model - stores forest blocks within a calculation
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Float, Boolean
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
    Supports compartment splitting and sub-compartment hierarchy.
    """
    __tablename__ = "forest_blocks"
    __table_args__ = {"schema": "public"}
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    geometry = Column(Geometry(srid=4326), nullable=False)
    area_hectares = Column(Float, nullable=False)
    index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Compartment fields
    is_compartment = Column(Boolean, nullable=False, default=False)
    parent_block_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_blocks.id", ondelete="CASCADE"), nullable=True)
    compartment_code = Column(String(50), nullable=True)
    area_sqm = Column(Float, nullable=True)
    
    # NEW: Hierarchy fields for sub-compartment support
    division_level = Column(Integer, nullable=False, default=0)  # 0=Block, 1=Compartment, 2+=Sub-compartment
    color = Column(String(7), nullable=True)  # Hex color like "#FF5733"
    is_locked = Column(Boolean, nullable=False, default=False)  # Lock from further division
    child_count = Column(Integer, nullable=False, default=0)  # Cached child count
    display_order = Column(Integer, nullable=False, default=0)  # Order in parent's list
    
    # Relationships
    parent_block = relationship("ForestBlock", remote_side=[id], foreign_keys=[parent_block_id])
    compartments = relationship("ForestBlock", back_populates="parent_block", foreign_keys=[parent_block_id])
    
    def __repr__(self):
        return f"<ForestBlock(id={self.id}, name={self.name}, level={self.division_level}, locked={self.is_locked})>"