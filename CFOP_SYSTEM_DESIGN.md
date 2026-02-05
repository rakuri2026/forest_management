# Community Forest Operational Plan (CFOP) System Design

## Executive Summary

This document outlines the design for a comprehensive Community Forest Operational Plan system for foresters in Nepal. The system will support the complete workflow for preparing and renewing operational plans at 5 or 10 year intervals, with multi-session draft support and context-aware navigation.

---

## System Overview

### Target Users
- Foresters working across Nepal
- Multiple concurrent operational plans (5-10+ per year per forester)
- Need for draft/work-in-progress support
- Multi-session workflow (plans completed over days/weeks)

### Core Requirement
Enable foresters to prepare government-compliant Community Forest Operational Plans through:
1. GIS/Remote sensing analysis (existing)
2. Systematic field sampling
3. Forest inventory and analysis
4. User group and committee management
5. Forest product pricing
6. Extensible table uploads

---

## Functional Requirements

### 1. Forest Block-wise Information (EXISTING - Enhanced)

**Current Features:**
- File upload (KML, GeoJSON, Shapefile)
- Area calculation with UTM projection
- 16-parameter raster analysis per block
- Results stored in `calculations` table

**New Requirements:**

#### a. Systematic Point Sampling

**User Choices:**
- **Systematic Sampling**: Regular grid pattern
- **Random Sampling**: Random points within boundary
- **Stratified Random**: Random within strata (e.g., by elevation, slope)

**Configuration Parameters:**
- Sampling intensity (points per hectare)
- Grid spacing (for systematic)
- Minimum distance between points
- Exclusion zones (water bodies, settlements)

**Implementation:**
```python
# New table: sampling_designs
- id (UUID)
- calculation_id (FK to calculations)
- sampling_type (ENUM: systematic, random, stratified)
- intensity_per_hectare (DECIMAL)
- grid_spacing_meters (INTEGER, for systematic)
- min_distance_meters (INTEGER)
- exclusion_geometry (GEOMETRY, optional)
- points_geometry (GEOMETRY(MULTIPOINT))
- total_points (INTEGER)
- created_at (TIMESTAMP)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/create-sampling
  Body: {
    "sampling_type": "systematic",
    "intensity_per_hectare": 0.5,
    "grid_spacing_meters": 50
  }

GET /api/forests/calculations/{id}/sampling-points
  Response: GeoJSON with point locations

PUT /api/forests/calculations/{id}/sampling-points
  Body: Edited GeoJSON (allow manual adjustment)
```

#### b. Fieldbook Table (Boundary Vertices + Interpolated Points)

**Purpose:** Extract vertices from uploaded polygon and create intermediate points every 20m along the boundary for field verification.

**Business Rules:**
1. Extract all vertices from polygon boundary
2. Calculate distance between consecutive vertices
3. If distance > 20m, create intermediate points at 20m intervals
4. Calculate longitude/latitude for each point
5. Number points sequentially (P1, P2, P3...)
6. Calculate azimuth (bearing) between consecutive points

**Implementation:**
```python
# New table: fieldbook
- id (UUID)
- calculation_id (FK to calculations)
- point_number (INTEGER)
- point_type (ENUM: vertex, interpolated)
- longitude (DECIMAL(10,7))
- latitude (DECIMAL(10,7))
- easting_utm (DECIMAL(12,3))
- northing_utm (DECIMAL(12,3))
- azimuth_to_next (DECIMAL(5,2)) # degrees
- distance_to_next (DECIMAL(8,2)) # meters
- elevation (DECIMAL(8,2)) # from DEM
- remarks (TEXT)
- is_verified (BOOLEAN)
- created_at (TIMESTAMP)
- UNIQUE(calculation_id, point_number)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/generate-fieldbook
  Response: {
    "total_vertices": 45,
    "interpolated_points": 78,
    "total_points": 123,
    "total_perimeter_meters": 2456.7
  }

GET /api/forests/calculations/{id}/fieldbook
  Query params: ?format=geojson|csv|excel
  Response: Fieldbook data in requested format

PATCH /api/forests/calculations/{id}/fieldbook/{point_number}
  Body: { "is_verified": true, "remarks": "GPS verified" }
```

**Excel/CSV Export Format:**
```
Point No. | Type        | Longitude  | Latitude  | Easting   | Northing  | Azimuth | Distance | Elevation | Verified | Remarks
----------|-------------|------------|-----------|-----------|-----------|---------|----------|-----------|----------|--------
P1        | Vertex      | 85.123456  | 27.789012 | 654321.45 | 3078912.34| 45.23   | 20.00    | 1234.5    | Yes      |
P2        | Interpolated| 85.123567  | 27.789123 | 654341.45 | 3078932.34| 45.23   | 20.00    | 1235.2    | No       |
P3        | Interpolated| 85.123678  | 27.789234 | 654361.45 | 3078952.34| 47.89   | 25.34    | 1236.0    | No       |
```

