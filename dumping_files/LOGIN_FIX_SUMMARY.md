# Login Issue Resolution

## Problem
Login attempts for `newuser@example.com` were failing with "401 Unauthorized" errors, even though the credentials were believed to be correct.

## Root Cause
The password stored in the database for `newuser@example.com` did not match the password you were attempting to use. The user was created on January 22, 2026, and the original password was either:
- Different from what you remembered
- Changed at some point
- Created with a different password during testing

## Solution
Reset the password for the user `newuser@example.com` to `SecurePass123` using the `reset_password.py` utility.

## Verification
Login now works successfully:

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"SecurePass123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Current Working Credentials

| Email | Password | Role | Status |
|-------|----------|------|--------|
| newuser@example.com | SecurePass123 | USER | ACTIVE |
| inventory_tester@example.com | (unknown) | USER | ACTIVE |
| edittest@example.com | (unknown) | USER | ACTIVE |
| extenttest@example.com | (unknown) | USER | ACTIVE |
| testblock@example.com | (unknown) | USER | ACTIVE |

## How to Reset Other User Passwords

If you need to reset passwords for other users, use the `reset_password.py` script:

```bash
./venv/Scripts/python.exe reset_password.py <email> <new_password>
```

Example:
```bash
./venv/Scripts/python.exe reset_password.py inventory_tester@example.com NewPassword123
```

## Authentication Code Review

The authentication code in `backend/app/api/auth.py` and `backend/app/utils/auth.py` is working correctly:

1. ✅ Password hashing with bcrypt (cost factor 12)
2. ✅ 72-byte truncation handling for long passwords
3. ✅ JWT token generation and verification
4. ✅ User status checks (ACTIVE/PENDING/SUSPENDED)
5. ✅ Role-based access control

No code changes were needed - the issue was purely a credential mismatch in the database.

## Testing Frontend Login

You can now test login from your frontend application using:

```javascript
// Login API call
const response = await fetch('http://localhost:8001/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    email: 'newuser@example.com',
    password: 'SecurePass123'
  })
});

const data = await response.json();
console.log('Token:', data.access_token);
```

## Utilities Created

Two new utility scripts were created for password management:

1. **`reset_password.py`** - Reset user password
   - Usage: `python reset_password.py <email> <new_password>`
   - Connects directly to PostgreSQL
   - Applies same bcrypt hashing as the API
   - Verifies the hash works after reset

2. **`test_password.py`** - Test password verification
   - Tests multiple passwords against a hash
   - Useful for debugging password issues
   - Shows how bcrypt verification works

## Prevention

To avoid this issue in the future:

1. **Document test credentials** - Keep a list of test users and passwords
2. **Use consistent passwords during development** - e.g., always use "Test123" for test users
3. **Implement password reset API** - Add "forgot password" functionality
4. **Keep a password manager** - Store development credentials securely

## Files Modified/Created

- ✅ `reset_password.py` - Password reset utility (NEW)
- ✅ `test_password.py` - Password testing utility (NEW)
- ✅ Database: Updated password hash for `newuser@example.com`
- ✅ No code changes to authentication system (working as designed)

---

**Issue Resolved:** February 2, 2026
**Status:** Login now working successfully
**User:** newuser@example.com
**Password:** SecurePass123
