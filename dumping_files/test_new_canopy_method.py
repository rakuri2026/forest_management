"""
Test the new canopy analysis method with pixel center points
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Test with Dunetar block using the new pixel center method
    query = text("""
        WITH dunetar_geom AS (
            SELECT
                jsonb_array_elements(result_data->'blocks')->'geometry' as geom_json,
                jsonb_array_elements(result_data->'blocks')->>'block_name' as block_name
            FROM public.calculations
            WHERE forest_name = 'testForest'
        ),
        boundary AS (
            SELECT
                ST_GeomFromGeoJSON(geom_json::text) as geom,
                block_name
            FROM dunetar_geom
            WHERE block_name = 'Dunetar'
        ),
        all_pixels AS (
            SELECT
                (pix).val as height,
                (pix).geom as pixel_center
            FROM (
                SELECT ST_PixelAsPolygons(rast) as pix
                FROM rasters.canopy_height, boundary
                WHERE ST_Intersects(rast, geom)
            ) as subq
        )
        SELECT
            CASE
                WHEN height = 0 THEN 'non_forest'
                WHEN height > 0 AND height <= 5 THEN 'bush_regenerated'
                WHEN height > 5 AND height <= 15 THEN 'pole_trees'
                WHEN height > 15 THEN 'high_forest'
            END as canopy_class,
            COUNT(*) as pixel_count,
            AVG(height) as avg_height
        FROM all_pixels, boundary
        WHERE ST_Contains(boundary.geom, ST_Centroid(pixel_center))
          AND height IS NOT NULL
          AND height >= 0
          AND height <= 50
        GROUP BY canopy_class
        ORDER BY pixel_count DESC
    """)

    results = db.execute(query).fetchall()

    if results:
        total_pixels = sum(r.pixel_count for r in results)

        print("=" * 80)
        print("Dunetar Block - NEW Pixel Center Method")
        print("=" * 80)
        print(f"Total pixels: {total_pixels}")
        print()

        zero_pixels = 0
        for r in results:
            pct = (r.pixel_count / total_pixels) * 100
            print(f"{r.canopy_class}: {r.pixel_count} pixels ({pct:.1f}%) - avg height: {r.avg_height:.1f}m")

            if r.canopy_class == 'non_forest':
                zero_pixels = r.pixel_count

        print()
        print("=" * 80)
        print("Comparison")
        print("=" * 80)
        print(f"QGIS Analysis:      ~1,500 pixels, 180 with 0m (12% non-forest)")
        print(f"Old PostGIS Method:  2,119 pixels, 1,020 with 0m (48% non-forest)")
        print(f"NEW PostGIS Method:  {total_pixels} pixels, {zero_pixels} with 0m ({(zero_pixels/total_pixels)*100:.1f}% non-forest)")
        print()

        improvement = ((2119 - total_pixels) / 2119) * 100
        print(f"Pixel count reduced by {2119 - total_pixels} pixels ({improvement:.1f}%)")

        if abs(total_pixels - 1500) < abs(2119 - 1500):
            print("SUCCESS: New method is closer to QGIS!")
        else:
            print("ISSUE: New method is still far from QGIS")

    else:
        print("No results found")

finally:
    db.close()
