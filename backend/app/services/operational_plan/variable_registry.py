from typing import Dict, Any, Optional, List, Callable, Literal
from pydantic import BaseModel, Field


class VariableDef(BaseModel):
    key: str
    category: Literal["A", "B", "C", "D", "E", "F"]
    label_ne: str = ""
    label_en: str = ""
    var_type: Literal["string", "number", "boolean", "dict", "list"] = "string"
    source: str = ""
    auto_populate: bool = True
    resolver: str = ""
    compute_fn: Optional[str] = None
    description: str = ""
    precision: int = 2


VARIABLE_REGISTRY: Dict[str, VariableDef] = {}


def _infer_precision(key: str, label_en: str) -> int:
    """Auto-detect decimal precision from variable key and English label."""
    text = f" {key} {label_en} ".replace("_", " ").lower()
    key_lower = key.lower()

    # Wood density (before generic "density" match)
    if "wood density" in text:
        return 4
    # Carbon/biomass/CO2 -> 3 decimal places
    if any(w in text for w in ("agb", "bgb", "biomass", "carbon", "co2")):
        return 3
    # Percentages/density -> 1 decimal place
    if any(w in text for w in ("percent", " pct ", "density")):
        return 1
    # Climate
    if any(w in text for w in ("temperature", "precipitation")):
        return 1
    # Elevation/altitude -> whole numbers
    if any(w in text for w in ("elevation", "altitude", "utm")):
        return 0
    # Whole-number measures
    if any(w in text for w in ("cft", "chatta", "bhari", "year", "budget", "rupees")):
        return 0
    # Counts (specific compound suffixes only)
    if any(w in text.split() for w in (
        "plots", "trees", "households", "members", "species", "blocks",
        "points", "settlements", "activities", "revision", "population",
        "male", "female", "occupation",
    )):
        return 0
    # Suffix-based count detection (on raw key before space replacement)
    if any(key_lower.endswith(s) for s in ("_count", "_total", "_number")):
        return 0
    return 2


def _reg(
    key: str,
    category: str,
    label_ne: str = "",
    label_en: str = "",
    var_type: str = "string",
    source: str = "",
    auto_populate: bool = True,
    resolver: str = "",
    compute_fn: str = "",
    description: str = "",
    precision: int = 2,
) -> None:
    if var_type == "number" and precision == 2:
        precision = _infer_precision(key, label_en)
    VARIABLE_REGISTRY[key] = VariableDef(
        key=key,
        category=category,
        label_ne=label_ne or key,
        label_en=label_en or key,
        var_type=var_type,
        source=source,
        auto_populate=auto_populate,
        resolver=resolver or f"resolve_{category.lower()}",
        compute_fn=compute_fn or None,
        description=description,
        precision=precision,
    )


# ═══════════════════════════════════════════════════════
# Category A: System Variables (109)
# ═══════════════════════════════════════════════════════

# A1: Basic Calculation Info (22)
_reg("forest_name", "A", "वनको नाम", "Forest Name", source="calculation")
_reg("block_name", "A", "ब्लकको नाम", "Block Name", source="calculation")
_reg("calculation_status", "A", "गणना स्थिति", "Calculation Status", source="calculation")
_reg("created_at", "A", "सृजना मिति", "Created At", var_type="string", source="calculation")
_reg("completed_at", "A", "सम्पन्न मिति", "Completed At", var_type="string", source="calculation")
_reg("total_area_sqm", "A", "कुल क्षेत्रफल (वर्गमि)", "Total Area (sqm)", var_type="number", source="calculation")
_reg("total_area_hectares", "A", "कुल क्षेत्रफल (हेक्टर)", "Total Area (ha)", var_type="number", source="calculation")
_reg("effective_area_hectares", "A", "प्रभावकारी क्षेत्रफल", "Effective Area (ha)", var_type="number", source="calculation")
_reg("excluded_area_hectares", "A", "बहिष्कृत क्षेत्रफल", "Excluded Area (ha)", var_type="number", source="calculation")
_reg("province", "A", "प्रदेश", "Province", source="calculation")
_reg("district", "A", "जिल्ला", "District", source="calculation")
_reg("municipality", "A", "नगरपालिका/गाउँपालिका", "Municipality", source="calculation")
_reg("municipality_type", "A", "स्थानीय तहको प्रकार", "Municipality Type", source="calculation")
_reg("ward", "A", "वडा नं.", "Ward No", source="calculation")
_reg("watershed", "A", "जलाधार", "Watershed", source="calculation")
_reg("major_river_basin", "A", "प्रमुख नदी बेसिन", "Major River Basin", source="calculation")
_reg("total_blocks", "A", "कुल ब्लक सङ्ख्या", "Total Blocks", var_type="number", source="calculation", precision=0)
_reg("utm_zone", "A", "UTM जोन", "UTM Zone", var_type="number", source="calculation", precision=0)

# A2: Raster - Physiography (12)
_reg("elevation_min_m", "A", "न्यूनतम उचाई (मि)", "Min Elevation (m)", var_type="number", source="raster", precision=0)
_reg("elevation_max_m", "A", "अधिकतम उचाई (मि)", "Max Elevation (m)", var_type="number", source="raster", precision=0)
_reg("elevation_mean_m", "A", "औसत उचाई (मि)", "Mean Elevation (m)", var_type="number", source="raster", precision=0)
_reg("slope_dominant_class", "A", "मुख्य भिरालो वर्ग", "Dominant Slope", source="raster")
_reg("slope_percentages", "A", "भिरालो प्रतिशत", "Slope Percentages", var_type="dict", source="raster")
_reg("aspect_dominant", "A", "मुख्य दिशा", "Dominant Aspect", source="raster")
_reg("aspect_percentages", "A", "दिशा प्रतिशत", "Aspect Percentages", var_type="dict", source="raster")
_reg("soil_dominant_type", "A", "मुख्य माटो प्रकार", "Dominant Soil Type", source="raster")
_reg("soil_percentages", "A", "माटो प्रतिशत", "Soil Percentages", var_type="dict", source="raster")
_reg("geology_percentages", "A", "भूगर्भ प्रतिशत", "Geology Percentages", var_type="dict", source="raster")
_reg("physiography_percentages", "A", "भू-आकृति प्रतिशत", "Physiography Percentages", var_type="dict", source="raster")
_reg("ecoregion_percentages", "A", "इकोरिजन प्रतिशत", "Ecoregion Percentages", var_type="dict", source="raster")

# A3: Raster - Climate (6)
_reg("temperature_mean_c", "A", "औसत तापक्रम (से)", "Mean Temperature (C)", var_type="number", source="raster", precision=1)
_reg("temperature_min_c", "A", "न्यूनतम तापक्रम (से)", "Min Temperature (C)", var_type="number", source="raster", precision=1)
_reg("temperature_max_c", "A", "अधिकतम तापक्रम (से)", "Max Temperature (C)", var_type="number", source="raster", precision=1)
_reg("precipitation_mean_mm", "A", "औसत वर्षा (मिमि)", "Mean Precipitation (mm)", var_type="number", source="raster", precision=1)
_reg("precipitation_min_mm", "A", "न्यूनतम वर्षा (मिमि)", "Min Precipitation (mm)", var_type="number", source="raster", precision=1)
_reg("precipitation_max_mm", "A", "अधिकतम वर्षा (मिमि)", "Max Precipitation (mm)", var_type="number", source="raster", precision=1)

# A4: Raster - Forest Cover (12)
_reg("forest_type_dominant", "A", "मुख्य वन प्रकार", "Dominant Forest Type", source="raster")
_reg("forest_type_percentages", "A", "वन प्रकार प्रतिशत", "Forest Type Percentages", var_type="dict", source="raster")
_reg("landcover_dominant", "A", "मुख्य भू-आवरण", "Dominant Landcover", source="raster")
_reg("landcover_percentages", "A", "भू-आवरण प्रतिशत", "Landcover Percentages", var_type="dict", source="raster")
_reg("forest_health_dominant", "A", "मुख्य वन स्वास्थ्य", "Dominant Forest Health", source="raster")
_reg("forest_health_percentages", "A", "वन स्वास्थ्य प्रतिशत", "Forest Health Percentages", var_type="dict", source="raster")
_reg("canopy_dominant_class", "A", "मुख्य वन मुकुट वर्ग", "Dominant Canopy Class", source="raster")
_reg("canopy_percentages", "A", "वन मुकुट प्रतिशत", "Canopy Percentages", var_type="dict", source="raster")
_reg("canopy_mean_m", "A", "औसत वन मुकुट (मि)", "Mean Canopy (m)", var_type="number", source="raster", precision=1)
_reg("forest_loss_hectares", "A", "वन क्षति (हे)", "Forest Loss (ha)", var_type="number", source="raster")
_reg("forest_gain_hectares", "A", "वन लाभ (हे)", "Forest Gain (ha)", var_type="number", source="raster")
_reg("forest_loss_by_year", "A", "वार्षिक वन क्षति", "Forest Loss by Year", var_type="dict", source="raster")
_reg("nasa_forest_2020_percentages", "A", "वन गुणस्तर प्रतिशत (नासा)", "Forest Quality Percentages (NASA)", var_type="dict", source="raster")
_reg("nasa_forest_2020_dominant", "A", "मुख्य वन गुणस्तर (नासा)", "Dominant Forest Quality (NASA)", source="raster")
_reg("chart:nasa_forest_2020_pie", "A", "वन गुणस्तर पाई चार्ट (नासा)", "Forest Quality Pie Chart (NASA)", var_type="dict", source="raster")

# A5: Raster - Biomass/Carbon (3)
_reg("agb_mean", "A", "औसत AGB", "Mean AGB", var_type="number", source="raster", precision=3)
_reg("agb_total", "A", "कुल AGB", "Total AGB", var_type="number", source="raster")
_reg("carbon_stock", "A", "कार्बन मौज्दात", "Carbon Stock", var_type="number", source="raster", precision=3)

# A6: Boundary (5)
_reg("boundary_type", "A", "सिमाना प्रकार", "Boundary Type", source="boundary")
_reg("boundary_features_north", "A", "उत्तर सिमाना", "North Boundary", var_type="list", source="boundary")
_reg("boundary_features_east", "A", "पूर्व सिमाना", "East Boundary", var_type="list", source="boundary")
_reg("boundary_features_south", "A", "दक्षिण सिमाना", "South Boundary", var_type="list", source="boundary")
_reg("boundary_features_west", "A", "पश्चिम सिमाना", "West Boundary", var_type="list", source="boundary")
_reg("extent_n", "A", "उत्तर अक्षांश", "North Latitude", precision=7, source="boundary")
_reg("extent_s", "A", "दक्षिण अक्षांश", "South Latitude", precision=7, source="boundary")
_reg("extent_e", "A", "पूर्व देशान्तर", "East Longitude", precision=7, source="boundary")
_reg("extent_w", "A", "पश्चिम देशान्तर", "West Longitude", precision=7, source="boundary")

