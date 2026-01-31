"""
Compare sundar.shp boundaries with testForest database boundaries
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text
import json

# First, let's check what's in the testForest calculation
db = SessionLocal()
try:
    # Get testForest geometry and blocks
    query = text("""
        SELECT
            id,
            forest_name,
            ST_AsGeoJSON(boundary_geom) as boundary_geojson,
            ST_Area(boundary_geom::geography) as area_m2,
            result_data->'blocks' as blocks
        FROM public.calculations
        WHERE forest_name = 'testForest'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    result = db.execute(query).first()

    if result:
        print("=" * 80)
        print("testForest Database Record")
        print("=" * 80)
        print(f"ID: {result.id}")
        print(f"Forest Name: {result.forest_name}")
        print(f"Total Boundary Area: {result.area_m2 / 10000:.2f} hectares")
        print()

        # Parse blocks
        blocks = result.blocks
        if blocks:
            print(f"Number of blocks: {len(blocks)}")
            print()

            total_block_area = 0
            for i, block in enumerate(blocks, 1):
                block_name = block.get('block_name', 'Unnamed')
                area_ha = block.get('area_hectares', 0)
                total_block_area += area_ha

                print(f"Block {i}: {block_name}")
                print(f"  Area: {area_ha:.2f} ha")

                # Check if geometry exists
                geom = block.get('geometry')
                if geom:
                    # Parse the geometry to get coordinate count
                    if 'coordinates' in geom:
                        coords = geom['coordinates']
                        if coords and len(coords) > 0:
                            # For Polygon
                            if geom.get('type') == 'Polygon':
                                ring_count = len(coords)
                                point_count = len(coords[0]) if ring_count > 0 else 0
                                print(f"  Geometry: Polygon with {ring_count} ring(s), {point_count} points in outer ring")
                            # For MultiPolygon
                            elif geom.get('type') == 'MultiPolygon':
                                poly_count = len(coords)
                                print(f"  Geometry: MultiPolygon with {poly_count} polygon(s)")
                print()

            print(f"Total block area: {total_block_area:.2f} ha")
            print(f"Boundary area: {result.area_m2 / 10000:.2f} ha")
            difference = (result.area_m2 / 10000) - total_block_area
            print(f"Difference: {difference:.2f} ha ({(difference / (result.area_m2 / 10000)) * 100:.1f}%)")

    else:
        print("No testForest calculation found")

finally:
    db.close()

print()
print("=" * 80)
print("Next: We need to compare these blocks with sundar.shp")
print("=" * 80)
print("To see if the uploaded polygon boundaries match the sundar.shp file")
