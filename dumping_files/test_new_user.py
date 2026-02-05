import requests

r = requests.post(
    "http://localhost:8001/api/auth/login",
    json={"email": "testuser@example.com", "password": "Test@123"}
)

print(f"Status: {r.status_code}")
if r.status_code == 200:
    print("✓ LOGIN SUCCESSFUL!")
    print(f"Token: {r.json()['access_token'][:50]}...")
else:
    print(f"✗ Failed: {r.json()}")
