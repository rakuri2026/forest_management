# Report Export Strategy - Excel & Word Documents

**Date:** February 10, 2026
**Status:** Design Proposal
**Purpose:** Define export formats for forest analysis reports suitable for government submission and stakeholder distribution

---

## Executive Summary

Forest management reports need to be exported in professional formats for:
- Government agency submissions (Department of Forests, District Forest Office)
- Community Forest User Group (CFUG) meetings
- Stakeholder presentations
- Archival and record-keeping
- Further analysis and customization

This document proposes **3 export formats** with different purposes and structures.

---

## Export Format Overview

### 1. **Excel Workbook** (Primary Data Format)
**Purpose:** Data analysis, customization, integration with other tools
**File Format:** `.xlsx` (Excel 2007+)
**Best For:** Technical users, further analysis, data sharing

### 2. **Word Document** (Official Report Format)
**Purpose:** Government submissions, official reports, printing
**File Format:** `.docx` (Word 2007+)
**Best For:** Formal submissions, presentations, archival

### 3. **PDF Report** (Distribution Format)
**Purpose:** Read-only distribution, presentations, web sharing
**File Format:** `.pdf`
**Best For:** Stakeholders, email distribution, web publishing

---

## 1. Excel Export Structure

### Workbook Organization (Multi-Sheet)

```
📊 Forest_Analysis_[ForestName]_[Date].xlsx
├─ 📄 Summary (Overview Dashboard)
├─ 📄 Forest_Characteristics
├─ 📄 Terrain_Climate
├─ 📄 LandCover_Change
├─ 📄 Soil_Analysis
├─ 📄 Location_Context
├─ 📄 Block_Comparison (if multiple blocks)
├─ 📄 Block_1_Kathe (detailed)
├─ 📄 Block_2_Gairibas (detailed)
├─ 📄 Raw_Data (GeoJSON, coordinates)
└─ 📄 Metadata (processing info, dates)
```

### Sheet 1: Summary Dashboard

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ COMMUNITY FOREST ANALYSIS REPORT                        │
│ Forest Name: [Name]            Date: [Date]            │
│ Total Area: [X] ha             Blocks: [N]             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ KEY METRICS                                             │
│ ┌──────────────┬──────────────┬──────────────┐        │
│ │ Parameter    │ Value        │ Unit         │        │
│ ├──────────────┼──────────────┼──────────────┤        │
│ │ Total Area   │ 145.6        │ hectares     │        │
│ │ Elevation    │ 800-1,500    │ meters       │        │
│ │ Mean Elev    │ 1,234        │ meters       │        │
│ │ Carbon Stock │ 12,450       │ Mg           │        │
│ │ Forest Health│ Healthy      │ -            │        │
│ └──────────────┴──────────────┴──────────────┘        │
│                                                          │
│ CHARTS (Embedded)                                       │
│ • Slope Distribution (Pie Chart)                       │
│ • Aspect Distribution (Pie Chart)                      │
│ • Forest Loss Timeline (Bar Chart)                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Formatted headers with merge cells
- Color-coded cells (green for healthy, red for poor)
- Embedded charts (Excel native charts)
- Conditional formatting for percentages
- Print-ready layout (A4 portrait)

### Sheet 2: Forest_Characteristics

**Table Structure:**
```
A          | B                    | C          | D
-----------+----------------------+------------+------------------
Parameter  | Value                | Unit       | Details/Notes
-----------+----------------------+------------+------------------
[CANOPY STRUCTURE]
Dominant   | Dense Forest         | -          | 45.2% of area
Mean Height| 18.5                 | meters     |
Class Dist | Dense: 45.2%        |            | Medium: 28.1%
           | Sparse: 15.3%       |            | Open: 11.4%

[ABOVE GROUND BIOMASS]
Total AGB  | 12,450              | Mg         | Total biomass
Mean AGB   | 85.5                | Mg/ha      | Per hectare
Carbon     | 6,225               | Mg         | 50% of AGB

[FOREST HEALTH]
Dominant   | Healthy             | -          | 60.2% of area
V. Healthy | 15.3                | %          |
Healthy    | 60.2                | %          |
Moderate   | 18.7                | %          |
Poor       | 4.8                 | %          |
V. Poor    | 1.0                 | %          |

[FOREST TYPE & SPECIES]
Dominant   | Sal Forest          | -          | 65.3% of area
Type Dist  | Sal: 65.3%         |            | Mixed: 22.1%
           | Pine: 8.5%         |            | Other: 4.1%

[POTENTIAL SPECIES] (Top 10)
#  | Local Name  | Scientific Name        | Economic Value | Role
1  | Sal         | Shorea robusta         | High          | Primary
2  | Chirpine    | Pinus roxburghii       | High          | Primary
...
```

**Features:**
- Section headers in bold, colored background
- Hierarchical organization with merged cells
- Species table formatted with borders
- Conditional formatting for percentages
- Comments/notes column for context

### Sheet 3: Terrain_Climate

