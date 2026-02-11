"""Test slope map with Rame kholsa forest boundary from KML"""
import sys
sys.path.insert(0, 'backend')

from backend.app.services.map_generator import MapGenerator
from backend.app.core.database import SessionLocal
import xml.etree.ElementTree as ET

print("Testing Slope Map with Rame kholsa Forest")
print("=" * 60)

# Parse KML file
kml_path = 'testData/inventory_test data/Outer_Rame.kml'
tree = ET.parse(kml_path)
root = tree.getroot()

# Extract coordinates from KML
ns = {'kml': 'http://www.opengis.net/kml/2.2'}
coords_text = root.find('.//kml:coordinates', ns).text.strip()

# Parse coordinates (format: lon,lat,alt lon,lat,alt ...)
coords = []
for coord_str in coords_text.split():
    parts = coord_str.split(',')
    if len(parts) >= 2:
        lon, lat = float(parts[0]), float(parts[1])
        coords.append([lon, lat])

print(f"Forest: Rame kholsa")
print(f"Area: 122.564 hectares")
print(f"Boundary points: {len(coords)}")
print(f"Location: ~85.04°E, 27.44°N")
print()

# Create GeoJSON geometry
geojson = {
    "type": "Polygon",
    "coordinates": [coords]
}

# Get bounds
lons = [c[0] for c in coords]
lats = [c[1] for c in coords]
print(f"Bounds:")
print(f"  Longitude: {min(lons):.6f} to {max(lons):.6f}")
print(f"  Latitude: {min(lats):.6f} to {max(lats):.6f}")
print()

# Generate slope map
db = SessionLocal()
generator = MapGenerator(dpi=300)

print("Generating slope map...")
print("Querying slope raster data from database...")
print()

try:
    generator.generate_slope_map(
        geometry=geojson,
        db_session=db,
        forest_name='Rame kholsa',
        orientation='auto',
        output_path='testData/slope_map_rame.png'
    )

    print("\n" + "=" * 60)
    print("SUCCESS! Slope map saved to:")
    print("  testData/slope_map_rame.png")
    print("\nExpected slope classes:")
    print("  [x] Flat (0-5°) - Green")
    print("  [x] Gentle (5-15°) - Yellow")
    print("  [x] Moderate (15-30°) - Orange")
    print("  [x] Steep (30-45°) - Red-Orange")
    print("  [x] Very Steep (>45°) - Dark Red")
    print("\nMap features:")
    print("  [x] Color-coded slope classification")
    print("  [x] Forest boundary outline")
    print("  [x] Legend with slope classes")
    print("  [x] North arrow, scale bar, metadata")

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
