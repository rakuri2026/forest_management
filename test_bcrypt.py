#!/usr/bin/env python
"""Test bcrypt password hashing and verification"""
import sys
sys.path.insert(0, './backend')

from passlib.context import CryptContext

# Create password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test password
test_password = "password123"

# Hash the password
print(f"Hashing password: {test_password}")
hashed = pwd_context.hash(test_password)
print(f"Hashed password: {hashed}")

# Verify the password
is_valid = pwd_context.verify(test_password, hashed)
print(f"Password verification: {is_valid}")

# Now try a simple test with existing hash from database
print("\nTesting with a known good bcrypt hash...")
known_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyVK.dxfcisO"  # Example
try:
    result = pwd_context.verify("test123", known_hash)
    print(f"Verification result: {result}")
except Exception as e:
    print(f"Error during verification: {e}")