**Dual Table Layout:**
```
TOPOGRAPHY                          | CLIMATE
------------------------------------+-----------------------------------
Parameter    | Value    | Details   | Parameter      | Value    | Unit
-------------+----------+-----------+----------------+----------+-------
Elevation Min| 800      | meters    | Mean Temp      | 18.5     | °C
Elevation Max| 1,500    | meters    | Min Temp       | 8.2      | °C
Mean Elev    | 1,234    | meters    | (Coldest Month)|          |
Range        | 700      | meters    | Annual Precip  | 1,850    | mm/yr

SLOPE DISTRIBUTION              | ASPECT DISTRIBUTION
--------------------------------+--------------------------------
Class     | Percentage | Area(ha)| Direction | Percentage | Area(ha)
----------+------------+---------+-----------+------------+---------
Gentle    | 12.5       | 18.2    | North     | 15.2       | 22.1
Moderate  | 35.8       | 52.1    | Northeast | 12.5       | 18.2
Steep     | 40.2       | 58.5    | East      | 18.3       | 26.6
Very Steep| 11.5       | 16.8    | Southeast | 10.1       | 14.7
                                 | South     | 20.4       | 29.7
                                 | Southwest | 8.7        | 12.7
                                 | West      | 9.6        | 14.0
                                 | Northwest | 5.2        | 7.6

[PIE CHARTS EMBEDDED BELOW EACH TABLE]
```

### Sheet 4: LandCover_Change

**Timeline Format:**
```
LAND COVER EVOLUTION

Year | Dominant Class    | Percentage | Secondary Class | Percentage
-----+-------------------+------------+-----------------+------------
1984 | Forest            | 70.5       | Shrubland       | 18.3
2000 | Dense Forest      | 75.2       | Forest          | 15.8
2023 | Dense Forest      | 78.3       | Forest          | 12.1

FOREST CHANGE DETECTION (2001-2023)

FOREST LOSS BY YEAR
Year | Loss (ha) | Loss (%) | Cumulative Loss (ha)
-----+-----------+----------+---------------------
2001 | 0.5       | 0.34     | 0.5
2002 | 0.3       | 0.21     | 0.8
2003 | 1.2       | 0.82     | 2.0
...
2023 | 0.8       | 0.55     | 15.3

Total Loss: 15.3 ha (10.5% of 2000 forest area)

FOREST GAIN (2000-2012)
Total Gain: 8.7 ha
Net Change: -6.6 ha (net loss)

FIRE-RELATED LOSS BY YEAR
[Similar table structure]

[BAR CHART: Loss by Year - embedded]
```

### Sheet 5: Soil_Analysis

**Comprehensive Soil Data:**
```
SOIL TEXTURE
Parameter          | Value           | System    | Notes
-------------------+-----------------+-----------+------------------
Texture Class      | Loamy Sand      | USDA      |
Sand %             | 75.3            | %         |
Silt %             | 18.2            | %         |
Clay %             | 6.5             | %         |

FERTILITY ASSESSMENT
Fertility Class    | High            |           | Score: 75/100
Limiting Factors   | Low Nitrogen    |           |
                   | Phosphorus Def. |           |

CARBON CONTENT
Organic Carbon     | 45.2            | t/ha      | Topsoil (0-30cm)
Sequestration Pot. | Medium          |           |

COMPACTION STATUS
Status             | Not Compacted   |           | No action needed
Bulk Density       | 1.32            | g/cm³     | Acceptable range

DRAINAGE & pH
Drainage Class     | Well Drained    |           |
pH Range           | 5.5-6.5         |           | Slightly acidic

[COLOR-CODED CELLS: Green=Good, Yellow=Moderate, Red=Poor]
```

### Sheet 6: Location_Context

**Geographic Information:**
```
ADMINISTRATIVE BOUNDARIES
Level          | Name                    | Code (if applicable)
---------------+-------------------------+---------------------
Province       | Bagmati Province        | 3
District       | Makawanpur              |
Municipality   | Hetauda Sub-Metro       |
Ward           | 5                       |

WATERSHED & HYDROLOGY
Watershed              | Bagmati River Watershed
Major River Basin      | Gandaki River Basin
Drainage Density       | Medium
Water Sources          | [List streams/rivers]

GEOGRAPHIC CLASSIFICATIONS
Classification | Dominant Type        | Percentage | Secondary
---------------+----------------------+------------+------------
Geology        | Sedimentary          | 65.3       | Metamorphic (34.7%)
Physiography   | Middle Mountains     | 100.0      | -
Ecoregion      | Himalayan Sub-Trop.  | 100.0      | -
NASA Forest    | Closed Canopy        | 78.5       | Open Canopy (21.5%)

DIRECTIONAL FEATURES (Within 100m)
Direction | Features
----------+--------------------------------------------------
North     | Agricultural land, scattered settlements
East      | Dense forest, seasonal stream
South     | Community grazing area, dirt road
West      | Forest continuation, no major features
```

### Sheet 7: Block_Comparison (Multi-Block Forests)

**Side-by-Side Comparison:**
```
Parameter           | Block 1: Kathe | Block 2: Gairibas | Block 3: Danda | Notes
--------------------+----------------+-------------------+----------------+-------
Area (ha)           | 45.2           | 38.7              | 61.7           |
Elevation Mean (m)  | 1,234          | 1,156             | 1,389          |
Slope Class         | Steep          | Moderate          | Very Steep     |
Dominant Aspect     | South          | East              | North          |
Canopy Class        | Dense          | Medium            | Dense          |
Forest Health       | Healthy        | Healthy           | Moderate       |
Carbon Stock (Mg)   | 3,850          | 3,100             | 5,500          |
Carbon/ha (Mg/ha)   | 85.2           | 80.1              | 89.1           |
Forest Loss (ha)    | 2.1            | 1.8               | 3.5            |
Soil Texture        | Loamy Sand     | Sandy Loam        | Clay Loam      |
Fertility Class     | High           | Medium            | High           |

[EMBEDDED CHARTS: Bar charts comparing key metrics across blocks]
```

