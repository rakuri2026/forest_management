"""
Reset password for a user
"""
import sys
from passlib.context import CryptContext
import psycopg2

# Configure bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__truncate_error=False
)

def reset_password(email: str, new_password: str):
    """Reset user password"""
    # Hash the new password
    hashed = pwd_context.hash(new_password)

    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="cf_db",
        user="postgres",
        password="admin123"
    )

    try:
        with conn.cursor() as cur:
            # Update password
            cur.execute(
                "UPDATE public.users SET hashed_password = %s WHERE email = %s RETURNING email",
                (hashed, email)
            )
            result = cur.fetchone()

            if result:
                conn.commit()
                print(f"Password reset successful for: {result[0]}")
                print(f"  New password: {new_password}")

                # Verify the hash works
                print(f"\n  Verification test: {pwd_context.verify(new_password, hashed)}")
            else:
                print(f"User not found: {email}")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python reset_password.py <email> <new_password>")
        print("\nExample:")
        print("  python reset_password.py newuser@example.com NewPass123")
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2]

    reset_password(email, new_password)