---

### 2. Forest Sampling and Analysis (NEW MODULE)

**Purpose:** Field data collection and statistical analysis for forest inventory.

**Workflow:**
1. Forester visits sampling points (from section 1a)
2. Records field measurements (DBH, height, species, etc.)
3. System analyzes data and generates statistics

**Implementation:**

#### Sample Plots Table
```python
# Table: sample_plots
- id (UUID)
- calculation_id (FK to calculations)
- sampling_design_id (FK to sampling_designs)
- plot_number (INTEGER)
- plot_center_point (GEOMETRY(POINT))
- plot_shape (ENUM: circular, square, rectangular)
- plot_radius_meters (DECIMAL) # for circular
- plot_length_meters (DECIMAL) # for rectangular
- plot_width_meters (DECIMAL)
- plot_area_sqm (DECIMAL)
- surveyor_name (VARCHAR)
- survey_date (DATE)
- gps_accuracy_meters (DECIMAL)
- accessibility (ENUM: easy, moderate, difficult)
- slope_percent (DECIMAL)
- aspect_degrees (DECIMAL)
- notes (TEXT)
- created_at (TIMESTAMP)
```

#### Tree Measurements Table
```python
# Table: plot_trees
- id (UUID)
- sample_plot_id (FK to sample_plots)
- tree_number (INTEGER)
- species_name (VARCHAR)
- dbh_cm (DECIMAL) # Diameter at Breast Height
- height_meters (DECIMAL)
- crown_diameter_meters (DECIMAL)
- tree_condition (ENUM: healthy, diseased, dead, dying)
- damage_type (VARCHAR) # fire, insect, mechanical, etc.
- estimated_age_years (INTEGER)
- notes (TEXT)
- created_at (TIMESTAMP)
```

#### Analysis Functions
```python
# Sample plot analysis functions
def calculate_stand_density(plot_id):
    """Trees per hectare"""

def calculate_basal_area(plot_id):
    """Total basal area m²/ha"""

def calculate_species_composition(calculation_id):
    """Percentage by species"""

def calculate_volume_per_hectare(plot_id):
    """Cubic meters per hectare using volume tables"""

def calculate_growing_stock(calculation_id):
    """Total forest volume"""
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/sample-plots
  Body: Plot metadata

POST /api/forests/sample-plots/{id}/trees
  Body: Tree measurements (single or batch)

GET /api/forests/calculations/{id}/sampling-analysis
  Response: {
    "total_plots": 50,
    "total_trees_measured": 1234,
    "stand_density_per_ha": 567,
    "basal_area_sqm_per_ha": 23.4,
    "species_composition": [...],
    "volume_cubic_m_per_ha": 145.6
  }
```

---

### 3. Tree Inventory and Analysis (EXISTING - Integration)

**Status:** Already developed (mentioned in CSV upload work)

**Integration Requirements:**
- Link inventory data to specific CFOP
- Allow upload per block or entire forest
- Cross-reference with sampling data
- Generate summary statistics

**New Fields to Add:**
```python
# Add to existing inventory table
- calculation_id (FK to calculations) # Link to CFOP
- block_name (VARCHAR) # Which block this inventory belongs to
- inventory_type (ENUM: complete, sample, mother_trees)
```

**API Enhancement:**
```
POST /api/forests/calculations/{id}/inventory/upload
  Body: CSV file with calculation_id linkage

GET /api/forests/calculations/{id}/inventory/summary
  Response: Statistics per block and total
```

---

### 4. Forest User Group Information (NEW MODULE)

**Purpose:** Manage community forest user group demographics and participation.

**Implementation:**

```python
# Table: forest_user_groups
- id (UUID)
- calculation_id (FK to calculations)
- group_name (VARCHAR)
- registration_number (VARCHAR)
- registration_date (DATE)
- total_households (INTEGER)
- total_members (INTEGER)
- male_members (INTEGER)
- female_members (INTEGER)
- dalit_members (INTEGER)
- janajati_members (INTEGER)
- madhesi_members (INTEGER)
- other_caste_members (INTEGER)
- area_hectares (DECIMAL)
- formation_date (DATE)
- renewed_date (DATE)
- expiry_date (DATE)
- address_district (VARCHAR)
- address_vdc_municipality (VARCHAR)
- address_ward (INTEGER)
- contact_person (VARCHAR)
- contact_phone (VARCHAR)
- contact_email (VARCHAR)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/user-group
  Body: User group information (form or CSV upload)

GET /api/forests/calculations/{id}/user-group
  Response: User group details

PUT /api/forests/calculations/{id}/user-group
  Body: Updated information

POST /api/forests/calculations/{id}/user-group/upload-csv
  Body: Bulk upload user group data
```

