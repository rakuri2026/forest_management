"""
Quick test to verify CORS is configured correctly
"""
import requests

def test_cors():
    print("=" * 60)
    print("Testing CORS Configuration")
    print("=" * 60)
    print()

    # Test with OPTIONS request (preflight)
    print("1. Testing CORS preflight (OPTIONS request)...")
    try:
        response = requests.options(
            "http://localhost:8001/api/inventory/upload",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type"
            }
        )

        print(f"   Status: {response.status_code}")
        print(f"   Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'NOT SET')}")
        print(f"   Access-Control-Allow-Credentials: {response.headers.get('Access-Control-Allow-Credentials', 'NOT SET')}")
        print(f"   Access-Control-Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'NOT SET')}")

        if response.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000':
            print("   [OK] CORS is configured correctly!")
        else:
            print("   [ERROR] CORS is NOT configured correctly!")
            print("   Expected: http://localhost:3000")
            print(f"   Got: {response.headers.get('Access-Control-Allow-Origin')}")

    except Exception as e:
        print(f"   [ERROR] Failed to test CORS: {e}")

    print()

    # Test health endpoint
    print("2. Testing health endpoint...")
    try:
        response = requests.get("http://localhost:8001/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   [ERROR] Backend not responding: {e}")

    print()
    print("=" * 60)

if __name__ == "__main__":
    test_cors()
