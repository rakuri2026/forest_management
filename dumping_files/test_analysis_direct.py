"""
Test analysis functions directly to find the issue
"""
import sys
sys.path.insert(0, 'D:/forest_management/backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.analysis import analyze_forest_boundary
import asyncio

# Database connection
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/cf_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

async def test_analysis():
    """Test analysis on the stuck calculation"""
    db = SessionLocal()

    # Get the stuck calculation ID
    calc_id = "8f16f946-ad56-4946-89bf-80fdeae6b374"  # vvvvvv

    print(f"Testing analysis for calculation: {calc_id}")

    try:
        result, processing_time = await analyze_forest_boundary(calc_id, db)
        print(f"\n✓ Analysis completed successfully!")
        print(f"Processing time: {processing_time} seconds")
        print(f"Result keys: {list(result.keys())}")
        print(f"\nSample results:")
        for key in list(result.keys())[:5]:
            print(f"  {key}: {result[key]}")
    except Exception as e:
        print(f"\n✗ Analysis failed with error:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")
        import traceback
        print(f"\nFull traceback:")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Forest Boundary Analysis")
    print("=" * 60)
    asyncio.run(test_analysis())
