"""
Script to re-run analysis on existing calculations with corrected raster analysis
This updates all calculations with the new categorical code-based analysis
"""
import asyncio
import sys
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.analysis import analyze_forest_boundary
from app.models.calculation import Calculation
from sqlalchemy import text
import json


async def reanalyze_calculation(calc_id: str, db: Session):
    """Re-analyze a single calculation with corrected analysis functions"""
    try:
        print(f"\nRe-analyzing calculation {calc_id}...")

        # Run the corrected analysis
        analysis_results, processing_time = await analyze_forest_boundary(calc_id, db)

        print(f"  Analysis completed in {processing_time}s")
        print(f"  Results contain {len(analysis_results)} top-level keys")

        # Update the calculation with new analysis results
        update_query = text("""
            UPDATE public.calculations
            SET
                result_data = CAST(:analysis_data AS jsonb),
                processing_time_seconds = :processing_time,
                status = :status,
                completed_at = NOW()
            WHERE id = :calc_id
        """)

        db.execute(update_query, {
            "analysis_data": json.dumps(analysis_results),
            "processing_time": processing_time,
            "status": "COMPLETED",
            "calc_id": calc_id
        })

        db.commit()

        # Print summary of new results
        print(f"  SUCCESS: Updated with corrected analysis")
        print(f"  Key metrics:")
        print(f"    - Slope: {analysis_results.get('slope_dominant_class')}")
        print(f"    - Aspect: {analysis_results.get('aspect_dominant')}")
        print(f"    - Canopy: {analysis_results.get('canopy_dominant_class')}")
        print(f"    - Forest Type: {analysis_results.get('forest_type_dominant')}")
        print(f"    - Land Cover: {analysis_results.get('landcover_dominant')}")
        print(f"    - Temperature: {analysis_results.get('temperature_mean_c')}°C")
        print(f"    - Precipitation: {analysis_results.get('precipitation_mean_mm')}mm")
        print(f"    - Forest Loss: {analysis_results.get('forest_loss_hectares')}ha")
        print(f"    - Soil Texture: {analysis_results.get('soil_texture')}")

        return True

    except Exception as e:
        db.rollback()
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def reanalyze_all():
    """Re-analyze all existing COMPLETED calculations"""
    db = SessionLocal()

    try:
        # Get all completed calculations
        calculations = db.query(Calculation).filter(
            Calculation.status == "COMPLETED"
        ).order_by(Calculation.created_at.desc()).all()

        print(f"\n{'='*80}")
        print(f"Re-analyzing {len(calculations)} completed calculations")
        print(f"This will update all calculations with corrected raster analysis")
        print(f"{'='*80}")

        if not calculations:
            print("\nNo completed calculations found in database.")
            return

        # Show list and ask for confirmation
        print("\nCalculations to re-analyze:")
        for i, calc in enumerate(calculations, 1):
            print(f"  {i}. {calc.id} - {calc.forest_name or 'N/A'} ({calc.created_at})")

        response = input(f"\nProceed with re-analysis of {len(calculations)} calculations? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

        # Re-analyze each calculation
        success_count = 0
        fail_count = 0

        for i, calc in enumerate(calculations, 1):
            print(f"\n[{i}/{len(calculations)}] Processing {calc.forest_name or 'Unnamed'}...")

            success = await reanalyze_calculation(str(calc.id), db)
            if success:
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"Re-analysis Complete")
        print(f"  Success: {success_count}/{len(calculations)}")
        print(f"  Failed: {fail_count}/{len(calculations)}")
        print(f"{'='*80}\n")

    finally:
        db.close()


async def reanalyze_single(calc_id: str):
    """Re-analyze a single calculation by ID"""
    db = SessionLocal()
    try:
        await reanalyze_calculation(calc_id, db)
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Re-analyze specific calculation
        calc_id = sys.argv[1]
        print(f"Re-analyzing single calculation: {calc_id}")
        asyncio.run(reanalyze_single(calc_id))
    else:
        # Re-analyze all calculations
        asyncio.run(reanalyze_all())
