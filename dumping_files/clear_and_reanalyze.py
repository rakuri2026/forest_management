"""
Clear old analysis results and run fresh analysis with corrected functions
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
        print(f"CLEARING AND RE-ANALYZING {len(calculations)} calculations")
        print(f"This will replace ALL old analysis with corrected results")
        print(f"{'='*80}\n")

        if not calculations:
            print("No completed calculations found in database.")
            return

        success_count = 0
        fail_count = 0

        for i, calc in enumerate(calculations, 1):
            print(f"\n[{i}/{len(calculations)}] Processing: {calc.forest_name or 'Unnamed'}")
            print(f"   ID: {calc.id}")

            try:
                # Run fresh analysis with corrected functions
                print(f"   Running corrected analysis...")
                analysis_results, processing_time = await analyze_forest_boundary(str(calc.id), db)

                # COMPLETELY REPLACE result_data (not merge)
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

                # Print key results
                print(f"   SUCCESS - Processing time: {processing_time}s")
                print(f"     Slope: {analysis_results.get('slope_dominant_class')} {analysis_results.get('slope_percentages', {})}")
                print(f"     Aspect: {analysis_results.get('aspect_dominant')} {analysis_results.get('aspect_percentages', {})}")
                print(f"     Forest Type: {analysis_results.get('forest_type_dominant')}")
                print(f"     Land Cover: {analysis_results.get('landcover_dominant')}")
                print(f"     Temperature: {analysis_results.get('temperature_mean_c')}°C")

                success_count += 1

            except Exception as e:
                db.rollback()
                print(f"   ERROR: {e}")
                fail_count += 1

        print(f"\n{'='*80}")
        print(f"RE-ANALYSIS COMPLETE")
        print(f"  ✓ Success: {success_count}/{len(calculations)}")
        print(f"  ✗ Failed: {fail_count}/{len(calculations)}")
        print(f"{'='*80}\n")

    finally:
        db.close()


if __name__ == "__main__":
    print("\nThis script will COMPLETELY REPLACE all existing analysis results.")
    print("Old data will be permanently removed and replaced with corrected analysis.\n")

    response = input("Continue? Type 'YES' to proceed: ")
    if response == "YES":
        asyncio.run(clear_and_reanalyze())
    else:
        print("Cancelled.")
