"""
Check Sundar calculation data structure
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')
from app.core.database import SessionLocal
from sqlalchemy import text
import json

db = SessionLocal()
try:
    # Get the Sundar calculation
    query = text("""
        SELECT
            id,
            forest_name,
            created_at,
            result_data
        FROM public.calculations
        WHERE forest_name LIKE '%Sundar%'
        ORDER BY created_at DESC
        LIMIT 1
    """)

    result = db.execute(query).first()

    if result:
        print(f"Forest: {result.forest_name}")
        print(f"Created: {result.created_at}")
        print()
        print("Top-level keys in result_data:")
        for key in result.result_data.keys():
            if key not in ['blocks', 'processing_info']:
                value = result.result_data[key]
                if isinstance(value, dict):
                    print(f"  {key}: {json.dumps(value)[:100]}...")
                else:
                    print(f"  {key}: {value}")
        print()
        print(f"Number of blocks: {len(result.result_data.get('blocks', []))}")

        # Check if area_hectares exists
        if 'area_hectares' in result.result_data:
            print(f"area_hectares: {result.result_data['area_hectares']}")
        else:
            print("WARNING: area_hectares not found in result_data!")

    else:
        print("No Sundar calculation found")

finally:
    db.close()