### Sheets 8-N: Individual Block Details

Each block gets its own sheet with full analysis (same structure as whole forest sections).

### Sheet: Raw_Data

**Machine-Readable Data:**
```
GEOMETRY (WKT)
Block Name | WKT Geometry
-----------+------------------------------------------------------------
Kathe      | POLYGON((83.123 27.456, 83.124 27.457, ...))
Gairibas   | POLYGON((83.125 27.458, 83.126 27.459, ...))

FIELDBOOK COORDINATES
Block | Point# | Latitude  | Longitude | Elevation | Type
------+--------+-----------+-----------+-----------+----------
Kathe | 1      | 27.45612  | 83.12345  | 1234      | Vertex
Kathe | 2      | 27.45623  | 83.12356  | 1235      | Interpolated

ANALYSIS PARAMETERS (JSON)
[Raw JSON data for programmatic access]
```

### Sheet: Metadata

**Processing Information:**
```
DOCUMENT INFORMATION
Parameter              | Value
-----------------------+----------------------------------------
Forest Name            | [Name]
Calculation ID         | [UUID]
Generated Date         | 2026-02-10 14:30:00 UTC
Generated By           | [User Name] ([Email])
Organization           | [Organization Name]
Software Version       | Forest Management System v1.2.1
Database Version       | PostgreSQL 15.3 / PostGIS 3.6

PROCESSING DETAILS
Uploaded File          | boundary_kathe.kml
Upload Date            | 2026-02-08 10:15:23 UTC
Processing Time        | 45 seconds
Status                 | Completed
Number of Blocks       | 3
Total Vertices         | 156
Coordinate System      | EPSG:4326 (WGS84)
Area Calculation SRID  | EPSG:32645 (UTM Zone 45N)

DATA SOURCES
Parameter          | Source Dataset              | Date
-------------------+-----------------------------+----------
Elevation          | SRTM DEM 30m                | 2000
Slope/Aspect       | Derived from DEM            | 2000
Canopy Height      | Global Canopy Height 2020   | 2020
Forest Type        | Nepal Forest Type Map       | 2015
Land Cover         | ESA WorldCover              | 2021
Forest Loss/Gain   | Hansen Global Forest Change | 2023
Temperature        | WorldClim Bio1              | 1970-2000
Precipitation      | WorldClim Bio12             | 1970-2000
Soil               | SoilGrids ISRIC             | 2020
```

---

## 2. Word Document Export Structure

### Document Layout (Official Report Format)

```
📄 Forest_Analysis_Report_[ForestName]_[Date].docx

┌─────────────────────────────────────────┐
│         [COVER PAGE]                    │
│                                          │
│   COMMUNITY FOREST                      │
│   ANALYSIS REPORT                       │
│                                          │
│   [Forest Name]                         │
│   [Location]                            │
│                                          │
│   Prepared: [Date]                      │
│   By: [Organization]                    │
│                                          │
│   [Logo/Seal]                           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│      TABLE OF CONTENTS                  │
│                                          │
│  1. Executive Summary.............. 3   │
│  2. Forest Overview................ 5   │
│  3. Forest Characteristics......... 7   │
│  4. Terrain & Climate.............. 12  │
│  5. Land Cover & Change............ 15  │
│  6. Soil Analysis.................. 19  │
│  7. Location & Context............. 22  │
│  8. Block-wise Details............. 25  │
│  9. Recommendations................ 35  │
│  10. Appendices.................... 38  │
└─────────────────────────────────────────┘
```

### Section 1: Executive Summary (1-2 pages)

**Content:**
```
1. EXECUTIVE SUMMARY

Overview
This report presents a comprehensive analysis of [Forest Name] community
forest located in [District], [Province]. The analysis was conducted on
[Date] using satellite imagery, raster datasets, and field-verified
boundaries.

Key Findings
• Total Forest Area: 145.6 hectares (divided into 3 management blocks)
• Forest Health: Predominantly Healthy (60.2% of area)
• Carbon Stock: 12,450 Mg total (85.5 Mg/ha average)
• Elevation Range: 800-1,500 meters above sea level
• Dominant Forest Type: Sal Forest (65.3% of area)
• Recent Forest Loss: 15.3 ha (2001-2023), primarily due to [causes]

Management Implications
Based on the analysis, the forest shows good overall health with
significant carbon sequestration potential. Priority areas for management
attention include:
1. Monitoring and preventing further forest loss in Block 3
2. Soil conservation measures on steep slopes (40% of area)
3. Species diversification in monoculture areas

Recommendations
[Top 3-5 actionable recommendations]
```

### Section 2: Forest Overview (2-3 pages)

**Content:**
```
2. FOREST OVERVIEW

2.1 Location and Access
[Map image showing forest location in district/province context]

Province: Bagmati Province
District: Makawanpur
Municipality: Hetauda Sub-Metropolitan City
Ward: 5
GPS Coordinates: 27.4562°N, 83.1234°E (centroid)

Access: The forest is accessible via [route description]

2.2 Administrative Context
[Description of administrative arrangements, user groups, etc.]

2.3 Area and Boundary
Total Area: 145.6 hectares
Number of Blocks: 3
Perimeter: 5.8 km

[Map image showing forest boundary with blocks labeled]

Block Distribution:
• Block 1 (Kathe): 45.2 ha (31.0%)
• Block 2 (Gairibas): 38.7 ha (26.6%)
• Block 3 (Danda): 61.7 ha (42.4%)

2.4 Extent Coordinates
Northern Extent: 27.4678°N
Southern Extent: 27.4523°N
Eastern Extent: 83.1345°E
Western Extent: 83.1198°E
```

