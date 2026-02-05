"""Create user with simple password"""
import requests

# Register user with test1234 password
response = requests.post(
    "http://localhost:8001/api/auth/register",
    json={
        "email": "simple@test.com",
        "password": "test1234",
        "full_name": "Simple Test User"
    }
)

if response.status_code == 201:
    print("User created successfully!")
    print("\nLOGIN CREDENTIALS:")
    print("Email: simple@test.com")
    print("Password: test1234")
    
    # Test login
    login = requests.post(
        "http://localhost:8001/api/auth/login",
        json={"email": "simple@test.com", "password": "test1234"}
    )
    
    if login.status_code == 200:
        print("\nLogin verified - READY TO USE!")
    else:
        print(f"\nLogin test failed: {login.status_code}")
else:
    print(f"Failed: {response.status_code} - {response.text}")
