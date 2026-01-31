"""
Test API response directly
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from app.core.database import SessionLocal
from app.models.calculation import Calculation
from sqlalchemy import func
import json

# Get a calculation directly from database
db = SessionLocal()
try:
    calc_id = 'd32a8c45-f841-4ddc-a1ef-9a094026b8b3'

    calculation = db.query(Calculation).filter(Calculation.id == calc_id).first()

    if calculation:
        print("Calculation found:")
        print(f"  ID: {calculation.id}")
        print(f"  Forest Name: {calculation.forest_name}")
        print(f"  Status: {calculation.status}")
        print(f"\nResult Data type: {type(calculation.result_data)}")
        print(f"Result Data is None: {calculation.result_data is None}")

        if calculation.result_data:
            print(f"\nKeys in result_data: {list(calculation.result_data.keys())[:10]}")
            print(f"\nSlope dominant class: {calculation.result_data.get('slope_dominant_class')}")
            print(f"Aspect dominant: {calculation.result_data.get('aspect_dominant')}")
            print(f"Forest type: {calculation.result_data.get('forest_type_dominant')}")
            print(f"Land cover: {calculation.result_data.get('landcover_dominant')}")
            print(f"Number of blocks: {len(calculation.result_data.get('blocks', []))}")
        else:
            print("\nERROR: result_data is None or empty!")
    else:
        print(f"Calculation {calc_id} not found!")

finally:
    db.close()
