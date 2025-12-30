"""
Tests for Admin API endpoints.
Tests deployment management, cleanup, and admin-only operations.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.user import User
from backend.models.submission import Submission
from backend.database import get_db
from backend.auth.jwt_handler import get_current_user
from backend.api.user import require_admin


class TestAdminDeploymentAPI:
    """Tests for admin deployment management endpoints."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "krishnanv2005@gmail.com"
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
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_submission_with_deployment(self):
        """Create a mock submission with an active deployment."""
        user = MagicMock(spec=User)
        user.email = "test@example.com"

        submission = MagicMock(spec=Submission)
        submission.id = 1
        submission.deployment_id = "deploy-123"
        submission.endpoint_url = "https://deploy-123.run.app"
        submission.status = "completed"
        submission.created_at = datetime.utcnow()
        submission.user = user
        submission.validation_feedback = {}
        return submission

    @pytest.fixture
    def mock_submission_no_deployment(self):
        """Create a mock submission without deployment."""
        submission = MagicMock(spec=Submission)
        submission.id = 2
        submission.deployment_id = None
        submission.endpoint_url = None
        submission.status = "pending"
        submission.created_at = datetime.utcnow()
        submission.user = None
        return submission

    def test_get_all_deployments_admin_success(self, mock_admin_user, mock_db, mock_submission_with_deployment):
        """Test getting all deployments as admin."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_submission_with_deployment
        ]

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments")

            assert response.status_code == 200
            data = response.json()
            assert "deployments" in data
            assert "total_count" in data
            assert data["total_count"] == 1
            assert data["deployments"][0]["deployment_id"] == "deploy-123"
        finally:
            app.dependency_overrides.clear()

    def test_get_all_deployments_non_admin_rejected(self, mock_regular_user, mock_db):
        """Test that non-admin cannot get deployments."""
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments")

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_get_all_deployments_empty(self, mock_admin_user, mock_db):
        """Test getting deployments when none exist."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments")

            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 0
            assert data["deployments"] == []
        finally:
            app.dependency_overrides.clear()

    def test_get_deployment_status_success(self, mock_admin_user, mock_db, mock_submission_with_deployment):
        """Test getting a specific deployment status."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission_with_deployment

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments/1")

            assert response.status_code == 200
            data = response.json()
            assert data["deployment_id"] == "deploy-123"
            assert data["user_email"] == "test@example.com"
        finally:
            app.dependency_overrides.clear()

    def test_get_deployment_status_not_found(self, mock_admin_user, mock_db):
        """Test getting a deployment that doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments/999")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_deployment_status_no_deployment(self, mock_admin_user, mock_db, mock_submission_no_deployment):
        """Test getting a submission that has no deployment."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission_no_deployment

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.get("/api/admin/deployments/2")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @patch('backend.api.admin._delete_cloud_run_service')
    def test_teardown_deployment_success(self, mock_delete, mock_admin_user, mock_db, mock_submission_with_deployment):
        """Test tearing down a deployment."""
        mock_delete.return_value = {
            "success": True,
            "submission_id": 1,
            "service_name": "deploy-123",
            "message": "Deleted Cloud Run service: deploy-123"
        }
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission_with_deployment

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/1/teardown")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_teardown_deployment_not_found(self, mock_admin_user, mock_db):
        """Test tearing down a deployment that doesn't exist."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/999/teardown")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_teardown_deployment_no_deployment(self, mock_admin_user, mock_db, mock_submission_no_deployment):
        """Test tearing down a submission with no deployment."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission_no_deployment

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/2/teardown")

            assert response.status_code == 400
            assert "No deployment" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @patch('backend.api.admin._delete_cloud_run_service')
    def test_teardown_deployment_failure(self, mock_delete, mock_admin_user, mock_db, mock_submission_with_deployment):
        """Test handling teardown failure."""
        mock_delete.return_value = {
            "success": False,
            "submission_id": 1,
            "error": "Service deletion failed"
        }
        mock_db.query.return_value.filter.return_value.first.return_value = mock_submission_with_deployment

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/1/teardown")

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    @patch('backend.api.admin._delete_cloud_run_service')
    def test_cleanup_all_deployments_success(self, mock_delete, mock_admin_user, mock_db, mock_submission_with_deployment):
        """Test cleaning up all deployments."""
        mock_delete.return_value = {
            "success": True,
            "submission_id": 1,
            "service_name": "deploy-123",
            "message": "Deleted"
        }
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_submission_with_deployment]

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/cleanup-all")

            assert response.status_code == 200
            data = response.json()
            assert data["cleaned_up"] == 1
            assert data["failed"] == 0
        finally:
            app.dependency_overrides.clear()

    @patch('backend.api.admin._delete_cloud_run_service')
    def test_cleanup_all_deployments_empty(self, mock_delete, mock_admin_user, mock_db):
        """Test cleanup when no deployments exist."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/cleanup-all")

            assert response.status_code == 200
            data = response.json()
            assert data["cleaned_up"] == 0
            assert data["failed"] == 0
        finally:
            app.dependency_overrides.clear()

    @patch('backend.api.admin._delete_cloud_run_service')
    def test_cleanup_all_deployments_partial_failure(self, mock_delete, mock_admin_user, mock_db):
        """Test cleanup when some deployments fail."""
        submission1 = MagicMock(spec=Submission)
        submission1.id = 1
        submission1.deployment_id = "deploy-1"
        submission1.user = MagicMock(email="a@example.com")

        submission2 = MagicMock(spec=Submission)
        submission2.id = 2
        submission2.deployment_id = "deploy-2"
        submission2.user = MagicMock(email="b@example.com")

        mock_delete.side_effect = [
            {"success": True, "submission_id": 1},
            {"success": False, "submission_id": 2, "error": "Failed"}
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = [submission1, submission2]

        app.dependency_overrides[get_current_user] = lambda: mock_admin_user
        app.dependency_overrides[require_admin] = lambda: mock_admin_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/cleanup-all")

            assert response.status_code == 200
            data = response.json()
            assert data["cleaned_up"] == 1
            assert data["failed"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_cleanup_all_non_admin_rejected(self, mock_regular_user, mock_db):
        """Test that non-admin cannot cleanup all deployments."""
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            client = TestClient(app)
            response = client.post("/api/admin/deployments/cleanup-all")

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


class TestDeleteCloudRunService:
    """Tests for the _delete_cloud_run_service helper function."""

    @pytest.fixture
    def mock_submission(self):
        """Create a mock submission."""
        submission = MagicMock(spec=Submission)
        submission.id = 1
        submission.deployment_id = "test-service"
        submission.endpoint_url = "https://test.run.app"
        submission.status = "completed"
        submission.validation_feedback = {}
        return submission

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    @patch('backend.api.admin.get_settings')
    @patch('google.cloud.run_v2.ServicesClient')
    async def test_delete_service_success(self, mock_client_class, mock_get_settings, mock_submission, mock_db):
        """Test successful service deletion."""
        from backend.api.admin import _delete_cloud_run_service

        mock_settings = MagicMock()
        mock_settings.gcp_project_id = "test-project"
        mock_settings.gcp_region = "us-central1"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_operation = MagicMock()
        mock_operation.result.return_value = None
        mock_client.delete_service.return_value = mock_operation
        mock_client_class.return_value = mock_client

        result = await _delete_cloud_run_service(mock_submission, mock_db)

        assert result["success"] is True
        assert result["submission_id"] == 1
        assert mock_submission.status == "cleaned_up"
        assert mock_submission.deployment_id is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.api.admin.get_settings')
    @patch('google.cloud.run_v2.ServicesClient')
    async def test_delete_service_not_found(self, mock_client_class, mock_get_settings, mock_submission, mock_db):
        """Test deletion when service doesn't exist in Cloud Run."""
        from backend.api.admin import _delete_cloud_run_service

        mock_settings = MagicMock()
        mock_settings.gcp_project_id = "test-project"
        mock_settings.gcp_region = "us-central1"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.delete_service.side_effect = Exception("Service not found")
        mock_client_class.return_value = mock_client

        result = await _delete_cloud_run_service(mock_submission, mock_db)

        # Should still succeed - marks as cleaned up even if service already gone
        assert result["success"] is True
        assert mock_submission.status == "cleaned_up"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.api.admin.get_settings')
    @patch('google.cloud.run_v2.ServicesClient')
    async def test_delete_service_exception(self, mock_client_class, mock_get_settings, mock_submission, mock_db):
        """Test handling of unexpected exception."""
        from backend.api.admin import _delete_cloud_run_service

        mock_settings = MagicMock()
        mock_settings.gcp_project_id = "test-project"
        mock_settings.gcp_region = "us-central1"
        mock_get_settings.return_value = mock_settings

        mock_client_class.side_effect = Exception("Connection failed")

        result = await _delete_cloud_run_service(mock_submission, mock_db)

        assert result["success"] is False
        assert "Connection failed" in result["error"]


class TestAdminWarmPoolStatus:
    """Tests for warm pool status endpoint."""

    @patch('backend.api.admin.WarmPoolService')
    def test_get_warm_pool_status(self, mock_warm_pool_class):
        """Test getting warm pool status."""
        mock_pool = MagicMock()
        mock_pool.get_pool_status.return_value = {
            "available_containers": 3,
            "total_containers": 5
        }
        mock_warm_pool_class.return_value = mock_pool

        client = TestClient(app)
        response = client.get("/api/admin/warm-pool/status")

        assert response.status_code == 200
        data = response.json()
        assert "available_containers" in data


class TestAdminDeploymentMode:
    """Tests for deployment mode endpoint."""

    @patch('backend.services.orchestrator.DEPLOYMENT_MODE', 'warm_pool')
    def test_get_deployment_mode(self):
        """Test getting deployment mode."""
        client = TestClient(app)
        response = client.get("/api/admin/deployment-mode")

        assert response.status_code == 200
        data = response.json()
        assert "current_mode" in data
        assert "available_modes" in data


class TestAdminInfrastructureStatus:
    """Tests for infrastructure status endpoint."""

    @patch('backend.api.admin.WarmPoolService')
    def test_get_infrastructure_status(self, mock_warm_pool_class):
        """Test getting infrastructure status."""
        mock_pool = MagicMock()
        mock_pool.infrastructure = {}
        mock_warm_pool_class.return_value = mock_pool

        client = TestClient(app)
        response = client.get("/api/admin/infrastructure/status")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "total_services" in data


class TestExtendDeploymentTimeout:
    """Tests for extending deployment timeout."""

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin user."""
        user = MagicMock(spec=User)
        user.id = 1
        user.email = "krishnanv2005@gmail.com"
        user.is_admin = True
        return user

    @patch('backend.api.admin.cleanup_scheduler')
    def test_extend_timeout_success(self, mock_scheduler, mock_admin_user):
        """Test extending deployment timeout successfully."""
        mock_scheduler.extend_timeout.return_value = {
            "success": True,
            "submission_id": 1,
            "new_timeout": "2024-01-01T12:30:00"
        }

        client = TestClient(app)
        response = client.post("/api/admin/deployments/1/extend?additional_minutes=30")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('backend.api.admin.cleanup_scheduler')
    def test_extend_timeout_failure(self, mock_scheduler, mock_admin_user):
        """Test extending timeout when deployment not found."""
        mock_scheduler.extend_timeout.return_value = {
            "success": False,
            "error": "Deployment not found"
        }

        client = TestClient(app)
        response = client.post("/api/admin/deployments/999/extend?additional_minutes=30")

        assert response.status_code == 400
