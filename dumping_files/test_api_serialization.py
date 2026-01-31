"""
Test what the API actually returns
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from app.core.database import SessionLocal
from app.models.calculation import Calculation
from app.schemas.forest import CalculationResponse
from sqlalchemy import func
import json

db = SessionLocal()
try:
    calc_id = 'e771aa41-7bcf-48d8-b1ec-d1a06e17df41'

    calculation = db.query(Calculation).filter(Calculation.id == calc_id).first()

    if calculation:
        # Simulate what the API endpoint does
        geojson_query = db.query(
            func.ST_AsGeoJSON(Calculation.boundary_geom).label("geojson")
        ).filter(Calculation.id == calc_id).first()

        geometry_json = json.loads(geojson_query.geojson) if geojson_query else None

        # Create the response object like the API does
        response = CalculationResponse(
            id=calculation.id,
            user_id=calculation.user_id,
            uploaded_filename=calculation.uploaded_filename,
            forest_name=calculation.forest_name,
            block_name=calculation.block_name,
            status=calculation.status,
            processing_time_seconds=calculation.processing_time_seconds,
            error_message=calculation.error_message,
            created_at=calculation.created_at,
            completed_at=calculation.completed_at,
            geometry=geometry_json,
            result_data=calculation.result_data
        )

        # Convert to dict like FastAPI would
        response_dict = response.model_dump()

        print("=== API RESPONSE ===")
        print(f"result_data type: {type(response_dict.get('result_data'))}")
        print(f"Has result_data: {response_dict.get('result_data') is not None}")

        if response_dict.get('result_data'):
            rd = response_dict['result_data']
            print(f"\nTop-level keys (first 10): {list(rd.keys())[:10]}")
            print(f"\nslope_dominant_class: {rd.get('slope_dominant_class')}")
            print(f"aspect_dominant: {rd.get('aspect_dominant')}")
            print(f"forest_type_dominant: {rd.get('forest_type_dominant')}")

            blocks = rd.get('blocks', [])
            print(f"\nNumber of blocks: {len(blocks)}")
            if blocks:
                print(f"\nFirst block keys: {list(blocks[0].keys())[:10]}")
                print(f"First block slope: {blocks[0].get('slope_dominant_class')}")
                print(f"First block aspect: {blocks[0].get('aspect_dominant')}")
                print(f"First block area_hectares: {blocks[0].get('area_hectares')}")
        else:
            print("\nERROR: result_data is None!")

finally:
    db.close()
