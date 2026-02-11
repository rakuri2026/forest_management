"""
Test script for new landcover_1984 and hansen2000 analyses
"""
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import analyze_landcover_1984_geometry, analyze_hansen2000_geometry

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Test with a sample geometry (small area in Nepal)
test_wkt = "POLYGON((84.5 27.5, 84.6 27.5, 84.6 27.6, 84.5 27.6, 84.5 27.5))"

print("=" * 70)
print("Testing New Analyses")
print("=" * 70)

# Test 1: Landcover 1984 (Vector)
print("\n1. Testing Landcover 1984 Analysis (Vector)...")
print("-" * 70)
try:
    result_1984 = analyze_landcover_1984_geometry(test_wkt, db)
    print(f"[OK] Success!")
    print(f"  Dominant Landcover (1984): {result_1984.get('landcover_1984_dominant')}")
    if result_1984.get('landcover_1984_percentages'):
        print(f"  Percentages:")
        for cover, pct in result_1984['landcover_1984_percentages'].items():
            print(f"    - {cover}: {pct}%")
    else:
        print(f"  No data found for this area")
except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Hansen 2000 (Raster)
print("\n2. Testing Hansen 2000 Forest Classification (Raster)...")
print("-" * 70)
try:
    result_hansen = analyze_hansen2000_geometry(test_wkt, db)
    print(f"[OK] Success!")
    print(f"  Dominant Forest Class (2000): {result_hansen.get('hansen2000_dominant')}")
    if result_hansen.get('hansen2000_percentages'):
        print(f"  Percentages:")
        for forest_class, pct in result_hansen['hansen2000_percentages'].items():
            print(f"    - {forest_class}: {pct}%")
    else:
        print(f"  No data found for this area")
except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

# Test with actual calculation geometry from database
print("\n3. Testing with Real Calculation Data...")
print("-" * 70)
try:
    # Get the most recent calculation with blocks
    query = text("""
        SELECT id, ST_AsText(boundary_geom) as wkt
        FROM calculations
        WHERE boundary_geom IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 1
    """)
    calc = db.execute(query).first()

    if calc:
        print(f"  Calculation ID: {calc.id}")
        print(f"  Testing with actual boundary geometry...")

        result_1984_real = analyze_landcover_1984_geometry(calc.wkt, db)
        result_hansen_real = analyze_hansen2000_geometry(calc.wkt, db)

        print(f"\n  Landcover 1984:")
        print(f"    Dominant: {result_1984_real.get('landcover_1984_dominant')}")
        if result_1984_real.get('landcover_1984_percentages'):
            for cover, pct in list(result_1984_real['landcover_1984_percentages'].items())[:3]:
                print(f"      {cover}: {pct}%")

        print(f"\n  Hansen 2000:")
        print(f"    Dominant: {result_hansen_real.get('hansen2000_dominant')}")
        if result_hansen_real.get('hansen2000_percentages'):
            for forest_class, pct in result_hansen_real['hansen2000_percentages'].items():
                print(f"      {forest_class}: {pct}%")
    else:
        print(f"  No calculations found in database")

except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)

db.close()
