-- Add comments to raster tables based on testData/comment.txt
-- Database: cf_db, Schema: rasters

-- agb_2022_nepal
COMMENT ON TABLE rasters.agb_2022_nepal IS
'Source: projects/sat-io/open-datasets/ESA/ESA_CCI_AGB/CCI_BIOMASS_100m_AGB_2022_V6
Description: Tonnes of above and below ground biomass carbon per hectare
Pixel Size: 0.000898315, -0.000898315 dd (100m)
Unit: mg/ha
Pixel Type: UInt16 - Sixteen bit unsigned integer
Data Type: continuous data';

-- annual_mean_temperature
COMMENT ON TABLE rasters.annual_mean_temperature IS
'Source: WORLDCLIM/V1/BIO
Band name: bio01
Description: Annual mean temperature
Pixel Size: 0.00833333 dd (927.67m)
Unit: deg;C
Scale: 0.1
Pixel Type: 32-bit floating-point numbers
Data Type: continuous data';

-- annual_precipitation
COMMENT ON TABLE rasters.annual_precipitation IS
'Source: WORLDCLIM/V1/BIO
Band name: bio12
Description: Annual precipitation
Pixel Size: 0.00833333 dd (927.67m)
Unit: mm
Min value: 0, Max value: 11401
Scale: 0
Pixel Type: 32-bit floating-point numbers
Data Type: continuous data';

-- canopy_height
COMMENT ON TABLE rasters.canopy_height IS
'Source: tree canopy height
Description: Forest canopy height classification
Classes:
  0 m = Non-forest (class 0)
  0 < height ≤ 5 m = Bush or shrub land (class 1)
  5 < height ≤ 15 m = Pole sized forest (class 2)
  height > 15 m = High forest (class 3)
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Unit: meter
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- dem
COMMENT ON TABLE rasters.dem IS
'Source: USGS/SRTMGL1_003
Description: Elevation from sea level in meters
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Unit: meter
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- esa_world_cover
COMMENT ON TABLE rasters.esa_world_cover IS
'Source: ESA/WorldCover/v200
Description: Global land cover classification
Classes:
  10 = Tree cover
  20 = Shrubland
  30 = Grassland
  40 = Cropland
  50 = Built-up
  60 = Bare / sparse vegetation
  70 = Snow and ice
  80 = Permanent water bodies
  90 = Herbaceous wetland
  95 = Mangroves
  100 = Moss and lichen
