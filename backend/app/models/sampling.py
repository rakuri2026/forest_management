"""
Sampling design models for forest inventory
"""
from sqlalchemy import Column, String, Integer, Numeric, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
import uuid

from ..core.database import Base


class SamplingDesign(Base):
    """
    Sampling design for forest inventory.
    Stores methodology and generated sampling points for a calculation.
    """
    __tablename__ = "sampling_designs"
    __table_args__ = {'schema': 'public'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey('public.calculations.id', ondelete='CASCADE'), nullable=False)

    # Sampling methodology
    sampling_type = Column(String(50), nullable=False)  # 'systematic', 'random', 'stratified'
    intensity_per_hectare = Column(Numeric(10, 4), nullable=True)  # Points per hectare
    grid_spacing_meters = Column(Integer, nullable=True)  # For systematic sampling
    min_distance_meters = Column(Integer, nullable=True)  # Minimum distance between points

    # Plot configuration
    plot_shape = Column(String(50), nullable=True)  # 'circular', 'square', 'rectangular'
    plot_radius_meters = Column(Numeric(10, 2), nullable=True)  # For circular plots
    plot_length_meters = Column(Numeric(10, 2), nullable=True)  # For rectangular plots
    plot_width_meters = Column(Numeric(10, 2), nullable=True)   # For rectangular plots

    # Spatial data
    exclusion_geometry = Column(Geometry('MULTIPOLYGON', srid=4326), nullable=True)  # Areas to exclude
    points_geometry = Column(Geometry('MULTIPOINT', srid=4326), nullable=True)       # Generated points

    # Summary
    total_points = Column(Integer, default=0, nullable=False)
    notes = Column(Text, nullable=True)

    # Block assignment for each point (for multi-block forests)
    # Format: [{"point_index": 0, "block_number": 1, "block_name": "Ward 5"}, ...]
    points_block_assignment = Column(JSONB, nullable=True)

    # Per-block sampling parameters (Option 2: Single design with overrides)
    # Default parameters applied to all blocks unless overridden
    # Format: {"sampling_type": "systematic", "intensity_percent": 0.5, "min_samples": 5, ...}
    default_parameters = Column(JSONB, nullable=True)

    # Block-specific parameter overrides
    # Format: {"Block 1": {"intensity_percent": 1.0, "min_samples": 10}, "Block 3": {...}}
    block_overrides = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    calculation = relationship("Calculation", back_populates="sampling_designs")

    def __repr__(self):
        return f"<SamplingDesign(id={self.id}, type={self.sampling_type}, points={self.total_points})>"
