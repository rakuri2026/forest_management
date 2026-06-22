"""
Data collector for report generation
Gathers all relevant data from database for each report section
"""
import json
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.calculation import Calculation
from app.models.forest_block import ForestBlock
from app.models.forest_sub_area import ForestSubArea
from app.models.inventory import InventoryCalculation, InventoryTree
from app.models.sampling import SamplingDesign
from app.models.household_information import HouseholdInformation
from app.models.forest_committee import ForestUserCommittee, AdvisoryCommittee, FinancialCommittee
from app.models.yearly_activities import ProposedYearlyActivity, ActivityYearDetail
from app.models.biodiversity import CalculationBiodiversity, BiodiversitySpecies
from app.models.user_group import UserGroupExtent, UserGroupBuilding


def _convert_decimals(obj):
    """Recursively convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def get_calculation_basic_info(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get basic calculation information"""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        return {}

    result_data = calc.result_data or {}

    # Fallback: query admin.admin_nepal for Nepali names if missing from result_data
    if not result_data.get("whole_division_n"):
        try:
            fn_query = text("""
                SELECT province_ne, division_n, subdivis_n, palika_n,
                       type_nep, ward_ne, physiography_ne, juridiction_ne
                FROM admin.admin_nepal
                WHERE ST_Contains(geom, ST_Centroid(ST_GeomFromText(:wkt, 4326)))
                LIMIT 1
            """)
            wkt = db.execute(
                text("SELECT ST_AsText(boundary_geom) FROM public.calculations WHERE id = :cid"),
                {"cid": str(calc.id)}
            ).scalar()
            if wkt:
                row = db.execute(fn_query, {"wkt": wkt}).first()
                if row:
                    result_data.setdefault("whole_province_ne", row[0])
                    result_data.setdefault("whole_division_n", row[1])
                    result_data.setdefault("whole_subdivis_n", row[2])
                    result_data.setdefault("whole_municipality_n", row[3])
                    result_data.setdefault("whole_municipality_type_nep", row[4])
                    result_data.setdefault("whole_ward_ne", row[5])
                    result_data.setdefault("whole_physiography_ne", row[6])
                    result_data.setdefault("whole_juridiction_ne", row[7])
        except Exception:
            pass

    return {
        "forest_name": calc.forest_name or "",
        "block_name": calc.block_name or "",
        "status": calc.status,
        "created_at": calc.created_at.isoformat() if calc.created_at else "",
        "completed_at": calc.completed_at.isoformat() if calc.completed_at else "",
        "total_area_sqm": result_data.get("area_sqm", 0),
        "total_area_hectares": result_data.get("area_hectares", 0),
        "effective_area_hectares": result_data.get("effective_area_hectares", 0),
        "excluded_area_hectares": result_data.get("excluded_area_hectares", 0),
        "province": result_data.get("whole_province_ne", "") or result_data.get("whole_province", ""),
        "district": result_data.get("whole_division_n", "") or result_data.get("whole_district", ""),
        "municipality": result_data.get("whole_municipality_n", "") or result_data.get("whole_municipality", ""),
        "municipality_type": result_data.get("whole_municipality_type_nep", "") or result_data.get("whole_municipality_type", ""),
        "ward": result_data.get("whole_ward_ne", "") or result_data.get("whole_ward", ""),
        "watershed": result_data.get("whole_watershed", ""),
        "major_river_basin": result_data.get("whole_major_river_basin", ""),
        "total_blocks": result_data.get("total_blocks", 0),
        "utm_zone": result_data.get("utm_zone", 0),
    }


