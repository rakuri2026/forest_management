"""Test script for Slope Map generation"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

print("Testing Slope Map generation...")
print("Slope Classes:")
print("  0-5°: Flat (green)")
print("  5-15°: Gentle (yellow)")
print("  15-30°: Moderate (orange)")
print("  30-45°: Steep (red-orange)")
print("  >45°: Very Steep (dark red)")

# Get calculation with completed analysis
db = SessionLocal()
stmt = select(Calculation).where(
    Calculation.boundary_geom.isnot(None),
    Calculation.status == 'completed'
).limit(1)
result = db.execute(stmt)
calculation = result.scalar_one_or_none()

if calculation:
    print(f"\nUsing calculation: {calculation.id}")
    print(f"Forest name: {calculation.forest_name or 'Community Forest'}")

    # Convert geometry to GeoJSON
    shape_geom = to_shape(calculation.boundary_geom)
    geojson = mapping(shape_geom)

    # Get bounds
    bounds = shape_geom.bounds
    print(f"Bounds: {bounds}")

    # Generate slope map
    generator = MapGenerator(dpi=300)
    output_file = 'testData/slope_map.png'

    print(f"\nGenerating slope map...")
    print("This may take a few minutes to query raster data...")

    generator.generate_slope_map(
        geometry=geojson,
        db_session=db,
        forest_name=calculation.forest_name or 'Community Forest',
        orientation='auto',
        output_path=output_file
    )

    print(f"\nSUCCESS! Slope map saved to: {output_file}")
    print("\nOpen the map to verify:")
    print("  [x] Color-coded slope classes")
    print("  [x] Forest boundary outline")
    print("  [x] Legend showing 5 slope classes")
    print("  [x] Professional layout (same as boundary map)")
    print("  [x] North arrow, scale bar, metadata")

else:
    print("No calculation found with completed analysis")

db.close()
