# Community Forest Management System

A comprehensive web-based GIS application for managing and analyzing community forest data in Nepal.

## Features

### Core Features
- **Authentication**: Secure JWT-based authentication with role-based access control
- **Forest Management**: Browse and manage 3,922+ community forests from database
- **File Upload**: Support for Shapefile, KML, GeoJSON, and GPKG formats
- **Geospatial Analysis**:
  - 16 raster datasets (DEM, slope, aspect, canopy, biomass, climate, soil, etc.)
  - Vector proximity analysis (roads, rivers, settlements, buildings)
  - Administrative boundary intersection
  - Block-wise analysis support

### Advanced Features
- **Species Management**: Database of 137 tree species with ecological data
- **Sampling Design**: Systematic, random, and stratified sampling methods
- **Field Inventory**: Tree measurement data import and validation
- **Tree Distribution Model**: Synthetic tree point generation (GPKG export)
- **Biodiversity Analysis**: Species richness and diversity metrics
- **User Group Mapping**: Multi-forest analysis with raster visualization
- **Interactive Maps**: Leaflet-based mapping with multiple base layers
- **Excel Export**: Comprehensive fieldbook generation
- **Data Export**: GPKG format with all analysis results

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL 15+ with PostGIS 3.6
- **Geospatial**: GeoAlchemy2, Shapely, Fiona, GeoPandas, rasterio
- **Authentication**: JWT tokens with bcrypt password hashing

### Frontend
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **Mapping**: Leaflet, React-Leaflet
- **UI**: Tailwind CSS
- **State Management**: React hooks
- **API Client**: Axios

## Installation

### Prerequisites

- Python 3.9+
- Node.js 18+ and npm
- PostgreSQL 15+ with PostGIS extension
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd forest_management
   ```

2. **Backend Setup**
   ```bash
   # Create virtual environment
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac

   # Install dependencies
   cd backend
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

4. **Database Setup**
   ```bash
   # Create database
   createdb cf_db

   # Enable PostGIS
   psql -d cf_db -c "CREATE EXTENSION postgis;"

   # Run migrations
   cd backend
   alembic upgrade head
   ```

5. **Configure Environment**
   ```bash
   # Copy .env.example to .env and configure
   cp .env.example .env

   # Edit .env with your database credentials:
   # DATABASE_URL=postgresql://postgres:your_password@localhost:5432/cf_db
   # SECRET_KEY=your-secret-key-here
   ```

6. **Start the Application**
   ```bash
   # Option 1: Use batch file (Windows)
   start_all.bat

   # Option 2: Manual start
   # Terminal 1 - Backend
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8001

   # Terminal 2 - Frontend
   cd frontend
   npm run dev
   ```

7. **Access the Application**
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8001
   - API Documentation: http://localhost:8001/docs

### Demo Credentials
```
Email: demo@forest.com
Password: Demo1234
```

## Project Structure

```
forest_management/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   │   ├── auth.py       # Authentication
│   │   │   ├── forests.py    # Forest management
│   │   │   ├── sampling.py   # Sampling design
│   │   │   ├── inventory.py  # Tree inventory
│   │   │   ├── tree_models.py # Tree distribution
│   │   │   ├── field_inventory.py
│   │   │   ├── user_group.py
│   │   │   └── ...
│   │   ├── core/             # Core configuration
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── analysis.py
│   │   │   ├── sampling.py
│   │   │   ├── inventory.py
│   │   │   ├── tree_distribution.py
│   │   │   └── ...
│   │   └── main.py
│   ├── alembic/              # Database migrations
│   ├── requirements.txt
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── AnalysisTabContent.tsx
│   │   │   ├── SamplingTab.tsx
│   │   │   ├── FieldbookTab.tsx
│   │   │   ├── TreeModelGenerator.tsx
│   │   │   ├── BiodiversityTab.tsx
│   │   │   ├── FieldInventoryTab.tsx
│   │   │   ├── TotalInventoryTab.tsx
│   │   │   └── ...
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   └── CalculationDetail.tsx
│   │   ├── services/
│   │   │   └── api.ts        # API client
│   │   └── types/
│   ├── package.json
│   └── vite.config.ts
├── uploads/                  # Uploaded files (gitignored)
├── exports/                  # Generated GPKG files (gitignored)
├── .env.example              # Example environment file
├── .gitignore
├── start_all.bat             # Windows start script
├── stop_all.bat              # Windows stop script
├── restart_all.bat           # Windows restart script
└── README.md
```

## Application Features

### Analysis Tab
- Whole forest summary statistics
- Block-wise detailed analysis
- 16 raster parameters analysis
- Species identification and management
- Interactive map visualization

