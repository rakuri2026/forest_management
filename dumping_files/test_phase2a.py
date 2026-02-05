"""
Test script for Phase 2A: Fieldbook and Sampling functionality
"""
import requests
import json
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
BASE_URL = "http://localhost:8001"
CALCULATION_ID = "4377c308-85cb-4151-a296-3fbae10ba708"

# Get token (login first)
def get_token():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "demo@forest.com",
            "password": "Demo1234"
        }
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print(f"Login failed: {response.status_code}")
        print(response.text)
        return None


def test_fieldbook_generation(token):
    """Test fieldbook generation"""
    print("\n" + "="*60)
    print("TEST 1: Generate Fieldbook")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    # First, check if fieldbook already exists and delete it
    print(f"\nChecking for existing fieldbook...")
    response = requests.get(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        if data.get("total_count", 0) > 0:
            print(f"Found existing fieldbook with {data['total_count']} points. Deleting...")
            delete_response = requests.delete(
                f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook",
                headers=headers
            )
            if delete_response.status_code == 200:
                print("Deleted successfully.")
            else:
                print(f"Delete failed: {delete_response.text}")

    # Generate new fieldbook
    print(f"\nGenerating fieldbook with 20m interpolation...")
    response = requests.post(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook/generate",
        headers=headers,
        json={
            "interpolation_distance_meters": 20,
            "extract_elevation": True
        }
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Fieldbook generated successfully!")
        print(f"  - Total vertices: {data.get('total_vertices', 0)}")
        print(f"  - Interpolated points: {data.get('interpolated_points', 0)}")
        print(f"  - Total points: {data.get('total_points', 0)}")

        perimeter = data.get('total_perimeter_meters')
        print(f"  - Total perimeter: {float(perimeter):.2f} m" if perimeter else "  - Total perimeter: N/A")

        min_elev = data.get('min_elevation_meters')
        max_elev = data.get('max_elevation_meters')
        avg_elev = data.get('avg_elevation_meters')

        print(f"  - Min elevation: {float(min_elev):.2f} m" if min_elev else "  - Min elevation: N/A")
        print(f"  - Max elevation: {float(max_elev):.2f} m" if max_elev else "  - Max elevation: N/A")
        print(f"  - Avg elevation: {float(avg_elev):.2f} m" if avg_elev else "  - Avg elevation: N/A")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def test_fieldbook_list(token):
    """Test listing fieldbook points"""
    print("\n" + "="*60)
    print("TEST 2: List Fieldbook Points")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        total = data.get("total_count", 0)
        print(f"✓ Retrieved {total} points")

        # Show first 3 points
        if data.get("points"):
            print(f"\nFirst 3 points:")
            for point in data["points"][:3]:
                lon = float(point['longitude'])
                lat = float(point['latitude'])
                elev = point.get('elevation')
                elev_str = f"{float(elev):.2f}m" if elev else "N/A"
                print(f"  P{point['point_number']}: ({lon:.6f}, {lat:.6f}) "
                      f"- {point['point_type']} - Elev: {elev_str}")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def test_fieldbook_export_csv(token):
    """Test CSV export"""
    print("\n" + "="*60)
    print("TEST 3: Export Fieldbook to CSV")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook?format=csv",
        headers=headers
    )

    if response.status_code == 200:
        csv_content = response.text
        lines = csv_content.split('\n')
        print(f"✓ CSV exported successfully!")
        print(f"  - Total lines: {len(lines)}")
        print(f"\nFirst 5 lines:")
        for line in lines[:5]:
            print(f"  {line}")

        # Save to file
        with open("test_fieldbook_export.csv", "w") as f:
            f.write(csv_content)
        print(f"\n  Saved to: test_fieldbook_export.csv")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def test_fieldbook_export_geojson(token):
    """Test GeoJSON export"""
    print("\n" + "="*60)
    print("TEST 4: Export Fieldbook to GeoJSON")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/fieldbook?format=geojson",
        headers=headers
    )

    if response.status_code == 200:
        geojson = response.json()
        print(f"✓ GeoJSON exported successfully!")
        print(f"  - Type: {geojson.get('type')}")
        print(f"  - Features: {len(geojson.get('features', []))}")

        # Save to file
        with open("test_fieldbook_export.geojson", "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"  Saved to: test_fieldbook_export.geojson")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def test_sampling_systematic(token):
    """Test systematic sampling"""
    print("\n" + "="*60)
    print("TEST 5: Create Systematic Sampling Design")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "systematic",
            "grid_spacing_meters": 100,
            "plot_shape": "circular",
            "plot_radius_meters": 8.0
        }
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Systematic sampling created successfully!")
        design_id = data.get('sampling_design_id')
        print(f"  - Design ID: {design_id}")
        print(f"  - Total points: {data.get('total_points', 0)}")
        print(f"  - Grid spacing: {data.get('grid_spacing_meters', 0)} m")

        plot_area = data.get('plot_area_sqm', 0)
        sampling_pct = data.get('sampling_percentage', 0)

        print(f"  - Plot area: {float(plot_area):.2f} m²" if plot_area else "  - Plot area: N/A")
        print(f"  - Sampling %: {float(sampling_pct):.2f}%" if sampling_pct else "  - Sampling %: N/A")
        return design_id
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return None


