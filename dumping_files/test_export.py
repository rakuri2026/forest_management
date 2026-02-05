"""
Test export functionality
"""
import requests

BASE_URL = "http://localhost:8001"
inventory_id = "26d11984-865b-4484-b59f-34ed3b0a8106"

# Login
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "newuser@example.com", "password": "SecurePass123"}
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print(f"=== Testing Export for Inventory {inventory_id} ===\n")

# Test CSV export
print("1. Testing CSV Export...")
export_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/export?format=csv",
    headers=headers
)

print(f"   Status: {export_response.status_code}")
if export_response.status_code == 200:
    print(f"   ✓ Success! File size: {len(export_response.content)} bytes")

    # Save file
    with open("test_export_result.csv", "wb") as f:
        f.write(export_response.content)
    print(f"   ✓ Saved to: test_export_result.csv")

    # Count lines
    lines = export_response.content.decode('utf-8').split('\n')
    print(f"   ✓ Total lines: {len(lines)} (should be 100: header + 99 trees)")
else:
    print(f"   ✗ Failed: {export_response.text}")

print()

# Test GeoJSON export
print("2. Testing GeoJSON Export...")
geojson_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/export?format=geojson",
    headers=headers
)

print(f"   Status: {geojson_response.status_code}")
if geojson_response.status_code == 200:
    print(f"   ✓ Success! File size: {len(geojson_response.content)} bytes")

    # Save file
    with open("test_export_result.geojson", "wb") as f:
        f.write(geojson_response.content)
    print(f"   ✓ Saved to: test_export_result.geojson")

    # Parse and count features
    import json
    data = json.loads(geojson_response.content)
    print(f"   ✓ Features: {len(data['features'])} (should be 99)")
else:
    print(f"   ✗ Failed: {geojson_response.text}")

print()

# Test Summary
print("3. Testing Summary Endpoint...")
summary_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/summary",
    headers=headers
)

print(f"   Status: {summary_response.status_code}")
if summary_response.status_code == 200:
    summary = summary_response.json()
    print(f"   ✓ Success!")
    print(f"   - Total trees: {summary['total_trees']}")
    print(f"   - Total volume: {summary['total_volume_m3']} m³")
    print(f"   - Net volume: {summary['total_net_volume_m3']} m³")
    print(f"   - Firewood: {summary['total_firewood_chatta']} chatta")
else:
    print(f"   ✗ Failed: {summary_response.text}")

print("\n=== All Tests Complete ===")
