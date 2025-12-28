"""
JWT token creation and verification.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.models.user import User

settings = get_settings()
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        print(f"Token verified successfully, payload: {payload}")
        return payload
    except JWTError as e:
        print(f"Token verification failed: {e}, token prefix: {token[:50] if token else 'None'}...")
        return None


def get_or_create_demo_user(db: Session) -> User:
    """Get or create a demo user for demo mode."""
    demo_user = db.query(User).filter(User.email == "demo@example.com").first()
    if not demo_user:
        demo_user = User(
            google_id="demo-user-id",
            email="demo@example.com",
            name="Demo User",
            avatar_url=None,
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
    return demo_user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user.
    In demo mode, returns a demo user without requiring authentication.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: If token is invalid or user not found (only in non-demo mode)
    """
    # In demo mode, return demo user
    if settings.demo_mode:
        return get_or_create_demo_user(db)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        print("get_current_user: No credentials provided")
        raise credentials_exception

    token = credentials.credentials
    print(f"get_current_user: Token received, length={len(token) if token else 0}")
    payload = verify_token(token)

    if payload is None:
        print("get_current_user: Token verification failed")
        raise credentials_exception

    user_id_str = payload.get("sub")
    if user_id_str is None:
        print("get_current_user: No user_id in payload")
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        print(f"get_current_user: Invalid user_id format: {user_id_str}")
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        print(f"get_current_user: User not found for id={user_id}")
        raise credentials_exception

    print(f"get_current_user: User found - {user.email}")
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional version of get_current_user that returns None for unauthenticated requests.
    In demo mode, returns a demo user.

    Args:
        credentials: Bearer token from Authorization header (optional)
        db: Database session

    Returns:
        User object or None if not authenticated
    """
    # In demo mode, return demo user
    if settings.demo_mode:
        return get_or_create_demo_user(db)

    if credentials is None:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        return None

    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None

    return db.query(User).filter(User.id == user_id).first()
