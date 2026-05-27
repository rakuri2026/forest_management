import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from uuid import UUID

from sqlalchemy.orm import Session
from nepali_datetime import date as nepali_date

from app.models.operational_plan import OperationalPlan
from app.models.calculation import Calculation
from .variable_registry import VARIABLE_REGISTRY, VariableDef
from .data_collector import collect_all_op_data
from app.utils.number_format import format_devanagari


VARIABLE_PATTERN = re.compile(r"\{\{(\w+:?\w+)\}\}")
_SENTINEL = object()


_KEY_ALIAS: Dict[tuple, str] = {
    # calculation -> basic_info
    ("basic_info", "calculation_status"): "status",

    # raster -> raster_analysis (nested under sub-objects)
    ("raster_analysis", "elevation_min_m"): "elevation.min_m",
    ("raster_analysis", "elevation_max_m"): "elevation.max_m",
    ("raster_analysis", "elevation_mean_m"): "elevation.mean_m",
    ("raster_analysis", "slope_dominant_class"): "slope.dominant_class",
    ("raster_analysis", "slope_percentages"): "slope.percentages",
    ("raster_analysis", "aspect_dominant"): "aspect.dominant",
    ("raster_analysis", "aspect_percentages"): "aspect.percentages",
    ("raster_analysis", "canopy_dominant_class"): "canopy.dominant_class",
    ("raster_analysis", "canopy_percentages"): "canopy.percentages",
    ("raster_analysis", "canopy_mean_m"): "canopy.mean_m",
    ("raster_analysis", "biomass_agb_mean"): "biomass.agb_mean",
    ("raster_analysis", "biomass_agb_total"): "biomass.agb_total",
    ("raster_analysis", "biomass_carbon_stock"): "biomass.carbon_stock",
    ("raster_analysis", "forest_health_dominant"): "forest_health.dominant",
    ("raster_analysis", "forest_health_percentages"): "forest_health.percentages",
    ("raster_analysis", "forest_type_dominant"): "forest_type.dominant",
    ("raster_analysis", "forest_type_percentages"): "forest_type.percentages",
    ("raster_analysis", "landcover_dominant"): "landcover.dominant",
    ("raster_analysis", "landcover_percentages"): "landcover.percentages",
    ("raster_analysis", "forest_loss_hectares"): "forest_loss_gain.loss_hectares",
    ("raster_analysis", "forest_gain_hectares"): "forest_loss_gain.gain_hectares",
    ("raster_analysis", "forest_loss_by_year"): "forest_loss_gain.loss_by_year",
    ("raster_analysis", "temperature_mean_c"): "temperature.mean_c",
    ("raster_analysis", "temperature_min_c"): "temperature.min_c",
    ("raster_analysis", "temperature_max_c"): "temperature.max_c",
    ("raster_analysis", "precipitation_mean_mm"): "precipitation.mean_mm",
    ("raster_analysis", "precipitation_min_mm"): "precipitation.min_mm",
    ("raster_analysis", "precipitation_max_mm"): "precipitation.max_mm",
    ("raster_analysis", "soil_dominant_type"): "soil.dominant_type",
    ("raster_analysis", "soil_percentages"): "soil.percentages",
    ("raster_analysis", "geology_percentages"): "geology.percentages",
    ("raster_analysis", "physiography_percentages"): "physiography.percentages",
    ("raster_analysis", "ecoregion_percentages"): "ecoregion.percentages",
    # Category B raster hybrid aliases
    ("raster_analysis", "altitude_min_m"): "elevation.min_m",
    ("raster_analysis", "altitude_max_m"): "elevation.max_m",
    ("raster_analysis", "altitude_mean_m"): "elevation.mean_m",
    ("raster_analysis", "dominant_slope"): "slope.dominant_class",
    ("raster_analysis", "dominant_aspect"): "aspect.dominant",
    ("raster_analysis", "dominant_soil"): "soil.dominant_type",
    ("raster_analysis", "crown_density_pct"): "canopy.mean_m",

    # boundary
    ("boundary", "boundary_features_east"): "features.east",
    ("boundary", "boundary_features_west"): "features.west",
    ("boundary", "boundary_features_north"): "features.north",
    ("boundary", "boundary_features_south"): "features.south",
    ("boundary", "boundary_forest_extent_data"): "whole_forest_extent",

    # block
    ("blocks", "blocks_count"): "total_blocks",
    ("blocks", "blocks_with_data"): "blocks",

    # species
    ("species", "species_role_counts"): "species_by_role",

    # inventory (registry uses inventory_ prefix, data does not)
    ("inventory", "inventory_total_trees"): "total_trees",
    ("inventory", "inventory_mother_trees_count"): "mother_trees_count",
    ("inventory", "inventory_felling_trees_count"): "felling_trees_count",
    ("inventory", "inventory_seedling_count"): "seedling_count",
    ("inventory", "inventory_total_volume_m3"): "total_volume_m3",
    ("inventory", "inventory_total_net_volume_m3"): "total_net_volume_m3",
    ("inventory", "inventory_total_net_volume_cft"): "total_net_volume_cft",
    ("inventory", "inventory_total_firewood_m3"): "total_firewood_m3",
    ("inventory", "inventory_total_firewood_chatta"): "total_firewood_chatta",
    ("inventory", "inventory_species_composition"): "species_summary",
    ("inventory", "inventory_dbh_distribution"): "dbh_summary",
    ("inventory", "inventory_block_summary"): "block_summary",

    # field_inventory (Category B aliases)
    ("field_inventory", "growing_stock_m3_per_ha"): "fi_growing_stock_m3_per_ha",
    ("field_inventory", "biomass_t_per_ha"): "fi_total_biomass_t_per_ha",
    ("field_inventory", "carbon_stock_tc_per_ha"): "fi_carbon_stock_tc_per_ha",

    # sampling (nested in designs[0])
    ("sampling", "sampling_type"): "designs.0.sampling_type",
    ("sampling", "sampling_total_points"): "designs.0.total_points",
    ("sampling", "sampling_plot_shape"): "designs.0.plot_shape",
    ("sampling", "sampling_plot_radius_m"): "designs.0.plot_radius_meters",
    ("sampling", "sampling_intensity_per_ha"): "designs.0.intensity_per_hectare",
    ("sampling", "fi_sampling_designs"): "designs",

    # household (strip hh_ prefix)
    ("households", "hh_total_households"): "total_households",
    ("households", "hh_total_population"): "total_population",
    ("households", "hh_total_male"): "total_male",
    ("households", "hh_total_female"): "total_female",
    ("households", "hh_prosperity_distribution"): "prosperity_distribution",
    ("households", "hh_caste_distribution"): "caste_distribution",
    ("households", "hh_timber_demand_cft"): "timber_demand_cft",
    ("households", "hh_firewood_demand_bhari"): "firewood_demand_bhari",
    ("households", "hh_forest_based_occupation"): "forest_based_occupation",

    # committee (special mapping)
    ("committees", "uc_members"): "user_committee.members",
    ("committees", "uc_total_members"): "user_committee.total_members",
    ("committees", "ac_members"): "advisory_committee.members",
    ("committees", "ac_total_members"): "advisory_committee.total_members",
    ("committees", "fc_members"): "financial_committee.members",
    ("committees", "fc_total_members"): "financial_committee.total_members",
    ("committees", "uc_gender_distribution"): "user_committee.gender_distribution",
    ("committees", "uc_position_distribution"): "user_committee.position_distribution",
    ("committees", "uc_caste_distribution"): "user_committee.caste_distribution",

    # biodiversity (strip bio_ prefix)
    ("biodiversity", "bio_available"): "available",
    ("biodiversity", "bio_total_species"): "total_species",
    ("biodiversity", "bio_vegetation_count"): "vegetation_count",
    ("biodiversity", "bio_animal_count"): "animal_count",
    ("biodiversity", "bio_vegetation"): "vegetation",
    ("biodiversity", "bio_animals"): "animals",

    # activities (strip activities_ prefix)
    ("activities", "activities_available"): "available",
    ("activities", "activities_total"): "total_activities",
    ("activities", "activities_total_budget"): "total_budget",
    ("activities", "activities_list"): "activities",

    # user_group (strip ug_ prefix)
    ("user_group", "ug_available"): "available",
    ("user_group", "ug_total_settlements"): "total_settlements",
    ("user_group", "ug_buildings"): "buildings",
}


