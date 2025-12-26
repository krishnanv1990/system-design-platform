"""
Authentication API routes.
Handles Google OAuth flow and JWT token management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.schemas.user import UserResponse, TokenResponse
from backend.auth.jwt_handler import create_access_token, get_current_user
from backend.auth.oauth import (
    get_google_oauth_url,
    exchange_code_for_token,
    get_google_user_info,
)
from backend.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/google")
async def google_auth():
    """
    Initiate Google OAuth flow.
    Redirects user to Google's authorization page.
    """
    oauth_url = get_google_oauth_url()
    return RedirectResponse(url=oauth_url)


@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from Google
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get access token from Google"
            )

        # Get user info from Google
        user_info = await get_google_user_info(access_token)
        google_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not google_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )

        # Find or create user
        user = db.query(User).filter(User.google_id == google_id).first()

        if user:
            # Update existing user info
            user.name = name
            user.avatar_url = avatar_url
            db.commit()
        else:
            # Create new user
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                avatar_url=avatar_url,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id})

        # Redirect to frontend with token
        redirect_url = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        # Redirect to frontend with error
        redirect_url = f"{settings.frontend_url}/auth/callback?error={str(e)}"
        return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's information.

    Args:
        current_user: User from JWT token

    Returns:
        User information
    """
    return current_user


@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    Note: JWT tokens are stateless, so actual logout is handled client-side
    by deleting the token. This endpoint exists for API completeness.

    Returns:
        Success message
    """
    return {"message": "Successfully logged out"}
