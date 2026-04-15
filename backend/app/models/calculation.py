"""
Calculation model - maps to existing calculations table
Stores uploaded boundaries and analysis results
"""
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Integer, ForeignKey, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
import enum
import uuid

from ..core.database import Base


class CalculationStatus(str, enum.Enum):
    """Calculation processing status"""
    PENDING = "pending"  # Waiting for block naming (multi-polygon upload)
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
    uploaded_filename = Column(String(255), nullable=True)  # Nullable for drafts
    boundary_geom = Column(Geometry(srid=4326), nullable=True)  # Nullable for drafts

    # Forest-specific metadata
    forest_name = Column(String(255), nullable=True)
    block_name = Column(String(255), nullable=True)

    # Analysis results stored as JSONB
    result_data = Column(JSONB, nullable=True)

    # Draft support for work-in-progress polygon creation
    is_draft = Column(Boolean, nullable=False, default=False)
    draft_data = Column(JSONB, nullable=True)  # Stores islands and other draft data

    # User's selected analysis and map options (for re-analysis and tracking)
    analysis_options = Column(JSONB, nullable=True)  # e.g., {"run_elevation": true, "run_slope": false, ...}
    map_options = Column(JSONB, nullable=True)  # e.g., {"boundary": true, "slope": true, ...}

    # Processing metadata
    status = Column(SQLEnum(CalculationStatus), nullable=False, default=CalculationStatus.PROCESSING)
    processing_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="calculations")
    fieldbook_points = relationship("Fieldbook", back_populates="calculation", cascade="all, delete-orphan")
    sampling_designs = relationship("SamplingDesign", back_populates="calculation", cascade="all, delete-orphan")
    biodiversity_records = relationship("CalculationBiodiversity", back_populates="calculation", cascade="all, delete-orphan")
    synthetic_tree_models = relationship("SyntheticTreeModel", back_populates="calculation", cascade="all, delete-orphan")
    household_data = relationship("HouseholdInformation", back_populates="calculation", cascade="all, delete-orphan")
    forest_committee_members = relationship("ForestUserCommittee", back_populates="calculation", cascade="all, delete-orphan")
    advisory_committee_members = relationship("AdvisoryCommittee", back_populates="calculation", cascade="all, delete-orphan")
    financial_committee_members = relationship("FinancialCommittee", back_populates="calculation", cascade="all, delete-orphan")
    proposed_activities = relationship("ProposedYearlyActivity", back_populates="calculation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Calculation(id={self.id}, user_id={self.user_id}, status={self.status.value})>"