**CSV Upload Format:**
```csv
Group Name,Registration No,Registration Date,Total HH,Total Members,Male,Female,Dalit,Janajati,Madhesi,Other,Area (ha),Formation Date,Contact Person,Phone
```

---

### 5. Forest User Committee Information (NEW MODULE)

**Purpose:** Track committee members, roles, and terms.

**Implementation:**

```python
# Table: forest_committees
- id (UUID)
- calculation_id (FK to calculations)
- committee_type (ENUM: executive, advisory, audit)
- formation_date (DATE)
- tenure_years (INTEGER)
- expiry_date (DATE)
- total_members (INTEGER)
- created_at (TIMESTAMP)

# Table: committee_members
- id (UUID)
- committee_id (FK to forest_committees)
- full_name (VARCHAR)
- position (VARCHAR) # Chairperson, Vice-chair, Secretary, Treasurer, Member
- gender (ENUM: male, female, other)
- caste_ethnicity (VARCHAR)
- address (VARCHAR)
- phone (VARCHAR)
- email (VARCHAR)
- education_level (VARCHAR)
- joining_date (DATE)
- leaving_date (DATE)
- is_active (BOOLEAN)
- created_at (TIMESTAMP)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/committees
  Body: Committee details

POST /api/forests/committees/{id}/members
  Body: Member information (single or batch)

GET /api/forests/calculations/{id}/committees
  Response: All committees with members

POST /api/forests/calculations/{id}/committees/upload-csv
  Body: Bulk upload committee data
```

**CSV Upload Format:**
```csv
Committee Type,Member Name,Position,Gender,Caste/Ethnicity,Address,Phone,Email,Education,Joining Date
Executive,Ram Bahadur Thapa,Chairperson,Male,Magar,Ward 5,9841234567,,SLC,2024-01-01
Executive,Sita Kumari Sharma,Secretary,Female,Brahmin,Ward 3,9857654321,,Bachelor,2024-01-01
```

---

### 6. Forest Product Price (NEW MODULE)

**Purpose:** Record forest product pricing for operational plan economics.

**Implementation:**

```python
# Table: forest_products
- id (UUID)
- calculation_id (FK to calculations)
- product_name (VARCHAR) # Timber, Fuelwood, Fodder, NTFP, etc.
- product_category (ENUM: timber, fuelwood, fodder, ntfp, other)
- species_name (VARCHAR) # For timber
- unit (VARCHAR) # cubic_foot, bundle, kg, etc.
- unit_price_npr (DECIMAL)
- market_price_npr (DECIMAL)
- community_price_npr (DECIMAL) # Discounted price for FUG members
- price_effective_date (DATE)
- price_source (VARCHAR) # DFO rate, market survey, etc.
- notes (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/products
  Body: Product pricing (form or CSV)

GET /api/forests/calculations/{id}/products
  Query: ?category=timber
  Response: List of products with prices

PUT /api/forests/products/{id}
  Body: Updated pricing

POST /api/forests/calculations/{id}/products/upload-csv
  Body: Bulk upload product prices
```

**CSV Upload Format:**
```csv
Product Name,Category,Species,Unit,Unit Price (NPR),Market Price (NPR),Community Price (NPR),Effective Date,Source
Sal Timber,timber,Sal,cft,150,200,120,2024-01-01,DFO Rate
Fuelwood,fuelwood,,bundle,50,80,40,2024-01-01,Market Survey
Chiraito,ntfp,Swertia chirayita,kg,500,600,450,2024-01-01,Local Rate
```

---

### 7. Extensible Table Upload System (NEW MODULE)

**Purpose:** Allow upload of additional tables for future requirements.

**Implementation:**

```python
# Table: custom_tables
- id (UUID)
- calculation_id (FK to calculations)
- table_name (VARCHAR)
- table_description (TEXT)
- schema_definition (JSONB) # Column definitions
- created_at (TIMESTAMP)

# Table: custom_table_data
- id (UUID)
- custom_table_id (FK to custom_tables)
- row_data (JSONB) # Flexible row storage
- row_number (INTEGER)
- created_at (TIMESTAMP)
```

**API Endpoints:**
```
POST /api/forests/calculations/{id}/custom-tables
  Body: {
    "table_name": "Soil Samples",
    "columns": ["Sample ID", "pH", "Organic Matter %", "Location"]
  }

POST /api/forests/custom-tables/{id}/upload-csv
  Body: CSV file with dynamic columns

GET /api/forests/calculations/{id}/custom-tables
  Response: List of all custom tables

GET /api/forests/custom-tables/{id}/data
  Response: Table data in JSON/CSV
```

---

## User Interface Design

### Core UX Principle: Context-Aware Navigation

**Problem:** Forester works on multiple CFOPs simultaneously over weeks/months.

