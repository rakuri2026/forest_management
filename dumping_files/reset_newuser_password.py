"""Reset newuser@example.com password to test123"""
import requests

# First, delete the old user
print("Creating fresh user with test123 password...")

# Register new user with test123 password
response = requests.post(
    "http://localhost:8001/api/auth/register",
    json={
        "email": "testuser123@example.com",
        "password": "test123",
        "full_name": "Test User 123"
    }
)

if response.status_code == 201:
    print("✓ New user created: testuser123@example.com / test123")
    
    # Test login
    login = requests.post(
        "http://localhost:8001/api/auth/login",
        json={"email": "testuser123@example.com", "password": "test123"}
    )
    
    if login.status_code == 200:
        print("✓ Login verified! Use these credentials in frontend:")
        print("\n  Email: testuser123@example.com")
        print("  Password: test123")
    else:
        print(f"✗ Login failed: {login.status_code}")
else:
    print(f"Failed to create user: {response.status_code}")
    print(response.text)
