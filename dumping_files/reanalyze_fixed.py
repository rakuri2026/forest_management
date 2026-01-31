"""
Re-run analysis with fixed error handling
"""
import asyncio
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.analysis import analyze_forest_boundary
from app.models.calculation import Calculation
from sqlalchemy import text
import json


async def reanalyze_all():
    """Re-run analysis on all completed calculations"""

    # Get all completed calculations
    db = SessionLocal()
    try:
        calculations = db.query(Calculation).filter(
            Calculation.status == "COMPLETED"
        ).order_by(Calculation.created_at.desc()).all()

        print(f"\n{'='*80}")
        print(f"RE-ANALYZING {len(calculations)} calculations")
        print(f"{'='*80}\n")

        success = 0
        failed = 0

        for i, calc in enumerate(calculations, 1):
            # Use NEW database session for each calculation
            db_new = SessionLocal()

            try:
                print(f"[{i}/{len(calculations)}] {calc.forest_name or 'Unnamed'}... ", end='', flush=True)

                # Run analysis
                analysis_results, processing_time = await analyze_forest_boundary(str(calc.id), db_new)

                # Update database
                update_query = text("""
                    UPDATE public.calculations
                    SET
                        result_data = CAST(:analysis_data AS jsonb),
                        processing_time_seconds = :processing_time,
                        status = 'COMPLETED',
                        completed_at = NOW()
                    WHERE id = :calc_id
                """)

                db_new.execute(update_query, {
                    "analysis_data": json.dumps(analysis_results),
                    "processing_time": processing_time,
                    "calc_id": str(calc.id)
                })

                db_new.commit()
                print(f"OK ({processing_time}s)")
                success += 1

            except Exception as e:
                db_new.rollback()
                print(f"FAILED: {str(e)[:60]}")
                failed += 1

            finally:
                db_new.close()

        print(f"\n{'='*80}")
        print(f"SUCCESS: {success}/{len(calculations)}")
        print(f"FAILED: {failed}/{len(calculations)}")
        print(f"{'='*80}\n")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(reanalyze_all())