**Solution:** CFOP-centric workspace with persistent context.

### Proposed UI Architecture

#### 1. Dashboard (Landing Page After Login)

```
+------------------------------------------------------------------+
|  [Logo] Community Forest Operational Plans        [User] [Logout]
+------------------------------------------------------------------+
|                                                                   |
|  MY OPERATIONAL PLANS                           [+ New CFOP]     |
|                                                                   |
|  +------------------+  +------------------+  +------------------+|
|  | Lohandra CF      |  | Chuchekhola CF   |  | Rame CF          ||
|  | Status: DRAFT    |  | Status: DRAFT    |  | Status: COMPLETED||
|  | Progress: 45%    |  | Progress: 78%    |  | Renewed: 2024    ||
|  | Updated: 2 days  |  | Updated: 1 hour  |  | Valid until 2029 ||
|  | [Continue >]     |  | [Continue >]     |  | [View Report]    ||
|  +------------------+  +------------------+  +------------------+|
|                                                                   |
|  RECENT ACTIVITY                                                 |
|  - Uploaded inventory data for Chuchekhola Block A               |
|  - Completed fieldbook generation for Lohandra                   |
|  - Added 5 committee members to Rame FUG                         |
|                                                                   |
+------------------------------------------------------------------+
```

**Features:**
- Card-based CFOP overview
- Visual progress indicators
- Quick action buttons
- Status badges (Draft, In Progress, Under Review, Completed)
- Last updated timestamps
- Search and filter CFOPs

#### 2. CFOP Workspace (After Clicking a CFOP)

```
+------------------------------------------------------------------+
|  < Back to Dashboard    LOHANDRA COMMUNITY FOREST                |
+------------------------------------------------------------------+
| Sidebar Navigation              | Main Content Area              |
|                                  |                                |
| OVERVIEW                         | FOREST BOUNDARY & BLOCKS       |
|   - Plan Summary                 |                                |
|   - Progress Tracker             | [Map View]                     |
|                                  | [Upload New Boundary]          |
| 1. FOREST BOUNDARY & BLOCKS  ✓   |                                |
|   - Upload Boundary              | Blocks Detected: 3             |
|   - Generate Fieldbook           | Total Area: 425.7 ha           |
|   - Create Sampling Points       |                                |
|                                  | Block A: 150.3 ha              |
| 2. FIELD SAMPLING            ⚠️  | Block B: 175.2 ha              |
|   - Sampling Design              | Block C: 100.2 ha              |
|   - Sample Plots                 |                                |
|   - Tree Measurements            | [Generate Fieldbook]           |
|                                  | [Create Sampling Design]       |
| 3. TREE INVENTORY            ✓   |                                |
|   - Upload Inventory             |                                |
|   - Inventory Analysis           |                                |
|   - Mother Trees                 |                                |
|                                  |                                |
| 4. USER GROUP INFO           -   |                                |
|   - FUG Details                  |                                |
|   - Member Demographics          |                                |
|                                  |                                |
| 5. COMMITTEE MANAGEMENT      -   |                                |
|   - Executive Committee          |                                |
|   - Advisory Committee           |                                |
|                                  |                                |
| 6. FOREST PRODUCTS           -   |                                |
|   - Product Pricing              |                                |
|   - Harvest Calculations         |                                |
|                                  |                                |
| 7. ADDITIONAL DATA           -   |                                |
|   - Custom Tables                |                                |
|   - Attachments                  |                                |
|                                  |                                |
| GENERATE REPORT                  |                                |
|   [Preview] [Export PDF]         |                                |
|                                  |                                |
+------------------------------------------------------------------+
| Status: DRAFT  | Last saved: 2 minutes ago | [Save] [Save & Exit]|
+------------------------------------------------------------------+
```

**Key Features:**

1. **Persistent Sidebar Navigation**
   - Always shows CFOP context
   - Progress indicators (✓ complete, ⚠️ incomplete, - not started)
   - Jump to any section instantly
   - Collapsible for more workspace

2. **Section Status Icons**
   - ✓ Green checkmark: Section complete
   - ⚠️ Orange warning: Section started but incomplete
   - - Gray dash: Not started
   - 🔒 Lock: Cannot access until prerequisites met

3. **Auto-save**
   - Draft saved every 2 minutes automatically
   - Manual save button always visible
   - "Last saved" timestamp

4. **Breadcrumb Navigation**
   - Always know: Dashboard > CFOP Name > Section
   - Quick navigation back

5. **Progress Tracker** (in Overview section)
   ```
   Overall Progress: 45%

   [███████████░░░░░░░░░░░░░] 45%

   ✓ Forest Boundary Uploaded
   ✓ Fieldbook Generated (123 points)
   ✓ Tree Inventory Uploaded (2,456 trees)
   ⚠️ Sampling Design Created (0/50 plots measured)
   - User Group Information (Not Started)
   - Committee Information (Not Started)
   - Forest Products (Not Started)
   ```

