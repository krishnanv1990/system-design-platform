"""
Authentication API routes.

Handles OAuth flows for multiple providers and JWT token management.
Supports Google, Facebook, LinkedIn, and GitHub authentication.
"""

import base64
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
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


def encode_oauth_state(source: str = "user") -> str:
    """Encode OAuth state with source info (user or admin)."""
    state_data = {"source": source}
    return base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()


def decode_oauth_state(state: Optional[str]) -> str:
    """Decode OAuth state to get source info. Returns 'user' by default."""
    if not state:
        return "user"
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        return state_data.get("source", "user")
    except Exception:
        return "user"


def get_redirect_url(source: str) -> str:
    """Get the appropriate frontend URL based on source."""
    if source == "admin":
        return settings.admin_url
    return settings.frontend_url


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


def create_auth_redirect(token: str, source: str = "user") -> RedirectResponse:
    """Create redirect to frontend with JWT token."""
    frontend_url = get_redirect_url(source)
    # Admin uses BrowserRouter (non-hash URLs), user portal uses HashRouter
    if source == "admin":
        redirect_url = f"{frontend_url}/auth/callback?token={token}"
    else:
        redirect_url = f"{frontend_url}/#/auth/callback?token={token}"
    print(f"OAuth redirect URL: {redirect_url[:100]}...")
    return RedirectResponse(url=redirect_url)


def create_error_redirect(error: str, source: str = "user") -> RedirectResponse:
    """Create redirect to frontend with error message."""
    frontend_url = get_redirect_url(source)
    # Admin uses BrowserRouter (non-hash URLs), user portal uses HashRouter
    if source == "admin":
        redirect_url = f"{frontend_url}/auth/callback?error={error}"
    else:
        redirect_url = f"{frontend_url}/#/auth/callback?error={error}"
    return RedirectResponse(url=redirect_url)


# =============================================================================
# Google OAuth Routes
# =============================================================================

