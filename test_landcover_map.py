"""Test script for Land Cover Map generation"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

print("Testing Land Cover Map generation...")
print("ESA WorldCover v100 Classes:")
print("  10: Tree cover (dark green)")
print("  20: Shrubland (olive)")
print("  30: Grassland (light yellow)")
print("  40: Cropland (pink)")
print("  50: Built-up (red)")
print("  60: Bare/sparse vegetation (gray)")
print("  80: Water (blue)")
print("  90: Herbaceous wetland (cyan)")

# Get calculation
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

    # Generate land cover map
    generator = MapGenerator(dpi=300)
    output_file = 'testData/landcover_map.png'

    print(f"\nGenerating land cover map...")
    print("This may take a few minutes to query raster data...")

    generator.generate_landcover_map(
        geometry=geojson,
        db_session=db,
        forest_name=calculation.forest_name or 'Community Forest',
        orientation='auto',
        output_path=output_file
    )

    print(f"\nSUCCESS! Land cover map saved to: {output_file}")
    print("\nOpen the map to verify:")
    print("  [x] Color-coded land cover classes")
    print("  [x] Forest boundary outline")
    print("  [x] Legend showing present land cover types")
    print("  [x] Professional layout (same template)")
    print("  [x] North arrow, scale bar, metadata")

else:
    print("No calculation found")

db.close()
