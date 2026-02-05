"""
Test mother tree identification with smaller grid spacing (5m)
to demonstrate selection when multiple trees per cell
"""
import requests

BASE_URL = "http://localhost:8001"

# Login
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "inventory_tester@example.com", "password": "TestPass123"}
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Upload with 5m grid (much tighter)
csv_file_path = "D:/forest_management/test_small_inventory.csv"

with open(csv_file_path, 'rb') as f:
    files = {'file': ('test_inventory.csv', f, 'text/csv')}
    data = {
        'grid_spacing_meters': 5.0,  # 5 meter grid (vs 20m before)
        'projection_epsg': 32645
    }
    upload_response = requests.post(
        f"{BASE_URL}/api/inventory/upload",
        headers=headers,
        files=files,
        data=data
    )

inventory_id = upload_response.json()['inventory_id']
print(f"Inventory ID: {inventory_id}")
print(f"Grid spacing: 5m (vs 20m in previous test)")

# Process
with open(csv_file_path, 'rb') as f:
    files = {'file': ('test_inventory.csv', f, 'text/csv')}
    process_response = requests.post(
        f"{BASE_URL}/api/inventory/{inventory_id}/process",
        headers=headers,
        files=files
    )

# Get summary
import time
time.sleep(2)

summary_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/summary",
    headers=headers
)

summary = summary_response.json()
print(f"\nResults with 5m grid:")
print(f"  Total trees: {summary['total_trees']}")
print(f"  Mother trees: {summary['mother_trees_count']} ({summary['mother_trees_count']/summary['total_trees']*100:.1f}%)")
print(f"  Felling trees: {summary['felling_trees_count']} ({summary['felling_trees_count']/summary['total_trees']*100:.1f}%)")
print(f"\nWith tighter grid, more trees compete for mother tree status")