# A7: Blocks & Sub-Areas (7)
_reg("blocks_count", "A", "ब्लक सङ्ख्या", "Blocks Count", var_type="number", source="block", precision=0)
_reg("sub_areas_by_category", "A", "उप-क्षेत्र प्रकार", "Sub-areas by Category", var_type="dict", source="block")
_reg("sub_areas_total", "A", "कुल उप-क्षेत्र", "Total Sub-areas", var_type="number", source="block", precision=0)

_reg("sub_areas_detail", "A",
     "उप-क्षेत्र विवरण",
     "Sub-Areas Detail",
     var_type="list", source="block")
_reg("block_area_detail_merged", "A",
     "ब्लक अनुसार क्षेत्रफलको विस्तृत विवरण तथा सामुदायिक वन क्षेत्रफल",
     "Block-wise Detailed Area & Community Forest Area Description (Merged)",
     var_type="list", source="block")

# A8: Species (4)
_reg("total_species", "A", "कुल प्रजाति सङ्ख्या", "Total Species", var_type="number", source="species", precision=0)
_reg("species_list", "A", "प्रजाति सूची", "Species List", var_type="list", source="species")
_reg("species_by_role", "A", "भूमिका अनुसार प्रजाति", "Species by Role", var_type="dict", source="species")
_reg("confirmed_species", "A", "पुष्टि गरिएका प्रजाति", "Confirmed Species", var_type="list", source="species")

# A9: Tree Inventory (13)
_reg("inventory_available", "A", "रूख गणना उपलब्ध", "Inventory Available", var_type="boolean", source="inventory")
_reg("inventory_total_trees", "A", "कुल रूख सङ्ख्या", "Total Trees", var_type="number", source="inventory", precision=0)
_reg("inventory_mother_trees", "A", "माँउ रूख सङ्ख्या", "Mother Trees", var_type="number", source="inventory", precision=0)
_reg("inventory_felling_trees", "A", "कटानी रूख सङ्ख्या", "Felling Trees", var_type="number", source="inventory", precision=0)
_reg("inventory_seedling_count", "A", "बिरुवा सङ्ख्या", "Seedling Count", var_type="number", source="inventory", precision=0)
_reg("inventory_volume_m3", "A", "कुल आयतन (m³)", "Total Volume (m3)", var_type="number", source="inventory")
_reg("inventory_net_volume_m3", "A", "शुद्ध आयतन (m³)", "Net Volume (m3)", var_type="number", source="inventory")
_reg("inventory_net_volume_cft", "A", "शुद्ध आयतन (cft)", "Net Volume (cft)", var_type="number", source="inventory", precision=0)
_reg("inventory_firewood_m3", "A", "दाउरा आयतन (m³)", "Firewood Volume (m3)", var_type="number", source="inventory")
_reg("inventory_firewood_chatta", "A", "दाउरा (चट्टा)", "Firewood (chatta)", var_type="number", source="inventory", precision=0)
_reg("inventory_species_summary", "A", "प्रजाति सारांश", "Species Summary", var_type="dict", source="inventory")
_reg("inventory_dbh_summary", "A", "DBH सारांश", "DBH Summary", var_type="dict", source="inventory")
_reg("inventory_block_summary", "A", "ब्लक सारांश", "Block Summary", var_type="dict", source="inventory")

# A10: Field Inventory (23)
_reg("fi_available", "A", "क्षेत्र सर्वेक्षण उपलब्ध", "Field Inventory Available", var_type="boolean", source="field_inventory")
_reg("fi_total_plots", "A", "कुल नमूना प्लट", "Total Sample Plots", var_type="number", source="field_inventory", precision=0)
_reg("fi_total_blocks", "A", "सर्वेक्षण ब्लक", "Survey Blocks", var_type="number", source="field_inventory", precision=0)
_reg("fi_regeneration_area_sqm", "A", "पुनरुत्पादन क्षेत्र (m²)", "Regeneration Area (sqm)", var_type="number", source="field_inventory")
_reg("fi_sapling_area_sqm", "A", "बिरुवा क्षेत्र (m²)", "Sapling Area (sqm)", var_type="number", source="field_inventory")
_reg("fi_pole_area_sqm", "A", "पोल क्षेत्र (m²)", "Pole Area (sqm)", var_type="number", source="field_inventory")
_reg("fi_tree_area_sqm", "A", "रूख क्षेत्र (m²)", "Tree Area (sqm)", var_type="number", source="field_inventory")
_reg("fi_regeneration_per_ha", "A", "प्रतिहेक्टर पुनरुत्पादन", "Regeneration per ha", var_type="number", source="field_inventory")
_reg("fi_sapling_per_ha", "A", "प्रतिहेक्टर बिरुवा", "Sapling per ha", var_type="number", source="field_inventory")
_reg("fi_pole_per_ha", "A", "प्रतिहेक्टर पोल", "Pole per ha", var_type="number", source="field_inventory")
_reg("fi_tree_per_ha", "A", "प्रतिहेक्टर रूख", "Tree per ha", var_type="number", source="field_inventory")
_reg("fi_growing_stock_m3_per_ha", "A", "प्रतिहेक्टर वन मौज्दात (m³)", "Growing Stock per ha", var_type="number", source="field_inventory")
_reg("fi_basal_area_m2_per_ha", "A", "प्रतिहेक्टर आधार क्षेत्र", "Basal Area per ha", var_type="number", source="field_inventory")
_reg("fi_regeneration_condition", "A", "पुनरुत्पादन अवस्था", "Regeneration Condition", source="field_inventory")
_reg("fi_forest_condition", "A", "वन अवस्था", "Forest Condition", source="field_inventory")
_reg("fi_mai_percent", "A", "MAI प्रतिशत", "MAI Percent", var_type="number", source="field_inventory", precision=1)
_reg("fi_agb_t_per_ha", "A", "प्रतिहेक्टर AGB (टन)", "AGB t/ha", var_type="number", source="field_inventory", precision=3)
_reg("fi_bgb_t_per_ha", "A", "प्रतिहेक्टर BGB (टन)", "BGB t/ha", var_type="number", source="field_inventory", precision=3)
_reg("fi_total_biomass_t_per_ha", "A", "प्रतिहेक्टर कुल जैविक पदार्थ", "Total Biomass t/ha", var_type="number", source="field_inventory", precision=3)
_reg("fi_carbon_stock_tc_per_ha", "A", "प्रतिहेक्टर कार्बन मौज्दात", "Carbon Stock tC/ha", var_type="number", source="field_inventory", precision=3)
_reg("fi_co2_equivalent_tco2_per_ha", "A", "प्रतिहेक्टर CO₂ समतुल्य", "CO₂ Equivalent tCO₂/ha", var_type="number", source="field_inventory", precision=3)
_reg("fi_weighted_wood_density", "A", "भारित काठ घनत्व", "Weighted Wood Density", var_type="number", source="field_inventory", precision=4)
_reg("fi_species_block_growing_stock", "A", "ब्लक अनुसार प्रजाति वन मौज्दात (पोल+रूख)", "Block-wise Species Growing Stock (Pole+Tree)", var_type="list", source="field_inventory")
_reg("fi_block_regeneration_status", "A", "वन खन्ड अनुसार पुनरोत्पादनको स्थिति", "Forest Block-wise Regeneration Status", var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_growing_stock", "A", "ब्लक अनुसार DBH वर्ग वन मौज्दात", "Block-wise DBH Class Growing Stock", var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_growing_stock_np", "A", "ब्लक अनुसार DBH वर्ग वन मौज्दात (नेपाली)", "Block-wise DBH Class Growing Stock (Nepali)", var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_ag_np", "A",
     "ब्यास क्लास अनुसार प्रति हेक्टर मौज्दात (एड्भान्स ग्रोथ र परिपक्व रूख)",
     "DBH Class Growing Stock — Advance Growth & Mature Tree (Nepali)",
     var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_advance_np", "A",
     "एड्भान्स ग्रोथ (१०-४० से.मी.) अनुसार प्रति हेक्टर मौज्दात",
     "Advance Growth (10-40 cm) Growing Stock per ha (Nepali)",
     var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_mature_np", "A",
     "परिपक्व रूख (>४० से.मी.) अनुसार प्रति हेक्टर मौज्दात",
     "Mature Tree (>40 cm) Growing Stock per ha (Nepali)",
     var_type="list", source="field_inventory")
_reg("fi_block_summaries", "A", "ब्लक अनुसार पूर्ण नतिजा", "Block-wise Full Results", var_type="list", source="field_inventory")
_reg("fi_block_tree_count_per_ha", "A",
     "वन ब्लक अनुसार प्रति हेक्टर विरूवा, लाथ्रा, पोल तथा रूखको संख्या",
     "Block-wise Trees per Hectare (Regen/Sapling/Pole/Tree)",
     var_type="list", source="field_inventory")
_reg("fi_block_pole_tree_volume", "A",
     "ब्लक अनुसार प्रति हेक्टर पोल (खाँवा) तथा रूखको काठ दाउराको परिणाम घ.मी.",
     "Block-wise Pole & Tree Timber/Firewood Volume m³/ha",
     var_type="list", source="field_inventory")
_reg("fi_block_growing_stock", "A",
     "वन ब्लक अनुसार काठ, दाउरा तथा जम्मा वृद्धि मौज्दात (Growing Stock) प्रति हेक्टर",
     "Block-wise Growing Stock (Timber/Firewood/Total) m³/ha",
     var_type="list", source="field_inventory")
_reg("fi_block_basal_area", "A",
     "ब्लक अनुसार प्रति हेक्टर वेसल एरीया",
     "Block-wise Basal Area m²/ha",
     var_type="list", source="field_inventory")
_reg("fi_block_satellite_volume", "A",
     "NASA/ORNL/biomass_carbon_density/v1 को अधारमा प्रति हेक्टर ग्रोइङ्स्टक अनुमान (घ.मी. प्रति हेक्टर)",
     "Block-wise Satellite-derived Growing Stock m³/ha",
     var_type="list", source="field_inventory")
_reg("fi_block_condition_growth", "A",
     "ब्लक अनुसार पुनरोत्पादन तथा वनको अवस्था र वार्षिक वृद्धि निर्धारण",
     "Block-wise Regeneration/Forest Condition & MAI%",
     var_type="list", source="field_inventory")
