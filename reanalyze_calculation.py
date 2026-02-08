"""
Script to re-run analysis for an existing calculation to update proximity features
Usage: python reanalyze_calculation.py <calculation_id>
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.services.analysis import analyze_block_geometry

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reanalyze_calculation(calculation_id: str):
    """Re-run analysis for a specific calculation"""
    from uuid import UUID
    from sqlalchemy import text as sql_text
    db = SessionLocal()

    # Convert string to UUID
    calc_uuid = UUID(calculation_id)

    try:
        # Get calculation
        query = sql_text("""
            SELECT
                id,
                forest_name,
                block_name,
                ST_AsText(boundary_geom) as wkt,
                result_data
            FROM public.calculations
            WHERE id = :calc_id
        """)

        result = db.execute(query, {"calc_id": calculation_id}).first()

        if not result:
            print(f"ERROR: Calculation {calculation_id} not found")
            return False

        print(f"\n=== Re-analyzing Calculation ===")
        print(f"ID: {result.id}")
        print(f"Forest: {result.forest_name}")
        print(f"Block: {result.block_name}")

        # Get existing blocks from result_data
        result_data = result.result_data or {}
        blocks = result_data.get('blocks', [])

        if not blocks:
            print("WARNING: No blocks found in result_data, analyzing whole forest only")
            blocks = [{'wkt': result.wkt, 'block_name': result.block_name or 'Block 1'}]

        print(f"Found {len(blocks)} block(s) to re-analyze\n")

        # Re-analyze each block
        updated_blocks = []
        for i, block in enumerate(blocks, 1):
            print(f"Re-analyzing Block {i}/{len(blocks)}: {block.get('block_name', 'Unknown')}")

            # Try to get geometry (GeoJSON format preferred, fallback to WKT)
            block_geom = block.get('geometry')
            block_wkt = block.get('wkt')

            if not block_geom and not block_wkt:
                print(f"  ERROR: Block {i} has no geometry, skipping")
                updated_blocks.append(block)
                continue

            # Run analysis
            try:
                import asyncio
                # analyze_block_geometry expects GeoJSON, not WKT
                if block_geom:
                    # Use existing GeoJSON geometry
                    new_block_data = asyncio.run(analyze_block_geometry(block_geom, calc_uuid, db))
                else:
                    # Convert WKT to GeoJSON first
                    geojson_query = sql_text("""
                        SELECT ST_AsGeoJSON(ST_GeomFromText(:wkt, 4326))::json as geojson
                    """)
                    geojson_result = db.execute(geojson_query, {"wkt": block_wkt}).first()
                    block_geom = geojson_result.geojson
                    new_block_data = asyncio.run(analyze_block_geometry(block_geom, calc_uuid, db))

                # Show proximity results
                print(f"  Features North: {new_block_data.get('features_north', 'None')[:100]}")
                print(f"  Features East:  {new_block_data.get('features_east', 'None')[:100]}")
                print(f"  Features South: {new_block_data.get('features_south', 'None')[:100]}")
                print(f"  Features West:  {new_block_data.get('features_west', 'None')[:100]}")

                updated_blocks.append(new_block_data)
                print(f"  ✓ Block {i} re-analyzed successfully\n")

            except Exception as e:
                print(f"  ERROR: Failed to analyze block {i}: {e}")
                updated_blocks.append(block)

        # Update result_data with new blocks
        result_data['blocks'] = updated_blocks

        # Also update whole forest features if available
        if result.wkt:
            print("Re-analyzing whole forest proximity...")
            from app.services.analysis import analyze_nearby_features

            try:
                whole_features = analyze_nearby_features(result.wkt, db)
                result_data['whole_features_north'] = whole_features.get('features_north')
                result_data['whole_features_east'] = whole_features.get('features_east')
                result_data['whole_features_south'] = whole_features.get('features_south')
                result_data['whole_features_west'] = whole_features.get('features_west')

                print(f"Whole Forest Features North: {whole_features.get('features_north', 'None')[:100]}")
                print(f"Whole Forest Features East:  {whole_features.get('features_east', 'None')[:100]}")
                print(f"Whole Forest Features South: {whole_features.get('features_south', 'None')[:100]}")
                print(f"Whole Forest Features West:  {whole_features.get('features_west', 'None')[:100]}")

            except Exception as e:
                print(f"WARNING: Failed to analyze whole forest: {e}")

        # Update database
        import json
        update_query = sql_text("""
            UPDATE public.calculations
            SET result_data = CAST(:result_data AS jsonb),
                status = 'COMPLETED'
            WHERE id = :calc_id
        """)

        db.execute(update_query, {
            "calc_id": calculation_id,
            "result_data": json.dumps(result_data)
        })
        db.commit()

        print("\n✓ Calculation re-analyzed and updated successfully!")
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reanalyze_calculation.py <calculation_id>")
        print("\nTo get calculation IDs, run:")
        print("  psql -U postgres -d cf_db -c \"SELECT id, forest_name FROM calculations WHERE status='COMPLETED' LIMIT 5;\"")
        sys.exit(1)

    calc_id = sys.argv[1]
    success = reanalyze_calculation(calc_id)
    sys.exit(0 if success else 1)
