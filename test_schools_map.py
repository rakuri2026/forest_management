"""Test script for boundary map with schools within 100m"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

print("Testing boundary map with schools within 100m...")

# Get calculation with completed analysis
db = SessionLocal()
stmt = select(Calculation).where(
    Calculation.boundary_geom.isnot(None),
    Calculation.status == 'completed'
).limit(1)
result = db.execute(stmt)
calculation = result.scalar_one_or_none()

if calculation:
    print(f"Using calculation: {calculation.id}")
    print(f"Forest name: {calculation.forest_name or 'Community Forest'}")

    # Convert geometry to GeoJSON
    shape_geom = to_shape(calculation.boundary_geom)
    geojson = mapping(shape_geom)

    # Get bounds for context
    bounds = shape_geom.bounds
    print(f"Bounds: {bounds}")

    # Generate map with schools
    generator = MapGenerator(dpi=300)
    output_file = 'testData/boundary_with_schools.png'

    print(f"\nGenerating map with schools (100m buffer)...")
    generator.generate_boundary_map(
        geometry=geojson,
        forest_name=calculation.forest_name or 'Community Forest',
        orientation='auto',
        output_path=output_file,
        db_session=db,  # Pass database session for school query
        show_schools=True,
        school_buffer_m=100.0
    )

    print(f"SUCCESS! Map with schools saved to: {output_file}")
    print("\nOpen the map to verify:")
    print("- Schools shown as red triangles")
    print("- School names labeled (if available)")
    print("- Legend includes 'Schools' entry")

else:
    print("No calculation found with completed analysis")

db.close()
