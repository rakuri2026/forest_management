"""Test script for Phase 3: All contextual features"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from sqlalchemy import select
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

print("Testing Phase 3: Boundary map with ALL contextual features...")
print("Features: Schools, POI, Roads, Rivers, Ridges, ESA Boundary")

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

    # Get bounds for context
    bounds = shape_geom.bounds
    print(f"Bounds: {bounds}")

    # Generate comprehensive map with all Phase 3 features
    generator = MapGenerator(dpi=300)
    output_file = 'testData/phase3_full_context_map.png'

    print(f"\nGenerating map with ALL contextual features (100m buffer)...")
    print("  - Schools (red triangles)")
    print("  - POI (orange diamonds)")
    print("  - Roads (colored lines, no labels)")
    print("  - Rivers (blue lines WITH labels - crucial)")
    print("  - Ridges (brown dashed lines WITH labels - crucial)")
    print("  - ESA Boundary (purple dotted line)")

    generator.generate_boundary_map(
        geometry=geojson,
        forest_name=calculation.forest_name or 'Community Forest',
        orientation='auto',
        output_path=output_file,
        db_session=db,
        show_schools=True,
        show_poi=True,
        show_roads=True,
        show_rivers=True,
        show_ridges=True,
        show_esa_boundary=True,
        buffer_m=100.0
    )

    print(f"\nSUCCESS! Full context map saved to: {output_file}")
    print("\nOpen the map to verify:")
    print("  [x] Schools shown as red triangles with labels")
    print("  [x] POI shown as orange diamonds with labels")
    print("  [x] Roads shown as colored lines (NO labels)")
    print("  [x] Rivers shown as blue lines WITH names")
    print("  [x] Ridges shown as brown dashed lines WITH names")
    print("  [x] ESA boundary shown as purple dotted line")
    print("  [x] Legend includes all visible features")
    print("  [x] Professional map appearance")

else:
    print("No calculation found with completed analysis")

db.close()
