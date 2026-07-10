import logging
import time
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

from app.models.calculation import Calculation
from app.models.forest_block import ForestBlock
from app.models.fieldbook import Fieldbook
from app.models.yearly_activities import (
    ProposedYearlyActivity, ActivityYearDetail, PotentialActivity,
    ActivitySpatialAssignment, ActivityDrawnFeature,
)
from app.services.report.data_collector import (
    collect_all_data as _collect_all_data,
)
from app.services.operational_plan.section_generators import collect_section_content

# Bump this when data_collector or any collector it calls changes schema/keys
OP_DATA_CACHE_VERSION = 11


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
            WHEN 'Sm. Pole (10-20)' THEN 1 WHEN 'Lg. Pole (20-30)' THEN 2
            WHEN 'Sm. Tree (30-40)' THEN 3 WHEN 'Med. Tree (40-50)' THEN 4
            WHEN 'Lg. Tree (50-60)' THEN 5 WHEN 'V. Lg. Tree (60+)' THEN 6
            ELSE 9 END
    """)
    results = db.execute(query, {"fi_id": fi_calc_id_str}).fetchall()

    rows = []
    for row in results:
        tp = float(row.total_plots or 1)
        st = str(row.stand_type or '')
        dcl = str(row.dbh_class or '')

        # Map to DBH class labels matching Excel col 39 pivot
        if dcl == 'Seedling (0-4)' or (dcl == 'Regeneration' and st == 'Regeneration'):
            label = '0-4 Seedling'
        elif dcl == 'Sapling (4-10)' or (dcl == 'Regeneration' and st == 'Sapling'):
            label = '4-10 Sapling'
        elif dcl == 'Sm. Pole (10-20)':
            label = '10-20 Sm.Pole'
        elif dcl == 'Lg. Pole (20-30)':
            label = '20-30 Lg.Pole'
        elif dcl == 'Sm. Tree (30-40)':
            label = '30-40 Sm.Tree'
        elif dcl == 'Med. Tree (40-50)':
            label = '40-50 Med.Tree'
        elif dcl == 'Lg. Tree (50-60)':
            label = '50-60 Lg.Tree'
        elif dcl == 'V. Lg. Tree (60+)':
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


def _prepare_dbh_class_chart_data(db: Session, fi_calc_id: str, block_areas: dict) -> List[Dict[str, Any]]:
    """Forest-wide DBH class (pole+tree) per-hectare volume for bar chart, Nepali labels."""
    rows = _fetch_dbh_class_breakdown(db, fi_calc_id, block_areas)
    np_labels = {
        "10-20 Sm.Pole": "१०-२० से.मी.",
        "20-30 Lg.Pole": "२०-३० से.मी.",
        "30-40 Sm.Tree": "३०-४० से.मी.",
        "40-50 Med.Tree": "४०-५० से.मी.",
        "50-60 Lg.Tree": "५०-६० से.मी.",
        "60+ V.Lg.Tree": ">६० से.मी.",
    }
    result = []
    for r in rows:
        if r["block_name"] != "Grand Total (Weighted)":
            continue
        label = np_labels.get(r["dbh_class"])
        if not label:
            continue
        result.append({
            "label": label,
            "count_per_ha": round(r["count_per_ha"], 2),
            "timber_m3_per_ha": round(r["timber_m3_per_ha"], 2),
            "fuelwood_m3_per_ha": round(r["fuelwood_m3_per_ha"], 2),
            "total_volume_m3_per_ha": round(r["total_volume_m3_per_ha"], 2),
        })
    return result


def _fetch_dbh_class_breakdown_ag_np(db: Session, fi_calc_id: str, blocks: List[Any]) -> List[Dict[str, Any]]:
    """DBH class grouped into Advance Growth (10-40 cm) and Mature Tree (>40 cm), Nepali.

    - एड्भान्स ग्रोथ (१०-४० से.मी.) = Sm.Pole + Lg.Pole + Sm.Tree
    - परिपक्व रूख (>४० से.मी.) = Med.Tree + Lg.Tree + V.Lg.Tree
    Grand total weighted by sample plot count.
    """
    per_block_rows = _fetch_dbh_class_breakdown(db, fi_calc_id, None)

    ag_classes = {"10-20 Sm.Pole", "20-30 Lg.Pole", "30-40 Sm.Tree"}
    mt_classes = {"40-50 Med.Tree", "50-60 Lg.Tree", "60+ V.Lg.Tree"}
    np_groups = [
        ("ag", "एड्भान्स ग्रोथ (१०-४० से.मी.)"),
        ("mt", "परिपक्व रूख (>४० से.मी.)"),
    ]

    # Aggregate per block
    block_data: Dict[str, Dict] = {}
    block_order: List[str] = []
    for r in per_block_rows:
        if r["dbh_class"] in ag_classes:
            grp = "ag"
        elif r["dbh_class"] in mt_classes:
            grp = "mt"
        else:
            continue
        bn = r["block_name"]
        if bn not in block_data:
            block_data[bn] = {"ag": {"cnt": 0, "tim": 0, "fuel": 0, "tot": 0},
                              "mt": {"cnt": 0, "tim": 0, "fuel": 0, "tot": 0}}
            block_order.append(bn)
        g = block_data[bn][grp]
        g["cnt"] += r["count_per_ha"]
        g["tim"] += r["timber_m3_per_ha"]
        g["fuel"] += r["fuelwood_m3_per_ha"]
        g["tot"] += r["total_volume_m3_per_ha"]

    def _dash(val):
        return "—" if val == 0 else round(val, 2)

    result = []
    for bn in block_order:
        for grp_key, np_label in np_groups:
            g = block_data[bn][grp_key]
            if g["cnt"] == 0 and g["tim"] == 0 and g["fuel"] == 0 and g["tot"] == 0:
                continue
            result.append({
                "वन खण्ड": bn,
                "ब्यास समूह": np_label,
                "संख्या /हे.": _dash(g["cnt"]),
                "काठ (घ.मी. /हे.)": _dash(g["tim"]),
                "दाउरा (घ.मी. /हे.)": _dash(g["fuel"]),
                "जम्मा (घ.मी. /हे.)": _dash(g["tot"]),
            })

    # Grand total (weighted by sample plot count)
    block_plot_counts = {b.block_name: b.total_sample_plots or 0 for b in blocks}
    total_plots = sum(block_plot_counts.values())
    if total_plots > 0:
        grand = {"ag": {"cnt": 0.0, "tim": 0.0, "fuel": 0.0, "tot": 0.0},
                 "mt": {"cnt": 0.0, "tim": 0.0, "fuel": 0.0, "tot": 0.0}}
        for bn in block_order:
            w = block_plot_counts.get(bn, 0)
            if w <= 0:
                continue
            for grp_key in ("ag", "mt"):
                g = block_data[bn][grp_key]
                grand[grp_key]["cnt"] += g["cnt"] * w
                grand[grp_key]["tim"] += g["tim"] * w
                grand[grp_key]["fuel"] += g["fuel"] * w
                grand[grp_key]["tot"] += g["tot"] * w
        for grp_key, np_label in np_groups:
            g = grand[grp_key]
            result.append({
                "वन खण्ड": "कुल जम्मा (भारित)",
                "ब्यास समूह": np_label,
                "संख्या /हे.": _dash(g["cnt"] / total_plots),
                "काठ (घ.मी. /हे.)": _dash(g["tim"] / total_plots),
                "दाउरा (घ.मी. /हे.)": _dash(g["fuel"] / total_plots),
                "जम्मा (घ.मी. /हे.)": _dash(g["tot"] / total_plots),
            })

    return result


def _fetch_dbh_class_breakdown_single_np(db: Session, fi_calc_id: str, blocks: List[Any],
                                          class_set: set, np_label: str) -> List[Dict[str, Any]]:
    """Shared helper: single DBH group per-block per-hectare summary, Nepali."""
    per_block_rows = _fetch_dbh_class_breakdown(db, fi_calc_id, None)

    block_data: Dict[str, dict] = {}
    block_order: List[str] = []
    for r in per_block_rows:
        if r["dbh_class"] not in class_set:
            continue
        bn = r["block_name"]
        if bn not in block_data:
            block_data[bn] = {"cnt": 0, "tim": 0, "fuel": 0, "tot": 0}
            block_order.append(bn)
        g = block_data[bn]
        g["cnt"] += r["count_per_ha"]
        g["tim"] += r["timber_m3_per_ha"]
        g["fuel"] += r["fuelwood_m3_per_ha"]
        g["tot"] += r["total_volume_m3_per_ha"]

    def _dash(val):
        return "—" if val == 0 else round(val, 2)

    result = []
    for bn in block_order:
        g = block_data[bn]
        result.append({
            "वन खण्ड": bn,
            "संख्या /हे.": _dash(g["cnt"]),
            "काठ (घ.मी. /हे.)": _dash(g["tim"]),
            "दाउरा (घ.मी. /हे.)": _dash(g["fuel"]),
            "जम्मा (घ.मी. /हे.)": _dash(g["tot"]),
        })

    # Grand total (weighted by sample plot count)
    block_plot_counts = {b.block_name: b.total_sample_plots or 0 for b in blocks}
    total_plots = sum(block_plot_counts.values())
    if total_plots > 0:
        grand = {"cnt": 0.0, "tim": 0.0, "fuel": 0.0, "tot": 0.0}
        for bn in block_order:
            w = block_plot_counts.get(bn, 0)
            if w <= 0:
                continue
            g = block_data[bn]
            grand["cnt"] += g["cnt"] * w
            grand["tim"] += g["tim"] * w
            grand["fuel"] += g["fuel"] * w
            grand["tot"] += g["tot"] * w
        result.append({
            "वन खण्ड": "कुल जम्मा (भारित)",
            "संख्या /हे.": _dash(grand["cnt"] / total_plots),
            "काठ (घ.मी. /हे.)": _dash(grand["tim"] / total_plots),
            "दाउरा (घ.मी. /हे.)": _dash(grand["fuel"] / total_plots),
            "जम्मा (घ.मी. /हे.)": _dash(grand["tot"] / total_plots),
        })

    return result


def _fetch_dbh_class_breakdown_advance_np(db: Session, fi_calc_id: str, blocks: List[Any]) -> List[Dict[str, Any]]:
    """Advance Growth (एड्भान्स ग्रोथ — DBH 10-40 cm) per-block per-hectare, Nepali."""
    return _fetch_dbh_class_breakdown_single_np(
        db, fi_calc_id, blocks,
        {"10-20 Sm.Pole", "20-30 Lg.Pole", "30-40 Sm.Tree"},
        "एड्भान्स ग्रोथ (१०-४० से.मी.)",
    )


def _fetch_dbh_class_breakdown_mature_np(db: Session, fi_calc_id: str, blocks: List[Any]) -> List[Dict[str, Any]]:
    """Mature Tree (परिपक्व रूख — DBH >40 cm) per-block per-hectare, Nepali."""
    return _fetch_dbh_class_breakdown_single_np(
        db, fi_calc_id, blocks,
        {"40-50 Med.Tree", "50-60 Lg.Tree", "60+ V.Lg.Tree"},
        "परिपक्व रूख (>४० से.मी.)",
    )


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

    # Block effective areas for weighted grand total and total inventory computation
    block_areas = _fetch_block_effective_areas(db, calculation_id)

    # Species-level block growing stock (with weighted totals)
    species_block_data = _fetch_species_block_breakdown(db, fi_calc.id, block_areas)

    if blocks:
        # Use sample plot count as weight (pool-all-plots methodology,
        # matching Tree Model's Overall Stand Summary)
        block_weights = {b.block_name: b.total_sample_plots or 0 for b in blocks}
        total_weight = sum(block_weights.values()) if block_weights else 0

        def _wavg(key: str, overall_fallback: Optional[float] = None) -> float:
            """Weighted average across blocks (weighted by sample plot count)."""
            if not block_weights or total_weight <= 0:
                return float(getattr(blocks[0], key, 0) or 0)
            wsum = sum(
                float(getattr(b, key, 0) or 0) * block_weights.get(b.block_name, 0)
                for b in blocks
            )
            return wsum / total_weight if total_weight else 0

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

        # ── Grand total row (weighted by sample plot count) ──
        def _wsum(key: str) -> float:
            return sum(
                float(getattr(b, key, 0) or 0) * block_weights.get(b.block_name, 0)
                for b in blocks
            )

        if block_weights and total_weight > 0:
            wpt = _wsum("pole_timber_m3_per_ha") / total_weight
            wpf = _wsum("pole_firewood_m3_per_ha") / total_weight
            wtt = _wsum("tree_timber_m3_per_ha") / total_weight
            wtf = _wsum("tree_firewood_m3_per_ha") / total_weight
            wgs = _wsum("total_growing_stock_m3_per_ha") / total_weight
            wmai = _wsum("mai_percent") / total_weight
            wcond = "—"
            waah = {"Good": 75.0, "Moderate": 60.0, "Weak": 40.0}
            wmai_val = wgs * wmai / 100.0
            waah_val = wmai_val * 60.0 / 100.0
            grand = {
                "total_sample_plots": sum(b.total_sample_plots or 0 for b in blocks),
                "regeneration_per_ha": round(_wsum("regeneration_per_ha") / total_weight),
                "sapling_per_ha": round(_wsum("sapling_per_ha") / total_weight),
                "pole_per_ha": round(_wsum("pole_per_ha") / total_weight),
                "tree_per_ha": round(_wsum("tree_per_ha") / total_weight),
                "pole_timber_m3_per_ha": round(wpt, 2),
                "pole_firewood_m3_per_ha": round(wpf, 2),
                "pole_total_m3_per_ha": round(wpt + wpf, 2),
                "tree_timber_m3_per_ha": round(wtt, 2),
                "tree_firewood_m3_per_ha": round(wtf, 2),
                "tree_total_m3_per_ha": round(wtt + wtf, 2),
                "total_volume_m3_per_ha": round(wpt + wpf + wtt + wtf, 2),
                "total_growing_stock_m3_per_ha": round(wgs, 2),
                "satellite_volume_m3_per_ha": round(_wsum("satellite_volume_m3_per_ha") / total_weight, 2),
                "basal_area_m2_per_ha": round(_wsum("basal_area_m2_per_ha") / total_weight, 2),
                "regeneration_condition": "—",
                "forest_condition": wcond,
                "mai_percent": round(wmai, 2),
                "aah_multiplier_percent": 60.0,
                "mai_total_m3_per_ha": round(wmai_val, 2),
                "aah_total_m3_per_ha": round(waah_val, 2),
                "weighted_wood_density": round(_wsum("weighted_wood_density") / total_weight, 3),
                "agb_t_per_ha": round(_wsum("agb_t_per_ha") / total_weight, 2),
                "bgb_t_per_ha": round(_wsum("bgb_t_per_ha") / total_weight, 2),
                "total_biomass_t_per_ha": round(_wsum("total_biomass_t_per_ha") / total_weight, 2),
                "carbon_stock_tc_per_ha": round(_wsum("carbon_stock_tc_per_ha") / total_weight, 2),
                "co2_equivalent_tco2_per_ha": round(_wsum("co2_equivalent_tco2_per_ha") / total_weight, 2),
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
            # ── Advance Growth (10-40 cm) & Mature Tree (>40 cm) — Nepali ──
            "fi_block_dbh_class_ag_np": _fetch_dbh_class_breakdown_ag_np(db, fi_calc.id, blocks),
            # ── Advance Growth only (एड्भान्स ग्रोथ — 10-40 cm) — Nepali ──
            "fi_block_dbh_class_advance_np": _fetch_dbh_class_breakdown_advance_np(db, fi_calc.id, blocks),
            # ── Mature Tree only (परिपक्व रूख — >40 cm) — Nepali ──
            "fi_block_dbh_class_mature_np": _fetch_dbh_class_breakdown_mature_np(db, fi_calc.id, blocks),
            # ── DBH class chart data (forest-wide grand total, pole+tree) ──
            "fi_dbh_class_chart_data": _prepare_dbh_class_chart_data(db, fi_calc.id, block_areas),
            # ── वार्षिक वृद्धि तालिका / MAI table ──
            "fi_mai_table": mai_table,
            # ── वार्षिक स्वीकार्य कटान तालिका / AAH table ──
            "fi_aah_table": aah_table,

            # ── ब्लक अनुसार प्रति हेक्टर विरूवा, लाथ्रा, पोल तथा रूखको संख्या ──
            "fi_block_tree_count_per_ha": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "विरुवा_प्रति_हेक्टर": br["regeneration_per_ha"],
                    "लाथ्रा_प्रति_हेक्टर": br["sapling_per_ha"],
                    "खाँवा_प्रति_हेक्टर": br["pole_per_ha"],
                    "रूख_प्रति_हेक्टर": br["tree_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "विरुवा_प्रति_हेक्टर": grand["regeneration_per_ha"],
                "लाथ्रा_प्रति_हेक्टर": grand["sapling_per_ha"],
                "खाँवा_प्रति_हेक्टर": grand["pole_per_ha"],
                "रूख_प्रति_हेक्टर": grand["tree_per_ha"],
            }] if grand else []),

            # ── ब्लक अनुसार प्रति हेक्टर पोल (खाँवा) तथा रूखको काठ दाउराको परिणाम ──
            "fi_block_pole_tree_volume": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "खाँवा_काठ_घमी_प्रति_हे": br["pole_timber_m3_per_ha"],
                    "खाँवा_दाउरा_घमी_प्रति_हे": br["pole_firewood_m3_per_ha"],
                    "खाँवा_जम्मा_घमी_प्रति_हे": br["pole_total_m3_per_ha"],
                    "रूख_काठ_घमी_प्रति_हे": br["tree_timber_m3_per_ha"],
                    "रूख_दाउरा_घमी_प्रति_हे": br["tree_firewood_m3_per_ha"],
                    "रूख_जम्मा_घमी_प्रति_हे": br["tree_total_m3_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "खाँवा_काठ_घमी_प्रति_हे": grand["pole_timber_m3_per_ha"],
                "खाँवा_दाउरा_घमी_प्रति_हे": grand["pole_firewood_m3_per_ha"],
                "खाँवा_जम्मा_घमी_प्रति_हे": grand["pole_total_m3_per_ha"],
                "रूख_काठ_घमी_प्रति_हे": grand["tree_timber_m3_per_ha"],
                "रूख_दाउरा_घमी_प्रति_हे": grand["tree_firewood_m3_per_ha"],
                "रूख_जम्मा_घमी_प्रति_हे": grand["tree_total_m3_per_ha"],
            }] if grand else []),

            # ── वन ब्लक अनुसार काठ, दाउरा तथा जम्मा वृद्धि मौज्दात प्रति हेक्टर ──
            "fi_block_growing_stock": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "वृद्धि_मौज्दात_काठ_घमी_प्रति_हे": round(
                        float(br["pole_timber_m3_per_ha"] or 0) + float(br["tree_timber_m3_per_ha"] or 0), 2),
                    "वृद्धि_मौज्दात_दाउरा_घमी_प्रति_हे": round(
                        float(br["pole_firewood_m3_per_ha"] or 0) + float(br["tree_firewood_m3_per_ha"] or 0), 2),
                    "वृद्धि_मौज्दात_जम्मा_घमी_प्रति_हे": br["total_volume_m3_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "वृद्धि_मौज्दात_काठ_घमी_प्रति_हे": round(
                    float(grand["pole_timber_m3_per_ha"] or 0) + float(grand["tree_timber_m3_per_ha"] or 0), 2),
                "वृद्धि_मौज्दात_दाउरा_घमी_प्रति_हे": round(
                    float(grand["pole_firewood_m3_per_ha"] or 0) + float(grand["tree_firewood_m3_per_ha"] or 0), 2),
                "वृद्धि_मौज्दात_जम्मा_घमी_प्रति_हे": grand["total_volume_m3_per_ha"],
            }] if grand else []),

            # ── ब्लक अनुसार प्रति हेक्टर वेसल एरीया ──
            "fi_block_basal_area": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "बेसल_एरिया_वर्गमी_प्रति_हे": br["basal_area_m2_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "बेसल_एरिया_वर्गमी_प्रति_हे": grand["basal_area_m2_per_ha"],
            }] if grand else []),

            # ── NASA/ORNL/biomass_carbon_density/v1 को अधारमा प्रति हेक्टर ग्रोइङ्स्टक अनुमान ──
            "fi_block_satellite_volume": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "भू_उपग्रहिय_इमेजको_आधारमा_जम्मा_आयतन": br["satellite_volume_m3_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "भू_उपग्रहिय_इमेजको_आधारमा_जम्मा_आयतन": grand["satellite_volume_m3_per_ha"],
            }] if grand else []),

            # ── ब्लक अनुसार पुनरोत्पादन तथा वनको अवस्था र वार्षिक वृद्धि निर्धारण ──
            "fi_block_condition_growth": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "पुनरोत्पादनको_अवस्था": br["regeneration_condition"],
                    "वनको_अवस्था": br["forest_condition"],
                    "औसत_वार्षिक_वृद्धि_प्रतिशत": br["mai_percent"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "पुनरोत्पादनको_अवस्था": "—",
                "वनको_अवस्था": "—",
                "औसत_वार्षिक_वृद्धि_प्रतिशत": grand["mai_percent"],
            }] if grand else []),

            # ── (IPCC/REDD+) अनुसारको वनश्रोत सर्भेक्षणको अधारमा बायोमास तथा कार्वनको अनुमान ──
            "fi_block_biomass_carbon": [
                {
                    "ब्लकको_नाम": br["block_name"],
                    "काठ_घनत्व_टन_प्रति_घमी": br["weighted_wood_density"],
                    "जमिन_माथिको_बायोमास_टन_प्रति_हे": br["agb_t_per_ha"],
                    "जमिन_मुनिको_बायोमास_टन_प्रति_हे": br["bgb_t_per_ha"],
                    "जम्मा_बायोमास_टन_प्रति_हे": br["total_biomass_t_per_ha"],
                    "कार्बन_टन_कार्बन_प्रति_हे": br["carbon_stock_tc_per_ha"],
                    "CO₂_समतुल्य_टन_CO₂_प्रति_हे": br["co2_equivalent_tco2_per_ha"],
                }
                for br in block_rows
            ] + ([{
                "ब्लकको_नाम": "जम्मा (भारित)",
                "काठ_घनत्व_टन_प्रति_घमी": grand["weighted_wood_density"],
                "जमिन_माथिको_बायोमास_टन_प्रति_हे": grand["agb_t_per_ha"],
                "जमिन_मुनिको_बायोमास_टन_प्रति_हे": grand["bgb_t_per_ha"],
                "जम्मा_बायोमास_टन_प्रति_हे": grand["total_biomass_t_per_ha"],
                "कार्बन_टन_कार्बन_प्रति_हे": grand["carbon_stock_tc_per_ha"],
                "CO₂_समतुल्य_टन_CO₂_प्रति_हे": grand["co2_equivalent_tco2_per_ha"],
            }] if grand else []),
            "_block_areas_ha": block_areas,
        }

    return {
        "available": True, "total_sample_plots": 0, "total_blocks": 0,
        "_block_areas_ha": block_areas,
        "fi_species_composition": {},
        "fi_dominant_species": [],
        "fi_co_dominant_species": [],
        "fi_associated_species": [],
        "fi_fast_growing_species": [],
        "fi_moderate_growing_species": [],
        "fi_slow_growing_species": [],
        "fi_species_volume_by_block": [],
    }


def _compute_total_inventory(fi_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert per-hectare field inventory data to total inventory absolute values.

    Takes the output of get_field_inventory_data() (which must include _block_areas_ha),
    computes ti_ (total inventory) keys by multiplying per-hectare values by block area.
    """
    result: Dict[str, Any] = {}
    block_areas: Dict[str, float] = fi_data.get("_block_areas_ha", {})
    if not fi_data.get("available") or not block_areas:
        result["ti_available"] = False
        return result
    result["ti_available"] = True

    total_area = sum(block_areas.values())
    result["ti_effective_area_ha"] = round(total_area, 4)
    result["ti_total_blocks"] = fi_data.get("total_blocks", 0)
    result["ti_total_plots"] = fi_data.get("total_sample_plots", 0)

    # ── Scalar forest-wide totals (per-ha × total_area) ──
    _SCALAR_TI = [
        ("fi_regeneration_per_ha", "ti_total_regeneration", 0),
        ("fi_sapling_per_ha", "ti_total_sapling", 0),
        ("fi_pole_per_ha", "ti_total_pole", 0),
        ("fi_tree_per_ha", "ti_total_tree", 0),
        ("fi_growing_stock_m3_per_ha", "ti_total_growing_stock_m3", 2),
        ("fi_basal_area_m2_per_ha", "ti_total_basal_area_m2", 2),
        ("fi_agb_t_per_ha", "ti_total_agb_tonnes", 3),
        ("fi_bgb_t_per_ha", "ti_total_bgb_tonnes", 3),
        ("fi_total_biomass_t_per_ha", "ti_total_biomass_tonnes", 3),
        ("fi_carbon_stock_tc_per_ha", "ti_total_carbon_tc", 3),
        ("fi_co2_equivalent_tco2_per_ha", "ti_total_co2_tco2", 3),
    ]
    for fi_key, ti_key, prec in _SCALAR_TI:
        val = fi_data.get(fi_key, 0)
        if isinstance(val, (int, float)) and val:
            result[ti_key] = round(val * total_area, prec) if prec else int(val * total_area)
        else:
            result[ti_key] = 0

    # ── MAI / AAH forest-wide totals ──
    gs_per_ha = float(fi_data.get("fi_growing_stock_m3_per_ha", 0) or 0)
    mai_pct = float(fi_data.get("fi_mai_percent", 0) or 0)
    mai_per_ha = gs_per_ha * mai_pct / 100.0
    result["ti_total_mai_m3_per_year"] = round(mai_per_ha * total_area, 2)
    aah_per_ha = mai_per_ha * 0.60
    result["ti_total_aah_m3_per_year"] = round(aah_per_ha * total_area, 2)

    # ── Weighted wood density (density is independent of area) ──
    result["ti_weighted_wood_density"] = fi_data.get("fi_weighted_wood_density", 0)

    # ── Helper: build block-wise absolute row from per-ha row ──
    def _to_abs(per_ha_row: dict, area: float) -> dict:
        """Multiply all per-hectare numeric fields by area to get absolute values."""
        abs_row = dict(per_ha_row)
        for k, v in per_ha_row.items():
            if isinstance(v, (int, float)) and k not in ("total_sample_plots", "mai_percent", "aah_multiplier_percent"):
                abs_row[k] = round(v * area, 2) if isinstance(v, float) else int(v * area)
        return abs_row

    # ── Block-wise list variables ──
    block_summaries = fi_data.get("fi_block_summaries", [])
    ti_block_rows = []
    for br in block_summaries:
        bn = br.get("block_name", "")
        if bn == "Grand Total (Weighted)":
            continue
        area = block_areas.get(bn, 0)
        if area <= 0:
            continue
        ti_block_rows.append(_to_abs(br, area))

    if ti_block_rows:
        # ti_block_summaries — full block-wise absolute results
        result["ti_block_summaries"] = ti_block_rows

        # Forest-wide total row
        ft = {
            "block_name": "Forest Total",
            "total_sample_plots": sum(r.get("total_sample_plots", 0) for r in ti_block_rows),
            "regeneration_per_ha": sum(r.get("regeneration_per_ha", 0) for r in ti_block_rows),
            "sapling_per_ha": sum(r.get("sapling_per_ha", 0) for r in ti_block_rows),
            "pole_per_ha": sum(r.get("pole_per_ha", 0) for r in ti_block_rows),
            "tree_per_ha": sum(r.get("tree_per_ha", 0) for r in ti_block_rows),
            "pole_timber_m3_per_ha": round(sum(r.get("pole_timber_m3_per_ha", 0) for r in ti_block_rows), 2),
            "pole_firewood_m3_per_ha": round(sum(r.get("pole_firewood_m3_per_ha", 0) for r in ti_block_rows), 2),
            "pole_total_m3_per_ha": round(sum(r.get("pole_total_m3_per_ha", 0) for r in ti_block_rows), 2),
            "tree_timber_m3_per_ha": round(sum(r.get("tree_timber_m3_per_ha", 0) for r in ti_block_rows), 2),
            "tree_firewood_m3_per_ha": round(sum(r.get("tree_firewood_m3_per_ha", 0) for r in ti_block_rows), 2),
            "tree_total_m3_per_ha": round(sum(r.get("tree_total_m3_per_ha", 0) for r in ti_block_rows), 2),
            "total_volume_m3_per_ha": round(sum(r.get("total_volume_m3_per_ha", 0) for r in ti_block_rows), 2),
            "total_growing_stock_m3_per_ha": round(sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows), 2),
            "satellite_volume_m3_per_ha": round(sum(r.get("satellite_volume_m3_per_ha", 0) for r in ti_block_rows), 2),
            "basal_area_m2_per_ha": round(sum(r.get("basal_area_m2_per_ha", 0) for r in ti_block_rows), 2),
            "mai_total_m3_per_ha": round(sum(r.get("mai_total_m3_per_ha", 0) for r in ti_block_rows), 2),
            "aah_total_m3_per_ha": round(sum(r.get("aah_total_m3_per_ha", 0) for r in ti_block_rows), 2),
            "mai_percent": round(
                sum(r.get("mai_percent", 0) * r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows) /
                max(sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows), 1), 2
            ),
            "aah_multiplier_percent": round(
                sum(r.get("aah_multiplier_percent", 60.0) * r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows) /
                max(sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows), 1), 1
            ),
            "agb_t_per_ha": round(sum(r.get("agb_t_per_ha", 0) for r in ti_block_rows), 2),
            "bgb_t_per_ha": round(sum(r.get("bgb_t_per_ha", 0) for r in ti_block_rows), 2),
            "total_biomass_t_per_ha": round(sum(r.get("total_biomass_t_per_ha", 0) for r in ti_block_rows), 2),
            "carbon_stock_tc_per_ha": round(sum(r.get("carbon_stock_tc_per_ha", 0) for r in ti_block_rows), 2),
            "co2_equivalent_tco2_per_ha": round(sum(r.get("co2_equivalent_tco2_per_ha", 0) for r in ti_block_rows), 2),
            "weighted_wood_density": round(
                sum(r.get("weighted_wood_density", 0) * r.get("total_growing_stock_m3_per_ha", 0)
                    for r in ti_block_rows) /
                max(sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows), 1), 3
            ),
        }
        result["ti_block_summaries"].append(ft)

        # ── Nepali-keyed block-wise tables ──
        result["ti_block_tree_count_total"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "विरुवा_कुल": r.get("regeneration_per_ha", 0),
                "लाथ्रा_कुल": r.get("sapling_per_ha", 0),
                "खाँवा_कुल": r.get("pole_per_ha", 0),
                "रूख_कुल": r.get("tree_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "विरुवा_कुल": ft.get("regeneration_per_ha", 0),
            "लाथ्रा_कुल": ft.get("sapling_per_ha", 0),
            "खाँवा_कुल": ft.get("pole_per_ha", 0),
            "रूख_कुल": ft.get("tree_per_ha", 0),
        }]

        result["ti_block_pole_tree_volume"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "खाँवा_काठ_कुल_घमी": r.get("pole_timber_m3_per_ha", 0),
                "खाँवा_दाउरा_कुल_घमी": r.get("pole_firewood_m3_per_ha", 0),
                "खाँवा_जम्मा_कुल_घमी": r.get("pole_total_m3_per_ha", 0),
                "रूख_काठ_कुल_घमी": r.get("tree_timber_m3_per_ha", 0),
                "रूख_दाउरा_कुल_घमी": r.get("tree_firewood_m3_per_ha", 0),
                "रूख_जम्मा_कुल_घमी": r.get("tree_total_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "खाँवा_काठ_कुल_घमी": ft.get("pole_timber_m3_per_ha", 0),
            "खाँवा_दाउरा_कुल_घमी": ft.get("pole_firewood_m3_per_ha", 0),
            "खाँवा_जम्मा_कुल_घमी": ft.get("pole_total_m3_per_ha", 0),
            "रूख_काठ_कुल_घमी": ft.get("tree_timber_m3_per_ha", 0),
            "रूख_दाउरा_कुल_घमी": ft.get("tree_firewood_m3_per_ha", 0),
            "रूख_जम्मा_कुल_घमी": ft.get("tree_total_m3_per_ha", 0),
        }]

        result["ti_block_growing_stock"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "वृद्धि_मौज्दात_काठ_कुल_घमी": round(
                    float(r.get("pole_timber_m3_per_ha", 0) or 0) + float(r.get("tree_timber_m3_per_ha", 0) or 0), 2),
                "वृद्धि_मौज्दात_दाउरा_कुल_घमी": round(
                    float(r.get("pole_firewood_m3_per_ha", 0) or 0) + float(r.get("tree_firewood_m3_per_ha", 0) or 0), 2),
                "वृद्धि_मौज्दात_जम्मा_कुल_घमी": r.get("total_volume_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "वृद्धि_मौज्दात_काठ_कुल_घमी": round(
                float(ft.get("pole_timber_m3_per_ha", 0) or 0) + float(ft.get("tree_timber_m3_per_ha", 0) or 0), 2),
            "वृद्धि_मौज्दात_दाउरा_कुल_घमी": round(
                float(ft.get("pole_firewood_m3_per_ha", 0) or 0) + float(ft.get("tree_firewood_m3_per_ha", 0) or 0), 2),
            "वृद्धि_मौज्दात_जम्मा_कुल_घमी": ft.get("total_volume_m3_per_ha", 0),
        }]

        result["ti_block_basal_area"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "बेसल_एरिया_कुल_वर्गमी": r.get("basal_area_m2_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "बेसल_एरिया_कुल_वर्गमी": ft.get("basal_area_m2_per_ha", 0),
        }]

        result["ti_block_satellite_volume"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "भू_उपग्रहिय_इमेजको_आधारमा_कुल_आयतन": r.get("satellite_volume_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "भू_उपग्रहिय_इमेजको_आधारमा_कुल_आयतन": ft.get("satellite_volume_m3_per_ha", 0),
        }]

        result["ti_block_condition_growth"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "पुनरोत्पादनको_अवस्था": r.get("regeneration_condition", ""),
                "वनको_अवस्था": r.get("forest_condition", ""),
                "औसत_वार्षिक_वृद्धि_प्रतिशत": r.get("mai_percent", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "पुनरोत्पादनको_अवस्था": "—",
            "वनको_अवस्था": "—",
            "औसत_वार्षिक_वृद्धि_प्रतिशत": ft.get("mai_percent", 0),
        }]

        result["ti_block_biomass_carbon"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "काठ_घनत्व_टन_प्रति_घमी": r.get("weighted_wood_density", 0),
                "जमिन_माथिको_बायोमास_कुल_टन": r.get("agb_t_per_ha", 0),
                "जमिन_मुनिको_बायोमास_कुल_टन": r.get("bgb_t_per_ha", 0),
                "जम्मा_बायोमास_कुल_टन": r.get("total_biomass_t_per_ha", 0),
                "कार्बन_कुल_टन_कार्बन": r.get("carbon_stock_tc_per_ha", 0),
                "CO₂_समतुल्य_कुल_टन_CO₂": r.get("co2_equivalent_tco2_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "काठ_घनत्व_टन_प्रति_घमी": ft.get("weighted_wood_density", 0),
            "जमिन_माथिको_बायोमास_कुल_टन": ft.get("agb_t_per_ha", 0),
            "जमिन_मुनिको_बायोमास_कुल_टन": ft.get("bgb_t_per_ha", 0),
            "जम्मा_बायोमास_कुल_टन": ft.get("total_biomass_t_per_ha", 0),
            "कार्बन_कुल_टन_कार्बन": ft.get("carbon_stock_tc_per_ha", 0),
            "CO₂_समतुल्य_कुल_टन_CO₂": ft.get("co2_equivalent_tco2_per_ha", 0),
        }]

        # ── MAI table (absolute) ──
        result["ti_mai_table"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "खाँवा_संख्या": r.get("pole_per_ha", 0),
                "रूख_संख्या": r.get("tree_per_ha", 0),
                "खाँवा_काठ_कुल_घमी": r.get("pole_timber_m3_per_ha", 0),
                "खाँवा_दाउरा_कुल_घमी": r.get("pole_firewood_m3_per_ha", 0),
                "खाँवा_जम्मा_कुल_घमी": r.get("pole_total_m3_per_ha", 0),
                "रूख_काठ_कुल_घमी": r.get("tree_timber_m3_per_ha", 0),
                "रूख_दाउरा_कुल_घमी": r.get("tree_firewood_m3_per_ha", 0),
                "रूख_जम्मा_कुल_घमी": r.get("tree_total_m3_per_ha", 0),
                "कुल_MAI_घमी_प्रति_वर्ष": r.get("mai_total_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "खाँवा_संख्या": ft.get("pole_per_ha", 0),
            "रूख_संख्या": ft.get("tree_per_ha", 0),
            "खाँवा_काठ_कुल_घमी": ft.get("pole_timber_m3_per_ha", 0),
            "खाँवा_दाउरा_कुल_घमी": ft.get("pole_firewood_m3_per_ha", 0),
            "खाँवा_जम्मा_कुल_घमी": ft.get("pole_total_m3_per_ha", 0),
            "रूख_काठ_कुल_घमी": ft.get("tree_timber_m3_per_ha", 0),
            "रूख_दाउरा_कुल_घमी": ft.get("tree_firewood_m3_per_ha", 0),
            "रूख_जम्मा_कुल_घमी": ft.get("tree_total_m3_per_ha", 0),
            "कुल_MAI_घमी_प्रति_वर्ष": ft.get("mai_total_m3_per_ha", 0),
        }]

        # ── AAH table (absolute) ──
        result["ti_aah_table"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "खाँवा_संख्या": r.get("pole_per_ha", 0),
                "रूख_संख्या": r.get("tree_per_ha", 0),
                "वन_अवस्था": r.get("forest_condition", ""),
                "AAH_गुणक_प्रतिशत": r.get("aah_multiplier_percent", 60.0),
                "कुल_AAH_घमी_प्रति_वर्ष": r.get("aah_total_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "खाँवा_संख्या": ft.get("pole_per_ha", 0),
            "रूख_संख्या": ft.get("tree_per_ha", 0),
            "वन_अवस्था": "—",
            "AAH_गुणक_प्रतिशत": 60.0,
            "कुल_AAH_घमी_प्रति_वर्ष": ft.get("aah_total_m3_per_ha", 0),
        }]

        # ── Regeneration status (absolute) ──
        result["ti_block_regeneration_status"] = fi_data.get("fi_block_regeneration_status", [])

    # ── Species block growing stock (absolute) ──
    species_data = fi_data.get("fi_species_block_growing_stock", [])
    ti_species_rows = []
    for sr in species_data:
        bn = sr.get("block_name", "")
        if bn == "Grand Total (Weighted)":
            continue
        area = block_areas.get(bn, 0)
        if area <= 0:
            continue
        ti_species_rows.append({
            "block_name": bn,
            "species_scientific": sr.get("species_scientific", ""),
            "species_local": sr.get("species_local", ""),
            "count_total": int((sr.get("count_per_ha", 0) or 0) * area),
            "timber_m3_total": round((sr.get("timber_m3_per_ha", 0) or 0) * area, 2),
            "fuelwood_m3_total": round((sr.get("fuelwood_m3_per_ha", 0) or 0) * area, 2),
            "total_volume_m3_total": round((sr.get("total_volume_m3_per_ha", 0) or 0) * area, 2),
        })
    if ti_species_rows:
        result["ti_species_block_growing_stock"] = ti_species_rows

        # Species-level grand totals
        sp_agg: Dict = {}
        sp_order: list = []
        for sr in ti_species_rows:
            key = (sr["species_scientific"] or "") + "||" + (sr["species_local"] or "")
            if key not in sp_agg:
                sp_agg[key] = {"sci": sr["species_scientific"], "loc": sr["species_local"],
                               "cnt": 0, "tim": 0.0, "fuel": 0.0, "tot": 0.0}
                sp_order.append(key)
            sp_agg[key]["cnt"] += sr["count_total"]
            sp_agg[key]["tim"] += sr["timber_m3_total"]
            sp_agg[key]["fuel"] += sr["fuelwood_m3_total"]
            sp_agg[key]["tot"] += sr["total_volume_m3_total"]
        for key in sp_order:
            s = sp_agg[key]
            ti_species_rows.append({
                "block_name": "Grand Total",
                "species_scientific": s["sci"],
                "species_local": s["loc"],
                "count_total": s["cnt"],
                "timber_m3_total": round(s["tim"], 2),
                "fuelwood_m3_total": round(s["fuel"], 2),
                "total_volume_m3_total": round(s["tot"], 2),
            })

    # ── Species volume by block (absolute) — sorted species list ──
    species_vol = fi_data.get("fi_species_volume_by_block", [])
    if species_vol:
        result["ti_species_volume_by_block"] = [
            {"species": name, "total_volume_m3": round(pct / 100.0 * result.get("ti_total_growing_stock_m3", 0), 2)}
            for name, pct in species_vol
        ]

    # ── Species composition (absolute numbers) ──
    comp_pct = fi_data.get("fi_species_composition", {})
    if comp_pct and result.get("ti_total_growing_stock_m3"):
        result["ti_species_composition_absolute"] = {
            name: round(pct / 100.0 * result["ti_total_growing_stock_m3"], 2)
            for name, pct in comp_pct.items()
        }
        result["ti_dominant_species_absolute"] = fi_data.get("fi_dominant_species", [])
        result["ti_co_dominant_species_absolute"] = fi_data.get("fi_co_dominant_species", [])
        result["ti_associated_species_absolute"] = fi_data.get("fi_associated_species", [])

    # ── Growth rate species totals (absolute volume) ──
    fast = fi_data.get("fi_fast_growing_species", [])
    moderate = fi_data.get("fi_moderate_growing_species", [])
    slow = fi_data.get("fi_slow_growing_species", [])
    if comp_pct and result.get("ti_total_growing_stock_m3"):
        result["ti_fast_growing_species_total"] = round(
            sum(comp_pct.get(s, 0) for s in fast) / 100.0 * result["ti_total_growing_stock_m3"], 2
        ) if fast else 0
        result["ti_moderate_growing_species_total"] = round(
            sum(comp_pct.get(s, 0) for s in moderate) / 100.0 * result["ti_total_growing_stock_m3"], 2
        ) if moderate else 0
        result["ti_slow_growing_species_total"] = round(
            sum(comp_pct.get(s, 0) for s in slow) / 100.0 * result["ti_total_growing_stock_m3"], 2
        ) if slow else 0

    # ── Chart data structures ──
    block_names = [r["block_name"] for r in ti_block_rows]
    block_stocks = [r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows]
    block_mais = [r.get("mai_total_m3_per_ha", 0) for r in ti_block_rows]
    block_aahs = [r.get("aah_total_m3_per_ha", 0) for r in ti_block_rows]
    colors = ["#22c55e", "#3b82f6", "#eab308", "#f97316", "#a855f7", "#ec4899", "#14b8a6", "#f43f5e"]

    result["ti_chart_block_stock_pie"] = {
        "type": "pie",
        "title_np": "ब्लक अनुसार कुल ग्रोइङ स्टक वितरण",
        "title_en": "Block-wise Total Growing Stock Distribution",
        "labels": block_names,
        "data": block_stocks,
        "backgroundColor": colors[:len(block_names)],
        "unit": "m³",
    }
    result["ti_chart_block_comparison_bar"] = {
        "type": "bar",
        "title_np": "ब्लक अनुसार ग्रोइङ स्टक, MAI तथा AAH तुलना",
        "title_en": "Block-wise Growing Stock, MAI & AAH Comparison",
        "labels": block_names,
        "datasets": [
            {"label": "ग्रोइङ स्टक (m³)", "data": block_stocks, "backgroundColor": "#22c55e"},
            {"label": "MAI (m³/yr)", "data": block_mais, "backgroundColor": "#a855f7"},
            {"label": "AAH (m³/yr)", "data": block_aahs, "backgroundColor": "#f59e0b"},
        ],
    }

    # ── DBH class stacked bar chart data ──
    dbh_data = fi_data.get("fi_dbh_class_chart_data", [])
    if dbh_data:
        dbh_labels = [d["label"] for d in dbh_data]
        dbh_volumes = [d["total_volume_m3_per_ha"] for d in dbh_data]
        result["ti_chart_dbh_class_bar"] = {
            "type": "bar",
            "title_np": "DBH वर्ग अनुसार प्रतिहेक्टर आयतन",
            "title_en": "DBH Class Volume per ha",
            "labels": dbh_labels,
            "datasets": [{"label": "आयतन (m³/ha)", "data": dbh_volumes, "backgroundColor": "#22c55e"}],
        }

    # ── T7: DBH क्लास अनुसार कुल मौज्दात (Absolute) ──
    dbh_raw = fi_data.get("fi_block_dbh_class_growing_stock", [])
    _DBH_NP_LABEL = {
        "10-20 Sm.Pole": "१०-२० (सानो खाँवा)",
        "20-30 Lg.Pole": "२०-३० (ठुलो खाँवा)",
        "30-40 Sm.Tree": "३०-४० (सानो रूख)",
        "40-50 Med.Tree": "४०-५० (मध्यम रूख)",
        "50-60 Lg.Tree": "५०-६० (ठुलो रूख)",
        "60+ V.Lg.Tree": ">६० (धेरै ठुलो रूख)",
    }
    if dbh_raw and ti_block_rows:
        # Per-block DBH class absolute values
        dbh_abs_rows = []
        for r in dbh_raw:
            bn = r.get("block_name", "")
            area = block_areas.get(bn, 0)
            if area <= 0 or bn == "Grand Total (Weighted)":
                continue
            dbh_abs_rows.append({
                "ब्लकको_नाम": bn,
                "DBH_क्लास": _DBH_NP_LABEL.get(r["dbh_class"], r["dbh_class"]),
                "गणना": int(r["count_per_ha"] * area),
                "काठ_घमी": round(r["timber_m3_per_ha"] * area, 2),
                "दाउरा_घमी": round(r["fuelwood_m3_per_ha"] * area, 2),
                "आयतन_घमी": round(r["total_volume_m3_per_ha"] * area, 2),
            })

        # Forest-wide DBH class totals
        ft_dbh: dict = {}
        ft_dbh_order: list = []
        for r in dbh_abs_rows:
            cls = r["DBH_क्लास"]
            if cls not in ft_dbh:
                ft_dbh[cls] = {"गणना": 0, "काठ_घमी": 0.0, "दाउरा_घमी": 0.0, "आयतन_घमी": 0.0}
                ft_dbh_order.append(cls)
            ft_dbh[cls]["गणना"] += r["गणना"]
            ft_dbh[cls]["काठ_घमी"] += r["काठ_घमी"]
            ft_dbh[cls]["दाउरा_घमी"] += r["दाउरा_घमी"]
            ft_dbh[cls]["आयतन_घमी"] += r["आयतन_घमी"]

        result["ti_dbh_class_totals_table"] = dbh_abs_rows + [
            {"ब्लकको_नाम": "जम्मा वन कुल", "DBH_क्लास": cls,
             "गणना": ft_dbh[cls]["गणना"],
             "काठ_घमी": round(ft_dbh[cls]["काठ_घमी"], 2),
             "दाउरा_घमी": round(ft_dbh[cls]["दाउरा_घमी"], 2),
             "आयतन_घमी": round(ft_dbh[cls]["आयतन_घमी"], 2)}
            for cls in ft_dbh_order
        ]

        # ── T8: DBH क्लास अनुसार कुल मौज्दात (प्रति हे.) ──
        dbh_perha_rows = []
        for r in dbh_raw:
            bn = r.get("block_name", "")
            if bn == "Grand Total (Weighted)":
                continue
            area = block_areas.get(bn, 0)
            if area <= 0:
                continue
            dbh_perha_rows.append({
                "ब्लकको_नाम": bn,
                "DBH_क्लास": _DBH_NP_LABEL.get(r["dbh_class"], r["dbh_class"]),
                "गणना_प्रति_हे": r["count_per_ha"],
                "काठ_घमी_प्रति_हे": r["timber_m3_per_ha"],
                "दाउरा_घमी_प्रति_हे": r["fuelwood_m3_per_ha"],
                "आयतन_घमी_प्रति_हे": r["total_volume_m3_per_ha"],
            })
        # Forest-wide per-ha
        ft_perha: dict = {}
        ft_ph_order: list = []
        for r in dbh_perha_rows:
            cls = r["DBH_क्लास"]
            if cls not in ft_perha:
                ft_perha[cls] = {"गणना_प्रति_हे": 0.0, "काठ_घमी_प्रति_हे": 0.0,
                                 "दाउरा_घमी_प्रति_हे": 0.0, "आयतन_घमी_प्रति_हे": 0.0}
                ft_ph_order.append(cls)
            area = block_areas.get(r["ब्लकको_नाम"], 0)
            ft_perha[cls]["गणना_प्रति_हे"] += r["गणना_प्रति_हे"] * area
            ft_perha[cls]["काठ_घमी_प्रति_हे"] += r["काठ_घमी_प्रति_हे"] * area
            ft_perha[cls]["दाउरा_घमी_प्रति_हे"] += r["दाउरा_घमी_प्रति_हे"] * area
            ft_perha[cls]["आयतन_घमी_प्रति_हे"] += r["आयतन_घमी_प्रति_हे"] * area
        for cls in ft_ph_order:
            for k in ft_perha[cls]:
                ft_perha[cls][k] = round(ft_perha[cls][k] / total_area, 2) if total_area > 0 else 0

        result["ti_dbh_class_perha_table"] = dbh_perha_rows + [
            {"ब्लकको_नाम": "जम्मा वन कुल/हे.", "DBH_क्लास": cls, **ft_perha[cls]}
            for cls in ft_ph_order
        ]

        # ── T5: प्रजाति अनुसार DBH क्लास मौज्दात (block+dbh class, without species dimension) ──
        if dbh_perha_rows:
            result["ti_species_dbh_class_table"] = dbh_perha_rows
            # T6: पुरै वन क्षेत्र — forest-wide species×DBH (without species breakdown)
            result["ti_forest_dbh_class_table"] = [
                {"DBH_क्लास": cls,
                 "गणना_प्रति_हे": ft_perha[cls]["गणना_प्रति_हे"],
                 "काठ_घमी_प्रति_हे": ft_perha[cls]["काठ_घमी_प्रति_हे"],
                 "दाउरा_घमी_प्रति_हे": ft_perha[cls]["दाउरा_घमी_प्रति_हे"],
                 "आयतन_घमी_प्रति_हे": ft_perha[cls]["आयतन_घमी_प्रति_हे"]}
                for cls in ft_ph_order
            ]

        # ── T9: DBH क्लास अनुसार MAI ──
        _mai_pct = float(fi_data.get("fi_mai_percent", 0) or 0)
        _aah_mult = 0.60  # default AAH multiplier
        # Build per-ha lookup from dbh_perha_rows
        _perha_lookup = {}
        for r in dbh_perha_rows:
            _perha_lookup[(r["ब्लकको_नाम"], r["DBH_क्लास"])] = r["गणना_प्रति_हे"]
        dbh_mai_rows = []
        for r in dbh_abs_rows:
            bname = r["ब्लकको_नाम"]
            vol = r["आयतन_घमी"]
            count_abs = r["गणना"]
            count_per_ha = _perha_lookup.get((bname, r["DBH_क्लास"]), 0)
            dbh_mai_rows.append({
                "ब्लकको_नाम": bname,
                "DBH_क्लास": r["DBH_क्लास"],
                "गणना_प्रति_हे": count_per_ha,
                "गणना": count_abs,
                "आयतन_घमी": vol,
                "MAI_घमी_प्रति_वर्ष": round(vol * _mai_pct / 100.0, 2),
                "MAI_संख्या_प्रति_हे": round(count_per_ha * _mai_pct / 100.0, 2),
            })
        # Forest-wide DBH MAI
        ft_mai = []
        for cls in ft_dbh_order:
            vol = ft_dbh[cls]["आयतन_घमी"]
            count_abs = ft_dbh[cls]["गणना"]
            count_per_ha = round(ft_perha[cls]["गणना_प्रति_हे"], 2) if cls in ft_perha else 0
            ft_mai.append({
                "DBH_क्लास": cls,
                "गणना_प्रति_हे": count_per_ha,
                "गणना": count_abs,
                "आयतन_घमी": round(vol, 2),
                "MAI_घमी_प्रति_वर्ष": round(vol * _mai_pct / 100.0, 2),
                "MAI_संख्या_प्रति_हे": round(count_per_ha * _mai_pct / 100.0, 2),
            })
        result["ti_dbh_mai_table"] = dbh_mai_rows + [
            {"ब्लकको_नाम": "जम्मा वन कुल", **r} for r in ft_mai
        ] if ft_mai else []

        # ── T10: DBH क्लास अनुसार AAH ──
        dbh_aah_rows = []
        for r in dbh_abs_rows:
            bname = r["ब्लकको_नाम"]
            vol = r["आयतन_घमी"]
            count_abs = r["गणना"]
            count_per_ha = _perha_lookup.get((bname, r["DBH_क्लास"]), 0)
            mai_val = vol * _mai_pct / 100.0
            mai_trees = count_per_ha * _mai_pct / 100.0
            dbh_aah_rows.append({
                "ब्लकको_नाम": bname,
                "DBH_क्लास": r["DBH_क्लास"],
                "गणना_प्रति_हे": count_per_ha,
                "गणना": count_abs,
                "आयतन_घमी": vol,
                "MAI_घमी_प्रति_वर्ष": round(mai_val, 2),
                "MAI_संख्या_प्रति_हे": round(mai_trees, 2),
                "AAH_घमी_प्रति_वर्ष": round(mai_val * _aah_mult, 2),
                "AAH_संख्या_प्रति_हे": round(mai_trees * _aah_mult, 2),
            })
        ft_aah = []
        for cls in ft_dbh_order:
            vol = ft_dbh[cls]["आयतन_घमी"]
            count_abs = ft_dbh[cls]["गणना"]
            count_per_ha = round(ft_perha[cls]["गणना_प्रति_हे"], 2) if cls in ft_perha else 0
            mai_val = vol * _mai_pct / 100.0
            mai_trees = count_per_ha * _mai_pct / 100.0
            ft_aah.append({
                "DBH_क्लास": cls,
                "गणना_प्रति_हे": count_per_ha,
                "गणना": count_abs,
                "आयतन_घमी": round(vol, 2),
                "MAI_घमी_प्रति_वर्ष": round(mai_val, 2),
                "MAI_संख्या_प्रति_हे": round(mai_trees, 2),
                "AAH_घमी_प्रति_वर्ष": round(mai_val * _aah_mult, 2),
                "AAH_संख्या_प्रति_हे": round(mai_trees * _aah_mult, 2),
            })
        result["ti_dbh_aah_table"] = dbh_aah_rows + [
            {"ब्लकको_नाम": "जम्मा वन कुल", **r} for r in ft_aah
        ] if ft_aah else []

    # ── T11: प्रजाति संरचना (स्थानीय नाम) ──
    comp_abs = fi_data.get("ti_species_composition_absolute", {})
    if comp_abs:
        total_vol = sum(v for v in comp_abs.values() if isinstance(v, (int, float)))
        result["ti_species_composition_table"] = [
            {
                "प्रजातिको_नाम": sp,
                "कुल_आयतन_घमी": round(vol, 2),
                "प्रतिशत": round(vol / total_vol * 100, 2) if total_vol > 0 else 0,
            }
            for sp, vol in sorted(comp_abs.items(), key=lambda x: x[1], reverse=True)
        ]

    # ── T12: ब्लक अनुसार उत्पादनसिल संचिती ──
    if ti_block_rows:
        result["ti_block_productivity_table"] = [
            {
                "ब्लकको_नाम": r["block_name"],
                "क्षेत्रफल_हे": round(block_areas.get(r["block_name"], 0), 4),
                "जम्मा_मौज्दात_घमी": r.get("total_growing_stock_m3_per_ha", 0),
                "प्रति_हे_मौज्दात_घमी": round(
                    r.get("total_growing_stock_m3_per_ha", 0) / max(block_areas.get(r["block_name"], 1), 0.01), 2),
                "MAI_घमी_प्रति_वर्ष": r.get("mai_total_m3_per_ha", 0),
                "AAH_घमी_प्रति_वर्ष": r.get("aah_total_m3_per_ha", 0),
            }
            for r in ti_block_rows
        ] + [{
            "ब्लकको_नाम": "जम्मा",
            "क्षेत्रफल_हे": round(total_area, 4),
            "जम्मा_मौज्दात_घमी": ft.get("total_growing_stock_m3_per_ha", 0),
            "प्रति_हे_मौज्दात_घमी": round(
                ft.get("total_growing_stock_m3_per_ha", 0) / max(total_area, 0.01), 2),
            "MAI_घमी_प्रति_वर्ष": ft.get("mai_total_m3_per_ha", 0),
            "AAH_घमी_प्रति_वर्ष": ft.get("aah_total_m3_per_ha", 0),
        }]

    # ── T13: आर्थिक मूल्याङ्कन ──
    # Default rates (NPR)
    _TIMBER_RATE = 2500
    _FUELWOOD_RATE = 1000
    _CARBON_RATE = 3000
    if ti_block_rows:
        econ_rows = []
        gt_timber_val = gt_fuel_val = gt_carbon_val = 0.0
        for r in ti_block_rows:
            bn = r["block_name"]
            area = block_areas.get(bn, 0)
            timber_vol = r.get("pole_timber_m3_per_ha", 0) + r.get("tree_timber_m3_per_ha", 0)
            fuel_vol = r.get("pole_firewood_m3_per_ha", 0) + r.get("tree_firewood_m3_per_ha", 0)
            co2 = r.get("co2_equivalent_tco2_per_ha", 0)
            t_val = round(timber_vol * _TIMBER_RATE, 2)
            f_val = round(fuel_vol * _FUELWOOD_RATE, 2)
            c_val = round(co2 * _CARBON_RATE, 2)
            econ_rows.append({
                "ब्लकको_नाम": bn,
                "उत्पादनसिल_संचिती_घमी": r.get("total_growing_stock_m3_per_ha", 0),
                "काठ_दर_रु": _TIMBER_RATE,
                "काठ_मूल्य_रु": t_val,
                "दाउरा_दर_रु": _FUELWOOD_RATE,
                "दाउरा_मूल्य_रु": f_val,
                "कार्बन_दर_रु": _CARBON_RATE,
                "कार्बन_मूल्य_रु": c_val,
                "जम्मा_मूल्य_रु": round(t_val + f_val + c_val, 2),
            })
            gt_timber_val += t_val
            gt_fuel_val += f_val
            gt_carbon_val += c_val
        result["ti_economic_valuation_table"] = econ_rows + [{
            "ब्लकको_नाम": "जम्मा",
            "उत्पादनसिल_संचिती_घमी": round(sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows), 2),
            "काठ_दर_रु": _TIMBER_RATE,
            "काठ_मूल्य_रु": round(gt_timber_val, 2),
            "दाउरा_दर_रु": _FUELWOOD_RATE,
            "दाउरा_मूल्य_रु": round(gt_fuel_val, 2),
            "कार्बन_दर_रु": _CARBON_RATE,
            "कार्बन_मूल्य_रु": round(gt_carbon_val, 2),
            "जम्मा_मूल्य_रु": round(gt_timber_val + gt_fuel_val + gt_carbon_val, 2),
        }]

    # ── T14: दिगोपन सूचकांक ──
    if ti_block_rows:
        sus_rows = []
        for r in ti_block_rows:
            bn = r["block_name"]
            area = block_areas.get(bn, 0) or 1
            gs = r.get("total_growing_stock_m3_per_ha", 0)
            mai_val = r.get("mai_total_m3_per_ha", 0)
            aah_val = r.get("aah_total_m3_per_ha", 0)
            si = round((aah_val / gs * 100), 2) if gs > 0 else 0
            hp = round((aah_val / mai_val * 100), 1) if mai_val > 0 else 0
            gs_per_ha = round(gs / area, 2) if area > 0 else 0
            regen_cond = r.get("regeneration_condition", "—")
            forest_cond = r.get("forest_condition", "—")
            sus_rows.append({
                "ब्लकको_नाम": bn,
                "दिगोपन_सूचकांक_SI_प्रतिशत": si,
                "कटान_दबाव_HP_प्रतिशत": hp,
                "उत्पादनसिल_संचिती_प्रति_हे_घमी": gs_per_ha,
                "MAI_प्रतिशत": r.get("mai_percent", 0),
                "AAH_घमी_प्रति_वर्ष": aah_val,
                "पुनरोत्पादन_अवस्था": regen_cond,
                "वन_अवस्था": forest_cond,
            })

        if sus_rows:
            gs_t = sum(r.get("total_growing_stock_m3_per_ha", 0) for r in ti_block_rows)
            mai_t = sum(r.get("mai_total_m3_per_ha", 0) for r in ti_block_rows)
            aah_t = sum(r.get("aah_total_m3_per_ha", 0) for r in ti_block_rows)
            si_t = round((aah_t / gs_t * 100), 2) if gs_t > 0 else 0
            hp_t = round((aah_t / mai_t * 100), 1) if mai_t > 0 else 0
            gs_t_per_ha = round(gs_t / total_area, 2) if total_area > 0 else 0
            sus_rows.append({
                "ब्लकको_नाम": "जम्मा",
                "दिगोपन_सूचकांक_SI_प्रतिशत": si_t,
                "कटान_दबाव_HP_प्रतिशत": hp_t,
                "उत्पादनसिल_संचिती_प्रति_हे_घमी": gs_t_per_ha,
                "MAI_प्रतिशत": round(mai_t / gs_t * 100, 1) if gs_t > 0 else 0,
                "AAH_घमी_प्रति_वर्ष": round(aah_t, 2),
                "पुनरोत्पादन_अवस्था": "—",
                "वन_अवस्था": "—",
            })
            result["ti_sustainability_table"] = sus_rows

    return result


