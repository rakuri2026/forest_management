"""
Diagnose canopy height analysis for a specific calculation
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text

print("Enter the forest name or calculation ID to diagnose:")
identifier = input().strip()

db = SessionLocal()
try:
    # Get the calculation
    if len(identifier) == 36 and '-' in identifier:
        # It's a UUID
        query = text("""
            SELECT id, forest_name, created_at
            FROM public.calculations
            WHERE id = :identifier::uuid
        """)
    else:
        # It's a forest name
        query = text("""
            SELECT id, forest_name, created_at
            FROM public.calculations
            WHERE forest_name = :identifier
            ORDER BY created_at DESC
            LIMIT 1
        """)

    calc = db.execute(query, {"identifier": identifier}).first()

    if not calc:
        print(f"No calculation found for: {identifier}")
        sys.exit(1)

    print(f"\n=== Analyzing: {calc.forest_name} ===")
    print(f"ID: {calc.id}")
    print(f"Created: {calc.created_at}")
    print()

    # Get detailed canopy analysis
    query2 = text("""
        WITH calc_boundary AS (
            SELECT boundary_geom
            FROM public.calculations
            WHERE id = :calc_id::uuid
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
        print("No canopy data found for this boundary!")
        sys.exit(1)

    total_pixels = sum(r.pixel_count for r in results)

    print(f"Total pixels analyzed: {total_pixels}")
    print()
    print("Top 20 canopy height values:")
    print("-" * 60)

    non_forest_pixels = 0
    bush_pixels = 0
    pole_pixels = 0
    high_pixels = 0

    for r in results:
        height = r.height
        count = r.pixel_count
        pct = (count / total_pixels) * 100

        print(f"Height {height:5.1f}m: {count:6d} pixels ({pct:5.1f}%)")

        if height == 0:
            non_forest_pixels = count
        elif height <= 5:
            bush_pixels += count
        elif height <= 15:
            pole_pixels += count
        else:
            high_pixels += count

    print("-" * 60)
    print()
    print("=== Classification Summary ===")
    print(f"Non-forest (0m):    {non_forest_pixels:6d} pixels ({(non_forest_pixels/total_pixels)*100:5.1f}%)")
    print(f"Bush/Shrub (1-5m):  {bush_pixels:6d} pixels ({(bush_pixels/total_pixels)*100:5.1f}%)")
    print(f"Pole (6-15m):       {pole_pixels:6d} pixels ({(pole_pixels/total_pixels)*100:5.1f}%)")
    print(f"High forest (>15m): {high_pixels:6d} pixels ({(high_pixels/total_pixels)*100:5.1f}%)")
    print()

    if non_forest_pixels / total_pixels > 0.5:
        print("WARNING: More than 50% non-forest!")
        print("This boundary may include:")
        print("  - Agricultural land")
        print("  - Clearings or open areas")
        print("  - Water bodies")
        print("  - Roads or settlements")
        print()
        print("Recommendation: Verify the boundary extent in QGIS")

finally:
    db.close()