#### 3. Section-Specific Views

**Example: Fieldbook Section**

```
+------------------------------------------------------------------+
|  Lohandra CF > Forest Boundary & Blocks > Fieldbook              |
+------------------------------------------------------------------+
|                                                                   |
|  BOUNDARY FIELDBOOK                                [Download ▼]  |
|                                                                   |
|  Summary:                                                         |
|  - Total Vertices: 45                                             |
|  - Interpolated Points: 78                                        |
|  - Total Points: 123                                              |
|  - Perimeter: 2,456.7 meters                                      |
|  - Average Elevation: 1,234 m                                     |
|                                                                   |
|  [🗺️ Map View] [📋 Table View] [📊 Statistics]                    |
|                                                                   |
|  +-----------------------------------------------------------+   |
|  | Point | Type   | Lat       | Lon       | Azimuth | Dist  |   |
|  |-------|--------|-----------|-----------|---------|-------|   |
|  | P1    | Vertex | 27.789012 | 85.123456 | 45.23°  | 20.0m |   |
|  | P2    | Inter  | 27.789123 | 85.123567 | 45.23°  | 20.0m |   |
|  | P3    | Inter  | 27.789234 | 85.123678 | 47.89°  | 25.3m |   |
|  | ...   | ...    | ...       | ...       | ...     | ...   |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  [✏️ Edit Points] [🗑️ Regenerate] [✓ Mark as Verified]           |
|                                                                   |
+------------------------------------------------------------------+
```

**Example: Sampling Design Section**

```
+------------------------------------------------------------------+
|  Lohandra CF > Field Sampling > Sampling Design                  |
+------------------------------------------------------------------+
|                                                                   |
|  CREATE SAMPLING DESIGN                                           |
|                                                                   |
|  Sampling Type:                                                   |
|  ( ) Systematic Grid    (•) Random    ( ) Stratified Random      |
|                                                                   |
|  Sampling Intensity:                                              |
|  [0.5] points per hectare                                         |
|  Estimated total points: 213 points for 425.7 ha                  |
|                                                                   |
|  Plot Configuration:                                              |
|  Plot Shape: (•) Circular  ( ) Square  ( ) Rectangular            |
|  Plot Radius: [8] meters (approx 201 m² per plot)                 |
|                                                                   |
|  [Preview on Map] [Generate Points]                               |
|                                                                   |
|  +----------------------------------------------------------+    |
|  |                    [Interactive Map]                     |    |
|  |                                                          |    |
|  |  Forest boundary shown                                   |    |
|  |  Sampling points overlaid                                |    |
|  |  Click to manually add/remove points                     |    |
|  |                                                          |    |
|  +----------------------------------------------------------+    |
|                                                                   |
|  [Save Design] [Export Coordinates for GPS]                       |
|                                                                   |
+------------------------------------------------------------------+
```

#### 4. Mobile-Responsive Field Data Collection

**For Field Use (Tablet/Phone):**

```
+--------------------------------+
| Lohandra CF - Plot #23         |
| Lat: 27.789 Lon: 85.123        |
+--------------------------------+
|                                |
| PLOT INFORMATION               |
|                                |
| Survey Date: [Today ▼]         |
| Surveyor: [Ram Thapa ▼]        |
|                                |
| Plot Shape: Circular           |
| Radius: 8m                     |
| Slope: [15] %                  |
| Aspect: [NE ▼]                 |
|                                |
| TREE MEASUREMENTS              |
|                                |
| Tree #1                        |
| Species: [Sal ▼]               |
| DBH: [35.5] cm                 |
| Height: [18.2] m               |
| Condition: [Healthy ▼]         |
| [+ Add Photo]                  |
|                                |
| [Save Tree] [+ Add Another]    |
|                                |
| Trees recorded: 12             |
|                                |
| [Complete Plot]                |
| [Skip to Next Plot >]          |
|                                |
+--------------------------------+
```

**Features:**
- Offline capability (sync when online)
- GPS integration
- Camera integration for photos
- Dropdown lists for standardized data entry
- Quick navigation between plots

---

## Database Schema Summary

### New Tables Required

1. **sampling_designs** - Sampling methodology per CFOP
2. **sample_plots** - Individual plot locations and metadata
3. **plot_trees** - Tree measurements per plot
4. **fieldbook** - Boundary vertices and interpolated points
5. **forest_user_groups** - FUG demographics
6. **forest_committees** - Committee structure
7. **committee_members** - Individual committee members
8. **forest_products** - Product pricing
9. **custom_tables** - Extensible table metadata
10. **custom_table_data** - Extensible table rows

### Enhanced Tables

