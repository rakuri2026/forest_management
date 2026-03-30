# Community Forest Management System

## Quick Reference

**Project:** Community Forest Management System
**Location:** `D:\forest_management`
**Database:** PostgreSQL `cf_db` (postgres/admin123@localhost:5432)
**Backend:** FastAPI + SQLAlchemy + PostGIS
**Frontend:** React + TypeScript + Leaflet

**Servers:**
- Backend API: http://localhost:8001
- Frontend: http://localhost:3001
- API Docs: http://localhost:8001/docs

**Login Credentials:**
- Email: demo@forest.com
- Password: Demo1234

---

## Starting the System

### Using Batch Files (Recommended)
```batch
# Start both servers
start_all.bat

# Stop both servers
stop_all.bat

# Restart both servers
restart_all.bat
```

### Manual Start
```bash
# Backend
cd D:\forest_management\backend
..\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001

# Frontend
cd D:\forest_management\frontend
npm run dev
```

---

## Current System Status

### ✅ Core Features Working
1. **Authentication** - JWT-based login/register
2. **File Upload** - KML, GeoJSON, Shapefile support
3. **Raster Analysis** - All 16 parameters (DEM, slope, aspect, canopy, biomass, etc.)
4. **Block-wise Analysis** - Multi-block boundary processing
5. **Species Analysis** - 137 species with ecological data
6. **Species Management** - Confirm/remove species, add manually
7. **Sampling Design** - Systematic/random/stratified sampling
8. **Tree Inventory** - Column mapping, validation, import
9. **Tree Distribution Model** - Synthetic GPKG generation
10. **Interactive UI** - Analysis dashboard, maps, charts

### 📋 Key Database Tables
- `public.users` - User accounts (JWT auth)
- `public.calculations` - Uploaded boundaries + analysis results (JSONB)
- `public.sampling_designs` - Sample plot designs
- `public.inventory` - Tree measurement data
- `public.synthetic_tree_models` - Generated tree models
- `admin.community_forests` - 3,922 existing forests
- `rasters.*` - 16 raster datasets (DEM, slope, canopy, etc.)
- `public.tree_species_coefficients` - 137 species with ecological data
- `public.forest_types` - 25 forest types (Forest Regulation 2079)

---

## Project Structure

```
D:\forest_management\
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── forests.py
│   │   │   ├── sampling.py
│   │   │   ├── inventory.py
│   │   │   └── tree_models.py
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── analysis.py   # Raster analysis (16 parameters)
│   │   │   ├── sampling.py   # Sampling design generation
│   │   │   ├── inventory.py  # Tree inventory processing
│   │   │   └── tree_distribution.py  # Tree model generation
│   │   └── main.py
│   └── alembic/              # Database migrations
├── frontend/
│   ├── src/
│   │   ├── pages/            # Main pages
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   └── CalculationDetail.tsx
│   │   ├── components/       # React components
│   │   │   ├── AnalysisTabContent.tsx
│   │   │   ├── SamplingTab.tsx
│   │   │   ├── TreeInventoryTab.tsx
│   │   │   ├── SpeciesTable.tsx
│   │   │   └── TreeModelGenerator.tsx
│   │   └── services/
│   │       └── api.ts        # API client
│   └── vite.config.ts
├── uploads/                  # Uploaded boundary files
├── exports/                  # Generated GPKG files
├── start_all.bat
├── stop_all.bat
└── restart_all.bat
```

---

## Key API Endpoints

### Authentication
```
POST /api/auth/login - Login with email/password
POST /api/auth/register - Create new account
GET /api/auth/me - Get current user
```

### Forest Management
```
POST /api/forests/upload - Upload boundary file (KML/GeoJSON/Shapefile)
GET /api/forests/calculations - List user's calculations
GET /api/forests/calculations/{id} - Get analysis results
DELETE /api/forests/calculations/{id} - Delete calculation
```

### Block Management (NEW - v1.6.0)
```
POST /api/forests/calculations/{id}/create-single-block - Create default single block
  Query Params: block_name (optional)

POST /api/forests/calculations/{id}/blocks - Create multiple blocks
  Body: { blocks: [{ polygon_index: 0, name: "Block 1" }] }

GET /api/forests/calculations/{id}/polygons - Get polygons for multi-block naming
```

### Sampling
```
POST /api/calculations/{id}/sampling/generate - Generate sampling design
GET /api/calculations/{id}/sampling - Get sampling designs
GET /api/sampling-designs/{id}/export - Export as GPKG/CSV
```

