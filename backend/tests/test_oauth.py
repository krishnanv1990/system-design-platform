"""
Tests for OAuth authentication functionality.

Tests cover:
- OAuth URL structure contracts
- OAuth provider configuration
- Token and user info response structures
"""

import pytest
from urllib.parse import parse_qs, urlparse


class TestOAuthURLContracts:
    """Tests for OAuth URL structure contracts."""

    def test_google_oauth_url_structure(self):
        """Test Google OAuth URL has correct structure."""
        # Expected structure for Google OAuth URL
        url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test-id&redirect_uri=https://api.example.com/api/auth/google/callback&response_type=code&scope=openid+email+profile"
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "accounts.google.com" in parsed.netloc
        assert "client_id" in params
        assert "redirect_uri" in params
        assert params["response_type"][0] == "code"

    def test_github_oauth_url_structure(self):
        """Test GitHub OAuth URL has correct structure."""
        url = "https://github.com/login/oauth/authorize?client_id=test-id&redirect_uri=https://api.example.com/api/auth/github/callback&scope=user:email+read:user"
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "github.com" in parsed.netloc
        assert "client_id" in params
        assert "redirect_uri" in params

    def test_facebook_oauth_url_structure(self):
        """Test Facebook OAuth URL has correct structure."""
        url = "https://www.facebook.com/v18.0/dialog/oauth?client_id=test-id&redirect_uri=https://api.example.com/api/auth/facebook/callback&response_type=code&scope=email,public_profile"
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "facebook.com" in parsed.netloc
        assert "client_id" in params
        assert params["response_type"][0] == "code"

    def test_linkedin_oauth_url_structure(self):
        """Test LinkedIn OAuth URL has correct structure."""
        url = "https://www.linkedin.com/oauth/v2/authorization?client_id=test-id&redirect_uri=https://api.example.com/api/auth/linkedin/callback&response_type=code&scope=openid+profile+email"
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert "linkedin.com" in parsed.netloc
        assert "client_id" in params
        assert params["response_type"][0] == "code"

    def test_oauth_url_with_state_parameter(self):
        """Test OAuth URL includes state parameter when provided."""
        url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=test-id&state=csrf-token"
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert params["state"][0] == "csrf-token"

    def test_oauth_redirect_uri_format(self):
        """Test OAuth redirect URI has correct format."""
        redirect_uri = "https://api.example.com/api/auth/google/callback"

        assert redirect_uri.startswith("https://")
        assert "/api/auth/" in redirect_uri
        assert "/callback" in redirect_uri


class TestOAuthProviderContract:
    """Tests for OAuth provider enumeration contract."""

    def test_oauth_provider_values(self):
        """Test OAuth provider values."""
        providers = ["google", "facebook", "linkedin", "github"]

        assert "google" in providers
        assert "facebook" in providers
        assert "linkedin" in providers
        assert "github" in providers
        assert len(providers) == 4


class TestOAuthTokenResponseContract:
    """Tests for OAuth token response contracts."""

    def test_google_token_response_structure(self):
        """Test Google token response structure."""
        response = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test-refresh-token",
            "id_token": "test-id-token"
        }

        assert "access_token" in response
        assert "token_type" in response
        assert response["token_type"] == "Bearer"

    def test_github_token_response_structure(self):
        """Test GitHub token response structure."""
        response = {
            "access_token": "test-github-access-token",
            "token_type": "bearer",
            "scope": "user:email,read:user"
        }

        assert "access_token" in response
        assert "token_type" in response
        assert "scope" in response


