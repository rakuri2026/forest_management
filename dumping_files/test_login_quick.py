import requests
import sys

BASE_URL = "http://localhost:8001"

print("Testing backend connection...")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"Backend status: {r.json()}")
except:
    print("ERROR: Backend not running!")
    sys.exit(1)

users = [
    {"email": "admin@cfapp.com", "password": "admin123"},
    {"email": "rajkumarrimal@gmail.com", "password": "Test@123"},
]

print("\nTrying login...")
for user in users:
    r = requests.post(f"{BASE_URL}/api/auth/login", json=user)
    print(f"\n{user['email']}: Status {r.status_code}")
    if r.status_code == 200:
        print("SUCCESS! Use these credentials:")
        print(f"  Email: {user['email']}")
        print(f"  Password: {user['password']}")
        break
    else:
        print(f"  Error: {r.json()}")