# ── Sub-Areas Detail ──

_CATEGORY_NP = {
    "protected": "संरक्षित",
    "private_land": "निजी जग्गा",
    "plantation": "वृक्षरोपण",
    "pro_poor": "विपन्न",
    "religious": "धार्मिक",
    "biodiversity": "जैविक विविधता",
    "tourist": "पर्यटक",
    "office": "कार्यालय",
    "agroforestry": "कृषि वन",
    "tree_strata": "रूख स्तर",
    "water_hole": "पानीको मुहान",
    "wildlife_corridor": "वन्यजन्तु करिडोर",
}


def _fetch_sub_areas_detail(db: Session, calculation_id: str) -> List[Dict[str, Any]]:
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.result_data:
        return []
    rd = calc.result_data

    sub_areas = rd.get("sub_areas", [])
    blocks = rd.get("blocks", [])
    block_map = {}
    for b in blocks:
        bid = b.get("block_id") or b.get("blockId")
        if bid:
            block_map[str(bid)] = b.get("block_name") or b.get("blockName") or ""

    result = []
    for sa in sub_areas:
        cat_np = _CATEGORY_NP.get(sa.get("category", ""), sa.get("category", ""))
        bid = sa.get("blockId") or sa.get("block_id")
        block_name = block_map.get(str(bid), "—") if bid else "—"
        status = "बहिष्कृत" if sa.get("isExcluded", sa.get("is_excluded", False)) else "समावेश"
        result.append({
            "उपक्षेत्रको_नाम": sa.get("name", ""),
            "प्रकार": cat_np,
            "क्षेत्रफल_हे": sa.get("area_hectares", 0),
            "सम्बन्धित_ब्लक": block_name,
            "स्थिति": status,
        })

    return result


