"""
Test the fixed canopy height analysis
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Test with EXCLUDING 0 values
    query = text("""
        WITH test_boundary AS (
            SELECT boundary_geom
            FROM public.calculations
            WHERE forest_name = 'test4'
            LIMIT 1
        )
        SELECT
            CASE
                WHEN (pvc).value > 0 AND (pvc).value <= 5 THEN 'bush_regenerated'
                WHEN (pvc).value > 5 AND (pvc).value <= 15 THEN 'pole_trees'
                WHEN (pvc).value > 15 THEN 'high_forest'
            END as canopy_class,
            SUM((pvc).count) as pixel_count,
            AVG((pvc).value) as avg_height
        FROM (
            SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
            FROM rasters.canopy_height, test_boundary
            WHERE ST_Intersects(rast, boundary_geom)
        ) as subquery
        WHERE (pvc).value IS NOT NULL
          AND (pvc).value > 0  -- EXCLUDE 0 as NoData
          AND (pvc).value <= 50
        GROUP BY canopy_class
        ORDER BY pixel_count DESC
    """)

    results = db.execute(query).fetchall()
    total_pixels = sum(r.pixel_count for r in results)

    print('=== Canopy Height Analysis (EXCLUDING 0 values) ===')
    print(f'Total forest pixels: {total_pixels}')
    print()

    for r in results:
        pct = (r.pixel_count / total_pixels) * 100
        print(f'{r.canopy_class}: {r.pixel_count} pixels ({pct:.1f}%) - avg height: {r.avg_height:.1f}m')

    print()

    # Calculate weighted mean
    total_weighted = sum(r.avg_height * r.pixel_count for r in results)
    mean_height = total_weighted / total_pixels
    print(f'Mean canopy height: {mean_height:.1f}m')

    # Find dominant class
    dominant = max(results, key=lambda x: x.pixel_count)
    print(f'Dominant class: {dominant.canopy_class}')

finally:
    db.close()
