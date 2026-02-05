from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password = "test123"
hashed = pwd_context.hash(password)

print(f"Password: {password}")
print(f"Hash: {hashed}")

# Output SQL
print(f"\nUPDATE public.users SET hashed_password = '{hashed}' WHERE email = 'newuser@example.com';")
