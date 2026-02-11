"""
Trigger re-analysis to add temperature and precipitation data
"""
import sys
import json
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import (
    analyze_temperature_geometry,
    analyze_precipitation_geometry
)

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Re-analyzing for Temperature and Precipitation")
print("=" * 70)

# Get the most recent calculation
query = text("""
    SELECT id, forest_name, ST_AsText(boundary_geom) as wkt, result_data
    FROM calculations
    WHERE boundary_geom IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
""")
calc = db.execute(query).first()

if calc:
    print(f"\nCalculation ID: {calc.id}")
    print(f"Forest Name: {calc.forest_name}")

    # Run temperature analysis on whole forest
    print("\n1. Running Temperature analysis (whole forest)...")
    result_temp = analyze_temperature_geometry(calc.wkt, db)
    print(f"   Mean: {result_temp.get('temperature_mean_c')}°C")
    print(f"   Min: {result_temp.get('temperature_min_c')}°C")

    # Run precipitation analysis on whole forest
    print("\n2. Running Precipitation analysis (whole forest)...")
    result_precip = analyze_precipitation_geometry(calc.wkt, db)
    print(f"   Annual: {result_precip.get('precipitation_mean_mm')} mm/year")

    # Update whole forest result_data
    print("\n3. Updating whole forest result_data...")
    result_data = calc.result_data or {}
    result_data['temperature_mean_c'] = result_temp.get('temperature_mean_c')
    result_data['temperature_min_c'] = result_temp.get('temperature_min_c')
    result_data['precipitation_mean_mm'] = result_precip.get('precipitation_mean_mm')

    # Also update all blocks
    print("\n4. Updating blocks...")
    blocks = result_data.get('blocks', [])
    if blocks:
        print(f"   Found {len(blocks)} blocks")
        for i, block in enumerate(blocks):
            if 'geometry' in block:
                # Convert GeoJSON to WKT
                from shapely.geometry import shape
                from shapely import wkt as shapely_wkt

                try:
                    geom = shape(block['geometry'])
                    block_wkt = shapely_wkt.dumps(geom)

                    # Run analyses for this block
                    block_temp = analyze_temperature_geometry(block_wkt, db)
                    block_precip = analyze_precipitation_geometry(block_wkt, db)

                    # Update block data
                    block['temperature_mean_c'] = block_temp.get('temperature_mean_c')
                    block['temperature_min_c'] = block_temp.get('temperature_min_c')
                    block['precipitation_mean_mm'] = block_precip.get('precipitation_mean_mm')

                    print(f"   Block {i+1} ({block.get('block_name', 'Unknown')}): " +
                          f"Temp={block_temp.get('temperature_mean_c')}°C, " +
                          f"Precip={block_precip.get('precipitation_mean_mm')}mm")
                except Exception as e:
                    print(f"   Block {i+1}: ERROR - {e}")

        result_data['blocks'] = blocks

    # Save to database
    print("\n5. Saving to database...")
    update_query = text("""
        UPDATE calculations
        SET result_data = CAST(:result_data AS jsonb)
        WHERE id = :calc_id
    """)

    db.execute(update_query, {
        'calc_id': str(calc.id),
        'result_data': json.dumps(result_data)
    })
    db.commit()

    print("\n[OK] Update complete!")
    print("\n" + "=" * 70)
    print("UPDATED DATA")
    print("=" * 70)

    print(f"\nWhole Forest:")
    print(f"  Temperature mean: {result_temp.get('temperature_mean_c')}°C")
    print(f"  Temperature min: {result_temp.get('temperature_min_c')}°C")
    print(f"  Precipitation: {result_precip.get('precipitation_mean_mm')} mm/year")

    print(f"\nBlocks updated: {len(blocks)}")

    print("\n" + "=" * 70)
    print("You can now refresh the frontend to see the updated data!")
    print("=" * 70)

else:
    print("No calculations found in database")

db.close()
