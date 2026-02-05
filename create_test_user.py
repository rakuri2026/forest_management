from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create hash for password "Test@123"
password = "Test@123"
hashed = pwd_context.hash(password)

print(f"Password: {password}")
print(f"Hash: {hashed}")
print("\nSQL to create user:")
print(f"""
INSERT INTO public.users (id, email, hashed_password, full_name, role, status)
VALUES (
  '{uuid.uuid4()}',
  'testuser@example.com',
  '{hashed}',
  'Test User',
  'USER',
  'ACTIVE'
);
""")
