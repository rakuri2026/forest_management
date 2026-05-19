"""
Field Inventory API endpoints
Handles field inventory upload, validation, processing, and export
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Any, Dict
from uuid import UUID
import pandas as pd
import numpy as np
import io
import json
import math

from ..core.database import get_db
from ..models.user import User
from ..models.field_inventory import (
    FieldInventoryCalculation,
    FieldInventorySamplePlot,
    FieldInventoryMeasurement,
    FieldInventoryBlockSummary
)
from ..schemas.field_inventory import (
    FieldInventoryCalculationResponse,
    FieldInventorySummaryResponse,
    FieldInventoryBlockSummaryResponse,
    FieldInventoryValidationReport
)
from ..utils.auth import get_current_active_user
from ..services.field_inventory_validator import FieldInventoryValidator
from ..services.field_inventory_service import FieldInventoryService

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def clean_nan_values(obj: Any) -> Any:
    """
    Recursively clean NaN, inf, and -inf values from nested structures
    Converts them to None for JSON serialization
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif pd.isna(obj):
        return None
    return obj


@router.post("/preview-mapping")
async def preview_column_mapping(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Preview automatic column mapping for uploaded CSV file
    """
    if not file.filename.endswith('.csv') and not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")

    try:
        content = await file.read()
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(content), nrows=10)
        else:
            df = pd.read_csv(io.BytesIO(content), nrows=10)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    # Return preview with column detection (clean NaN values)
    preview_data = {
        "success": True,
        "filename": file.filename,
        "total_rows": len(df),
        "csv_columns": df.columns.tolist(),
        "sample_data": df.head(5).to_dict('records'),
        "detected_stand_types": []  # TODO: Implement auto-detection
    }

    return clean_nan_values(preview_data)


@router.post("/upload")
async def upload_field_inventory(
    file: UploadFile = File(...),
    calculation_id: Optional[str] = Form(None),
    mapping: str = Form(...),  # JSON string
    regeneration_area_sqm: float = Form(10.0),
    sapling_area_sqm: float = Form(25.0),
    pole_area_sqm: float = Form(100.0),
    tree_area_sqm: float = Form(500.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload and validate field inventory CSV
    """
    if not file.filename.endswith('.csv') and not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")

    # Parse mapping
    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid mapping JSON")

    # Read file
    try:
        content = await file.read()
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # Validate
    validator = FieldInventoryValidator(db)
    calc_id = UUID(calculation_id) if calculation_id else None
    validation_report = await validator.validate_field_inventory_file(df, calc_id)

    # Clean NaN values before JSON serialization
    validation_report = clean_nan_values(validation_report)

    # If validation passed, create record
    if validation_report['summary'].get('ready_for_processing'):
        field_inventory = FieldInventoryCalculation(
            user_id=current_user.id,
            calculation_id=calc_id,
            uploaded_filename=file.filename,
            column_mapping=mapping_dict,
            regeneration_area_sqm=regeneration_area_sqm,
            sapling_area_sqm=sapling_area_sqm,
            pole_area_sqm=pole_area_sqm,
            tree_area_sqm=tree_area_sqm,
            status='validated'
        )
        db.add(field_inventory)
        db.commit()
        db.refresh(field_inventory)

        validation_report['field_inventory_id'] = str(field_inventory.id)
        validation_report['next_step'] = 'POST /api/field-inventory/{field_inventory_id}/process'

    return validation_report


@router.post("/{field_inventory_id}/process")
async def process_field_inventory(
    field_inventory_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Process validated field inventory
    """
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    if field_inventory.status != 'validated':
        raise HTTPException(status_code=400, detail=f"Cannot process. Status: {field_inventory.status}")

    # Read file
    try:
        content = await file.read()
        if field_inventory.uploaded_filename.endswith('.xlsx'):
            df = pd.read_excel(io.BytesIO(content))
        else:
            df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # Process
    service = FieldInventoryService(db)
    try:
        result = await service.process_field_inventory(
            field_inventory_id,
            df,
            field_inventory.column_mapping
        )
        return result
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/{field_inventory_id}/status", response_model=FieldInventoryCalculationResponse)
async def get_status(
    field_inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get processing status"""
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    return field_inventory


@router.get("/{field_inventory_id}/summary", response_model=FieldInventorySummaryResponse)
async def get_summary(
    field_inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get complete summary with all blocks"""
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    # Get all block summaries
    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == field_inventory_id
    ).all()

    # Calculate forest-wide averages
    if blocks:
        from collections import Counter
        total_blocks = len(blocks)

        # Average trees per hectare
        avg_regeneration = sum(b.regeneration_per_ha or 0 for b in blocks) / total_blocks
        avg_sapling = sum(b.sapling_per_ha or 0 for b in blocks) / total_blocks
        avg_pole = sum(b.pole_per_ha or 0 for b in blocks) / total_blocks
        avg_tree = sum(b.tree_per_ha or 0 for b in blocks) / total_blocks

        # Average volumes
        avg_pole_timber = sum(float(b.pole_timber_m3_per_ha or 0) for b in blocks) / total_blocks
        avg_pole_firewood = sum(float(b.pole_firewood_m3_per_ha or 0) for b in blocks) / total_blocks
        avg_tree_timber = sum(float(b.tree_timber_m3_per_ha or 0) for b in blocks) / total_blocks
        avg_tree_firewood = sum(float(b.tree_firewood_m3_per_ha or 0) for b in blocks) / total_blocks
        avg_growing_stock = sum(float(b.total_growing_stock_m3_per_ha or 0) for b in blocks) / total_blocks

        # Average basal area
        avg_basal_area = sum(float(b.basal_area_m2_per_ha or 0) for b in blocks) / total_blocks

        # Average carbon metrics
        avg_wood_density = sum(float(b.weighted_wood_density or 0) for b in blocks) / total_blocks
        avg_agb = sum(float(b.agb_t_per_ha or 0) for b in blocks) / total_blocks
        avg_bgb = sum(float(b.bgb_t_per_ha or 0) for b in blocks) / total_blocks
        avg_total_biomass = sum(float(b.total_biomass_t_per_ha or 0) for b in blocks) / total_blocks
        avg_carbon = sum(float(b.carbon_stock_tc_per_ha or 0) for b in blocks) / total_blocks
        avg_co2 = sum(float(b.co2_equivalent_tco2_per_ha or 0) for b in blocks) / total_blocks

        # Average MAI
        avg_mai = sum(float(b.mai_percent or 0) for b in blocks) / total_blocks

        # Overall forest condition (majority vote)
        conditions = [b.forest_condition for b in blocks if b.forest_condition]
        overall_condition = Counter(conditions).most_common(1)[0][0] if conditions else None

        regen_conditions = [b.regeneration_condition for b in blocks if b.regeneration_condition]
        overall_regen = Counter(regen_conditions).most_common(1)[0][0] if regen_conditions else None

        growth_rates = [b.dominant_growth_rate for b in blocks if b.dominant_growth_rate]
        overall_growth_rate = Counter(growth_rates).most_common(1)[0][0] if growth_rates else None
    else:
        # No blocks, return zeros
        avg_regeneration = avg_sapling = avg_pole = avg_tree = 0
        avg_pole_timber = avg_pole_firewood = avg_tree_timber = avg_tree_firewood = 0
        avg_growing_stock = avg_mai = 0
        avg_wood_density = avg_agb = avg_bgb = avg_total_biomass = avg_carbon = avg_co2 = 0
        overall_condition = overall_regen = overall_growth_rate = None

    return {
        "field_inventory_id": field_inventory.id,
        "status": field_inventory.status,
        "total_sample_plots": field_inventory.total_sample_plots or 0,
        "total_blocks": field_inventory.total_blocks or 0,
        "blocks": blocks,

        # Forest-wide averages (NEW)
        "total_regeneration_per_ha": int(avg_regeneration),
        "total_sapling_per_ha": int(avg_sapling),
        "total_pole_per_ha": int(avg_pole),
        "total_tree_per_ha": int(avg_tree),
        "total_pole_timber_m3_per_ha": round(avg_pole_timber, 2),
        "total_pole_firewood_m3_per_ha": round(avg_pole_firewood, 2),
        "total_tree_timber_m3_per_ha": round(avg_tree_timber, 2),
        "total_tree_firewood_m3_per_ha": round(avg_tree_firewood, 2),
        "total_growing_stock_m3_per_ha": round(avg_growing_stock, 2),
        "average_basal_area_m2_per_ha": round(avg_basal_area, 2),

        # Overall assessments
        "overall_forest_condition": overall_condition,
        "overall_regeneration_condition": overall_regen,
        "overall_growth_rate": overall_growth_rate,
        "average_mai_percent": round(avg_mai, 2),

        # Carbon averages (NEW)
        "average_wood_density": round(avg_wood_density, 3),
        "average_agb_t_per_ha": round(avg_agb, 2),
        "average_bgb_t_per_ha": round(avg_bgb, 2),
        "average_total_biomass_t_per_ha": round(avg_total_biomass, 2),
        "average_carbon_stock_tc_per_ha": round(avg_carbon, 2),
        "average_co2_equivalent_tco2_per_ha": round(avg_co2, 2),

        "processing_time_seconds": field_inventory.processing_time_seconds,
        "created_at": field_inventory.created_at,
        "completed_at": field_inventory.completed_at
    }


@router.get("/{field_inventory_id}/blocks", response_model=List[FieldInventoryBlockSummaryResponse])
async def list_blocks(
    field_inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all blocks"""
    # Verify ownership
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == field_inventory_id
    ).all()

    return blocks


@router.get("/{field_inventory_id}/species-breakdown")
async def get_species_breakdown(
    field_inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get species-wise breakdown by block"""
    from sqlalchemy import text

    # Verify ownership
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    # Get sample plot areas
    regen_area = float(field_inventory.regeneration_area_sqm)
    sapling_area = float(field_inventory.sapling_area_sqm)
    pole_area = float(field_inventory.pole_area_sqm)
    tree_area = float(field_inventory.tree_area_sqm)

    # Query to get species-wise breakdown by block
    query = text("""
        WITH plot_species AS (
            SELECT
                sp.block_name,
                m.species_scientific,
                m.species_local,
                m.stand_type,
                COUNT(DISTINCT sp.id) as total_plots_in_block,
                SUM(m.count) as total_count,
                SUM(COALESCE(m.net_volume, 0)) as total_timber,
                SUM(COALESCE(m.firewood_m3, 0)) as total_firewood,
                SUM(COALESCE(m.basal_area_m2, 0) * m.count) as total_basal_area
            FROM public.field_inventory_sample_plots sp
            JOIN public.field_inventory_measurements m ON m.sample_plot_id = sp.id
            WHERE sp.field_inventory_calculation_id = :field_inventory_id
            GROUP BY sp.block_name, m.species_scientific, m.species_local, m.stand_type
        )
        SELECT
            block_name,
            species_scientific,
            species_local,
            SUM(CASE WHEN stand_type = 'Regeneration' THEN total_count ELSE 0 END) as regen_count,
            SUM(CASE WHEN stand_type = 'Sapling' THEN total_count ELSE 0 END) as sapling_count,
            SUM(CASE WHEN stand_type = 'Pole' THEN total_count ELSE 0 END) as pole_count,
            SUM(CASE WHEN stand_type = 'Tree' THEN total_count ELSE 0 END) as tree_count,
            SUM(CASE WHEN stand_type = 'Pole' THEN total_basal_area ELSE 0 END) as pole_basal_area,
            SUM(CASE WHEN stand_type = 'Tree' THEN total_basal_area ELSE 0 END) as tree_basal_area,
            SUM(CASE WHEN stand_type = 'Pole' THEN total_timber ELSE 0 END) as pole_timber,
            SUM(CASE WHEN stand_type = 'Pole' THEN total_firewood ELSE 0 END) as pole_firewood,
            SUM(CASE WHEN stand_type = 'Tree' THEN total_timber ELSE 0 END) as tree_timber,
            SUM(CASE WHEN stand_type = 'Tree' THEN total_firewood ELSE 0 END) as tree_firewood,
            MAX(total_plots_in_block) as total_plots
        FROM plot_species
        GROUP BY block_name, species_scientific, species_local
        ORDER BY block_name, species_scientific
    """)

    results = db.execute(query, {"field_inventory_id": str(field_inventory_id)}).fetchall()

    # Load species coefficients (for wood density)
    species_coefficients_query = text("""
        SELECT scientific_name, wood_density_gm_cm3
        FROM public.tree_species_coefficients
        WHERE is_active = TRUE
    """)
    species_coef_results = db.execute(species_coefficients_query).fetchall()
    species_densities = {row.scientific_name: float(row.wood_density_gm_cm3 or 0.65) for row in species_coef_results}

    # IPCC/REDD+ carbon calculation constants
    BEF = 1.40  # Biomass Expansion Factor
    ROOT_SHOOT_RATIO = 0.24  # Root-to-shoot ratio
    CARBON_FRACTION = 0.47  # Carbon fraction in biomass
    CO2_TO_C_RATIO = 3.67  # CO2 to C conversion

    # Process results to calculate per-hectare values and carbon metrics
    species_data = []
    for row in results:
        total_plots = row.total_plots or 1

        # Calculate per-hectare counts (convert Decimal to float for calculations)
        regen_per_ha = int((float(row.regen_count or 0) / total_plots / regen_area) * 10000) if row.regen_count > 0 else 0
        sapling_per_ha = int((float(row.sapling_count or 0) / total_plots / sapling_area) * 10000) if row.sapling_count > 0 else 0
        pole_per_ha = int((float(row.pole_count or 0) / total_plots / pole_area) * 10000) if row.pole_count > 0 else 0
        tree_per_ha = int((float(row.tree_count or 0) / total_plots / tree_area) * 10000) if row.tree_count > 0 else 0

        # Calculate per-hectare volumes
        pole_timber_per_ha = (float(row.pole_timber or 0) / total_plots / pole_area) * 10000 if row.pole_timber else 0
        pole_firewood_per_ha = (float(row.pole_firewood or 0) / total_plots / pole_area) * 10000 if row.pole_firewood else 0
        tree_timber_per_ha = (float(row.tree_timber or 0) / total_plots / tree_area) * 10000 if row.tree_timber else 0
        tree_firewood_per_ha = (float(row.tree_firewood or 0) / total_plots / tree_area) * 10000 if row.tree_firewood else 0

        growing_stock = pole_timber_per_ha + tree_timber_per_ha
        total_volume = pole_timber_per_ha + pole_firewood_per_ha + tree_timber_per_ha + tree_firewood_per_ha

        # Calculate per-hectare basal area
        pole_basal_per_ha = (float(row.pole_basal_area or 0) / total_plots / pole_area) * 10000 if row.pole_basal_area else 0
        tree_basal_per_ha = (float(row.tree_basal_area or 0) / total_plots / tree_area) * 10000 if row.tree_basal_area else 0
        basal_area_m2_per_ha = pole_basal_per_ha + tree_basal_per_ha

        # Carbon calculations
        wood_density = species_densities.get(row.species_scientific, 0.65)  # Default to 0.65 t/m³ if not found
        agb_t_per_ha = growing_stock * wood_density * BEF
        bgb_t_per_ha = agb_t_per_ha * ROOT_SHOOT_RATIO
        total_biomass_t_per_ha = agb_t_per_ha + bgb_t_per_ha
        carbon_stock_tC_per_ha = total_biomass_t_per_ha * CARBON_FRACTION
        co2_equivalent_tCO2_per_ha = carbon_stock_tC_per_ha * CO2_TO_C_RATIO

        species_data.append({
            "block_name": row.block_name,
            "species_scientific": row.species_scientific,
            "species_local": row.species_local or "",
            "regeneration_per_ha": regen_per_ha,
            "sapling_per_ha": sapling_per_ha,
            "pole_per_ha": pole_per_ha,
            "tree_per_ha": tree_per_ha,
            "pole_timber_m3_per_ha": round(pole_timber_per_ha, 2),
            "pole_firewood_m3_per_ha": round(pole_firewood_per_ha, 2),
            "tree_timber_m3_per_ha": round(tree_timber_per_ha, 2),
            "tree_firewood_m3_per_ha": round(tree_firewood_per_ha, 2),
            "growing_stock_m3_per_ha": round(growing_stock, 2),
            "total_volume_m3_per_ha": round(total_volume, 2),
            "basal_area_m2_per_ha": round(basal_area_m2_per_ha, 2),
            # Carbon metrics (IPCC/REDD+)
            "wood_density_t_m3": round(wood_density, 3),
            "agb_t_per_ha": round(agb_t_per_ha, 2),
            "bgb_t_per_ha": round(bgb_t_per_ha, 2),
            "total_biomass_t_per_ha": round(total_biomass_t_per_ha, 2),
            "carbon_stock_tc_per_ha": round(carbon_stock_tC_per_ha, 2),
            "co2_equivalent_tco2_per_ha": round(co2_equivalent_tCO2_per_ha, 2)
        })

    return {"species_breakdown": species_data}


@router.get("/by-calculation/{calculation_id}")
async def get_by_calculation(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get field inventory for a calculation"""
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="No field inventory found for this calculation")

    return field_inventory


@router.get("/{field_inventory_id}/mai-aah")
async def get_mai_aah(
    field_inventory_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    custom_multipliers: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate MAI and AAH tables for field inventory

    MAI (Mean Annual Increment) = Growing Stock × (MAI% / 100)
    AAH (Annual Allowable Harvest) = MAI × AAH_Multiplier

    AAH Multipliers (user-configurable):
    - Good forest: 75% (default)
    - Moderate forest: 60% (default)
    - Weak forest: 40% (default)

    Custom multipliers can be provided per block via custom_multipliers parameter
    as JSON string: {"Block A": 80.0, "Block B": 55.0}
    """
    # Parse custom multipliers if provided
    import json
    custom_mult_dict = {}
    if custom_multipliers:
        try:
            custom_mult_dict = json.loads(custom_multipliers)
        except json.JSONDecodeError:
            pass
    # Verify ownership
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    # Get all block summaries
    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == field_inventory_id
    ).all()

    if not blocks:
        return {
            "mai_blocks": [],
            "aah_blocks": [],
            "mai_overall": {},
            "aah_overall": {},
            "aah_multipliers": {
                "good": aah_good,
                "moderate": aah_moderate,
                "weak": aah_weak
            }
        }

    # Calculate MAI and AAH for each block
    mai_blocks = []
    aah_blocks = []

    for block in blocks:
        # Get MAI percentage (already calculated)
        mai_percent = float(block.mai_percent or 0) / 100  # Convert to decimal

        # Get volumes
        pole_timber = float(block.pole_timber_m3_per_ha or 0)
        pole_firewood = float(block.pole_firewood_m3_per_ha or 0)
        tree_timber = float(block.tree_timber_m3_per_ha or 0)
        tree_firewood = float(block.tree_firewood_m3_per_ha or 0)
        total_growing_stock = float(block.total_growing_stock_m3_per_ha or 0)

        # Get tree counts
        pole_per_ha = int(block.pole_per_ha or 0)
        tree_per_ha = int(block.tree_per_ha or 0)

        # Calculate MAI volumes (Growing Stock × MAI%)
        mai_pole_timber = pole_timber * mai_percent
        mai_pole_firewood = pole_firewood * mai_percent
        mai_pole_total = mai_pole_timber + mai_pole_firewood
        mai_tree_timber = tree_timber * mai_percent
        mai_tree_firewood = tree_firewood * mai_percent
        mai_tree_total = mai_tree_timber + mai_tree_firewood
        mai_total = total_growing_stock * mai_percent

        # Calculate MAI tree counts (Trees × MAI%)
        mai_pole_per_ha = int(pole_per_ha * mai_percent)
        mai_tree_per_ha = int(tree_per_ha * mai_percent)

        # Determine AAH multiplier based on forest condition
        forest_condition = block.forest_condition
        block_name = block.block_name

        # Check if block has custom multiplier
        if block_name in custom_mult_dict:
            aah_multiplier = custom_mult_dict[block_name] / 100
            is_custom = True
        else:
            # Use default based on forest condition
            if forest_condition == 'Good':
                aah_multiplier = aah_good / 100
            elif forest_condition == 'Moderate':
                aah_multiplier = aah_moderate / 100
            else:  # Weak
                aah_multiplier = aah_weak / 100
            is_custom = False

        # Calculate AAH volumes (MAI × AAH multiplier)
        aah_pole_timber = mai_pole_timber * aah_multiplier
        aah_pole_firewood = mai_pole_firewood * aah_multiplier
        aah_pole_total = mai_pole_total * aah_multiplier
        aah_tree_timber = mai_tree_timber * aah_multiplier
        aah_tree_firewood = mai_tree_firewood * aah_multiplier
        aah_tree_total = mai_tree_total * aah_multiplier
        aah_total = mai_total * aah_multiplier

        # Calculate AAH tree counts (MAI trees × AAH multiplier)
        aah_pole_per_ha = int(mai_pole_per_ha * aah_multiplier)
        aah_tree_per_ha = int(mai_tree_per_ha * aah_multiplier)

        # MAI block data
        mai_blocks.append({
            "block_name": block.block_name,
            "pole_per_ha": mai_pole_per_ha,
            "tree_per_ha": mai_tree_per_ha,
            "pole_timber_m3_per_ha": round(mai_pole_timber, 2),
            "pole_firewood_m3_per_ha": round(mai_pole_firewood, 2),
            "pole_total_m3_per_ha": round(mai_pole_total, 2),
            "tree_timber_m3_per_ha": round(mai_tree_timber, 2),
            "tree_firewood_m3_per_ha": round(mai_tree_firewood, 2),
            "tree_total_m3_per_ha": round(mai_tree_total, 2),
            "total_mai_m3_per_ha": round(mai_total, 2),
            "mai_percent": float(block.mai_percent or 0)
        })

        # Determine default multiplier for this block
        if forest_condition == 'Good':
            default_multiplier = aah_good
        elif forest_condition == 'Moderate':
            default_multiplier = aah_moderate
        else:  # Weak
            default_multiplier = aah_weak

        # AAH block data
        aah_blocks.append({
            "block_name": block.block_name,
            "pole_per_ha": aah_pole_per_ha,
            "tree_per_ha": aah_tree_per_ha,
            "forest_condition": forest_condition,
            "aah_multiplier_percent": aah_multiplier * 100,
            "default_multiplier_percent": default_multiplier,
            "is_custom": is_custom,
            "pole_timber_m3_per_ha": round(aah_pole_timber, 2),
            "pole_firewood_m3_per_ha": round(aah_pole_firewood, 2),
            "pole_total_m3_per_ha": round(aah_pole_total, 2),
            "tree_timber_m3_per_ha": round(aah_tree_timber, 2),
            "tree_firewood_m3_per_ha": round(aah_tree_firewood, 2),
            "tree_total_m3_per_ha": round(aah_tree_total, 2),
            "total_aah_m3_per_ha": round(aah_total, 2)
        })

    # Calculate overall forest averages
    total_blocks = len(blocks)

    # Overall MAI
    avg_mai_pole_per_ha = int(sum(b["pole_per_ha"] for b in mai_blocks) / total_blocks)
    avg_mai_tree_per_ha = int(sum(b["tree_per_ha"] for b in mai_blocks) / total_blocks)
    avg_mai_pole_timber = sum(b["pole_timber_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_pole_firewood = sum(b["pole_firewood_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_pole_total = sum(b["pole_total_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_tree_timber = sum(b["tree_timber_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_tree_firewood = sum(b["tree_firewood_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_tree_total = sum(b["tree_total_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_total = sum(b["total_mai_m3_per_ha"] for b in mai_blocks) / total_blocks
    avg_mai_percent = sum(b["mai_percent"] for b in mai_blocks) / total_blocks

    # Overall AAH
    avg_aah_pole_per_ha = int(sum(b["pole_per_ha"] for b in aah_blocks) / total_blocks)
    avg_aah_tree_per_ha = int(sum(b["tree_per_ha"] for b in aah_blocks) / total_blocks)
    avg_aah_pole_timber = sum(b["pole_timber_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_pole_firewood = sum(b["pole_firewood_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_pole_total = sum(b["pole_total_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_tree_timber = sum(b["tree_timber_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_tree_firewood = sum(b["tree_firewood_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_tree_total = sum(b["tree_total_m3_per_ha"] for b in aah_blocks) / total_blocks
    avg_aah_total = sum(b["total_aah_m3_per_ha"] for b in aah_blocks) / total_blocks

    # Overall forest condition (majority vote)
    from collections import Counter
    conditions = [b["forest_condition"] for b in aah_blocks if b["forest_condition"]]
    overall_condition = Counter(conditions).most_common(1)[0][0] if conditions else None

    # Overall AAH multiplier based on overall condition
    if overall_condition == 'Good':
        overall_aah_multiplier = aah_good
    elif overall_condition == 'Moderate':
        overall_aah_multiplier = aah_moderate
    else:
        overall_aah_multiplier = aah_weak

    return {
        "mai_blocks": mai_blocks,
        "aah_blocks": aah_blocks,
        "mai_overall": {
            "block_name": "Overall Forest",
            "pole_per_ha": avg_mai_pole_per_ha,
            "tree_per_ha": avg_mai_tree_per_ha,
            "pole_timber_m3_per_ha": round(avg_mai_pole_timber, 2),
            "pole_firewood_m3_per_ha": round(avg_mai_pole_firewood, 2),
            "pole_total_m3_per_ha": round(avg_mai_pole_total, 2),
            "tree_timber_m3_per_ha": round(avg_mai_tree_timber, 2),
            "tree_firewood_m3_per_ha": round(avg_mai_tree_firewood, 2),
            "tree_total_m3_per_ha": round(avg_mai_tree_total, 2),
            "total_mai_m3_per_ha": round(avg_mai_total, 2),
            "mai_percent": round(avg_mai_percent, 2)
        },
        "aah_overall": {
            "block_name": "Overall Forest",
            "pole_per_ha": avg_aah_pole_per_ha,
            "tree_per_ha": avg_aah_tree_per_ha,
            "forest_condition": overall_condition,
            "aah_multiplier_percent": overall_aah_multiplier,
            "pole_timber_m3_per_ha": round(avg_aah_pole_timber, 2),
            "pole_firewood_m3_per_ha": round(avg_aah_pole_firewood, 2),
            "pole_total_m3_per_ha": round(avg_aah_pole_total, 2),
            "tree_timber_m3_per_ha": round(avg_aah_tree_timber, 2),
            "tree_firewood_m3_per_ha": round(avg_aah_tree_firewood, 2),
            "tree_total_m3_per_ha": round(avg_aah_tree_total, 2),
            "total_aah_m3_per_ha": round(avg_aah_total, 2)
        },
        "aah_multipliers": {
            "good": aah_good,
            "moderate": aah_moderate,
            "weak": aah_weak
        }
    }


@router.delete("/{field_inventory_id}")
async def delete_field_inventory(
    field_inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete field inventory"""
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    db.delete(field_inventory)
    db.commit()

    return {"message": "Field inventory deleted successfully"}


@router.get("/{field_inventory_id}/export-excel")
async def export_field_inventory_excel(
    field_inventory_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    custom_multipliers: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export field inventory as a measurement-level Excel file.
    One row = one tree/plant measurement with all calculated volume metrics,
    block-level per-hectare aggregates, and MAI/AAH rates repeated per row.
    Ideal for further analysis, pivot tables, and custom calculations.
    """
    from ..services.field_inventory_excel_export import generate_field_inventory_excel

    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    custom_mult_dict = {}
    if custom_multipliers:
        try:
            custom_mult_dict = json.loads(custom_multipliers)
        except json.JSONDecodeError:
            pass

    from ..models.calculation import Calculation
    from datetime import datetime
    from urllib.parse import quote

    # Pre-check: ensure there are measurements before calling the generator
    has_measurements = db.query(FieldInventoryMeasurement).join(
        FieldInventorySamplePlot,
        FieldInventoryMeasurement.sample_plot_id == FieldInventorySamplePlot.id
    ).filter(
        FieldInventorySamplePlot.field_inventory_calculation_id == field_inventory_id
    ).first()
    if not has_measurements:
        raise HTTPException(
            status_code=400,
            detail="No measurements found in this field inventory. Please upload and process measurement data first."
        )

    try:
        excel_bytes = generate_field_inventory_excel(
            db=db,
            field_inventory_id=field_inventory_id,
            aah_good=aah_good,
            aah_moderate=aah_moderate,
            aah_weak=aah_weak,
            custom_multipliers=custom_mult_dict,
        )

        calc = db.query(Calculation).filter(Calculation.id == field_inventory.calculation_id).first()
        forest_name = calc.forest_name.replace(" ", "_") if calc and calc.forest_name else "Forest"
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{forest_name}_Field_Inventory_Report_{date_str}.xlsx"

        ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
        encoded = quote(filename)

        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}',
                "Content-Length": str(len(excel_bytes)),
            }
        )
    except ValueError as e:
        detail = str(e)
        if "No measurements found" in detail:
            detail = "No measurements found in this field inventory. Please upload and process measurement data first."
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        logger.error(f"Excel export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Excel export failed: {str(e)}")


@router.get("/{field_inventory_id}/export-dfo-summary")
async def export_field_inventory_dfo_summary(
    field_inventory_id: UUID,
    calculation_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export DFO-format Nepali block-wise + species-wise summary Excel.
    15 sheets: 6 base (Species×Block, Block Aggregate, Carbon, DBH, Regen, Descriptions)
    + 9 management plan sheets (Species Comp, Block Comparison, Harvest Plan,
    Forest Condition, DBH Volume, Carbon Block, Growth Rate, Stand Structure,
    Productivity).
    """
    from ..services.field_inventory_dfo_export import generate_field_inventory_dfo_summary

    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    try:
        excel_bytes = generate_field_inventory_dfo_summary(
            db=db,
            field_inventory_id=field_inventory_id,
            calculation_id=calculation_id,
            aah_good=aah_good,
            aah_moderate=aah_moderate,
            aah_weak=aah_weak,
        )

        from ..models.calculation import Calculation
        from datetime import datetime
        from urllib.parse import quote

        calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
        forest_name = calc.forest_name.replace(" ", "_") if calc and calc.forest_name else "Forest"
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{forest_name}_FieldInventory_DFOSummary_{date_str}.xlsx"

        ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
        encoded = quote(filename)

        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}',
                "Content-Length": str(len(excel_bytes)),
            }
        )
    except ValueError as e:
        detail = str(e)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        logger.error(f"DFO summary export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DFO summary export failed: {str(e)}")


@router.get("/{field_inventory_id}/total-inventory")
async def get_total_inventory(
    field_inventory_id: UUID,
    block_areas: Optional[str] = None,
    custom_multipliers: Optional[str] = None,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Calculate total inventory (absolute quantities) by multiplying per-hectare values by block area

    Requires block_areas parameter as JSON string: {"Block A": 45.5, "Block B": 32.0}
    Returns total quantities for each block and forest-wide totals
    """
    # Verify ownership
    field_inventory = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()

    if not field_inventory:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    # Parse block areas
    block_area_dict = {}
    if block_areas:
        try:
            block_area_dict = json.loads(block_areas)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid block_areas JSON format")

    # Parse custom AAH multipliers
    custom_mult_dict = {}
    if custom_multipliers:
        try:
            custom_mult_dict = json.loads(custom_multipliers)
        except json.JSONDecodeError:
            pass

    # Get all block summaries
    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == field_inventory_id
    ).all()

    if not blocks:
        return {
            "blocks": [],
            "forest_totals": {},
            "missing_areas": []
        }

    # DBH class keys for implementation plan (Pole + Tree volume-carrying classes)
    DBH_CLASS_KEYS = ['10_20', '20_30', '30_40', '40_50', '50_60']

    # Calculate totals for each block
    total_blocks = []
    missing_areas = []

    # Forest-wide accumulators
    forest_total_area = 0
    forest_total_regeneration = 0
    forest_total_sapling = 0
    forest_total_pole = 0
    forest_total_tree = 0
    forest_total_growing_stock = 0
    forest_total_mai = 0
    forest_total_aah = 0
    forest_total_agb = 0
    forest_total_bgb = 0
    forest_total_biomass = 0
    forest_total_carbon = 0
    forest_total_co2 = 0

    # Forest-wide DBH class accumulators
    forest_dbh_class_totals = {}
    for cls_key in DBH_CLASS_KEYS:
        forest_dbh_class_totals[cls_key] = {
            "total_count": 0,
            "total_timber_m3": 0.0,
            "total_firewood_m3": 0.0,
            "total_tree_volume_m3": 0.0
        }

    for block in blocks:
        block_name = block.block_name

        # Get block area
        if block_name not in block_area_dict:
            missing_areas.append(block_name)
            continue

        area_ha = float(block_area_dict[block_name])

        # Get per-hectare values
        regeneration_per_ha = int(block.regeneration_per_ha or 0)
        sapling_per_ha = int(block.sapling_per_ha or 0)
        pole_per_ha = int(block.pole_per_ha or 0)
        tree_per_ha = int(block.tree_per_ha or 0)

        pole_timber_per_ha = float(block.pole_timber_m3_per_ha or 0)
        pole_firewood_per_ha = float(block.pole_firewood_m3_per_ha or 0)
        tree_timber_per_ha = float(block.tree_timber_m3_per_ha or 0)
        tree_firewood_per_ha = float(block.tree_firewood_m3_per_ha or 0)
        growing_stock_per_ha = float(block.total_growing_stock_m3_per_ha or 0)

        # Carbon/biomass per hectare
        agb_per_ha = float(block.agb_t_per_ha or 0)
        bgb_per_ha = float(block.bgb_t_per_ha or 0)
        biomass_per_ha = float(block.total_biomass_t_per_ha or 0)
        carbon_per_ha = float(block.carbon_stock_tc_per_ha or 0)
        co2_per_ha = float(block.co2_equivalent_tco2_per_ha or 0)

        # Calculate MAI and AAH
        mai_percent = float(block.mai_percent or 0) / 100
        mai_per_ha = growing_stock_per_ha * mai_percent

        # Determine AAH multiplier
        forest_condition = block.forest_condition
        if block_name in custom_mult_dict:
            aah_multiplier = custom_mult_dict[block_name] / 100
        else:
            if forest_condition == 'Good':
                aah_multiplier = aah_good / 100
            elif forest_condition == 'Moderate':
                aah_multiplier = aah_moderate / 100
            else:
                aah_multiplier = aah_weak / 100

        aah_per_ha = mai_per_ha * aah_multiplier

        # Calculate TOTALS (multiply by area)
        total_regeneration = int(regeneration_per_ha * area_ha)
        total_sapling = int(sapling_per_ha * area_ha)
        total_pole = int(pole_per_ha * area_ha)
        total_tree = int(tree_per_ha * area_ha)

        total_pole_timber = pole_timber_per_ha * area_ha
        total_pole_firewood = pole_firewood_per_ha * area_ha
        total_tree_timber = tree_timber_per_ha * area_ha
        total_tree_firewood = tree_firewood_per_ha * area_ha
        total_growing_stock = growing_stock_per_ha * area_ha
        total_mai = mai_per_ha * area_ha
        total_aah = aah_per_ha * area_ha

        total_agb = agb_per_ha * area_ha
        total_bgb = bgb_per_ha * area_ha
        total_biomass = biomass_per_ha * area_ha
        total_carbon = carbon_per_ha * area_ha
        total_co2 = co2_per_ha * area_ha

        # Compute DBH class breakdown for this block
        dbh_class_per_ha = {}
        dbh_class_totals = {}
        if block.dbh_class_breakdown:
            for cls_key in DBH_CLASS_KEYS:
                cls_data = block.dbh_class_breakdown.get(cls_key, {})
                if cls_data:
                    cpk = float(cls_data.get('count_per_ha', 0) or 0)
                    tpk = float(cls_data.get('timber_m3_per_ha', 0) or 0)
                    fpk = float(cls_data.get('firewood_m3_per_ha', 0) or 0)
                    tvpk = tpk + fpk

                    dbh_class_per_ha[cls_key] = {
                        "count_per_ha": round(cpk, 2),
                        "timber_m3_per_ha": round(tpk, 2),
                        "firewood_m3_per_ha": round(fpk, 2),
                        "tree_volume_m3_per_ha": round(tvpk, 2),
                        "label_en": cls_data.get('label_en', ''),
                        "label_np": cls_data.get('label_np', '')
                    }

                    dbh_class_totals[cls_key] = {
                        "total_count": int(round(cpk * area_ha)),
                        "total_timber_m3": round(tpk * area_ha, 2),
                        "total_firewood_m3": round(fpk * area_ha, 2),
                        "total_tree_volume_m3": round(tvpk * area_ha, 2)
                    }

                    # Accumulate forest-wide DBH totals
                    fct = forest_dbh_class_totals[cls_key]
                    fct["total_count"] += int(round(cpk * area_ha))
                    fct["total_timber_m3"] += round(tpk * area_ha, 2)
                    fct["total_firewood_m3"] += round(fpk * area_ha, 2)
                    fct["total_tree_volume_m3"] += round(tvpk * area_ha, 2)

        # Accumulate forest totals
        forest_total_area += area_ha
        forest_total_regeneration += total_regeneration
        forest_total_sapling += total_sapling
        forest_total_pole += total_pole
        forest_total_tree += total_tree
        forest_total_growing_stock += total_growing_stock
        forest_total_mai += total_mai
        forest_total_aah += total_aah
        forest_total_agb += total_agb
        forest_total_bgb += total_bgb
        forest_total_biomass += total_biomass
        forest_total_carbon += total_carbon
        forest_total_co2 += total_co2

        # Build block result
        total_blocks.append({
            "block_name": block_name,
            "area_ha": round(area_ha, 2),
            "sample_plots": block.total_sample_plots,
            "forest_condition": forest_condition,

            # Per-hectare reference values
            "regeneration_per_ha": regeneration_per_ha,
            "sapling_per_ha": sapling_per_ha,
            "pole_per_ha": pole_per_ha,
            "tree_per_ha": tree_per_ha,
            "growing_stock_m3_per_ha": round(growing_stock_per_ha, 2),
            "mai_m3_per_ha": round(mai_per_ha, 2),
            "aah_m3_per_ha": round(aah_per_ha, 2),

            # TOTAL quantities
            "total_regeneration": total_regeneration,
            "total_sapling": total_sapling,
            "total_pole": total_pole,
            "total_tree": total_tree,
            "total_pole_timber_m3": round(total_pole_timber, 2),
            "total_pole_firewood_m3": round(total_pole_firewood, 2),
            "total_tree_timber_m3": round(total_tree_timber, 2),
            "total_tree_firewood_m3": round(total_tree_firewood, 2),
            "total_growing_stock_m3": round(total_growing_stock, 2),
            "total_mai_m3": round(total_mai, 2),
            "total_aah_m3": round(total_aah, 2),
            "total_agb_tonnes": round(total_agb, 2),
            "total_bgb_tonnes": round(total_bgb, 2),
            "total_biomass_tonnes": round(total_biomass, 2),
            "total_carbon_tc": round(total_carbon, 2),
            "total_co2_tco2": round(total_co2, 2),

            # DBH class breakdown
            "dbh_class_per_ha": dbh_class_per_ha,
            "dbh_class_totals": dbh_class_totals,
        })

    # Forest-wide totals
    forest_totals = {
        "total_area_ha": round(forest_total_area, 2),
        "total_blocks": len(total_blocks),
        "total_regeneration": forest_total_regeneration,
        "total_sapling": forest_total_sapling,
        "total_pole": forest_total_pole,
        "total_tree": forest_total_tree,
        "total_growing_stock_m3": round(forest_total_growing_stock, 2),
        "total_mai_m3_per_year": round(forest_total_mai, 2),
        "total_aah_m3_per_year": round(forest_total_aah, 2),
        "total_agb_tonnes": round(forest_total_agb, 2),
        "total_bgb_tonnes": round(forest_total_bgb, 2),
        "total_biomass_tonnes": round(forest_total_biomass, 2),
        "total_carbon_tc": round(forest_total_carbon, 2),
        "total_co2_tco2": round(forest_total_co2, 2),

        # Forest-wide DBH class totals
        "dbh_class_totals": {
            cls_key: {
                "total_count": int(v["total_count"]),
                "total_timber_m3": round(v["total_timber_m3"], 2),
                "total_firewood_m3": round(v["total_firewood_m3"], 2),
                "total_tree_volume_m3": round(v["total_tree_volume_m3"], 2)
            }
            for cls_key, v in forest_dbh_class_totals.items()
        },
    }

    return {
        "blocks": total_blocks,
        "forest_totals": forest_totals,
        "missing_areas": missing_areas
    }


@router.get("/{field_inventory_id}/management-plan-data")
async def get_management_plan_data_endpoint(
    field_inventory_id: UUID,
    calculation_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get management plan summary data (all 9 datasets) for frontend charts.
    """
    from ..services.field_inventory_mgmt_data import get_management_plan_data

    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()
    if not fi:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    try:
        data = get_management_plan_data(
            db=db,
            field_inventory_id=field_inventory_id,
            calculation_id=calculation_id,
            aah_good=aah_good,
            aah_moderate=aah_moderate,
            aah_weak=aah_weak,
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{field_inventory_id}/export-management-plan-docx")
async def export_management_plan_docx(
    field_inventory_id: UUID,
    calculation_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export 10-Year Management Plan DOCX with 12 chapters, embedded maps,
    charts, block-wise 10-year schedule, and data tables.
    Replaces the previous flat maps+charts export.
    """
    from ..services.management_plan_docx import generate_10yr_management_plan_docx

    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()
    if not fi:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    try:
        docx_bytes = generate_10yr_management_plan_docx(
            db=db,
            field_inventory_id=field_inventory_id,
            calculation_id=calculation_id,
            aah_good=aah_good,
            aah_moderate=aah_moderate,
            aah_weak=aah_weak,
        )

        from ..models.calculation import Calculation
        from urllib.parse import quote
        from datetime import datetime

        calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
        forest_name = calc.forest_name.replace(" ", "_") if calc and calc.forest_name else "Forest"
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{forest_name}_ManagementPlan_10Yr_{date_str}.docx"

        ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
        encoded = quote(filename)

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}',
                "Content-Length": str(len(docx_bytes)),
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Management plan DOCX export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Management plan DOCX export failed: {str(e)}")

@router.get("/{field_inventory_id}/export-10yr-plan-docx")
async def export_10yr_plan_docx(
    field_inventory_id: UUID,
    calculation_id: UUID,
    aah_good: float = 75.0,
    aah_moderate: float = 60.0,
    aah_weak: float = 40.0,
    include_maps: bool = True,
    include_charts: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export 10-Year Management Plan DOCX with full chapter structure.
    Same as export-management-plan-docx but with additional options
    for including/excluding maps and charts.
    """
    from ..services.management_plan_docx import generate_10yr_management_plan_docx

    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.id == field_inventory_id,
        FieldInventoryCalculation.user_id == current_user.id
    ).first()
    if not fi:
        raise HTTPException(status_code=404, detail="Field inventory not found")

    try:
        docx_bytes = generate_10yr_management_plan_docx(
            db=db,
            field_inventory_id=field_inventory_id,
            calculation_id=calculation_id,
            aah_good=aah_good,
            aah_moderate=aah_moderate,
            aah_weak=aah_weak,
            include_maps=include_maps,
            include_charts=include_charts,
        )

        from ..models.calculation import Calculation
        from urllib.parse import quote
        from datetime import datetime

        calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
        forest_name = calc.forest_name.replace(" ", "_") if calc and calc.forest_name else "Forest"
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{forest_name}_10Yr_ManagementPlan_{date_str}.docx"

        ascii_fallback = filename.encode("ascii", errors="replace").decode("ascii")
        encoded = quote(filename)

        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}',
                "Content-Length": str(len(docx_bytes)),
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"10-Year plan DOCX export failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"10-Year plan DOCX export failed: {str(e)}")
