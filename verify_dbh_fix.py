"""
Verify DBH threshold fix in the most recent tree model Excel export.
Run this after generating a new tree model to confirm the fix is working.
"""
import pandas as pd
import glob
import os
from pathlib import Path

def find_latest_excel():
    """Find the most recent tree model Excel file."""
    pattern = r"D:\forest_management\backend\exports\tree_model_*.xlsx"
    files = glob.glob(pattern)
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    return latest

def verify_dbh_thresholds(excel_path):
    """Verify DBH thresholds are correct."""
    print(f"\n{'='*70}")
    print(f"VERIFYING DBH THRESHOLDS")
    print(f"{'='*70}\n")
    print(f"File: {Path(excel_path).name}")
    print(f"Modified: {pd.Timestamp.fromtimestamp(os.path.getmtime(excel_path))}\n")

    try:
        df = pd.read_excel(excel_path, sheet_name='Tree Model')

        results = []
        all_passed = True

        # Check regen_dbh column (should be 1.0 to 3.9)
        regen_dbh = df['regen_dbh'].dropna()
        if len(regen_dbh) > 0:
            min_val = regen_dbh.min()
            max_val = regen_dbh.max()
            passed = (min_val >= 1.0 and max_val <= 3.9)
            all_passed = all_passed and passed

            status = "✓ PASS" if passed else "✗ FAIL"
            results.append({
                'Column': 'regen_dbh',
                'Expected Range': '1.0 - 3.9',
                'Actual Range': f'{min_val} - {max_val}',
                'Count': len(regen_dbh),
                'Status': status
            })

        # Check sapling_dbh_cm column (should be 4.0 to 9.9)
        sapling_dbh = df['sapling_dbh_cm'].dropna()
        if len(sapling_dbh) > 0:
            min_val = sapling_dbh.min()
            max_val = sapling_dbh.max()
            passed = (min_val >= 4.0 and max_val <= 9.9)
            all_passed = all_passed and passed

            status = "✓ PASS" if passed else "✗ FAIL"
            results.append({
                'Column': 'sapling_dbh_cm',
                'Expected Range': '4.0 - 9.9',
                'Actual Range': f'{min_val} - {max_val}',
                'Count': len(sapling_dbh),
                'Status': status
            })

        # Check pole_dbh_cm column (should be 10.0 to 29.9)
        pole_dbh = df['pole_dbh_cm'].dropna()
        if len(pole_dbh) > 0:
            min_val = pole_dbh.min()
            max_val = pole_dbh.max()
            passed = (min_val >= 10.0 and max_val <= 29.9)
            all_passed = all_passed and passed

            status = "✓ PASS" if passed else "✗ FAIL"
            results.append({
                'Column': 'pole_dbh_cm',
                'Expected Range': '10.0 - 29.9',
                'Actual Range': f'{min_val} - {max_val}',
                'Count': len(pole_dbh),
                'Status': status
            })

        # Check tree_dbh_cm column (should be >= 30.0)
        tree_dbh = df['tree_dbh_cm'].dropna()
        if len(tree_dbh) > 0:
            min_val = tree_dbh.min()
            max_val = tree_dbh.max()
            passed = (min_val >= 30.0)
            all_passed = all_passed and passed

            status = "✓ PASS" if passed else "✗ FAIL"
            results.append({
                'Column': 'tree_dbh_cm',
                'Expected Range': '>= 30.0',
                'Actual Range': f'{min_val} - {max_val}',
                'Count': len(tree_dbh),
                'Status': status
            })

        # Print results table
        result_df = pd.DataFrame(results)
        print(result_df.to_string(index=False))
        print(f"\n{'-'*70}")

        if all_passed:
            print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
            print("DBH thresholds are correctly implemented.\n")
        else:
            print("\n✗✗✗ SOME TESTS FAILED! ✗✗✗")
            print("Backend may not have loaded the new code.")
            print("Try restarting the backend again.\n")

        print(f"{'='*70}\n")
        return all_passed

    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    latest_file = find_latest_excel()

    if not latest_file:
        print("\n✗ No tree model Excel files found in backend/exports/")
        print("Generate a tree model first, then run this script.\n")
    else:
        verify_dbh_thresholds(latest_file)