def _fetch_block_area_detail_merged(db: Session, calculation_id: str) -> List[Dict[str, Any]]:
    from app.services.tree_cover_analysis import calculate_block_area_details

    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.result_data:
        return []
    rd = calc.result_data
    blocks = rd.get("blocks", [])
    sub_areas = rd.get("sub_areas", [])
    if not blocks:
        return []

    details = calculate_block_area_details(db, blocks, sub_areas)

    result = []
    grand = {
        "total_area_ha": 0.0, "tree_cover_area_ha": 0.0,
        "other_landcover_area_ha": 0.0, "protected_area_ha": 0.0,
        "private_land_area_ha": 0.0, "effective_area_ha": 0.0,
        "official_area_ha": 0.0,
    }
    for d in details:
        excluded = (d["protected_area_ha"] or 0) + (d["private_land_area_ha"] or 0)
        official = (d["official_area_ha"] or 0)
        effective = (d["effective_area_ha"] or 0)
        result.append({
            "ब्लकको_नाम": d["block_name"],
            "कुल_क्षेत्रफल_हे": round(d["total_area_ha"], 4),
            "रूखले_ढाकेको_हे": round(d["tree_cover_area_ha"], 4),
            "अन्यले_ढाकेको_हे": round(d["other_landcover_area_ha"], 4),
            "संरक्षित_क्षेत्र_हे": round(d["protected_area_ha"], 4),
            "निजि_आवादी_हे": round(d["private_land_area_ha"], 4),
            "बनश्रोत_अप्रभावित_क्षेत्र_हे": round(excluded, 4),
            "हस्तान्तरीत_क्षेत्रफल": round(official, 4),
            "वन_श्रोत_प्रभावित_क्षेत्रफल": round(effective, 4),
        })
        for k in grand:
            grand[k] += d.get(k, 0) or 0

    g_excluded = grand["protected_area_ha"] + grand["private_land_area_ha"]
    result.append({
        "ब्लकको_नाम": "जम्मा",
        "कुल_क्षेत्रफल_हे": round(grand["total_area_ha"], 4),
        "रूखले_ढाकेको_हे": round(grand["tree_cover_area_ha"], 4),
        "अन्यले_ढाकेको_हे": round(grand["other_landcover_area_ha"], 4),
        "संरक्षित_क्षेत्र_हे": round(grand["protected_area_ha"], 4),
        "निजि_आवादी_हे": round(grand["private_land_area_ha"], 4),
        "बनश्रोत_अप्रभावित_क्षेत्र_हे": round(g_excluded, 4),
        "हस्तान्तरीत_क्षेत्रफल": round(grand["official_area_ha"], 4),
        "वन_श्रोत_प्रभावित_क्षेत्रफल": round(grand["effective_area_ha"], 4),
    })

    return result


