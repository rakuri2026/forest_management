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


VARIABLE_REGISTRY: Dict[str, VariableDef] = {}


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
) -> None:
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
    )


# ═══════════════════════════════════════════════════════
# Category A: System Variables (103)
# ═══════════════════════════════════════════════════════

# A1: Basic Calculation Info (18)
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
_reg("total_blocks", "A", "कुल ब्लक सङ्ख्या", "Total Blocks", var_type="number", source="calculation")
_reg("utm_zone", "A", "UTM जोन", "UTM Zone", var_type="number", source="calculation")

# A2: Raster - Physiography (12)
_reg("elevation_min_m", "A", "न्यूनतम उचाई (मि)", "Min Elevation (m)", var_type="number", source="raster")
_reg("elevation_max_m", "A", "अधिकतम उचाई (मि)", "Max Elevation (m)", var_type="number", source="raster")
_reg("elevation_mean_m", "A", "औसत उचाई (मि)", "Mean Elevation (m)", var_type="number", source="raster")
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
_reg("temperature_mean_c", "A", "औसत तापक्रम (से)", "Mean Temperature (C)", var_type="number", source="raster")
_reg("temperature_min_c", "A", "न्यूनतम तापक्रम (से)", "Min Temperature (C)", var_type="number", source="raster")
_reg("temperature_max_c", "A", "अधिकतम तापक्रम (से)", "Max Temperature (C)", var_type="number", source="raster")
_reg("precipitation_mean_mm", "A", "औसत वर्षा (मिमि)", "Mean Precipitation (mm)", var_type="number", source="raster")
_reg("precipitation_min_mm", "A", "न्यूनतम वर्षा (मिमि)", "Min Precipitation (mm)", var_type="number", source="raster")
_reg("precipitation_max_mm", "A", "अधिकतम वर्षा (मिमि)", "Max Precipitation (mm)", var_type="number", source="raster")

# A4: Raster - Forest Cover (12)
_reg("forest_type_dominant", "A", "मुख्य वन प्रकार", "Dominant Forest Type", source="raster")
_reg("forest_type_percentages", "A", "वन प्रकार प्रतिशत", "Forest Type Percentages", var_type="dict", source="raster")
_reg("landcover_dominant", "A", "मुख्य भू-आवरण", "Dominant Landcover", source="raster")
_reg("landcover_percentages", "A", "भू-आवरण प्रतिशत", "Landcover Percentages", var_type="dict", source="raster")
_reg("forest_health_dominant", "A", "मुख्य वन स्वास्थ्य", "Dominant Forest Health", source="raster")
_reg("forest_health_percentages", "A", "वन स्वास्थ्य प्रतिशत", "Forest Health Percentages", var_type="dict", source="raster")
_reg("canopy_dominant_class", "A", "मुख्य वन मुकुट वर्ग", "Dominant Canopy Class", source="raster")
_reg("canopy_percentages", "A", "वन मुकुट प्रतिशत", "Canopy Percentages", var_type="dict", source="raster")
_reg("canopy_mean_m", "A", "औसत वन मुकुट (मि)", "Mean Canopy (m)", var_type="number", source="raster")
_reg("forest_loss_hectares", "A", "वन क्षति (हे)", "Forest Loss (ha)", var_type="number", source="raster")
_reg("forest_gain_hectares", "A", "वन लाभ (हे)", "Forest Gain (ha)", var_type="number", source="raster")
_reg("forest_loss_by_year", "A", "वार्षिक वन क्षति", "Forest Loss by Year", var_type="dict", source="raster")

# A5: Raster - Biomass/Carbon (3)
_reg("agb_mean", "A", "औसत AGB", "Mean AGB", var_type="number", source="raster")
_reg("agb_total", "A", "कुल AGB", "Total AGB", var_type="number", source="raster")
_reg("carbon_stock", "A", "कार्बन मौज्दात", "Carbon Stock", var_type="number", source="raster")

# A6: Boundary (5)
_reg("boundary_type", "A", "सिमाना प्रकार", "Boundary Type", source="boundary")
_reg("boundary_features_north", "A", "उत्तर सिमाना", "North Boundary", var_type="list", source="boundary")
_reg("boundary_features_east", "A", "पूर्व सिमाना", "East Boundary", var_type="list", source="boundary")
_reg("boundary_features_south", "A", "दक्षिण सिमाना", "South Boundary", var_type="list", source="boundary")
_reg("boundary_features_west", "A", "पश्चिम सिमाना", "West Boundary", var_type="list", source="boundary")

