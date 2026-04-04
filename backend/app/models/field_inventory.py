"""
Field Inventory models - For fieldbook measurements with 4 stand types
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Numeric, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
from datetime import datetime
import uuid

from ..core.database import Base


class FieldInventoryCalculation(Base):
    """
    Field inventory calculation model
    Stores main field inventory processing records
    """
    __tablename__ = "field_inventory_calculations"
    __table_args__ = (
        Index('idx_field_inventory_calc_user', 'user_id'),
        Index('idx_field_inventory_calc_calculation', 'calculation_id'),
        Index('idx_field_inventory_calc_status', 'status'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="SET NULL"), nullable=True, unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)

    # File metadata
    uploaded_filename = Column(String(255), nullable=False)
    column_mapping = Column(JSONB, nullable=True)

    # Configurable sample plot sizes (in square meters)
    regeneration_area_sqm = Column(Numeric(10, 2), default=10.0, nullable=False)
    sapling_area_sqm = Column(Numeric(10, 2), default=25.0, nullable=False)
    pole_area_sqm = Column(Numeric(10, 2), default=100.0, nullable=False)
    tree_area_sqm = Column(Numeric(10, 2), default=500.0, nullable=False)

    # Processing status
    status = Column(String(50), default='processing', nullable=False)
    processing_time_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Summary statistics
    total_sample_plots = Column(Integer, nullable=True)
    total_blocks = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="field_inventory_calculations")
    calculation = relationship("Calculation", foreign_keys=[calculation_id])
    sample_plots = relationship("FieldInventorySamplePlot", back_populates="field_inventory_calculation", cascade="all, delete-orphan")
    block_summaries = relationship("FieldInventoryBlockSummary", back_populates="field_inventory_calculation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FieldInventoryCalculation(id={self.id}, status='{self.status}', plots={self.total_sample_plots})>"


class FieldInventorySamplePlot(Base):
    """
    Sample plot model
    Stores sample plot locations for field inventory
    """
    __tablename__ = "field_inventory_sample_plots"
    __table_args__ = (
        Index('idx_field_inventory_plots_calc', 'field_inventory_calculation_id'),
        Index('idx_field_inventory_plots_block', 'block_name'),
        Index('idx_field_inventory_plots_location', 'location', postgresql_using='gist'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_inventory_calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.field_inventory_calculations.id", ondelete="CASCADE"), nullable=False)

    # Plot identification
    block_name = Column(String(255), nullable=False)
    sample_plot_number = Column(Integer, nullable=False)
    location = Column(Geography('POINT', srid=4326), nullable=False)

    # NTFP and other forest products (kg per 100 sqm per year)
    firewood_kg_per_100sqm_per_year = Column(Numeric(15, 6), nullable=True)
    grass_kg_per_100sqm_per_year = Column(Numeric(15, 6), nullable=True)
    bedding_material_kg_per_100sqm_per_year = Column(Numeric(15, 6), nullable=True)
    ntfp_kg_per_100sqm_per_year = Column(Numeric(15, 6), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    field_inventory_calculation = relationship("FieldInventoryCalculation", back_populates="sample_plots")
    measurements = relationship("FieldInventoryMeasurement", back_populates="sample_plot", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FieldInventorySamplePlot(id={self.id}, block='{self.block_name}', plot={self.sample_plot_number})>"


class FieldInventoryMeasurement(Base):
    """
    Individual measurement model
    Stores tree measurements by stand type (Regeneration, Sapling, Pole, Tree)
    """
    __tablename__ = "field_inventory_measurements"
    __table_args__ = (
        Index('idx_field_inventory_meas_plot', 'sample_plot_id'),
        Index('idx_field_inventory_meas_stand_type', 'stand_type'),
        Index('idx_field_inventory_meas_species', 'species_scientific'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_plot_id = Column(UUID(as_uuid=True), ForeignKey("public.field_inventory_sample_plots.id", ondelete="CASCADE"), nullable=False)

    # Measurement data
    stand_type = Column(String(20), nullable=False)  # 'Regeneration', 'Sapling', 'Pole', 'Tree'
    sn = Column(Integer, nullable=True)
    species_scientific = Column(String(255), nullable=False)
    species_local = Column(String(255), nullable=True)
    dbh_cm = Column(Numeric(10, 2), nullable=True)
    height_m = Column(Numeric(10, 2), nullable=True)
    height_estimated = Column(Boolean, default=False, nullable=False)
    tree_class = Column(String(10), nullable=True)
    count = Column(Integer, default=1, nullable=False)

    # Calculated volumes (only for Pole and Tree)
    stem_volume = Column(Numeric(15, 6), nullable=True)
    branch_volume = Column(Numeric(15, 6), nullable=True)
    tree_volume = Column(Numeric(15, 6), nullable=True)
    gross_volume = Column(Numeric(15, 6), nullable=True)
    net_volume = Column(Numeric(15, 6), nullable=True)
    net_volume_cft = Column(Numeric(15, 6), nullable=True)
    firewood_m3 = Column(Numeric(15, 6), nullable=True)
    firewood_chatta = Column(Numeric(15, 6), nullable=True)

    # DBH classification
    dbh_class = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    sample_plot = relationship("FieldInventorySamplePlot", back_populates="measurements")

    def __repr__(self):
        return f"<FieldInventoryMeasurement(id={self.id}, stand_type='{self.stand_type}', species='{self.species_scientific}')>"


class FieldInventoryBlockSummary(Base):
    """
    Block summary model
    Stores per-hectare extrapolation and forest condition assessment
    """
    __tablename__ = "field_inventory_block_summary"
    __table_args__ = (
        Index('idx_field_inventory_summary_calc', 'field_inventory_calculation_id'),
        Index('idx_field_inventory_summary_block', 'block_name'),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_inventory_calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.field_inventory_calculations.id", ondelete="CASCADE"), nullable=False)
    block_name = Column(String(255), nullable=False)

    # Sample plot statistics
    total_sample_plots = Column(Integer, nullable=False)

    # Per-hectare counts (extrapolated)
    regeneration_per_ha = Column(Integer, nullable=True)
    sapling_per_ha = Column(Integer, nullable=True)
    pole_per_ha = Column(Integer, nullable=True)
    tree_per_ha = Column(Integer, nullable=True)

    # Per-hectare volumes (extrapolated) - timber only
    pole_timber_m3_per_ha = Column(Numeric(15, 6), nullable=True)
    pole_firewood_m3_per_ha = Column(Numeric(15, 6), nullable=True)
    tree_timber_m3_per_ha = Column(Numeric(15, 6), nullable=True)
    tree_firewood_m3_per_ha = Column(Numeric(15, 6), nullable=True)

    # Total growing stock (timber only)
    total_growing_stock_m3_per_ha = Column(Numeric(15, 6), nullable=True)

    # Satellite-derived volume (from AGB raster - added 2026-03-23)
    satellite_volume_m3_per_ha = Column(Numeric(15, 6), nullable=True)  # Volume from AGB 2022 Nepal raster

    # Forest condition assessment
    regeneration_condition = Column(String(20), nullable=True)  # 'Good', 'Moderate', 'Weak'
    forest_condition = Column(String(20), nullable=True)  # 'Good', 'Moderate', 'Weak'

    # Mean Annual Increment (%)
    mai_percent = Column(Numeric(5, 2), nullable=True)
    dominant_growth_rate = Column(String(20), nullable=True)  # 'Fast', 'Moderate', 'Slow'

    # Carbon and biomass metrics (IPCC/REDD+ - added 2026-03-03)
    agb_t_per_ha = Column(Numeric(15, 6), nullable=True)  # Above-ground biomass (tonnes/ha)
    bgb_t_per_ha = Column(Numeric(15, 6), nullable=True)  # Below-ground biomass (tonnes/ha)
    total_biomass_t_per_ha = Column(Numeric(15, 6), nullable=True)  # Total biomass (tonnes/ha)
    carbon_stock_tc_per_ha = Column(Numeric(15, 6), nullable=True)  # Carbon stock (tonnes C/ha)
    co2_equivalent_tco2_per_ha = Column(Numeric(15, 6), nullable=True)  # CO2 equivalent (tonnes CO2/ha)
    weighted_wood_density = Column(Numeric(5, 3), nullable=True)  # Volume-weighted wood density (t/m³)

    # NTFP and other forest products (per hectare, extrapolated from 100 sqm plots)
    firewood_kg_per_ha = Column(Numeric(15, 6), nullable=True)  # Firewood (kg/ha/year)
    grass_kg_per_ha = Column(Numeric(15, 6), nullable=True)  # Grass (kg/ha/year)
    bedding_material_kg_per_ha = Column(Numeric(15, 6), nullable=True)  # Bedding material (kg/ha/year)
    ntfp_kg_per_ha = Column(Numeric(15, 6), nullable=True)  # Non-timber forest products (kg/ha/year)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    field_inventory_calculation = relationship("FieldInventoryCalculation", back_populates="block_summaries")

    def __repr__(self):
        return f"<FieldInventoryBlockSummary(id={self.id}, block='{self.block_name}', condition='{self.forest_condition}')>"
