"""
Google OAuth 2.0 integration.
"""

from typing import Optional
from urllib.parse import urlencode

import httpx

from backend.config import get_settings

settings = get_settings()

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_oauth_url(state: Optional[str] = None) -> str:
    """
    Generate the Google OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Full OAuth authorization URL
    """
    redirect_uri = f"{settings.backend_url}/api/auth/google/callback"

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """
    Exchange authorization code for access token.

    Args:
        code: Authorization code from Google callback

    Returns:
        Token response containing access_token and id_token

    Raises:
        httpx.HTTPError: If token exchange fails
    """
    redirect_uri = f"{settings.backend_url}/api/auth/google/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_google_user_info(access_token: str) -> dict:
    """
    Fetch user information from Google.

    Args:
        access_token: Valid Google access token

    Returns:
        User info dict containing id, email, name, picture

    Raises:
        httpx.HTTPError: If user info request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