# A7: Blocks & Sub-Areas (5)
_reg("blocks_count", "A", "ब्लक सङ्ख्या", "Blocks Count", var_type="number", source="block")
_reg("sub_areas_by_category", "A", "उप-क्षेत्र प्रकार", "Sub-areas by Category", var_type="dict", source="block")
_reg("sub_areas_total", "A", "कुल उप-क्षेत्र", "Total Sub-areas", var_type="number", source="block")
_reg("sub_area_categories", "A", "उप-क्षेत्र कोटीहरू", "Sub-area Categories", var_type="list", source="block")

# A8: Species (4)
_reg("total_species", "A", "कुल प्रजाति सङ्ख्या", "Total Species", var_type="number", source="species")
_reg("species_list", "A", "प्रजाति सूची", "Species List", var_type="list", source="species")
_reg("species_by_role", "A", "भूमिका अनुसार प्रजाति", "Species by Role", var_type="dict", source="species")
_reg("confirmed_species", "A", "पुष्टि गरिएका प्रजाति", "Confirmed Species", var_type="list", source="species")

# A9: Tree Inventory (13)
_reg("inventory_available", "A", "रूख गणना उपलब्ध", "Inventory Available", var_type="boolean", source="inventory")
_reg("inventory_total_trees", "A", "कुल रूख सङ्ख्या", "Total Trees", var_type="number", source="inventory")
_reg("inventory_mother_trees", "A", "माता रूख सङ्ख्या", "Mother Trees", var_type="number", source="inventory")
_reg("inventory_felling_trees", "A", "कटानी रूख सङ्ख्या", "Felling Trees", var_type="number", source="inventory")
_reg("inventory_seedling_count", "A", "बिरुवा सङ्ख्या", "Seedling Count", var_type="number", source="inventory")
_reg("inventory_volume_m3", "A", "कुल आयतन (m³)", "Total Volume (m3)", var_type="number", source="inventory")
_reg("inventory_net_volume_m3", "A", "शुद्ध आयतन (m³)", "Net Volume (m3)", var_type="number", source="inventory")
_reg("inventory_net_volume_cft", "A", "शुद्ध आयतन (cft)", "Net Volume (cft)", var_type="number", source="inventory")
_reg("inventory_firewood_m3", "A", "दाउरा आयतन (m³)", "Firewood Volume (m3)", var_type="number", source="inventory")
_reg("inventory_firewood_chatta", "A", "दाउरा (चट्टा)", "Firewood (chatta)", var_type="number", source="inventory")
_reg("inventory_species_summary", "A", "प्रजाति सारांश", "Species Summary", var_type="dict", source="inventory")
_reg("inventory_dbh_summary", "A", "DBH सारांश", "DBH Summary", var_type="dict", source="inventory")
_reg("inventory_block_summary", "A", "ब्लक सारांश", "Block Summary", var_type="dict", source="inventory")

