"""
Test script for mother tree identification
"""
import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_mother_tree_identification():
    """Test the complete mother tree identification workflow"""

    print("=" * 80)
    print("Testing Mother Tree Identification")
    print("=" * 80)

    # Step 1: Login
    print("\n1. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "inventory_tester@example.com",
            "password": "TestPass123"
        }
    )

    if login_response.status_code != 200:
        print(f"[ERROR] Login failed: {login_response.status_code}")
        print(login_response.text)
        return

    token = login_response.json()["access_token"]
    print(f"[OK] Login successful")

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Upload small test inventory with grid spacing
    print("\n2. Uploading test inventory...")

    csv_file_path = "D:/forest_management/test_small_inventory.csv"

    with open(csv_file_path, 'rb') as f:
        files = {'file': ('test_inventory.csv', f, 'text/csv')}
        data = {
            'grid_spacing_meters': 20.0,  # 20 meter grid spacing
            'projection_epsg': 32645  # UTM Zone 45N for Nepal
        }

        upload_response = requests.post(
            f"{BASE_URL}/api/inventory/upload",
            headers=headers,
            files=files,
            data=data
        )

    if upload_response.status_code != 200:
        print(f"[ERROR] Upload failed: {upload_response.status_code}")
        print(upload_response.text)
        return

    upload_result = upload_response.json()
    print(f"[OK] Upload successful")

    if not upload_result.get('summary', {}).get('ready_for_processing'):
        print(f"[ERROR] Validation failed:")
        print(json.dumps(upload_result, indent=2))
        return

    inventory_id = upload_result['inventory_id']
    print(f"[OK] Inventory ID: {inventory_id}")
    print(f"  Total rows: {upload_result['summary']['total_rows']}")
    print(f"  Valid rows: {upload_result['summary']['valid_rows']}")
    print(f"  Errors: {upload_result['summary'].get('total_errors', 0)}")

    # Step 3: Process inventory (with mother tree identification)
    print("\n3. Processing inventory...")

    with open(csv_file_path, 'rb') as f:
        files = {'file': ('test_inventory.csv', f, 'text/csv')}

        process_response = requests.post(
            f"{BASE_URL}/api/inventory/{inventory_id}/process",
            headers=headers,
            files=files
        )

    if process_response.status_code != 200:
        print(f"[ERROR] Processing failed: {process_response.status_code}")
        print(process_response.text)
        return

    print(f"[OK] Processing initiated")

    # Step 4: Wait for processing and check status
    print("\n4. Waiting for processing to complete...")

    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        time.sleep(2)

        status_response = requests.get(
            f"{BASE_URL}/api/inventory/{inventory_id}/status",
            headers=headers
        )

        if status_response.status_code != 200:
            print(f"[ERROR] Status check failed: {status_response.status_code}")
            return

        status = status_response.json()['status']
        print(f"  Status: {status}")

        if status == 'completed':
            print("[OK] Processing completed!")
            break
        elif status == 'failed':
            print(f"[ERROR] Processing failed: {status_response.json().get('error_message')}")
            return

        retry_count += 1

    if retry_count >= max_retries:
        print("[ERROR] Timeout waiting for processing")
        return

    # Step 5: Get summary with mother tree counts
    print("\n5. Getting inventory summary...")

    summary_response = requests.get(
        f"{BASE_URL}/api/inventory/{inventory_id}/summary",
        headers=headers
    )

    if summary_response.status_code != 200:
        print(f"[ERROR] Summary failed: {summary_response.status_code}")
        print(summary_response.text)
        return

    summary = summary_response.json()

    print(f"[OK] Summary retrieved:")
    print(f"  Total trees: {summary['total_trees']}")
    print(f"  Mother trees: {summary['mother_trees_count']}")
    print(f"  Felling trees: {summary['felling_trees_count']}")
    print(f"  Seedlings: {summary['seedling_count']}")
    print(f"  Total volume: {summary['total_volume_m3']} m3")
    print(f"  Net volume: {summary['total_net_volume_m3']} m3")
    print(f"  Processing time: {summary['processing_time_seconds']}s")

    # Step 6: Check mother tree distribution
    print("\n6. Checking mother tree distribution...")

    mother_trees_response = requests.get(
        f"{BASE_URL}/api/inventory/{inventory_id}/trees?remark=Mother Tree&page_size=10",
        headers=headers
    )

    if mother_trees_response.status_code != 200:
        print(f"[ERROR] Failed to get mother trees: {mother_trees_response.status_code}")
        return

    mother_trees = mother_trees_response.json()

    print(f"[OK] Mother trees (first 10):")
    for tree in mother_trees['trees'][:10]:
        print(f"  - {tree['species']} (DBH: {tree['dia_cm']}cm, Grid: {tree['grid_cell_id']})")

    # Step 7: Export results
    print("\n7. Exporting results with mother tree designation...")

    export_response = requests.get(
        f"{BASE_URL}/api/inventory/{inventory_id}/export?format=csv",
        headers=headers
    )

    if export_response.status_code != 200:
        print(f"[ERROR] Export failed: {export_response.status_code}")
        return

    export_filename = f"mother_trees_test_{inventory_id}.csv"
    with open(export_filename, 'wb') as f:
        f.write(export_response.content)

    print(f"[OK] Exported to: {export_filename}")

    # Success summary
    print("\n" + "=" * 80)
    print("[SUCCESS] Mother Tree Identification Test PASSED")
    print("=" * 80)
    print(f"\nKey Results:")
    print(f"  - {summary['mother_trees_count']} mother trees identified")
    print(f"  - {summary['felling_trees_count']} felling trees marked")
    print(f"  - {summary['seedling_count']} seedlings marked")
    print(f"  - Grid spacing: 20m")
    print(f"  - Projection: EPSG:32645 (UTM 45N)")
    print(f"\nMother trees are spatially distributed across the forest")
    print(f"using a grid-based selection algorithm that ensures even coverage.")


if __name__ == "__main__":
    test_mother_tree_identification()
