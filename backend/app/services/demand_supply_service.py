"""
Demand and Supply Service
Computes forest product demand vs. supply from multiple sources
"""
from typing import Dict, Optional
from sqlalchemy.orm import Session
from uuid import UUID
from decimal import Decimal
import logging

from ..models.calculation import Calculation
from ..models.field_inventory import (
    FieldInventoryCalculation,
    FieldInventoryBlockSummary
)
from ..models.household_information import HouseholdInformation

logger = logging.getLogger(__name__)

# Conversion constants
BHARI_KG = 30  # 1 bhari = 30 kg
CFT_PER_M3 = 35.315  # 1 m³ = 35.315 cubic feet
PER_100SQM_TO_HA = 100  # 100 sqm → 1 ha multiplier
WOOD_DENSITY_KG_PER_M3 = 670  # avg wood density for Nepal

# Private land assumptions
PRIVATE_MAI_PERCENT = 3.0  # Tree cover MAI%
PRIVATE_SHRUB_MAI_PERCENT = 1.5  # Shrubland MAI% (half)
PRIVATE_AAH_MULTIPLIER = 60.0  # AAH multiplier % (moderate)
PRIVATE_TIMBER_FRACTION = 0.60  # 60% of growing stock = timber
PRIVATE_FIREWOOD_FRACTION = 0.40  # 40% = firewood
AVG_POLE_VOLUME_M3 = 0.05  # avg volume per pole
CROPLAND_GRASS_YIELD_KG_HA = 12000  # kg/ha/yr agricultural residue
GRASSLAND_BEDDING_YIELD_KG_HA = 8000  # kg/ha/yr for grass+beding


def _fetch_block_areas(db: Session, calculation_id: UUID) -> Dict[str, float]:
    """Read block areas from calculation result_data"""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.result_data:
        return {}
    blocks = calc.result_data.get("blocks", [])
    return {
        b.get("block_name", ""): float(b.get("area_hectares", 0))
        for b in blocks if b.get("block_name")
    }


def get_demand(db: Session, calculation_id: UUID) -> Dict[str, Optional[float]]:
    """Aggregate household demand from survey data"""
    households = db.query(HouseholdInformation).filter(
        HouseholdInformation.calculation_id == calculation_id
    ).all()

    if not households:
        return {
            "firewood_bhari": 0,
            "grass_bhari": 0,
            "bedding_bhari": 0,
            "timber_cft": 0,
            "poles_count": 0,
        }

    return {
        "firewood_bhari": float(sum(h.firewood_demand_bhari or 0 for h in households)),
        "grass_bhari": float(sum(h.grass_demand_bhari or 0 for h in households)),
        "bedding_bhari": float(sum(h.bedding_demand_bhari or 0 for h in households)),
        "timber_cft": float(sum(h.timber_demand_cft or 0 for h in households)),
        "poles_count": int(sum(h.pole_demand or 0 for h in households)),
    }


def get_community_forest_regular_supply(
    db: Session, calculation_id: UUID
) -> Dict[str, Optional[float]]:
    """
    Compute regular collection supply from community forest.
    Uses kg/100sqm → kg/ha → bhari conversion for firewood, grass, bedding.
    """
    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id
    ).first()

    if not fi:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    block_areas = _fetch_block_areas(db, calculation_id)
    if not block_areas:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    block_summaries = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == fi.id
    ).all()

    total_fw_bhari = 0.0
    total_gr_bhari = 0.0
    total_bd_bhari = 0.0

    for bs in block_summaries:
        area_ha = block_areas.get(bs.block_name, 0)
        if area_ha <= 0:
            continue

        fw_kg_ha = float(bs.firewood_kg_per_ha_per_year or 0)
        gr_kg_ha = float(bs.grass_kg_per_ha_per_year or 0)
        bd_kg_ha = float(bs.bedding_material_kg_per_ha_per_year or 0)

        total_fw_bhari += (fw_kg_ha * area_ha) / BHARI_KG
        total_gr_bhari += (gr_kg_ha * area_ha) / BHARI_KG
        total_bd_bhari += (bd_kg_ha * area_ha) / BHARI_KG

    return {
        "firewood_bhari": round(total_fw_bhari, 2),
        "grass_bhari": round(total_gr_bhari, 2),
        "bedding_bhari": round(total_bd_bhari, 2),
        "timber_cft": None,
        "poles_count": None,
    }


