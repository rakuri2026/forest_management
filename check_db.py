"""Check latest upload in database"""
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = 'postgresql://postgres:admin123@localhost:5432/cf_db'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

query = text("""
    SELECT
        forest_name,
        status,
        created_at,
        result_data
    FROM public.calculations
    ORDER BY created_at DESC
    LIMIT 1
""")

result = db.execute(query).first()

if result:
    print(f"Forest: {result.forest_name}")
    print(f"Status: {result.status}")
    print(f"Created: {result.created_at}")
    print("\nBlock 1 Features:")

    if result.result_data and 'blocks' in result.result_data:
        block1 = result.result_data['blocks'][0]
        print(f"  Block Name: {block1.get('block_name', 'N/A')}")
        print(f"  Features North: {block1.get('features_north', 'MISSING')}")
        print(f"  Features East: {block1.get('features_east', 'MISSING')}")
        print(f"  Features South: {block1.get('features_south', 'MISSING')}")
        print(f"  Features West: {block1.get('features_west', 'MISSING')}")
    else:
        print("  No blocks data found")
else:
    print("No calculations found")

db.close()