1. **calculations** - Add `cfop_status` and `progress_percentage`
   ```python
   - cfop_status (ENUM: draft, in_progress, under_review, completed, archived)
   - progress_percentage (INTEGER)
   - last_saved_at (TIMESTAMP)
   - plan_type (ENUM: new, renewal)
   - renewal_year (INTEGER)
   - valid_until (DATE)
   ```

### Relationships

```
calculations (CFOP)
  ├── sampling_designs
  │     └── sample_plots
  │           └── plot_trees
  ├── fieldbook
  ├── forest_user_groups
  ├── forest_committees
  │     └── committee_members
  ├── forest_products
  └── custom_tables
        └── custom_table_data
```

---

## API Design Principles

### RESTful Structure

**CFOP-Centric Routes:**
```
/api/cfop/{cfop_id}/boundary
/api/cfop/{cfop_id}/fieldbook
/api/cfop/{cfop_id}/sampling
/api/cfop/{cfop_id}/sampling/plots
/api/cfop/{cfop_id}/inventory
/api/cfop/{cfop_id}/user-group
/api/cfop/{cfop_id}/committees
/api/cfop/{cfop_id}/products
/api/cfop/{cfop_id}/custom-tables
```

**Draft Management:**
```
POST   /api/cfop                    # Create new CFOP
GET    /api/cfop                    # List user's CFOPs
GET    /api/cfop/{id}               # Get CFOP details
PUT    /api/cfop/{id}               # Update CFOP metadata
PATCH  /api/cfop/{id}/status        # Change status (draft->completed)
DELETE /api/cfop/{id}               # Delete draft
POST   /api/cfop/{id}/duplicate     # Clone existing CFOP
```

**Auto-save Endpoint:**
```
PATCH /api/cfop/{id}/auto-save
Body: {
  "section": "fieldbook",
  "data": {...},
  "timestamp": "2026-01-28T12:34:56Z"
}
Response: {
  "saved": true,
  "version": 45,
  "last_saved_at": "2026-01-28T12:34:56Z"
}
```

---

## Implementation Phases

### Phase 2A: Fieldbook & Sampling (Immediate Priority)

**Tasks:**
1. Create `fieldbook` table and API
2. Implement vertex extraction algorithm
3. Implement 20m interpolation logic
4. Create `sampling_designs` table and API
5. Implement systematic sampling algorithm
6. Implement random sampling algorithm
7. Frontend: Fieldbook viewer/editor
8. Frontend: Sampling design wizard
9. Frontend: Interactive map for point placement
10. Export to GPS format (GPX, CSV)

**Duration:** 2-3 weeks

### Phase 2B: Field Data Collection

**Tasks:**
1. Create `sample_plots` and `plot_trees` tables
2. Implement plot data API
3. Implement tree measurement API
4. Frontend: Plot data entry form
5. Frontend: Tree measurement form
6. Mobile-optimized interface
7. Offline data collection support
8. Statistical analysis functions
9. Reports and visualizations

**Duration:** 3-4 weeks

### Phase 2C: User Group & Committee Management

**Tasks:**
1. Create FUG and committee tables
2. Implement CRUD APIs
3. CSV upload functionality
4. Frontend: FUG information form
5. Frontend: Committee management interface
6. Member search and filtering
7. Demographic reports

**Duration:** 2 weeks

### Phase 2D: Product Pricing & Economics

**Tasks:**
1. Create `forest_products` table
2. Implement pricing API
3. CSV upload functionality
4. Frontend: Product pricing interface
5. Economic analysis calculations
6. Harvest planning integration

**Duration:** 1-2 weeks

### Phase 2E: Extensible Tables & Reporting

**Tasks:**
1. Create custom tables system
2. Dynamic CSV upload
3. Frontend: Table viewer/editor
4. Final report generation
5. PDF export with all sections
6. Government-compliant template

**Duration:** 2-3 weeks

### Phase 2F: Draft Management & UX Polish

**Tasks:**
1. CFOP dashboard implementation
2. Progress tracking system
3. Auto-save functionality
4. Section navigation
5. Mobile responsiveness
6. User testing and refinement

**Duration:** 2 weeks

**Total Estimated Duration:** 12-16 weeks for complete Phase 2

---

## Technical Recommendations

### 1. Frontend Framework

**Recommended:** React with TypeScript
- Component-based architecture
- Strong typing for data integrity
- Large ecosystem (maps, forms, charts)
- Mobile-responsive capabilities

**Alternative:** Vue.js
- Simpler learning curve
- Good documentation
- Progressive enhancement

### 2. Map Library

**Recommended:** MapLibre GL JS
- Open-source, no API keys
- Excellent performance
- Vector tile support
- Interactive editing capabilities

**Alternative:** Leaflet
- Simpler API
- Wide plugin ecosystem
- Good for basic mapping needs

### 3. State Management