### Section 3: Forest Characteristics (4-5 pages)

**Content:**
```
3. FOREST CHARACTERISTICS

3.1 Canopy Structure
The forest exhibits predominantly dense canopy cover, indicating good
forest health and productivity.

Canopy Height Distribution:
[Bar chart image]

• Dense Forest (>15m): 45.2% of area
• Medium Forest (10-15m): 28.1% of area
• Sparse Forest (5-10m): 15.3% of area
• Open/Degraded (<5m): 11.4% of area

Mean Canopy Height: 18.5 meters

Analysis: The high percentage of dense canopy indicates mature forest
with good regeneration potential...

3.2 Above Ground Biomass and Carbon Stock
[Table with biomass data]

Total Above Ground Biomass: 12,450 Mg
Mean Biomass Density: 85.5 Mg/ha
Total Carbon Stock: 6,225 Mg (50% of AGB)
Carbon Density: 42.8 Mg C/ha

Comparison: This carbon density is [above/below] the national average
for similar forest types...

3.3 Forest Health Status
[Pie chart image showing health distribution]

Health Classification:
• Very Healthy: 15.3%
• Healthy: 60.2% (dominant)
• Moderate: 18.7%
• Poor: 4.8%
• Very Poor: 1.0%

Overall Assessment: The forest is in good health with 75.5% classified
as healthy or very healthy...

3.4 Forest Type and Composition
[Horizontal bar chart showing forest type percentages]

Dominant Forest Type: Sal Forest (Shorea robusta dominated)
Coverage: 65.3% of total area

Forest Type Distribution:
1. Sal Forest: 65.3% (95.1 ha)
2. Mixed Broadleaf: 22.1% (32.2 ha)
3. Pine Forest: 8.5% (12.4 ha)
4. Other: 4.1% (6.0 ha)

3.5 Potential Tree Species
Based on elevation, climate, soil conditions, and regional species
distribution, the following tree species show high potential for
successful growth in this forest:

[Table: Top 10 Species]
#  | Local Name | Scientific Name      | Economic Value | Ecological Role
---|------------|----------------------|----------------|------------------
1  | Sal        | Shorea robusta       | High          | Primary canopy
2  | Chirpine   | Pinus roxburghii     | High          | Primary canopy
3  | Chilaune   | Schima wallichii     | Medium        | Secondary canopy
...

[Full species list with descriptions in Appendix A]
```

### Section 4: Terrain & Climate (3-4 pages)

```
4. TERRAIN & CLIMATE ANALYSIS

4.1 Elevation Profile
[Elevation map or profile chart]

Minimum Elevation: 800 m
Maximum Elevation: 1,500 m
Mean Elevation: 1,234 m
Elevation Range: 700 m

Classification: Middle Mountains physiographic zone

4.2 Slope Analysis
[Slope map with color-coded classes]

Slope Distribution:
[Table with slope classes, percentages, areas, management implications]

Class       | Percentage | Area (ha) | Management Implications
------------|------------|-----------|---------------------------
Gentle      | 12.5%      | 18.2      | Suitable for all activities
Moderate    | 35.8%      | 52.1      | Standard management practices
Steep       | 40.2%      | 58.5      | Erosion control needed
Very Steep  | 11.5%      | 16.8      | Protection priority, limited access

Recommendation: 51.7% of the forest is on steep to very steep slopes,
requiring careful management to prevent soil erosion...

4.3 Aspect Analysis
[Compass rose diagram or aspect map]

Dominant Aspect: South-facing (20.4%)
[Table with all directions and percentages]

Implications for Management:
• South-facing slopes: Higher solar radiation, drier conditions
• North-facing slopes: Cooler, moister microclimate
• Species selection should account for aspect variation

4.4 Climate Conditions
[Climate chart or table]

Temperature:
• Annual Mean: 18.5°C
• Minimum (Coldest Month): 8.2°C
• Maximum (Warmest Month): 28.3°C [if available]

Precipitation:
• Annual Total: 1,850 mm
• Distribution: Monsoon-dominated (June-September)

Climate Classification: Humid Subtropical Highland

Suitability: Climate conditions are favorable for diverse sub-tropical
and warm-temperate species...
```

### Section 5: Land Cover & Change (3-4 pages)

```
5. LAND COVER AND FOREST CHANGE ANALYSIS

5.1 Land Cover Evolution
[Timeline graphic showing 1984 → 2000 → 2023]

Historical Land Cover Trends:
[Table showing land cover at three time periods]

Year | Dominant Class  | Coverage | Observations
-----|-----------------|----------|------------------
1984 | Forest          | 70.5%    | Baseline year
2000 | Dense Forest    | 75.2%    | Improvement (+4.7%)
2023 | Dense Forest    | 78.3%    | Continued improvement (+3.1%)

Trend Analysis: The forest has shown consistent improvement over the
39-year period, with forest cover increasing by 7.8 percentage points...

5.2 Forest Loss Analysis (2001-2023)
[Bar chart showing annual forest loss]

Total Forest Loss: 15.3 hectares (10.5% of 2000 forest extent)
Annual Average Loss: 0.67 ha/year

Peak Loss Years:
• 2003: 1.2 ha (severe drought)
• 2015: 1.8 ha (earthquake-related damage)
• 2019: 1.4 ha (illegal logging incident)

[Detailed table with year-by-year breakdown in Appendix]

5.3 Forest Gain (2000-2012)
Total Forest Gain: 8.7 hectares
Net Change: -6.6 hectares (net loss over full period)

Areas of Regeneration:
[Description of where gain occurred, possibly with map]

5.4 Fire-Related Forest Loss
Total Fire Loss: 2.3 hectares (15% of total loss)
Fire Years: 2009 (0.8 ha), 2016 (0.9 ha), 2021 (0.6 ha)

Fire Risk Assessment: Moderate risk during dry season (March-May)
Recommendations: Fire line maintenance, community fire watch program
```

