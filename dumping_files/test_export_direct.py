"""
Test export directly with the latest completed inventory
"""
import requests

BASE_URL = "http://localhost:8001"
inventory_id = "c89d0c0e-5ca2-4335-b8c0-d07ed0e9a6f4"

# Login
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "newuser@example.com", "password": "SecurePass123"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    exit(1)

token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print(f"Testing export for inventory: {inventory_id}")
print()

# Test CSV export
print("1. CSV Export...")
export_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/export?format=csv",
    headers=headers
)

print(f"   Status: {export_response.status_code}")
if export_response.status_code == 200:
    print(f"   Size: {len(export_response.content)} bytes")
    lines = export_response.content.decode('utf-8').split('\n')
    print(f"   Lines: {len(lines)}")
    print("   SUCCESS!")
else:
    print(f"   Error: {export_response.text}")

print()

# Test GeoJSON export
print("2. GeoJSON Export...")
geojson_response = requests.get(
    f"{BASE_URL}/api/inventory/{inventory_id}/export?format=geojson",
    headers=headers
)

print(f"   Status: {geojson_response.status_code}")
if geojson_response.status_code == 200:
    print(f"   Size: {len(geojson_response.content)} bytes")
    import json
    data = json.loads(geojson_response.content)
    print(f"   Features: {len(data['features'])}")
    print("   SUCCESS!")
else:
    print(f"   Error: {geojson_response.text}")
