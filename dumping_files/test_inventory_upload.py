"""
Test inventory upload endpoint
"""
import requests
import json

# Get token from user
TOKEN = input("Enter your JWT token (from browser localStorage): ").strip()

# API endpoint
BASE_URL = "http://localhost:8001"
UPLOAD_URL = f"{BASE_URL}/api/inventory/upload"

# Test file
file_path = r"D:\forest_management\testData\sundar\rame_tree.csv"
grid_spacing = 20.0
projection_epsg = None  # Leave None for auto-detection

print(f"\n--- Inventory Upload Test ---")
print(f"File: {file_path}")
print(f"Grid Spacing: {grid_spacing} meters")
print(f"Projection EPSG: {projection_epsg or 'Auto-detect'}")
print(f"Token: {TOKEN[:20]}...")

try:
    # Prepare the upload
    with open(file_path, 'rb') as f:
        files = {
            'file': ('rame_tree.csv', f, 'text/csv')
        }

        data = {
            'grid_spacing_meters': grid_spacing,
        }

        if projection_epsg:
            data['projection_epsg'] = projection_epsg

        headers = {
            'Authorization': f'Bearer {TOKEN}'
        }

        print("\nSending request...")
        response = requests.post(
            UPLOAD_URL,
            files=files,
            data=data,
            headers=headers,
            timeout=120
        )

        print(f"\nStatus Code: {response.status_code}")

        try:
            result = response.json()
            print(f"\nResponse:")
            print(json.dumps(result, indent=2))

            if response.status_code == 200:
                print("\n✓ Upload successful!")
                if result.get('summary'):
                    summary = result['summary']
                    print(f"  Total Rows: {summary.get('total_rows')}")
                    print(f"  Valid Rows: {summary.get('valid_rows')}")
                    print(f"  Errors: {summary.get('error_count')}")
                    print(f"  Warnings: {summary.get('warning_count')}")
                    print(f"  Ready: {summary.get('ready_for_processing')}")

                    if result.get('inventory_id'):
                        print(f"  Inventory ID: {result['inventory_id']}")
            else:
                print(f"\n✗ Upload failed!")
                print(f"Error: {result.get('detail', 'Unknown error')}")
        except Exception as e:
            print(f"\nResponse Text: {response.text[:500]}")
            print(f"JSON Parse Error: {e}")

except FileNotFoundError:
    print(f"\n✗ Error: File not found: {file_path}")
except requests.exceptions.ConnectionError:
    print(f"\n✗ Error: Cannot connect to {BASE_URL}")
    print("Is the backend server running?")
except requests.exceptions.RequestException as e:
    print(f"\n✗ Request Error: {e}")
except Exception as e:
    print(f"\n✗ Unexpected Error: {e}")
    import traceback
    traceback.print_exc()
