from typing import Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.calculation import Calculation
from app.services.report.data_collector import (
    collect_all_data as _collect_all_data,
)


def _fetch_species_block_breakdown(db: Session, fi_calc_id: str) -> List[Dict[str, Any]]:
    """Reuses the species-breakdown SQL to return per-species-per-block growing stock data (pole + tree)."""
    fi_calc_id_str = str(fi_calc_id)
    pole_area = 100.0
    tree_area = 500.0

    query = text("""
        WITH block_total_plots AS (
            SELECT block_name, COUNT(DISTINCT id) as total_plots
            FROM public.field_inventory_sample_plots
            WHERE field_inventory_calculation_id = :fi_id
            GROUP BY block_name
        ),
        species_data AS (
            SELECT
                sp.block_name,
                m.species_scientific,
                m.species_local,
                m.stand_type,
                SUM(m.count) as total_count,
                SUM(COALESCE(m.stem_volume, 0)) as total_timber,
                SUM(COALESCE(m.branch_volume, 0)) as total_firewood
            FROM public.field_inventory_sample_plots sp
            JOIN public.field_inventory_measurements m ON m.sample_plot_id = sp.id
            WHERE sp.field_inventory_calculation_id = :fi_id
            GROUP BY sp.block_name, m.species_scientific, m.species_local, m.stand_type
        )
        SELECT
            sd.block_name,
            sd.species_scientific,
            sd.species_local,
            btp.total_plots,
            SUM(CASE WHEN sd.stand_type = 'Pole' THEN sd.total_count ELSE 0 END) as pole_count,
            SUM(CASE WHEN sd.stand_type = 'Tree' THEN sd.total_count ELSE 0 END) as tree_count,
            SUM(CASE WHEN sd.stand_type = 'Pole' THEN sd.total_timber ELSE 0 END) as pole_timber,
            SUM(CASE WHEN sd.stand_type = 'Pole' THEN sd.total_firewood ELSE 0 END) as pole_firewood,
            SUM(CASE WHEN sd.stand_type = 'Tree' THEN sd.total_timber ELSE 0 END) as tree_timber,
            SUM(CASE WHEN sd.stand_type = 'Tree' THEN sd.total_firewood ELSE 0 END) as tree_firewood
        FROM species_data sd
        JOIN block_total_plots btp ON btp.block_name = sd.block_name
        GROUP BY sd.block_name, sd.species_scientific, sd.species_local, btp.total_plots
        ORDER BY sd.block_name, sd.species_scientific
    """)
    results = db.execute(query, {"fi_id": fi_calc_id_str}).fetchall()

    rows = []
    for row in results:
        tp = row.total_plots or 1
        pole_count_ha = int((float(row.pole_count or 0) / tp / pole_area) * 10000) if row.pole_count else 0
        tree_count_ha = int((float(row.tree_count or 0) / tp / tree_area) * 10000) if row.tree_count else 0
        pole_timber_ha = (float(row.pole_timber or 0) / tp / pole_area) * 10000 if row.pole_timber else 0
        pole_firewood_ha = (float(row.pole_firewood or 0) / tp / pole_area) * 10000 if row.pole_firewood else 0
        tree_timber_ha = (float(row.tree_timber or 0) / tp / tree_area) * 10000 if row.tree_timber else 0
        tree_firewood_ha = (float(row.tree_firewood or 0) / tp / tree_area) * 10000 if row.tree_firewood else 0

        rows.append({
            "block_name": row.block_name,
            "species_scientific": row.species_scientific,
            "species_local": row.species_local or "",
            "count_per_ha": pole_count_ha + tree_count_ha,
            "timber_m3_per_ha": round(pole_timber_ha + tree_timber_ha, 2),
            "fuelwood_m3_per_ha": round(pole_firewood_ha + tree_firewood_ha, 2),
            "total_volume_m3_per_ha": round(pole_timber_ha + pole_firewood_ha + tree_timber_ha + tree_firewood_ha, 2),
        })

    return rows


