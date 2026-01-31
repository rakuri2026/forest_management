"""
Fix: Add geology, access, and features data to blocks
The previous script had transaction errors when processing blocks
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.calculation import Calculation
from app.services.analysis import analyze_geology_geometry, calculate_access_info, analyze_nearby_features
import json

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def update_blocks(calculation_id: str = None):
    """
    Update geology, access, and features for blocks only
    """
    db = SessionLocal()

    try:
        if calculation_id:
            calculations = db.query(Calculation).filter(Calculation.id == calculation_id).all()
        else:
            calculations = db.query(Calculation).filter(Calculation.status == 'completed').all()

        print(f"Found {len(calculations)} calculation(s) to update")

        for calc in calculations:
            print(f"\nProcessing {calc.forest_name or calc.id}...")

            result_data = calc.result_data or {}
            blocks = result_data.get('blocks', [])

            if not blocks:
                print("  No blocks found")
                continue

            print(f"  Processing {len(blocks)} blocks...")
            updated = False

            for i, block in enumerate(blocks):
                if 'geometry' not in block:
                    print(f"    Block {i+1}: No geometry")
                    continue

                try:
                    # Create a fresh session for each block to avoid transaction errors
                    block_db = SessionLocal()

                    # Convert GeoJSON to WKT
                    geojson_str = json.dumps(block['geometry'])
                    block_wkt_query = text("""
                        SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson)) as wkt
                    """)
                    block_wkt_result = block_db.execute(block_wkt_query, {"geojson": geojson_str}).first()

                    if not block_wkt_result:
                        print(f"    Block {i+1}: Could not convert geometry")
                        block_db.close()
                        continue

                    block_wkt = block_wkt_result.wkt

                    # Analyze geology
                    block_geology = analyze_geology_geometry(block_wkt, block_db)
                    blocks[i]['geology_percentages'] = block_geology.get('geology_percentages')

                    # Analyze access
                    block_access = calculate_access_info(block_wkt, block_db)
                    blocks[i]['access_info'] = block_access.get('access_info')

                    # Analyze nearby features
                    block_features = analyze_nearby_features(block_wkt, block_db)
                    blocks[i]['features_north'] = block_features.get('features_north')
                    blocks[i]['features_east'] = block_features.get('features_east')
                    blocks[i]['features_south'] = block_features.get('features_south')
                    blocks[i]['features_west'] = block_features.get('features_west')

                    print(f"    Block {i+1}: SUCCESS")
                    updated = True

                    block_db.close()

                except Exception as block_error:
                    print(f"    Block {i+1}: ERROR - {block_error}")
                    try:
                        block_db.close()
                    except:
                        pass
                    continue

            if updated:
                # Save updated blocks
                result_data['blocks'] = blocks
                calc.result_data = result_data
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(calc, "result_data")
                db.commit()
                print("  SAVED!")
            else:
                print("  No updates made")

        print(f"\nCompleted! Processed {len(calculations)} calculations")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        update_blocks(sys.argv[1])
    else:
        print("Updating blocks for all completed calculations...")
        update_blocks()