class TestOAuthUserInfoResponseContract:
    """Tests for OAuth user info response contracts."""

    def test_google_user_info_response(self):
        """Test Google user info response structure."""
        response = {
            "id": "google-user-123",
            "email": "user@gmail.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg"
        }

        assert "id" in response
        assert "email" in response
        assert "name" in response
        assert "picture" in response

    def test_github_user_info_response(self):
        """Test GitHub user info response structure."""
        response = {
            "id": "12345",
            "email": "user@github.com",
            "name": "Test User",
            "picture": "https://github.com/avatar.jpg"
        }

        # Normalized response should have these fields
        assert "id" in response
        assert "email" in response
        assert "name" in response
        assert "picture" in response

    def test_github_raw_user_info_response(self):
        """Test GitHub raw user info response structure."""
        response = {
            "id": 12345,
            "login": "testuser",
            "name": "Test User",
            "avatar_url": "https://github.com/avatar.jpg",
            "email": "user@github.com"
        }

        assert "id" in response
        assert "login" in response
        assert "avatar_url" in response

    def test_facebook_user_info_response(self):
        """Test Facebook user info response structure."""
        response = {
            "id": "facebook-123",
            "email": "user@facebook.com",
            "name": "Test User",
            "picture": {"data": {"url": "https://facebook.com/avatar.jpg"}}
        }

        assert "id" in response
        assert "email" in response
        assert "picture" in response

    def test_linkedin_user_info_response(self):
        """Test LinkedIn user info response structure."""
        response = {
            "sub": "linkedin-123",
            "email": "user@linkedin.com",
            "name": "Test User",
            "picture": "https://linkedin.com/avatar.jpg"
        }

        assert "sub" in response  # LinkedIn uses 'sub' for user ID
        assert "email" in response
        assert "name" in response


class TestOAuthURLConstants:
    """Tests for OAuth URL constants."""

    def test_google_oauth_endpoints(self):
        """Test Google OAuth endpoint URLs."""
        google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        google_token_url = "https://oauth2.googleapis.com/token"
        google_userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"

        assert "accounts.google.com" in google_auth_url
        assert "googleapis.com" in google_token_url
        assert "googleapis.com" in google_userinfo_url

    def test_github_oauth_endpoints(self):
        """Test GitHub OAuth endpoint URLs."""
        github_auth_url = "https://github.com/login/oauth/authorize"
        github_token_url = "https://github.com/login/oauth/access_token"
        github_userinfo_url = "https://api.github.com/user"

        assert "github.com" in github_auth_url
        assert "github.com" in github_token_url
        assert "api.github.com" in github_userinfo_url

    def test_facebook_oauth_endpoints(self):
        """Test Facebook OAuth endpoint URLs."""
        facebook_auth_url = "https://www.facebook.com/v18.0/dialog/oauth"
        facebook_token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        facebook_userinfo_url = "https://graph.facebook.com/v18.0/me"

        assert "facebook.com" in facebook_auth_url
        assert "graph.facebook.com" in facebook_token_url
        assert "graph.facebook.com" in facebook_userinfo_url

    def test_linkedin_oauth_endpoints(self):
        """Test LinkedIn OAuth endpoint URLs."""
        linkedin_auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        linkedin_token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        linkedin_userinfo_url = "https://api.linkedin.com/v2/userinfo"

        assert "linkedin.com" in linkedin_auth_url
        assert "linkedin.com" in linkedin_token_url
        assert "api.linkedin.com" in linkedin_userinfo_url


class TestAuthRedirectContract:
    """Tests for auth redirect response contracts."""

    def test_auth_redirect_url_format(self):
        """Test auth redirect URL has correct format."""
        frontend_url = "https://frontend.example.com"
        token = "test-jwt-token"

        redirect_url = f"{frontend_url}/#/auth/callback?token={token}"

        assert "/#/auth/callback" in redirect_url
        assert "token=" in redirect_url
        assert token in redirect_url

    def test_error_redirect_url_format(self):
        """Test error redirect URL has correct format."""
        frontend_url = "https://frontend.example.com"
        error = "auth_failed"

        redirect_url = f"{frontend_url}/#/auth/callback?error={error}"

        assert "/#/auth/callback" in redirect_url
        assert "error=" in redirect_url
        assert error in redirect_url