def get_boundary_info(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get boundary geometry and fieldbook data"""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        return {}

    result_data = calc.result_data or {}
    blocks = result_data.get("blocks", [])

    block_info = []
    for block in blocks:
        block_info.append({
            "name": block.get("block_name", ""),
            "area_hectares": block.get("area_hectares", 0),
            "effective_area_hectares": block.get("effective_area_hectares", 0),
            "centroid": block.get("centroid", {}),
        })

    features = {
        "north": result_data.get("whole_features_north") or [],
        "east": result_data.get("whole_features_east") or [],
        "south": result_data.get("whole_features_south") or [],
        "west": result_data.get("whole_features_west") or [],
    }

    return {
        "total_blocks": len(blocks),
        "blocks": block_info,
        "boundary_type": "MultiPolygon" if len(blocks) > 1 else "Polygon",
        "features": features,
        "whole_forest_extent": result_data.get("whole_forest_extent") or {},
    }


def get_species_info(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get species data from analysis results"""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        return {}

    result_data = calc.result_data or {}
    species_list = result_data.get("potential_species", [])
    removed_species = result_data.get("removed_species", [])
    confirmed_species = result_data.get("confirmed_species", [])

    filtered_species = [s for s in species_list if s.get("scientific_name") not in removed_species]

    species_by_role = {}
    for s in filtered_species:
        role = s.get("role", "Other")
        if role not in species_by_role:
            species_by_role[role] = []
        species_by_role[role].append({
            "scientific_name": s.get("scientific_name", ""),
            "local_name": s.get("local_name", ""),
            "nepali_name": s.get("nepali_name", ""),
            "altitude_range": s.get("altitude_range", ""),
            "growth_rate": s.get("growth_rate", ""),
            "economic_value": s.get("economic_value", ""),
        })

    return {
        "total_species": len(filtered_species),
        "species_list": filtered_species,
        "removed_species": removed_species,
        "confirmed_species": confirmed_species,
        "species_by_role": species_by_role,
        "species_count": result_data.get("species_count", 0),
    }


def get_raster_analysis(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get all raster analysis results"""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        return {}

    result_data = calc.result_data or {}

    return {
        "elevation": {
            "min_m": result_data.get("elevation_min_m", 0),
            "max_m": result_data.get("elevation_max_m", 0),
            "mean_m": result_data.get("elevation_mean_m", 0),
        },
        "slope": {
            "dominant_class": result_data.get("slope_dominant_class", ""),
            "percentages": result_data.get("slope_percentages", {}),
        },
        "aspect": {
            "dominant": result_data.get("aspect_dominant", ""),
            "percentages": result_data.get("aspect_percentages", {}),
        },
        "canopy": {
            "dominant_class": result_data.get("canopy_dominant_class", ""),
            "percentages": result_data.get("canopy_percentages", {}),
            "mean_m": result_data.get("canopy_mean_m", 0),
        },
        "biomass": {
            "agb_mean": result_data.get("agb_mean", 0),
            "agb_total": result_data.get("agb_total", 0),
            "carbon_stock": result_data.get("carbon_stock", 0),
        },
        "forest_health": {
            "dominant": result_data.get("forest_health_dominant", ""),
            "percentages": result_data.get("forest_health_percentages", {}),
        },
        "forest_type": {
            "dominant": result_data.get("forest_type_dominant", ""),
            "percentages": result_data.get("forest_type_percentages", {}),
        },
        "landcover": {
            "dominant": result_data.get("landcover_dominant", ""),
            "percentages": result_data.get("landcover_percentages", {}),
        },
        "forest_loss_gain": {
            "loss_hectares": result_data.get("forest_loss_hectares", 0),
            "gain_hectares": result_data.get("forest_gain_hectares", 0),
            "loss_by_year": result_data.get("forest_loss_by_year", {}),
        },
        "temperature": {
            "mean_c": result_data.get("temperature_mean_c", 0),
            "min_c": result_data.get("temperature_min_c", 0),
            "max_c": result_data.get("temperature_max_c", 0),
        },
        "precipitation": {
            "mean_mm": result_data.get("precipitation_mean_mm", 0),
            "min_mm": result_data.get("precipitation_min_mm", 0),
            "max_mm": result_data.get("precipitation_max_mm", 0),
        },
        "soil": {
            "dominant_type": result_data.get("soil_dominant_type", ""),
            "percentages": result_data.get("soil_percentages", {}),
        },
        "geology": {
            "percentages": result_data.get("whole_geology_percentages", {}),
        },
        "physiography": {
            "percentages": result_data.get("whole_physiography_percentages", {}),
        },
        "ecoregion": {
            "percentages": result_data.get("whole_ecoregion_percentages", {}),
        },
        "landcover_historical": {
            "landcover_1984_dominant": result_data.get("landcover_1984_dominant", ""),
            "landcover_1984_percentages": result_data.get("landcover_1984_percentages", {}),
            "hansen2000_dominant": result_data.get("hansen2000_dominant", ""),
            "hansen2000_percentages": result_data.get("hansen2000_percentages", {}),
        },
    }


def get_block_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get block-wise data from database"""
    blocks = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id
    ).order_by(ForestBlock.index).all()

    sub_areas = db.query(ForestSubArea).filter(
        ForestSubArea.calculation_id == calculation_id
    ).all()

    block_results = []
    for block in blocks:
        block_data = {
            "id": str(block.id),
            "name": block.name,
            "area_hectares": block.area_hectares,
            "area_sqm": block.area_sqm,
            "index": block.index,
            "is_compartment": block.is_compartment,
            "sub_areas": [],
        }

        for sa in sub_areas:
            if sa.block_id == block.id:
                block_data["sub_areas"].append({
                    "name": sa.name,
                    "category": sa.category,
                    "area_hectares": sa.area_hectares,
                    "is_excluded": sa.is_excluded,
                })

        block_results.append(block_data)

    sub_area_summary = {}
    for sa in sub_areas:
        cat = sa.category
        if cat not in sub_area_summary:
            sub_area_summary[cat] = {"count": 0, "total_area_hectares": 0}
        sub_area_summary[cat]["count"] += 1
        sub_area_summary[cat]["total_area_hectares"] += sa.area_hectares

    return {
        "blocks": block_results,
        "total_blocks": len(blocks),
        "sub_areas": sub_area_summary,
        "total_sub_areas": len(sub_areas),
    }


def get_inventory_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get tree inventory data"""
    inv_calc = db.query(InventoryCalculation).filter(
        InventoryCalculation.calculation_id == calculation_id
    ).first()

    if not inv_calc:
        return {"available": False}

    trees = db.query(InventoryTree).filter(
        InventoryTree.inventory_calculation_id == inv_calc.id
    ).all()

    species_summary = {}
    dbh_summary = {}
    block_summary = {}

    for tree in trees:
        sp = tree.species
        species_summary[sp] = species_summary.get(sp, 0) + 1

        dbh_class = tree.dbh_class or "Unknown"
        dbh_summary[dbh_class] = dbh_summary.get(dbh_class, 0) + 1

        bn = tree.block_name or "Unassigned"
        if bn not in block_summary:
            block_summary[bn] = {"count": 0, "total_volume": 0}
        block_summary[bn]["count"] += 1
        block_summary[bn]["total_volume"] += tree.net_volume or 0

    return {
        "available": True,
        "total_trees": inv_calc.total_trees or 0,
        "mother_trees_count": inv_calc.mother_trees_count or 0,
        "felling_trees_count": inv_calc.felling_trees_count or 0,
        "seedling_count": inv_calc.seedling_count or 0,
        "total_volume_m3": round(inv_calc.total_volume_m3 or 0, 2),
        "total_net_volume_m3": round(inv_calc.total_net_volume_m3 or 0, 2),
        "total_net_volume_cft": round(inv_calc.total_net_volume_cft or 0, 2),
        "total_firewood_m3": round(inv_calc.total_firewood_m3 or 0, 2),
        "total_firewood_chatta": round(inv_calc.total_firewood_chatta or 0, 2),
        "species_summary": dict(sorted(species_summary.items(), key=lambda x: x[1], reverse=True)),
        "dbh_summary": dbh_summary,
        "block_summary": block_summary,
    }


def get_sampling_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get sampling design data"""
    designs = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id
    ).all()

    if not designs:
        return {"available": False}

    design_list = []
    for d in designs:
        rd = d.result_data or {}
        design_list.append({
            "id": str(d.id),
            "sampling_type": d.sampling_type,
            "total_points": d.total_points,
            "plot_shape": d.plot_shape,
            "plot_radius_meters": float(d.plot_radius_meters) if d.plot_radius_meters else 0,
            "intensity_per_hectare": float(d.intensity_per_hectare) if d.intensity_per_hectare else 0,
            "total_blocks": rd.get("total_blocks", 0),
            "forest_area_hectares": rd.get("forest_area_hectares", 0),
            "requested_intensity_percent": rd.get("requested_intensity_percent", 0),
            "sampling_percentage": rd.get("sampling_percentage", 0),
            "actual_intensity_per_hectare": rd.get("actual_intensity_per_hectare", 0),
            "plot_area_sqm": rd.get("plot_area_sqm", 0),
            "total_sampled_area_hectares": rd.get("total_sampled_area_hectares", 0),
            "blocks_info": rd.get("blocks_info", []),
        })

    return {
        "available": True,
        "designs": design_list,
    }


