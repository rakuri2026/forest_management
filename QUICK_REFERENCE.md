# Quick Reference Guide

## 🚀 Common Commands

### Start the Server
```bash
cd D:\forest_management
start.bat
```

### Manual Start (Alternative)
```bash
cd D:\forest_management\backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Database Migration
```bash
cd D:\forest_management\backend
alembic upgrade head
```

### Check Migration Status
```bash
cd D:\forest_management\backend
alembic current
alembic history
```

---

## 🌐 Important URLs

| Resource | URL |
|----------|-----|
| API Root | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| OpenAPI Schema | http://localhost:8000/openapi.json |

---

## 🔑 API Authentication

### 1. Register User
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123",
    "full_name": "John Doe"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 3. Use Token
Add to request headers:
```
Authorization: Bearer eyJhbGc...
```

---

## 🌲 Common API Operations

### List Community Forests
```bash
curl "http://localhost:8000/api/forests/community-forests?limit=10"
```

### Search Forests
```bash
curl "http://localhost:8000/api/forests/community-forests?search=Lohandra"
```

### Get Forest Details
```bash
curl "http://localhost:8000/api/forests/community-forests/1"
```

### Upload Forest Boundary (requires auth)
```bash
curl -X POST "http://localhost:8000/api/forests/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@forest.shp" \
  -F "forest_name=Test Forest"
```

### Get My Forests (requires auth)
```bash
curl "http://localhost:8000/api/forests/my-forests" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### List Calculations (requires auth)
```bash
curl "http://localhost:8000/api/forests/calculations" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Calculation Result (requires auth)
```bash
curl "http://localhost:8000/api/forests/calculations/CALC_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🗄️ Database Commands

### Connect to Database
```bash
psql -U postgres -d cf_db
```

### Check Tables
```sql
-- List all tables in public schema
\dt public.*

-- Check forest_managers table
SELECT * FROM public.forest_managers;

-- Check users
SELECT id, email, full_name, role, status FROM public.users;

-- Count community forests
SELECT COUNT(*) FROM admin."community forests";
```

### Create Super Admin
```sql
-- Update existing user to super admin
UPDATE public.users
SET role = 'super_admin'
WHERE email = 'admin@example.com';
```

### Assign User to Forest
```sql
-- Insert forest manager record
INSERT INTO public.forest_managers (user_id, community_forest_id, role)
VALUES (
  'USER_UUID',
  1,  -- Forest ID
  'manager'
);
```

---

## 🐛 Troubleshooting

### Check Server Status
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

### View Database Pool Status
```bash
curl http://localhost:8000/api/db-info
```

### Check Logs
Server logs appear in terminal where uvicorn is running.

### Verify PostGIS
```sql
SELECT PostGIS_Full_Version();
```

### Check Raster Data
```sql
-- Check if rasters schema exists
\dn

-- List raster tables
\dt rasters.*

-- Check DEM raster
SELECT rid, ST_BandMetaData(rast, 1)
FROM rasters.dem
LIMIT 1;
```

---

## 📝 File Upload Formats

### Supported Formats
- **Shapefile**: `.shp` (must be in `.zip` with .shx, .dbf, .prj)
- **KML**: `.kml`
- **GeoJSON**: `.geojson` or `.json`
- **GeoPackage**: `.gpkg`

### Supported Geometries
- Point (creates buffer)
- LineString (converts to polygon)
- Polygon (direct use)

### File Size Limit
- Maximum: 50 MB (configured in .env)

---

## 🔧 Configuration

### Environment Variables (.env)
```bash
DATABASE_URL=postgresql://postgres:admin123@localhost:5432/cf_db
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
MAX_UPLOAD_SIZE_MB=50
DEBUG=True
```

### Change Port
Edit start.bat:
```batch
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Change Database
Edit .env:
```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

---

## 📊 Analysis Results Structure

### Response Format
```json
{
  "id": "uuid",
  "status": "completed",
  "processing_time_seconds": 15,
  "result_data": {
    "area_sqm": 1000000,
    "area_hectares": 100.0,
    "elevation_min_m": 1200,
    "elevation_max_m": 1800,
    "elevation_mean_m": 1500,
    "slope_dominant_class": "moderate",
    "slope_percentages": {
      "gentle": 20.5,
      "moderate": 45.3,
      "steep": 25.2,
      "very_steep": 9.0
    },
    "aspect_dominant": "south",
    "canopy_dominant_class": "pole_trees",
    "agb_mean_mg_ha": 150.5,
    "carbon_stock_mg": 7525.0
  }
}
```

---

## 🎯 Testing Checklist

### Smoke Tests
- [ ] Server starts without errors
- [ ] Health endpoint returns healthy
- [ ] API docs load at /docs
- [ ] Database connection successful

### Functionality Tests
- [ ] User registration works
- [ ] Login returns valid token
- [ ] List forests returns data
- [ ] Get forest details includes geometry
- [ ] Upload file processes successfully
- [ ] Analysis completes and returns results

### Security Tests
- [ ] Can't access protected routes without token
- [ ] Can't access other users' data
- [ ] Invalid token returns 401
- [ ] Weak password rejected

---

## 💻 Development Workflow

### 1. Make Changes
Edit files in `backend/app/`

### 2. Server Auto-Reloads
Uvicorn with `--reload` flag watches for changes

### 3. Test via Swagger
Open http://localhost:8000/docs

### 4. Check Logs
View terminal where server is running

### 5. Database Changes
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Review migration file
# Edit alembic/versions/XXX_description.py

# Apply migration
alembic upgrade head
```

---

## 📚 Code Locations

### Add New Raster Analysis
File: `backend/app/services/analysis.py`
Function: `analyze_rasters()`

### Add New API Endpoint
File: `backend/app/api/forests.py` or `auth.py`
Register in: `backend/app/main.py`

### Add New Database Model
File: `backend/app/models/`
Then: Create migration with alembic

### Add New Validation Schema
File: `backend/app/schemas/`

### Modify File Processing
File: `backend/app/services/file_processor.py`

---

## 🎓 Learning Resources

### FastAPI
- Official Docs: https://fastapi.tiangolo.com
- Tutorial: https://fastapi.tiangolo.com/tutorial/

### SQLAlchemy
- Official Docs: https://docs.sqlalchemy.org
- ORM Tutorial: https://docs.sqlalchemy.org/en/20/orm/

### PostGIS
- Official Docs: https://postgis.net/docs/
- Raster Functions: https://postgis.net/docs/RT_reference.html

### GeoPandas
- Official Docs: https://geopandas.org
- Examples: https://geopandas.org/en/stable/gallery/

---

## 🚨 Common Errors

### Error: "Port 8000 already in use"
Solution: Kill existing process or use different port
```bash
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Error: "Database connection failed"
Solution: Check PostgreSQL is running
```bash
services.msc
# Find postgresql-x64-15 service
```

### Error: "Module not found"
Solution: Install dependencies
```bash
pip install -r requirements.txt
```

### Error: "No module named 'app'"
Solution: Run from correct directory
```bash
cd D:\forest_management\backend
python -m uvicorn app.main:app --reload
```

### Error: "Alembic: Can't locate revision"
Solution: Stamp database to current version
```bash
alembic stamp head
```

---

## 📞 Support

1. Check this quick reference
2. Review SETUP.md for detailed instructions
3. Check PROJECT_SUMMARY.md for overview
4. Review API docs at /docs
5. Check server logs for errors

---

**Last Updated**: January 21, 2026
**Version**: 1.0.0