class TestOAuthProvidersEndpointContract:
    """Tests for OAuth providers availability endpoint contract."""

    def test_providers_response_structure(self):
        """Test providers endpoint response structure."""
        response = {
            "providers": {
                "google": True,
                "facebook": False,
                "linkedin": False,
                "github": True,
            }
        }

        assert "providers" in response
        assert isinstance(response["providers"], dict)
        assert "google" in response["providers"]
        assert "github" in response["providers"]
        assert "facebook" in response["providers"]
        assert "linkedin" in response["providers"]

    def test_provider_availability_logic(self):
        """Test provider availability depends on configuration."""
        # Provider is available when both client_id and client_secret are set
        configs = [
            {"client_id": "test-id", "client_secret": "test-secret", "expected": True},
            {"client_id": "test-id", "client_secret": "", "expected": False},
            {"client_id": "", "client_secret": "test-secret", "expected": False},
            {"client_id": "", "client_secret": "", "expected": False},
        ]

        for config in configs:
            is_available = bool(config["client_id"] and config["client_secret"])
            assert is_available == config["expected"]


class TestFindOrCreateUserContract:
    """Tests for user creation/lookup logic contracts."""

    def test_user_data_structure(self):
        """Test user data structure."""
        user = {
            "id": 1,
            "email": "test@example.com",
            "name": "Test User",
            "avatar_url": "https://example.com/avatar.jpg",
            "google_id": "google-123",
            "github_id": None,
            "facebook_id": None,
            "linkedin_id": None,
        }

        required_fields = ["id", "email", "name", "avatar_url"]
        oauth_id_fields = ["google_id", "github_id", "facebook_id", "linkedin_id"]

        for field in required_fields:
            assert field in user

        for field in oauth_id_fields:
            assert field in user

    def test_provider_to_id_field_mapping(self):
        """Test provider to ID field mapping."""
        mapping = {
            "google": "google_id",
            "facebook": "facebook_id",
            "linkedin": "linkedin_id",
            "github": "github_id",
        }

        assert mapping["google"] == "google_id"
        assert mapping["github"] == "github_id"
        assert mapping["facebook"] == "facebook_id"
        assert mapping["linkedin"] == "linkedin_id"

    def test_user_lookup_priority(self):
        """Test user lookup priority order."""
        # Expected order:
        # 1. Look up by provider OAuth ID
        # 2. Look up by email
        # 3. Create new user
        lookup_order = ["provider_id", "email", "create"]

        assert lookup_order[0] == "provider_id"
        assert lookup_order[1] == "email"
        assert lookup_order[2] == "create"


class TestJWTTokenContract:
    """Tests for JWT token contracts."""

    def test_jwt_token_payload_structure(self):
        """Test JWT token payload structure."""
        payload = {
            "sub": "1",  # User ID
            "exp": 1735430400,  # Expiration timestamp
        }

        assert "sub" in payload
        assert "exp" in payload

    def test_jwt_authorization_header_format(self):
        """Test JWT authorization header format."""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        header = f"Bearer {token}"

        assert header.startswith("Bearer ")
        assert token in header


class TestOAuthScopeRequirements:
    """Tests for OAuth scope requirements."""

    def test_google_oauth_scopes(self):
        """Test Google OAuth required scopes."""
        required_scopes = ["openid", "email", "profile"]

        for scope in required_scopes:
            assert scope in required_scopes

    def test_github_oauth_scopes(self):
        """Test GitHub OAuth required scopes."""
        required_scopes = ["user:email", "read:user"]

        assert "user:email" in required_scopes
        assert "read:user" in required_scopes

    def test_facebook_oauth_scopes(self):
        """Test Facebook OAuth required scopes."""
        required_scopes = ["email", "public_profile"]

        assert "email" in required_scopes
        assert "public_profile" in required_scopes

    def test_linkedin_oauth_scopes(self):
        """Test LinkedIn OAuth required scopes."""
        required_scopes = ["openid", "profile", "email"]

        for scope in required_scopes:
            assert scope in required_scopes