**Recommended:** React Context + React Query
- Context for CFOP-level state
- React Query for server state
- Automatic caching and synchronization
- Built-in offline support

### 4. Form Handling

**Recommended:** React Hook Form + Zod
- Performance-optimized
- Type-safe validation
- Easy integration with backend schemas

### 5. Offline Support

**Recommended:** Service Workers + IndexedDB
- Cache API calls
- Queue mutations for sync
- Progressive Web App (PWA) capabilities
- Works on mobile devices

### 6. Mobile Field Collection

**Option 1:** PWA (Progressive Web App)
- Single codebase
- Works offline
- Install on device
- Camera and GPS access

**Option 2:** React Native
- Full native capabilities
- Better performance
- Separate app store distribution
- More development overhead

**Recommendation:** Start with PWA, migrate to React Native if needed

---

## Security & Data Integrity

### 1. Draft Versioning

**Requirement:** Track changes to prevent data loss

**Implementation:**
```python
# Table: cfop_versions
- id (UUID)
- calculation_id (FK to calculations)
- version_number (INTEGER)
- section_name (VARCHAR)
- data_snapshot (JSONB)
- changed_by (UUID FK to users)
- changed_at (TIMESTAMP)
- change_description (TEXT)
```

**API:**
```
GET /api/cfop/{id}/versions
GET /api/cfop/{id}/versions/{version_number}/restore
```

### 2. Concurrent Editing Protection

**Problem:** Two foresters editing same CFOP simultaneously

**Solution:** Optimistic locking
```python
# Add to calculations table
- version (INTEGER)
- locked_by (UUID FK to users)
- locked_at (TIMESTAMP)
```

**API Response:**
```json
{
  "error": "CFOP is currently locked",
  "locked_by": "Ram Thapa",
  "locked_since": "2026-01-28T10:30:00Z",
  "lock_expires": "2026-01-28T11:00:00Z"
}
```

### 3. Data Validation Rules

**Field-level validation:**
- DBH: 1-300 cm (reject outliers)
- Height: 0.5-80 meters
- Slope: 0-100%
- Coordinates: Within Nepal bounds

**Cross-field validation:**
- Plot area calculation matches shape/radius
- Sampling points within boundary
- Tree count matches plot size expectations

**Business rules:**
- Cannot mark CFOP complete if required sections empty
- Cannot delete CFOP if status = completed
- Renewal CFOP must reference previous plan

---

## User Experience Enhancements

### 1. Smart Defaults

- Pre-fill surveyor name from login
- Default to today's date
- Remember last used plot configuration
- Copy settings from previous plots

### 2. Bulk Operations

- Upload multiple plot measurements (CSV/Excel)
- Batch edit species names
- Apply pricing to multiple products at once
- Export multiple sections simultaneously

### 3. Validation Feedback

```
+------------------------------------------+
| ⚠️ VALIDATION WARNINGS                   |
+------------------------------------------+
| • 3 trees have DBH > 100cm (unusual)     |
| • Plot #12 has 0 trees recorded          |
| • Sampling intensity (0.2/ha) is low     |
|   Recommended: 0.5-1.0 for this terrain  |
|                                          |
| [Review Issues] [Ignore] [Fix Now]       |
+------------------------------------------+
```

### 4. Context-Sensitive Help

- Inline tooltips explaining fields
- Video tutorials for each section
- Sample data templates
- Government regulation references

### 5. Collaboration Features

**Future Enhancement:**
- Assign sections to team members
- Comment/annotation system
- Review/approval workflow
- Notification system

---

## Performance Optimization

### 1. Large Dataset Handling

**Problem:** 40,000+ tree inventory records

**Solutions:**
- Pagination (50-100 records per page)
- Virtual scrolling for long lists
- Server-side filtering and sorting
- Aggregate summaries instead of full datasets
- Background processing for statistics

### 2. Map Performance

**Problem:** Complex polygons with thousands of vertices

**Solutions:**
- Geometry simplification for display (Douglas-Peucker)
- Vector tiles for large datasets
- Clustering for sampling points
- Progressive loading (viewport-based)
- WebGL rendering (MapLibre)

### 3. Offline Synchronization

**Strategy:**
```
1. User works offline on mobile device
2. Changes queued in IndexedDB
3. When online, sync queue processed
4. Conflict resolution (last-write-wins or manual)
5. User notified of sync status
```

---

## Reporting & Export

### 1. Final CFOP Report Structure

**Government-Compliant Format:**

