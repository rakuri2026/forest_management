"""Quick test bypassing broken pyproj import"""
import sys
sys.path.insert(0, 'backend')

# Import map_generator directly without going through __init__
from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

print("Testing OSM basemap integration...")

# Get calculation
db = SessionLocal()
stmt = select(Calculation).where(
    Calculation.boundary_geom.isnot(None),
    Calculation.status == 'completed'
).limit(1)
result = db.execute(stmt)
calculation = result.scalar_one_or_none()

if calculation:
    # Convert to GeoJSON
    shape_geom = to_shape(calculation.boundary_geom)
    geojson = mapping(shape_geom)

    # Generate map
    generator = MapGenerator(dpi=300)
    generator.generate_boundary_map(
        geometry=geojson,
        forest_name='Community Forest',
        orientation='auto',
        output_path='testData/osm_test.png'
    )
    print("SUCCESS! Map saved to: testData/osm_test.png")
else:
    print("No calculation found")

db.close()