# ─────────────────────────────────────────────────────────
# Compartment data (5 tables, 3-state logic)
# ─────────────────────────────────────────────────────────

_DBH_CLASS_RANGES: List[tuple] = [
    ("१०-२० से.मी.", 10, 20),
    ("२०-३० से.मी.", 20, 30),
    ("३०-४० से.मी.", 30, 40),
    ("४०-५० से.मी.", 40, 50),
    ("५०-६० से.मी.", 50, 60),
    (">६० से.मी.", 60, 999),
]


def _classify_dbh_np(dia_cm: Optional[float]) -> Optional[str]:
    if dia_cm is None:
        return None
    for label, lo, hi in _DBH_CLASS_RANGES:
        if lo <= dia_cm < hi:
            return label
    return ">६० से.मी."


def _fetch_compartment_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    from app.models.forest_block import ForestBlock
    from app.models.inventory import InventoryTree, InventoryCalculation
    from sqlalchemy import func as sa_func
    from collections import defaultdict

    cid = str(calculation_id)
    _N = "\u2014"  # em-dash for null cells

    # ── Step 1: Fetch all compartments/sub-compartments ──
    compartments = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == cid,
        ForestBlock.is_compartment == True
    ).order_by(
        ForestBlock.parent_block_id, ForestBlock.division_level, ForestBlock.display_order
    ).all()

    if not compartments:
        return {
            "compartment_message": "यस सामुदायिक वनमा कुनै पनि कम्पाृ्टमेन्ट "
                                   "वा सव कम्पाृ्टमेन्ट तयार गरिएको छैन",
            "compartment_summary": [],
            "compartment_detail": [],
            "compartment_species_composition": [],
            "compartment_area_breakdown": [],
            "compartment_dbh_distribution": [],
        }

    # Parent block name map
    parent_ids = [str(c.parent_block_id) for c in compartments if c.parent_block_id]
    parent_blocks = {}
    if parent_ids:
        from uuid import UUID
        for pb in db.query(ForestBlock).filter(
                ForestBlock.id.in_([UUID(p) for p in set(parent_ids)])
        ).all():
            parent_blocks[str(pb.id)] = pb.name

    # ── Step 2: Check if any trees exist ──
    tree_count = db.query(sa_func.count(InventoryTree.id)).select_from(InventoryTree).join(
        InventoryCalculation,
        InventoryTree.inventory_calculation_id == InventoryCalculation.id
    ).filter(InventoryCalculation.calculation_id == cid).scalar() or 0

    # ── Helper: build State B rows (identity + area only) ──
    def _state_b_rows():
        bgroup: Dict[str, dict] = {}
        for c in compartments:
            pid = str(c.parent_block_id) if c.parent_block_id else ""
            if pid not in bgroup:
                bgroup[pid] = {"name": parent_blocks.get(pid, pid),
                               "comp": 0, "sub": 0, "area": 0.0}
            bg = bgroup[pid]
            if c.division_level == 1:
                bg["comp"] += 1
            else:
                bg["sub"] += 1
            bg["area"] += (c.area_hectares or 0)

        summary = []
        for pid in sorted(bgroup):
            bg = bgroup[pid]
            summary.append({
                "ब्लकको_नाम": bg["name"],
                "कम्पार्टमेन्ट_संख्या": bg["comp"],
                "उपकम्पार्टमेन्ट_संख्या": bg["sub"],
                "कम्पार्टमेन्ट_क्षेत्रफल_हे": round(bg["area"], 4),
                "जम्मा_रूख_संख्या": _N,
                "जम्मा_काठ_मात्रा_m3": _N,
                "जम्मा_दाउरा_मात्रा_m3": _N,
            })
        if len(summary) > 1:
            summary.append({
                "ब्लकको_नाम": "जम्मा",
                "कम्पार्टमेन्ट_संख्या": sum(r["कम्पार्टमेन्ट_संख्या"] for r in summary),
                "उपकम्पार्टमेन्ट_संख्या": sum(r["उपकम्पार्टमेन्ट_संख्या"] for r in summary),
                "कम्पार्टमेन्ट_क्षेत्रफल_हे": round(
                    sum(r["कम्पार्टमेन्ट_क्षेत्रफल_हे"] for r in summary), 4),
                "जम्मा_रूख_संख्या": _N,
                "जम्मा_काठ_मात्रा_m3": _N,
                "जम्मा_दाउरा_मात्रा_m3": _N,
            })

        detail = []
        for c in compartments:
            pid = str(c.parent_block_id) if c.parent_block_id else ""
            detail.append({
                "ब्लकको_नाम": parent_blocks.get(pid, ""),
                "कोड": c.compartment_code or "",
                "नाम": c.name,
                "स्तर": "कम्पार्टमेन्ट" if c.division_level == 1 else "उप-कम्पार्टमेन्ट",
                "क्षेत्रफल_हे": round(c.area_hectares or 0, 4),
                "रूख_संख्या": _N,
                "काठ_मात्रा_m3": _N,
                "दाउरा_मात्रा_m3": _N,
                "स्थिति": "लक" if c.is_locked else "खुला",
            })

        comp_only = [c for c in compartments if c.division_level == 1]
        area_breakdown = []
        for c in comp_only:
            pid = str(c.parent_block_id) if c.parent_block_id else ""
            children = [sc for sc in compartments
                        if str(sc.parent_block_id) == str(c.id)]
            cnames = ", ".join(sc.name for sc in children)
            area_breakdown.append({
                "ब्लकको_नाम": parent_blocks.get(pid, ""),
                "कम्पार्टमेन्ट": c.name,
                "क्षेत्रफल_हे": round(c.area_hectares or 0, 4),
                "उप_कम्पार्टमेन्ट_संख्या": len(children),
                "उप_कम्पार्टमेन्टहरू": cnames if cnames else _N,
            })

        return summary, detail, area_breakdown

    if tree_count == 0:
        s, d, a = _state_b_rows()
        return {
            "compartment_message": "",
            "compartment_summary": s,
            "compartment_detail": d,
            "compartment_species_composition": [],
            "compartment_area_breakdown": a,
            "compartment_dbh_distribution": [],
        }

    # ── State C: full data with spatial tree-to-compartment assignment ──
    sql = text("""
        WITH tree_comp AS (
            SELECT DISTINCT ON (t.id)
                t.id,
                t.species,
                t.local_name,
                t.stem_volume,
                t.branch_volume,
                t.dia_cm,
                t.block_id,
                comp.id AS compartment_id,
                comp.name AS compartment_name,
                comp.compartment_code,
                comp.division_level,
                comp.parent_block_id
            FROM inventory_trees t
            JOIN inventory_calculations ic ON t.inventory_calculation_id = ic.id
            LEFT JOIN forest_blocks comp ON
                comp.calculation_id = ic.calculation_id
                AND comp.is_compartment = TRUE
                AND ST_Within(t.location::geometry, comp.geometry)
            WHERE ic.calculation_id = :calc_id
            ORDER BY t.id, comp.division_level DESC NULLS LAST
        )
        SELECT
            tc.*,
            parent.name AS parent_block_name
        FROM tree_comp tc
        LEFT JOIN forest_blocks parent ON tc.parent_block_id = parent.id
    """)
    rows = db.execute(sql, {"calc_id": cid}).fetchall()

    # Group trees by compartment_id
    comp_trees: Dict[str, list] = defaultdict(list)
    unassigned: list = []
    for r in rows:
        d = {
            "species": r.species,
            "local_name": r.local_name or "",
            "stem_volume": r.stem_volume or 0,
            "branch_volume": r.branch_volume or 0,
            "dia_cm": r.dia_cm,
        }
        ccid = str(r.compartment_id) if r.compartment_id else None
        if ccid:
            comp_trees[ccid].append(d)
        else:
            unassigned.append(d)

    # ── Summary: group compartments by parent block ──
    bgroup: Dict[str, dict] = {}
    for c in compartments:
        pid = str(c.parent_block_id) if c.parent_block_id else ""
        if pid not in bgroup:
            bgroup[pid] = {"name": parent_blocks.get(pid, pid),
                           "comp": 0, "sub": 0, "area": 0.0,
                           "trees": 0, "timber": 0.0, "fuelwood": 0.0}
        bg = bgroup[pid]
        if c.division_level == 1:
            bg["comp"] += 1
        else:
            bg["sub"] += 1
        bg["area"] += (c.area_hectares or 0)
        for t in comp_trees.get(str(c.id), []):
            bg["trees"] += 1
            bg["timber"] += t["stem_volume"]
            bg["fuelwood"] += t["branch_volume"]

    summary = []
    for pid in sorted(bgroup):
        bg = bgroup[pid]
        summary.append({
            "ब्लकको_नाम": bg["name"],
            "कम्पार्टमेन्ट_संख्या": bg["comp"],
            "उपकम्पार्टमेन्ट_संख्या": bg["sub"],
            "कम्पार्टमेन्ट_क्षेत्रफल_हे": round(bg["area"], 4),
            "जम्मा_रूख_संख्या": bg["trees"],
            "जम्मा_काठ_मात्रा_m3": round(bg["timber"], 4),
            "जम्मा_दाउरा_मात्रा_m3": round(bg["fuelwood"], 4),
        })
    if unassigned:
        ut = unassigned
        summary.append({
            "ब्लकको_नाम": "कम्पार्टमेन्ट बाहिर",
            "कम्पार्टमेन्ट_संख्या": _N,
            "उपकम्पार्टमेन्ट_संख्या": _N,
            "कम्पार्टमेन्ट_क्षेत्रफल_हे": _N,
            "जम्मा_रूख_संख्या": len(ut),
            "जम्मा_काठ_मात्रा_m3": round(sum(t["stem_volume"] for t in ut), 4),
            "जम्मा_दाउरा_मात्रा_m3": round(sum(t["branch_volume"] for t in ut), 4),
        })
    if len(summary) > 1:
        total_trees = sum(r["जम्मा_रूख_संख्या"]
                          for r in summary
                          if isinstance(r["जम्मा_रूख_संख्या"], (int, float)))
        total_timber = sum(r["जम्मा_काठ_मात्रा_m3"]
                          for r in summary
                          if isinstance(r["जम्मा_काठ_मात्रा_m3"], (int, float)))
        total_fuelwood = sum(r["जम्मा_दाउरा_मात्रा_m3"]
                            for r in summary
                            if isinstance(r["जम्मा_दाउरा_मात्रा_m3"], (int, float)))
        total_comp = sum(r["कम्पार्टमेन्ट_संख्या"]
                        for r in summary
                        if isinstance(r["कम्पार्टमेन्ट_संख्या"], int))
        total_sub = sum(r["उपकम्पार्टमेन्ट_संख्या"]
                       for r in summary
                       if isinstance(r["उपकम्पार्टमेन्ट_संख्या"], int))
        total_area = sum(r["कम्पार्टमेन्ट_क्षेत्रफल_हे"]
                        for r in summary
                        if isinstance(r["कम्पार्टमेन्ट_क्षेत्रफल_हे"], (int, float)))
        summary.insert(0, {
            "ब्लकको_नाम": "जम्मा",
            "कम्पार्टमेन्ट_संख्या": total_comp,
            "उपकम्पार्टमेन्ट_संख्या": total_sub,
            "कम्पार्टमेन्ट_क्षेत्रफल_हे": round(total_area, 4),
            "जम्मा_रूख_संख्या": total_trees,
            "जम्मा_काठ_मात्रा_m3": round(total_timber, 4),
            "जम्मा_दाउरा_मात्रा_m3": round(total_fuelwood, 4),
        })

    # ── Detail: one row per compartment ──
    detail = []
    for c in compartments:
        pid = str(c.parent_block_id) if c.parent_block_id else ""
        ct = comp_trees.get(str(c.id), [])
        detail.append({
            "ब्लकको_नाम": parent_blocks.get(pid, ""),
            "कोड": c.compartment_code or "",
            "नाम": c.name,
            "स्तर": "कम्पार्टमेन्ट" if c.division_level == 1 else "उप-कम्पार्टमेन्ट",
            "क्षेत्रफल_हे": round(c.area_hectares or 0, 4),
            "रूख_संख्या": len(ct),
            "काठ_मात्रा_m3": round(sum(t["stem_volume"] for t in ct), 4),
            "दाउरा_मात्रा_m3": round(sum(t["branch_volume"] for t in ct), 4),
            "स्थिति": "लक" if c.is_locked else "खुला",
        })
    if unassigned:
        detail.append({
            "ब्लकको_नाम": "",
            "कोड": "",
            "नाम": "कम्पार्टमेन्ट बाहिर",
            "स्तर": _N,
            "क्षेत्रफल_हे": _N,
            "रूख_संख्या": len(unassigned),
            "काठ_मात्रा_m3": round(sum(t["stem_volume"] for t in unassigned), 4),
            "दाउरा_मात्रा_m3": round(sum(t["branch_volume"] for t in unassigned), 4),
            "स्थिति": _N,
        })

    # ── Species composition ──
    sp_data = defaultdict(lambda: {"count": 0, "timber": 0.0, "fuelwood": 0.0})
    for ccid, trees in comp_trees.items():
        comp_obj = next((c for c in compartments if str(c.id) == ccid), None)
        cname = comp_obj.name if comp_obj else ccid
        pid = str(comp_obj.parent_block_id) if comp_obj and comp_obj.parent_block_id else ""
        bname = parent_blocks.get(pid, "")
        for t in trees:
            key = (bname, cname, t["species"], t["local_name"])
            sp_data[key]["count"] += 1
            sp_data[key]["timber"] += t["stem_volume"]
            sp_data[key]["fuelwood"] += t["branch_volume"]
    for t in unassigned:
        key = ("", "कम्पार्टमेन्ट बाहिर", t["species"], t["local_name"])
        sp_data[key]["count"] += 1
        sp_data[key]["timber"] += t["stem_volume"]
        sp_data[key]["fuelwood"] += t["branch_volume"]

    species_rows = []
    for (bname, cname, sci, loc), sd in sorted(sp_data.items()):
        species_rows.append({
            "ब्लकको_नाम": bname,
            "कम्पार्टमेन्ट": cname,
            "प्रजाति_वैज्ञानिक": sci,
            "प्रजाति_स्थानीय": loc or _N,
            "रूख_संख्या": sd["count"],
            "काठ_मात्रा_m3": round(sd["timber"], 4),
            "दाउरा_मात्रा_m3": round(sd["fuelwood"], 4),
            "जम्मा_मात्रा_m3": round(sd["timber"] + sd["fuelwood"], 4),
        })

    # ── DBH class distribution ──
    dbh_data = defaultdict(lambda: {"count": 0, "timber": 0.0, "fuelwood": 0.0})
    for ccid, trees in comp_trees.items():
        comp_obj = next((c for c in compartments if str(c.id) == ccid), None)
        cname = comp_obj.name if comp_obj else ccid
        pid = str(comp_obj.parent_block_id) if comp_obj and comp_obj.parent_block_id else ""
        bname = parent_blocks.get(pid, "")
        for t in trees:
            dlabel = _classify_dbh_np(t.get("dia_cm"))
            if dlabel:
                key = (bname, cname, dlabel)
                dbh_data[key]["count"] += 1
                dbh_data[key]["timber"] += t["stem_volume"]
                dbh_data[key]["fuelwood"] += t["branch_volume"]
    for t in unassigned:
        dlabel = _classify_dbh_np(t.get("dia_cm"))
        if dlabel:
            key = ("", "कम्पार्टमेन्ट बाहिर", dlabel)
            dbh_data[key]["count"] += 1
            dbh_data[key]["timber"] += t["stem_volume"]
            dbh_data[key]["fuelwood"] += t["branch_volume"]

    dbh_rows = []
    for (bname, cname, dlabel), dd in sorted(dbh_data.items()):
        dbh_rows.append({
            "ब्लकको_नाम": bname,
            "कम्पार्टमेन्ट": cname,
            "डीबीएच_वर्ग": dlabel,
            "रूख_संख्या": dd["count"],
            "काठ_मात्रा_m3": round(dd["timber"], 4),
            "दाउरा_मात्रा_m3": round(dd["fuelwood"], 4),
        })

    # ── Area breakdown ──
    comp_only = [c for c in compartments if c.division_level == 1]
    area_breakdown = []
    for c in comp_only:
        pid = str(c.parent_block_id) if c.parent_block_id else ""
        children = [sc for sc in compartments
                    if str(sc.parent_block_id) == str(c.id)]
        cnames = ", ".join(sc.name for sc in children)
        area_breakdown.append({
            "ब्लकको_नाम": parent_blocks.get(pid, ""),
            "कम्पार्टमेन्ट": c.name,
            "क्षेत्रफल_हे": round(c.area_hectares or 0, 4),
            "उप_कम्पार्टमेन्ट_संख्या": len(children),
            "उप_कम्पार्टमेन्टहरू": cnames if cnames else _N,
        })

    return {
        "compartment_message": "",
        "compartment_summary": summary,
        "compartment_detail": detail,
        "compartment_species_composition": species_rows,
        "compartment_area_breakdown": area_breakdown,
        "compartment_dbh_distribution": dbh_rows,
    }