### Tree Inventory
```
POST /api/calculations/{id}/inventory/upload - Upload inventory CSV
GET /api/calculations/{id}/inventory - Get inventory data
POST /api/calculations/{id}/inventory/column-mapping - Map CSV columns
```

### Species Management
```
PATCH /api/forests/calculations/{id}/species/{name}/confirm - Confirm species
POST /api/forests/calculations/{id}/add-species - Add species manually
DELETE /api/forests/calculations/{id}/remove-species/{name} - Remove species
```

### Tree Model
```
POST /api/calculations/{id}/generate-tree-model - Generate synthetic tree points
GET /api/tree-models/{id} - Get model status/progress
GET /api/tree-models/{id}/download - Download GPKG
```

---

## Important Files & Locations

### Backend Services
- **Analysis:** `backend/app/services/analysis.py` - All 16 raster analysis functions
- **Sampling:** `backend/app/services/sampling.py` - Sampling design generation
- **Inventory:** `backend/app/services/inventory.py` - Tree data validation & import
- **Tree Distribution:** `backend/app/services/tree_distribution.py` - Synthetic tree generation

### Frontend Components
- **Analysis Tab:** `frontend/src/components/AnalysisTabContent.tsx`
- **Sampling Tab:** `frontend/src/components/SamplingTab.tsx`
- **Inventory Tab:** `frontend/src/components/TreeInventoryTab.tsx`
- **Species Table:** `frontend/src/components/SpeciesTable.tsx`
- **Tree Model:** `frontend/src/components/TreeModelGenerator.tsx`
- **Block Naming:** `frontend/src/pages/BlockNaming.tsx` (NEW - v1.6.0, redesigned with live labels)
- **Tooltip:** `frontend/src/components/Tooltip.tsx` (NEW - v1.6.0, compact help text)
- **Compact Styles:** `frontend/src/styles/compact.css` (NEW - v1.6.0, reusable layout)

### Configuration
- **Backend Config:** `backend/app/core/config.py`
- **Database:** `backend/app/core/database.py`
- **Frontend API:** `frontend/src/services/api.ts`
- **Environment:** `.env` (DATABASE_URL, SECRET_KEY)

---

## Database Alignment

### Forest Regulation 2079 Compliance
- ✅ 25 forest types with class numbers (1-25)
- ✅ 137 tree species with ecological data
- ✅ Species characteristics: altitude, growth rate, economic value, N-fixing, family
- ✅ No generic placeholder species

### Key Species Columns
```sql
-- tree_species_coefficients table
scientific_name, local_name, nepali_name
min_altitude_m, max_altitude_m
growth_rate (Fast/Moderate/Slow)
economic_value (Very High/High/Moderate/Low)
nitrogen_fixing (boolean)
main_uses, ecological_role, rarity_status, family
```

---

## Common Tasks

### Adding a New Feature
1. Backend: Add endpoint in `backend/app/api/`
2. Backend: Add business logic in `backend/app/services/`
3. Frontend: Add API call in `frontend/src/services/api.ts`
4. Frontend: Create/update component in `frontend/src/components/`
5. Test with demo@forest.com account

### Database Migration
```bash
cd backend
..\venv\Scripts\alembic revision --autogenerate -m "Description"
..\venv\Scripts\alembic upgrade head
```

### Debugging
- Backend logs: Check Uvicorn console output
- Frontend logs: Browser DevTools Console
- Database: `psql -U postgres -d cf_db`
- API testing: http://localhost:8001/docs (Swagger UI)

---

## Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
netstat -ano | findstr :8001
netstat -ano | findstr :3001

# Kill processes
taskkill /F /IM python.exe
taskkill /F /IM node.exe
```

### Database Connection Failed
```bash
# Check PostgreSQL is running
sc query postgresql-x64-15

