"""
Direct test of inventory upload to see exact error
"""
import requests
import json

# First, let's login to get a fresh token
print("Step 1: Logging in...")
login_url = "http://localhost:8001/api/auth/login"
login_data = {
    "email": "newuser@example.com",
    "password": "SecurePass123"
}

try:
    login_response = requests.post(login_url, json=login_data)
    if login_response.status_code == 200:
        token_data = login_response.json()
        TOKEN = token_data.get('access_token')
        print(f"✓ Login successful! Token: {TOKEN[:20]}...")
    else:
        print(f"✗ Login failed: {login_response.text}")
        print("\nPlease update the email/password in this script to match a valid user")
        exit(1)
except Exception as e:
    print(f"✗ Cannot connect to backend: {e}")
    exit(1)

# Now test the upload
print("\nStep 2: Testing inventory upload...")
upload_url = "http://localhost:8001/api/inventory/upload"
file_path = r"D:\forest_management\testData\sundar\rame_tree.csv"

try:
    with open(file_path, 'rb') as f:
        files = {
            'file': ('rame_tree.csv', f, 'text/csv')
        }

        data = {
            'grid_spacing_meters': '20.0',
        }

        headers = {
            'Authorization': f'Bearer {TOKEN}'
        }

        print(f"Uploading: {file_path}")
        response = requests.post(
            upload_url,
            files=files,
            data=data,
            headers=headers,
            timeout=120
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}\n")

        if response.status_code == 200:
            result = response.json()
            print("✓ Upload successful!")
            print(json.dumps(result, indent=2))
        else:
            print("✗ Upload failed!")
            print(f"Response: {response.text}")

            # Try to parse as JSON
            try:
                error_detail = response.json()
                print(f"\nError Detail: {json.dumps(error_detail, indent=2)}")
            except:
                pass

except FileNotFoundError:
    print(f"✗ File not found: {file_path}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
