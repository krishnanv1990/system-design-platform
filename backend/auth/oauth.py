"""
OAuth 2.0 integration for multiple providers.

Supports:
- Google OAuth 2.0
- Facebook OAuth 2.0
- LinkedIn OAuth 2.0
- GitHub OAuth 2.0

Each provider follows the standard OAuth 2.0 authorization code flow:
1. Generate authorization URL with client_id and scopes
2. Exchange authorization code for access token
3. Fetch user info using access token
"""

from typing import Optional
from urllib.parse import urlencode
from enum import Enum

import httpx

from backend.config import get_settings

settings = get_settings()


class OAuthProvider(Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    GITHUB = "github"


# =============================================================================
# Google OAuth Configuration
# =============================================================================

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


async def exchange_google_code_for_token(code: str) -> dict:
    """
    Exchange Google authorization code for access token.

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


# Legacy aliases for backward compatibility
async def exchange_code_for_token(code: str) -> dict:
    """Legacy alias for exchange_google_code_for_token."""
    return await exchange_google_code_for_token(code)


# =============================================================================
# Facebook OAuth Configuration
# =============================================================================

FACEBOOK_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
FACEBOOK_USERINFO_URL = "https://graph.facebook.com/v18.0/me"


def get_facebook_oauth_url(state: Optional[str] = None) -> str:
    """
    Generate the Facebook OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Full OAuth authorization URL
    """
    redirect_uri = f"{settings.backend_url}/api/auth/facebook/callback"

    params = {
        "client_id": settings.facebook_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "email,public_profile",
    }

    if state:
        params["state"] = state

    return f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"


async def exchange_facebook_code_for_token(code: str) -> dict:
    """
    Exchange Facebook authorization code for access token.

    Args:
        code: Authorization code from Facebook callback

    Returns:
        Token response containing access_token

    Raises:
        httpx.HTTPError: If token exchange fails
    """
    redirect_uri = f"{settings.backend_url}/api/auth/facebook/callback"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            FACEBOOK_TOKEN_URL,
            params={
                "client_id": settings.facebook_client_id,
                "client_secret": settings.facebook_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_facebook_user_info(access_token: str) -> dict:
    """
    Fetch user information from Facebook.

    Args:
        access_token: Valid Facebook access token

    Returns:
        User info dict containing id, email, name, picture

    Raises:
        httpx.HTTPError: If user info request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            FACEBOOK_USERINFO_URL,
            params={
                "fields": "id,email,name,picture.width(200).height(200)",
                "access_token": access_token,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Normalize the response to match our expected format
        return {
            "id": data.get("id"),
            "email": data.get("email"),
            "name": data.get("name"),
            "picture": data.get("picture", {}).get("data", {}).get("url"),
        }


# =============================================================================
# LinkedIn OAuth Configuration
# =============================================================================

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def get_linkedin_oauth_url(state: Optional[str] = None) -> str:
    """
    Generate the LinkedIn OAuth authorization URL.

    Uses OpenID Connect scopes for profile and email access.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Full OAuth authorization URL
    """
    redirect_uri = f"{settings.backend_url}/api/auth/linkedin/callback"

    params = {
        "client_id": settings.linkedin_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
    }

    if state:
        params["state"] = state

    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"


async def exchange_linkedin_code_for_token(code: str) -> dict:
    """
    Exchange LinkedIn authorization code for access token.

    Args:
        code: Authorization code from LinkedIn callback

    Returns:
        Token response containing access_token

    Raises:
        httpx.HTTPError: If token exchange fails
    """
    redirect_uri = f"{settings.backend_url}/api/auth/linkedin/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            LINKEDIN_TOKEN_URL,
            data={
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        return response.json()


async def get_linkedin_user_info(access_token: str) -> dict:
    """
    Fetch user information from LinkedIn using OpenID Connect userinfo endpoint.

    Args:
        access_token: Valid LinkedIn access token

    Returns:
        User info dict containing sub (id), email, name, picture

    Raises:
        httpx.HTTPError: If user info request fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()

        # Normalize the response to match our expected format
        return {
            "id": data.get("sub"),
            "email": data.get("email"),
            "name": data.get("name"),
            "picture": data.get("picture"),
        }


# =============================================================================
# GitHub OAuth Configuration
# =============================================================================

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def get_github_oauth_url(state: Optional[str] = None) -> str:
    """
    Generate the GitHub OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Full OAuth authorization URL
    """
    redirect_uri = f"{settings.backend_url}/api/auth/github/callback"

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "user:email read:user",
    }

    if state:
        params["state"] = state

    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


async def exchange_github_code_for_token(code: str) -> dict:
    """
    Exchange GitHub authorization code for access token.

    Args:
        code: Authorization code from GitHub callback

    Returns:
        Token response containing access_token

    Raises:
        httpx.HTTPError: If token exchange fails
    """
    redirect_uri = f"{settings.backend_url}/api/auth/github/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


async def get_github_user_info(access_token: str) -> dict:
    """
    Fetch user information from GitHub.

    GitHub may not return email in the user endpoint if user has set email
    to private, so we also fetch from the emails endpoint.

    Args:
        access_token: Valid GitHub access token

    Returns:
        User info dict containing id, email, name, picture (avatar_url)

    Raises:
        httpx.HTTPError: If user info request fails
    """
    async with httpx.AsyncClient() as client:
        # Get user profile
        user_response = await client.get(
            GITHUB_USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        user_response.raise_for_status()
        user_data = user_response.json()

        # Get email if not in profile
        email = user_data.get("email")
        if not email:
            emails_response = await client.get(
                GITHUB_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            emails_response.raise_for_status()
            emails = emails_response.json()

            # Find primary email
            for email_obj in emails:
                if email_obj.get("primary") and email_obj.get("verified"):
                    email = email_obj.get("email")
                    break

            # Fallback to any verified email
            if not email:
                for email_obj in emails:
                    if email_obj.get("verified"):
                        email = email_obj.get("email")
                        break

        # Normalize the response to match our expected format
        return {
            "id": str(user_data.get("id")),  # GitHub returns numeric ID
            "email": email,
            "name": user_data.get("name") or user_data.get("login"),
            "picture": user_data.get("avatar_url"),
        }


# =============================================================================
# Generic OAuth Functions
# =============================================================================

def get_oauth_url(provider: OAuthProvider, state: Optional[str] = None) -> str:
    """
    Get OAuth URL for any supported provider.

    Args:
        provider: The OAuth provider to use
        state: Optional state parameter for CSRF protection

    Returns:
        Full OAuth authorization URL

    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        OAuthProvider.GOOGLE: get_google_oauth_url,
        OAuthProvider.FACEBOOK: get_facebook_oauth_url,
        OAuthProvider.LINKEDIN: get_linkedin_oauth_url,
        OAuthProvider.GITHUB: get_github_oauth_url,
    }

    if provider not in providers:
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    return providers[provider](state)


async def exchange_oauth_code(provider: OAuthProvider, code: str) -> dict:
    """
    Exchange authorization code for tokens for any supported provider.

    Args:
        provider: The OAuth provider to use
        code: Authorization code from callback

    Returns:
        Token response containing access_token

    Raises:
        ValueError: If provider is not supported
        httpx.HTTPError: If token exchange fails
    """
    providers = {
        OAuthProvider.GOOGLE: exchange_google_code_for_token,
        OAuthProvider.FACEBOOK: exchange_facebook_code_for_token,
        OAuthProvider.LINKEDIN: exchange_linkedin_code_for_token,
        OAuthProvider.GITHUB: exchange_github_code_for_token,
    }

    if provider not in providers:
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    return await providers[provider](code)


async def get_oauth_user_info(provider: OAuthProvider, access_token: str) -> dict:
    """
    Get user info for any supported provider.

    Args:
        provider: The OAuth provider to use
        access_token: Valid access token

    Returns:
        User info dict containing id, email, name, picture

    Raises:
        ValueError: If provider is not supported
        httpx.HTTPError: If user info request fails
    """
    providers = {
        OAuthProvider.GOOGLE: get_google_user_info,
        OAuthProvider.FACEBOOK: get_facebook_user_info,
        OAuthProvider.LINKEDIN: get_linkedin_user_info,
        OAuthProvider.GITHUB: get_github_user_info,
    }

    if provider not in providers:
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    return await providers[provider](access_token)
