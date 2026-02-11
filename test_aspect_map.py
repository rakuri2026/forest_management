"""
Test script for aspect map generation
"""

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
from backend.app.models.calculation import Calculation
from shapely.geometry import mapping

print("Testing Aspect Map generation...")
print("Aspect Classes (pre-classified in database):")
print("  0: Flat (slope < 2°)")
print("  1: N (337.5° - 22.5°)")
print("  2: NE (22.5° - 67.5°)")
print("  3: E (67.5° - 112.5°)")
print("  4: SE (112.5° - 157.5°)")
print("  5: S (157.5° - 202.5°)")
print("  6: SW (202.5° - 247.5°)")
print("  7: W (247.5° - 292.5°)")
print("  8: NW (292.5° - 337.5°)")

# Get database session
db = SessionLocal()

try:
    # Get a test calculation with boundary
    calc = db.query(Calculation).filter(
        Calculation.boundary_geom.isnot(None),
        Calculation.status == 'COMPLETED'
    ).first()

    if not calc:
        print("ERROR: No completed calculations found with boundary geometry")
        exit(1)

    print(f"\nUsing calculation: {calc.id}")
    print(f"Forest name: {calc.forest_name}")

    # Convert boundary to GeoJSON
    from shapely import wkb
    geom_shape = wkb.loads(bytes(calc.boundary_geom.data))
    geometry = mapping(geom_shape)

    # Get bounds for info
    bounds = geom_shape.bounds
    print(f"Bounds: ({bounds[0]:.2f}, {bounds[1]:.2f}, {bounds[2]:.2f}, {bounds[3]:.2f})")

    # Create map generator
    generator = MapGenerator(dpi=300)

    # Generate aspect map
    print("\nGenerating aspect map...")
    print("This may take a few minutes to query raster data...")

    output_path = "testData/aspect_map.png"

    buffer = generator.generate_aspect_map(
        geometry=geometry,
        db_session=db,
        forest_name=calc.forest_name or 'Community Forest',
        orientation='auto',
        output_path=output_path
    )

    print(f"\nSUCCESS! Aspect map saved to: {output_path}")
    print("\nOpen the map to verify:")
    print("  [x] Color-coded aspect classes (9 directions)")
    print("  [x] Forest boundary outline")
    print("  [x] Legend showing present aspect classes")
    print("  [x] Professional layout (same template)")
    print("  [x] North arrow, scale bar, metadata")

finally:
    db.close()