_reg("fi_block_biomass_carbon", "A",
     "(IPCC/REDD+) अनुसारको वनश्रोत सर्भेक्षणको अधारमा बायोमास तथा कार्वनको अनुमान",
     "Block-wise Biomass & Carbon (IPCC/REDD+)",
     var_type="list", source="field_inventory")
_reg("fi_mai_table", "A", "वार्षिक वृद्धि तालिका (m³/ha/yr)", "Annual Increment (MAI) Table", var_type="list", source="field_inventory")
_reg("fi_aah_table", "A", "वार्षिक स्वीकार्य कटान तालिका (m³/ha/yr)", "Annual Allowable Cut (AAH) Table", var_type="list", source="field_inventory")
_reg("fi_species_composition", "A", "प्रजाति संरचना (प्रतिशत)", "Species Composition (%)", var_type="dict", source="field_inventory")
_reg("fi_dominant_species", "A", "मुख्य प्रजाति", "Dominant Species", var_type="list", source="field_inventory")
_reg("fi_co_dominant_species", "A", "सह-मुख्य प्रजाति", "Co-dominant Species", var_type="list", source="field_inventory")
_reg("fi_associated_species", "A", "आनुषंगिक प्रजाति", "Associated Species", var_type="list", source="field_inventory")
_reg("fi_fast_growing_species", "A", "द्रुत बृद्धि हुने प्रजाति", "Fast Growing Species", var_type="list", source="field_inventory")
_reg("fi_moderate_growing_species", "A", "मध्यम बृद्धि हुने प्रजाति", "Moderate Growing Species", var_type="list", source="field_inventory")
_reg("fi_slow_growing_species", "A", "सुस्त बृद्धि हुने प्रजाति", "Slow Growing Species", var_type="list", source="field_inventory")
_reg("fi_species_volume_by_block", "A", "ब्लक अनुसार प्रजाति आयतन", "Block-wise Species Volume", var_type="list", source="field_inventory")

