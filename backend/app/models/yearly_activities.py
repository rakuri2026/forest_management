"""
Yearly Activities models for community forest planning
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean, Numeric, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database import Base


class PotentialActivity(Base):
    """
    Master list of all possible activities for community forests.
    Admins manage this table.
    """
    __tablename__ = "potential_activities"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), nullable=True)

    # Hierarchy (existing columns with typo in original table)
    sn = Column(String, nullable=True)
    project_name = Column(String, nullable=True)
    progarms = Column(String, nullable=True)  # Note: typo in original table
    activities = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    quantity = Column(String, nullable=True)  # Original as varchar
    yearly_budget = Column(String, nullable=True)  # Original as varchar
    is_default = Column(String, nullable=True)  # Original as varchar

    # New columns added by migration
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    proposed_activities = relationship("ProposedYearlyActivity", back_populates="potential_activity", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PotentialActivity(id={self.id}, activity='{self.activities}')>"

    @property
    def program(self):
        """Alias for progarms field (with typo)"""
        return self.progarms

    @property
    def activity(self):
        """Alias for activities field"""
        return self.activities


class ProposedYearlyActivity(Base):
    """
    Activities selected by a specific community forest.
    Each forest can select multiple activities from the master list.
    Includes spatial assignment to blocks and sub-areas.
    """
    __tablename__ = "proposed_yearly_activities"
    __table_args__ = (
        CheckConstraint(
            '(sub_area_id IS NULL) OR (sub_area_id IS NOT NULL AND block_id IS NOT NULL)',
            name='check_sub_area_has_block'
        ),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    potential_activity_id = Column(Integer, ForeignKey("public.potential_activities.id", ondelete="CASCADE"), nullable=False)
    block_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_blocks.id", ondelete="SET NULL"), nullable=True)
    sub_area_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_sub_areas.id", ondelete="SET NULL"), nullable=True)

    # Default values (apply to all 10 years unless overridden)
    default_quantity = Column(Numeric(10, 2), nullable=False)
    default_yearly_budget = Column(Numeric(12, 2), nullable=False)

    # Metadata
    notes = Column(Text, nullable=True)
    status = Column(String(50), default='proposed', nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    calculation = relationship("Calculation", back_populates="proposed_activities")
    potential_activity = relationship("PotentialActivity", back_populates="proposed_activities")
    block = relationship("ForestBlock", foreign_keys=[block_id])
    sub_area = relationship("ForestSubArea", foreign_keys=[sub_area_id])
    year_details = relationship("ActivityYearDetail", back_populates="proposed_activity", cascade="all, delete-orphan")

    def __repr__(self):
        location = "entire forest"
        if self.sub_area:
            location = f"{self.sub_area.name} ({self.sub_area.category})"
        elif self.block:
            location = f"{self.block.name}"
        return f"<ProposedYearlyActivity(id={self.id}, location={location})>"


class ActivityYearDetail(Base):
    """
    Year-specific overrides for quantity and budget.
    If a row exists, it overrides the default values for that year.
    """
    __tablename__ = "activity_year_details"
    __table_args__ = (
        CheckConstraint('year_number >= 1 AND year_number <= 10', name='check_year_number'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key
    proposed_activity_id = Column(UUID(as_uuid=True), ForeignKey("public.proposed_yearly_activities.id", ondelete="CASCADE"), nullable=False)

    # Year tracking
    year_number = Column(Integer, nullable=False)

    # Overridden values (NULL = use default from proposed_yearly_activities)
    quantity = Column(Numeric(10, 2), nullable=True)
    yearly_budget = Column(Numeric(12, 2), nullable=True)

    # Year-specific details
    target_completion_month = Column(String(20), nullable=True)
    actual_quantity = Column(Numeric(10, 2), nullable=True)
    actual_budget = Column(Numeric(12, 2), nullable=True)
    status = Column(String(50), default='planned', nullable=False)

    # Notes
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    proposed_activity = relationship("ProposedYearlyActivity", back_populates="year_details")

    def __repr__(self):
        return f"<ActivityYearDetail(id={self.id}, year={self.year_number})>"
