"""
Clear old analysis results and run fresh analysis with corrected functions (AUTO-CONFIRM)
"""
import asyncio
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.analysis import analyze_forest_boundary
from app.models.calculation import Calculation
from sqlalchemy import text
import json


async def clear_and_reanalyze():
    """Clear all analysis results and re-run with corrected functions"""
    db = SessionLocal()

    try:
        # Get all completed calculations
        calculations = db.query(Calculation).filter(
            Calculation.status == "COMPLETED"
        ).order_by(Calculation.created_at.desc()).all()

        print(f"\n{'='*80}")
        print(f"AUTO RE-ANALYZING {len(calculations)} calculations")
        print(f"Replacing old analysis with corrected results")
        print(f"{'='*80}\n")

        if not calculations:
            print("No completed calculations found.")
            return

        success_count = 0
        fail_count = 0

        for i, calc in enumerate(calculations, 1):
            calc_name = calc.forest_name or 'Unnamed'
            print(f"[{i}/{len(calculations)}] {calc_name[:30]}")

            try:
                # Run corrected analysis
                analysis_results, processing_time = await analyze_forest_boundary(str(calc.id), db)

                # Replace result_data completely
                update_query = text("""
                    UPDATE public.calculations
                    SET
                        result_data = CAST(:analysis_data AS jsonb),
                        processing_time_seconds = :processing_time,
                        status = 'COMPLETED',
                        completed_at = NOW()
                    WHERE id = :calc_id
                """)

                db.execute(update_query, {
                    "analysis_data": json.dumps(analysis_results),
                    "processing_time": processing_time,
                    "calc_id": str(calc.id)
                })

                db.commit()

                # Print results
                slope = analysis_results.get('slope_dominant_class', 'N/A')
                aspect = analysis_results.get('aspect_dominant', 'N/A')
                print(f"  ✓ Slope: {slope}, Aspect: {aspect} ({processing_time}s)")

                success_count += 1

            except Exception as e:
                db.rollback()
                print(f"  ✗ ERROR: {str(e)[:50]}")
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"COMPLETE: {success_count} success, {fail_count} failed")
        print(f"{'='*80}\n")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(clear_and_reanalyze())