Pixel Size: 0.00008333 dd (9.28m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- forest_type
COMMENT ON TABLE rasters.forest_type IS
'Source: FRTC, Kathmandu
Description: Forest type classification for Nepal
Classes:
  1 = Shorea robusta Forest
  2 = Tropical Mixed Broadleaved Forest
  3 = Subtropical Mixed Broadleaved Forest
  4 = Shorea robusta - Mixed Broadleaved Forest
  5 = Abies Mixed Forest
  6 = Upper Temperate Coniferous Forest
  7 = Cool Temperate Mixed Broadleaved Forest
  8 = Castanopsis Lower Temperate Mixed Broadleaved Forest
  9 = Pinus roxburghii Forest
  10 = Alnus Forest
  11 = Schima Forest
  12 = Pinus roxburghii - Mixed Broadleaved Forest
  13 = Pinus wallichiana Forest
  14 = Warm Temperate Mixed Broadleaved Forest
  15 = Upper Temperate Quercus Forest
  16 = Rhododendron arboreum Forest
  17 = Temperate Rhododendron Mixed Broadleaved Forest
  18 = Dalbergia sissoo-Senegalia catechu Forest
  19 = Terminalia - Tropical Mixed Broadleaved Forest
  20 = Temperate Mixed Broadleaved Forest
  21 = Tropical Deciduous Indigenous Riverine Forest
  22 = Tropical Riverine Forest
  23 = Lower Temperate Mixed robusta Forest
  24 = Pinus roxburghii - Shorea robusta Forest
  25 = Lower Temperate Pinus roxburghii - Quercus Forest
  26 = Non forest
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- min_temp_coldest_month
COMMENT ON TABLE rasters.min_temp_coldest_month IS
'Source: WORLDCLIM/V1/BIO
Band name: bio06
Description: Minimum temperature of coldest month
Pixel Size: 0.00833333 dd (927.67m)
Unit: deg;C
Scale: 0.1
Pixel Type: Float64 - Sixty four bit floating point
Data Type: continuous data';

-- forest_loss_fire
COMMENT ON TABLE rasters.forest_loss_fire IS
'Source: users/sashatyu/2001-2024_fire_forest_loss_annual
Band: Band 1
Description: Forest loss due to fire by year (2001-2024)
Values: 0-24
  0 = no forest loss due to fire
  1-24 = year of forest loss (1=2001, 2=2002, ..., 24=2024)
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Unit: year
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- nepal_forest_health
COMMENT ON TABLE rasters.nepal_forest_health IS
'Source: Sentinel-2 NDVI
Band name: band 1
Description: Forest health classification based on NDVI
Classes:
  1 = Stressed (NDVI < 0.2)
  2 = Poor (NDVI 0.2 - 0.4)
  3 = Moderate (NDVI 0.4 - 0.6)
  4 = Healthy (NDVI 0.6 - 0.8)
  5 = Excellent (NDVI > 0.8)
Pixel Size: 8.98315e-05, -8.98315e-05 dd (10m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- nepal_gain
COMMENT ON TABLE rasters.nepal_gain IS
'Source: UMD/hansen/global_forest_change_2024_v1_12
Band name: band 1
Description: Forest gain (2000-2012)
Values:
  0 = no forest gain
  1 = forest gain
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- nepal_lossyear
COMMENT ON TABLE rasters.nepal_lossyear IS
'Source: UMD/hansen/global_forest_change_2024_v1_12
Band name: band 1
Description: Year of forest loss (2001-2024)
Values:
  0 = no forest loss
  1-24 = year of forest loss (1=2001, 2=2002, ..., 24=2024)
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- soilgrids_isric
COMMENT ON TABLE rasters.soilgrids_isric IS
'Source: soilgrids_isric
Description: Soil properties from ISRIC SoilGrids
Bands:
  Band 1 = clay_g_kg (Clay content in g/kg)
  Band 2 = sand_g_kg (Sand content in g/kg)
  Band 3 = silt_g_kg (Silt content in g/kg)
  Band 4 = ph_h2o (Soil pH in H2O)
  Band 5 = soc_dg_kg (Soil organic carbon in dg/kg)
  Band 6 = nitrogen_cg_kg (Nitrogen content in cg/kg)
  Band 7 = bdod_cg_cm3 (Bulk density in cg/cm3)
  Band 8 = cec_mmol_kg (Cation exchange capacity in mmol/kg)
Pixel Size: 0.002245788210298803843, -0.002245788210298803843 dd (250m)
Pixel Type: Float32 - Thirty two bit floating point
Data Type: continuous data';

-- aspect
COMMENT ON TABLE rasters.aspect IS
'Source: derived from USGS/SRTMGL1_003
Description: Terrain aspect (direction of slope)
Classes:
  0 = Flat (slope < 2°)
  1 = N (337.5° - 22.5°)
  2 = NE (22.5° - 67.5°)
  3 = E (67.5° - 112.5°)
  4 = SE (112.5° - 157.5°)
  5 = S (157.5° - 202.5°)
  6 = SW (202.5° - 247.5°)
  7 = W (247.5° - 292.5°)
  8 = NW (292.5° - 337.5°)
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';

-- slope
COMMENT ON TABLE rasters.slope IS
'Source: derived from USGS/SRTMGL1_003
Description: Terrain slope classification
Classes:
  1 = <10° (Gentle/Flat)
  2 = 10-20° (Moderate)
  3 = 20-30° (Steep)
  4 = >30° (Very Steep)
Pixel Size: 0.000269495, -0.000269495 dd (30m)
Pixel Type: Byte - Eight bit unsigned integer
Data Type: categorical data';