def get_community_forest_aah_supply(
    db: Session, calculation_id: UUID
) -> Dict[str, Optional[float]]:
    """
    Compute AAH-based harvest supply from community forest for timber and poles.
    Uses block summaries to compute MAI/AAH per block then sum.
    """
    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id
    ).first()

    if not fi:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    block_areas = _fetch_block_areas(db, calculation_id)
    if not block_areas:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    # Default AAH multipliers (moderate condition)
    AAH_GOOD = 75.0
    AAH_MODERATE = 60.0
    AAH_WEAK = 40.0

    aah_mult_map = {"Good": AAH_GOOD, "Moderate": AAH_MODERATE, "Weak": AAH_WEAK}

    block_summaries = db.query(FieldInventoryBlockSummary).filter(
        FieldInventoryBlockSummary.field_inventory_calculation_id == fi.id
    ).all()

    total_aah_m3 = 0.0
    total_poles = 0

    for bs in block_summaries:
        area_ha = block_areas.get(bs.block_name, 0)
        if area_ha <= 0:
            continue

        # MAI = growing_stock × MAI%
        mai_percent = float(bs.mai_percent or 0) / 100.0
        growing_stock = float(bs.total_growing_stock_m3_per_ha or 0)
        mai_m3_per_ha = growing_stock * mai_percent

        # AAH = MAI × multiplier (based on forest condition)
        condition = bs.forest_condition or "Moderate"
        aah_mult = aah_mult_map.get(condition, AAH_MODERATE) / 100.0
        aah_m3_per_ha = mai_m3_per_ha * aah_mult

        total_aah_m3 += aah_m3_per_ha * area_ha

        # Poles (pole_per_ha count is for the whole growing stock,
        # we use pole count as-is from the extrapolation)
        pole_count = int((bs.pole_per_ha or 0) * area_ha * mai_percent * aah_mult)
        total_poles += pole_count

    return {
        "firewood_bhari": None,
        "grass_bhari": None,
        "bedding_bhari": None,
        "timber_cft": round(total_aah_m3 * CFT_PER_M3, 2),
        "poles_count": total_poles,
    }


def _class_area(result_data: Dict, class_name: str, total_area_ha: float) -> float:
    """Get area in hectares for a land cover class from result_data percentages"""
    pcts = result_data.get("landcover_percentages", {})
    pct = float(pcts.get(class_name, 0))
    return (pct / 100.0) * total_area_ha if pct else 0.0


def _total_calc_area(result_data: Dict) -> float:
    """Sum block areas from result_data"""
    return sum(
        float(b.get("area_hectares", 0))
        for b in result_data.get("blocks", [])
    )


def get_private_supply(
    db: Session, calculation_id: UUID
) -> Dict[str, Optional[float]]:
    """
    Estimate supply from private land (user boundary, outside forest).
    Uses land cover classification data from calculation result_data.
    """
    calc = db.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    if not calc or not calc.result_data:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    rd = calc.result_data
    total_area_ha = _total_calc_area(rd)
    if total_area_ha <= 0:
        return {
            "firewood_bhari": None,
            "grass_bhari": None,
            "bedding_bhari": None,
            "timber_cft": None,
            "poles_count": None,
        }

    # Get per-class areas from landcover_percentages in result_data
    tree_cover_area_ha = _class_area(rd, "Tree cover", total_area_ha)
    shrub_area_ha = _class_area(rd, "Shrubland", total_area_ha)
    grassland_area_ha = _class_area(rd, "Grassland", total_area_ha)
    cropland_area_ha = _class_area(rd, "Cropland", total_area_ha)

    # --- Estimate tree cover growing stock ---
    # Try average from field inventory; fall back to default 120 m³/ha for Nepal
    fi = db.query(FieldInventoryCalculation).filter(
        FieldInventoryCalculation.calculation_id == calculation_id
    ).first()
    if fi:
        bs_list = db.query(FieldInventoryBlockSummary).filter(
            FieldInventoryBlockSummary.field_inventory_calculation_id == fi.id
        ).all()
        gs_vals = [float(b.total_growing_stock_m3_per_ha or 0) for b in bs_list if b.total_growing_stock_m3_per_ha]
        avg_gs = sum(gs_vals) / len(gs_vals) if gs_vals else 120.0
    else:
        avg_gs = 120.0

    tree_cover_volume_m3 = tree_cover_area_ha * avg_gs

    # --- Timber & Firewood from tree cover ---
    # Private MAI = growing_stock × MAI%
    # Private AAH = MAI × AAH_multiplier
    mai_decimal = PRIVATE_MAI_PERCENT / 100.0
    aah_decimal = PRIVATE_AAH_MULTIPLIER / 100.0

    private_mai_m3 = tree_cover_volume_m3 * mai_decimal
    private_aah_m3 = private_mai_m3 * aah_decimal

    private_timber_m3 = private_aah_m3 * PRIVATE_TIMBER_FRACTION
    private_firewood_m3 = private_aah_m3 * PRIVATE_FIREWOOD_FRACTION

    # Shrubland firewood (lower rate)
    shrub_vol_est = shrub_area_ha * 20  # assume 20 m³/ha growing stock
    shrub_mai = shrub_vol_est * (PRIVATE_SHRUB_MAI_PERCENT / 100.0)
    shrub_aah = shrub_mai * aah_decimal
    shrub_firewood_m3 = shrub_aah  # all shrub = firewood

    total_firewood_m3 = private_firewood_m3 + shrub_firewood_m3
    firewood_bhari = (total_firewood_m3 * WOOD_DENSITY_KG_PER_M3) / BHARI_KG

    # Poles from private timber
    private_poles = int((private_timber_m3) / AVG_POLE_VOLUME_M3) if private_timber_m3 > 0 else 0

    # --- Grass from cropland ---
    grass_bhari = (cropland_area_ha * CROPLAND_GRASS_YIELD_KG_HA) / BHARI_KG

    # --- Bedding from grassland ---
    bedding_bhari = (grassland_area_ha * GRASSLAND_BEDDING_YIELD_KG_HA) / BHARI_KG

    return {
        "firewood_bhari": round(firewood_bhari, 2),
        "grass_bhari": round(grass_bhari, 2),
        "bedding_bhari": round(bedding_bhari, 2),
        "timber_cft": round(private_timber_m3 * CFT_PER_M3, 2),
        "poles_count": private_poles,
    }