def get_household_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get household information data"""
    households = db.query(HouseholdInformation).filter(
        HouseholdInformation.calculation_id == calculation_id
    ).all()

    if not households:
        return {"available": False}

    total_male = sum(h.male_count or 0 for h in households)
    total_female = sum(h.female_count or 0 for h in households)

    prosperity = {}
    for h in households:
        p = h.prosperity_level or "Unknown"
        prosperity[p] = prosperity.get(p, 0) + 1

    caste = {}
    for h in households:
        c = h.caste_classification_ne or "Unknown"
        caste[c] = caste.get(c, 0) + 1

    total_timber_demand = sum(float(h.timber_demand_cft or 0) for h in households)
    total_firewood_demand = sum(float(h.firewood_demand_bhari or 0) for h in households)

    return {
        "available": True,
        "total_households": len(households),
        "total_population": total_male + total_female,
        "total_male": total_male,
        "total_female": total_female,
        "prosperity_distribution": prosperity,
        "caste_distribution": caste,
        "timber_demand_cft": round(total_timber_demand, 2),
        "firewood_demand_bhari": round(total_firewood_demand, 2),
        "forest_based_occupation": sum(1 for h in households if h.forest_based_occupation),
        "livestock": {
            "cow_ox": sum(h.cow_ox_count or 0 for h in households),
            "buffalo": sum(h.buffalo_count or 0 for h in households),
            "goat_sheep": sum(h.goat_sheep_count or 0 for h in households),
        },
    }


def get_committee_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get forest committee data"""
    user_committee = db.query(ForestUserCommittee).filter(
        ForestUserCommittee.calculation_id == calculation_id
    ).order_by(ForestUserCommittee.serial_no).all()

    advisory = db.query(AdvisoryCommittee).filter(
        AdvisoryCommittee.calculation_id == calculation_id
    ).order_by(AdvisoryCommittee.serial_no).all()

    financial = db.query(FinancialCommittee).filter(
        FinancialCommittee.calculation_id == calculation_id
    ).order_by(FinancialCommittee.serial_no).all()

    return {
        "user_committee": {
            "total_members": len(user_committee),
            "members": [
                {
                    "name": m.name,
                    "position": m.position,
                    "gender": m.gender,
                    "address": m.address,
                    "mobile": m.mobile,
                }
                for m in user_committee
            ],
        },
        "advisory_committee": {
            "total_members": len(advisory),
            "members": [{"name": m.name, "address": m.address} for m in advisory],
        },
        "financial_committee": {
            "total_members": len(financial),
            "members": [{"name": m.name, "address": m.address} for m in financial],
        },
    }