# A10: Field Inventory (23)
_reg("fi_available", "A", "क्षेत्र सर्वेक्षण उपलब्ध", "Field Inventory Available", var_type="boolean", source="field_inventory")
_reg("fi_total_plots", "A", "कुल नमूना प्लट", "Total Sample Plots", var_type="number", source="field_inventory")
_reg("fi_total_blocks", "A", "सर्वेक्षण ब्लक", "Survey Blocks", var_type="number", source="field_inventory")
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
_reg("fi_mai_percent", "A", "MAI प्रतिशत", "MAI Percent", var_type="number", source="field_inventory")
_reg("fi_agb_t_per_ha", "A", "प्रतिहेक्टर AGB (टन)", "AGB t/ha", var_type="number", source="field_inventory")
_reg("fi_bgb_t_per_ha", "A", "प्रतिहेक्टर BGB (टन)", "BGB t/ha", var_type="number", source="field_inventory")
_reg("fi_total_biomass_t_per_ha", "A", "प्रतिहेक्टर कुल जैविक पदार्थ", "Total Biomass t/ha", var_type="number", source="field_inventory")
_reg("fi_carbon_stock_tc_per_ha", "A", "प्रतिहेक्टर कार्बन मौज्दात", "Carbon Stock tC/ha", var_type="number", source="field_inventory")
_reg("fi_co2_equivalent_tco2_per_ha", "A", "प्रतिहेक्टर CO₂ समतुल्य", "CO₂ Equivalent tCO₂/ha", var_type="number", source="field_inventory")
_reg("fi_weighted_wood_density", "A", "भारित काठ घनत्व", "Weighted Wood Density", var_type="number", source="field_inventory")
_reg("fi_species_block_growing_stock", "A", "ब्लक अनुसार प्रजाति वन मौज्दात (पोल+रूख)", "Block-wise Species Growing Stock (Pole+Tree)", var_type="list", source="field_inventory")
_reg("fi_block_regeneration_status", "A", "वन खन्ड अनुसार पुनरोत्पादनको स्थिति", "Forest Block-wise Regeneration Status", var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_growing_stock", "A", "ब्लक अनुसार DBH वर्ग वन मौज्दात", "Block-wise DBH Class Growing Stock", var_type="list", source="field_inventory")
_reg("fi_block_dbh_class_growing_stock_np", "A", "ब्लक अनुसार DBH वर्ग वन मौज्दात (नेपाली)", "Block-wise DBH Class Growing Stock (Nepali)", var_type="list", source="field_inventory")
_reg("fi_block_summaries", "A", "ब्लक अनुसार पूर्ण नतिजा", "Block-wise Full Results", var_type="list", source="field_inventory")
_reg("fi_mai_table", "A", "वार्षिक वृद्धि तालिका (m³/ha/yr)", "Annual Increment (MAI) Table", var_type="list", source="field_inventory")
_reg("fi_aah_table", "A", "वार्षिक स्वीकार्य कटान तालिका (m³/ha/yr)", "Annual Allowable Cut (AAH) Table", var_type="list", source="field_inventory")

# A11: Sampling (6)
_reg("sampling_available", "A", "नमूना योजना उपलब्ध", "Sampling Available", var_type="boolean", source="sampling")
_reg("sampling_type", "A", "नमूना प्रकार", "Sampling Type", source="sampling")
_reg("sampling_total_points", "A", "कुल नमूना बिन्दु", "Total Sample Points", var_type="number", source="sampling")
_reg("sampling_plot_shape", "A", "प्लट आकार", "Plot Shape", source="sampling")
_reg("sampling_plot_radius_m", "A", "प्लट अर्धव्यास (मि)", "Plot Radius (m)", var_type="number", source="sampling")
_reg("sampling_intensity_per_ha", "A", "प्रतिहेक्टर तीव्रता", "Intensity per ha", var_type="number", source="sampling")

# A12: Household (10)
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

# A14: Biodiversity (6)
_reg("bio_available", "A", "जैविक विविधता उपलब्ध", "Biodiversity Available", var_type="boolean", source="biodiversity")
_reg("bio_total_species", "A", "कुल जैविक प्रजाति", "Total Biodiversity Species", var_type="number", source="biodiversity")
_reg("bio_vegetation_count", "A", "वनस्पति प्रजाति सङ्ख्या", "Vegetation Count", var_type="number", source="biodiversity")
_reg("bio_animal_count", "A", "जनावर प्रजाति सङ्ख्या", "Animal Count", var_type="number", source="biodiversity")
_reg("bio_vegetation", "A", "वनस्पति विवरण", "Vegetation Details", var_type="list", source="biodiversity")
_reg("bio_animals", "A", "जनावर विवरण", "Animal Details", var_type="list", source="biodiversity")

# A15: Activities (4)
_reg("activities_available", "A", "क्रियाकलाप उपलब्ध", "Activities Available", var_type="boolean", source="activities")
_reg("activities_total", "A", "कुल क्रियाकलाप", "Total Activities", var_type="number", source="activities")
_reg("activities_total_budget", "A", "कुल बजेट (रु)", "Total Budget (Rs)", var_type="number", source="activities")
_reg("activities_list", "A", "क्रियाकलाप सूची", "Activities List", var_type="list", source="activities")

# A16: User Group (3)
_reg("ug_available", "A", "उपभोक्ता समूह डाटा उपलब्ध", "User Group Available", var_type="boolean", source="user_group")
_reg("ug_total_settlements", "A", "कुल बस्ती", "Total Settlements", var_type="number", source="user_group")
_reg("ug_buildings", "A", "बस्ती विवरण", "Settlement Details", var_type="list", source="user_group")

# A17: Additional Committee (0 — reuses A13)

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
# Category C: User Input Variables (21)
# ═══════════════════════════════════════════════════════
_reg("plan_year_start", "C", "योजना सुरु वर्ष", "Plan Start Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("plan_year_end", "C", "योजना अन्त वर्ष", "Plan End Year", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("plan_duration_years", "C", "योजना अवधि (वर्ष)", "Plan Duration (years)", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("user_group_name", "C", "उपभोक्ता समूहको नाम", "User Group Name", auto_populate=False, resolver="resolve_user_input")
_reg("user_group_code", "C", "दर्ता नं.", "Registration No", auto_populate=False, resolver="resolve_user_input")
_reg("registration_date", "C", "दर्ता मिति", "Registration Date", auto_populate=False, resolver="resolve_user_input")
_reg("registration_office", "C", "दर्ता कार्यालय", "Registration Office", auto_populate=False, resolver="resolve_user_input")
_reg("cf_area_provided", "C", "प्रदान गरिएको क्षेत्रफल (हे)", "CF Area Provided (ha)", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("cf_handover_date", "C", "हस्तान्तरण मिति", "Handover Date", auto_populate=False, resolver="resolve_user_input")
_reg("cf_total_households", "C", "कुल घरधुरी", "Total Households", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("cf_total_population", "C", "कुल जनसंख्या", "Total Population", var_type="number", auto_populate=False, resolver="resolve_user_input")
_reg("vdc_ward", "C", "वडा नं.", "Ward No", auto_populate=False, resolver="resolve_user_input")
_reg("contact_person", "C", "सम्पर्क व्यक्ति", "Contact Person", auto_populate=False, resolver="resolve_user_input")
_reg("contact_designation", "C", "पद", "Designation", auto_populate=False, resolver="resolve_user_input")
_reg("contact_phone", "C", "फोन नं.", "Phone No", auto_populate=False, resolver="resolve_user_input")
_reg("ranger_name", "C", "रेन्जरको नाम", "Ranger Name", auto_populate=False, resolver="resolve_user_input")
_reg("ranger_phone", "C", "रेन्जर फोन", "Ranger Phone", auto_populate=False, resolver="resolve_user_input")
_reg("prepared_by", "C", "तयार गर्ने", "Prepared By", auto_populate=False, resolver="resolve_user_input")
_reg("reviewed_by", "C", "समीक्षा गर्ने", "Reviewed By", auto_populate=False, resolver="resolve_user_input")
_reg("approved_by", "C", "स्वीकृत गर्ने", "Approved By", auto_populate=False, resolver="resolve_user_input")
_reg("plan_language", "C", "भाषा", "Language", auto_populate=False, resolver="resolve_user_input")

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

# ═══════════════════════════════════════════════════════
# Category E: Section Content (5)
# ═══════════════════════════════════════════════════════
_reg("section_6_previous_review", "E", "विगत समीक्षा (पाठ)", "Previous Review Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_8_production", "E", "उत्पादन (पाठ)", "Production Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_16_prohibited", "E", "निषेधित कार्य (पाठ)", "Prohibited Activities Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_17_penalties", "E", "वन अपराध (पाठ)", "Penalties Text", source="template", auto_populate=True, resolver="resolve_section_content")
_reg("section_18_misc", "E", "विविध (पाठ)", "Miscellaneous Text", source="template", auto_populate=True, resolver="resolve_section_content")

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
# Chart Variables (13) — special content_type="chart"
# ═══════════════════════════════════════════════════════
_reg("chart:forest_type_pie", "A", "वन प्रकार पाई चार्ट", "Forest Type Pie Chart", var_type="dict", source="raster")
_reg("chart:landcover_pie", "A", "भू-आवरण पाई चार्ट", "Landcover Pie Chart", var_type="dict", source="raster")
_reg("chart:slope_bar", "A", "भिरालो बार चार्ट", "Slope Bar Chart", var_type="dict", source="raster")
_reg("chart:aspect_rose", "A", "दिशा रोज चार्ट", "Aspect Rose Chart", var_type="dict", source="raster")
_reg("chart:soil_bar", "A", "माटो बार चार्ट", "Soil Bar Chart", var_type="dict", source="raster")
_reg("chart:canopy_bar", "A", "वन मुकुट बार चार्ट", "Canopy Bar Chart", var_type="dict", source="raster")
_reg("chart:forest_health_pie", "A", "वन स्वास्थ्य पाई चार्ट", "Forest Health Pie Chart", var_type="dict", source="raster")
_reg("chart:species_composition_pie", "A", "प्रजाति संरचना पाई चार्ट", "Species Comp. Pie Chart", var_type="dict", source="inventory")
_reg("chart:block_volume_bar", "A", "ब्लक आयतन बार चार्ट", "Block Volume Bar Chart", var_type="dict", source="inventory")
_reg("chart:block_area_bar", "A", "ब्लक क्षेत्रफल बार चार्ट", "Block Area Bar Chart", var_type="dict", source="block")
_reg("chart:hh_prosperity_pie", "A", "समृद्धि पाई चार्ट", "Prosperity Pie Chart", var_type="dict", source="household")
_reg("chart:hh_caste_bar", "A", "जाति बार चार्ट", "Caste Bar Chart", var_type="dict", source="household")
_reg("chart:budget_bar", "A", "बजेट बार चार्ट", "Budget Bar Chart", var_type="dict", source="activities")

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
    ("table_13", "माग र आपूर्ति", "Demand and Supply"),
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
]
for _tid, _ne, _en in _TABLE_LABELS:
    _reg(f"table:{_tid}", "A", _ne, _en, var_type="dict", source="op_table")


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
