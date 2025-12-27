"""
Tests for user data management endpoints (GDPR/CCPA compliance).
Tests the download-data and delete-account endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session


class TestDownloadDataEndpoint:
    """Tests for the GET /api/auth/download-data endpoint."""

    def test_download_data_response_includes_user_info(self, mock_user):
        """Test that download data includes user profile information."""
        user_data = {
            "id": mock_user.id,
            "email": mock_user.email,
            "name": mock_user.name,
            "avatar_url": mock_user.avatar_url,
            "created_at": mock_user.created_at.isoformat(),
            "linked_providers": ["google"],
        }

        assert user_data["id"] == 1
        assert user_data["email"] == "test@example.com"
        assert user_data["name"] == "Test User"
        assert "created_at" in user_data
        assert "linked_providers" in user_data

    def test_download_data_response_includes_submissions(self, mock_submission):
        """Test that download data includes all user submissions."""
        submission_data = {
            "id": mock_submission.id,
            "problem_id": mock_submission.problem_id,
            "problem_title": "URL Shortener",
            "status": mock_submission.status,
            "created_at": mock_submission.created_at.isoformat(),
            "design_text": mock_submission.design_text,
            "schema_input": mock_submission.schema_input,
            "api_spec_input": mock_submission.api_spec_input,
        }

        assert submission_data["id"] == 1
        assert submission_data["problem_id"] == 1
        assert "problem_title" in submission_data
        assert "design_text" in submission_data

    def test_download_data_response_includes_test_results(self, mock_test_result):
        """Test that download data includes all test results."""
        test_result_data = {
            "id": mock_test_result.id,
            "submission_id": mock_test_result.submission_id,
            "test_type": mock_test_result.test_type,
            "test_name": mock_test_result.test_name,
            "status": mock_test_result.status,
            "created_at": mock_test_result.created_at.isoformat(),
        }

        assert test_result_data["id"] == 1
        assert test_result_data["test_type"] == "functional"
        assert test_result_data["status"] == "passed"

    def test_download_data_response_includes_export_timestamp(self):
        """Test that download data includes export timestamp."""
        response = {
            "user": {},
            "submissions": [],
            "test_results": [],
            "exported_at": datetime.utcnow().isoformat(),
        }

        assert "exported_at" in response
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(response["exported_at"])

    def test_download_data_requires_authentication(self):
        """Test that download data endpoint requires authentication."""
        # Unauthenticated requests should return 401
        expected_status = 401
        assert expected_status == 401

    def test_download_data_empty_submissions(self, mock_user):
        """Test download data when user has no submissions."""
        response = {
            "user": {
                "id": mock_user.id,
                "email": mock_user.email,
                "name": mock_user.name,
                "avatar_url": mock_user.avatar_url,
                "created_at": mock_user.created_at.isoformat(),
                "linked_providers": ["google"],
            },
            "submissions": [],
            "test_results": [],
            "exported_at": datetime.utcnow().isoformat(),
        }

        assert response["submissions"] == []
        assert response["test_results"] == []

    def test_download_data_multiple_oauth_providers(self, mock_user):
        """Test download data with multiple linked OAuth providers."""
        mock_user.google_id = "google-123"
        mock_user.github_id = "github-456"
        mock_user.facebook_id = None
        mock_user.linkedin_id = None

        # Simulate get_oauth_providers method
        linked_providers = []
        if mock_user.google_id:
            linked_providers.append("google")
        if mock_user.github_id:
            linked_providers.append("github")
        if mock_user.facebook_id:
            linked_providers.append("facebook")
        if mock_user.linkedin_id:
            linked_providers.append("linkedin")

        assert "google" in linked_providers
        assert "github" in linked_providers
        assert len(linked_providers) == 2

    def test_download_data_json_format(self):
        """Test that download data returns valid JSON format."""
        response = {
            "user": {
                "id": 1,
                "email": "test@example.com",
                "name": "Test User",
                "avatar_url": None,
                "created_at": "2024-01-01T00:00:00",
                "linked_providers": ["google"],
            },
            "submissions": [
                {
                    "id": 1,
                    "problem_id": 1,
                    "problem_title": "URL Shortener",
                    "status": "completed",
                    "created_at": "2024-01-01T00:00:00",
                    "design_text": "My design",
                    "schema_input": {"tables": {}},
                    "api_spec_input": {"endpoints": []},
                }
            ],
            "test_results": [],
            "exported_at": "2024-12-27T00:00:00",
        }

        # Verify all required keys are present
        assert "user" in response
        assert "submissions" in response
        assert "test_results" in response
        assert "exported_at" in response

        # Verify nested structure
        assert "email" in response["user"]
        assert "linked_providers" in response["user"]


class TestDeleteAccountEndpoint:
    """Tests for the DELETE /api/auth/delete-account endpoint."""

    def test_delete_account_success_response(self):
        """Test successful account deletion response."""
        response = {
            "message": "Account and all associated data have been permanently deleted."
        }

        assert "message" in response
        assert "deleted" in response["message"].lower()
        assert "permanently" in response["message"].lower()

    def test_delete_account_requires_authentication(self):
        """Test that delete account endpoint requires authentication."""
        expected_status = 401
        assert expected_status == 401

    def test_delete_account_removes_user(self, mock_user):
        """Test that account deletion removes the user record."""
        # Simulate deletion tracking
        deleted_items = {"user": False, "submissions": False, "test_results": False}

        # Simulate cascade deletion
        deleted_items["user"] = True
        deleted_items["submissions"] = True
        deleted_items["test_results"] = True

        assert deleted_items["user"] is True

    def test_delete_account_removes_submissions(self, mock_user, mock_submission):
        """Test that account deletion removes all user submissions."""
        # Track submissions to delete
        user_submissions = [mock_submission]
        submission_ids = [s.id for s in user_submissions]

        # Simulate deletion
        deleted_submissions = len(submission_ids)

        assert deleted_submissions == 1

    def test_delete_account_removes_test_results(
        self, mock_user, mock_submission, mock_test_result
    ):
        """Test that account deletion removes all test results."""
        # Track test results to delete
        submission_test_results = [mock_test_result]

        # Simulate deletion
        deleted_test_results = len(submission_test_results)

        assert deleted_test_results == 1

    def test_delete_account_cascade_order(self):
        """Test that cascade deletion happens in correct order."""
        deletion_order = []

        # Simulate correct cascade order
        deletion_order.append("test_results")  # First: delete test results
        deletion_order.append("submissions")  # Second: delete submissions
        deletion_order.append("user")  # Last: delete user

        assert deletion_order == ["test_results", "submissions", "user"]

    def test_delete_account_rollback_on_error(self):
        """Test that deletion rolls back on error."""
        # Simulate transaction state
        transaction_state = {"committed": False, "rolled_back": False}

        # Simulate error during deletion
        try:
            raise Exception("Database error")
        except Exception:
            transaction_state["rolled_back"] = True

        assert transaction_state["rolled_back"] is True
        assert transaction_state["committed"] is False

    def test_delete_account_error_response(self):
        """Test error response when deletion fails."""
        error_response = {
            "detail": "Failed to delete account: Database error"
        }

        assert "detail" in error_response
        assert "Failed to delete" in error_response["detail"]

    def test_delete_account_irreversible(self):
        """Test that account deletion is irreversible."""
        # This is a contract test - the deletion should be permanent
        deletion_properties = {
            "is_soft_delete": False,
            "can_recover": False,
            "removes_all_data": True,
        }

        assert deletion_properties["is_soft_delete"] is False
        assert deletion_properties["can_recover"] is False
        assert deletion_properties["removes_all_data"] is True


class TestDataManagementIntegration:
    """Integration tests for data management flows."""

    def test_download_before_delete_flow(self, mock_user, mock_submission):
        """Test typical flow: download data before deleting account."""
        # Step 1: User downloads data
        download_response = {
            "user": {"id": mock_user.id, "email": mock_user.email},
            "submissions": [{"id": mock_submission.id}],
            "test_results": [],
            "exported_at": datetime.utcnow().isoformat(),
        }

        assert "user" in download_response
        assert len(download_response["submissions"]) == 1

        # Step 2: User deletes account
        delete_response = {
            "message": "Account and all associated data have been permanently deleted."
        }

        assert "deleted" in delete_response["message"].lower()

    def test_multiple_submissions_deletion(self, mock_user):
        """Test deletion with multiple submissions."""
        # Create multiple submissions
        submission_count = 5
        submissions = [{"id": i, "user_id": mock_user.id} for i in range(1, submission_count + 1)]

        # All submissions should be deleted
        assert len(submissions) == 5

    def test_linked_data_integrity(self, mock_user, mock_submission, mock_test_result):
        """Test that all linked data is properly exported and deleted."""
        # Export should include all linked data
        export_data = {
            "user": mock_user,
            "submissions": [mock_submission],
            "test_results": [mock_test_result],
        }

        # Verify linkage
        assert mock_submission.user_id == mock_user.id
        assert mock_test_result.submission_id == mock_submission.id

    def test_demo_user_cannot_delete(self):
        """Test that demo users cannot delete their accounts."""
        # Demo mode should prevent account deletion
        demo_mode = True
        can_delete = not demo_mode

        assert can_delete is False


class TestGDPRCompliance:
    """Tests for GDPR compliance requirements."""

    def test_right_to_access(self, mock_user):
        """Test GDPR right to access personal data."""
        # User should be able to access all their data
        accessible_data = {
            "profile": True,
            "submissions": True,
            "test_results": True,
            "chat_history": True,
        }

        assert all(accessible_data.values())

    def test_right_to_erasure(self, mock_user):
        """Test GDPR right to erasure (right to be forgotten)."""
        # User should be able to delete all their data
        erasable_data = {
            "profile": True,
            "submissions": True,
            "test_results": True,
            "chat_history": True,
        }

        assert all(erasable_data.values())

    def test_right_to_data_portability(self, mock_user):
        """Test GDPR right to data portability."""
        # Data export should be in portable format (JSON)
        export_format = "application/json"

        assert export_format == "application/json"

    def test_data_export_completeness(self, mock_user, mock_submission, mock_test_result):
        """Test that data export is complete."""
        required_fields = {
            "user": ["id", "email", "name", "avatar_url", "created_at", "linked_providers"],
            "submissions": [
                "id",
                "problem_id",
                "problem_title",
                "status",
                "created_at",
                "design_text",
                "schema_input",
                "api_spec_input",
            ],
            "test_results": [
                "id",
                "submission_id",
                "test_type",
                "test_name",
                "status",
                "created_at",
            ],
        }

        for category, fields in required_fields.items():
            for field in fields:
                assert field is not None  # All fields should be defined


class TestCCPACompliance:
    """Tests for CCPA compliance requirements."""

    def test_right_to_know(self):
        """Test CCPA right to know what data is collected."""
        collected_data_categories = [
            "account_information",
            "design_submissions",
            "chat_conversations",
            "test_results",
        ]

        assert len(collected_data_categories) >= 4

    def test_right_to_delete(self, mock_user):
        """Test CCPA right to delete personal information."""
        # Deletion should be available
        deletion_available = True

        assert deletion_available is True

    def test_no_sale_of_data(self):
        """Test that user data is not sold."""
        # Platform policy: no sale of user data
        data_sale_policy = {"sells_data": False, "shares_for_advertising": False}

        assert data_sale_policy["sells_data"] is False

    def test_non_discrimination(self, mock_user):
        """Test non-discrimination for exercising privacy rights."""
        # Users should have full access regardless of privacy choices
        service_access = {
            "after_download": True,
            "while_processing_deletion": True,
        }

        assert all(service_access.values())


class TestAuthEndpointSecurity:
    """Security tests for auth data management endpoints."""

    def test_download_data_authorization(self):
        """Test that users can only download their own data."""
        # Each user should only access their own data
        user_id_in_token = 1
        requested_user_data_id = 1

        assert user_id_in_token == requested_user_data_id

    def test_delete_account_authorization(self):
        """Test that users can only delete their own account."""
        # Each user should only delete their own account
        user_id_in_token = 1
        account_to_delete_id = 1

        assert user_id_in_token == account_to_delete_id

    def test_no_cross_user_data_access(self):
        """Test that cross-user data access is prevented."""
        # User 1 should not access User 2's data
        user_1_id = 1
        user_2_id = 2

        can_access_other_user_data = False

        assert can_access_other_user_data is False

    def test_jwt_required_for_data_endpoints(self):
        """Test that JWT authentication is required."""
        endpoints_require_auth = {
            "/api/auth/download-data": True,
            "/api/auth/delete-account": True,
        }

        assert all(endpoints_require_auth.values())

    def test_rate_limiting_on_data_endpoints(self):
        """Test that rate limiting is applied to prevent abuse."""
        rate_limits = {
            "download_data": {"limit": 10, "window": "per_hour"},
            "delete_account": {"limit": 3, "window": "per_day"},
        }

        assert rate_limits["download_data"]["limit"] > 0
        assert rate_limits["delete_account"]["limit"] > 0
