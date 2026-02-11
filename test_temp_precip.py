"""
Test temperature and precipitation analyses
"""
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import analyze_temperature_geometry, analyze_precipitation_geometry

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Testing Temperature and Precipitation Analyses")
print("=" * 70)

# Get the most recent calculation
query = text("""
    SELECT id, forest_name, ST_AsText(boundary_geom) as wkt, result_data
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

    print("\n" + "=" * 70)
    print("WHOLE FOREST DATA (from result_data)")
    print("=" * 70)

    print("\nTemperature:")
    print(f"  Mean: {result_data.get('temperature_mean_c')} °C")
    print(f"  Min (coldest month): {result_data.get('temperature_min_c')} °C")

    print("\nPrecipitation:")
    print(f"  Annual mean: {result_data.get('precipitation_mean_mm')} mm/year")

    # Test with actual geometry
    print("\n" + "=" * 70)
    print("TESTING FUNCTIONS WITH WHOLE FOREST GEOMETRY")
    print("=" * 70)

    print("\n1. Testing analyze_temperature_geometry()...")
    try:
        temp_result = analyze_temperature_geometry(calc.wkt, db)
        print(f"   Result: {temp_result}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n2. Testing analyze_precipitation_geometry()...")
    try:
        precip_result = analyze_precipitation_geometry(calc.wkt, db)
        print(f"   Result: {precip_result}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Check blocks
    print("\n" + "=" * 70)
    print("BLOCK DATA")
    print("=" * 70)
    blocks = result_data.get('blocks', [])
    if blocks:
        print(f"\nTotal blocks: {len(blocks)}")
        print(f"\nChecking first 3 blocks for temperature/precipitation:")
        print("-" * 70)
        for i, block in enumerate(blocks[:3]):
            print(f"\nBlock {i+1}: {block.get('block_name', 'Unknown')}")
            print(f"  Temperature mean: {block.get('temperature_mean_c')} °C")
            print(f"  Temperature min: {block.get('temperature_min_c')} °C")
            print(f"  Precipitation: {block.get('precipitation_mean_mm')} mm/year")
    else:
        print("  No blocks found")

else:
    print("No calculations found in database")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)

db.close()