### Fieldbook Tab
- Systematic sampling design
- Plot layout generation
- Topographic feature analysis
- Excel export with proper formatting

### Sampling Tab
- Multiple sampling methods (systematic, random, stratified)
- Accessible forest filtering
- Sample plot export (GPKG, CSV)

### Tree Model Tab
- Synthetic tree distribution generation
- Species-wise DBH and height classes
- GPKG export for GIS software
- Volume calculation integration

### Tree Mapping Tab
- CSV import with column mapping
- Tree data validation
- Volume calculations
- Export with allometric data

### Biodiversity Tab
- Species richness analysis
- Diversity indices
- Family-wise distribution
- Ecological characteristics

### Field Inventory Tab
- Field data import
- Sample plot configuration
- MAI/AAH calculations
- Species breakdown

### Total Inventory Tab
- Total forest inventory calculations
- Tree cover analysis
- Block-wise effective area
- Custom multipliers

### User Group Map Tab
- Multi-forest analysis
- Raster layer visualization
- Land cover analysis
- Climate data integration

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info

### Forest Management
- `POST /api/forests/upload` - Upload boundary file
- `GET /api/forests/calculations` - List user's calculations
- `GET /api/forests/calculations/{id}` - Get analysis results
- `DELETE /api/forests/calculations/{id}` - Delete calculation
- `POST /api/forests/calculations/{id}/tree-cover-areas` - Calculate tree cover

### Species Management
- `PATCH /api/forests/calculations/{id}/species/{name}/confirm` - Confirm species
- `POST /api/forests/calculations/{id}/add-species` - Add species manually
- `DELETE /api/forests/calculations/{id}/remove-species/{name}` - Remove species

### Sampling
- `POST /api/calculations/{id}/sampling/generate` - Generate sampling design
- `GET /api/calculations/{id}/sampling` - Get sampling designs
- `GET /api/sampling-designs/{id}/export` - Export sampling design

### Tree Inventory
- `POST /api/calculations/{id}/inventory/upload` - Upload inventory CSV
- `POST /api/calculations/{id}/inventory/column-mapping` - Map columns
- `GET /api/calculations/{id}/inventory` - Get inventory data

### Tree Model
- `POST /api/calculations/{id}/generate-tree-model` - Generate tree model
- `GET /api/tree-models/{id}` - Get model status
- `GET /api/tree-models/{id}/download` - Download GPKG

## Database Schema

### Key Tables
- `public.users` - User authentication
- `public.calculations` - Analysis results (JSONB storage)
- `public.sampling_designs` - Sample plot designs
- `public.inventory` - Tree measurement data
- `public.synthetic_tree_models` - Generated tree models
- `public.tree_species_coefficients` - 137 species with ecological data
- `public.forest_types` - 25 forest types (Forest Regulation 2079)
- `admin.community_forests` - 3,922 existing forests
- `rasters.*` - 16 raster datasets

## Development

### Running Tests
```bash
cd backend
pytest
```

### Database Migration
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Code Style
- Backend: Follow PEP 8 style guidelines
- Frontend: ESLint + Prettier configuration
- Use type hints (Python) and TypeScript types

## Deployment

### Production Checklist
1. Set `DEBUG=False` in .env
2. Use strong `SECRET_KEY`
3. Configure proper CORS origins
4. Use production WSGI server (gunicorn)
5. Set up reverse proxy (nginx)
6. Enable HTTPS/SSL
7. Configure database connection pooling
8. Set up logging and monitoring
9. Optimize PostgreSQL for production
10. Set up backup strategy

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cf_db

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
ALLOWED_ORIGINS=http://localhost:3001,https://yourdomain.com
```

## Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8001
netstat -ano | findstr :3001
taskkill /F /PID <PID>

# Linux
lsof -i :8001
kill -9 <PID>
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
# Windows: Check Services
# Linux: systemctl status postgresql

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

## Forest Regulation 2079 Compliance

This system follows Nepal's Forest Regulation 2079 (2023):
- 25 standardized forest types with class numbers
- 137 tree species with scientific and local names
- Species characteristics: altitude range, growth rate, economic value
- Volume calculation using approved allometric equations
- MAI (Mean Annual Increment) calculations
- AAH (Allowable Annual Harvest) methodology

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

Proprietary - Community Forest Management System

## Support

For support and questions:
- Check API documentation: http://localhost:8001/docs
- Review system logs
- Contact development team

## Version

**Version**: 1.5.0
**Last Updated**: March 23, 2026
**Status**: Production Ready

---

**Note**: This system requires raster datasets to be loaded in the database. Contact the development team for data setup instructions.