# Test connection
psql -U postgres -d cf_db
```

### Frontend Build Errors
```bash
cd frontend
rm -rf node_modules .vite
npm install
npm run dev
```

---

## Recent Implementation: Single Block Default System

**Status:** ✅ COMPLETE - Awaiting Testing (2026-03-29)
**Documentation:** `SINGLE_BLOCK_DEFAULT_IMPLEMENTATION.md` (See this file for complete details)
**Implementation Date:** March 29, 2026

### Overview
Implemented Nepal's community forest management practice where forests default to a single block equal to the outer boundary. Users now explicitly choose between single or multiple blocks with an intuitive, compact UI.

### What's Been Implemented

#### Backend Changes:
- ✅ New endpoint: `POST /api/forests/calculations/{id}/create-single-block`
- ✅ Removed `run_analysis` parameter from 3 endpoints (upload, create-from-map, blocks)
- ✅ Analysis fallback for empty blocks array
- ✅ Database migration 014 for existing calculations without blocks

#### Frontend Changes:
- ✅ Complete redesign of Block Naming page with:
  - Single/Multiple block toggle with explicit choice
  - Left sidebar table for multiple blocks (color, name, area)
  - Live map labels at polygon centroids
  - Real-time label updates as user types
  - Inline editing with double-click or edit button
  - Auto-fit map bounds to show all polygons
  - Compact UI (70-80% map, 20-30% controls)
- ✅ New Tooltip component for compact help text
- ✅ New compact.css for reusable compact layout utilities
- ✅ Updated MapCreationWizard (removed "Finish & Analyze")
- ✅ Added "Edit Blocks" button to CalculationDetail page

### User Workflow (NEW)
```
Upload/Digitize → Block Naming (⚪ Single ⚪ Multiple) → Save → Analysis Tab → Run Analysis
                                                        ↓
                                Can Edit Blocks Later ←┘
```

### Manual Steps Required (USER ACTION)

**🔴 BEFORE TESTING - Must complete these steps:**

1. **Run Database Migration:**
   ```bash
   cd D:\forest_management\backend
   ..\venv\Scripts\alembic upgrade head
   ```

2. **Restart Servers:**
   ```bash
   cd D:\forest_management
   restart_all.bat
   ```

3. **Test All Workflows:**
   - See `SINGLE_BLOCK_DEFAULT_IMPLEMENTATION.md` for detailed testing checklist

### Key Features
- ✅ Explicit single/multiple block choice (no more "No blocks defined yet" error)
- ✅ Default single block: "{forest_name} - Block 1"
- ✅ Multiple blocks: Table sidebar with live labels on map
- ✅ Analysis ONLY triggered from Analysis tab (never auto-triggered)
- ✅ Sub-areas work with both single and multiple blocks
- ✅ Compact UI design minimizes screen space usage
- ✅ Edit blocks after creation with "Edit Blocks" button

### Files Modified
**Backend (5 files):**
- `backend/app/api/forests.py` (new endpoint + removed run_analysis)
- `backend/app/services/analysis.py` (fallback for empty blocks)
- `backend/app/schemas/forest.py` (removed run_analysis)
- `backend/app/schemas/map_creation.py` (removed run_analysis)
- `backend/alembic/versions/014_*.py` (NEW - migration)

**Frontend (6 files):**
- `frontend/src/pages/BlockNaming.tsx` (COMPLETE REDESIGN - 459 lines)
- `frontend/src/components/Tooltip.tsx` (NEW)
- `frontend/src/styles/compact.css` (NEW)
- `frontend/src/services/api.ts` (new method + removed parameter)
- `frontend/src/components/MapCreation/MapCreationWizard.tsx` (removed analysis trigger)
- `frontend/src/pages/CalculationDetail.tsx` (added Edit Blocks button)

---

## Recent Implementation: Multi-Island Support (Non-Contiguous Forests)

**Status:** ✅ COMPLETE - Ready for Testing (2026-03-29)
**Documentation:** `ISLAND_FEATURE_DOCUMENTATION.md` (See this file for complete guide)
**Implementation Date:** March 29, 2026

### Overview
Full support for community forests with multiple separate, non-contiguous areas ("islands"). Applies to BOTH file upload and on-screen digitization workflows.

### What Are Islands?
Multiple separate polygons that together form one community forest. Examples:
- Forest divided by roads or rivers
- Community managing patches in different locations
- Natural boundaries creating separate areas

### Feature Capabilities

#### File Upload:
- ✅ Upload MultiPolygon GeoJSON/Shapefile with multiple separate polygons
- ✅ Each polygon extracted and shown in Block Naming table
- ✅ Choose: Single block (all islands together) or Multiple blocks (one per island)
- ✅ Already working (tested with existing system)

#### On-Screen Digitization (NEW):
- ✅ Draw multiple separate polygons in manual digitizing mode
- ✅ "+ Add Island" button to create new polygon
- ✅ Color-coded islands (7 colors: green, blue, orange, red, purple, pink, cyan)
- ✅ Island list showing area and status for each
- ✅ Remove islands with trash button
- ✅ Auto-fit map to show all islands
- ✅ Combines into MultiPolygon geometry for backend

### User Workflow (On-Screen Digitization)

```
Step 1: Create New Map
   ↓
Step 2: Outer Boundary → Select "Manual Digitizing"
   ↓
   Click "+ Add First Island"
   Draw first polygon on map
   ↓
   Click "+ Add Island"
   Draw second polygon in different location
   ↓
   Click "+ Add Island"
   Draw third polygon, etc.
   ↓
   Summary shows: "3 Islands Created, Type: MultiPolygon"
   ↓
