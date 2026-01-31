"""
Test the fixed DEM analysis
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from app.core.database import SessionLocal
from app.services.analysis import analyze_dem_geometry
from sqlalchemy import text

def test_dem_fix():
    db = SessionLocal()
    try:
        # Get a test geometry from sundar.kml (test4 calculation)
        query = text("""
            SELECT ST_AsText(boundary_geom) as wkt
            FROM public.calculations
            WHERE forest_name = 'test4'
            LIMIT 1
        """)

        result = db.execute(query).first()
        if not result:
            print('No test4 calculation found')
            return

        print('Testing DEM analysis with fixed NoData handling...')
        print()

        dem_result = analyze_dem_geometry(result.wkt, db)

        print('=== DEM Analysis Result ===')
        print(f"Min elevation: {dem_result.get('elevation_min_m')}m")
        print(f"Max elevation: {dem_result.get('elevation_max_m')}m")
        print(f"Mean elevation: {dem_result.get('elevation_mean_m')}m")
        print()

        if dem_result.get('elevation_mean_m'):
            mean = dem_result['elevation_mean_m']
            if 60 <= mean <= 8850:
                print(f'SUCCESS! Elevation {mean}m is within valid range for Nepal')
            else:
                print(f'WARNING: Elevation {mean}m is outside Nepal typical range')
        else:
            print('FAILED: No elevation data returned')

    finally:
        db.close()

if __name__ == "__main__":
    test_dem_fix()
