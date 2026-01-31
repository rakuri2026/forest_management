"""
Add geology, access, and nearby features data to existing calculations
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

def update_calculations(calculation_id: str = None):
    """
    Update geology, access, and features for one or all calculations
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

            # Get whole forest geometry
            wkt_query = text("""
                SELECT ST_AsText(boundary_geom) as wkt
                FROM public.calculations
                WHERE id = :calc_id
            """)
            result = db.execute(wkt_query, {"calc_id": str(calc.id)}).first()

            if not result:
                continue

            whole_wkt = result.wkt

            # Update whole forest data
            print("  Analyzing whole forest...")
            geology_data = analyze_geology_geometry(whole_wkt, db)
            access_data = calculate_access_info(whole_wkt, db)
            features_data = analyze_nearby_features(whole_wkt, db)

            result_data = calc.result_data or {}
            result_data['whole_geology_percentages'] = geology_data.get('geology_percentages')
            result_data['whole_access_info'] = access_data.get('access_info')
            result_data['whole_features_north'] = features_data.get('features_north')
            result_data['whole_features_east'] = features_data.get('features_east')
            result_data['whole_features_south'] = features_data.get('features_south')
            result_data['whole_features_west'] = features_data.get('features_west')

            print(f"    Geology: {len(geology_data.get('geology_percentages') or {})} classes")
            print(f"    Access: {access_data.get('access_info')}")
            print(f"    Features: N={bool(features_data.get('features_north'))}, E={bool(features_data.get('features_east'))}, S={bool(features_data.get('features_south'))}, W={bool(features_data.get('features_west'))}")

            # Update blocks
            blocks = result_data.get('blocks', [])
            if blocks:
                print(f"  Analyzing {len(blocks)} blocks...")
                for i, block in enumerate(blocks):
                    if 'geometry' in block:
                        try:
                            geojson_str = json.dumps(block['geometry'])
                            block_wkt_query = text("""
                                SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson)) as wkt
                            """)
                            block_wkt_result = db.execute(block_wkt_query, {"geojson": geojson_str}).first()

                            if block_wkt_result:
                                block_geology = analyze_geology_geometry(block_wkt_result.wkt, db)
                                block_access = calculate_access_info(block_wkt_result.wkt, db)
                                block_features = analyze_nearby_features(block_wkt_result.wkt, db)

                                blocks[i]['geology_percentages'] = block_geology.get('geology_percentages')
                                blocks[i]['access_info'] = block_access.get('access_info')
                                blocks[i]['features_north'] = block_features.get('features_north')
                                blocks[i]['features_east'] = block_features.get('features_east')
                                blocks[i]['features_south'] = block_features.get('features_south')
                                blocks[i]['features_west'] = block_features.get('features_west')
                        except Exception as block_error:
                            print(f"    Block {i+1} error: {block_error}")
                            db.rollback()
                            continue

                result_data['blocks'] = blocks

            # Save
            calc.result_data = result_data
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(calc, "result_data")
            db.commit()

            print("  SUCCESS!")

        print(f"\nCompleted! Updated {len(calculations)} calculations")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        update_calculations(sys.argv[1])
    else:
        print("Updating all completed calculations...")
        update_calculations()
