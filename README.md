# Community Forest Management System

A comprehensive web-based GIS application for managing and analyzing community forest data in Nepal.

## Features

- **Authentication**: Secure JWT-based authentication with role-based access control
- **Forest Management**: Browse and manage 3,922+ community forests from database
- **File Upload**: Support for Shapefile, KML, GeoJSON, and GPKG formats
- **Geospatial Analysis**:
  - 16 raster datasets (DEM, slope, aspect, canopy, biomass, climate, etc.)
  - Vector proximity analysis (roads, rivers, settlements, buildings)
  - Administrative boundary intersection
- **Data Export**: GPKG format with all analysis results
- **User Permissions**: Data isolation per user, super admin oversight

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL 15+ with PostGIS 3.6
- **Geospatial**: GeoAlchemy2, Shapely, Fiona, GeoPandas
- **Authentication**: JWT tokens with bcrypt password hashing

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 15+ with PostGIS extension
- Existing cf_db database (from F:\CF_application)

### Setup

1. **Clone/Navigate to project**
   ```bash
   cd D:\forest_management
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy .env.example to .env and update if needed
   cp .env.example .env
   ```

5. **Run database migration**
   ```bash
   # Create forest_managers table
   alembic upgrade head
   ```

6. **Start development server**
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access API documentation**
   - Open browser: http://localhost:8000/docs
   - Interactive Swagger UI available

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/change-password` - Change password

### Forest Management
- `GET /api/forests/community-forests` - List community forests
- `GET /api/forests/community-forests/{id}` - Get forest details
- `GET /api/forests/my-forests` - Get user's assigned forests
- `POST /api/forests/upload` - Upload forest boundary for analysis
- `GET /api/forests/calculations` - List user's calculations
- `GET /api/forests/calculations/{id}` - Get calculation results

### Admin Only
- `POST /api/forests/assign-manager` - Assign user to forest (super admin)

## Database Schema

### New Tables (Minimal Changes)
- `public.forest_managers` - Junction table for user-forest assignments

### Existing Tables (Reused)
- `public.users` - User authentication
- `public.organizations` - Organization management
- `public.calculations` - Analysis results storage
- `admin.community_forests` - 3,922 community forest polygons
- `rasters.*` - 16 raster layers (DEM, biomass, climate, etc.)

## Project Structure

```
D:\forest_management\
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   │   ├── auth.py       # Authentication routes
│   │   │   └── forests.py    # Forest management routes
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py     # Settings management
│   │   │   └── database.py   # Database connection
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── forest_manager.py
│   │   │   ├── calculation.py
│   │   │   └── community_forest.py
│   │   ├── schemas/          # Pydantic schemas
│   │   │   ├── auth.py
│   │   │   └── forest.py
│   │   ├── services/         # Business logic
│   │   │   ├── file_processor.py
│   │   │   └── analysis.py
│   │   ├── utils/            # Utilities
│   │   │   └── auth.py
│   │   └── main.py           # FastAPI app
│   ├── alembic/              # Database migrations
│   │   └── versions/
│   ├── requirements.txt
│   └── alembic.ini
├── uploads/                  # Uploaded files (temporary)
├── exports/                  # Generated GPKG files
├── .env                      # Environment variables
└── README.md
```

## Usage Examples

### 1. Register User
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "forester@example.com",
    "password": "SecurePass123",
    "full_name": "John Forester",
    "phone": "+977-9800000000"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "forester@example.com",
    "password": "SecurePass123"
  }'
```

### 3. Upload Forest Boundary
```bash
curl -X POST "http://localhost:8000/api/forests/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@forest_boundary.shp" \
  -F "forest_name=Lohandra Community Forest" \
  -F "block_name=Block A"
```

### 4. List Community Forests
```bash
curl -X GET "http://localhost:8000/api/forests/community-forests?search=Lohandra&limit=10"
```

## Analysis Features

### Raster Analysis (16 Datasets)
1. **DEM** - Elevation min/max/mean
2. **Slope** - Classification percentages (gentle, moderate, steep, very steep)
3. **Aspect** - Directional distribution (N, NE, E, SE, S, SW, W, NW)
4. **Canopy Height** - Forest structure (non-forest, bush, pole, high forest)
5. **Above-ground Biomass** - AGB statistics and carbon stock
6. **Forest Health** - Health class distribution (1-5)
7. **Forest Type** - Dominant forest type
8. **ESA WorldCover** - Land cover classification
9. **Climate** - Temperature and precipitation
10. **Forest Loss/Gain** - Change detection (2000-2023)
11. **Soil Properties** - pH, clay, sand, organic carbon

### Vector Analysis
- **Proximity**: Settlements, roads, rivers, buildings within 1km
- **Directional**: District headquarters (N, E, S, W + distance)
- **Administrative**: Province, municipality, ward (dominant overlap)
- **Historical**: Land cover 1984 comparison
- **Natural Hazards**: Nearest earthquake point

### Area Calculation
- Automatic UTM zone detection (32644/32645 for Nepal)
- Accurate area calculation in square meters and hectares
- Vector-based precision (not raster pixel counting)

## Development

### Run Tests
```bash
pytest
```

### Database Migration
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Code Style
- Follow PEP 8 style guidelines
- Use type hints where possible
- Document functions with docstrings

## Production Deployment

1. Set `DEBUG=False` in .env
2. Use strong SECRET_KEY
3. Configure proper CORS origins
4. Use production WSGI server (gunicorn)
5. Set up reverse proxy (nginx)
6. Enable HTTPS/SSL
7. Configure database connection pooling
8. Set up logging and monitoring

## License

Proprietary - Community Forest Management System

## Contact

For support and questions, contact the development team.
