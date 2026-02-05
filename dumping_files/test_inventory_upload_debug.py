"""
Test inventory upload to debug the issue
"""
import requests
import json

BASE_URL = "http://localhost:8001"

def test_upload():
    print("=" * 60)
    print("Testing Inventory Upload")
    print("=" * 60)

    # Step 1: Login
    print("\n1. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123"
        }
    )

    if login_response.status_code != 200:
        print(f"   ERROR: Login failed with status {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    print(f"   [OK] Login successful")

    # Step 2: Upload inventory file
    print("\n2. Uploading inventory CSV...")

    headers = {
        "Authorization": f"Bearer {token}"
    }

    files = {
        "file": ("test_small_inventory.csv", open("test_small_inventory.csv", "rb"), "text/csv")
    }

    data = {
        "grid_spacing_meters": "20.0"
    }

    try:
        upload_response = requests.post(
            f"{BASE_URL}/api/inventory/upload",
            headers=headers,
            files=files,
            data=data,
            timeout=30
        )

        print(f"   Status Code: {upload_response.status_code}")

        if upload_response.status_code == 200:
            result = upload_response.json()
            print(f"   [OK] Upload successful!")
            print(f"\n   Summary:")
            print(f"   - Total rows: {result.get('summary', {}).get('total_rows', 'N/A')}")
            print(f"   - Valid rows: {result.get('summary', {}).get('valid_rows', 'N/A')}")
            print(f"   - Errors: {result.get('summary', {}).get('error_count', 'N/A')}")
            print(f"   - Ready for processing: {result.get('summary', {}).get('ready_for_processing', False)}")

            if result.get('errors'):
                print(f"\n   Errors ({len(result['errors'])}):")
                for err in result['errors'][:5]:  # Show first 5 errors
                    print(f"   - Row {err.get('row', 'N/A')}: {err.get('message', 'N/A')}")

            if result.get('warnings'):
                print(f"\n   Warnings ({len(result['warnings'])}):")
                for warn in result['warnings'][:5]:  # Show first 5 warnings
                    print(f"   - Row {warn.get('row', 'N/A')}: {warn.get('message', 'N/A')}")

            # Save full result
            with open('upload_debug_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n   Full result saved to: upload_debug_result.json")

        else:
            print(f"   [ERROR] Upload failed!")
            print(f"   Response: {upload_response.text}")

            # Try to parse as JSON
            try:
                error_detail = upload_response.json()
                print(f"   Detail: {error_detail.get('detail', 'No detail')}")
            except:
                pass

    except requests.exceptions.Timeout:
        print(f"   [ERROR] Request timed out after 30 seconds")
    except Exception as e:
        print(f"   [ERROR] Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_upload()
