"""
Tests for the GCP Assets API.
Tests admin access control and asset retrieval.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.user import User
from backend.models.submission import Submission
from backend.database import get_db
from backend.auth.jwt_handler import get_current_user


class TestAssetsAPIAdminAccess:
    """Tests for admin access control on assets endpoints."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "admin@example.com"
        user.name = "Admin User"
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
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        # Return empty list for submissions query
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        return db

    def test_get_all_assets_admin_success(self, mock_admin_user, mock_db):
        """Test that admin users can access all assets."""
        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/admin/all")

            assert response.status_code == 200
            data = response.json()
            assert "total_submissions" in data
            assert "active_deployments" in data
            assert "assets" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_all_assets_non_admin_forbidden(self, mock_regular_user, mock_db):
        """Test that non-admin users cannot access all assets."""
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/admin/all")

            assert response.status_code == 403
            assert "admin" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_cleanup_candidates_admin_success(self, mock_admin_user, mock_db):
        """Test that admin users can access cleanup candidates."""
        # Setup mock for cleanup candidates query
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/admin/cleanup-candidates")

            assert response.status_code == 200
            data = response.json()
            assert "cutoff_hours" in data
            assert "candidates" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_cleanup_candidates_non_admin_forbidden(self, mock_regular_user, mock_db):
        """Test that non-admin users cannot access cleanup candidates."""
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/admin/cleanup-candidates")

            assert response.status_code == 403
            assert "admin" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()


class TestAssetsAPIWithData:
    """Tests for assets API with actual data."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "admin@example.com"
        user.is_admin = True
        user.is_banned = False
        return user

    @pytest.fixture
    def mock_submission(self, mock_admin_user):
        """Create a mock submission with deployment."""
        submission = MagicMock(spec=Submission)
        submission.id = 1
        submission.deployment_id = "candidate-1"
        submission.endpoint_url = "https://candidate-1.run.app"
        submission.status = "completed"
        submission.created_at = datetime.utcnow()
        submission.validation_feedback = {"deployment": {"image": "gcr.io/proj/img"}}
        # Mock user relationship
        submission.user = mock_admin_user
        return submission

    @pytest.fixture
    def mock_db_with_submissions(self, mock_submission):
        """Create a mock database with submissions."""
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_submission]
        return db

    @patch('backend.api.assets.settings')
    def test_get_all_assets_returns_correct_data(self, mock_settings, mock_admin_user, mock_db_with_submissions):
        """Test that assets API returns correct data structure."""
        mock_settings.gcp_project_id = "test-project"
        mock_settings.gcp_region = "us-central1"

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db_with_submissions
        try:
            client = TestClient(app)
            response = client.get("/api/assets/admin/all")

            assert response.status_code == 200
            data = response.json()
            assert data["total_submissions"] == 1
            assert data["active_deployments"] == 1
            assert len(data["assets"]) == 1
            assert data["assets"][0]["submission_id"] == 1
            assert data["assets"][0]["status"] == "completed"
        finally:
            app.dependency_overrides.clear()


class TestUserAssetsAPI:
    """Tests for user-specific asset endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "user@example.com"
        user.is_admin = False
        user.is_banned = False
        return user

    @pytest.fixture
    def mock_submission(self, mock_user):
        """Create a mock submission."""
        submission = MagicMock(spec=Submission)
        submission.id = 1
        submission.user_id = 1
        submission.deployment_id = "candidate-1"
        submission.endpoint_url = "https://candidate-1.run.app"
        submission.status = "completed"
        submission.created_at = datetime.utcnow()
        submission.validation_feedback = {}
        return submission

    @pytest.fixture
    def mock_db(self, mock_submission):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = mock_submission
        return db

    @patch('backend.api.assets.settings')
    def test_get_submission_assets_own_submission(self, mock_settings, mock_user, mock_db):
        """Test user can access their own submission assets."""
        mock_settings.gcp_project_id = "test-project"
        mock_settings.gcp_region = "us-central1"

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/submission/1")

            assert response.status_code == 200
            data = response.json()
            assert data["submission_id"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_get_submission_assets_not_found(self, mock_user):
        """Test 404 when submission not found."""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/assets/submission/999")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
