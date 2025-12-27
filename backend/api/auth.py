"""
Authentication API routes.

Handles OAuth flows for multiple providers and JWT token management.
Supports Google, Facebook, LinkedIn, and GitHub authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.models.user import User
from backend.schemas.user import UserResponse
from backend.auth.jwt_handler import create_access_token, get_current_user
from backend.auth.oauth import (
    OAuthProvider,
    get_google_oauth_url,
    exchange_google_code_for_token,
    get_google_user_info,
    get_facebook_oauth_url,
    exchange_facebook_code_for_token,
    get_facebook_user_info,
    get_linkedin_oauth_url,
    exchange_linkedin_code_for_token,
    get_linkedin_user_info,
    get_github_oauth_url,
    exchange_github_code_for_token,
    get_github_user_info,
)
from backend.config import get_settings

router = APIRouter()
settings = get_settings()


# =============================================================================
# Helper Functions
# =============================================================================

def find_or_create_user(
    db: Session,
    provider: OAuthProvider,
    oauth_id: str,
    email: str,
    name: Optional[str],
    avatar_url: Optional[str],
) -> User:
    """
    Find existing user or create new one based on OAuth info.

    Users are matched by email first (to allow linking multiple OAuth providers),
    then by provider-specific OAuth ID.

    Args:
        db: Database session
        provider: OAuth provider used for authentication
        oauth_id: Provider-specific user ID
        email: User's email address
        name: User's display name
        avatar_url: Profile picture URL

    Returns:
        User object (existing or newly created)
    """
    # Map provider to the corresponding ID field name
    provider_id_fields = {
        OAuthProvider.GOOGLE: "google_id",
        OAuthProvider.FACEBOOK: "facebook_id",
        OAuthProvider.LINKEDIN: "linkedin_id",
        OAuthProvider.GITHUB: "github_id",
    }
    id_field = provider_id_fields[provider]

    # First, try to find user by OAuth provider ID
    user = db.query(User).filter(getattr(User, id_field) == oauth_id).first()

    if user:
        # Update user info from OAuth provider
        if name:
            user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        db.commit()
        return user

    # Try to find user by email (allows linking multiple OAuth providers)
    user = db.query(User).filter(User.email == email).first()

    if user:
        # Link this OAuth provider to existing user
        setattr(user, id_field, oauth_id)
        if name:
            user.name = name
        if avatar_url:
            user.avatar_url = avatar_url
        db.commit()
        return user

    # Create new user
    user_data = {
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
        id_field: oauth_id,
    }
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_auth_redirect(token: str) -> RedirectResponse:
    """Create redirect to frontend with JWT token."""
    redirect_url = f"{settings.frontend_url}/#/auth/callback?token={token}"
    return RedirectResponse(url=redirect_url)


def create_error_redirect(error: str) -> RedirectResponse:
    """Create redirect to frontend with error message."""
    redirect_url = f"{settings.frontend_url}/#/auth/callback?error={error}"
    return RedirectResponse(url=redirect_url)


# =============================================================================
# Google OAuth Routes
# =============================================================================

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
        token_data = await exchange_google_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from Google")

        # Get user info from Google
        user_info = await get_google_user_info(access_token)
        google_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not google_id or not email:
            return create_error_redirect("Failed to get user info from Google")

        # Find or create user
        user = find_or_create_user(
            db=db,
            provider=OAuthProvider.GOOGLE,
            oauth_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id})
        return create_auth_redirect(jwt_token)

    except Exception as e:
        return create_error_redirect(str(e))


# =============================================================================
# Facebook OAuth Routes
# =============================================================================

@router.get("/facebook")
async def facebook_auth():
    """
    Initiate Facebook OAuth flow.
    Redirects user to Facebook's authorization page.
    """
    oauth_url = get_facebook_oauth_url()
    return RedirectResponse(url=oauth_url)


@router.get("/facebook/callback")
async def facebook_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle Facebook OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from Facebook
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_facebook_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from Facebook")

        # Get user info from Facebook
        user_info = await get_facebook_user_info(access_token)
        facebook_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not facebook_id or not email:
            return create_error_redirect("Failed to get user info from Facebook")

        # Find or create user
        user = find_or_create_user(
            db=db,
            provider=OAuthProvider.FACEBOOK,
            oauth_id=facebook_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id})
        return create_auth_redirect(jwt_token)

    except Exception as e:
        return create_error_redirect(str(e))


# =============================================================================
# LinkedIn OAuth Routes
# =============================================================================

@router.get("/linkedin")
async def linkedin_auth():
    """
    Initiate LinkedIn OAuth flow.
    Redirects user to LinkedIn's authorization page.
    """
    oauth_url = get_linkedin_oauth_url()
    return RedirectResponse(url=oauth_url)


@router.get("/linkedin/callback")
async def linkedin_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle LinkedIn OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from LinkedIn
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_linkedin_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from LinkedIn")

        # Get user info from LinkedIn
        user_info = await get_linkedin_user_info(access_token)
        linkedin_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not linkedin_id or not email:
            return create_error_redirect("Failed to get user info from LinkedIn")

        # Find or create user
        user = find_or_create_user(
            db=db,
            provider=OAuthProvider.LINKEDIN,
            oauth_id=linkedin_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id})
        return create_auth_redirect(jwt_token)

    except Exception as e:
        return create_error_redirect(str(e))


# =============================================================================
# GitHub OAuth Routes
# =============================================================================

@router.get("/github")
async def github_auth():
    """
    Initiate GitHub OAuth flow.
    Redirects user to GitHub's authorization page.
    """
    oauth_url = get_github_oauth_url()
    return RedirectResponse(url=oauth_url)


@router.get("/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle GitHub OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from GitHub
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_github_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from GitHub")

        # Get user info from GitHub
        user_info = await get_github_user_info(access_token)
        github_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not github_id or not email:
            return create_error_redirect("Failed to get user info from GitHub")

        # Find or create user
        user = find_or_create_user(
            db=db,
            provider=OAuthProvider.GITHUB,
            oauth_id=github_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )

        # Create JWT token
        jwt_token = create_access_token(data={"sub": user.id})
        return create_auth_redirect(jwt_token)

    except Exception as e:
        return create_error_redirect(str(e))


# =============================================================================
# Common Auth Routes
# =============================================================================

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


@router.get("/demo-status")
async def get_demo_status():
    """
    Check if demo mode is enabled.
    In demo mode, authentication is bypassed.

    Returns:
        Demo mode status
    """
    return {
        "demo_mode": settings.demo_mode,
        "message": "Authentication is disabled in demo mode" if settings.demo_mode else "Authentication required"
    }


@router.get("/demo-user", response_model=UserResponse)
async def get_demo_user(db: Session = Depends(get_db)):
    """
    Get or create a demo user for testing without authentication.
    Only available when demo_mode is enabled.

    Returns:
        Demo user information
    """
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is not enabled"
        )

    from backend.auth.jwt_handler import get_or_create_demo_user
    return get_or_create_demo_user(db)


@router.get("/providers")
async def get_available_providers():
    """
    Get list of available OAuth providers with their configuration status.

    Returns:
        Dict of provider names to their availability status
    """
    return {
        "providers": {
            "google": bool(settings.google_client_id and settings.google_client_secret),
            "facebook": bool(settings.facebook_client_id and settings.facebook_client_secret),
            "linkedin": bool(settings.linkedin_client_id and settings.linkedin_client_secret),
            "github": bool(settings.github_client_id and settings.github_client_secret),
        }
    }