def _fetch_dbh_class_breakdown(db: Session, fi_calc_id: str) -> List[Dict[str, Any]]:
    """Block + DBH class wise growing stock, matching Excel pivot table values.

    For FSM=t (Acacia catechu): timber = stem_volume, fuelwood = branch_volume
    For FSM=f (all others): timber = gross_volume * 0.6, fuelwood = tree - timber
    (RF defaults to 60% in Excel because tree_class "X.0" doesn't match "X")
    """
    fi_calc_id_str = str(fi_calc_id)

    query = text("""
        WITH block_total_plots AS (
            SELECT block_name, COUNT(DISTINCT id) as total_plots
            FROM public.field_inventory_sample_plots
            WHERE field_inventory_calculation_id = :fi_id
            GROUP BY block_name
        )
        SELECT
            sp.block_name,
            m.dbh_class,
            m.stand_type,
            btp.total_plots,
            SUM(m.count) as total_count,
            SUM(COALESCE(m.tree_volume, 0)) as total_tree,
            SUM(CASE WHEN tsc.full_stem_merchantable THEN COALESCE(m.stem_volume, 0) ELSE COALESCE(m.gross_volume, 0) * 0.6 END) as total_timber
        FROM public.field_inventory_sample_plots sp
        JOIN public.field_inventory_measurements m ON m.sample_plot_id = sp.id
        LEFT JOIN public.tree_species_coefficients tsc ON tsc.scientific_name = m.species_scientific
        JOIN block_total_plots btp ON btp.block_name = sp.block_name
        WHERE sp.field_inventory_calculation_id = :fi_id
        GROUP BY sp.block_name, m.dbh_class, m.stand_type, btp.total_plots
        ORDER BY sp.block_name,
          CASE m.stand_type
            WHEN 'Regeneration' THEN 1 WHEN 'Sapling' THEN 2 WHEN 'Pole' THEN 3 ELSE 4 END,
          CASE m.dbh_class
            WHEN 'Small pole (10-20)' THEN 1 WHEN 'Large pole (20-30)' THEN 2
            WHEN 'Small tree (30-40)' THEN 3 WHEN 'Medium tree (40-50)' THEN 4
            WHEN 'Large tree (50-60)' THEN 5 WHEN 'Very large tree (>60)' THEN 6
            ELSE 9 END
    """)
    results = db.execute(query, {"fi_id": fi_calc_id_str}).fetchall()

    rows = []
    for row in results:
        tp = float(row.total_plots or 1)
        st = str(row.stand_type or '')
        dcl = str(row.dbh_class or '')

        # Map to DBH class labels matching Excel pivot
        if dcl == 'Regeneration' and st == 'Regeneration':
            label = 'Seedling'
        elif dcl == 'Regeneration' and st == 'Sapling':
            label = 'Sapling'
        elif dcl == 'Small pole (10-20)':
            label = '10-20 Sm.Pole'
        elif dcl == 'Large pole (20-30)':
            label = '20-30 Lg.Pole'
        elif dcl == 'Small tree (30-40)':
            label = '30-40 Sm.Tree'
        elif dcl == 'Medium tree (40-50)':
            label = '40-50 Med.Tree'
        elif dcl == 'Large tree (50-60)':
            label = '50-60 Lg.Tree'
        elif dcl == 'Very large tree (>60)':
            label = '60+ V.Lg.Tree'
        else:
            label = dcl

        if st == 'Regeneration':
            plot_area = 10.0
        elif st == 'Sapling':
            plot_area = 25.0
        elif st == 'Pole':
            plot_area = 100.0
        else:
            plot_area = 500.0

        count_ha = (float(row.total_count or 0) / tp / plot_area) * 10000
        timber_ha = (float(row.total_timber or 0) / tp / plot_area) * 10000
        tree_ha = (float(row.total_tree or 0) / tp / plot_area) * 10000
        fuel_ha = tree_ha - timber_ha

        rows.append({
            "block_name": row.block_name,
            "dbh_class": label,
            "count_per_ha": round(count_ha, 2),
            "timber_m3_per_ha": round(timber_ha, 2),
            "fuelwood_m3_per_ha": round(fuel_ha, 2),
            "total_volume_m3_per_ha": round(tree_ha, 2),
        })

    return rows


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

    # Species-level block growing stock
    species_block_data = _fetch_species_block_breakdown(db, fi_calc.id)

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
            # ═══════════════════════════════════════════════════════════
            # Block-wise Growing Stocks (Pole & Tree) — species-level
            # Used by {{fi_species_block_growing_stock}} variable
            # ═══════════════════════════════════════════════════════════
            "fi_species_block_growing_stock": species_block_data,
            # ═══════════════════════════════════════════════════════════
            # Block-wise Regeneration Status
            # Used by {{fi_block_regeneration_status}} variable
            #
            "fi_block_regeneration_status": [
                {
                    "वन_खन्डको_नाम": b.block_name,
                    "विरूवा_प्रति_हेक्टर": round(b.regeneration_per_ha or 0),
                    "लाथ्रा_प्रति_हेक्टर": round(b.sapling_per_ha or 0),
                }
                for b in blocks
            ],
            # ═══════════════════════════════════════════════════════════
            # Block-wise DBH Class Growing Stock
            # Used by {{fi_block_dbh_class_growing_stock}} variable
            # ═══════════════════════════════════════════════════════════
            "fi_block_dbh_class_growing_stock": _fetch_dbh_class_breakdown(db, fi_calc.id),
        }

    return {"available": True, "total_sample_plots": 0, "total_blocks": 0}


def collect_all_op_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    raw = _collect_all_data(db, calculation_id)
    fi_data = get_field_inventory_data(db, calculation_id)
    raw["field_inventory"] = fi_data
    return raw