### Section 6: Soil Analysis (3 pages)

```
6. SOIL ANALYSIS

6.1 Soil Texture and Composition
[Soil texture triangle diagram if possible]

Texture Class: Loamy Sand (USDA classification)
Particle Size Distribution:
• Sand: 75.3%
• Silt: 18.2%
• Clay: 6.5%

Characteristics: Well-drained, low water retention, moderate fertility

6.2 Soil Fertility Assessment
[Table or color-coded chart]

Fertility Class: High (Score: 75/100)

Nutrient Status:
• Nitrogen: Low (limiting factor)
• Phosphorus: Deficient (limiting factor)
• Potassium: Adequate
• Organic Matter: Moderate

Recommendations:
1. Nitrogen-fixing species (legumes) to improve N content
2. Organic matter addition through mulching
3. Avoid removal of leaf litter

6.3 Soil Carbon Stock
Organic Carbon Stock: 45.2 t/ha (topsoil 0-30cm)
Total Soil Carbon: 657 tonnes

Combined Carbon Storage:
• Above-ground biomass: 6,225 Mg
• Soil (topsoil): 657 Mg
• Total: 6,882 Mg (47.3 Mg/ha)

Carbon Sequestration Potential: Medium

6.4 Compaction Status
Status: Not Compacted
Bulk Density: 1.32 g/cm³ (acceptable range)
Assessment: No compaction issues detected. Maintain low-impact
harvesting practices to prevent future compaction.
```

### Section 7: Location & Context (2-3 pages)

```
7. LOCATION AND ADMINISTRATIVE CONTEXT

7.1 Administrative Boundaries
[Administrative map]

Province: Bagmati Province (Province 3)
District: Makawanpur
Municipality: Hetauda Sub-Metropolitan City
Ward: Ward No. 5

7.2 Watershed and Hydrology
Watershed: Bagmati River Watershed
Major River Basin: Gandaki River Basin
Sub-basin: [If applicable]

Water Features:
• Seasonal streams: 2 (East and North boundaries)
• Springs: None identified
• Wetlands: None present

7.3 Geographic Classifications
[Table with classifications]

Classification   | Type                        | Coverage
-----------------|-----------------------------|----------
Geology          | Sedimentary (65.3%)         | Dominant
Physiography     | Middle Mountains            | 100%
Ecoregion        | Himalayan Subtropical       | 100%
Forest Type      | Closed Canopy (78.5%)       | Dominant

7.4 Surrounding Land Use and Features
[Directional features diagram or map]

Northern Boundary: Agricultural land, scattered settlements
Eastern Boundary: Dense forest continuation, seasonal stream
Southern Boundary: Community grazing area, rural road access
Western Boundary: Forest continuation, no major human activity

Proximity to Infrastructure:
• Nearest road: 500m (south)
• Nearest settlement: 1.2 km (north)
• District headquarters: 15 km

7.5 Community Forest User Group
[If data available]
User Group Name: [Name]
Total Households: [Number]
Population: [Number]
Formation Date: [Date]
```

### Section 8: Block-wise Details (2-3 pages per block)

```
8. DETAILED BLOCK-WISE ANALYSIS

8.1 Block 1: Kathe
[Repeat full analysis structure for each block]
Area: 45.2 ha (31.0% of total)
[All parameters: elevation, slope, canopy, biomass, etc.]
[Block-specific map]

8.2 Block 2: Gairibas
[Similar structure]

8.3 Block 3: Danda
[Similar structure]

8.4 Block Comparison Summary
[Comparison table from Excel sheet]
[Comparative charts showing key metrics across blocks]

Management Recommendations by Block:
Block 1 (Kathe): [Specific recommendations]
Block 2 (Gairibas): [Specific recommendations]
Block 3 (Danda): [Specific recommendations]
```

### Section 9: Recommendations (2-3 pages)