# A10b: Total Inventory — कुल मौज्दात (Absolute quantities from per-hectare data)
# Scalar forest-wide totals
_reg("ti_available", "A", "कुल मौज्दात उपलब्ध", "Total Inventory Available", var_type="boolean", source="field_inventory")
_reg("ti_effective_area_ha", "A", "प्रभावकारी क्षेत्रफल (हे)", "Effective Area (ha)", var_type="number", source="field_inventory")
_reg("ti_total_blocks", "A", "कुल ब्लक सङ्ख्या", "Total Blocks", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_plots", "A", "कुल नमूना प्लट", "Total Sample Plots", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_regeneration", "A", "कुल पुनरुत्पादन (सङ्ख्या)", "Total Regeneration (count)", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_sapling", "A", "कुल लाथ्रा (सङ्ख्या)", "Total Sapling (count)", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_pole", "A", "कुल पोल/खाँवा (सङ्ख्या)", "Total Pole (count)", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_tree", "A", "कुल रूख (सङ्ख्या)", "Total Tree (count)", var_type="number", source="field_inventory", precision=0)
_reg("ti_total_growing_stock_m3", "A", "कुल वन मौज्दात (m³)", "Total Growing Stock (m³)", var_type="number", source="field_inventory")
_reg("ti_total_basal_area_m2", "A", "कुल आधार क्षेत्र (m²)", "Total Basal Area (m²)", var_type="number", source="field_inventory")
_reg("ti_total_mai_m3_per_year", "A", "कुल वार्षिक वृद्धि (m³/वर्ष)", "Total MAI (m³/yr)", var_type="number", source="field_inventory")
_reg("ti_total_aah_m3_per_year", "A", "कुल वार्षिक स्वीकार्य कटानी (m³/वर्ष)", "Total AAH (m³/yr)", var_type="number", source="field_inventory")
_reg("ti_total_agb_tonnes", "A", "कुल जमिन माथिको बायोमास (टन)", "Total AGB (tonnes)", var_type="number", source="field_inventory", precision=3)
_reg("ti_total_bgb_tonnes", "A", "कुल जमिन मुनिको बायोमास (टन)", "Total BGB (tonnes)", var_type="number", source="field_inventory", precision=3)
_reg("ti_total_biomass_tonnes", "A", "कुल जैविक पदार्थ (टन)", "Total Biomass (tonnes)", var_type="number", source="field_inventory", precision=3)
_reg("ti_total_carbon_tc", "A", "कुल कार्बन मौज्दात (tC)", "Total Carbon Stock (tC)", var_type="number", source="field_inventory", precision=3)
_reg("ti_total_co2_tco2", "A", "कुल CO₂ समतुल्य (tCO₂)", "Total CO₂ Equivalent (tCO₂)", var_type="number", source="field_inventory", precision=3)
_reg("ti_weighted_wood_density", "A", "भारित काठ घनत्व", "Weighted Wood Density", var_type="number", source="field_inventory", precision=4)

# Block-wise list variables (absolute / कुल मौज्दात)
_reg("ti_block_summaries", "A", "ब्लक अनुसार कुल मौज्दात (पूर्ण नतिजा)", "Block-wise Total Inventory (Full Results)", var_type="list", source="field_inventory")
_reg("ti_block_tree_count_total", "A", "ब्लक अनुसार कुल रूख सङ्ख्या", "Block-wise Total Tree Count", var_type="list", source="field_inventory")
_reg("ti_block_pole_tree_volume", "A", "ब्लक अनुसार कुल पोल तथा रूख आयतन", "Block-wise Total Pole & Tree Volume", var_type="list", source="field_inventory")
_reg("ti_block_growing_stock", "A", "ब्लक अनुसार कुल वृद्धि मौज्दात", "Block-wise Total Growing Stock", var_type="list", source="field_inventory")
_reg("ti_block_basal_area", "A", "ब्लक अनुसार कुल आधार क्षेत्र", "Block-wise Total Basal Area", var_type="list", source="field_inventory")
_reg("ti_block_satellite_volume", "A", "ब्लक अनुसार कुल उपग्रह-आधारित आयतन", "Block-wise Total Satellite Volume", var_type="list", source="field_inventory")
_reg("ti_block_condition_growth", "A", "ब्लक अनुसार अवस्था तथा वार्षिक वृद्धि", "Block-wise Condition & MAI%", var_type="list", source="field_inventory")
_reg("ti_block_biomass_carbon", "A", "ब्लक अनुसार कुल बायोमास तथा कार्बन", "Block-wise Total Biomass & Carbon", var_type="list", source="field_inventory")
_reg("ti_block_regeneration_status", "A", "ब्लक अनुसार पुनरोत्पादन अवस्था", "Block-wise Regeneration Status", var_type="list", source="field_inventory")
_reg("ti_mai_table", "A", "वार्षिक वृद्धि तालिका (कुल)", "MAI Table (Absolute)", var_type="list", source="field_inventory")
_reg("ti_aah_table", "A", "वार्षिक स्वीकार्य कटानी तालिका (कुल)", "AAH Table (Absolute)", var_type="list", source="field_inventory")
_reg("ti_species_block_growing_stock", "A", "ब्लक अनुसार प्रजाति कुल मौज्दात", "Block-wise Species Total Growing Stock", var_type="list", source="field_inventory")
_reg("ti_species_volume_by_block", "A", "ब्लक अनुसार प्रजाति कुल आयतन", "Block-wise Species Total Volume", var_type="list", source="field_inventory")

# Species composition (absolute values)
_reg("ti_species_composition_absolute", "A", "प्रजाति संरचना (कुल मौज्दात)", "Species Composition (Absolute)", var_type="dict", source="field_inventory")
_reg("ti_dominant_species_absolute", "A", "मुख्य प्रजाति (कुल)", "Dominant Species (Absolute)", var_type="list", source="field_inventory")
_reg("ti_co_dominant_species_absolute", "A", "सह-मुख्य प्रजाति (कुल)", "Co-dominant Species (Absolute)", var_type="list", source="field_inventory")
_reg("ti_associated_species_absolute", "A", "आनुषंगिक प्रजाति (कुल)", "Associated Species (Absolute)", var_type="list", source="field_inventory")
_reg("ti_fast_growing_species_total", "A", "द्रुत वृद्धि प्रजाति कुल आयतन", "Fast Growing Species Total", var_type="number", source="field_inventory")
_reg("ti_moderate_growing_species_total", "A", "मध्यम वृद्धि प्रजाति कुल आयतन", "Moderate Growing Species Total", var_type="number", source="field_inventory")
_reg("ti_slow_growing_species_total", "A", "सुस्त वृद्धि प्रजाति कुल आयतन", "Slow Growing Species Total", var_type="number", source="field_inventory")

# Chart variables for Total Inventory
_reg("ti_chart_block_stock_pie", "A", "ब्लक अनुसार ग्रोइङ स्टक पाई चार्ट", "Block-wise Growing Stock Pie Chart", var_type="dict", source="field_inventory")
_reg("ti_chart_block_comparison_bar", "A", "ब्लक तुलना बार चार्ट", "Block Comparison Bar Chart", var_type="dict", source="field_inventory")
_reg("ti_chart_dbh_class_bar", "A", "DBH वर्ग आयतन बार चार्ट", "DBH Class Volume Bar Chart", var_type="dict", source="field_inventory")

# A10c: Total Inventory — new table variables for OP document
_reg("ti_block_area_table", "A", "ब्लक क्षेत्रफल — प्रभावकारी वन आवरण",
     "Block Area — Effective Forest Cover",
     var_type="list", source="field_inventory")
_reg("ti_species_dbh_class_table", "A", "प्रजाति अनुसार DBH क्लास मौज्दात",
     "Species-wise DBH Class Growing Stock",
     var_type="list", source="field_inventory")
_reg("ti_forest_dbh_class_table", "A", "पुरै वन क्षेत्र — प्रजाति अनुसार DBH क्लास मौज्दात",
     "Entire Forest — Species-wise DBH Class",
     var_type="list", source="field_inventory")
_reg("ti_dbh_class_totals_table", "A", "DBH क्लास अनुसार कुल मौज्दात",
     "DBH Class Total Growing Stock",
     var_type="list", source="field_inventory")
_reg("ti_dbh_class_perha_table", "A", "DBH क्लास अनुसार कुल मौज्दात (प्रति हे.)",
     "DBH Class Total Growing Stock (per ha)",
     var_type="list", source="field_inventory")
_reg("ti_dbh_mai_table", "A", "DBH क्लास अनुसार MAI",
     "DBH Class-wise MAI",
     var_type="list", source="field_inventory")
_reg("ti_dbh_aah_table", "A", "DBH क्लास अनुसार AAH",
     "DBH Class-wise AAH",
     var_type="list", source="field_inventory")
_reg("ti_species_composition_table", "A", "प्रजाति संरचना (स्थानीय नाम)",
     "Species Composition (Local Name)",
     var_type="list", source="field_inventory")
_reg("ti_block_productivity_table", "A", "ब्लक अनुसार उत्पादनसिल संचिती",
     "Block-wise Productive Growing Stock",
     var_type="list", source="field_inventory")
_reg("ti_economic_valuation_table", "A", "आर्थिक मूल्याङ्कन",
     "Economic Valuation",
     var_type="list", source="field_inventory")
_reg("ti_sustainability_table", "A", "दिगोपन सूचकांक",
     "Sustainability Index",
     var_type="list", source="field_inventory")

# A10d: Total Inventory — section narrations (auto-generated)
_reg("section:ti_block_area_narration", "A", "ब्लक क्षेत्रफल विवरण (स्वतः उत्पन्न)",
     "Block Area Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_forest_total_narration", "A", "सामुदायिक वन कुल योग विवरण (स्वतः उत्पन्न)",
     "Forest Total Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_block_growing_stock_narration", "A", "ब्लक मौज्दात विवरण (स्वतः उत्पन्न)",
     "Block Growing Stock Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_species_stock_narration", "A", "प्रजाति मौज्दात विवरण (स्वतः उत्पन्न)",
     "Species Stock Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_species_dbh_narration", "A", "प्रजाति DBH वर्ग मौज्दात विवरण (स्वतः उत्पन्न)",
     "Species DBH Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_forest_dbh_narration", "A", "पुरै वन DBH वर्ग विवरण (स्वतः उत्पन्न)",
     "Forest DBH Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_dbh_total_narration", "A", "DBH वर्ग कुल मौज्दात विवरण (स्वतः उत्पन्न)",
     "DBH Class Total Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_dbh_perha_narration", "A", "DBH वर्ग प्रति हे. मौज्दात विवरण (स्वतः उत्पन्न)",
     "DBH Class Per Ha Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_dbh_mai_narration", "A", "DBH वर्ग MAI विवरण (स्वतः उत्पन्न)",
     "DBH Class MAI Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_dbh_aah_narration", "A", "DBH वर्ग AAH विवरण (स्वतः उत्पन्न)",
     "DBH Class AAH Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_species_composition_narration", "A", "प्रजाति संरचना विवरण (स्वतः उत्पन्न)",
     "Species Composition Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_productivity_narration", "A", "उत्पादनसिल संचिती विवरण (स्वतः उत्पन्न)",
     "Productivity Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_economic_narration", "A", "आर्थिक मूल्याङ्कन विवरण (स्वतः उत्पन्न)",
     "Economic Valuation Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:ti_sustainability_narration", "A", "दिगोपन सूचकांक विवरण (स्वतः उत्पन्न)",
     "Sustainability Index Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)

_reg("section:field_inventory_narration", "A",
     "क्षेत्र सर्वेक्षण विवरण (स्वतः उत्पन्न)", "Field Inventory Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sampling_narration", "A",
     "स्याम्पलिङ विवरण (स्वतः उत्पन्न)", "Sampling Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:fieldbook_narration", "A",
     "फिल्डबुक विवरण (स्वतः उत्पन्न)", "Fieldbook Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:household_narration", "A",
     "घरधुरी विवरण (स्वतः उत्पन्न)", "Household Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:committee_narration", "A",
     "समिति विवरण (स्वतः उत्पन्न)", "Committee Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:user_group_narration", "A",
     "उपभोक्ता समूह विवरण (स्वतः उत्पन्न)", "User Group Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:demand_supply_narration", "A",
     "माग/आपूर्ति विवरण (स्वतः उत्पन्न)", "Demand & Supply Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)

# Tree Mapping Analysis Narrations
_reg("section:sm_hierarchy_narration", "A",
     "स्थानिक स्तर रूख सारांश विवरण (स्वतः उत्पन्न)", "Hierarchy Summary Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_species_narration", "A",
     "प्रजाति संरचना विवरण (स्वतः उत्पन्न)", "Species Composition Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_dbh_narration", "A",
     "DBH वर्ग विवरण (स्वतः उत्पन्न)", "DBH Class Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_stand_type_narration", "A",
     "स्ट्यान्ड प्रकार विवरण (स्वतः उत्पन्न)", "Stand Type Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_carbon_narration", "A",
     "कार्बन मौज्दात विवरण (स्वतः उत्पन्न)", "Carbon Stock Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_volume_narration", "A",
     "आयतन वितरण विवरण (स्वतः उत्पन्न)", "Volume Distribution Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_mother_tree_narration", "A",
     "माँउ रूख कभरेज विवरण (स्वतः उत्पन्न)", "Mother Tree Coverage Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)
_reg("section:sm_felling_narration", "A",
     "कटानी रूख विश्लेषण विवरण (स्वतः उत्पन्न)", "Felling Tree Analysis Narration (Auto-generated)",
     var_type="string", source="section_generator", auto_populate=True)

# A11: Sampling (14)
_reg("sampling_available", "A", "नमूना योजना उपलब्ध", "Sampling Available", var_type="boolean", source="sampling")
_reg("sampling_type", "A", "नमूना प्रकार", "Sampling Type", source="sampling")
_reg("sampling_total_points", "A", "कुल नमूना बिन्दु", "Total Sample Points", var_type="number", source="sampling")
_reg("sampling_total_blocks", "A", "कुल ब्लक सङ्ख्या", "Total Blocks", var_type="number", source="sampling")
_reg("sampling_plot_shape", "A", "प्लट आकार", "Plot Shape", source="sampling")
_reg("sampling_plot_radius_m", "A", "प्लट अर्धव्यास (मि)", "Plot Radius (m)", var_type="number", source="sampling")
_reg("sampling_intensity_per_ha", "A", "प्रतिहेक्टर तीव्रता", "Intensity per ha", var_type="number", source="sampling")
_reg("sampling_requested_intensity", "A", "अनुरोध गरिएको नमुना इन्टेन्सिटी", "Requested Intensity", var_type="number", source="sampling")
_reg("sampling_actual_intensity", "A", "वास्तविक नमुना इन्टेन्सिटी", "Actual Sampling Intensity", var_type="number", source="sampling")
_reg("sampling_block_summary", "A", "ब्लक अनुसार नमुनाप्लट विवरण तालीका", "Per-Block Sampling Summary", var_type="list", source="sampling")
_reg("sampling_point_locations", "A", "नमुना प्लट स्थान विवरण तालीका", "Sample Point Locations", var_type="list", source="sampling")
_reg("sampling_forest_area_ha", "A", "वन क्षेत्रफल (हे)", "Forest Area (ha)", var_type="number", source="sampling")
_reg("sampling_plot_area_sqm", "A", "प्लट क्षेत्रफल (वर्गमि)", "Plot Area (sqm)", var_type="number", source="sampling")
_reg("sampling_total_sampled_area_ha", "A", "जम्मा नमुना क्षेत्रफल (हे)", "Total Sampled Area (ha)", var_type="number", source="sampling")

# A12: Household (13)
_reg("hh_available", "A", "घरधुरी डाटा उपलब्ध", "Household Data Available", var_type="boolean", source="household")
_reg("hh_total_households", "A", "कुल घरधुरी", "Total Households", var_type="number", source="household")
_reg("hh_total_population", "A", "कुल जनसंख्या", "Total Population", var_type="number", source="household")
_reg("hh_total_male", "A", "पुरुष जनसंख्या", "Male Population", var_type="number", source="household")
_reg("hh_total_female", "A", "महिला जनसंख्या", "Female Population", var_type="number", source="household")
_reg("hh_prosperity_distribution", "A", "समृद्धि वितरण", "Prosperity Distribution", var_type="dict", source="household")
_reg("hh_caste_distribution", "A", "जाति वितरण", "Caste Distribution", var_type="dict", source="household")
_reg("hh_timber_demand_cft", "A", "काठ माग (cft)", "Timber Demand (cft)", var_type="number", source="household")
_reg("hh_firewood_demand_bhari", "A", "दाउरा माग (भारी)", "Firewood Demand (bhari)", var_type="number", source="household")
_reg("hh_forest_based_occupation", "A", "वन पेशा भएका घरधुरी", "Forest-based Occupation HH", var_type="number", source="household")
_reg("chart:hh_caste_pie", "A",
     "जाति वितरण (पाई चार्ट)",
     "Caste Distribution Pie Chart",
     var_type="dict", source="household")
_reg("chart:hh_prosperity_bar", "A",
     "समृद्धि वितरण (बार चार्ट)",
     "Prosperity Distribution Bar Chart",
     var_type="dict", source="household")
_reg("chart:hh_demand_supply_bar", "A",
     "माग र आपूर्ति तुलना (बार चार्ट)",
     "Demand & Supply Comparison Bar Chart",
     var_type="dict", source="household")
_reg("chart:demand_supply_bar", "A",
     "माग र आपूर्ति ब्रेकडाउन (बार चार्ट)",
     "Demand & Supply Breakdown Bar Chart",
     var_type="dict", source="household")
_reg("chart:demand_supply_deficit_bar", "A",
     "बचत/कमी तुलना (बार चार्ट)",
     "Surplus/Deficit Comparison Bar Chart",
     var_type="dict", source="household")
_reg("hh_records", "A",
     "घरपरिवारको विस्तृत तालिका",
     "Household Records Table",
     var_type="list", source="household")

# A13: Committees (9)
_reg("uc_members", "A", "उपभोक्ता समिति सदस्य", "User Committee Members", var_type="list", source="committee")
_reg("uc_total_members", "A", "उपभोक्ता समिति सदस्य सङ्ख्या", "UC Total Members", var_type="number", source="committee")
_reg("ac_members", "A", "सल्लाहकार समिति सदस्य", "Advisory Committee Members", var_type="list", source="committee")
_reg("ac_total_members", "A", "सल्लाहकार समिति सदस्य सङ्ख्या", "AC Total Members", var_type="number", source="committee")
_reg("fc_members", "A", "वित्त समिति सदस्य", "Finance Committee Members", var_type="list", source="committee")
_reg("fc_total_members", "A", "वित्त समिति सदस्य सङ्ख्या", "FC Total Members", var_type="number", source="committee")
_reg("uc_gender_distribution", "A", "लैङ्गिक वितरण", "Gender Distribution", var_type="dict", source="committee")
_reg("uc_position_distribution", "A", "पद वितरण", "Position Distribution", var_type="dict", source="committee")
_reg("uc_caste_distribution", "A", "जातीय वितरण", "Caste Distribution", var_type="dict", source="committee")
_reg("cf_chairperson", "A", "सामुदायिक वन अध्यक्ष", "CF Chairperson", source="committee", resolver="resolve_chairperson")

# A14: Biodiversity (12)
_reg("bio_available", "A", "जैविक विविधता उपलब्ध", "Biodiversity Available", var_type="boolean", source="biodiversity")
_reg("bio_total_species", "A", "कुल जैविक प्रजाति", "Total Biodiversity Species", var_type="number", source="biodiversity")
_reg("bio_vegetation_count", "A", "वनस्पति प्रजाति सङ्ख्या", "Vegetation Count", var_type="number", source="biodiversity")
_reg("bio_animal_count", "A", "जनावर प्रजाति सङ्ख्या", "Animal Count", var_type="number", source="biodiversity")
_reg("bio_protected_count", "A", "संरक्षित प्रजाति सङ्ख्या", "Protected Species Count", var_type="number", source="biodiversity")
_reg("bio_invasive_count", "A", "मिचाहा प्रजाति सङ्ख्या", "Invasive Species Count", var_type="number", source="biodiversity")
_reg("bio_iucn_cr", "A", "संकटग्रस्त प्रजाति (CR)", "Critically Endangered (CR)", var_type="number", source="biodiversity")
_reg("bio_iucn_en", "A", "लोपोन्मुख प्रजाति (EN)", "Endangered (EN)", var_type="number", source="biodiversity")
_reg("bio_iucn_vu", "A", "असुरक्षित प्रजाति (VU)", "Vulnerable (VU)", var_type="number", source="biodiversity")
_reg("bio_sub_category_breakdown", "A", "उप-प्रकार अनुसार विवरण", "Sub-category Breakdown", var_type="dict", source="biodiversity")
_reg("bio_vegetation", "A", "वनस्पति विवरण", "Vegetation Details", var_type="list", source="biodiversity")
_reg("bio_animals", "A", "जनावर विवरण", "Animal Details", var_type="list", source="biodiversity")

# A15: Activities (4)
_reg("activities_available", "A", "क्रियाकलाप उपलब्ध", "Activities Available", var_type="boolean", source="activities")
_reg("activities_total", "A", "कुल क्रियाकलाप", "Total Activities", var_type="number", source="activities")
_reg("activities_total_budget", "A", "कुल बजेट (रु)", "Total Budget (Rs)", var_type="number", source="activities")
_reg("activities_list", "A", "क्रियाकलाप सूची", "Activities List", var_type="list", source="activities")

# A16: Yearly Plan — 10-Year Activity Breakdown (8)
_reg("ya_available", "A", "वार्षिक योजना उपलब्ध", "Yearly Plan Available",
     var_type="boolean", source="yearly_activities")
_reg("ya_year_summary", "A", "वर्ष अनुसार क्रियाकलाप सारांश",
     "Year-wise Activity Summary", var_type="list", source="yearly_activities")
_reg("ya_plan_matrix", "A", "१० वर्षे योजना तालिका (क्रियाकलाप × वर्ष)",
     "10-Year Plan Matrix (Activity × Year)", var_type="list", source="yearly_activities")
_reg("ya_program_budget", "A", "कार्यक्रम अनुसार बजेट विवरण",
     "Program-wise Budget Breakdown", var_type="list", source="yearly_activities")
_reg("ya_total_budget_by_year", "A", "वर्ष अनुसार कुल बजेट",
     "Total Budget per Year", var_type="dict", source="yearly_activities")
_reg("ya_total_ten_year_budget", "A", "१० वर्षे कुल बजेट",
     "Total 10-Year Budget", var_type="number", source="yearly_activities")
_reg("ya_program_pie_data", "A", "कार्यक्रम अनुसार बजेट पाई डाटा",
     "Program Budget Pie Data", var_type="dict", source="yearly_activities")
_reg("ya_budget_year_trend", "A", "वर्ष अनुसार बजेट प्रवृत्ति",
     "Budget Year Trend", var_type="dict", source="yearly_activities")
_reg("ya_activity_plan_detail", "A", "क्रियाकलाप योजना विस्तृत विवरण",
     "Activity Plan Detail (CSV-style)", var_type="list", source="yearly_activities")

# A17: User Group (20)
_reg("ug_available", "A", "उपभोक्ता समूह डाटा उपलब्ध", "User Group Available", var_type="boolean", source="user_group")
_reg("ug_total_settlements", "A", "कुल बस्ती", "Total Settlements", var_type="number", source="user_group")
_reg("ug_buildings", "A", "बस्ती विवरण", "Settlement Details", var_type="list", source="user_group")

# Settlement / Building Breakdown
_reg("ug_total_buildings", "A", "कुल भवन", "Total Buildings", var_type="number", source="user_group")
_reg("ug_total_building_area_m2", "A", "कुल भवन क्षेत्रफल (m²)", "Total Building Area (m²)", var_type="number", source="user_group")
_reg("ug_avg_building_size_m2", "A", "औसत भवन आकार (m²)", "Avg Building Size (m²)", var_type="number", source="user_group")
_reg("ug_small_buildings", "A", "साना भवन (<50 m²)", "Small Buildings (<50 m²)", var_type="number", source="user_group")
_reg("ug_medium_buildings", "A", "मध्यम भवन (50-150 m²)", "Medium Buildings (50-150 m²)", var_type="number", source="user_group")
_reg("ug_large_buildings", "A", "ठुला भवन (>150 m²)", "Large Buildings (>150 m²)", var_type="number", source="user_group")
_reg("ug_small_pct", "A", "साना भवन प्रतिशत", "Small Buildings %", var_type="number", source="user_group")
_reg("ug_medium_pct", "A", "मध्यम भवन प्रतिशत", "Medium Buildings %", var_type="number", source="user_group")
_reg("ug_large_pct", "A", "ठुला भवन प्रतिशत", "Large Buildings %", var_type="number", source="user_group")

# Land Cover / Area Summary
_reg("ug_user_group_area_ha", "A", "उपभोक्ता समूह क्षेत्रफल (हे)", "User Group Area (ha)", var_type="number", source="user_group")
_reg("ug_forest_overlap_area_ha", "A", "वन ओभरल्याप क्षेत्रफल (हे)", "Forest Overlap Area (ha)", var_type="number", source="user_group")
_reg("ug_net_analysis_area_ha", "A", "शुद्ध विश्लेषण क्षेत्रफल (हे)", "Net Analysis Area (ha)", var_type="number", source="user_group")

# Biomass / Volume
_reg("ug_total_biomass_mg", "A", "कुल जैविक पदार्थ (Mg)", "Total Biomass (Mg)", var_type="number", source="user_group")
_reg("ug_total_volume_m3", "A", "कुल आयतन (m³)", "Total Volume (m³)", var_type="number", source="user_group")
_reg("ug_avg_biomass_mg_per_ha", "A", "औसत जैविक पदार्थ (Mg/ha)", "Avg Biomass (Mg/ha)", var_type="number", source="user_group")
_reg("ug_avg_volume_m3_per_ha", "A", "औसत आयतन (m³/ha)", "Avg Volume (m³/ha)", var_type="number", source="user_group")

# Land Cover Classes (list)
_reg("ug_land_cover_classes", "A", "भू-आवरण वर्ग विवरण", "Land Cover Class Details", var_type="list", source="user_group")

# A17: Additional Committee (0 — reuses A13)

# A18: Compartments (6)
_reg("compartment_message", "A",
     "कम्पार्टमेन्ट सन्देश", "Compartment Message",
     source="compartment")
_reg("compartment_summary", "A",
     "कम्पार्टमेन्ट सारांश", "Compartment Summary",
     var_type="list", source="compartment")
_reg("compartment_detail", "A",
     "कम्पार्टमेन्ट विवरण", "Compartment Detail",
     var_type="list", source="compartment")
_reg("compartment_species_composition", "A",
     "कम्पार्टमेन्ट प्रजाति संरचना", "Compartment Species Composition",
     var_type="list", source="compartment")
_reg("compartment_area_breakdown", "A",
     "कम्पार्टमेन्ट क्षेत्रफल विवरण", "Compartment Area Breakdown",
     var_type="list", source="compartment")
_reg("compartment_dbh_distribution", "A",
     "कम्पार्टमेन्ट DBH वितरण", "Compartment DBH Distribution",
     var_type="list", source="compartment")

# ═══════════════════════════════════════════════════════
# Category B: Hybrid Variables (11)
# ═══════════════════════════════════════════════════════
_reg("altitude_min_m", "B", "न्यूनतम उचाई (मि)", "Min Altitude (m)", var_type="number", source="raster", resolver="resolve_hybrid")
_reg("altitude_max_m", "B", "अधिकतम उचाई (मि)", "Max Altitude (m)", var_type="number", source="raster", resolver="resolve_hybrid")
_reg("altitude_mean_m", "B", "औसत उचाई (मि)", "Mean Altitude (m)", var_type="number", source="raster", resolver="resolve_hybrid")
_reg("dominant_slope", "B", "मुख्य भिरालो", "Dominant Slope", source="raster", resolver="resolve_hybrid")
_reg("dominant_aspect", "B", "मुख्य दिशा", "Dominant Aspect", source="raster", resolver="resolve_hybrid")
_reg("dominant_soil", "B", "मुख्य माटो", "Dominant Soil", source="raster", resolver="resolve_hybrid")
_reg("crown_density_pct", "B", "वन मुकुट घनत्व (%)", "Crown Density (%)", var_type="number", source="raster", resolver="resolve_hybrid")
_reg("trees_per_hectare", "B", "प्रतिहेक्टर रूख", "Trees per Hectare", var_type="number", source="inventory", resolver="resolve_hybrid")
_reg("growing_stock_m3_per_ha", "B", "प्रतिहेक्टर वन मौज्दात", "Growing Stock per ha (m³)", var_type="number", source="field_inventory", resolver="resolve_hybrid")
_reg("biomass_t_per_ha", "B", "प्रतिहेक्टर जैविक पदार्थ", "Biomass per ha (t)", var_type="number", source="field_inventory", resolver="resolve_hybrid")
_reg("carbon_stock_tc_per_ha", "B", "प्रतिहेक्टर कार्बन मौज्दात", "Carbon Stock per ha (tC)", var_type="number", source="field_inventory", resolver="resolve_hybrid")

# ═══════════════════════════════════════════════════════
# Category C: User Input Variables (50)
# ═══════════════════════════════════════════════════════
_reg("cf_registration_number", "C", "सामुदायिक वन दर्ता नं.", "CF Registration No", auto_populate=False, resolver="resolve_user_input")
_reg("op_preparation_year", "C", "कार्ययोजना तयारी वर्ष", "OP Preparation Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("cf_code", "C", "सामुदायिक वन कोड", "CF Code", auto_populate=False, resolver="resolve_user_input")
_reg("op_start_fy", "C", "कार्ययोजना सुरू आर्थिक वर्ष", "OP Start FY", auto_populate=False, resolver="resolve_user_input")
_reg("op_end_fy", "C", "कार्ययोजना अन्तिम आर्थिक वर्ष", "OP End FY", auto_populate=False, resolver="resolve_user_input")
_reg("physiography_zone", "C", "भू-आकृति क्षेत्र", "Physiography Zone", auto_populate=False, resolver="resolve_user_input")
_reg("protected_area_status", "C", "संरक्षित क्षेत्र स्थिति", "Protected Area Status", auto_populate=False, resolver="resolve_user_input")
_reg("technical_assistance_org", "C", "प्राविधिक सहयोग संस्था", "Technical Assistance Org", auto_populate=False, resolver="resolve_user_input")
_reg("op_general_assembly_date", "C", "साधारण सभा मिति", "General Assembly Date", auto_populate=False, resolver="resolve_user_input")
_reg("forest_type", "C", "वनको किसिम", "Forest Type", auto_populate=False, resolver="resolve_user_input")
_reg("forest_abundance", "C", "वन बाहुल्यता", "Forest Abundance", auto_populate=False, resolver="resolve_user_input")
_reg("forest_avg_age", "C", "औसत वन उमेर", "Forest Avg Age", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("main_non_timber_fp", "C", "मुख्य गैर-काठ वन पैदावार", "Main Non-Timber FP", auto_populate=False, resolver="resolve_user_input")
_reg("avg_crown_density_pct", "C", "औसत छत्र घनत्व (%)", "Avg Crown Density (%)", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("ug_settlement", "C", "उपभोक्ता समूह बस्ती", "UG Settlement", auto_populate=False, resolver="resolve_user_input")
_reg("prepared_by", "C", "तयार गर्ने", "Prepared By", auto_populate=False, resolver="resolve_user_input")
_reg("reviewed_by", "C", "समीक्षा गर्ने", "Reviewed By", auto_populate=False, resolver="resolve_user_input")
_reg("plan_year_start", "C", "योजना सुरु वर्ष", "Plan Start Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("plan_year_end", "C", "योजना अन्त वर्ष", "Plan End Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("user_group_name", "C", "उपभोक्ता समूहको नाम", "User Group Name", auto_populate=False, resolver="resolve_user_input")
_reg("user_group_code", "C", "दर्ता नं.", "Registration No", auto_populate=False, resolver="resolve_user_input")
_reg("cf_handover_date", "C", "हस्तान्तरण मिति", "Handover Date", auto_populate=False, resolver="resolve_user_input")
_reg("plan_language", "C", "भाषा", "Language", auto_populate=False, resolver="resolve_user_input")

_reg("kabuliyatnama_date", "C", "कबुलियतिनामा मिति", "Kabuliyatnama Date", auto_populate=False, resolver="resolve_user_input")
_reg("kabuliyatnama_date_year", "C", "कबुलियतिनामा मिति (वर्ष)", "Kabuliyatnama Date Year", var_type="number", auto_populate=False, resolver="resolve_kabuliyatnama_detail")
_reg("kabuliyatnama_date_month", "C", "कबुलियतिनामा मिति (महिना)", "Kabuliyatnama Date Month", var_type="number", auto_populate=False, resolver="resolve_kabuliyatnama_detail")
_reg("kabuliyatnama_date_day", "C", "कबुलियतिनामा मिति (गते)", "Kabuliyatnama Date Day", var_type="number", auto_populate=False, resolver="resolve_kabuliyatnama_detail")
_reg("kabuliyatnama_date_sentence", "C", "कबुलियतिनामा मिति (वाक्य)", "Kabuliyatnama Date Sentence", auto_populate=False, resolver="resolve_kabuliyatnama_detail")

# ── Metadata Form Fields (boundaries, locations, identifiers) ──
_reg("sn_number", "C", "क्रम संख्या", "SN Number", auto_populate=False, resolver="resolve_user_input")
_reg("province_guideline_year", "C", "प्रदेश कार्यविधि वर्ष", "Province Guideline Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("division", "C", "डिभिजन", "Division", auto_populate=False, resolver="resolve_user_input")
_reg("sub_division", "C", "सब डिभिजन", "Sub Division", auto_populate=False, resolver="resolve_user_input")
_reg("sub_division_chief", "C", "सब डिभिजन प्रमुख", "Sub Division Chief", auto_populate=False, resolver="resolve_user_input")
_reg("forest_management_section_chief", "C", "वन व्यवस्थापन शाखा प्रमुख", "Forest Management Section Chief", auto_populate=False, resolver="resolve_user_input")
_reg("division_forest_officer", "C", "डिभिजन प्रमुख", "Division Forest Officer", auto_populate=False, resolver="resolve_user_input")
_reg("forest_municipality", "C", "स्थानीय तह", "Municipality", auto_populate=False, resolver="resolve_user_input")
_reg("forest_ward", "C", "वार्ड", "Ward", auto_populate=False, resolver="resolve_user_input")
_reg("forest_district", "C", "जिल्ला (वन)", "District (Forest)", auto_populate=False, resolver="resolve_user_input")
_reg("ug_district", "C", "जिल्ला (उपभोक्ता)", "District (User Group)", auto_populate=False, resolver="resolve_user_input")
_reg("forest_municipality_type", "C", "स्थानीय तहको प्रकार (वन)", "Municipality Type (Forest)", auto_populate=False, resolver="resolve_user_input")
_reg("ug_municipality_type", "C", "स्थानीय तहको प्रकार (उपभोक्ता)", "Municipality Type (User Group)", auto_populate=False, resolver="resolve_user_input")
_reg("cf_sn_number", "C", "सामुदायिक वन क्रम संख्या", "CF SN Number", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("constitution_approved_year", "C", "विधान स्वीकृति मिति", "Constitution Approved Date", auto_populate=False, resolver="resolve_user_input")
_reg("user_group_reg_no", "C", "समूह दर्ता नं.", "User Group Reg No", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("cf_name", "C", "सामुदायिक वनको नाम", "CF Name", auto_populate=False, resolver="resolve_user_input")
_reg("cf_boundary_east", "C", "पूर्व सिमाना", "East Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("cf_boundary_west", "C", "पश्चिम सिमाना", "West Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("cf_boundary_north", "C", "उत्तर सिमाना", "North Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("cf_boundary_south", "C", "दक्षिण सिमाना", "South Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("ug_boundary_east", "C", "उपभोक्ता समूह पूर्व सिमाना", "UG East Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("ug_boundary_west", "C", "उपभोक्ता समूह पश्चिम सिमाना", "UG West Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("ug_boundary_north", "C", "उपभोक्ता समूह उत्तर सिमाना", "UG North Boundary", auto_populate=False, resolver="resolve_user_input")
_reg("ug_boundary_south", "C", "उपभोक्ता समूह दक्षिण सिमाना", "UG South Boundary", auto_populate=False, resolver="resolve_user_input")


# ═══════════════════════════════════════════════════════
# Category D: Computed Variables (10)
# ═══════════════════════════════════════════════════════
_reg("total_plan_area_ha", "D", "योजना कुल क्षेत्रफल", "Total Plan Area (ha)", var_type="number", resolver="resolve_computed", compute_fn="compute_total_plan_area")
_reg("forest_area_ha", "D", "वन क्षेत्रफल", "Forest Area (ha)", var_type="number", resolver="resolve_computed", compute_fn="compute_forest_area")
_reg("non_forest_area_ha", "D", "गैर-वन क्षेत्रफल", "Non-forest Area (ha)", var_type="number", resolver="resolve_computed", compute_fn="compute_non_forest_area")
_reg("forest_pct", "D", "वन प्रतिशत", "Forest Percentage", var_type="number", resolver="resolve_computed", compute_fn="compute_forest_pct")
_reg("total_growing_stock_m3", "D", "कुल वन मौज्दात (m³)", "Total Growing Stock (m³)", var_type="number", resolver="resolve_computed", compute_fn="compute_total_growing_stock")
_reg("total_carbon_stock_tc", "D", "कुल कार्बन मौज्दात (tC)", "Total Carbon Stock (tC)", var_type="number", resolver="resolve_computed", compute_fn="compute_total_carbon_stock")
_reg("total_co2_tco2", "D", "कुल CO₂ (tCO₂)", "Total CO₂ (tCO₂)", var_type="number", resolver="resolve_computed", compute_fn="compute_total_co2")
_reg("annual_increment_m3", "D", "वार्षिक वृद्धि (m³)", "Annual Increment (m³)", var_type="number", resolver="resolve_computed", compute_fn="compute_annual_increment")
_reg("household_forest_area_per_hh", "D", "प्रति घरधुरी वन क्षेत्र", "Forest Area per HH (ha)", var_type="number", resolver="resolve_computed", compute_fn="compute_forest_per_hh")
_reg("plan_years_range", "D", "योजना अवधि (साल)", "Plan Years Range", var_type="string", resolver="resolve_computed", compute_fn="compute_plan_years_range")
_reg("cf_area_provided", "D", "प्रदान गरिएको क्षेत्रफल (हे)", "CF Area Provided (ha)", var_type="number", resolver="resolve_computed", compute_fn="compute_cf_area_provided")

# ═══════════════════════════════════════════════════════
# Category E: Section Content (5)
# ═══════════════════════════════════════════════════════
_reg("section_6_previous_review", "E", "विगत समीक्षा (पाठ)", "Previous Review Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_8_production", "E", "उत्पादन (पाठ)", "Production Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_16_prohibited", "E", "निषेधित कार्य (पाठ)", "Prohibited Activities Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_17_penalties", "E", "वन अपराध (पाठ)", "Penalties Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_18_misc", "E", "विविध (पाठ)", "Miscellaneous Text", source="template", auto_populate=True, resolver="resolve_section_content")

# ═══════════════════════════════════════════════════════
# Section Generator Variables (20) — auto-generated Nepali narratives
# ═══════════════════════════════════════════════════════
_reg("section:forest_summary", "A", "वन सारांश विवरण", "Forest Summary Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:slope_analysis", "A", "भिरालो विश्लेषण विवरण", "Slope Analysis Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:elevation_profile", "A", "उचाइ विवरण", "Elevation Profile Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:aspect_analysis", "A", "दिशा विश्लेषण विवरण", "Aspect Analysis Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:forest_health", "A", "वन स्वास्थ्य विवरण", "Forest Health Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:forest_type", "A", "वन प्रकार विवरण", "Forest Type Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:species_potential", "A", "सम्भावित प्रजाति विवरण", "Potential Species Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:actual_species", "A", "वास्तविक प्रजाति विवरण", "Actual Species Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:biodiversity", "A", "जैविक विविधता विवरण", "Biodiversity Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:canopy_structure", "A", "वन मुकुट विवरण", "Canopy Structure Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:biomass_carbon", "A", "जैविक पदार्थ तथा कार्बन विवरण", "Biomass & Carbon Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:climate_conditions", "A", "मौसम अवस्था विवरण", "Climate Conditions Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:land_cover", "A", "भू-आवरण विवरण", "Land Cover Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:forest_loss", "A", "वन क्षति विवरण", "Forest Loss Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:fire_loss", "A", "आगलागी क्षति विवरण", "Fire Loss Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:forest_quality", "A", "वन गुणस्तर विवरण (नासा)", "Forest Quality Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:soil_analysis", "A", "माटो विश्लेषण विवरण", "Soil Analysis Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:location_context", "A", "स्थान तथा सन्दर्भ विवरण", "Location & Context Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:species_distribution", "A", "प्रजाति वितरण विवरण", "Species Distribution Section", var_type="string", source="section_generator", auto_populate=True)
_reg("section:accessible_forest", "A", "पहुँचयोग्य वन क्षेत्र विवरण", "Accessible Forest Section", var_type="string", source="section_generator", auto_populate=True)

# ═══════════════════════════════════════════════════════
# Category F: Template Variables (6)
# ═══════════════════════════════════════════════════════
_reg("document_version", "F", "दस्तावेज संस्करण", "Document Version", auto_populate=True, resolver="resolve_template")
_reg("generated_date", "F", "उत्पादन मिति", "Generated Date", auto_populate=True, resolver="resolve_template")
_reg("generated_by", "F", "उत्पादन गर्ने", "Generated By", auto_populate=True, resolver="resolve_template")
_reg("document_language", "F", "दस्तावेज भाषा", "Document Language", auto_populate=True, resolver="resolve_template")
_reg("export_format", "F", "निर्यात ढाँचा", "Export Format", auto_populate=True, resolver="resolve_template")
_reg("plan_revision_number", "F", "संशोधन नं.", "Revision Number", var_type="number", auto_populate=True, resolver="resolve_template")

# ═══════════════════════════════════════════════════════
# Chart Variables (14) — special content_type="chart"
# ═══════════════════════════════════════════════════════
_reg("chart:forest_type_pie", "A", "वन प्रकार पाई चार्ट", "Forest Type Pie Chart", var_type="dict", source="raster")
_reg("chart:landcover_pie", "A", "भू-आवरण पाई चार्ट", "Landcover Pie Chart", var_type="dict", source="raster")
_reg("chart:ug_land_cover_classes_chart", "A", "उपभोक्ता समूह भू-आवरण पाई चार्ट", "UG Land Cover Classes Pie Chart", var_type="dict", source="user_group")
_reg("chart:slope_bar", "A", "भिरालो बार चार्ट", "Slope Bar Chart", var_type="dict", source="raster")
_reg("chart:aspect_rose", "A", "दिशा रोज चार्ट", "Aspect Rose Chart", var_type="dict", source="raster")
_reg("chart:soil_bar", "A", "माटो बार चार्ट", "Soil Bar Chart", var_type="dict", source="raster")
_reg("chart:canopy_bar", "A", "वन मुकुट बार चार्ट", "Canopy Bar Chart", var_type="dict", source="raster")
_reg("chart:forest_health_pie", "A", "वन स्वास्थ्य पाई चार्ट", "Forest Health Pie Chart", var_type="dict", source="raster")
_reg("chart:species_composition_pie", "A", "प्रजाति संरचना पाई चार्ट", "Species Comp. Pie Chart", var_type="dict", source="inventory")
_reg("chart:species_composition_pie_fi", "A", "प्रजाति संरचना पाई चार्ट (क्षेत्र सर्वेक्षण)", "Species Comp. Pie Chart (Field Inventory)", var_type="dict", source="field_inventory")
_reg("chart:block_volume_bar", "A", "ब्लक आयतन बार चार्ट", "Block Volume Bar Chart", var_type="dict", source="inventory")
_reg("chart:block_area_bar", "A", "ब्लक क्षेत्रफल बार चार्ट", "Block Area Bar Chart", var_type="dict", source="block")
_reg("chart:hh_prosperity_pie", "A", "समृद्धि पाई चार्ट", "Prosperity Pie Chart", var_type="dict", source="household")
_reg("chart:hh_caste_bar", "A", "जाति बार चार्ट", "Caste Bar Chart", var_type="dict", source="household")
_reg("chart:budget_bar", "A", "बजेट बार चार्ट", "Budget Bar Chart", var_type="dict", source="activities")
_reg("chart:ya_budget_year_bar", "A", "वर्ष अनुसार बजेट बार चार्ट",
     "Year-wise Budget Bar Chart", var_type="dict", source="yearly_activities")
_reg("chart:ya_program_pie", "A", "कार्यक्रम अनुसार बजेट पाई चार्ट",
     "Program-wise Budget Pie Chart", var_type="dict", source="yearly_activities")
_reg("chart:dbh_class_bar", "A",
     "ब्यास क्लास अनुसार प्रति हेक्टर मौज्दात (खाँवा र रूख)",
     "DBH Class Growing Stock Bar Chart (Pole & Tree)",
     var_type="dict", source="field_inventory")
_reg("chart:dbh_class_count_bar", "A",
     "ब्यास क्लास अनुसार प्रति हेक्टर रूख संख्या (खाँवा र रूख)",
     "DBH Class Tree Count Bar Chart (Pole & Tree)",
     var_type="dict", source="field_inventory")

# ── Tree Mapping (sm_*) chart variables ──
_reg("chart:sm_felling_dbh_pie", "A",
     "ब्यास वर्ग अनुसार कटानी रूख (पाई चार्ट)",
     "DBH-wise Felling Trees (Pie Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_felling_species_bar", "A",
     "प्रजाति अनुसार कटानी रूख (बार चार्ट)",
     "Species-wise Felling Trees (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_mother_felling_pie", "A",
     "माँउ रूख बनाम कटानी रूख (पाई चार्ट)",
     "Mother vs Felling Trees (Pie Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_mother_felling_species_bar", "A",
     "प्रजाति अनुसार माँउ बनाम कटानी (बार चार्ट)",
     "Mother vs Felling by Species (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_stand_type_bar", "A",
     "स्तर अनुसार वन प्रकार (बार चार्ट)",
     "Stand Type by Hierarchy (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_carbon_bar", "A",
     "स्तर अनुसार कार्बन (बार चार्ट)",
     "Carbon by Hierarchy (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_volume_bar", "A",
     "स्तर अनुसार आयतन (बार चार्ट)",
     "Volume by Hierarchy (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")
_reg("chart:sm_mother_felling_hierarchy_bar", "A",
     "स्तर अनुसार माँउ बनाम कटानी (बार चार्ट)",
     "Mother vs Felling by Hierarchy (Bar Chart)",
     var_type="dict", source="tree_mapping_analysis")

# ═══════════════════════════════════════════════════════
# Fieldbook Variables
# ═══════════════════════════════════════════════════════
_FIELDBOOK_VARS = [
    ("fieldbook_total_points",       "जम्मा फिल्डबुक बिन्दु",                 "Total Fieldbook Points"),
    ("fieldbook_vertex_count",       "मुख्य बिन्दु संख्या",                   "Vertex Point Count"),
    ("fieldbook_interpolated_count", "अन्तरसम्मिलित बिन्दु संख्या",           "Interpolated Point Count"),
    ("fieldbook_perimeter_m",        "वन परिधि (मिटर)",                       "Forest Perimeter (m)"),
    ("fieldbook_avg_elevation_m",    "औसत उचाइ (मिटर)",                       "Average Elevation (m)"),
    ("fieldbook_min_elevation_m",    "न्यूनतम उचाइ (मिटर)",                   "Minimum Elevation (m)"),
    ("fieldbook_max_elevation_m",    "अधिकतम उचाइ (मिटर)",                    "Maximum Elevation (m)"),
    ("fieldbook_points",             "फिल्डबुक बिन्दु विवरण तालिका",          "Fieldbook Points Table"),
    ("fieldbook_block_summary",      "ब्लक अनुसार फिल्डबुक बिन्दु विवरण",    "Block-wise Fieldbook Points"),
    ("fieldbook_narration",          "फिल्डबुक विवरण (अनुच्छेद)",             "Fieldbook Narration"),
]
for _fk, _fne, _fen in _FIELDBOOK_VARS:
    _vtype = "list" if _fk in ("fieldbook_points", "fieldbook_block_summary") else "string"
    _src = "section_generator" if _fk == "fieldbook_narration" else "fieldbook"
    _reg(_fk, "A", _fne, _fen, var_type=_vtype, source=_src)

# ═══════════════════════════════════════════════════════
# Map Variables
# ═══════════════════════════════════════════════════════
_MAP_TYPES = [
    ("map:boundary",      "सिमाना नक्सा",          "Boundary Map"),
    ("map:forest_type",   "वन प्रकार नक्सा",       "Forest Type Map"),
    ("map:forest_health", "वन स्वास्थ्य नक्सा",    "Forest Health Map"),
    ("map:slope",         "भिरालो नक्सा",          "Slope Map"),
    ("map:biomass",       "बायोमास नक्सा",         "Biomass Map"),
    ("map:landcover",     "भू-आवरण नक्सा",          "Land Cover Map"),
    ("map:soil_texture",  "माटो बनावट नक्सा",      "Soil Texture Map"),
    ("map:dem",           "उचाइ नक्सा",             "Elevation Map"),
    ("map:aspect",        "दिशा नक्सा",             "Aspect Map"),
    ("map:canopy",        "वन छाना नक्सा",          "Canopy Cover Map"),
    ("map:sampling_plot",           "नमुना प्लट नक्सा",                "Sample Plot Map"),
    ("map:sampling_plot_topo",      "स्थलाकृतिक नमुना प्लट नक्सा",     "Sample Plot Map (Topo)"),
    ("map:sampling_plot_satellite", "उपग्रह नमुना प्लट नक्सा",         "Sample Plot Map (Satellite)"),
    ("map:fieldbook",               "फिल्डबुक बाटो नक्सा",             "Fieldbook Path Map"),
    ("map:usergroup",               "उपयोगकर्ता समूह नक्सा",            "User Group Map"),
    ("map:subarea",                 "उप-क्षेत्र नक्सा",                 "Sub-Area Map"),
    ("map:compartment",             "कम्पार्टमेन्ट नक्सा",              "Compartment Map"),
    ("map:sub_compartment",         "उप-कम्पार्टमेन्ट नक्सा",          "Sub-Compartment Map"),
]
for _mkey, _mne, _men in _MAP_TYPES:
    _reg(_mkey, "A", _mne, _men, var_type="dict", source="maps")
# backward compat alias
_reg("map:boundary_map", "A", "सिमाना नक्सा", "Boundary Map", var_type="dict", source="maps")

# ═══════════════════════════════════════════════════════
# Table Variables (32) — inline table rendering
# ═══════════════════════════════════════════════════════
_TABLE_LABELS = [
    ("table_1", "भौगोलिक अवस्था", "Geographic Condition"),
    ("table_2", "वन क्षेत्रफल", "Forest Area"),
    ("table_3", "भू-उपयोग विवरण", "Land Use Details"),
    ("table_4", "माटोको प्रकार", "Soil Type"),
    ("table_5", "ब्लक विवरण", "Block Details"),
    ("table_6", "वन प्रकार", "Forest Type"),
    ("table_7", "रूख गणना", "Tree Count"),
    ("table_8", "आयतन विवरण", "Volume Details"),
    ("table_9", "नियत मात्रा", "Prescribed Quantity"),
    ("table_10", "मुख्य प्रजाति", "Main Species"),
    ("table_11", "घरधुरी विवरण", "Household Details"),
    ("table_12", "जनसंख्या विवरण", "Population Details"),
    ("demand_supply", "माग र आपूर्ति", "Demand and Supply"),
    ("table_14", "समिति विवरण", "Committee Details"),
    ("table_15", "वार्षिक क्रियाकलाप", "Annual Activities"),
    ("table_16", "बजेट विवरण", "Budget Details"),
    ("table_17", "वन पैदावार सङ्कलन", "Forest Product Collection"),
    ("table_18", "वन संवर्द्धन क्रियाकलाप", "Forest Enhancement Activities"),
    ("table_19", "संरक्षण योजना", "Conservation Plan"),
    ("table_20", "जैविक विविधता", "Biodiversity"),
    ("table_21", "आय-आर्जन योजना", "Income Generation Plan"),
    ("table_22", "सीप विकास", "Skill Development"),
    ("table_23", "पर्यापर्यटन", "Eco-tourism"),
    ("table_24", "अनुगमन योजना", "Monitoring Plan"),
    ("table_25", "मूल्याङ्कन मापदण्ड", "Evaluation Criteria"),
    ("table_26", "सामुदायिक विकास", "Community Development"),
    ("table_27", "वैकल्पिक उर्जा", "Alternative Energy"),
    ("table_28", "संस्थागत विकास", "Institutional Development"),
    ("table_29", "सहकार्य सम्झौता", "Collaboration Agreement"),
    ("table_30", "वित्तीय विश्लेषण", "Financial Analysis"),
    ("table_31", "जोखिम व्यवस्थापन", "Risk Management"),
    ("table_32", "अन्य तालिका", "Other Table"),
    ("table_33", "संरक्षण स्थिति विवरण", "IUCN Conservation Status"),
    ("table_34", "संरक्षित प्रजाति सूची", "Protected Species List"),
    ("table_35", "मिचाहा प्रजाति सूची", "Invasive Species List"),
    ("table_36", "वनस्पति प्रजाति सूची", "Vegetation Species List"),
    ("table_37", "जनावर प्रजाति सूची", "Animal Species List"),
]
for _tid, _ne, _en in _TABLE_LABELS:
    _reg(f"table:{_tid}", "A", _ne, _en, var_type="dict", source="op_table")

TABLE_ID_ALIAS = {
    "biodiversity": "table_20",
    "iucn_status": "table_33",
    "protected_species": "table_34",
    "invasive_species": "table_35",
    "vegetation_species": "table_36",
    "animal_species": "table_37",
}

_reg("table:fieldinventory", "A",
     "क्षेत्र सर्वेक्षण मापन तथ्याङ्क",
     "Field Inventory Measurement Data",
     var_type="list", source="field_inventory")
for _alias, _tid in TABLE_ID_ALIAS.items():
    _entry = VARIABLE_REGISTRY.get(f"table:{_tid}")
    if _entry:
        _reg(f"table:{_alias}", "A", _entry.label_ne, _entry.label_en, var_type="dict", source="op_table")

# ═══════════════════════════════════════════════════════════════════
# Category A: Tree Mapping Analysis (source="tree_mapping_analysis")
# ═══════════════════════════════════════════════════════════════════

# Scalar variables
_reg("sm_available", "A", "रूख म्यापिङ विश्लेषण उपलब्ध",
     "Tree Mapping Analysis Available",
     var_type="boolean", source="tree_mapping_analysis")
_reg("sm_total_blocks_analyzed", "A", "विश्लेषित ब्लक सङ्ख्या",
     "Blocks Analyzed",
     var_type="number", source="tree_mapping_analysis", precision=0)
_reg("sm_total_trees_analyzed", "A", "विश्लेषित कुल रूख सङ्ख्या",
     "Total Trees Analyzed",
     var_type="number", source="tree_mapping_analysis", precision=0)
_reg("sm_total_carbon_tc", "A", "कुल कार्बन मौज्दात (tC)",
     "Total Carbon Stock (tC)",
     var_type="number", source="tree_mapping_analysis", precision=3)
_reg("sm_total_co2_tco2", "A", "कुल CO₂ समतुल्य (tCO₂)",
     "Total CO₂ Equivalent (tCO₂)",
     var_type="number", source="tree_mapping_analysis", precision=3)

# List variables (rendered as inline tables in DOCX)
_reg("sm_hierarchy_summary", "A", "स्थानिक स्तर अनुसार रूख सारांश",
     "Spatial Hierarchy Tree Summary",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_species_by_hierarchy", "A", "स्थानिक स्तर अनुसार प्रजाति विश्लेषण",
     "Species Composition by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_species_diversity", "A", "ब्लक अनुसार प्रजाति विविधता",
     "Species Diversity by Block",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_dbh_by_hierarchy", "A", "स्थानिक स्तर अनुसार DBH वर्ग विश्लेषण",
     "DBH Class by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_dbh_species_by_hierarchy", "A", "स्थानिक स्तर अनुसार DBH-प्रजाति विश्लेषण",
     "DBH × Species by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_stand_type_by_hierarchy", "A", "स्थानिक स्तर अनुसार स्ट्यान्ड प्रकार",
     "Stand Type by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_carbon_by_hierarchy", "A", "स्थानिक स्तर अनुसार कार्बन मौज्दात",
     "Carbon Stock by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_volume_by_hierarchy", "A", "स्थानिक स्तर अनुसार आयतन विश्लेषण",
     "Volume Analysis by Spatial Level",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_top_species_by_volume", "A", "आयतन अनुसार शीर्ष प्रजाति",
     "Top Species by Volume",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_mother_tree_by_hierarchy", "A", "स्थानिक स्तर अनुसार माँउ रूख विश्लेषण",
     "Mother Tree Analysis by Spatial Level",
     var_type="list", source="tree_mapping_analysis")

# Dict variables
_reg("sm_forest_structure_status", "A", "वन संरचना अवस्था",
     "Forest Structure Status",
     var_type="dict", source="tree_mapping_analysis")
_reg("sm_mother_tree_coverage", "A", "माँउ रूख ग्रिड कभरेज",
     "Mother Tree Grid Coverage",
     var_type="dict", source="tree_mapping_analysis")
_reg("sm_mother_tree_by_species", "A", "प्रजाति अनुसार माँउ रूख",
     "Mother Tree by Species",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_felling_tree_by_species", "A", "प्रजाति अनुसार कटानी रूख",
     "Felling Tree by Species",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_mother_felling_summary", "A", "माँउ रूख बनाम कटानी रूख सारांश",
     "Mother Tree vs Felling Tree Summary",
     var_type="dict", source="tree_mapping_analysis")
_reg("sm_hierarchy_remark_breakdown", "A", "स्तर अनुसार माँउ/कटानी विभाजन",
     "Hierarchy Remark Breakdown",
     var_type="dict", source="tree_mapping_analysis")
_reg("sm_species_hier_remark", "A", "स्तर र प्रजाति अनुसार माँउ/कटानी",
     "Species by Hierarchy with Remark",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_dbh_hier_remark", "A", "स्तर र DBH अनुसार माँउ/कटानी",
     "DBH by Hierarchy with Remark",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_felling_dbh_analysis", "A", "कटानी रूख DBH विश्लेषण (≥३० सेमी)",
     "Felling Tree DBH Analysis (≥30cm)",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_felling_species_analysis", "A", "कटानी रूख प्रजाति विश्लेषण (≥३० सेमी)",
     "Felling Tree Species Analysis (≥30cm)",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_felling_totals", "A", "कटानी रूख कुल योग (≥३० सेमी)",
     "Felling Tree Totals (≥30cm)",
     var_type="dict", source="tree_mapping_analysis")

# --- Legend variables for chart symbolization ---
_reg("sm_mf_hierarchy_legend", "A", "माँउ/कटानी स्तर चार्ट लिजेन्ड",
     "Mother/Felling Hierarchy Chart Legend",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_stand_type_legend", "A", "स्ट्यान्ड प्रकार चार्ट लिजेन्ड",
     "Stand Type Chart Legend",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_carbon_legend", "A", "कार्बन चार्ट लिजेन्ड",
     "Carbon Chart Legend",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_volume_legend", "A", "आयतन चार्ट लिजेन्ड",
     "Volume Chart Legend",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_mf_species_legend", "A", "माँउ/कटानी प्रजाति चार्ट लिजेन्ड",
     "Mother/Felling Species Chart Legend",
     var_type="list", source="tree_mapping_analysis")
_reg("sm_felling_species_legend", "A", "कटानी प्रजाति चार्ट लिजेन्ड",
     "Felling Species Chart Legend",
     var_type="list", source="tree_mapping_analysis")


def get_variable(key: str) -> Optional[VariableDef]:
    return VARIABLE_REGISTRY.get(key)


def get_variables_by_category(category: str) -> List[VariableDef]:
    return [v for v in VARIABLE_REGISTRY.values() if v.category == category]


def get_variables_by_source(source: str) -> List[VariableDef]:
    return [v for v in VARIABLE_REGISTRY.values() if v.source == source]


def search_variables(query: str) -> List[VariableDef]:
    q = query.lower()
    return [
        v for v in VARIABLE_REGISTRY.values()
        if q in v.key.lower() or q in v.label_ne.lower() or q in v.label_en.lower()
    ]


def get_all_variables() -> List[VariableDef]:
    return list(VARIABLE_REGISTRY.values())
