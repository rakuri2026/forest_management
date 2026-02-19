"""
Test tree model generation endpoint
"""
import requests
import json

# First login to get token
login_url = "http://localhost:8001/api/auth/login"
login_data = {
    "email": "demo@forest.com",
    "password": "Demo1234"
}

print("1. Logging in...")
response = requests.post(login_url, json=login_data)
print(f"Login status: {response.status_code}")

if response.status_code != 200:
    print(f"Login failed: {response.text}")
    exit(1)

token_data = response.json()
token = token_data["access_token"]
print(f"Token obtained: {token[:20]}...")

# Get list of calculations
print("\n2. Getting calculations...")
calc_url = "http://localhost:8001/api/forests/calculations"
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(calc_url, headers=headers)
print(f"Calculations status: {response.status_code}")

if response.status_code != 200:
    print(f"Failed to get calculations: {response.text}")
    exit(1)

calculations = response.json()
print(f"Found {len(calculations)} calculations")

if len(calculations) == 0:
    print("No calculations found. Upload a boundary first.")
    exit(1)

# Use first calculation
calc_id = calculations[0]["id"]
print(f"Using calculation: {calc_id}")

# Try to generate tree model
print("\n3. Testing tree model generation endpoint...")
tree_model_url = f"http://localhost:8001/api/calculations/{calc_id}/generate-tree-model"
tree_model_data = {
    "config": {
        "min_dbh_cm": 10.0,
        "min_height_m": 5.0,
        "max_trees_per_ha": 1000,
        "spatial_distribution": "random",
        "algorithm_version": "v1.0"
    }
}

print(f"POST {tree_model_url}")
print(f"Body: {json.dumps(tree_model_data, indent=2)}")

response = requests.post(tree_model_url, headers=headers, json=tree_model_data)
print(f"\nResponse status: {response.status_code}")
print(f"Response body: {response.text}")

if response.status_code == 200:
    print("\n✓ SUCCESS!")
    result = response.json()
    print(f"Model ID: {result.get('id')}")
    print(f"Status: {result.get('status')}")
else:
    print("\n✗ FAILED!")
    print(f"Error: {response.text}")
