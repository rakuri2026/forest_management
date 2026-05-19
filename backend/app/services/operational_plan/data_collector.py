from typing import Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.calculation import Calculation
from app.services.report.data_collector import (
    collect_all_data as _collect_all_data,
)


def get_field_inventory_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    from app.models.field_inventory import FieldInventoryCalculation, FieldInventoryBlockSummary
    fi_calc = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id
    ).first()
    if not fi_calc:
        return {"available": False}

    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == fi_calc.id
    ).all()

    if blocks:
        first = blocks[0]
        return {
            "available": True,
            "total_sample_plots": fi_calc.total_sample_plots or 0,
            "total_blocks": fi_calc.total_blocks or 0,
            "regeneration_area_sqm": float(fi_calc.regeneration_area_sqm or 10.0),
            "sapling_area_sqm": float(fi_calc.sapling_area_sqm or 25.0),
            "pole_area_sqm": float(fi_calc.pole_area_sqm or 100.0),
            "tree_area_sqm": float(fi_calc.tree_area_sqm or 500.0),
            "fi_regeneration_per_ha": first.regeneration_per_ha or 0,
            "fi_sapling_per_ha": first.sapling_per_ha or 0,
            "fi_pole_per_ha": first.pole_per_ha or 0,
            "fi_tree_per_ha": first.tree_per_ha or 0,
            "fi_growing_stock_m3_per_ha": float(first.total_growing_stock_m3_per_ha or 0),
            "fi_basal_area_m2_per_ha": float(first.basal_area_m2_per_ha or 0),
            "fi_regeneration_condition": first.regeneration_condition or "",
            "fi_forest_condition": first.forest_condition or "",
            "fi_mai_percent": float(first.mai_percent or 0),
            "fi_agb_t_per_ha": float(first.agb_t_per_ha or 0),
            "fi_bgb_t_per_ha": float(first.bgb_t_per_ha or 0),
            "fi_total_biomass_t_per_ha": float(first.total_biomass_t_per_ha or 0),
            "fi_carbon_stock_tc_per_ha": float(first.carbon_stock_tc_per_ha or 0),
            "fi_co2_equivalent_tco2_per_ha": float(first.co2_equivalent_tco2_per_ha or 0),
            "fi_weighted_wood_density": float(first.weighted_wood_density or 0),
            "fi_block_summaries": [
                {
                    "block_name": b.block_name,
                    "regeneration_per_ha": b.regeneration_per_ha or 0,
                    "sapling_per_ha": b.sapling_per_ha or 0,
                    "pole_per_ha": b.pole_per_ha or 0,
                    "tree_per_ha": b.tree_per_ha or 0,
                    "total_growing_stock_m3_per_ha": float(b.total_growing_stock_m3_per_ha or 0),
                    "forest_condition": b.forest_condition or "",
                    "agb_t_per_ha": float(b.agb_t_per_ha or 0),
                    "carbon_stock_tc_per_ha": float(b.carbon_stock_tc_per_ha or 0),
                }
                for b in blocks
            ],
        }

    return {"available": True, "total_sample_plots": 0, "total_blocks": 0}


def collect_all_op_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    raw = _collect_all_data(db, calculation_id)
    fi_data = get_field_inventory_data(db, calculation_id)
    raw["field_inventory"] = fi_data
    return raw
