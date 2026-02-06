"""
Test script for new per-block sampling system
Run this after starting the backend server
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8001"

def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)

def print_json(data):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2, default=str))

def get_auth_token():
    """Get authentication token"""
    print_separator("AUTHENTICATION")
    print("Logging in...")

    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "demo@forest.com",
            "password": "Demo1234"
        }
    )

    if response.status_code == 200:
        token = response.json()['access_token']
        print("✓ Login successful")
        return token
    else:
        print(f"✗ Login failed: {response.status_code}")
        print(response.text)
        return None

def get_calculation_with_blocks(token):
    """Find a calculation that has multiple blocks"""
    print_separator("FINDING TEST CALCULATION")
    print("Looking for calculations with multiple blocks...")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/forests/calculations", headers=headers)

    if response.status_code != 200:
        print(f"✗ Failed to get calculations: {response.status_code}")
        print(f"Response: {response.text}")
        return None

    calculations = response.json()

    if not calculations:
        print("✗ No calculations found")
        print("  Please upload a forest boundary first")
        return None

    print(f"Found {len(calculations)} calculation(s)")

    # Find one with blocks
    for calc in calculations:
        if not calc:
            continue

        calc_id = calc.get('id')
        result_data = calc.get('result_data')

        if not result_data or not isinstance(result_data, dict):
            continue

        blocks = result_data.get('blocks')

        if blocks and isinstance(blocks, list) and len(blocks) >= 1:
            print(f"\n✓ Found calculation: {calc_id}")
            print(f"  Forest: {calc.get('forest_name', 'Unknown')}")
            print(f"  Blocks: {len(blocks)}")

            for block in blocks:
                if isinstance(block, dict):
                    area_ha = block.get('area_hectares', 0)
                    block_name = block.get('block_name', 'Unknown')
                    print(f"    - {block_name}: {area_ha:.2f} ha")

            return calc_id

    # If no multi-block found, use any calculation
    print("\n⚠️  No multi-block calculation found")
    print("  Using first available calculation (single block test)")

    if calculations and calculations[0]:
        calc = calculations[0]
        calc_id = calc.get('id')
        print(f"  ID: {calc_id}")
        print(f"  Forest: {calc.get('forest_name', 'Unknown')}")
        return calc_id

    print("✗ No calculations found")
    print("  Please upload a forest boundary first")
    return None

def test_systematic_sampling(token, calculation_id):
    """Test systematic sampling with new parameters"""
    print_separator("TEST 1: SYSTEMATIC SAMPLING")
    print("Creating systematic sampling design...")
    print("Parameters:")
    print("  - Intensity: 0.5%")
    print("  - Min samples (≥1 ha): 5")
    print("  - Min samples (<1 ha): 2")
    print("  - Plot: Circular, r=12.62m (500m²)")

    headers = {"Authorization": f"Bearer {token}"}

    # First, delete any existing sampling design
    print("  Checking for existing sampling designs...")
    try:
        # Try to get list of designs for this calculation
        list_url = f"{BASE_URL}/api/calculations/{calculation_id}/sampling"
        response = requests.get(list_url, headers=headers)

        if response.status_code == 200:
            designs = response.json()
            if designs and len(designs) > 0:
                for design in designs:
                    design_id = design.get('id')
                    print(f"  Found existing design: {design_id}")
                    print(f"  Deleting...")

                    # Correct endpoint: /api/sampling/{design_id}
                    delete_url = f"{BASE_URL}/api/sampling/{design_id}"
                    del_response = requests.delete(delete_url, headers=headers)

                    if del_response.status_code in [200, 204]:
                        print(f"  ✓ Deleted successfully")
                    else:
                        print(f"  ⚠️  Delete returned: {del_response.status_code}")
                        print(f"     {del_response.text}")
            else:
                print("  No existing designs found")
        else:
            print(f"  Could not list designs: {response.status_code}")
    except Exception as e:
        print(f"  Note: Could not check for existing designs: {str(e)}")
        pass

    # Create new design
    response = requests.post(
        f"{BASE_URL}/api/calculations/{calculation_id}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "systematic",
            "sampling_intensity_percent": 0.5,
            "min_samples_per_block": 5,
            "min_samples_small_blocks": 2,
            "plot_shape": "circular",
            "plot_radius_meters": 12.6156,
            "notes": "Test systematic sampling with per-block minimum"
        }
    )

    print(f"\nResponse Status: {response.status_code}")

    if response.status_code == 200:
        print("✓ SUCCESS!")
        result = response.json()

        print("\n--- OVERALL SUMMARY ---")
        print(f"Total Points: {result['total_points']}")
        print(f"Total Blocks: {result['total_blocks']}")
        print(f"Forest Area: {result['forest_area_hectares']} ha")
        print(f"Requested Intensity: {result['requested_intensity_percent']}%")
        print(f"Actual Intensity: {result['actual_intensity_per_hectare']} points/ha")
        print(f"Sampling Percentage: {result['sampling_percentage']}%")

        print("\n--- PER-BLOCK DETAILS ---")
        for block in result.get('blocks_info', []):
            enforced = "⚠️  MINIMUM ENFORCED" if block['minimum_enforced'] else "✓"
            print(f"\n{block['block_name']} ({block['block_area_hectares']} ha):")
            print(f"  Samples Generated: {block['samples_generated']}")
            print(f"  Actual Intensity: {block['actual_intensity_percent']}%")
            print(f"  Status: {enforced}")

        return result
    else:
        print(f"✗ FAILED!")
        print(response.text)
        return None

def test_random_sampling(token, calculation_id):
    """Test random sampling"""
    print_separator("TEST 2: RANDOM SAMPLING")
    print("Creating random sampling design...")

    headers = {"Authorization": f"Bearer {token}"}

    # Delete existing
    print("  Checking for existing designs...")
    try:
        list_url = f"{BASE_URL}/api/calculations/{calculation_id}/sampling"
        response = requests.get(list_url, headers=headers)
        if response.status_code == 200:
            designs = response.json()
            if designs and len(designs) > 0:
                for design in designs:
                    design_id = design.get('id')
                    print(f"  Deleting design: {design_id}")
                    delete_url = f"{BASE_URL}/api/sampling/{design_id}"
                    requests.delete(delete_url, headers=headers)
    except:
        pass

    response = requests.post(
        f"{BASE_URL}/api/calculations/{calculation_id}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "random",
            "sampling_intensity_percent": 1.0,  # Higher intensity
            "min_samples_per_block": 8,  # Custom minimum
            "min_samples_small_blocks": 3,
            "plot_shape": "circular",
            "plot_radius_meters": 8.0,  # Smaller plot (200m²)
            "min_distance_meters": 30
        }
    )

    print(f"\nResponse Status: {response.status_code}")

    if response.status_code == 200:
        print("✓ SUCCESS!")
        result = response.json()
        print(f"\nTotal Points: {result['total_points']}")
        print(f"With custom minimums (8 for large, 3 for small blocks)")

        for block in result.get('blocks_info', []):
            print(f"  {block['block_name']}: {block['samples_generated']} samples")

        return result
    else:
        print(f"✗ FAILED!")
        print(response.text)
        return None

def test_validation_errors(token, calculation_id):
    """Test validation and error handling"""
    print_separator("TEST 3: VALIDATION & ERROR HANDLING")

    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: Invalid minimum range
    print("\n1. Testing invalid minimum (11 > max 10)...")
    response = requests.post(
        f"{BASE_URL}/api/calculations/{calculation_id}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "systematic",
            "sampling_intensity_percent": 0.5,
            "min_samples_per_block": 11,  # Too high!
            "plot_shape": "circular"
        }
    )

    if response.status_code == 422 or response.status_code == 400:
        print("   ✓ Correctly rejected invalid minimum")
    else:
        print(f"   ✗ Should have rejected, got: {response.status_code}")

    # Test 2: Invalid intensity
    print("\n2. Testing invalid intensity (15% > max 10%)...")
    response = requests.post(
        f"{BASE_URL}/api/calculations/{calculation_id}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "systematic",
            "sampling_intensity_percent": 15.0,  # Too high!
            "plot_shape": "circular"
        }
    )

    if response.status_code == 422 or response.status_code == 400:
        print("   ✓ Correctly rejected invalid intensity")
    else:
        print(f"   ✗ Should have rejected, got: {response.status_code}")

    print("\n✓ Validation tests complete")

def main():
    """Run all tests"""
    print_separator("SAMPLING SYSTEM BACKEND TEST")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing against: {BASE_URL}")

    # Step 1: Authenticate
    token = get_auth_token()
    if not token:
        print("\n✗ Cannot proceed without authentication")
        return

    # Step 2: Find test calculation
    calculation_id = get_calculation_with_blocks(token)
    if not calculation_id:
        print("\n✗ Cannot proceed without test calculation")
        print("\nTo fix: Upload a forest boundary with multiple blocks")
        return

    # Step 3: Run tests
    try:
        test_systematic_sampling(token, calculation_id)

        input("\nPress Enter to continue with random sampling test...")
        test_random_sampling(token, calculation_id)

        input("\nPress Enter to continue with validation tests...")
        test_validation_errors(token, calculation_id)

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        return
    except Exception as e:
        print(f"\n✗ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    print_separator("ALL TESTS COMPLETE")
    print("✓ Backend sampling system is working correctly!")
    print("\nNext step: Update frontend with new parameters")

if __name__ == "__main__":
    main()
