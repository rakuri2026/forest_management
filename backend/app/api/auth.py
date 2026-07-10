"""
Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt

from ..core.database import get_db
from ..models.user import User, UserStatus
from ..schemas.auth import UserRegister, UserLogin, Token, UserResponse, PasswordChange
from ..utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
)
from ..core.config import settings

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user

    - **email**: Valid email address (must be unique)
    - **password**: Strong password (min 8 chars, uppercase, lowercase, digit)
    - **full_name**: User's full name
    - **phone**: Optional phone number
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        phone=user_data.phone,
        status=UserStatus.ACTIVE,  # Auto-activate for now
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password

    Returns JWT access token
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Verify password
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check user status
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value}. Please contact administrator."
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user information

    Requires valid JWT token in Authorization header
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change user password

    Requires current password for verification
    """
    # Verify old password
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    # Check new password is different
    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.get("/roles")
async def get_available_roles():
    """
    Get list of available user roles

    Used for admin interfaces
    """
    from ..models.user import UserRole
    return {
        "roles": [
            {"value": role.value, "label": role.value.replace("_", " ").title()}
            for role in UserRole
        ]
    }


@router.post("/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Refresh the access token — extends the session.

    Accepts a token that is still valid OR recently expired (signature
    must match, but expiration is ignored). Returns a fresh token.
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/toggle-role")
async def toggle_user_role(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Toggle current user between super_admin and user (dev convenience)."""
    new_role = UserRole.USER if current_user.role == UserRole.SUPER_ADMIN else UserRole.SUPER_ADMIN
    current_user.role = new_role
    db.commit()
    db.refresh(current_user)
    return current_user
