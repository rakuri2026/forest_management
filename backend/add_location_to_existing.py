"""
Script to add location data to existing calculations
Run this to populate location fields for records that were analyzed before the feature was added
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.calculation import Calculation
from app.services.analysis import get_administrative_location
import json

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def update_calculation_locations(calculation_id: str = None):
    """
    Update location data for one or all calculations

    Args:
        calculation_id: Optional UUID of specific calculation. If None, updates all.
    """
    db = SessionLocal()

    try:
        # Get calculations to update
        if calculation_id:
            calculations = db.query(Calculation).filter(Calculation.id == calculation_id).all()
        else:
            calculations = db.query(Calculation).filter(Calculation.status == 'completed').all()

        print(f"Found {len(calculations)} calculation(s) to update")

        for calc in calculations:
            print(f"\nProcessing calculation {calc.id}...")
            print(f"  Forest: {calc.forest_name or 'Unknown'}")

            # Get the boundary geometry as WKT
            wkt_query = text("""
                SELECT ST_AsText(boundary_geom) as wkt
                FROM public.calculations
                WHERE id = :calc_id
            """)
            result = db.execute(wkt_query, {"calc_id": str(calc.id)}).first()

            if not result or not result.wkt:
                print(f"  ERROR: No geometry found")
                continue

            whole_wkt = result.wkt

            # Get whole forest location
            print(f"  Getting whole forest location...")
            whole_location = get_administrative_location(whole_wkt, db)

            print(f"    Province: {whole_location.get('province')}")
            print(f"    District: {whole_location.get('district')}")
            print(f"    Municipality: {whole_location.get('municipality')}")
            print(f"    Ward: {whole_location.get('ward')}")
            print(f"    Watershed: {whole_location.get('watershed')}")

            # Update result_data
            result_data = calc.result_data or {}
            result_data['whole_province'] = whole_location.get('province')
            result_data['whole_district'] = whole_location.get('district')
            result_data['whole_municipality'] = whole_location.get('municipality')
            result_data['whole_ward'] = whole_location.get('ward')
            result_data['whole_watershed'] = whole_location.get('watershed')
            result_data['whole_major_river_basin'] = whole_location.get('major_river_basin')

            # Update block locations if there are blocks
            blocks = result_data.get('blocks', [])
            if blocks:
                print(f"  Updating {len(blocks)} block(s)...")
                for i, block in enumerate(blocks):
                    if 'geometry' in block:
                        # Convert block GeoJSON to WKT
                        geojson_str = json.dumps(block['geometry'])
                        block_wkt_query = text("""
                            SELECT ST_AsText(ST_GeomFromGeoJSON(:geojson)) as wkt
                        """)
                        block_wkt_result = db.execute(block_wkt_query, {"geojson": geojson_str}).first()

                        if block_wkt_result:
                            block_location = get_administrative_location(block_wkt_result.wkt, db)
                            blocks[i]['province'] = block_location.get('province')
                            blocks[i]['district'] = block_location.get('district')
                            blocks[i]['municipality'] = block_location.get('municipality')
                            blocks[i]['ward'] = block_location.get('ward')
                            blocks[i]['watershed'] = block_location.get('watershed')
                            blocks[i]['major_river_basin'] = block_location.get('major_river_basin')
                            print(f"    Block {i+1}: {block_location.get('municipality')}, Ward {block_location.get('ward')}")

                result_data['blocks'] = blocks

            # Save to database
            calc.result_data = result_data
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(calc, "result_data")
            db.commit()

            print(f"  SUCCESS: Location data updated")

        print(f"\n\nCompleted! Updated {len(calculations)} calculation(s)")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Update specific calculation
        calc_id = sys.argv[1]
        print(f"Updating calculation {calc_id}...")
        update_calculation_locations(calc_id)
    else:
        # Update all calculations
        print("Updating all completed calculations...")
        print("(Pass a calculation ID as argument to update just one)")
        update_calculation_locations()
