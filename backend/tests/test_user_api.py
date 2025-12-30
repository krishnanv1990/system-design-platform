"""
Tests for the User Profile API.
Tests profile retrieval, updates, contact support, and admin functions.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.user import User
from backend.api.user import require_admin
from backend.database import get_db
from backend.auth.jwt_handler import get_current_user


class TestUserProfileAPI:
    """Tests for user profile endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.name = "Test User"
        user.display_name = "TestDisplayName"
        user.avatar_url = "https://example.com/avatar.jpg"
        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        user.is_admin = False
        user.created_at = datetime.utcnow()
        user.get_oauth_providers = MagicMock(return_value=["google"])
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock(spec=User)
        user.id = 2
        user.email = "admin@example.com"
        user.name = "Admin User"
        user.display_name = None
        user.avatar_url = None
        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        user.is_admin = True
        user.created_at = datetime.utcnow()
        user.get_oauth_providers = MagicMock(return_value=["google"])
        return user

    @pytest.fixture
    def mock_banned_user(self):
        """Create a mock banned user."""
        user = MagicMock(spec=User)
        user.id = 3
        user.email = "banned@example.com"
        user.name = "Banned User"
        user.display_name = None
        user.avatar_url = None
        user.is_banned = True
        user.ban_reason = "Policy violations"
        user.banned_at = datetime.utcnow()
        user.is_admin = False
        user.created_at = datetime.utcnow()
        user.get_oauth_providers = MagicMock(return_value=[])
        return user

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        return db

    def test_get_profile_success(self, mock_user, mock_db):
        """Test getting user profile successfully."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/user/profile")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_user.id
            assert data["email"] == mock_user.email
            assert data["display_name"] == mock_user.display_name
            assert data["linked_providers"] == ["google"]
        finally:
            app.dependency_overrides.clear()

    def test_update_profile_display_name(self, mock_user, mock_db):
        """Test updating display name."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/user/profile",
                json={"display_name": "NewDisplayName"}
            )

            assert response.status_code == 200
            # Check that display_name was updated
            assert mock_user.display_name == "NewDisplayName"
            mock_db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_update_profile_banned_user(self, mock_banned_user, mock_db):
        """Test that banned users cannot update profile."""
        app.dependency_overrides[get_current_user] = lambda: mock_banned_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/user/profile",
                json={"display_name": "NewName"}
            )

            assert response.status_code == 403
            assert "suspended" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_update_profile_display_name_too_long(self, mock_user, mock_db):
        """Test that display name length is validated."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.put(
                "/api/user/profile",
                json={"display_name": "x" * 150}  # Too long
            )

            assert response.status_code == 400
            assert "100 characters" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_contact_support_success(self, mock_user, mock_db):
        """Test contacting support successfully."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/user/contact-support",
                json={
                    "subject": "Test Subject",
                    "message": "Test message content"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "ticket_id" in data
            assert data["ticket_id"].startswith("SDP-")
        finally:
            app.dependency_overrides.clear()


class TestAdminUserAPI:
    """Tests for admin user management endpoints."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user with whitelisted email."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "krishnanv2005@gmail.com"  # Must match ADMIN_EMAILS whitelist
        user.name = "Admin"
        user.is_admin = True
        user.is_banned = False
        return user

    @pytest.fixture
    def mock_regular_user(self):
        """Create a mock regular user."""
        user = MagicMock(spec=User)
        user.id = 2
        user.email = "user@example.com"
        user.name = "Regular User"
        user.is_admin = False
        user.is_banned = False
        return user

    @pytest.fixture
    def mock_banned_user(self):
        """Create a mock banned user."""
        user = MagicMock(spec=User)
        user.id = 3
        user.email = "banned@example.com"
        user.name = "Banned User"
        user.display_name = None
        user.is_admin = False
        user.is_banned = True
        user.ban_reason = "Jailbreak attempts"
        user.banned_at = datetime.utcnow()
        user.created_at = datetime.utcnow()
        return user

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    def test_list_users_admin_only(self, mock_regular_user, mock_db):
        """Test that non-admin cannot list users."""
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/user/admin/users")

            assert response.status_code == 403
            assert "admin" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_unban_user_success(self, mock_admin_user, mock_banned_user, mock_db):
        """Test unbanning a user successfully."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_banned_user

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/user/admin/unban",
                json={"user_id": 3, "reason": "Appeal approved"}
            )

            assert response.status_code == 200
            assert mock_banned_user.is_banned is False
            mock_db.commit.assert_called()
        finally:
            app.dependency_overrides.clear()

    def test_unban_non_banned_user(self, mock_admin_user, mock_regular_user, mock_db):
        """Test unbanning a user that isn't banned."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_regular_user

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/user/admin/unban",
                json={"user_id": 2}
            )

            assert response.status_code == 400
            assert "not banned" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_unban_user_not_found(self, mock_admin_user, mock_db):
        """Test unbanning a user that doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post(
                "/api/user/admin/unban",
                json={"user_id": 999}
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestRequireAdminDependency:
    """Tests for the require_admin dependency."""

    def test_require_admin_with_admin_user(self):
        """Test that admin users with whitelisted email pass the check."""
        admin_user = MagicMock(spec=User)
        admin_user.is_admin = True
        admin_user.email = "krishnanv2005@gmail.com"  # Must match ADMIN_EMAILS whitelist

        # Should not raise - call the function directly
        result = require_admin(admin_user)
        assert result is admin_user

    def test_require_admin_with_regular_user(self):
        """Test that regular users are rejected."""
        regular_user = MagicMock(spec=User)
        regular_user.is_admin = False

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            require_admin(regular_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()
