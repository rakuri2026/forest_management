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

## System Version

**Version:** 1.5.0
**Last Updated:** February 21, 2026
**Status:** Production Ready

**Current Features:**
- ✅ File upload & analysis (16 raster parameters)
- ✅ Block-wise processing
- ✅ Species management (137 species)
- ✅ Sampling design (3 types)
- ✅ Tree inventory import
- ✅ Synthetic tree model generation
- ✅ Interactive UI with tabs, maps, charts

---

**For detailed technical documentation, see separate .md files in project root.**
