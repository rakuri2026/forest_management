"""
Debug script to test file upload endpoint
"""
import requests
import json
import sys

# Replace with your actual token
TOKEN = input("Enter your JWT token: ").strip()

# API endpoint
BASE_URL = "http://localhost:8001"
UPLOAD_URL = f"{BASE_URL}/api/forests/upload"

# Test file path - update this to the file you're trying to upload
file_path = input("Enter the file path to upload: ").strip()

# Forest details
forest_name = input("Enter forest name: ").strip() or "Test Forest"
block_name = input("Enter block name (optional): ").strip() or None

print(f"\n--- Upload Test ---")
print(f"File: {file_path}")
print(f"Forest Name: {forest_name}")
print(f"Block Name: {block_name}")
print(f"Token: {TOKEN[:20]}...")

try:
    # Prepare the upload
    with open(file_path, 'rb') as f:
        files = {
            'file': (file_path.split('\\')[-1], f, 'application/octet-stream')
        }

        data = {
            'forest_name': forest_name,
        }

        if block_name:
            data['block_name'] = block_name

        headers = {
            'Authorization': f'Bearer {TOKEN}'
        }

        print("\nSending request...")
        response = requests.post(
            UPLOAD_URL,
            files=files,
            data=data,
            headers=headers,
            timeout=300  # 5 minute timeout for large files
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        try:
            result = response.json()
            print(f"\nResponse JSON:")
            print(json.dumps(result, indent=2))

            if response.status_code == 201:
                print("\n✓ Upload successful!")
                print(f"Calculation ID: {result.get('id')}")
                print(f"Status: {result.get('status')}")
            else:
                print(f"\n✗ Upload failed!")
                print(f"Error: {result.get('detail', 'Unknown error')}")
        except Exception as e:
            print(f"\nResponse Text: {response.text}")
            print(f"JSON Parse Error: {e}")

except FileNotFoundError:
    print(f"\n✗ Error: File not found: {file_path}")
except requests.exceptions.RequestException as e:
    print(f"\n✗ Request Error: {e}")
except Exception as e:
    print(f"\n✗ Unexpected Error: {e}")
    import traceback
    traceback.print_exc()
