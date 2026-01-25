#!/usr/bin/env python
"""Create a test user with proper bcrypt hash"""
import sys
import uuid
from datetime import datetime
sys.path.insert(0, './backend')

from passlib.context import CryptContext
import psycopg2

# Create password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test user credentials
email = "newuser@example.com"
password = "test123"
full_name = "Test New User"

# Hash the password
hashed_password = pwd_context.hash(password)
print(f"Email: {email}")
print(f"Password: {password}")
print(f"Hashed: {hashed_password}")

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="cf_db",
    user="postgres",
    password="admin123"
)
cur = conn.cursor()

# Check if user already exists
cur.execute("SELECT id FROM public.users WHERE email = %s", (email,))
existing = cur.fetchone()

if existing:
    # Update existing user
    cur.execute("""
        UPDATE public.users
        SET hashed_password = %s, status = 'ACTIVE'
        WHERE email = %s
    """, (hashed_password, email))
    print(f"\nUpdated existing user: {email}")
else:
    # Insert new user
    user_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO public.users (id, email, hashed_password, full_name, role, status, created_at)
        VALUES (%s, %s, %s, %s, 'USER', 'ACTIVE', %s)
    """, (user_id, email, hashed_password, full_name, datetime.utcnow()))
    print(f"\nCreated new user: {email}")

conn.commit()
cur.close()
conn.close()

print(f"\nYou can now login with:")
print(f"  Email: {email}")
print(f"  Password: {password}")
