"""
Re-analyze testForest with the new canopy analysis method
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from app.services.analysis import analyze_canopy_height_geometry
from sqlalchemy import text
import json

db = SessionLocal()
try:
    # Get testForest calculation
    query = text("""
        SELECT
            id,
            forest_name,
            result_data
        FROM public.calculations
        WHERE forest_name = 'testForest'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    calc = db.execute(query).first()

    if not calc:
        print("No testForest calculation found")
        sys.exit(1)

    print(f"Re-analyzing: {calc.forest_name}")
    print(f"ID: {calc.id}")
    print()

    result_data = calc.result_data
    blocks = result_data.get('blocks', [])

    print(f"Found {len(blocks)} blocks")
    print()

    # Re-analyze each block
    for i, block in enumerate(blocks, 1):
        block_name = block.get('block_name', f'Block {i}')
        geometry = block.get('geometry')

        if not geometry:
            print(f"Block {block_name}: No geometry found")
            continue

        # Convert GeoJSON to WKT
        from shapely.geometry import shape
        from shapely import wkt as shapely_wkt

        geom = shape(geometry)
        wkt = shapely_wkt.dumps(geom)

        print(f"Analyzing block: {block_name}")

        # Run new canopy analysis
        canopy_result = analyze_canopy_height_geometry(wkt, db)

        print(f"  Canopy result: {canopy_result}")
        print()

        # Update block with new results
        block['canopy_mean_m'] = canopy_result.get('canopy_mean_m')
        block['canopy_dominant_class'] = canopy_result.get('canopy_dominant_class')
        block['canopy_percentages'] = canopy_result.get('canopy_percentages', {})

    # Update database
    update_query = text("""
        UPDATE public.calculations
        SET result_data = :result_data
        WHERE id = :calc_id
    """)

    db.execute(update_query, {
        "calc_id": str(calc.id),
        "result_data": json.dumps(result_data)
    })
    db.commit()

    print("=" * 80)
    print("SUCCESS: testForest re-analyzed with new canopy method")
    print("=" * 80)

finally:
    db.close()
