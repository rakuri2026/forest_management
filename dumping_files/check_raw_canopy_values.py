"""
Check raw canopy pixel values for testForest blocks
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Get Dunetar block (should have 12% non-forest per QGIS)
    query = text("""
        WITH block_geom AS (
            SELECT
                jsonb_array_elements(result_data->'blocks')->'geometry' as geom_json,
                jsonb_array_elements(result_data->'blocks')->>'block_name' as block_name
            FROM public.calculations
            WHERE forest_name = 'testForest'
        ),
        block_polygon AS (
            SELECT
                ST_GeomFromGeoJSON(geom_json::text) as geom,
                block_name
            FROM block_geom
            WHERE block_name = 'Dunetar'
        )
        SELECT
            (pvc).value as height,
            SUM((pvc).count) as pixel_count
        FROM (
            SELECT ST_ValueCount(ST_Clip(rast, geom)) as pvc
            FROM rasters.canopy_height, block_polygon
            WHERE ST_Intersects(rast, geom)
        ) as subquery
        WHERE (pvc).value IS NOT NULL
        GROUP BY height
        ORDER BY pixel_count DESC
        LIMIT 20
    """)

    results = db.execute(query).fetchall()

    if results:
        total_pixels = sum(r.pixel_count for r in results)
        print(f"Dunetar Block - Top 20 canopy height values:")
        print(f"Total pixels: {total_pixels}")
        print()

        zero_pixels = 0
        forest_pixels = 0

        for r in results:
            h = r.height
            c = r.pixel_count
            pct = (c / total_pixels) * 100

            print(f"Height {h:5.1f}m: {c:6d} pixels ({pct:5.1f}%)")

            if h == 0:
                zero_pixels = c
            else:
                forest_pixels += c

        print()
        print(f"Zero (0m) pixels: {zero_pixels} ({(zero_pixels/total_pixels)*100:.1f}%)")
        print(f"Forest (>0m) pixels: {forest_pixels} ({(forest_pixels/total_pixels)*100:.1f}%)")
        print()
        print("QGIS says: 180 pixels with 0m (12%)")
        print(f"Our count: {zero_pixels} pixels with 0m ({(zero_pixels/total_pixels)*100:.1f}%)")
    else:
        print("No results found")

finally:
    db.close()
