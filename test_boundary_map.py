"""
Test script for real boundary map generation.

Fetches a calculation from the database and generates its boundary map.
"""

import sys
from pathlib import Path
import asyncio

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from app.services.map_generator import MapGenerator
from app.core.database import SessionLocal
from app.models.calculation import Calculation
from sqlalchemy import select


async def test_boundary_map_generation():
    """Generate boundary map from real database data."""
    print("="*60)
    print("Real Boundary Map Generation Test")
    print("="*60)

    # Create database session
    print("\n1. Connecting to database...")
    db = SessionLocal()

    try:
        # Fetch a calculation with geometry
        print("2. Fetching calculation with geometry...")
        stmt = select(Calculation).where(
            Calculation.boundary_geom.isnot(None),
            Calculation.status == 'completed'
        ).limit(1)
        result = db.execute(stmt)
        calculation = result.scalar_one_or_none()

        if not calculation:
            print("  [FAIL] No completed calculations with geometry found!")
            return

        print(f"  [OK] Found calculation: {calculation.forest_name}")
        print(f"       ID: {calculation.id}")
        print(f"       Status: {calculation.status.value}")
        print(f"       Uploaded: {calculation.created_at}")

        # Convert boundary_geom to GeoJSON
        from geoalchemy2.shape import to_shape
        from shapely.geometry import mapping

        if not calculation.boundary_geom:
            print("  [FAIL] Calculation has no geometry!")
            return

        # Convert to GeoJSON
        shape = to_shape(calculation.boundary_geom)
        geojson = mapping(shape)

        print(f"  [OK] Geometry type: {geojson.get('type', 'Unknown')}")

        # Initialize map generator
        print("\n3. Initializing MapGenerator...")
        generator = MapGenerator(dpi=300)
        print("  [OK] MapGenerator initialized")

        # Generate boundary map with auto-orientation
        print("\n4. Generating boundary map (auto-orientation)...")
        print("  - Processing geometry...")
        print("  - Detecting optimal orientation...")
        print("  - Creating figure...")
        print("  - Plotting boundary...")
        print("  - Adding OpenStreetMap basemap...")

        boundary_map = generator.generate_boundary_map(
            geometry=geojson,
            forest_name=calculation.forest_name or 'Community Forest',
            orientation='auto',  # Let it auto-detect based on extent
            output_path=f'testData/boundary_map_{calculation.id}.png'
        )

        print(f"  [OK] Boundary map generated with auto-orientation!")
        print(f"  [OK] Saved to: testData/boundary_map_{calculation.id}.png")

        print("\n" + "="*60)
        print("[SUCCESS] Boundary map with OSM basemap generated!")
        print("="*60)
        print(f"\nGenerated map for: {calculation.forest_name or 'Community Forest'}")
        print(f"  File: testData/boundary_map_{calculation.id}.png")
        print(f"  Orientation: Auto-detected based on extent proportions")
        print("\nMap features:")
        print("  - OpenStreetMap basemap for context")
        print("  - Green forest boundary with filled area")
        print("  - North arrow (top-right, outside map)")
        print("  - Scale bar (bottom-left, outside map)")
        print("  - Legend (bottom-right, outside map)")
        print("  - Clean coordinate grid")
        print("  - WGS84 coordinate system (EPSG:4326)")
        print("\nNext: Open the PNG file to verify the basemap integration!")

    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(test_boundary_map_generation())
