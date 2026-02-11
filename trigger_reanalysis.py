"""
Trigger re-analysis of most recent calculation to add new whole forest analyses
"""
import sys
import asyncio
import json
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.app.services.analysis import analyze_landcover_1984_geometry, analyze_hansen2000_geometry

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Re-analyzing Most Recent Calculation")
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

    # Run the two new analyses on whole forest
    print("\n1. Running Landcover 1984 analysis...")
    result_1984 = analyze_landcover_1984_geometry(calc.wkt, db)
    print(f"   Dominant: {result_1984.get('landcover_1984_dominant')}")

    print("\n2. Running Hansen 2000 analysis...")
    result_hansen = analyze_hansen2000_geometry(calc.wkt, db)
    print(f"   Dominant: {result_hansen.get('hansen2000_dominant')}")

    # Update the calculation's result_data
    print("\n3. Updating calculation result_data...")
    result_data = calc.result_data or {}
    result_data['landcover_1984_dominant'] = result_1984.get('landcover_1984_dominant')
    result_data['landcover_1984_percentages'] = result_1984.get('landcover_1984_percentages')
    result_data['hansen2000_dominant'] = result_hansen.get('hansen2000_dominant')
    result_data['hansen2000_percentages'] = result_hansen.get('hansen2000_percentages')

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
    print("UPDATED WHOLE FOREST ANALYSIS")
    print("=" * 70)

    print(f"\nLandcover 1984:")
    print(f"  Dominant: {result_1984.get('landcover_1984_dominant')}")
    if result_1984.get('landcover_1984_percentages'):
        for cover, pct in list(result_1984['landcover_1984_percentages'].items())[:5]:
            print(f"    {cover}: {pct}%")

    print(f"\nHansen 2000:")
    print(f"  Dominant: {result_hansen.get('hansen2000_dominant')}")
    if result_hansen.get('hansen2000_percentages'):
        for forest_class, pct in result_hansen['hansen2000_percentages'].items():
            print(f"    {forest_class}: {pct}%")

    print("\n" + "=" * 70)
    print("You can now refresh the frontend to see the updated data!")
    print("=" * 70)

else:
    print("No calculations found in database")

db.close()
