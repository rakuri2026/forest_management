"""
ForestBlock model - stores forest blocks and compartments within a calculation
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
    ForestBlock model - stores individual forest blocks and compartments.

    A forest block can be:
    1. A parent block (is_compartment=False, parent_block_id=NULL)
    2. A compartment (is_compartment=True, parent_block_id=<parent_id>)

    Each forest can have multiple blocks (e.g., North Block, South Block, etc.)
    Blocks can be subdivided into compartments for finer management.
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

    # Compartment fields
    is_compartment = Column(Boolean, default=False, nullable=False)
    parent_block_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_blocks.id", ondelete="CASCADE"), nullable=True)
    compartment_code = Column(String(50), nullable=True)
    area_sqm = Column(Float, nullable=True)

    # Relationships
    parent_block = relationship("ForestBlock", remote_side=[id], backref="compartments", foreign_keys=[parent_block_id])

    def __repr__(self):
        return f"<ForestBlock(id={self.id}, name={self.name}, is_compartment={self.is_compartment})>"