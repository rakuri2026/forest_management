"""
Check testForest canopy values
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Get testForest calculation
    query = text("""
        SELECT id, forest_name, created_at
        FROM public.calculations
        WHERE forest_name = 'testForest'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    calc = db.execute(query).first()

    if not calc:
        print('No testForest calculation found')
        sys.exit(1)

    print(f'=== Analyzing: {calc.forest_name} ===')
    print(f'ID: {calc.id}')
    print(f'Created: {calc.created_at}')
    print()

    # Get detailed canopy analysis using the ID
    query2 = text("""
        WITH calc_boundary AS (
            SELECT boundary_geom
            FROM public.calculations
            WHERE id = :calc_id
        )
        SELECT
            (pvc).value as height,
            SUM((pvc).count) as pixel_count
        FROM (
            SELECT ST_ValueCount(ST_Clip(rast, boundary_geom)) as pvc
            FROM rasters.canopy_height, calc_boundary
            WHERE ST_Intersects(rast, boundary_geom)
        ) as subquery
        WHERE (pvc).value IS NOT NULL
        GROUP BY height
        ORDER BY pixel_count DESC
        LIMIT 20
    """)

    results = db.execute(query2, {"calc_id": str(calc.id)}).fetchall()

    if not results:
        print('No canopy data found!')
        sys.exit(1)

    total_pixels = sum(r.pixel_count for r in results)

    print(f'Total pixels analyzed: {total_pixels}')
    print()
    print('Top 20 canopy height values:')
    print('-' * 60)

    non_forest = 0
    bush = 0
    pole = 0
    high = 0

    for r in results:
        h = r.height
        c = r.pixel_count
        pct = (c / total_pixels) * 100

        print(f'Height {h:5.1f}m: {c:6d} pixels ({pct:5.1f}%)')

        if h == 0:
            non_forest = c
        elif h <= 5:
            bush += c
        elif h <= 15:
            pole += c
        else:
            high += c

    print('-' * 60)
    print()
    print('=== Classification Summary ===')
    print(f'Non-forest (0m):    {non_forest:6d} pixels ({(non_forest/total_pixels)*100:5.1f}%)')
    print(f'Bush/Shrub (1-5m):  {bush:6d} pixels ({(bush/total_pixels)*100:5.1f}%)')
    print(f'Pole (6-15m):       {pole:6d} pixels ({(pole/total_pixels)*100:5.1f}%)')
    print(f'High forest (>15m): {high:6d} pixels ({(high/total_pixels)*100:5.1f}%)')

finally:
    db.close()
