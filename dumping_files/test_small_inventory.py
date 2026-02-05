"""
Test inventory processing with small file
"""
import requests

BASE_URL = "http://localhost:8001"

# Login
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "newuser@example.com", "password": "SecurePass123"}
)
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=== Uploading small inventory ===")

# Upload & validate
with open("test_small_inventory.csv", "rb") as f:
    files = {"file": ("test_small_inventory.csv", f, "text/csv")}
    data = {"grid_spacing_meters": 20.0}

    upload_response = requests.post(
        f"{BASE_URL}/api/inventory/upload",
        headers=headers,
        files=files,
        data=data
    )

print(f"Upload Status: {upload_response.status_code}")

if upload_response.status_code == 200:
    result = upload_response.json()
    inventory_id = result.get("inventory_id")
    print(f"Inventory ID: {inventory_id}")

    # Process
    print("\n=== Processing inventory ===")
    with open("test_small_inventory.csv", "rb") as f:
        files = {"file": ("test_small_inventory.csv", f, "text/csv")}

        process_response = requests.post(
            f"{BASE_URL}/api/inventory/{inventory_id}/process",
            headers=headers,
            files=files
        )

    print(f"Process Status: {process_response.status_code}")
    if process_response.status_code == 200:
        print(f"Result: {process_response.json()}")
    else:
        print(f"Error: {process_response.text}")
