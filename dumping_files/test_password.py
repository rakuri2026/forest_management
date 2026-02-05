"""
Test password verification
"""
from passlib.context import CryptContext

# Configure bcrypt to truncate passwords automatically
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__truncate_error=False
)

# The hash from database
db_hash = "$2b$12$uPt5vujWQA6zz8axXZ5uNOXJsjKi7sBHL6z/F0smh9x7JqeDfjEuS"

# Test different passwords
test_passwords = [
    "SecurePass123",
    "Test123",
    "newuser123",
    "password123",
]

print("Testing password verification...")
print(f"Database hash: {db_hash}\n")

for password in test_passwords:
    # Apply same truncation logic as in utils/auth.py
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        password = password_bytes.decode('utf-8', errors='ignore')

    result = pwd_context.verify(password, db_hash)
    print(f"Password: '{password}' -> {result}")

# Also test creating a new hash to see if it matches
print("\n\nCreating new hash for 'SecurePass123':")
new_hash = pwd_context.hash("SecurePass123")
print(f"New hash: {new_hash}")
print(f"Verify against new hash: {pwd_context.verify('SecurePass123', new_hash)}")
