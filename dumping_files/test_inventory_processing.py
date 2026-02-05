"""
Test inventory processing workflow
"""
import requests
import json

BASE_URL = "http://localhost:8001"

# Use existing validated inventory
inventory_id = "98ef1ca7-b6d2-4a27-92b6-bbb453b8cdf5"

# Login first to get token
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "newuser@example.com", "password": "SecurePass123"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print(f"Token: {token[:50]}...")
print()

# Check inventory status before processing
print("=== Checking inventory status BEFORE processing ===")
status_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/status",
    headers=headers
)
print(f"Status: {status_response.status_code}")
if status_response.status_code == 200:
    data = status_response.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Total trees: {data.get('total_trees')}")
    print(f"  Total volume: {data.get('total_volume_m3')}")
print()

# Process inventory (need to re-upload file)
print("=== Processing inventory ===")
print("NOTE: We need to re-upload the CSV file for processing")
print("File path: D:/forest_management/testData/sundar/fortyThaousand80.csv")

# Read the file
with open(r"D:\forest_management\testData\sundar\fortyThaousand80.csv", "rb") as f:
    files = {"file": ("fortyThaousand80.csv", f, "text/csv")}

    process_response = requests.post(
        f"{BASE_URL}/api/inventory/{inventory_id}/process",
        headers=headers,
        files=files
    )

print(f"Process Status: {process_response.status_code}")
print(f"Response: {json.dumps(process_response.json(), indent=2)}")
print()

# Check inventory status after processing
print("=== Checking inventory status AFTER processing ===")
status_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/status",
    headers=headers
)
print(f"Status: {status_response.status_code}")
if status_response.status_code == 200:
    data = status_response.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Total trees: {data.get('total_trees')}")
    print(f"  Total volume: {data.get('total_volume_m3')} m³")
    print(f"  Seedlings: {data.get('seedling_count')}")
    print(f"  Felling trees: {data.get('felling_trees_count')}")
print()

# Try to get summary
print("=== Getting inventory summary ===")
summary_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/summary",
    headers=headers
)
print(f"Summary Status: {summary_response.status_code}")
if summary_response.status_code == 200:
    print(json.dumps(summary_response.json(), indent=2))
print()

# Try to export
print("=== Exporting inventory ===")
export_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/export?format=csv",
    headers=headers
)
print(f"Export Status: {export_response.status_code}")
if export_response.status_code == 200:
    print(f"Content length: {len(export_response.content)} bytes")
    # Save to file
    with open("exported_inventory.csv", "wb") as f:
        f.write(export_response.content)
    print("Saved to: exported_inventory.csv")
else:
    print(f"Export failed: {export_response.text}")