def get_biodiversity_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get biodiversity records"""
    records = db.query(CalculationBiodiversity).filter(
        CalculationBiodiversity.calculation_id == calculation_id
    ).all()

    if not records:
        return {"available": False}

    vegetation = []
    animals = []

    species_ids = [r.species_id for r in records]
    species_map = {s.id: s for s in db.query(BiodiversitySpecies).filter(
        BiodiversitySpecies.id.in_(species_ids)
    ).all()}

    for r in records:
        species = species_map.get(r.species_id)

        record = {
            "name": species.nepali_name if species else "",
            "scientific_name": species.scientific_name if species else "",
            "presence_status": r.presence_status,
            "abundance": r.abundance,
            "iucn_status": species.iucn_status if species else "",
        }

        if species and species.category == "vegetation":
            vegetation.append(record)
        else:
            animals.append(record)

    return {
        "available": True,
        "total_species": len(records),
        "vegetation_count": len(vegetation),
        "animal_count": len(animals),
        "vegetation": vegetation,
        "animals": animals,
    }


def get_activities_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get proposed yearly activities"""
    activities = db.query(ProposedYearlyActivity).filter(
        ProposedYearlyActivity.calculation_id == calculation_id
    ).all()

    if not activities:
        return {"available": False}

    activity_list = []
    total_budget = 0

    from collections import defaultdict
    activity_ids = [a.id for a in activities]
    all_year_details = defaultdict(list)
    for yd in db.query(ActivityYearDetail).filter(
        ActivityYearDetail.proposed_activity_id.in_(activity_ids)
    ).order_by(ActivityYearDetail.year_number).all():
        all_year_details[yd.proposed_activity_id].append(yd)

    for act in activities:
        year_details = all_year_details.get(act.id, [])

        yearly_budgets = []
        for yd in year_details:
            yearly_budgets.append({
                "year": yd.year_number,
                "quantity": float(yd.quantity or 0),
                "budget": float(yd.yearly_budget or 0),
            })
            total_budget += float(yd.yearly_budget or 0)

        activity_list.append({
            "activity_id": act.potential_activity_id,
            "notes": act.notes,
            "default_quantity": float(act.default_quantity or 0),
            "yearly_details": yearly_budgets,
        })

    return {
        "available": True,
        "total_activities": len(activities),
        "activities": activity_list,
        "total_budget": round(total_budget, 2),
    }