def _collect_yearly_activities_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Collect 10-year plan data from yearly activities for OP document consumption.

    Returns structured dicts for year-wise summaries, activity×year matrix,
    program-wise breakdown, and chart data.
    """
    activities = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.calculation_id == calculation_id
    ).all()

    if not activities:
        return {"available": False}

    # Pre-fetch all PotentialActivity for name/program/unit lookups
    potential_ids = list(set(a.potential_activity_id for a in activities))
    potential_map = {}
    if potential_ids:
        for pa in db.query(PotentialActivity).filter(PotentialActivity.id.in_(potential_ids)).all():
            potential_map[pa.id] = pa

    # Pre-fetch all year details for all activities
    activity_ids = [a.id for a in activities]
    year_details = db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id.in_(activity_ids)
    ).order_by(ActivityYearDetail.proposed_activity_id, ActivityYearDetail.year_number).all()

    # Index year details by proposed_activity_id
    yd_by_activity: Dict[UUID, Dict[int, ActivityYearDetail]] = {}
    for yd in year_details:
        pid = yd.proposed_activity_id
        if pid not in yd_by_activity:
            yd_by_activity[pid] = {}
        yd_by_activity[pid][yd.year_number] = yd

    plan_years = list(range(1, 11))

    # ── (A) ya_year_summary: one row per year ──
    year_summary = []
    cumulative_budget = 0.0
    for y in plan_years:
        year_count = 0
        year_qty = 0.0
        year_budget = 0.0
        for act in activities:
            yd = yd_by_activity.get(act.id, {}).get(y)
            qty = float(yd.quantity) if yd and yd.quantity is not None else float(act.default_quantity or 0)
            bgt = float(yd.yearly_budget) if yd and yd.yearly_budget is not None else float(act.default_yearly_budget or 0)
            if bgt > 0 or qty > 0:
                year_count += 1
            year_qty += qty
            year_budget += bgt
        cumulative_budget += year_budget
        year_summary.append({
            "year": y,
            "activity_count": year_count,
            "total_quantity": round(year_qty, 2),
            "total_budget": round(year_budget, 2),
            "cumulative_budget": round(cumulative_budget, 2),
        })

    # ── (B) ya_plan_matrix: one row per activity, columns per year ──
    plan_matrix = []
    for act in activities:
        pa = potential_map.get(act.potential_activity_id)
        row = {
            "activity_name": pa.activities if pa else f"Activity {act.potential_activity_id}",
            "program": pa.progarms if pa else "",
            "unit": pa.unit if pa else "",
        }
        total_qty = 0.0
        total_bgt = 0.0
        for y in plan_years:
            yd = yd_by_activity.get(act.id, {}).get(y)
            qty = float(yd.quantity) if yd and yd.quantity is not None else float(act.default_quantity or 0)
            bgt = float(yd.yearly_budget) if yd and yd.yearly_budget is not None else float(act.default_yearly_budget or 0)
            row[f"year_{y}_qty"] = round(qty, 2)
            row[f"year_{y}_budget"] = round(bgt, 2)
            total_qty += qty
            total_bgt += bgt
        row["total_quantity"] = round(total_qty, 2)
        row["total_budget"] = round(total_bgt, 2)
        plan_matrix.append(row)

    # ── (C) ya_program_budget: grouped by program ──
    program_data: Dict[str, Dict] = {}
    for act in activities:
        pa = potential_map.get(act.potential_activity_id)
        prog = pa.progarms if pa else "Other"
        if prog not in program_data:
            program_data[prog] = {f"year_{y}_budget": 0.0 for y in plan_years}
            program_data[prog]["activity_count"] = 0
            program_data[prog]["total_budget"] = 0.0
        program_data[prog]["activity_count"] += 1
        for y in plan_years:
            yd = yd_by_activity.get(act.id, {}).get(y)
            bgt = float(yd.yearly_budget) if yd and yd.yearly_budget is not None else float(act.default_yearly_budget or 0)
            program_data[prog][f"year_{y}_budget"] += bgt
            program_data[prog]["total_budget"] += bgt
    program_budget = []
    for prog_name, pd in sorted(program_data.items()):
        row = {"program": prog_name}
        row.update(pd)
        row["total_budget"] = round(row["total_budget"], 2)
        for y in plan_years:
            row[f"year_{y}_budget"] = round(row[f"year_{y}_budget"], 2)
        program_budget.append(row)

    # ── (D) ya_total_budget_by_year: dict year→budget ──
    total_budget_by_year = {str(y): round(ys["total_budget"], 2) for ys in year_summary}

    # ── (E) ya_total_ten_year_budget ──
    total_ten_year_budget = round(sum(ys["total_budget"] for ys in year_summary), 2)

    # ── (F) ya_program_pie_data: {program: total_budget} ──
    program_pie_data = {pb["program"]: pb["total_budget"] for pb in program_budget}

    # ── (G) ya_budget_year_trend: {year: budget} ──
    budget_year_trend = {str(y): ys["total_budget"] for ys in year_summary}

    # ── (H) ya_activity_plan_detail: one row per activity matching CSV export ──
    sa_all = db.query(ActivitySpatialAssignment).filter(
        ActivitySpatialAssignment.proposed_activity_id.in_(activity_ids)
    ).all()
    df_all = db.query(ActivityDrawnFeature).filter(
        ActivityDrawnFeature.proposed_activity_id.in_(activity_ids)
    ).all()

    block_ids = set()
    for sa in sa_all:
        if sa.block_id:
            block_ids.add(sa.block_id)
    block_map: Dict[str, str] = {}
    if block_ids:
        for b in db.query(ForestBlock).filter(ForestBlock.id.in_(list(block_ids))).all():
            block_map[str(b.id)] = b.name

    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    sub_area_names: Dict[str, str] = {}
    if calc and calc.result_data and calc.result_data.get("sub_areas"):
        for sa_entry in calc.result_data["sub_areas"]:
            sa_id = str(sa_entry.get("id", ""))
            sa_name = sa_entry.get("name", "") or ""
            sub_area_names[sa_id] = sa_name

    sa_by_activity: Dict[UUID, list] = {}
    for sa in sa_all:
        sa_by_activity.setdefault(sa.proposed_activity_id, []).append(sa)
    df_by_activity: Dict[UUID, list] = {}
    for df in df_all:
        df_by_activity.setdefault(df.proposed_activity_id, []).append(df)

    activity_plan_detail = []
    for idx, act in enumerate(activities, start=1):
        pa = potential_map.get(act.potential_activity_id)
        activity_name = pa.activities if pa else f"Activity {act.potential_activity_id}"
        program_name = pa.progarms if pa else ""
        unit_name = pa.unit if pa else ""

        qty_parts: list[str] = []
        bgt_parts: list[str] = []
        total_bgt = 0.0
        for y in plan_years:
            yd = yd_by_activity.get(act.id, {}).get(y)
            qty = float(yd.quantity) if yd and yd.quantity is not None else float(act.default_quantity or 0)
            bgt = float(yd.yearly_budget) if yd and yd.yearly_budget is not None else float(act.default_yearly_budget or 0)
            if qty > 0:
                qty_parts.append(f"Y{y}:{qty:g}")
            if bgt > 0:
                bgt_parts.append(f"Y{y}:{bgt:g}")
            total_bgt += bgt

        assignments = sa_by_activity.get(act.id, [])
        if act.assign_to_all_blocks or any(s.assignment_type == "all_blocks" for s in assignments):
            location_type = "all"
            location_details = "All Blocks"
        elif assignments:
            loc_names: list[str] = []
            has_block = False
            has_sub_area = False
            for s in assignments:
                if s.assignment_type == "block" and s.block_id:
                    has_block = True
                    loc_names.append(block_map.get(str(s.block_id), str(s.block_id)))
                elif s.assignment_type == "sub_area":
                    has_sub_area = True
                    nm = block_map.get(str(s.block_id), "")
                    if s.sub_area_id:
                        san = sub_area_names.get(str(s.sub_area_id), "")
                        if san:
                            nm = f"{nm} > {san}" if nm else san
                    loc_names.append(nm or str(s.sub_area_id))
            location_type = "blocks" if has_block else "sub_areas" if has_sub_area else "none"
            location_details = ", ".join(loc_names) if loc_names else "No specific location"
        else:
            location_type = "none"
            location_details = "No specific location"

        drawn_features_list = df_by_activity.get(act.id, [])
        feature_names = []
        for df in drawn_features_list:
            fn = (df.properties or {}).get("name", "") or (df.properties or {}).get("label", "")
            if fn:
                feature_names.append(fn)
        spatial_features = ", ".join(feature_names) if feature_names else "None"

        activity_plan_detail.append({
            "s_no": idx,
            "activity": activity_name,
            "program": program_name,
            "unit": unit_name,
            "quantity_years": ", ".join(qty_parts) if qty_parts else "None",
            "budget_years": ", ".join(bgt_parts) if bgt_parts else "None",
            "total_budget": round(total_bgt, 2),
            "location_type": location_type,
            "location_details": location_details,
            "spatial_features": spatial_features,
        })

    return {
        "available": True,
        "year_summary": year_summary,
        "plan_matrix": plan_matrix,
        "program_budget": program_budget,
        "total_budget_by_year": total_budget_by_year,
        "total_ten_year_budget": total_ten_year_budget,
        "program_pie_data": program_pie_data,
        "budget_year_trend": budget_year_trend,
        "activity_plan_detail": activity_plan_detail,
    }


def _fetch_sampling_point_locations(db: Session, calculation_id: str) -> List[Dict[str, Any]]:
    """Build per-point location table from sampling design data.

    Returns a list of dicts with Nepali keys as table headers.
    Uses cached points_data (from API) when available, falls back to on-the-fly.
    """
    from app.models.sampling import SamplingDesign
    from app.utils.number_format import format_devanagari, _ARABIC_TO_DEV
    from shapely import wkt as shapely_wkt

    designs = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id,
        SamplingDesign.points_geometry.isnot(None),
    ).all()

    if not designs:
        return []

    design = designs[0]
    cached = design.points_data or {}
    cached_points = cached.get("points") if isinstance(cached, dict) else None

    # Use cached points_data when available (includes topographic context)
    if cached_points:
        from app.utils.geospatial import extract_elevation_at_point
        points_list = []
        for pt in cached_points:
            lon = pt.get("longitude")
            lat = pt.get("latitude")
            elevation_m = pt.get("elevation_m")
            topo_ctx = pt.get("topographic_context") or pt.get("nearest_feature_name") or ""
            dist = pt.get("distance_from_boundary")

            if lon is None or lat is None:
                continue

            lon_str = f"{lon:.7f}".translate(_ARABIC_TO_DEV)
            lat_str = f"{lat:.7f}".translate(_ARABIC_TO_DEV)
            elev_str = format_devanagari(int(elevation_m), 0) if elevation_m else "-"
            dist_str = format_devanagari(round(dist, 2), 2) if dist else "-"

            points_list.append({
                "नमुना_प्लट_नं": pt.get("plot_number", ""),
                "ब्लकको_नाम": pt.get("block_name", ""),
                "क्षेत्रको_किसिम": pt.get("zone_type", "productive"),
                "देशान्तर": lon_str,
                "अक्षांश": lat_str,
                "उचाइ_मि": elev_str,
                "ईपिएसजी_कोड": "EPSG:4326",
                "नजिकको_प्राकृतिक_चिन्ह": topo_ctx,
                "वन_सिमाना_देखिको_दुरी_मि": dist_str,
            })
        return points_list

    # Fallback: compute from scratch
    from app.utils.geospatial import extract_elevation_at_point

    block_assignment = design.points_block_assignment or []

    result = db.execute(
        text("SELECT ST_AsText(points_geometry) FROM public.sampling_designs WHERE id = :id"),
        {"id": str(design.id)},
    ).first()
    if not result or not result[0]:
        return []

    multipoint = shapely_wkt.loads(result[0])

    from app.models.calculation import Calculation
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    boundary_wkt = None
    if calc:
        br = db.execute(
            text("SELECT ST_AsText(boundary_geom) FROM public.calculations WHERE id = :id"),
            {"id": calculation_id},
        ).first()
        if br:
            boundary_wkt = br[0]

    points_list = []
    for i, point in enumerate(multipoint.geoms):
        lon, lat = point.x, point.y

        block_info = next(
            (b for b in block_assignment if b.get("point_index") == i), None
        )
        block_name = (block_info or {}).get("block_name", "")
        zone_type = (block_info or {}).get("zone_type", "productive")

        elevation_m = extract_elevation_at_point(db, lon, lat)

        distance = None
        if boundary_wkt:
            try:
                boundary_geom = shapely_wkt.loads(boundary_wkt)
                distance = point.distance(boundary_geom.boundary) * 111320
            except Exception:
                pass

        lon_str = f"{lon:.7f}".translate(_ARABIC_TO_DEV)
        lat_str = f"{lat:.7f}".translate(_ARABIC_TO_DEV)
        elev_str = format_devanagari(int(elevation_m), 0) if elevation_m else "-"
        dist_str = format_devanagari(round(distance, 2), 2) if distance else "-"

        points_list.append({
            "नमुना_प्लट_नं": i + 1,
            "ब्लकको_नाम": block_name,
            "क्षेत्रको_किसिम": zone_type,
            "देशान्तर": lon_str,
            "अक्षांश": lat_str,
            "उचाइ_मि": elev_str,
            "ईपिएसजी_कोड": "EPSG:4326",
            "नजिकको_प्राकृतिक_चिन्ह": "",
            "वन_सिमाना_देखिको_दुरी_मि": dist_str,
        })

    return points_list


def _fetch_fieldbook_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    from app.utils.number_format import format_devanagari as _fmt_d

    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        return {"available": False, "total_points": 0}

    vertex_count = sum(1 for p in points if p.point_type == "vertex")
    interp_count = sum(1 for p in points if p.point_type == "interpolated")
    total = len(points)
    perimeter = sum(float(p.distance_to_next or 0) for p in points[:-1])

    elev_vals = [float(p.elevation) for p in points if p.elevation is not None]
    avg_el = sum(elev_vals) / len(elev_vals) if elev_vals else None
    min_el = min(elev_vals) if elev_vals else None
    max_el = max(elev_vals) if elev_vals else None

    # Per-block summary
    block_map: Dict[str, dict] = {}
    for p in points:
        bn = p.block_name or "Unknown"
        if bn not in block_map:
            block_map[bn] = {"block_name": bn, "vertex": 0, "interpolated": 0, "total": 0, "perimeter_m": 0.0}
        block_map[bn]["total"] += 1
        block_map[bn][p.point_type] = block_map[bn].get(p.point_type, 0) + 1
    # Compute per-block perimeter
    for i, p in enumerate(points[:-1]):
        bn = p.block_name or "Unknown"
        if bn in block_map:
            block_map[bn]["perimeter_m"] += float(p.distance_to_next or 0)
    block_rows = []
    for bn in sorted(block_map.keys()):
        b = block_map[bn]
        block_rows.append({
            "ब्लकको_नाम": b["block_name"],
            "मुख्य_बिन्दु": b["vertex"],
            "अन्तरसम्मिलित": b["interpolated"],
            "जम्मा_बिन्दु": b["total"],
            "परिधि_मि": round(b["perimeter_m"], 2),
        })

    # Per-point table with Nepali keys
    from app.utils.number_format import _ARABIC_TO_DEV as _to_dev
    point_rows = []
    for p in points:
        ele_str = _fmt_d(int(p.elevation), 0) if p.elevation else "-"
        lon_str = f"{float(p.longitude):.7f}".translate(_to_dev)
        lat_str = f"{float(p.latitude):.7f}".translate(_to_dev)
        point_rows.append({
            "बिन्दु_नं": p.point_number,
            "प्रकार": "V" if p.point_type == "vertex" else "I",
            "ब्लकको_नाम": p.block_name or "",
            "देशान्तर": lon_str,
            "अक्षांश": lat_str,
            "CRS": "EPSG:4326",
            "उचाइ_मि": ele_str,
            "अजिमुथ": f"{float(p.azimuth_to_next):.1f}" if p.azimuth_to_next else "-",
            "दुरी_मि": f"{float(p.distance_to_next):.1f}" if p.distance_to_next else "-",
        })

    result = {
        "available": True,
        "total_points": total,
        "vertex_count": vertex_count,
        "interpolated_count": interp_count,
        "perimeter_m": round(perimeter, 2),
        "avg_elevation_m": round(avg_el, 1) if avg_el else None,
        "min_elevation_m": round(min_el, 1) if min_el else None,
        "max_elevation_m": round(max_el, 1) if max_el else None,
        "points": point_rows,
        "block_summary": block_rows,
    }
    return result


def collect_all_op_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    t_start = time.time()
    import uuid
    from app.models.op_data_cache import OpDataCache
    calc_uuid = uuid.UUID(calculation_id) if isinstance(calculation_id, str) else calculation_id
    cached = db.query(OpDataCache).filter(
        OpDataCache.calculation_id == calc_uuid
    ).first()
    if cached:
        cached_data = dict(cached.data)
        # Invalidate if cache version doesn't match (schema/keys may have changed)
        if cached_data.pop("_cache_version", None) == OP_DATA_CACHE_VERSION:
            logger.info("OP_COLLECT: cache HIT for calc=%s (%.2fs)", calculation_id, time.time() - t_start)
            return cached_data

    logger.info("OP_COLLECT: cache MISS for calc=%s — starting full collection", calculation_id)
    t0 = time.time()
    raw = _collect_all_data(db, calculation_id)
    logger.info("OP_COLLECT: _collect_all_data done in %.2fs", time.time() - t0)

    # Merge user_group_landcover into user_group so all UG vars resolve from one source
    if "user_group_landcover" in raw:
        buildings_available = raw.get("user_group", {}).get("available", False)
        ug_lc = raw.pop("user_group_landcover", {})
        raw.setdefault("user_group", {})
        raw["user_group"].update(ug_lc)
        # Preserve buildings availability — don't let missing landcover overwrite
        if buildings_available:
            raw["user_group"]["available"] = True

    t1 = time.time()
    fi_data = get_field_inventory_data(db, calculation_id,
                                       base_species_data=raw.get("species"))
    logger.info("OP_COLLECT: get_field_inventory_data done in %.2fs", time.time() - t1)
    raw["field_inventory"] = fi_data

    # Compute total inventory (absolute) from per-hectare field inventory data
    t2 = time.time()
    ti_data = _compute_total_inventory(fi_data)
    logger.info("OP_COLLECT: _compute_total_inventory done in %.2fs", time.time() - t2)
    raw["field_inventory"].update(ti_data)

    t2b = time.time()
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    raw["result_data"] = calc.result_data or {} if calc else {}

    raw["blocks"]["sub_areas_detail"] = _fetch_sub_areas_detail(db, calculation_id)
    raw["blocks"]["block_area_detail_merged"] = _fetch_block_area_detail_merged(db, calculation_id)
    # T1: Block area table — merge into field_inventory for ti_ variable resolution
    raw["field_inventory"]["ti_block_area_table"] = raw["blocks"]["block_area_detail_merged"]

    raw["compartment"] = _fetch_compartment_data(db, calculation_id)

    # Yearly plan (10-year activities data)
    raw["yearly_plan"] = _collect_yearly_activities_data(db, calculation_id)

    # Fieldbook data — must be before section_generators so narration sees it
    raw["fieldbook"] = _fetch_fieldbook_data(db, calculation_id)

    # Demand-supply data for section:demand_supply_narration
    try:
        from app.services.demand_supply_service import (
            get_demand,
            get_community_forest_regular_supply,
            get_community_forest_aah_supply,
            get_private_supply,
        )
        calc_uuid = UUID(calculation_id)
        demand = get_demand(db, calc_uuid)
        cf_reg = get_community_forest_regular_supply(db, calc_uuid)
        cf_aah = get_community_forest_aah_supply(db, calc_uuid)
        cf_data = {
            "firewood_bhari": cf_reg.get("firewood_bhari", 0),
            "grass_bhari": cf_reg.get("grass_bhari", 0),
            "bedding_bhari": cf_reg.get("bedding_bhari", 0),
            "timber_cft": cf_aah.get("timber_cft", 0),
            "poles_count": cf_aah.get("poles_count", 0),
        }
        pvt = get_private_supply(db, calc_uuid)
        total_supply = {
            k: (cf_data.get(k, 0) or 0) + (pvt.get(k, 0) or 0)
            for k in ("firewood_bhari", "grass_bhari", "bedding_bhari", "timber_cft", "poles_count")
        }
        deficit = {
            k: total_supply.get(k, 0) - (demand.get(k, 0) or 0)
            for k in ("firewood_bhari", "grass_bhari", "bedding_bhari", "timber_cft", "poles_count")
        }
        raw["demand_supply"] = {
            "demand": demand,
            "supply_cf_regular": cf_reg,
            "supply_cf_aah": cf_aah,
            "supply_private": pvt,
            "total_supply": total_supply,
            "deficit": deficit,
        }
    except Exception as exc:
        logger.warning("OP_COLLECT: demand-supply collection failed: %s", exc)
        raw["demand_supply"] = {}

    t3 = time.time()
    raw["section_generators"] = collect_section_content(raw)
    logger.info("OP_COLLECT: block+compartment+act+fieldbook+sections done in %.2fs", time.time() - t2b)

    # Sampling: Nepali-keyed variants for inline table rendering
    sampling_data = raw.get("sampling", {})
    if sampling_data.get("available"):
        sampling_data["sampling_point_locations"] = _fetch_sampling_point_locations(
            db, calculation_id
        )

        # Transform blocks_info keys to Nepali for {{sampling_block_summary}}
        designs = sampling_data.get("designs", [])
        if designs:
            bi = designs[0].get("blocks_info") or []
            nepali_rows = []
            for b in bi:
                nepali_rows.append({
                    "ब्लकको_नाम": b.get("block_name", ""),
                    "क्षेत्रफल_हे": b.get("block_area_hectares", 0),
                    "पहुँचयुक्त_वन_हे": b.get("accessible_forest_area_ha", ""),
                    "संरक्षित": b.get("is_protected", ""),
                    "नमुना_प्लट_संख्या": b.get("samples_generated", 0),
                    "प्लट_दुरी_मि": b.get("grid_spacing_meters", ""),
                    "वास्तविक_इन्टेन्सिटी_प्रतिशत": b.get("actual_intensity_percent", ""),
                    "स्याम्पलिङ_विधि": b.get("sampling_method", ""),
                })
            sampling_data["sampling_block_summary"] = nepali_rows

    from app.models.op_data_cache import OpDataCache
    existing = db.query(OpDataCache).filter(
        OpDataCache.calculation_id == calc_uuid
    ).first()
    raw["_cache_version"] = OP_DATA_CACHE_VERSION
    if existing:
        existing.data = raw
        existing.updated_at = datetime.utcnow()
    else:
        db.add(OpDataCache(calculation_id=calc_uuid, data=raw))
    db.commit()
    logger.info(
        "OP_COLLECT: total=%.2fs calc=%s cache=%s",
        time.time() - t_start, calculation_id, "WRITTEN",
    )
    return raw