```
9. MANAGEMENT RECOMMENDATIONS

Based on the comprehensive analysis, the following recommendations are
proposed for sustainable management of [Forest Name]:

9.1 Short-term Actions (1-2 years)
1. Fire Prevention
   - Establish firebreaks in high-risk areas
   - Organize community fire watch during dry season
   - Conduct fire awareness training

2. Erosion Control
   - Install check dams on steep slopes (Blocks 1 and 3)
   - Plant grasses on exposed slopes
   - Maintain vegetative cover

3. Monitoring and Protection
   - Regular patrolling in Block 3 (highest loss area)
   - Establish permanent sample plots for monitoring
   - Mark and monitor boundary clearly

9.2 Medium-term Actions (3-5 years)
1. Regeneration and Enrichment
   - Identify and plant native species in degraded areas
   - Focus on nitrogen-fixing species for soil improvement
   - Establish nursery for native species

2. Soil Fertility Enhancement
   - Promote leaf litter retention
   - Discourage fodder collection in degraded areas
   - Consider controlled composting

3. Carbon Enhancement
   - Protect existing high-carbon density areas
   - Focus regeneration on low-carbon blocks
   - Explore carbon credit opportunities

9.3 Long-term Actions (5-10 years)
1. Sustainable Harvesting Plan
   - Develop block-wise rotation plan
   - Maintain forest cover above 70%
   - Selective harvesting in mature stands

2. Biodiversity Conservation
   - Identify and protect rare species
   - Create wildlife corridors
   - Maintain habitat heterogeneity

3. Climate Adaptation
   - Monitor climate change impacts
   - Diversify species composition
   - Increase resilience through mixed forests

9.4 Monitoring Framework
Annual Monitoring:
- Forest health assessment
- Fire occurrence and damage
- Illegal activity incidents

5-year Monitoring:
- Carbon stock re-assessment
- Canopy cover change
- Species composition change
- Boundary verification
```

### Section 10: Appendices

```
10. APPENDICES

Appendix A: Complete Potential Species List
[Full table with 20-30 species, descriptions, uses]

Appendix B: Detailed Forest Loss Data by Year
[Year-by-year table with causes if known]

Appendix C: Fieldbook Coordinates
[Table of boundary vertices and interpolated points]

Appendix D: Technical Methodology
- Data sources and dates
- Processing methods
- Accuracy assessment
- Coordinate systems used

Appendix E: Maps
- Location map
- Block boundary map
- Slope map
- Aspect map
- Land cover map
- Forest loss/gain map

Appendix F: Glossary of Terms
[Definitions of technical terms used in report]

Appendix G: References
[Citations for datasets, methods, standards]
```

### Document Formatting Standards

**Fonts:**
- Headings: Arial Bold, 14-16pt
- Body Text: Times New Roman, 12pt
- Tables: Arial, 10pt
- Captions: Arial Italic, 10pt

**Spacing:**
- Line spacing: 1.5 for body text
- Before heading: 12pt
- After heading: 6pt
- Margins: 1 inch (2.54 cm) all sides

**Page Layout:**
- Paper size: A4 (210mm × 297mm)
- Orientation: Portrait (Landscape for wide tables)
- Header: Document title + page number
- Footer: Organization name + Date