@router.get("/google")
async def google_auth(source: str = Query("user", description="Login source: 'user' or 'admin'")):
    """
    Initiate Google OAuth flow.
    Redirects user to Google's authorization page.

    Args:
        source: Where the login originated from ('user' or 'admin')
    """
    state = encode_oauth_state(source)
    oauth_url = get_google_oauth_url(state=state)
    return RedirectResponse(url=oauth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Handle Google OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from Google
        state: OAuth state containing source info
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    source = decode_oauth_state(state)
    try:
        # Exchange code for tokens
        token_data = await exchange_google_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from Google", source)

        # Get user info from Google
        user_info = await get_google_user_info(access_token)
        google_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not google_id or not email:
            return create_error_redirect("Failed to get user info from Google", source)

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
        jwt_token = create_access_token(data={"sub": str(user.id)})
        return create_auth_redirect(jwt_token, source)

    except Exception as e:
        return create_error_redirect(str(e), source)


# =============================================================================
# Facebook OAuth Routes
# =============================================================================

@router.get("/facebook")
async def facebook_auth(source: str = Query("user", description="Login source: 'user' or 'admin'")):
    """
    Initiate Facebook OAuth flow.
    Redirects user to Facebook's authorization page.

    Args:
        source: Where the login originated from ('user' or 'admin')
    """
    state = encode_oauth_state(source)
    oauth_url = get_facebook_oauth_url(state=state)
    return RedirectResponse(url=oauth_url)


@router.get("/facebook/callback")
async def facebook_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Handle Facebook OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from Facebook
        state: OAuth state containing source info
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    source = decode_oauth_state(state)
    try:
        # Exchange code for tokens
        token_data = await exchange_facebook_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from Facebook", source)

        # Get user info from Facebook
        user_info = await get_facebook_user_info(access_token)
        facebook_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not facebook_id or not email:
            return create_error_redirect("Failed to get user info from Facebook", source)

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
        jwt_token = create_access_token(data={"sub": str(user.id)})
        return create_auth_redirect(jwt_token, source)

    except Exception as e:
        return create_error_redirect(str(e), source)


# =============================================================================
# LinkedIn OAuth Routes
# =============================================================================

@router.get("/linkedin")
async def linkedin_auth(source: str = Query("user", description="Login source: 'user' or 'admin'")):
    """
    Initiate LinkedIn OAuth flow.
    Redirects user to LinkedIn's authorization page.

    Args:
        source: Where the login originated from ('user' or 'admin')
    """
    state = encode_oauth_state(source)
    oauth_url = get_linkedin_oauth_url(state=state)
    return RedirectResponse(url=oauth_url)


@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Handle LinkedIn OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from LinkedIn
        state: OAuth state containing source info
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    source = decode_oauth_state(state)
    try:
        # Exchange code for tokens
        token_data = await exchange_linkedin_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from LinkedIn", source)

        # Get user info from LinkedIn
        user_info = await get_linkedin_user_info(access_token)
        linkedin_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not linkedin_id or not email:
            return create_error_redirect("Failed to get user info from LinkedIn", source)

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
        jwt_token = create_access_token(data={"sub": str(user.id)})
        return create_auth_redirect(jwt_token, source)

    except Exception as e:
        return create_error_redirect(str(e), source)


# =============================================================================
# GitHub OAuth Routes
# =============================================================================

@router.get("/github")
async def github_auth(source: str = Query("user", description="Login source: 'user' or 'admin'")):
    """
    Initiate GitHub OAuth flow.
    Redirects user to GitHub's authorization page.

    Args:
        source: Where the login originated from ('user' or 'admin')
    """
    state = encode_oauth_state(source)
    oauth_url = get_github_oauth_url(state=state)
    return RedirectResponse(url=oauth_url)


@router.get("/github/callback")
async def github_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Handle GitHub OAuth callback.
    Exchanges code for tokens, creates/updates user, and returns JWT.

    Args:
        code: Authorization code from GitHub
        state: OAuth state containing source info
        db: Database session

    Returns:
        Redirect to frontend with JWT token in URL params
    """
    source = decode_oauth_state(state)
    try:
        # Exchange code for tokens
        token_data = await exchange_github_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return create_error_redirect("Failed to get access token from GitHub", source)

        # Get user info from GitHub
        user_info = await get_github_user_info(access_token)
        github_id = user_info.get("id")
        email = user_info.get("email")
        name = user_info.get("name")
        avatar_url = user_info.get("picture")

        if not github_id or not email:
            return create_error_redirect("Failed to get user info from GitHub", source)

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
        jwt_token = create_access_token(data={"sub": str(user.id)})
        return create_auth_redirect(jwt_token, source)

    except Exception as e:
        return create_error_redirect(str(e), source)


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


# =============================================================================
# Data Management Routes (GDPR/CCPA Compliance)
# =============================================================================

@router.get("/download-data")
async def download_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download all user data (GDPR/CCPA compliance).

    Returns all data associated with the user including:
    - User profile information
    - All submissions and designs
    - Test results

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        Complete user data export
    """
    from backend.models.submission import Submission
    from backend.models.test_result import TestResult
    from backend.models.problem import Problem
    from datetime import datetime

    # Get all user submissions with problem titles
    submissions = (
        db.query(Submission, Problem.title)
        .join(Problem, Submission.problem_id == Problem.id)
        .filter(Submission.user_id == current_user.id)
        .all()
    )

    # Get all test results for user's submissions
    submission_ids = [s[0].id for s in submissions]
    test_results = (
        db.query(TestResult)
        .filter(TestResult.submission_id.in_(submission_ids))
        .all()
        if submission_ids
        else []
    )

    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "avatar_url": current_user.avatar_url,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "linked_providers": current_user.get_oauth_providers(),
        },
        "submissions": [
            {
                "id": sub.id,
                "problem_id": sub.problem_id,
                "problem_title": title,
                "status": sub.status,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "design_text": sub.design_text,
                "schema_input": sub.schema_input,
                "api_spec_input": sub.api_spec_input,
            }
            for sub, title in submissions
        ],
        "test_results": [
            {
                "id": tr.id,
                "submission_id": tr.submission_id,
                "test_type": tr.test_type,
                "test_name": tr.test_name,
                "status": tr.status,
                "created_at": tr.created_at.isoformat() if tr.created_at else None,
            }
            for tr in test_results
        ],
        "exported_at": datetime.utcnow().isoformat(),
    }


@router.delete("/delete-account")
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete user account and all associated data.

    This is a destructive operation that permanently removes:
    - User profile and account
    - All submissions and designs
    - All test results
    - All chat history (if stored)

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        Confirmation message
    """
    from backend.models.submission import Submission
    from backend.models.test_result import TestResult

    try:
        # Get all user submissions
        submissions = db.query(Submission).filter(Submission.user_id == current_user.id).all()
        submission_ids = [s.id for s in submissions]

        # Delete all test results for user's submissions
        if submission_ids:
            db.query(TestResult).filter(TestResult.submission_id.in_(submission_ids)).delete(
                synchronize_session=False
            )

        # Delete all user submissions
        db.query(Submission).filter(Submission.user_id == current_user.id).delete(
            synchronize_session=False
        )

        # Delete the user
        db.delete(current_user)
        db.commit()

        return {"message": "Account and all associated data have been permanently deleted."}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}",
        )
