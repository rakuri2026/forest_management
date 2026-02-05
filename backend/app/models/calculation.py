"""
Calculation model - maps to existing calculations table
Stores uploaded boundaries and analysis results
"""
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Integer, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import enum
import uuid

from ..core.database import Base


class CalculationStatus(str, enum.Enum):
    """Calculation processing status"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Calculation(Base):
    """
    Calculation model - maps to public.calculations table
    Stores user-uploaded forest boundaries and analysis results
    """
    __tablename__ = "calculations"
    __table_args__ = (
        Index('idx_calculations_boundary_geom', 'boundary_geom', postgresql_using='gist'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=False)
    application_id = Column(UUID(as_uuid=True), nullable=True)  # Optional reference to application

    # File and geometry data
    uploaded_filename = Column(String(255), nullable=False)
    boundary_geom = Column(Geometry(srid=4326), nullable=False)  # Accepts Polygon or MultiPolygon

    # Forest-specific metadata
    forest_name = Column(String(255), nullable=True)
    block_name = Column(String(255), nullable=True)

    # Analysis results stored as JSONB
    result_data = Column(JSONB, nullable=True)

    # Processing metadata
    status = Column(SQLEnum(CalculationStatus), nullable=False, default=CalculationStatus.PROCESSING)
    processing_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="calculations")
    fieldbook_points = relationship("Fieldbook", back_populates="calculation", cascade="all, delete-orphan")
    sampling_designs = relationship("SamplingDesign", back_populates="calculation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Calculation(id={self.id}, user_id={self.user_id}, status={self.status.value})>"