**Colors:**
- Headers: Dark green (#2C5530)
- Captions: Dark gray (#333333)
- Tables: Alternating row colors (white/light gray)
- Charts: Earth tones (greens, browns, blues)

---

## 3. PDF Export (Read-Only Distribution)

**Generation Method:**
- Convert Word document to PDF
- Or generate directly with PDF library

**Features:**
- Embedded fonts for universal viewing
- Compressed images for smaller file size
- Hyperlinked table of contents
- Bookmarks for navigation
- Form fields locked (read-only)

**Security Options:**
- Password protection (optional)
- Prevent editing
- Allow printing
- Allow copying text (for accessibility)

---

## Implementation Technical Details

### Backend API Endpoints

```python
# New endpoints in backend/app/api/forests.py

@router.get("/calculations/{calculation_id}/export/excel")
async def export_calculation_excel(
    calculation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export calculation results as Excel workbook
    Returns: Excel file download
    """
    # Generate Excel using openpyxl or xlsxwriter
    # Return as downloadable file
    pass

@router.get("/calculations/{calculation_id}/export/word")
async def export_calculation_word(
    calculation_id: str,
    template: str = "standard",  # standard, detailed, summary
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export calculation results as Word document
    Returns: Word file download
    """
    # Generate Word doc using python-docx
    # Return as downloadable file
    pass

@router.get("/calculations/{calculation_id}/export/pdf")
async def export_calculation_pdf(
    calculation_id: str,
    template: str = "standard",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export calculation results as PDF
    Returns: PDF file download
    """
    # Generate PDF using reportlab or convert from Word
    # Return as downloadable file
    pass
```

### Python Libraries Required

```python
# For Excel Export
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment
from openpyxl.chart import PieChart, BarChart, LineChart
from openpyxl.drawing.image import Image

# For Word Export
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# For PDF Export
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
# OR convert Word to PDF
import docx2pdf

# For Charts/Visualization
import matplotlib.pyplot as plt
import io
from PIL import Image as PILImage
```

### Excel Generation Example

```python
# backend/app/services/export_excel.py

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import PieChart, BarChart, Reference
import io

class ExcelReportGenerator:
    def __init__(self, calculation_data):
        self.data = calculation_data
        self.wb = Workbook()

    def generate(self):
        """Generate complete Excel workbook"""
        # Remove default sheet
        self.wb.remove(self.wb.active)

        # Create sheets
        self._create_summary_sheet()
        self._create_forest_characteristics_sheet()
        self._create_terrain_climate_sheet()
        self._create_landcover_change_sheet()
        self._create_soil_analysis_sheet()
        self._create_location_context_sheet()

        if len(self.data.get('blocks', [])) > 1:
            self._create_block_comparison_sheet()

        for idx, block in enumerate(self.data.get('blocks', [])):
            self._create_block_detail_sheet(block, idx)

        self._create_raw_data_sheet()
        self._create_metadata_sheet()

        # Return as bytes
        output = io.BytesIO()
        self.wb.save(output)
        output.seek(0)
        return output

    def _create_summary_sheet(self):
        """Create Summary dashboard sheet"""
        ws = self.wb.create_sheet("Summary", 0)

        # Header
        ws['A1'] = "COMMUNITY FOREST ANALYSIS REPORT"
        ws['A1'].font = Font(size=16, bold=True, color="FFFFFF")
        ws['A1'].fill = PatternFill(start_color="2C5530", end_color="2C5530", fill_type="solid")
        ws.merge_cells('A1:D1')

        # Forest info
        ws['A2'] = "Forest Name:"
        ws['B2'] = self.data.get('forest_name', 'N/A')
        ws['C2'] = "Date:"
        ws['D2'] = self.data.get('created_at', 'N/A')

        # Key metrics table
        row = 4
        ws[f'A{row}'] = "KEY METRICS"
        ws[f'A{row}'].font = Font(size=14, bold=True)

        row += 1
        headers = ['Parameter', 'Value', 'Unit', 'Notes']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

        # Add metrics
        metrics = [
            ('Total Area', self.data.get('area_hectares'), 'hectares', ''),
            ('Elevation (Mean)', self.data.get('elevation_mean_m'), 'meters', ''),
            ('Carbon Stock', self.data.get('carbon_stock_mg'), 'Mg', 'Above-ground'),
            ('Forest Health', self.data.get('forest_health_dominant'), '-', ''),
            # ... more metrics
        ]

        for metric in metrics:
            row += 1
            for col, value in enumerate(metric, start=1):
                ws.cell(row=row, column=col, value=value)

        # Add charts
        self._add_pie_chart(ws, 'Slope Distribution', ...)

        # Format columns
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 30

    def _add_pie_chart(self, ws, title, data_range):
        """Add pie chart to worksheet"""
        chart = PieChart()
        chart.title = title
        # ... configure chart
        ws.add_chart(chart, 'F5')

    # Similar methods for other sheets...
```

### Word Generation Example

```python
# backend/app/services/export_word.py

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io

class WordReportGenerator:
    def __init__(self, calculation_data, template_type="standard"):
        self.data = calculation_data
        self.template_type = template_type
        self.doc = Document()
        self._setup_styles()

    def _setup_styles(self):
        """Configure document styles"""
        styles = self.doc.styles

        # Heading 1 style
        heading1 = styles['Heading 1']
        heading1.font.name = 'Arial'
        heading1.font.size = Pt(16)
        heading1.font.bold = True
        heading1.font.color.rgb = RGBColor(44, 85, 48)  # Dark green

        # Normal style
        normal = styles['Normal']
        normal.font.name = 'Times New Roman'
        normal.font.size = Pt(12)

    def generate(self):
        """Generate complete Word document"""
        self._add_cover_page()
        self._add_table_of_contents()
        self._add_executive_summary()
        self._add_forest_overview()
        self._add_forest_characteristics()
        self._add_terrain_climate()
        self._add_landcover_change()
        self._add_soil_analysis()
        self._add_location_context()
        self._add_block_details()
        self._add_recommendations()
        self._add_appendices()

        # Return as bytes
        output = io.BytesIO()
        self.doc.save(output)
        output.seek(0)
        return output

    def _add_cover_page(self):
        """Add cover page"""
        # Title
        title = self.doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run("COMMUNITY FOREST\nANALYSIS REPORT")
        title_run.font.size = Pt(24)
        title_run.font.bold = True

        self.doc.add_paragraph()  # Spacing

        # Forest name
        forest_name = self.doc.add_paragraph()
        forest_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fn_run = forest_name.add_run(self.data.get('forest_name', 'N/A'))
        fn_run.font.size = Pt(18)
        fn_run.font.bold = True

        # Add page break
        self.doc.add_page_break()

    def _add_executive_summary(self):
        """Add executive summary section"""
        self.doc.add_heading('1. EXECUTIVE SUMMARY', level=1)

        # Overview paragraph
        self.doc.add_paragraph(
            f"This report presents a comprehensive analysis of "
            f"{self.data.get('forest_name')} community forest located in "
            f"{self.data.get('district')}, {self.data.get('province')}. "
            f"The analysis was conducted on {self.data.get('created_at')} "
            f"using satellite imagery, raster datasets, and field-verified boundaries."
        )

        # Key findings
        self.doc.add_heading('Key Findings', level=2)
        findings = [
            f"Total Forest Area: {self.data.get('area_hectares')} hectares",
            f"Forest Health: {self.data.get('forest_health_dominant')}",
            f"Carbon Stock: {self.data.get('carbon_stock_mg')} Mg total",
            # ... more findings
        ]
        for finding in findings:
            self.doc.add_paragraph(finding, style='List Bullet')

        # Add table
        self._add_key_metrics_table()

    def _add_key_metrics_table(self):
        """Add formatted table with key metrics"""
        table = self.doc.add_table(rows=1, cols=3)
        table.style = 'Light Grid Accent 1'

        # Header row
        header_cells = table.rows[0].cells
        header_cells[0].text = 'Parameter'
        header_cells[1].text = 'Value'
        header_cells[2].text = 'Unit'

        # Data rows
        metrics = [
            ('Total Area', self.data.get('area_hectares'), 'hectares'),
            ('Elevation', self.data.get('elevation_mean_m'), 'meters'),
            # ... more rows
        ]

        for metric in metrics:
            row_cells = table.add_row().cells
            row_cells[0].text = str(metric[0])
            row_cells[1].text = str(metric[1])
            row_cells[2].text = str(metric[2])

    # Similar methods for other sections...
```

### Frontend Download Buttons

```tsx
// frontend/src/pages/CalculationDetail.tsx

const handleExportExcel = async () => {
  try {
    const response = await fetch(
      `${API_URL}/api/forests/calculations/${calculation.id}/export/excel`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Forest_Analysis_${calculation.forest_name}_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (error) {
    console.error('Excel export failed:', error);
  }
};

const handleExportWord = async (template = 'standard') => {
  // Similar to Excel export
};

// In JSX:
<div className="flex gap-4 mt-6">
  <button
    onClick={handleExportExcel}
    className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
  >
    📊 Export to Excel
  </button>
  <button
    onClick={() => handleExportWord('standard')}
    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
  >
    📄 Export to Word (Standard)
  </button>
  <button
    onClick={() => handleExportWord('detailed')}
    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
  >
    📄 Export to Word (Detailed)
  </button>
  <button
    onClick={handleExportPDF}
    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
  >
    📕 Export to PDF
  </button>
</div>
```

---

## Export Template System

### Template Types

**1. Standard Report (Default)**
- All sections included
- Moderate detail level
- 20-30 pages typically
- Suitable for most submissions

**2. Detailed Report (Comprehensive)**
- Extended analysis
- Additional appendices
- Full species lists
- Technical methodology details
- 35-50 pages typically
- For research or detailed planning

**3. Summary Report (Brief)**
- Executive summary + key metrics only
- Block comparison
- Recommendations
- 5-10 pages
- For quick reviews, presentations

**4. Custom Template**
- User-defined sections
- Configurable content
- Save templates for reuse
- Organization-specific formatting

### Template Configuration UI

```tsx
// Export Modal with Template Selection

<Modal>
  <h2>Export Analysis Report</h2>

  <label>Export Format:</label>
  <select>
    <option value="excel">Excel Workbook (.xlsx)</option>
    <option value="word">Word Document (.docx)</option>
    <option value="pdf">PDF Document (.pdf)</option>
  </select>

  <label>Template Type:</label>
  <select>
    <option value="standard">Standard Report</option>
    <option value="detailed">Detailed Report</option>
    <option value="summary">Summary Report</option>
    <option value="custom">Custom Template...</option>
  </select>

  <label>Include Sections:</label>
  <CheckboxGroup>
    <Checkbox checked>Executive Summary</Checkbox>
    <Checkbox checked>Forest Characteristics</Checkbox>
    <Checkbox checked>Terrain & Climate</Checkbox>
    <Checkbox checked>Land Cover & Change</Checkbox>
    <Checkbox checked>Soil Analysis</Checkbox>
    <Checkbox checked>Location & Context</Checkbox>
    <Checkbox checked>Block Details</Checkbox>
    <Checkbox>Recommendations</Checkbox>
    <Checkbox>Full Species List</Checkbox>
    <Checkbox>Methodology</Checkbox>
  </CheckboxGroup>

  <label>Include Maps:</label>
  <CheckboxGroup>
    <Checkbox checked>Boundary Map</Checkbox>
    <Checkbox checked>Slope Map</Checkbox>
    <Checkbox>Aspect Map</Checkbox>
    <Checkbox>Land Cover Map</Checkbox>
  </CheckboxGroup>

  <button>Generate Report</button>
</Modal>
```

---

## Integration with Analysis Page Redesign

### Export Button Placement

**Option 1: Header Action Bar**
```
┌──────────────────────────────────────────────────┐
│ Forest Name: Kathe Community Forest              │
│ Area: 145.6 ha | Date: 2026-02-10                │
│                                                   │
│ [← Back] [Edit] [📊 Export ▼] [Delete]          │
└──────────────────────────────────────────────────┘
```

**Option 2: Tab-Level Export**
```
┌──────────────────────────────────────────────────┐
│ [Analysis] [Fieldbook] [Sampling] [Tree] [Bio]  │
│                             [📊 Export This Tab]  │
├──────────────────────────────────────────────────┤
```

**Option 3: Section-Level Export** (For grouped cards)
```
┌────────────────────────────────────────────┐
│ 🌲 Forest Characteristics    [▼] [Export]  │
└────────────────────────────────────────────┘
```

---

## Success Metrics

### For Excel Export
✅ Generate workbook in <5 seconds for typical forest
✅ All charts embedded and formatted correctly
✅ File size <5MB for typical forest
✅ Opens correctly in Excel 2007+, Google Sheets, LibreOffice

### For Word Export
✅ Generate document in <10 seconds (including charts)
✅ Professional formatting maintained
✅ Images embedded at appropriate resolution
✅ Table of contents auto-generated
✅ File size <10MB

### For PDF Export
✅ Generate PDF in <15 seconds
✅ All fonts embedded
✅ Images high-quality but compressed
✅ Hyperlinks functional
✅ Print-ready (A4, proper margins)

---

## Next Steps

1. **Review and Approve Structure** - Confirm report structure meets needs
2. **Develop Python Export Services** - Implement generation code
3. **Create Report Templates** - Design Word/Excel templates
4. **Build Frontend UI** - Add export buttons and modals
5. **Test with Real Data** - Generate reports for actual forests
6. **User Acceptance Testing** - Get feedback from foresters
7. **Documentation** - User guide for customizing reports

---

**Document Version:** 1.0
**Last Updated:** February 10, 2026
**Status:** Awaiting Review & Implementation
