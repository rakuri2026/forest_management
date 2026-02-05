"""
Fieldbook model for boundary vertices and interpolated points
"""
from sqlalchemy import Column, String, Integer, Numeric, Boolean, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
import uuid

from app.core.database import Base


class Fieldbook(Base):
    """
    Fieldbook entries for boundary verification.
    Stores vertices extracted from polygon boundaries plus interpolated points
    at 20m intervals for field verification.
    """
    __tablename__ = "fieldbook"
    __table_args__ = (
        UniqueConstraint('calculation_id', 'point_number', name='uq_fieldbook_calc_point'),
        {'schema': 'public'}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey('public.calculations.id', ondelete='CASCADE'), nullable=False)

    # Point identification
    point_number = Column(Integer, nullable=False)  # Sequential number P1, P2, P3...
    point_type = Column(String(20), nullable=False)  # 'vertex' or 'interpolated'

    # Block information (for multi-block forests)
    block_number = Column(Integer, nullable=True)  # Which block this point belongs to (1, 2, 3...)
    block_name = Column(String(100), nullable=True)  # Optional block name (e.g., "Ward 5", "North Block")

    # Coordinates
    longitude = Column(Numeric(10, 7), nullable=False)  # WGS84 longitude
    latitude = Column(Numeric(10, 7), nullable=False)   # WGS84 latitude
    easting_utm = Column(Numeric(12, 3), nullable=True)  # UTM Easting
    northing_utm = Column(Numeric(12, 3), nullable=True) # UTM Northing
    utm_zone = Column(Integer, nullable=True)            # UTM Zone (44N or 45N for Nepal)

    # Navigation data
    azimuth_to_next = Column(Numeric(5, 2), nullable=True)    # Bearing to next point (degrees)
    distance_to_next = Column(Numeric(8, 2), nullable=True)   # Distance to next point (meters)

    # Terrain data
    elevation = Column(Numeric(8, 2), nullable=True)  # Elevation from DEM (meters)

    # Field verification
    remarks = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)  # GPS verified in field

    # Geometry for spatial queries
    point_geometry = Column(Geometry('POINT', srid=4326), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    calculation = relationship("Calculation", back_populates="fieldbook_points")

    def __repr__(self):
        return f"<Fieldbook(id={self.id}, calc={self.calculation_id}, point={self.point_number}, type={self.point_type})>"
