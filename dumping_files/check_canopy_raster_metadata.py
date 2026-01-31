"""
Check canopy_height raster metadata
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    query = text("""
        SELECT
            ST_BandNoDataValue(rast, 1) as nodata,
            ST_BandPixelType(rast, 1) as pixel_type,
            ST_Width(rast) as width,
            ST_Height(rast) as height,
            ST_ScaleX(rast) as scale_x,
            ST_ScaleY(rast) as scale_y,
            ST_SRID(rast) as srid
        FROM rasters.canopy_height
        LIMIT 1
    """)

    result = db.execute(query).first()

    if result:
        print("=" * 80)
        print("Canopy Height Raster Metadata")
        print("=" * 80)
        print(f"NoData Value: {result.nodata}")
        print(f"Pixel Type: {result.pixel_type}")
        print(f"Dimensions: {result.width} x {result.height}")
        print(f"Scale X: {result.scale_x}")
        print(f"Scale Y: {result.scale_y}")
        print(f"SRID: {result.srid}")
        print()

        # Check actual value range
        query2 = text("""
            SELECT
                MIN((ST_SummaryStats(rast)).min) as global_min,
                MAX((ST_SummaryStats(rast)).max) as global_max,
                AVG((ST_SummaryStats(rast)).mean) as global_mean
            FROM rasters.canopy_height
            LIMIT 10
        """)

        result2 = db.execute(query2).first()

        if result2:
            print("Value Range (from sample tiles):")
            print(f"  Min: {result2.global_min}")
            print(f"  Max: {result2.global_max}")
            print(f"  Mean: {result2.global_mean}")
            print()

        # Check 0 value distribution
        query3 = text("""
            SELECT
                COUNT(*) as tile_count,
                SUM((pvc).count) FILTER (WHERE (pvc).value = 0) as zero_pixels,
                SUM((pvc).count) as total_pixels
            FROM (
                SELECT ST_ValueCount(rast) as pvc
                FROM rasters.canopy_height
                LIMIT 100
            ) as subquery
        """)

        result3 = db.execute(query3).first()

        if result3:
            print(f"Sample Analysis (100 tiles):")
            print(f"  Total pixels: {result3.total_pixels}")
            print(f"  Zero (0m) pixels: {result3.zero_pixels}")
            if result3.total_pixels:
                pct = (result3.zero_pixels / result3.total_pixels) * 100
                print(f"  Percentage 0m: {pct:.1f}%")

    else:
        print("No canopy_height raster found")

finally:
    db.close()