```
COMMUNITY FOREST OPERATIONAL PLAN
[Forest Name]
[Valid Period: 2026-2036]

SECTION 1: INTRODUCTION
  1.1 Forest Location and Boundaries
  1.2 User Group Information
  1.3 Management Objectives

SECTION 2: FOREST RESOURCE ASSESSMENT
  2.1 Forest Boundary (Fieldbook Table)
  2.2 Block-wise GIS Analysis (16 parameters)
  2.3 Sampling Design and Plot Layout
  2.4 Forest Inventory Results
  2.5 Growing Stock Estimation

SECTION 3: FOREST MANAGEMENT PLAN
  3.1 Silvicultural System
  3.2 Harvest Planning
  3.3 Regeneration Activities
  3.4 Protection Measures

SECTION 4: BENEFIT SHARING
  4.1 User Group Demographics
  4.2 Committee Structure
  4.3 Forest Product Pricing
  4.4 Income Distribution Plan

SECTION 5: MAPS
  5.1 Location Map
  5.2 Forest Type Map
  5.3 Slope Map
  5.4 Sampling Plot Map
  5.5 Harvest Block Map
  (Additional thematic maps)

APPENDICES
  A. Fieldbook (Complete)
  B. Sampling Point Coordinates
  C. Tree Inventory (Full dataset)
  D. Species List
  E. Committee Member Details
  F. FUG Member List
  G. Price List
```

### 2. Export Formats

- **PDF:** Final report (government submission)
- **Word/ODT:** Editable template for customization
- **Excel:** All tables for further analysis
- **GeoPackage:** All spatial data
- **Shapefile:** For legacy GIS software
- **KML:** For Google Earth viewing
- **CSV:** Individual tables for flexibility

### 3. Map Output

- **A5 PNG:** As per original requirement
- **A4 PDF:** For printing
- **Interactive HTML:** For web viewing
- **Tiles:** For mobile offline use

---

## Deployment Considerations

### 1. Server Requirements

**Minimum:**
- 4 CPU cores
- 16 GB RAM
- 500 GB SSD
- PostgreSQL 15+ with PostGIS 3.6

**Recommended:**
- 8 CPU cores
- 32 GB RAM
- 1 TB SSD
- Database replication

### 2. Scalability Targets

- 500 concurrent users
- 10,000 CFOPs per year
- 5 million tree records
- 50 GB raster datasets

### 3. Backup Strategy

- Daily database backups
- Weekly full system snapshots
- User draft auto-save every 2 minutes
- Cloud backup for disaster recovery

### 4. Hosting Options

**Option 1: On-Premises**
- Government data center
- Full control
- Higher maintenance
- Initial hardware costs

**Option 2: Cloud (AWS/Azure/GCP)**
- Scalable infrastructure
- Managed services (RDS, storage)
- Pay-as-you-grow
- Automatic backups

**Recommendation:** Hybrid approach
- Database and sensitive data on-premises
- Frontend and static assets on CDN
- Raster tiles on cloud storage

---

## Success Metrics

### User Adoption
- 80% of foresters complete at least one CFOP
- Average 5-8 CFOPs per forester per year
- 70% of CFOPs completed within draft system

### Efficiency Gains
- 50% reduction in plan preparation time
- 30% fewer data entry errors
- 90% reduction in manual calculations

### Data Quality
- 95% field completion rate for required sections
- <5% validation warnings per CFOP
- <1% data loss incidents

### System Performance
- <2 second page load time
- 99.5% uptime
- <1 hour for large dataset processing

---

## Next Steps

### Immediate Actions

1. **Review and Approval**
   - Stakeholder review of this design document
   - User feedback from sample foresters
   - Government regulation compliance check

2. **Technical Setup**
   - Finalize frontend framework choice
   - Set up development environment
   - Create database migration plan

3. **Phase 2A Kickoff**
   - Assign development tasks
   - Create detailed technical specifications
   - Begin fieldbook implementation

4. **User Testing Plan**
   - Recruit 5-10 forester beta testers
   - Prepare test datasets
   - Schedule feedback sessions

### Long-term Roadmap

**Q2 2026:** Complete Phase 2A-2B (Fieldbook, Sampling, Field Data)
**Q3 2026:** Complete Phase 2C-2D (User Groups, Committees, Products)
**Q4 2026:** Complete Phase 2E-2F (Reporting, UX Polish)
**Q1 2027:** Pilot deployment with 50 foresters
**Q2 2027:** Full production rollout

---

## Conclusion

This design provides a comprehensive, user-centered approach to Community Forest Operational Plan preparation. Key strengths:

1. **Context-Aware Navigation:** CFOP-centric interface keeps users oriented
2. **Draft Management:** Multi-session work support with auto-save
3. **Modular Design:** Each component can be developed and tested independently
4. **Extensibility:** Custom table system allows future requirements
5. **Mobile Support:** Field data collection on phones/tablets
6. **Government Compliance:** Structured to match official CFOP format

The proposed system will significantly reduce the time and effort required to prepare operational plans while improving data quality and consistency across Nepal's community forests.

---

**Document Version:** 1.0
**Date:** February 3, 2026
**Author:** Forest Management System Design Team
**Status:** Awaiting Review