def build_nepali_description(
    demand: Dict,
    supply_cf_reg: Dict,
    supply_cf_aah: Dict,
    supply_pvt: Dict,
    total_supply: Dict,
    deficit: Dict,
) -> str:
    """Generate Devanagari description paragraph explaining the table"""
    fw_surplus = deficit.get("firewood_bhari", 0)
    gr_surplus = deficit.get("grass_bhari", 0)
    bd_surplus = deficit.get("bedding_bhari", 0)
    tm_surplus = deficit.get("timber_cft", 0)
    pl_surplus = deficit.get("poles_count", 0)

    def _status(val, unit_np):
        if val is None:
            return "—"
        if val > 0:
            return f"{abs(val):,.1f} {unit_np} बचत"
        elif val < 0:
            return f"{abs(val):,.1f} {unit_np} अभाव"
        return "सन्तुलित"

    desc = (
        "यस तालिकाले उपभोक्ता समूहका घरधुरीहरूको वन पैदावार माग र आपूर्ति अवस्था देखाउँदछ। "
        "मागको गणना घरधुरी सर्वेक्षण (Household Survey) का आधारमा गरिएको छ। "
        "सामुदायिक वनबाट हुने आपूर्ति दुई भागमा विभाजन गरिएको छ: "
        "(क) नियमित सङ्कलन — दाउरा, घाँस र सोतर जस्ता वर्षभरि सङ्कलन हुने सामान्य वन पैदावारहरू, "
        "जुन क्षेत्र सर्वेक्षणमा उल्लेख गरिएको प्रति १ सय वर्गमिटर वार्षिक उपज (केजी) लाई प्रति हेक्टरमा "
        "रूपान्तरण (× १००) गरी वन ब्लकको क्षेत्रफलले गुणन गरी ३० केजी = १ भारी का दरले भारीमा "
        "गणना गरिएको छ। "
        "(ख) वार्षिक स्वीकार्य कटान (AAH) — काठ र खाँवाको लागि वन अवस्था र वृद्धि दरमा आधारित दिगो उपज। "
        "निजी क्षेत्रबाट हुने आपूर्ति जमिन वर्गीकरण (Land Cover) का आधारमा अनुमान गरिएको छ। "
        f"आपूर्ति र माग बीचको अन्तर: दाउरा ({_status(fw_surplus, 'भारी')}), "
        f"घाँस ({_status(gr_surplus, 'भारी')}), "
        f"सोतर ({_status(bd_surplus, 'भारी')}), "
        f"काठ ({_status(tm_surplus, 'क्यू.फि.')}), "
        f"खाँवा ({_status(pl_surplus, 'संख्या')})."
    )
    return desc
