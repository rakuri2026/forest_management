from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.calculation import Calculation
from app.services.report.data_collector import (
    collect_all_data as _collect_all_data,
)


def _fetch_species_block_breakdown(db: Session, fi_calc_id: str,
                                    block_areas: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Block + species level growing stock (Pole + Tree), matching Excel pivot.

    If block_areas is provided, weighted grand total rows per species are appended.
    """
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
                SUM(COALESCE(m.net_volume, 0)) as total_timber,
                SUM(COALESCE(m.firewood_m3, 0)) as total_firewood
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

    # ── Weighted grand total per species ──
    if block_areas:
        total_area = sum(block_areas.values())
        if total_area > 0:
            species_agg: Dict[str, Dict] = {}
            species_order: List[str] = []
            for r in rows:
                key = (r["species_scientific"] or "") + "||" + (r["species_local"] or "")
                if key not in species_agg:
                    species_agg[key] = {
                        "sci": r["species_scientific"],
                        "loc": r["species_local"],
                        "cnt": 0.0, "tim": 0.0, "fuel": 0.0, "tot": 0.0,
                    }
                    species_order.append(key)
                area = block_areas.get(r["block_name"], 0)
                species_agg[key]["cnt"] += r["count_per_ha"] * area
                species_agg[key]["tim"] += r["timber_m3_per_ha"] * area
                species_agg[key]["fuel"] += r["fuelwood_m3_per_ha"] * area
                species_agg[key]["tot"] += r["total_volume_m3_per_ha"] * area
            for key in species_order:
                s = species_agg[key]
                rows.append({
                    "block_name": "Grand Total (Weighted)",
                    "species_scientific": s["sci"],
                    "species_local": s["loc"],
                    "count_per_ha": int(s["cnt"] / total_area),
                    "timber_m3_per_ha": round(s["tim"] / total_area, 2),
                    "fuelwood_m3_per_ha": round(s["fuel"] / total_area, 2),
                    "total_volume_m3_per_ha": round(s["tot"] / total_area, 2),
                })

    return rows


def _fetch_dbh_class_breakdown(db: Session, fi_calc_id: str, block_areas: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Block + DBH class wise growing stock, matching Excel pivot table values.

    Net timber and firewood already account for tree_class quality factors
    per Forest Regulation 2079 (a=80%, b=60%, c=30%, d=0%).
    Timber = net_volume, fuelwood = tree_volume - timber.

    If block_areas is provided (block_name → effective hectares),
    weighted grand average rows are appended at the end.
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
            SUM(COALESCE(m.net_volume, 0)) as total_timber
        FROM public.field_inventory_sample_plots sp
        JOIN public.field_inventory_measurements m ON m.sample_plot_id = sp.id
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

        # Map to DBH class labels matching Excel col 39 pivot
        if dcl == 'Regeneration' and st == 'Regeneration':
            label = '0-4 Seedling'
        elif dcl == 'Regeneration' and st == 'Sapling':
            label = '4-10 Sapling'
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

    # ── Weighted grand average per DBH class ──
    if block_areas:
        total_area = sum(block_areas.values())
        if total_area > 0:
            classes = {}
            order = []
            for r in rows:
                cls = r["dbh_class"]
                if cls not in classes:
                    classes[cls] = {"cnt": 0.0, "tim": 0.0, "fuel": 0.0, "tot": 0.0}
                    order.append(cls)
                area = block_areas.get(r["block_name"], 0)
                classes[cls]["cnt"] += r["count_per_ha"] * area
                classes[cls]["tim"] += r["timber_m3_per_ha"] * area
                classes[cls]["fuel"] += r["fuelwood_m3_per_ha"] * area
                classes[cls]["tot"] += r["total_volume_m3_per_ha"] * area
            for cls in order:
                c = classes[cls]
                rows.append({
                    "block_name": "Grand Total (Weighted)",
                    "dbh_class": cls,
                    "count_per_ha": round(c["cnt"] / total_area, 2),
                    "timber_m3_per_ha": round(c["tim"] / total_area, 2),
                    "fuelwood_m3_per_ha": round(c["fuel"] / total_area, 2),
                    "total_volume_m3_per_ha": round(c["tot"] / total_area, 2),
                })

    return rows


def _fetch_dbh_class_breakdown_np(db: Session, fi_calc_id: str, block_areas: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Nepali version of DBH class growing stock with dash for zero values."""
    rows = _fetch_dbh_class_breakdown(db, fi_calc_id, block_areas)
    np_label_map = {
        "0-4 Seedling": "०-४ (विरूवा)",
        "4-10 Sapling": "४-१० (लाथ्रा)",
        "10-20 Sm.Pole": "१०-२० (सानो खाँवा)",
        "20-30 Lg.Pole": "२०-३० (ठुलो खाँवा)",
        "30-40 Sm.Tree": "३०-४० (सानो रूख)",
        "40-50 Med.Tree": "४०-५० (मध्यम रूख)",
        "50-60 Lg.Tree": "५०-६० (ठुलो रूख)",
        "60+ V.Lg.Tree": ">६० (धेरै ठुलो रूख)",
    }

    def _dash(val):
        return "—" if val == 0 else val

    def _block_name(bn):
        return "कुल जम्मा (भारित)" if bn == "Grand Total (Weighted)" else bn

    return [
        {
            "वन खण्ड": _block_name(r["block_name"]),
            "ब्यास क्लास": np_label_map.get(r["dbh_class"], r["dbh_class"]),
            "संख्या /हे.": _dash(r["count_per_ha"]),
            "काठ (घ.मी. /हे.)": _dash(r["timber_m3_per_ha"]),
            "दाउरा (घ.मी. /हे.)": _dash(r["fuelwood_m3_per_ha"]),
            "जम्मा (घ.मी. /हे.)": _dash(r["total_volume_m3_per_ha"]),
        }
        for r in rows
    ]


def _fetch_block_effective_areas(db: Session, calculation_id: str) -> Dict[str, float]:
    """Fetch net effective forest cover area per block using GIS-based computation.

    Uses calculate_block_area_details() — the same function as the
    block-area-detail endpoint — to subtract excluded sub-areas (private land,
    protected areas) from block geometry and recompute tree cover on the
    effective geometry.  Matches the Total Inventory tab exactly.
    """
    from app.services.tree_cover_analysis import calculate_block_area_details

    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.result_data:
        return {}
    rd = calc.result_data
    blocks = rd.get('blocks', [])
    sub_areas = rd.get('sub_areas', [])
    if not blocks:
        return {}

    details = calculate_block_area_details(db, blocks, sub_areas)
    return {d['block_name']: round(d['effective_area_ha'], 2) for d in details}


def _compute_species_composition(species_block_data: List[Dict],
                                  base_species_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Compute species composition analysis from block-level species growing stock.

    Classifies species into dominant (>=20%), co-dominant (10-20%), associated (<10%)
    based on total volume share. Also categorizes by growth rate from base species data.
    """
    species_vol: Dict[str, float] = {}
    for row in species_block_data:
        if row.get("block_name") == "Grand Total (Weighted)" or not row.get("species_scientific"):
            continue
        sci = row["species_scientific"]
        loc = row.get("species_local", "") or ""
        key = f"{sci} ({loc})" if loc else sci
        species_vol[key] = species_vol.get(key, 0) + float(row.get("total_volume_m3_per_ha", 0))

    if not species_vol:
        return {}

    total = sum(species_vol.values())
    if total <= 0:
        return {}

    pct = {k: round(v / total * 100, 1) for k, v in species_vol.items()}
    sorted_species = sorted(pct.items(), key=lambda x: x[1], reverse=True)

    dominant = [s for s, p in sorted_species if p >= 20.0]
    co_dominant = [s for s, p in sorted_species if 10.0 <= p < 20.0]
    associated = [s for s, p in sorted_species if p < 10.0]

    # ── Growth rate categorization from base species data ──
    fast_growing: List[str] = []
    moderate_growing: List[str] = []
    slow_growing: List[str] = []

    if base_species_data:
        for sp in base_species_data:
            sci = sp.get("scientific_name", "")
            loc = sp.get("local_name", "") or sp.get("nepali_name", "") or ""
            key = f"{sci} ({loc})" if loc else sci
            rate = (sp.get("growth_rate") or "").lower()
            if rate in ("fast", "high"):
                fast_growing.append(key)
            elif rate in ("moderate", "medium"):
                moderate_growing.append(key)
            elif rate in ("slow", "low"):
                slow_growing.append(key)

    return {
        "fi_species_composition": pct,
        "fi_dominant_species": dominant,
        "fi_co_dominant_species": co_dominant,
        "fi_associated_species": associated,
        "fi_fast_growing_species": fast_growing,
        "fi_moderate_growing_species": moderate_growing,
        "fi_slow_growing_species": slow_growing,
        # For block-species volume bar chart: sorted list of (name, pct)
        "fi_species_volume_by_block": sorted_species,
    }


def get_field_inventory_data(db: Session, calculation_id: str,
                              base_species_data: Optional[Dict] = None) -> Dict[str, Any]:
    from app.models.field_inventory import FieldInventoryCalculation, FieldInventoryBlockSummary
    fi_calc = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id
    ).first()
    if not fi_calc:
        return {"available": False}

    blocks = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == fi_calc.id
    ).all()

    # Block effective areas for weighted grand total
    block_areas = _fetch_block_effective_areas(db, calculation_id)

    # Species-level block growing stock (with weighted totals)
    species_block_data = _fetch_species_block_breakdown(db, fi_calc.id, block_areas)

    if blocks:
        total_area = sum(block_areas.values()) if block_areas else 0

        def _wavg(key: str, overall_fallback: Optional[float] = None) -> float:
            """Weighted average of a numeric field across blocks."""
            if not block_areas or total_area <= 0:
                return float(getattr(blocks[0], key, 0) or 0)
            wsum = sum(
                float(getattr(b, key, 0) or 0) * block_areas.get(b.block_name, 0)
                for b in blocks
            )
            return wsum / total_area if total_area else 0

        # ── Helper: row builder for per-block dict ──
        def _block_row(b, area):
            pt = float(b.pole_timber_m3_per_ha or 0)
            pf = float(b.pole_firewood_m3_per_ha or 0)
            tt = float(b.tree_timber_m3_per_ha or 0)
            tf = float(b.tree_firewood_m3_per_ha or 0)
            gs = float(b.total_growing_stock_m3_per_ha or 0)
            mai_pct = float(b.mai_percent or 0)
            cond = b.forest_condition or "Moderate"
            aah_map = {"Good": 75.0, "Moderate": 60.0, "Weak": 40.0}
            aah_pct = aah_map.get(cond, 60.0)
            mai_val = gs * mai_pct / 100.0
            aah_val = mai_val * aah_pct / 100.0
            return {
                "block_name": b.block_name,
                "total_sample_plots": b.total_sample_plots or 0,
                "regeneration_per_ha": b.regeneration_per_ha or 0,
                "sapling_per_ha": b.sapling_per_ha or 0,
                "pole_per_ha": b.pole_per_ha or 0,
                "tree_per_ha": b.tree_per_ha or 0,
                "pole_timber_m3_per_ha": round(pt, 2),
                "pole_firewood_m3_per_ha": round(pf, 2),
                "pole_total_m3_per_ha": round(pt + pf, 2),
                "tree_timber_m3_per_ha": round(tt, 2),
                "tree_firewood_m3_per_ha": round(tf, 2),
                "tree_total_m3_per_ha": round(tt + tf, 2),
                "total_volume_m3_per_ha": round(pt + pf + tt + tf, 2),
                "total_growing_stock_m3_per_ha": round(gs, 2),
                "satellite_volume_m3_per_ha": round(float(b.satellite_volume_m3_per_ha or 0), 2),
                "basal_area_m2_per_ha": round(float(b.basal_area_m2_per_ha or 0), 2),
                "regeneration_condition": b.regeneration_condition or "",
                "forest_condition": cond,
                "mai_percent": round(mai_pct, 2),
                "aah_multiplier_percent": round(aah_pct, 1),
                "mai_total_m3_per_ha": round(mai_val, 2),
                "aah_total_m3_per_ha": round(aah_val, 2),
                "weighted_wood_density": round(float(b.weighted_wood_density or 0), 3),
                "agb_t_per_ha": round(float(b.agb_t_per_ha or 0), 2),
                "bgb_t_per_ha": round(float(b.bgb_t_per_ha or 0), 2),
                "total_biomass_t_per_ha": round(float(b.total_biomass_t_per_ha or 0), 2),
                "carbon_stock_tc_per_ha": round(float(b.carbon_stock_tc_per_ha or 0), 2),
                "co2_equivalent_tco2_per_ha": round(float(b.co2_equivalent_tco2_per_ha or 0), 2),
            }

        block_rows = [_block_row(b, block_areas.get(b.block_name, 0)) for b in blocks]

        # ── Weighted grand total row ──
        def _wsum(key: str) -> float:
            return sum(
                float(getattr(b, key, 0) or 0) * block_areas.get(b.block_name, 0)
                for b in blocks
            )

        if block_areas and total_area > 0:
            wpt = _wsum("pole_timber_m3_per_ha") / total_area
            wpf = _wsum("pole_firewood_m3_per_ha") / total_area
            wtt = _wsum("tree_timber_m3_per_ha") / total_area
            wtf = _wsum("tree_firewood_m3_per_ha") / total_area
            wgs = _wsum("total_growing_stock_m3_per_ha") / total_area
            wmai = _wsum("mai_percent") / total_area
            wcond = "—"
            waah = {"Good": 75.0, "Moderate": 60.0, "Weak": 40.0}
            wmai_val = wgs * wmai / 100.0
            waah_val = wmai_val * 60.0 / 100.0
            grand = {
                "total_sample_plots": sum(b.total_sample_plots or 0 for b in blocks),
                "regeneration_per_ha": round(_wsum("regeneration_per_ha") / total_area),
                "sapling_per_ha": round(_wsum("sapling_per_ha") / total_area),
                "pole_per_ha": round(_wsum("pole_per_ha") / total_area),
                "tree_per_ha": round(_wsum("tree_per_ha") / total_area),
                "pole_timber_m3_per_ha": round(wpt, 2),
                "pole_firewood_m3_per_ha": round(wpf, 2),
                "pole_total_m3_per_ha": round(wpt + wpf, 2),
                "tree_timber_m3_per_ha": round(wtt, 2),
                "tree_firewood_m3_per_ha": round(wtf, 2),
                "tree_total_m3_per_ha": round(wtt + wtf, 2),
                "total_volume_m3_per_ha": round(wpt + wpf + wtt + wtf, 2),
                "total_growing_stock_m3_per_ha": round(wgs, 2),
                "satellite_volume_m3_per_ha": round(_wsum("satellite_volume_m3_per_ha") / total_area, 2),
                "basal_area_m2_per_ha": round(_wsum("basal_area_m2_per_ha") / total_area, 2),
                "regeneration_condition": "—",
                "forest_condition": wcond,
                "mai_percent": round(wmai, 2),
                "aah_multiplier_percent": 60.0,
                "mai_total_m3_per_ha": round(wmai_val, 2),
                "aah_total_m3_per_ha": round(waah_val, 2),
                "weighted_wood_density": round(_wsum("weighted_wood_density") / total_area, 3),
                "agb_t_per_ha": round(_wsum("agb_t_per_ha") / total_area, 2),
                "bgb_t_per_ha": round(_wsum("bgb_t_per_ha") / total_area, 2),
                "total_biomass_t_per_ha": round(_wsum("total_biomass_t_per_ha") / total_area, 2),
                "carbon_stock_tc_per_ha": round(_wsum("carbon_stock_tc_per_ha") / total_area, 2),
                "co2_equivalent_tco2_per_ha": round(_wsum("co2_equivalent_tco2_per_ha") / total_area, 2),
            }
        else:
            grand = None

        block_summaries = block_rows + ([grand] if grand else [])

        # ── MAI table (per block) ──
        mai_table = []
        for br in block_rows:
            mai_table.append({
                "block_name": br["block_name"],
                "pole_per_ha": br["pole_per_ha"],
                "tree_per_ha": br["tree_per_ha"],
                "pole_timber_m3_per_ha": br["pole_timber_m3_per_ha"],
                "pole_firewood_m3_per_ha": br["pole_firewood_m3_per_ha"],
                "pole_total_m3_per_ha": br["pole_total_m3_per_ha"],
                "tree_timber_m3_per_ha": br["tree_timber_m3_per_ha"],
                "tree_firewood_m3_per_ha": br["tree_firewood_m3_per_ha"],
                "tree_total_m3_per_ha": br["tree_total_m3_per_ha"],
                "total_mai_m3_per_ha": br["mai_total_m3_per_ha"],
            })
        # MAI grand total
        if grand:
            mai_table.append({
                "block_name": "Grand Total (Weighted)",
                "pole_per_ha": grand["pole_per_ha"],
                "tree_per_ha": grand["tree_per_ha"],
                "pole_timber_m3_per_ha": grand["pole_timber_m3_per_ha"],
                "pole_firewood_m3_per_ha": grand["pole_firewood_m3_per_ha"],
                "pole_total_m3_per_ha": grand["pole_total_m3_per_ha"],
                "tree_timber_m3_per_ha": grand["tree_timber_m3_per_ha"],
                "tree_firewood_m3_per_ha": grand["tree_firewood_m3_per_ha"],
                "tree_total_m3_per_ha": grand["tree_total_m3_per_ha"],
                "total_mai_m3_per_ha": grand["mai_total_m3_per_ha"],
            })

        # ── AAH table (per block) ──
        aah_table = []
        for br in block_rows:
            cond = br["forest_condition"]
            aah_map = {"Good": 75.0, "Moderate": 60.0, "Weak": 40.0}
            aah_pct = aah_map.get(cond, 60.0)
            mai_val = br["mai_total_m3_per_ha"]
            aah_val = round(mai_val * aah_pct / 100.0, 2)
            aah_table.append({
                "block_name": br["block_name"],
                "pole_per_ha": br["pole_per_ha"],
                "tree_per_ha": br["tree_per_ha"],
                "forest_condition": cond,
                "aah_multiplier_percent": aah_pct,
                "pole_timber_m3_per_ha": br["pole_timber_m3_per_ha"],
                "pole_firewood_m3_per_ha": br["pole_firewood_m3_per_ha"],
                "pole_total_m3_per_ha": br["pole_total_m3_per_ha"],
                "tree_timber_m3_per_ha": br["tree_timber_m3_per_ha"],
                "tree_firewood_m3_per_ha": br["tree_firewood_m3_per_ha"],
                "tree_total_m3_per_ha": br["tree_total_m3_per_ha"],
                "total_aah_m3_per_ha": aah_val,
            })
        if grand:
            aah_map_g = {"Good": 75.0, "Moderate": 60.0, "Weak": 40.0}
            aah_table.append({
                "block_name": "Grand Total (Weighted)",
                "pole_per_ha": grand["pole_per_ha"],
                "tree_per_ha": grand["tree_per_ha"],
                "forest_condition": "—",
                "aah_multiplier_percent": 60.0,
                "pole_timber_m3_per_ha": grand["pole_timber_m3_per_ha"],
                "pole_firewood_m3_per_ha": grand["pole_firewood_m3_per_ha"],
                "pole_total_m3_per_ha": grand["pole_total_m3_per_ha"],
                "tree_timber_m3_per_ha": grand["tree_timber_m3_per_ha"],
                "tree_firewood_m3_per_ha": grand["tree_firewood_m3_per_ha"],
                "tree_total_m3_per_ha": grand["tree_total_m3_per_ha"],
                "total_aah_m3_per_ha": grand["aah_total_m3_per_ha"],
            })

        return {
            "available": True,
            "total_sample_plots": fi_calc.total_sample_plots or 0,
            "total_blocks": fi_calc.total_blocks or 0,
            "regeneration_area_sqm": float(fi_calc.regeneration_area_sqm or 10.0),
            "sapling_area_sqm": float(fi_calc.sapling_area_sqm or 25.0),
            "pole_area_sqm": float(fi_calc.pole_area_sqm or 100.0),
            "tree_area_sqm": float(fi_calc.tree_area_sqm or 500.0),
            "fi_regeneration_per_ha": grand["regeneration_per_ha"] if grand else 0,
            "fi_sapling_per_ha": grand["sapling_per_ha"] if grand else 0,
            "fi_pole_per_ha": grand["pole_per_ha"] if grand else 0,
            "fi_tree_per_ha": grand["tree_per_ha"] if grand else 0,
            "fi_growing_stock_m3_per_ha": grand["total_growing_stock_m3_per_ha"] if grand else 0,
            "fi_basal_area_m2_per_ha": grand["basal_area_m2_per_ha"] if grand else 0,
            "fi_regeneration_condition": blocks[0].regeneration_condition or "",
            "fi_forest_condition": blocks[0].forest_condition or "",
            "fi_mai_percent": grand["mai_percent"] if grand else 0,
            "fi_agb_t_per_ha": grand["agb_t_per_ha"] if grand else 0,
            "fi_bgb_t_per_ha": grand["bgb_t_per_ha"] if grand else 0,
            "fi_total_biomass_t_per_ha": grand["total_biomass_t_per_ha"] if grand else 0,
            "fi_carbon_stock_tc_per_ha": grand["carbon_stock_tc_per_ha"] if grand else 0,
            "fi_co2_equivalent_tco2_per_ha": grand["co2_equivalent_tco2_per_ha"] if grand else 0,
            "fi_weighted_wood_density": grand["weighted_wood_density"] if grand else 0,
            # ── Per-block detailed results (used by {{fi_block_summaries}}) ──
            "fi_block_summaries": block_summaries,
            # ── Block-wise species growing stock ──
            "fi_species_block_growing_stock": species_block_data,
            # ── Species composition analysis from field inventory ──
            **_compute_species_composition(species_block_data,
                                            base_species_data.get("species_list")
                                            if base_species_data else None),
            # ── Block-wise regeneration status ──
            "fi_block_regeneration_status": [
                {
                    "वन_खन्डको_नाम": b.block_name,
                    "विरूवा_प्रति_हेक्टर": round(b.regeneration_per_ha or 0),
                    "लाथ्रा_प्रति_हेक्टर": round(b.sapling_per_ha or 0),
                }
                for b in blocks
            ],
            # ── Block-wise DBH class growing stock (English) ──
            "fi_block_dbh_class_growing_stock": _fetch_dbh_class_breakdown(db, fi_calc.id, block_areas),
            # ── Block-wise DBH class growing stock (Nepali) ──
            "fi_block_dbh_class_growing_stock_np": _fetch_dbh_class_breakdown_np(db, fi_calc.id, block_areas),
            # ── वार्षिक वृद्धि तालिका / MAI table ──
            "fi_mai_table": mai_table,
            # ── वार्षिक स्वीकार्य कटान तालिका / AAH table ──
            "fi_aah_table": aah_table,
        }

    return {
        "available": True, "total_sample_plots": 0, "total_blocks": 0,
        "fi_species_composition": {},
        "fi_dominant_species": [],
        "fi_co_dominant_species": [],
        "fi_associated_species": [],
        "fi_fast_growing_species": [],
        "fi_moderate_growing_species": [],
        "fi_slow_growing_species": [],
        "fi_species_volume_by_block": [],
    }


def collect_all_op_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    raw = _collect_all_data(db, calculation_id)
    fi_data = get_field_inventory_data(db, calculation_id,
                                       base_species_data=raw.get("species"))
    raw["field_inventory"] = fi_data
    return raw
