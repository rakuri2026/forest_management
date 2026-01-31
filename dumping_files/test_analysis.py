"""
Test script to verify raster analysis functions work correctly
Run this after uploading a test boundary to verify all analysis functions
"""
import sys
import asyncio
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, '.')

from app.core.config import settings
from app.services.analysis import (
    analyze_dem,
    analyze_slope,
    analyze_aspect,
    analyze_canopy_height,
    analyze_agb,
    analyze_forest_health,
    analyze_forest_type,
    analyze_esa_worldcover,
    analyze_climate,
    analyze_forest_change,
    analyze_soil
)

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def test_all_analysis_functions(calculation_id: str):
    """Test all raster analysis functions with a real calculation ID"""

    db = SessionLocal()
    calc_uuid = UUID(calculation_id)

    print(f"\n{'='*80}")
    print(f"Testing Raster Analysis Functions")
    print(f"Calculation ID: {calculation_id}")
    print(f"{'='*80}\n")

    try:
        # Test 1: DEM Analysis
        print("1. Testing DEM (Elevation) Analysis...")
        dem_result = analyze_dem(calc_uuid, db)
        print(f"   ✓ Result: {dem_result}")

        # Test 2: Slope Analysis
        print("\n2. Testing Slope Analysis...")
        slope_result = analyze_slope(calc_uuid, db)
        print(f"   ✓ Result: {slope_result}")

        # Test 3: Aspect Analysis
        print("\n3. Testing Aspect Analysis...")
        aspect_result = analyze_aspect(calc_uuid, db)
        print(f"   ✓ Result: {aspect_result}")

        # Test 4: Canopy Height Analysis
        print("\n4. Testing Canopy Height Analysis...")
        canopy_result = analyze_canopy_height(calc_uuid, db)
        print(f"   ✓ Result: {canopy_result}")

        # Test 5: AGB Analysis
        print("\n5. Testing Above-Ground Biomass Analysis...")
        agb_result = analyze_agb(calc_uuid, db)
        print(f"   ✓ Result: {agb_result}")

        # Test 6: Forest Health Analysis
        print("\n6. Testing Forest Health Analysis...")
        health_result = analyze_forest_health(calc_uuid, db)
        print(f"   ✓ Result: {health_result}")

        # Test 7: Forest Type Analysis
        print("\n7. Testing Forest Type Analysis...")
        forest_type_result = analyze_forest_type(calc_uuid, db)
        print(f"   ✓ Result: {forest_type_result}")

        # Test 8: ESA WorldCover Analysis
        print("\n8. Testing ESA WorldCover Analysis...")
        esa_result = analyze_esa_worldcover(calc_uuid, db)
        print(f"   ✓ Result: {esa_result}")

        # Test 9: Climate Analysis
        print("\n9. Testing Climate Analysis...")
        climate_result = analyze_climate(calc_uuid, db)
        print(f"   ✓ Result: {climate_result}")

        # Test 10: Forest Change Analysis
        print("\n10. Testing Forest Change Analysis...")
        change_result = analyze_forest_change(calc_uuid, db)
        print(f"   ✓ Result: {change_result}")

        # Test 11: Soil Analysis
        print("\n11. Testing Soil Properties Analysis...")
        soil_result = analyze_soil(calc_uuid, db)
        print(f"   ✓ Result: {soil_result}")

        print(f"\n{'='*80}")
        print("All tests completed successfully!")
        print(f"{'='*80}\n")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def list_recent_calculations():
    """List recent calculations to find test IDs"""
    db = SessionLocal()

    try:
        from app.models.calculation import Calculation

        calculations = db.query(Calculation).order_by(
            Calculation.created_at.desc()
        ).limit(5).all()

        print("\nRecent Calculations:")
        print("-" * 80)
        for calc in calculations:
            print(f"ID: {calc.id}")
            print(f"  Forest: {calc.forest_name or 'N/A'}")
            print(f"  Status: {calc.status}")
            print(f"  Created: {calc.created_at}")
            print()

        if calculations:
            return str(calculations[0].id)

    except Exception as e:
        print(f"Error listing calculations: {e}")
    finally:
        db.close()

    return None


if __name__ == "__main__":
    # If calculation ID provided as argument, use it
    if len(sys.argv) > 1:
        calc_id = sys.argv[1]
        test_all_analysis_functions(calc_id)
    else:
        # Otherwise, find most recent calculation
        print("No calculation ID provided. Looking for recent calculations...")
        recent_id = list_recent_calculations()

        if recent_id:
            print(f"\nUsing most recent calculation: {recent_id}")
            response = input("Press Enter to test, or Ctrl+C to cancel...")
            test_all_analysis_functions(recent_id)
        else:
            print("\nNo calculations found in database.")
            print("\nUsage:")
            print("  python test_analysis.py <calculation_id>")
            print("\nExample:")
            print("  python test_analysis.py 12345678-1234-1234-1234-123456789abc")
