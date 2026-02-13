"""
Inventory models - maps to inventory tables
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid

from ..core.database import Base


class TreeSpeciesCoefficient(Base):
    """
    Tree species coefficients model
    Stores allometric equations for volume calculations
    """
    __tablename__ = "tree_species_coefficients"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    scientific_name = Column(String(255), unique=True, nullable=False)
    local_name = Column(String(100), nullable=True)

    # Volume equation coefficients
    a = Column(Float, nullable=True)
    b = Column(Float, nullable=True)
    c = Column(Float, nullable=True)
    a1 = Column(Float, nullable=True)
    b1 = Column(Float, nullable=True)

    # Additional parameters
    s = Column(Float, nullable=True)
    m = Column(Float, nullable=True)
    bg = Column(Float, nullable=True)

    # Species metadata
    aliases = Column(JSONB, nullable=True)  # Array stored as JSONB
    max_dbh_cm = Column(Float, nullable=True)
    max_height_m = Column(Float, nullable=True)
    typical_hd_ratio_min = Column(Float, nullable=True)
    typical_hd_ratio_max = Column(Float, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<TreeSpeciesCoefficient(id={self.id}, name='{self.scientific_name}')>"


class InventoryCalculation(Base):
    """
    Inventory calculation model
    Stores main inventory processing records
    """
    __tablename__ = "inventory_calculations"
    __table_args__ = (
        Index('idx_inventory_calc_user', 'user_id'),
        Index('idx_inventory_calc_calculation', 'calculation_id'),
        Index('idx_inventory_calc_status', 'status'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="SET NULL"), nullable=True, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    uploaded_filename = Column(String(255), nullable=False)

    # Grid settings for mother tree selection
    grid_spacing_meters = Column(Float, default=20.0, nullable=False)
    projection_epsg = Column(Integer, default=32644, nullable=False)

    # Column mapping (stores user's column mapping for processing)
    column_mapping = Column(JSONB, nullable=True)

    # Processing status
    status = Column(String(50), default='processing', nullable=False)
    processing_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Summary statistics
    total_trees = Column(Integer, nullable=True)
    mother_trees_count = Column(Integer, nullable=True)
    felling_trees_count = Column(Integer, nullable=True)
    seedling_count = Column(Integer, nullable=True)
    total_volume_m3 = Column(Float, nullable=True)
    total_net_volume_m3 = Column(Float, nullable=True)
    total_net_volume_cft = Column(Float, nullable=True)
    total_firewood_m3 = Column(Float, nullable=True)
    total_firewood_chatta = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="inventory_calculations")
    calculation = relationship("Calculation", foreign_keys=[calculation_id])
    trees = relationship("InventoryTree", back_populates="inventory_calculation", cascade="all, delete-orphan")
    validation_logs = relationship("InventoryValidationLog", back_populates="inventory_calculation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<InventoryCalculation(id={self.id}, status='{self.status}', trees={self.total_trees})>"


class InventoryTree(Base):
    """
    Individual tree record model
    Stores tree measurements and calculated volumes
    """
    __tablename__ = "inventory_trees"
    __table_args__ = (
        Index('idx_inventory_trees_calc', 'inventory_calculation_id'),
        Index('idx_inventory_trees_location', 'location', postgresql_using='gist'),
        Index('idx_inventory_trees_remark', 'remark'),
        Index('idx_inventory_trees_species', 'species'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.inventory_calculations.id", ondelete="CASCADE"), nullable=False)

    # Original data
    species = Column(String(255), nullable=False)
    dia_cm = Column(Float, nullable=False)
    height_m = Column(Float, nullable=True)
    tree_class = Column(String(10), nullable=True)

    # Spatial location
    location = Column(Geography('POINT', srid=4326), nullable=False)

    # Calculated volumes
    stem_volume = Column(Float, nullable=True)
    branch_volume = Column(Float, nullable=True)
    tree_volume = Column(Float, nullable=True)
    gross_volume = Column(Float, nullable=True)
    net_volume = Column(Float, nullable=True)
    net_volume_cft = Column(Float, nullable=True)
    firewood_m3 = Column(Float, nullable=True)
    firewood_chatta = Column(Float, nullable=True)

    # Mother tree designation
    remark = Column(String(50), nullable=True)  # 'Mother Tree' or 'Felling Tree'
    grid_cell_id = Column(Integer, nullable=True)

    # Metadata
    local_name = Column(String(100), nullable=True)
    row_number = Column(Integer, nullable=True)

    # Extra columns from uploaded CSV (JSONB)
    extra_columns = Column(JSONB, nullable=True)

    # Boundary correction tracking
    was_corrected = Column(Boolean, default=False, nullable=False)
    original_x = Column(Float, nullable=True)  # Original longitude before correction
    original_y = Column(Float, nullable=True)  # Original latitude before correction

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    inventory_calculation = relationship("InventoryCalculation", back_populates="trees")

    def __repr__(self):
        return f"<InventoryTree(id={self.id}, species='{self.species}', dbh={self.dia_cm})>"


class InventoryValidationLog(Base):
    """
    Validation log model
    Stores validation history and reports
    """
    __tablename__ = "inventory_validation_logs"
    __table_args__ = (
        Index('idx_validation_logs_calc', 'inventory_calculation_id'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.inventory_calculations.id", ondelete="CASCADE"), nullable=True)

    # Validation metadata
    validated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    total_rows = Column(Integer, nullable=True)
    valid_rows = Column(Integer, nullable=True)
    error_rows = Column(Integer, nullable=True)
    warning_rows = Column(Integer, nullable=True)
    auto_corrections = Column(Integer, nullable=True)

    # Detection results
    detected_crs = Column(String(20), nullable=True)
    detected_diameter_type = Column(String(20), nullable=True)
    coordinate_x_column = Column(String(50), nullable=True)
    coordinate_y_column = Column(String(50), nullable=True)

    # Full validation report
    validation_report = Column(JSONB, nullable=True)

    # User actions
    user_confirmed = Column(Boolean, default=False, nullable=False)
    user_confirmation_time = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    inventory_calculation = relationship("InventoryCalculation", back_populates="validation_logs")
    issues = relationship("InventoryValidationIssue", back_populates="validation_log", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<InventoryValidationLog(id={self.id}, errors={self.error_rows}, warnings={self.warning_rows})>"


class InventoryValidationIssue(Base):
    """
    Individual validation issue model
    Stores row-level validation problems
    """
    __tablename__ = "inventory_validation_issues"
    __table_args__ = (
        Index('idx_validation_issues_log', 'validation_log_id'),
        Index('idx_validation_issues_severity', 'severity'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validation_log_id = Column(UUID(as_uuid=True), ForeignKey("public.inventory_validation_logs.id", ondelete="CASCADE"), nullable=False)

    # Issue details
    row_number = Column(Integer, nullable=False)
    column_name = Column(String(100), nullable=True)
    severity = Column(String(20), nullable=False)  # 'error', 'warning', 'info'
    issue_type = Column(String(50), nullable=True)

    # Values
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)

    # Message
    message = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    # User action
    user_accepted = Column(Boolean, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    validation_log = relationship("InventoryValidationLog", back_populates="issues")

    def __repr__(self):
        return f"<InventoryValidationIssue(id={self.id}, row={self.row_number}, severity='{self.severity}')>"


class TreeCorrectionLog(Base):
    """
    Tree correction log model
    Stores record of boundary corrections applied to out-of-boundary trees
    """
    __tablename__ = "tree_correction_logs"
    __table_args__ = (
        Index('idx_tree_corrections_inventory', 'inventory_calculation_id'),
        {"schema": "public"}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.inventory_calculations.id", ondelete="CASCADE"), nullable=False)

    # Tree identification
    tree_row_number = Column(Integer, nullable=False)
    species = Column(String(255), nullable=True)

    # Original coordinates (before correction)
    original_x = Column(Float, nullable=False)
    original_y = Column(Float, nullable=False)

    # Corrected coordinates (snapped to boundary)
    corrected_x = Column(Float, nullable=False)
    corrected_y = Column(Float, nullable=False)

    # Distance moved
    distance_moved_meters = Column(Float, nullable=False)

    # Why corrected
    correction_reason = Column(String(100), nullable=False)  # 'out_of_boundary', 'gps_error'

    # When corrected
    corrected_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    inventory_calculation = relationship("InventoryCalculation")

    def __repr__(self):
        return f"<TreeCorrectionLog(id={self.id}, row={self.tree_row_number}, moved={self.distance_moved_meters:.2f}m)>"