def get_user_group_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Get user group extent and buildings data"""
    extents = db.query(UserGroupExtent).filter(
        UserGroupExtent.calculation_id == calculation_id
    ).all()

    if not extents:
        return {"available": False}

    from collections import defaultdict
    extent_ids = [ext.id for ext in extents]
    ext_buildings_map = defaultdict(list)
    for b in db.query(UserGroupBuilding).filter(
        UserGroupBuilding.extent_id.in_(extent_ids)
    ).all():
        ext_buildings_map[b.extent_id].append(b)

    buildings = []
    for ext in extents:
        for b in ext_buildings_map.get(ext.id, []):
            buildings.append({
                "settlement_name": b.settlement_name,
                "building_count": b.building_count,
                "direction_from_forest": b.direction_from_forest,
                "total_area_m2": b.total_building_area_m2,
            })

    return {
        "available": True,
        "total_settlements": len(buildings),
        "buildings": buildings,
    }


def collect_all_data(db: Session, calculation_id: str) -> Dict[str, Any]:
    """Collect all data needed for the full report"""
    raw_data = {
        "basic_info": get_calculation_basic_info(db, calculation_id),
        "boundary": get_boundary_info(db, calculation_id),
        "species": get_species_info(db, calculation_id),
        "raster_analysis": get_raster_analysis(db, calculation_id),
        "blocks": get_block_data(db, calculation_id),
        "inventory": get_inventory_data(db, calculation_id),
        "sampling": get_sampling_data(db, calculation_id),
        "households": get_household_data(db, calculation_id),
        "committees": get_committee_data(db, calculation_id),
        "biodiversity": get_biodiversity_data(db, calculation_id),
        "activities": get_activities_data(db, calculation_id),
        "user_group": get_user_group_data(db, calculation_id),
    }
    return _convert_decimals(raw_data)
