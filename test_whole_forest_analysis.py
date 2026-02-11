"""
Test whole forest analysis for landcover_1984 and hansen2000
"""
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from uuid import UUID

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=" * 70)
print("Testing Whole Forest Analysis Integration")
print("=" * 70)

# Get the most recent calculation
query = text("""
    SELECT id, forest_name, result_data
    FROM calculations
    WHERE boundary_geom IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
""")
calc = db.execute(query).first()

if calc:
    print(f"\nCalculation ID: {calc.id}")
    print(f"Forest Name: {calc.forest_name}")

    result_data = calc.result_data or {}

    print("\n" + "=" * 70)
    print("WHOLE FOREST ANALYSIS RESULTS")
    print("=" * 70)

    # Check landcover_1984
    print("\n1. Land Cover (1984) - Historical Baseline:")
    print("-" * 70)
    if 'landcover_1984_dominant' in result_data:
        print(f"  Dominant: {result_data.get('landcover_1984_dominant')}")
        if 'landcover_1984_percentages' in result_data:
            print(f"  Distribution:")
            for cover, pct in list(result_data['landcover_1984_percentages'].items())[:5]:
                print(f"    {cover}: {pct}%")
    else:
        print("  [NOT FOUND] - Need to re-run analysis")

    # Check hansen2000
    print("\n2. Forest Status (2000) - Hansen Classification:")
    print("-" * 70)
    if 'hansen2000_dominant' in result_data:
        print(f"  Dominant: {result_data.get('hansen2000_dominant')}")
        if 'hansen2000_percentages' in result_data:
            print(f"  Distribution:")
            for forest_class, pct in result_data['hansen2000_percentages'].items():
                print(f"    {forest_class}: {pct}%")
    else:
        print("  [NOT FOUND] - Need to re-run analysis")

    # Check current landcover for comparison
    print("\n3. Land Cover (Current) - ESA WorldCover:")
    print("-" * 70)
    if 'landcover_dominant' in result_data:
        print(f"  Dominant: {result_data.get('landcover_dominant')}")
        if 'landcover_percentages' in result_data:
            print(f"  Distribution:")
            for cover, pct in list(result_data['landcover_percentages'].items())[:5]:
                print(f"    {cover}: {pct}%")
    else:
        print("  [NOT FOUND]")

    # Check blocks
    print("\n" + "=" * 70)
    print("BLOCK ANALYSIS RESULTS")
    print("=" * 70)
    blocks = result_data.get('blocks', [])
    if blocks:
        print(f"\nTotal blocks: {len(blocks)}")
        print(f"\nChecking first block for new analyses:")
        print("-" * 70)
        first_block = blocks[0]
        print(f"Block name: {first_block.get('block_name', 'Unknown')}")

        if 'landcover_1984_dominant' in first_block:
            print(f"  Landcover 1984: {first_block.get('landcover_1984_dominant')}")
        else:
            print(f"  Landcover 1984: [NOT FOUND]")

        if 'hansen2000_dominant' in first_block:
            print(f"  Hansen 2000: {first_block.get('hansen2000_dominant')}")
        else:
            print(f"  Hansen 2000: [NOT FOUND]")
    else:
        print("  No blocks found")

else:
    print("No calculations found in database")

print("\n" + "=" * 70)
print("Test Complete!")
print("=" * 70)
print("\nNOTE: If analyses are NOT FOUND, you need to upload a new file")
print("      to trigger the analysis with the updated code.")

db.close()
