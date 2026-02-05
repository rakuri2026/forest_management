"""
Test login API
"""
import requests
import json

# API endpoint
BASE_URL = "http://localhost:8001"
LOGIN_URL = f"{BASE_URL}/api/auth/login"

# Credentials
credentials = {
    "email": "newuser@example.com",
    "password": "SecurePass123"
}

print(f"Testing login at: {LOGIN_URL}")
print(f"Credentials: {credentials['email']}")
print()

# Attempt login
response = requests.post(LOGIN_URL, json=credentials)

print(f"Status Code: {response.status_code}")
print(f"Response:")
print(json.dumps(response.json(), indent=2))

if response.status_code == 200:
    print("\n✓ Login successful!")
    token = response.json().get("access_token")
    print(f"Access token: {token[:50]}...")
else:
    print("\n✗ Login failed!")