Step 3: Block Naming → Choose Single or Multiple blocks
   ↓
Step 4: Save → Analysis Tab → Run Analysis
```

### Implementation Details

**Frontend Changes:**
- ✅ `PolygonCreator.tsx` - Completely rewritten (695 lines)
  - New `Island` interface for tracking multiple polygons
  - New `MultiIslandDrawingControls` component
  - Island management UI (add, remove, list)
  - Color-coded visualization
  - Combines islands into Polygon or MultiPolygon output

**Backend Support:**
- ✅ Already handles MultiPolygon in `map_creation_service.py`
- ✅ `shape(outer_boundary)` supports both Polygon and MultiPolygon
- ✅ `validate_map_creation_data()` validates MultiPolygon correctly
- ✅ PostGIS operations (ST_Area, ST_Dump, ST_Intersection) work with MultiPolygon

**Key Features:**
- Each island has unique ID and color
- Islands tracked in array with geometry and area
- Active island indicator during drawing
- Remove button per island
- Total area calculation across all islands
- Auto-detect single vs multiple (output type)

### File Format Support

| Format | MultiPolygon | Notes |
|--------|--------------|-------|
| GeoJSON | ✅ Full | Native MultiPolygon type |
| Shapefile | ✅ Full | MULTIPOLYGON geometry |
| KML | ⚠️ Limited | Use multiple Placemarks |

### Testing Checklist

See `ISLAND_FEATURE_DOCUMENTATION.md` for 7 detailed test cases:
1. File upload with 3 islands
2. On-screen digitization with 2 islands
3. Single block for multiple islands
4. Edit blocks with islands
5. Sub-areas with islands
6. Island removal during digitization
7. Performance test with 10+ islands

### Files Modified

**Frontend (1 file):**
- `frontend/src/components/MapCreation/PolygonCreator.tsx` (COMPLETE REWRITE - 695 lines)

**Backend:**
- No changes needed (already supported MultiPolygon)

### Manual Steps Required (USER ACTION)

**🟢 No migration or restart required** - Frontend-only enhancement

**Testing Steps:**
1. Restart frontend if running: `npm run dev` (optional, hot reload should work)
2. Follow testing guide in `ISLAND_FEATURE_DOCUMENTATION.md`
3. Test both file upload and on-screen digitization workflows

---

## System Version

**Version:** 1.6.0 (Pending Testing)
**Last Updated:** March 29, 2026
**Status:** Implementation Complete - Awaiting User Testing

**Current Features:**
- ✅ File upload & analysis (16 raster parameters)
- ✅ Block-wise processing with single block default
- ✅ Multi-island support for non-contiguous forests
- ✅ Species management (137 species)
- ✅ Sampling design (3 types)
- ✅ Tree inventory import
- ✅ Synthetic tree model generation
- ✅ Interactive UI with tabs, maps, charts
- ✅ Compact UI for block configuration
- ✅ Live map labels for multiple blocks
- ✅ Iterative block editing

**Version 1.6.0 New Features:**
- ✅ Single block default system (following Nepal forest management practice)
- ✅ Multi-island support for on-screen digitization (draw multiple separate polygons)
- ✅ MultiPolygon geometry handling (file upload + map creation)
- ✅ Compact UI design (70-80% map, 20-30% controls)
- ✅ Live label updates on map during block naming
- ✅ Table sidebar for easy block management
- ✅ Color-coded island visualization (7 colors)
- ✅ Island add/remove functionality
- ✅ Analysis separation (only from Analysis tab)
- ✅ Edit blocks after creation

---

## ⚠️ Block Editing Implementation (In Progress)

**Backup Created:** March 30, 2026
**Branch:** `backup-before-block-editing`

### Before Implementing Block Editing
If the implementation fails or needs to be reverted, restore from backup:

```bash
# Restore from backup branch
git checkout backup-before-block-editing

# Or reset current branch to backup
git reset --hard backup-before-block-editing
```

### Backup Locations
- **GitHub (forest_management):** https://github.com/rakuri2026/forest_management/tree/backup-before-block-editing
- **GitHub (dream):** https://github.com/rakuri2026/dream/tree/backup-before-block-editing

### What Was Saved
- All frontend code including MapEditor, BlockNaming, SubAreaManager
- All backend API code for forests, blocks, sub-areas
- All database schemas and models

### Implementation Plan
See: `BLOCK_EDITING_IMPLEMENTATION_PLAN.md`

---

**For detailed technical documentation, see separate .md files in project root.**
