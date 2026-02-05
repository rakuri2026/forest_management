"""
Test mother tree identification with dense tree data (rame_tree.csv)
8000 trees in ~2.1km x 1.2km area
"""
import requests
import time

BASE_URL = "http://localhost:8001"

# Login
print("Logging in...")
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "inventory_tester@example.com", "password": "TestPass123"}
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("[OK] Logged in")

# Test with different grid spacings
grid_spacings = [10, 20, 30, 50]
csv_file_path = "D:/forest_management/testData/sundar/rame_tree.csv"

print(f"\nTesting with 8000 trees over ~2.1km x 1.2km area")
print("=" * 70)

for grid_size in grid_spacings:
    print(f"\n### Grid Spacing: {grid_size}m ###")

    # Upload
    with open(csv_file_path, 'rb') as f:
        files = {'file': ('rame_tree.csv', f, 'text/csv')}
        data = {
            'grid_spacing_meters': float(grid_size),
            'projection_epsg': 32645  # UTM 45N
        }
        upload_response = requests.post(
            f"{BASE_URL}/api/inventory/upload",
            headers=headers,
            files=files,
            data=data
        )

    if upload_response.status_code != 200:
        print(f"[ERROR] Upload failed: {upload_response.text}")
        continue

    inventory_id = upload_response.json()['inventory_id']
    print(f"Inventory ID: {inventory_id}")

    # Process
    with open(csv_file_path, 'rb') as f:
        files = {'file': ('rame_tree.csv', f, 'text/csv')}
        process_response = requests.post(
            f"{BASE_URL}/api/inventory/{inventory_id}/process",
            headers=headers,
            files=files
        )

    if process_response.status_code != 200:
        print(f"[ERROR] Processing failed: {process_response.text}")
        continue

    # Wait for completion
    print("Processing...", end='', flush=True)
    max_wait = 60
    for i in range(max_wait):
        time.sleep(2)
        status_response = requests.get(
            f"{BASE_URL}/api/inventory/{inventory_id}/status",
            headers=headers
        )
        status = status_response.json()['status']
        if status == 'completed':
            print(" [DONE]")
            break
        elif status == 'failed':
            print(f" [FAILED]: {status_response.json().get('error_message')}")
            break
        if i % 5 == 0:
            print(".", end='', flush=True)

    # Get summary
    summary_response = requests.get(
        f"{BASE_URL}/api/inventory/{inventory_id}/summary",
        headers=headers
    )

    if summary_response.status_code != 200:
        print(f"[ERROR] Summary failed")
        continue

    summary = summary_response.json()

    total = summary['total_trees']
    mothers = summary['mother_trees_count']
    felling = summary['felling_trees_count']
    seedlings = summary['seedling_count']

    print(f"Results:")
    print(f"  Total trees:    {total}")
    print(f"  Mother trees:   {mothers:4d} ({mothers/total*100:5.1f}%)")
    print(f"  Felling trees:  {felling:4d} ({felling/total*100:5.1f}%)")
    print(f"  Seedlings:      {seedlings:4d} ({seedlings/total*100:5.1f}%)")
    print(f"  Processing time: {summary['processing_time_seconds']}s")

    # Calculate expected grid size
    area_x, area_y = 2105, 1186
    expected_cells = (area_x // grid_size) * (area_y // grid_size)
    print(f"  Expected grid: {area_x // grid_size} x {area_y // grid_size} = {expected_cells} cells")
    print(f"  Avg trees per cell: {total / expected_cells:.2f}")

print("\n" + "=" * 70)
print("Summary: Denser grids (smaller spacing) = more felling trees")
print("         because multiple trees compete within each cell")
