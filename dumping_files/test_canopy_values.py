"""
Test canopy height values distribution
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Get test4 boundary and check canopy values
    query = text("""
        WITH test_boundary AS (
            SELECT boundary_geom
            FROM public.calculations
            WHERE forest_name = 'test4'
            LIMIT 1
        )
        SELECT
            (pvc).value as height,
            SUM((pvc).count) as pixel_count
        FROM (
            SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
            FROM rasters.canopy_height, test_boundary
            WHERE ST_Intersects(rast, boundary_geom)
        ) as subquery
        WHERE (pvc).value IS NOT NULL
        GROUP BY height
        ORDER BY pixel_count DESC
        LIMIT 20
    """)

    results = db.execute(query).fetchall()
    total_pixels = sum(r.pixel_count for r in results)

    print('=== Canopy Height Distribution for test4 ===')
    print(f'Total pixels: {total_pixels}')
    print()

    non_forest = 0
    bush = 0
    pole = 0
    high = 0

    for r in results:
        height = r.height
        count = r.pixel_count
        pct = (count / total_pixels) * 100

        print(f'Height: {height:.1f}m -> {count} pixels ({pct:.1f}%)')

        if height == 0:
            non_forest += count
        elif height <= 5:
            bush += count
        elif height <= 15:
            pole += count
        else:
            high += count

    print()
    print('=== Classification Summary ===')
    print(f'Non-forest (0m): {non_forest} pixels ({(non_forest/total_pixels)*100:.1f}%)')
    print(f'Bush/Shrub (0-5m): {bush} pixels ({(bush/total_pixels)*100:.1f}%)')
    print(f'Pole forest (5-15m): {pole} pixels ({(pole/total_pixels)*100:.1f}%)')
    print(f'High forest (>15m): {high} pixels ({(high/total_pixels)*100:.1f}%)')

finally:
    db.close()