class VariableResolver:

    def __init__(self, db: Session, calculation_id: UUID, plan: OperationalPlan):
        self.db = db
        self.calculation_id = calculation_id
        self.plan = plan
        self._raw_data: Optional[Dict[str, Any]] = None
        self._resolved: Dict[str, Any] = {}

    def get_raw_data(self) -> Dict[str, Any]:
        if self._raw_data is None:
            self._raw_data = collect_all_op_data(self.db, str(self.calculation_id))
        return self._raw_data

    @staticmethod
    def _deep_get(data: Union[Dict, List, Any], path: str) -> Any:
        if not path:
            return None
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, (list, tuple)):
                try:
                    idx = int(key)
                    current = current[idx] if 0 <= idx < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    def resolve_all(self) -> Dict[str, Any]:
        for key, var_def in VARIABLE_REGISTRY.items():
            if key.startswith("chart:"):
                continue
            self._resolved[key] = self._resolve_single(var_def)
        return self._resolved

    def resolve_node_content(self, content: str) -> str:
        def _replacer(match):
            var_name = match.group(1)
            if var_name.startswith("chart:") or var_name.startswith("map:") or var_name.startswith("table:"):
                return match.group(0)
            var_def = VARIABLE_REGISTRY.get(var_name)
            if var_def is None:
                return ""
            if var_name not in self._resolved:
                self._resolved[var_name] = self._resolve_single(var_def)
            val = self._resolved[var_name]
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                return match.group(0)
            return format_devanagari(val, var_def.precision)

        return VARIABLE_PATTERN.sub(_replacer, content)

    def _resolve_single(self, var_def: VariableDef) -> Any:
        resolver_map = {
            "resolve_a": self._resolve_category_a,
            "resolve_b": self._resolve_hybrid,
            "resolve_c": self._resolve_user_input,
            "resolve_d": self._resolve_computed,
            "resolve_e": self._resolve_section_content,
            "resolve_f": self._resolve_template,
            "resolve_hybrid": self._resolve_hybrid,
            "resolve_user_input": self._resolve_user_input,
            "resolve_computed": self._resolve_computed,
            "resolve_section_content": self._resolve_section_content,
            "resolve_template": self._resolve_template,
            "resolve_kabuliyatnama_detail": self._resolve_kabuliyatnama_detail,
            "resolve_chairperson": self._resolve_chairperson,
        }
        resolver = resolver_map.get(var_def.resolver, self._resolve_category_a)
        return resolver(var_def)

    def _resolve_category_a(self, var_def: VariableDef) -> Any:
        data = self.get_raw_data()
        source_map = {
            "calculation": "basic_info",
            "raster": "raster_analysis",
            "boundary": "boundary",
            "block": "blocks",
            "species": "species",
            "inventory": "inventory",
            "field_inventory": "field_inventory",
            "sampling": "sampling",
            "household": "households",
            "committee": "committees",
            "biodiversity": "biodiversity",
            "activities": "activities",
            "user_group": "user_group",
        }
        section = source_map.get(var_def.source, "basic_info")
        section_data = data.get(section, {})

        if var_def.key in section_data:
            return section_data[var_def.key]

        path = _KEY_ALIAS.get((section, var_def.key))
        if path:
            return self._deep_get(section_data, path)

        return None

    def _resolve_hybrid(self, var_def: VariableDef) -> Any:
        overrides = (self.plan.plan_metadata or {}).get("hybrid_overrides", {})
        if var_def.key in overrides:
            return overrides[var_def.key]
        system_val = self._resolve_category_a(var_def)
        if system_val is not None:
            return system_val
        return None

    def _resolve_user_input(self, var_def: VariableDef) -> Any:
        user_inputs = (self.plan.plan_metadata or {}).get("user_inputs", {})
        val = user_inputs.get(var_def.key, _SENTINEL)
        if val is _SENTINEL or val is None:
            if var_def.key == "kabuliyatnama_date":
                return nepali_date.today().strftime("%Y/%m/%d")
            fallback_map = {
                "forest_municipality": "municipality",
                "forest_ward": "ward",
            }
            if var_def.key in fallback_map:
                a_def = VARIABLE_REGISTRY.get(fallback_map[var_def.key])
                if a_def:
                    return self._resolve_category_a(a_def)
            return None
        return val

    MONTH_NAMES_NP = (None, "वैशाख", "जेष्ठ", "असार", "श्रावण", "भदौ", "आश्विन", "कार्तिक", "मंसिर", "पौष", "माघ", "फाल्गुण", "चैत्र")
    DAY_NAMES_NP = ("आइतबार", "सोमबार", "मङ्गलबार", "बुधबार", "बिहिबार", "शुक्रबार", "शनिबार")

    def _resolve_kabuliyatnama_detail(self, var_def: VariableDef) -> Any:
        user_inputs = (self.plan.plan_metadata or {}).get("user_inputs", {})
        raw = user_inputs.get("kabuliyatnama_date", "")
        if not raw or not isinstance(raw, str):
            today_default = nepali_date.today()
            raw = today_default.strftime("%Y/%m/%d")
        parts = raw.split("/")
        if len(parts) != 3:
            return raw
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if var_def.key == "kabuliyatnama_date_year":
            return y
        if var_def.key == "kabuliyatnama_date_month":
            return m
        if var_def.key == "kabuliyatnama_date_day":
            return d
        if var_def.key == "kabuliyatnama_date_sentence":
            try:
                nd = nepali_date(y, m, d)
                month_name = self.MONTH_NAMES_NP[m] if 1 <= m <= 12 else str(m)
                day_name = self.DAY_NAMES_NP[nd.weekday()]
                return f"ईति सम्वत {format_devanagari(y)} साल {month_name} महिना {format_devanagari(d)} गते रोज {day_name} शुभम् ।"
            except (ValueError, OverflowError):
                return raw
        return raw

    def _resolve_chairperson(self, var_def: VariableDef) -> Any:
        data = self.get_raw_data()
        committees = data.get("committees", {})
        uc = committees.get("user_committee", {})
        members = uc.get("members", [])
        for m in members:
            if m.get("position") == "अध्यक्ष":
                return m.get("name")
        return None

    def _resolve_computed(self, var_def: VariableDef) -> Any:
        if not var_def.compute_fn:
            return None
        ctx = self._resolved if self._resolved else self.resolve_all()
        compute_map = {
            "compute_total_plan_area": lambda: ctx.get("total_area_hectares", 0),
            "compute_forest_area": lambda: self._compute_forest_area(ctx),
            "compute_non_forest_area": lambda: max(0, ctx.get("total_plan_area_ha", 0) - ctx.get("forest_area_ha", 0)),
            "compute_forest_pct": lambda: round(ctx.get("forest_area_ha", 0) / max(ctx.get("total_plan_area_ha", 1), 1) * 100, 2),
            "compute_total_growing_stock": lambda: ctx.get("growing_stock_m3_per_ha", 0) * ctx.get("forest_area_ha", 0),
            "compute_total_carbon_stock": lambda: ctx.get("carbon_stock_tc_per_ha", 0) * ctx.get("forest_area_ha", 0),
            "compute_total_co2": lambda: ctx.get("total_carbon_stock_tc", 0) * 3.67,
            "compute_annual_increment": lambda: ctx.get("total_growing_stock_m3", 0) * ctx.get("fi_mai_percent", 0) / 100,
            "compute_forest_per_hh": lambda: round(ctx.get("forest_area_ha", 0) / max(ctx.get("hh_total_households", 1), 1), 2),
            "compute_plan_years_range": lambda: f"{ctx.get('plan_year_start', '')}-{ctx.get('plan_year_end', '')}",
            "compute_cf_area_provided": lambda: self._compute_cf_area_provided(),
        }
        fn = compute_map.get(var_def.compute_fn)
        return fn() if fn else None

    def _compute_forest_area(self, ctx: Dict) -> float:
        data = self.get_raw_data()
        blocks_data = data.get("blocks", {})
        sub_areas = blocks_data.get("sub_areas", {})
        forest_area = 0
        for cat, info in sub_areas.items():
            if "वन" in str(cat) or "forest" in str(cat).lower():
                forest_area += info.get("total_area_hectares", 0)
        if forest_area == 0:
            forest_area = data.get("basic_info", {}).get("effective_area_hectares", 0)
        return forest_area

    def _compute_cf_area_provided(self) -> float:
        data = self.get_raw_data()
        bi = data.get("basic_info", {})
        effective = bi.get("effective_area_hectares", 0)
        if effective:
            return effective
        blocks_data = data.get("blocks", {})
        blocks = blocks_data.get("blocks", [])
        return sum(b.get("effective_area_hectares", b.get("area_hectares", 0)) for b in blocks)

    def _resolve_section_content(self, var_def: VariableDef) -> Any:
        sections = {
            "section_6_previous_review": "विगतको कार्ययोजनाको समीक्षा गर्दा...",
            "section_8_production": "वन पैदावार उत्पादन निम्नानुसार गरिनेछ...",
            "section_16_prohibited": "सामुदायिक वनमा निम्न कार्यहरू निषेधित गरिएका छन्...",
            "section_17_penalties": "वन अपराध सम्बन्धी सजाय: ...",
            "section_18_misc": "अन्य विविध व्यवस्थाहरू: ...",
        }
        return sections.get(var_def.key, "")

    def _resolve_template(self, var_def: VariableDef) -> Any:
        now = datetime.utcnow()
        template_values = {
            "document_version": (self.plan.plan_metadata or {}).get("version", "2.0"),
            "generated_date": now.strftime("%Y-%m-%d"),
            "generated_by": "",
            "document_language": (self.plan.plan_metadata or {}).get("language", "NP"),
            "export_format": "DOCX",
            "plan_revision_number": (self.plan.plan_metadata or {}).get("revision", 1),
        }
        return template_values.get(var_def.key, "")
