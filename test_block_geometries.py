"""
Test why some blocks have no temperature/precipitation data
"""
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import analyze_temperature_geometry, analyze_precipitation_geometry
from shapely.geometry import shape
from shapely import wkt as shapely_wkt

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Testing Block Geometries for Temperature/Precipitation")
print("=" * 70)

# Get the most recent calculation
query = text("""
    SELECT id, forest_name, result_data
    FROM calculations
    WHERE boundary_geom IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
""")
calc = db.execute(query).first()

if calc:
    print(f"\nCalculation ID: {calc.id}")
    print(f"Forest Name: {calc.forest_name}")

    result_data = calc.result_data or {}
    blocks = result_data.get('blocks', [])

    print(f"\nTesting all {len(blocks)} blocks:")
    print("=" * 70)

    for i, block in enumerate(blocks):
        block_name = block.get('block_name', f'Block {i+1}')
        print(f"\n{i+1}. {block_name}")
        print("-" * 70)

        # Check if block has WKT or geometry
        if 'wkt' in block:
            block_wkt = block['wkt']
            print(f"   Using WKT from block data")
        elif 'geometry' in block:
            try:
                geom = shape(block['geometry'])
                block_wkt = shapely_wkt.dumps(geom)
                print(f"   Converted GeoJSON to WKT")
            except Exception as e:
                print(f"   ERROR converting geometry: {e}")
                continue
        else:
            print(f"   ERROR: No geometry found")
            continue

        # Test temperature
        try:
            temp_result = analyze_temperature_geometry(block_wkt, db)
            temp_mean = temp_result.get('temperature_mean_c')
            temp_min = temp_result.get('temperature_min_c')
            print(f"   Temperature: {temp_mean}°C (mean), {temp_min}°C (min)")
        except Exception as e:
            print(f"   Temperature ERROR: {e}")

        # Test precipitation
        try:
            precip_result = analyze_precipitation_geometry(block_wkt, db)
            precip_mean = precip_result.get('precipitation_mean_mm')
            print(f"   Precipitation: {precip_mean} mm/year")
        except Exception as e:
            print(f"   Precipitation ERROR: {e}")

        # Show what's currently in the block data
        print(f"   Current in DB: temp={block.get('temperature_mean_c')}, precip={block.get('precipitation_mean_mm')}")

else:
    print("No calculations found in database")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)

db.close()
