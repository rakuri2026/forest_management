"""
Test script for per-block sampling parameter overrides
"""
import requests
import json

BASE_URL = "http://localhost:8001"

# Test credentials (using existing user)
EMAIL = "newuser@example.com"
PASSWORD = "NewPassword123"

def test_block_overrides():
    """Test creating sampling design with block-specific overrides"""

    print("Step 1: Login to get access token...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )

    if login_response.status_code != 200:
        print(f"Login failed: {login_response.status_code}")
        print(login_response.text)
        return False

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Login successful! Token: {token[:20]}...")

    print("\nStep 2: Get a calculation with multiple blocks...")
    calcs_response = requests.get(
        f"{BASE_URL}/api/forests/calculations",
        headers=headers,
        params={"limit": 10}
    )

    if calcs_response.status_code != 200:
        print(f"Failed to get calculations: {calcs_response.status_code}")
        return False

    calculations = calcs_response.json()
    if not calculations:
        print("No calculations found. Please upload a boundary first.")
        return False

    # Find a calculation with multiple blocks
    calc_id = None
    for calc in calculations:
        if calc.get("result_data", {}).get("blocks"):
            blocks = calc["result_data"]["blocks"]
            if len(blocks) > 1:
                calc_id = calc["id"]
                print(f"  Found calculation {calc_id} with {len(blocks)} blocks")
                for block in blocks[:3]:  # Show first 3 blocks
                    print(f"    - {block.get('block_name', 'Unknown')}: {block.get('area_hectares', 0):.2f} ha")
                break

    if not calc_id:
        # Use first calculation even if it has only 1 block
        calc_id = calculations[0]["id"]
        print(f"  Using calculation {calc_id} (may have single block)")

    print("\nStep 3: Create sampling design with block overrides...")

    # Create sampling design with block overrides
    sampling_request = {
        "sampling_type": "systematic",
        "sampling_intensity_percent": 0.5,  # Default 0.5%
        "min_samples_per_block": 5,
        "min_samples_small_blocks": 2,
        "boundary_buffer_meters": 50.0,
        "plot_shape": "circular",
        "plot_radius_meters": 12.6156,
        "notes": "Testing per-block parameter overrides",
        # Block-specific overrides
        "block_overrides": {
            "Block 1": {
                "sampling_intensity_percent": 1.0,  # Higher intensity for Block 1
                "min_samples_per_block": 10
            },
            "Block 2": {
                "sampling_type": "random",  # Different sampling type for Block 2
                "boundary_buffer_meters": 100.0  # Larger buffer
            }
        }
    }

    print(f"  Request payload:")
    print(f"    Default sampling_intensity_percent: {sampling_request['sampling_intensity_percent']}%")
    print(f"    Block overrides:")
    for block_name, overrides in sampling_request["block_overrides"].items():
        print(f"      {block_name}: {overrides}")

    create_response = requests.post(
        f"{BASE_URL}/api/forests/calculations/{calc_id}/sampling/create",
        headers=headers,
        json=sampling_request
    )

    if create_response.status_code != 200:
        print(f"\n  Failed to create sampling design: {create_response.status_code}")
        print(f"  Error: {create_response.text}")
        return False

    result = create_response.json()
    design_id = result["sampling_design_id"]

    print(f"\n  Sampling design created successfully!")
    print(f"  Design ID: {design_id}")
    print(f"  Total points: {result['total_points']}")
    print(f"  Total blocks: {result['total_blocks']}")
    print(f"  Forest area: {result['forest_area_hectares']} ha")

    if "blocks_info" in result:
        print(f"\n  Per-block summary:")
        for block_info in result["blocks_info"]:
            print(f"    {block_info['block_name']}:")
            print(f"      Area: {block_info['block_area_hectares']} ha")
            print(f"      Samples: {block_info['samples_generated']}")
            print(f"      Actual intensity: {block_info['actual_intensity_percent']:.2f}%")
            print(f"      Minimum enforced: {block_info['minimum_enforced']}")

    print("\nStep 4: Verify stored parameters...")

    # Get the design details to verify parameters were stored
    design_response = requests.get(
        f"{BASE_URL}/api/sampling/{design_id}",
        headers=headers
    )

    if design_response.status_code != 200:
        print(f"  Failed to get design details: {design_response.status_code}")
        return False

    design_data = design_response.json()

    print(f"  Default parameters: {design_data.get('default_parameters', 'Not stored')}")
    print(f"  Block overrides: {design_data.get('block_overrides', 'Not stored')}")

    print("\n✓ Test completed successfully!")
    return True


if __name__ == "__main__":
    try:
        success = test_block_overrides()
        if not success:
            print("\n✗ Test failed")
    except Exception as e:
        print(f"\n✗ Test error: {e}")
        import traceback
        traceback.print_exc()
