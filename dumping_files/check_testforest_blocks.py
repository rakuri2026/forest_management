"""
Check testForest calculation blocks
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text
import json

db = SessionLocal()
try:
    query = text("""
        SELECT
            id,
            forest_name,
            result_data->'blocks' as blocks,
            ST_Area(boundary_geom::geography) / 10000 as area_hectares,
            ST_AsText(ST_Centroid(boundary_geom)) as centroid
        FROM public.calculations
        WHERE forest_name = 'testForest'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    result = db.execute(query).first()

    if result:
        print(f"Forest: {result.forest_name}")
        print(f"ID: {result.id}")
        print(f"Area: {result.area_hectares:.2f} hectares")
        print(f"Centroid: {result.centroid}")
        print()

        if result.blocks:
            blocks = result.blocks
            print(f"Number of blocks: {len(blocks)}")
            print()

            total_non_forest = 0
            total_count = 0

            for i, block in enumerate(blocks, 1):
                block_name = block.get("block_name", "Unnamed")
                print(f"Block {i}: {block_name}")

                # Get area
                area_ha = block.get("area_hectares", 0)
                print(f"  Area: {area_ha:.2f} ha")

                # Get canopy data
                if "canopy_percentages" in block:
                    canopy = block["canopy_percentages"]
                    non_forest = canopy.get("non_forest", 0)
                    bush = canopy.get("bush_regenerated", 0)
                    pole = canopy.get("pole_trees", 0)
                    high = canopy.get("high_forest", 0)

                    print(f"  Canopy Analysis:")
                    print(f"    Non-forest: {non_forest}%")
                    print(f"    Bush/Shrub: {bush}%")
                    print(f"    Pole: {pole}%")
                    print(f"    High: {high}%")

                    total_non_forest += non_forest
                    total_count += 1
                print()

            if total_count > 0:
                avg_non_forest = total_non_forest / total_count
                print(f"Average non-forest across blocks: {avg_non_forest:.1f}%")
        else:
            print("No blocks found in result_data")
    else:
        print("No testForest calculation found")

finally:
    db.close()