def test_sampling_random(token):
    """Test random sampling"""
    print("\n" + "="*60)
    print("TEST 6: Create Random Sampling Design")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/sampling/create",
        headers=headers,
        json={
            "sampling_type": "random",
            "intensity_per_hectare": 0.5,
            "min_distance_meters": 30,
            "plot_shape": "circular",
            "plot_radius_meters": 10.0
        }
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Random sampling created successfully!")
        design_id = data.get('sampling_design_id')
        print(f"  - Design ID: {design_id}")
        print(f"  - Total points: {data.get('total_points', 0)}")

        intensity = data.get('actual_intensity_per_hectare', 0)
        min_dist = data.get('min_distance_meters', 0)
        plot_area = data.get('plot_area_sqm', 0)

        print(f"  - Intensity: {float(intensity) if intensity else 0} pts/ha")
        print(f"  - Min distance: {float(min_dist) if min_dist else 0} m")
        print(f"  - Plot area: {float(plot_area):.2f} m²" if plot_area else "  - Plot area: N/A")
        return design_id
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return None


def test_sampling_export_geojson(token, design_id):
    """Test sampling GeoJSON export"""
    print("\n" + "="*60)
    print("TEST 7: Export Sampling Points to GeoJSON")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/api/sampling/{design_id}/points?format=geojson",
        headers=headers
    )

    if response.status_code == 200:
        geojson = response.json()
        print(f"✓ GeoJSON exported successfully!")
        print(f"  - Type: {geojson.get('type')}")
        print(f"  - Features: {len(geojson.get('features', []))}")

        # Save to file
        with open("test_sampling_export.geojson", "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"  Saved to: test_sampling_export.geojson")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def test_sampling_list(token):
    """Test listing sampling designs"""
    print("\n" + "="*60)
    print("TEST 8: List All Sampling Designs")
    print("="*60)

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/api/calculations/{CALCULATION_ID}/sampling",
        headers=headers
    )

    if response.status_code == 200:
        designs = response.json()
        print(f"✓ Retrieved {len(designs)} sampling designs")

        for i, design in enumerate(designs, 1):
            print(f"\n  Design {i}:")
            print(f"    - Type: {design.get('sampling_type')}")
            print(f"    - Total points: {design.get('total_points')}")
            print(f"    - Created: {design.get('created_at')}")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        print(response.text)
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PHASE 2A TESTING: Fieldbook & Sampling")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Calculation ID: {CALCULATION_ID}")

    # Get authentication token
    print("\nAuthenticating...")
    token = get_token()
    if not token:
        print("✗ Authentication failed. Exiting.")
        return

    print("✓ Authentication successful")

    # Run tests
    results = []

    # Fieldbook tests
    results.append(("Fieldbook Generation", test_fieldbook_generation(token)))
    results.append(("Fieldbook List", test_fieldbook_list(token)))
    results.append(("Fieldbook CSV Export", test_fieldbook_export_csv(token)))
    results.append(("Fieldbook GeoJSON Export", test_fieldbook_export_geojson(token)))

    # Sampling tests
    systematic_id = test_sampling_systematic(token)
    results.append(("Systematic Sampling", systematic_id is not None))

    random_id = test_sampling_random(token)
    results.append(("Random Sampling", random_id is not None))

    if systematic_id:
        results.append(("Sampling GeoJSON Export", test_sampling_export_geojson(token, systematic_id)))

    results.append(("List Sampling Designs", test_sampling_list(token)))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Phase 2A implementation is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above for details.")


if __name__ == "__main__":
    main()
