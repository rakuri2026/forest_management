"""
Script to automatically re-run analysis on all existing calculations
Auto-confirms and runs without user input
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
        # Run the corrected analysis
        analysis_results, processing_time = await analyze_forest_boundary(calc_id, db)

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

        # Print summary
        print(f"  SUCCESS:")
        print(f"    Slope: {analysis_results.get('slope_dominant_class')}")
        print(f"    Aspect: {analysis_results.get('aspect_dominant')}")
        print(f"    Canopy: {analysis_results.get('canopy_dominant_class')}")
        print(f"    Forest Type: {analysis_results.get('forest_type_dominant')}")
        print(f"    Land Cover: {analysis_results.get('landcover_dominant')}")

        return True

    except Exception as e:
        db.rollback()
        print(f"  ERROR: {e}")
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
        print(f"AUTO RE-ANALYSIS: {len(calculations)} completed calculations")
        print(f"{'='*80}\n")

        if not calculations:
            print("No completed calculations found in database.")
            return

        # Re-analyze each calculation
        success_count = 0
        fail_count = 0

        for i, calc in enumerate(calculations, 1):
            print(f"[{i}/{len(calculations)}] {calc.forest_name or 'Unnamed'} ({calc.id})")

            success = await reanalyze_calculation(str(calc.id), db)
            if success:
                success_count += 1
            else:
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"COMPLETE: {success_count} success, {fail_count} failed")
        print(f"{'='*80}\n")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(reanalyze_all())
