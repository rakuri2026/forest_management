"""
Test script for new analysis functions (physiography, ecoregion, NASA forest 2020)
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.services.analysis import (
    analyze_physiography_geometry,
    analyze_ecoregion_geometry,
    analyze_nasa_forest_2020_geometry
)

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def test_new_analysis():
    """Test the three new analysis functions on Chaukitole CF"""

    db = SessionLocal()

    try:
        # Get a completed calculation with geometry
        calc_query = text("""
            SELECT id, forest_name, ST_AsText(boundary_geom) as wkt
            FROM public.calculations
            WHERE status = 'COMPLETED'
              AND boundary_geom IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        """)

        result = db.execute(calc_query).first()

        if not result:
            print("No completed calculations found!")
            return

        print(f"\nTesting on: {result.forest_name}")
        print(f"Calculation ID: {result.id}")
        print("=" * 80)

        wkt = result.wkt

        # Test 1: Physiography
        print("\n1. Testing Physiography Analysis...")
        physio_result = analyze_physiography_geometry(wkt, db)
        print(f"   Result: {physio_result}")

        if physio_result.get('physiography_percentages'):
            percentages = physio_result['physiography_percentages']
            total = sum(percentages.values())
            print(f"   Total percentage: {total:.2f}% (should be ~100%)")
            for zone, pct in percentages.items():
                print(f"   - {zone}: {pct}%")
        else:
            print("   WARNING: No physiography data returned!")

        # Test 2: Ecoregion
        print("\n2. Testing Ecoregion Analysis...")
        ecoregion_result = analyze_ecoregion_geometry(wkt, db)
        print(f"   Result: {ecoregion_result}")

        if ecoregion_result.get('ecoregion_percentages'):
            percentages = ecoregion_result['ecoregion_percentages']
            total = sum(percentages.values())
            print(f"   Total percentage: {total:.2f}% (should be ~100%)")
            for eco, pct in percentages.items():
                print(f"   - {eco}: {pct}%")
        else:
            print("   WARNING: No ecoregion data returned!")

        # Test 3: NASA Forest 2020
        print("\n3. Testing NASA Forest 2020 Analysis...")
        nasa_result = analyze_nasa_forest_2020_geometry(wkt, db)
        print(f"   Result: {nasa_result}")

        if nasa_result.get('nasa_forest_2020_percentages'):
            percentages = nasa_result['nasa_forest_2020_percentages']
            total = sum(percentages.values())
            print(f"   Total percentage: {total:.2f}% (should be ~100%)")
            print(f"   Dominant class: {nasa_result.get('nasa_forest_2020_dominant')}")
            for forest_type, pct in percentages.items():
                print(f"   - {forest_type}: {pct}%")
        else:
            print("   WARNING: No NASA forest 2020 data returned!")

        print("\n" + "=" * 80)
        print("Test completed successfully!")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_new_analysis()
