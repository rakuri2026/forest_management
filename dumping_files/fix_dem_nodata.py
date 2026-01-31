"""
Fix DEM raster NoData value

The DEM raster doesn't have a NoData value registered in PostGIS,
causing -32768 values to be treated as actual elevations.

This script sets the NoData value to -32768 for all DEM tiles.
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from app.core.database import SessionLocal
from sqlalchemy import text

def fix_dem_nodata():
    db = SessionLocal()
    try:
        print("Checking current DEM NoData configuration...")

        # Check current state
        check_query = text("""
            SELECT
                ST_BandNoDataValue(rast, 1) as nodata_value,
                COUNT(*) as tile_count
            FROM rasters.dem
            GROUP BY ST_BandNoDataValue(rast, 1)
        """)

        results = db.execute(check_query).fetchall()
        print(f"\nCurrent NoData values in DEM tiles:")
        for r in results:
            print(f"  NoData={r.nodata_value}: {r.tile_count} tiles")

        # Count total tiles
        count_query = text("SELECT COUNT(*) as total FROM rasters.dem")
        total = db.execute(count_query).first().total
        print(f"\nTotal DEM tiles: {total}")

        # Set NoData value to -32768 for all tiles
        print("\nSetting NoData value to -32768 for all tiles...")
        print("This may take a few minutes...")

        update_query = text("""
            UPDATE rasters.dem
            SET rast = ST_SetBandNoDataValue(rast, 1, -32768)
        """)

        db.execute(update_query)
        db.commit()

        print("✓ NoData value updated successfully!")

        # Verify the change
        print("\nVerifying update...")
        results = db.execute(check_query).fetchall()
        print(f"New NoData values in DEM tiles:")
        for r in results:
            print(f"  NoData={r.nodata_value}: {r.tile_count} tiles")

        # Test with sample statistics
        print("\nTesting with sample tile...")
        test_query = text("""
            SELECT
                (stats).min as min_val,
                (stats).max as max_val,
                (stats).mean as mean_val
            FROM (
                SELECT ST_SummaryStats(rast, 1, true) as stats
                FROM rasters.dem
                WHERE ST_Intersects(rast, ST_MakeEnvelope(80, 26, 88, 31, 4326))
                LIMIT 1
            ) as subquery
        """)

        result = db.execute(test_query).first()
        if result:
            print(f"  Min elevation: {result.min_val}m")
            print(f"  Max elevation: {result.max_val}m")
            print(f"  Mean elevation: {result.mean_val}m")

            if result.min_val and result.min_val >= 0 and result.max_val and result.max_val <= 9000:
                print("\n✓ SUCCESS: Elevation values are now within valid range for Nepal!")
            else:
                print("\n⚠ WARNING: Elevation values still look suspicious")

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("FIX DEM RASTER NODATA VALUE")
    print("=" * 60)
    print()
    print("This script will set the NoData value for the DEM raster")
    print("to -32768, which is the standard for 16-bit signed integer DEMs.")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        fix_dem_nodata()
    else:
        print("Cancelled.")
