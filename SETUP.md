# Setup Guide - Community Forest Management System

## Quick Start (Windows)

### Step 1: Install Prerequisites

1. **Python 3.9+**
   - Download from: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"
   - Verify: `python --version`

2. **PostgreSQL 15+ with PostGIS**
   - Already installed (cf_db database exists)
   - Connection: postgres/admin123@localhost:5432/cf_db

### Step 2: Setup Project

```bash
# Navigate to project directory
cd D:\forest_management

# Run the start script (will setup everything automatically)
start.bat
```

The `start.bat` script will automatically:
- Create Python virtual environment
- Install all dependencies
- Run database migrations
- Start the FastAPI server

### Step 3: Verify Installation

1. **Check API is running**
   - Open browser: http://localhost:8000
   - Should see: `{"app": "Community Forest Management System", "status": "running"}`

2. **Access API Documentation**
   - Open: http://localhost:8000/docs
   - Interactive Swagger UI with all endpoints

3. **Check Database Connection**
   - Open: http://localhost:8000/health
   - Should see: `{"status": "healthy", "database": "connected"}`

### Step 4: Create First User

Using the API docs (http://localhost:8000/docs):

1. Expand `POST /api/auth/register`
2. Click "Try it out"
3. Fill in user details:
   ```json
   {
     "email": "admin@example.com",
     "password": "SecurePass123",
     "full_name": "Forest Administrator",
     "phone": "+977-9800000000"
   }
   ```
4. Click "Execute"
5. Copy the response (user created successfully)

### Step 5: Login and Get Token

1. Expand `POST /api/auth/login`
2. Click "Try it out"
3. Enter credentials:
   ```json
   {
     "email": "admin@example.com",
     "password": "SecurePass123"
   }
   ```
4. Click "Execute"
5. Copy the `access_token` from response

### Step 6: Authorize in Swagger UI

1. Click the "Authorize" button (top right with lock icon)
2. Enter: `Bearer YOUR_ACCESS_TOKEN` (replace with your token)
3. Click "Authorize"
4. Click "Close"

Now all endpoints are authenticated and you can test them!

---

## Manual Setup (Alternative)

If you prefer manual setup:

### 1. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# .env file is already created with correct settings
# Database: postgresql://postgres:admin123@localhost:5432/cf_db
```

### 4. Run Database Migration
```bash
cd backend
alembic upgrade head
```

This creates the `forest_managers` table in cf_db database.

### 5. Start Server
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Testing the System

### Test 1: List Community Forests
```bash
curl http://localhost:8000/api/forests/community-forests?limit=5
```

Should return 5 community forests from the database.

### Test 2: Get Specific Forest
```bash
curl http://localhost:8000/api/forests/community-forests/1
```

Returns detailed information including boundary geometry.

### Test 3: Upload File (requires authentication)
```bash
curl -X POST "http://localhost:8000/api/forests/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_forest.shp" \
  -F "forest_name=Test Forest"
```

---

## Database Verification

Check if forest_managers table was created:

```sql
-- Connect to cf_db
psql -U postgres -d cf_db

-- Check if table exists
\dt public.forest_managers

-- View table structure
\d public.forest_managers

-- Exit
\q
```

Expected output:
```
Table "public.forest_managers"
Column              | Type                     | Nullable | Default
--------------------+--------------------------+----------+---------
id                  | uuid                     | not null | gen_random_uuid()
user_id             | uuid                     | not null |
community_forest_id | integer                  | not null |
role                | character varying(50)    | not null |
assigned_date       | timestamp with time zone | not null | now()
is_active           | boolean                  | not null | true
```

---

## Common Issues and Solutions

### Issue 1: Port 8000 already in use
**Solution**: Change port in start.bat or run manually:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Issue 2: Database connection failed
**Solution**: Check PostgreSQL is running:
```bash
# Check PostgreSQL service
services.msc
# Find "postgresql-x64-15" and ensure it's running
```

### Issue 3: Import errors
**Solution**: Reinstall dependencies:
```bash
pip install --force-reinstall -r requirements.txt
```

### Issue 4: Alembic migration errors
**Solution**: Check current migration status:
```bash
alembic current
alembic history
```

If needed, stamp to current version:
```bash
alembic stamp head
```

---

## Next Steps

1. **Create Super Admin User**
   - Update a user role in database:
   ```sql
   UPDATE public.users
   SET role = 'super_admin'
   WHERE email = 'admin@example.com';
   ```

2. **Assign Forests to Users**
   - Use `POST /api/forests/assign-manager` endpoint (super admin only)

3. **Test File Upload**
   - Prepare test files: .shp, .kml, .geojson, or .gpkg
   - Upload via API or Swagger UI

4. **Explore Community Forests**
   - Browse 3,922 existing forests via API
   - Get boundaries and metadata

5. **Run Analysis**
   - Upload forest boundary
   - System automatically analyzes:
     - Raster data (elevation, slope, biomass, etc.)
     - Vector proximity (roads, rivers, settlements)
     - Administrative boundaries

---

## Development Tips

### View Logs
```bash
# Server logs are in console
# For file logging, configure in app/core/config.py
```

### Database Query Testing
```bash
# Connect to database
psql -U postgres -d cf_db

# Test spatial query
SELECT name, ST_Area(geom) as area
FROM admin."community forests"
LIMIT 5;
```

### API Testing with Postman
1. Import OpenAPI spec: http://localhost:8000/openapi.json
2. Create environment with base URL: http://localhost:8000
3. Add authorization header: Bearer {{token}}

---

## Production Deployment Checklist

- [ ] Change SECRET_KEY in .env
- [ ] Set DEBUG=False
- [ ] Configure proper CORS_ORIGINS
- [ ] Use gunicorn instead of uvicorn
- [ ] Set up nginx reverse proxy
- [ ] Enable HTTPS/SSL
- [ ] Configure logging to files
- [ ] Set up database backups
- [ ] Monitor application health
- [ ] Set up firewall rules

---

## Support

For issues or questions:
1. Check this setup guide
2. Review API documentation at /docs
3. Check server logs
4. Verify database connection
5. Contact development team
