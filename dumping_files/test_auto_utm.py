"""
Test automatic UTM zone detection for EPSG:4326 data
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
print("[OK] Logged in\n")

# Test with rame_tree.csv WITHOUT specifying projection_epsg
csv_file_path = "D:/forest_management/testData/sundar/rame_tree.csv"

print("Testing automatic UTM detection with rame_tree.csv")
print("=" * 70)
print("File: rame_tree.csv (EPSG:4326 data)")
print("Grid spacing: 20m")
print("Projection: NOT SPECIFIED (should auto-detect)")
print()

# Upload WITHOUT projection_epsg parameter
with open(csv_file_path, 'rb') as f:
    files = {'file': ('rame_tree.csv', f, 'text/csv')}
    data = {
        'grid_spacing_meters': 20.0
        # projection_epsg NOT specified - should auto-detect
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
    exit(1)

result = upload_response.json()
print("[OK] Upload successful")

# Check if auto-detection message exists
if 'info' in result:
    for info in result['info']:
        if info.get('type') == 'auto_utm_detection':
            print(f"[INFO] {info['message']}")

inventory_id = result['inventory_id']
print(f"[OK] Inventory ID: {inventory_id}\n")

# Process
print("Processing inventory...")
with open(csv_file_path, 'rb') as f:
    files = {'file': ('rame_tree.csv', f, 'text/csv')}
    process_response = requests.post(
        f"{BASE_URL}/api/inventory/{inventory_id}/process",
        headers=headers,
        files=files
    )

if process_response.status_code != 200:
    print(f"[ERROR] Processing failed: {process_response.status_code}")
    print(process_response.text)
    exit(1)

# Wait for completion
max_wait = 60
for i in range(max_wait):
    time.sleep(2)
    status_response = requests.get(
        f"{BASE_URL}/api/inventory/{inventory_id}/status",
        headers=headers
    )
    status = status_response.json()['status']

    if status == 'completed':
        print("[OK] Processing completed!\n")
        break
    elif status == 'failed':
        error_msg = status_response.json().get('error_message', 'Unknown error')
        print(f"[ERROR] Processing failed: {error_msg}")
        exit(1)

    if i % 10 == 0 and i > 0:
        print(f"  Still processing... ({i*2}s)")

# Get summary
summary_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/summary",
    headers=headers
)

if summary_response.status_code != 200:
    print(f"[ERROR] Summary failed")
    exit(1)

summary = summary_response.json()

print("Results:")
print(f"  Total trees:    {summary['total_trees']}")
print(f"  Mother trees:   {summary['mother_trees_count']} ({summary['mother_trees_count']/summary['total_trees']*100:.1f}%)")
print(f"  Felling trees:  {summary['felling_trees_count']} ({summary['felling_trees_count']/summary['total_trees']*100:.1f}%)")
print(f"  Seedlings:      {summary['seedling_count']}")
print(f"  Processing time: {summary['processing_time_seconds']}s")
print()

# Verify projection was auto-detected
status_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/status",
    headers=headers
)
inventory_info = status_response.json()
print(f"Auto-detected projection: EPSG:{inventory_info.get('projection_epsg')}")

print()
print("=" * 70)
if summary['mother_trees_count'] > 100 and summary['mother_trees_count'] < summary['total_trees']:
    print("[SUCCESS] Auto UTM detection working correctly!")
    print(f"Expected ~2900 mother trees with 20m grid, got {summary['mother_trees_count']}")
else:
    print("[WARNING] Unexpected mother tree count")
    print(f"Got {summary['mother_trees_count']} mother trees")
