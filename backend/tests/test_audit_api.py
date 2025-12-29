"""
Tests for the Audit API endpoints.
Tests usage costs and activity log endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from backend.models.audit_log import AuditLog, UsageCost, ActionType, CostCategory


class TestAuditMiddleware:
    """Tests for the audit middleware."""

    def test_middleware_skips_health_check(self):
        """Test that middleware skips health check endpoint."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/health")
        assert action is None

    def test_middleware_skips_root(self):
        """Test that middleware skips root endpoint."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/")
        assert action is None

    def test_middleware_skips_docs(self):
        """Test that middleware skips documentation endpoints."""
        from backend.middleware.audit_middleware import get_action_for_request

        assert get_action_for_request("GET", "/docs") is None
        assert get_action_for_request("GET", "/redoc") is None
        assert get_action_for_request("GET", "/openapi.json") is None

    def test_middleware_skips_static(self):
        """Test that middleware skips static files."""
        from backend.middleware.audit_middleware import get_action_for_request

        assert get_action_for_request("GET", "/static/style.css") is None
        assert get_action_for_request("GET", "/static/js/app.js") is None

    def test_middleware_maps_login_action(self):
        """Test that middleware correctly maps login action."""
        from backend.middleware.audit_middleware import get_action_for_request

        assert get_action_for_request("POST", "/api/auth/google") == ActionType.LOGIN
        assert get_action_for_request("POST", "/api/auth/github") == ActionType.LOGIN
        assert get_action_for_request("POST", "/api/auth/facebook") == ActionType.LOGIN
        assert get_action_for_request("POST", "/api/auth/linkedin") == ActionType.LOGIN

    def test_middleware_maps_logout_action(self):
        """Test that middleware correctly maps logout action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("POST", "/api/auth/logout")
        assert action == ActionType.LOGOUT

    def test_middleware_maps_chat_action(self):
        """Test that middleware correctly maps chat action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("POST", "/api/chat/message")
        assert action == ActionType.CHAT_MESSAGE

    def test_middleware_maps_summary_action(self):
        """Test that middleware correctly maps summary action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("POST", "/api/chat/summary")
        assert action == ActionType.GENERATE_SUMMARY

    def test_middleware_maps_evaluate_diagram_action(self):
        """Test that middleware correctly maps evaluate diagram action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("POST", "/api/chat/evaluate-diagram")
        assert action == ActionType.EVALUATE_DIAGRAM

    def test_middleware_maps_problem_view(self):
        """Test that middleware correctly maps problem view action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/api/problems/1")
        assert action == ActionType.VIEW_PROBLEM

        action = get_action_for_request("GET", "/api/problems/123")
        assert action == ActionType.VIEW_PROBLEM

    def test_middleware_maps_problems_list(self):
        """Test that middleware correctly maps problems list action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/api/problems")
        assert action == ActionType.LIST_PROBLEMS

    def test_middleware_maps_submission_view(self):
        """Test that middleware correctly maps submission view action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/api/submissions/1")
        assert action == ActionType.VIEW_SUBMISSION

    def test_middleware_maps_submissions_list(self):
        """Test that middleware correctly maps submissions list action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/api/submissions")
        assert action == ActionType.LIST_SUBMISSIONS

    def test_middleware_maps_validate_submission(self):
        """Test that middleware correctly maps validate submission action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("POST", "/api/submissions/validate")
        assert action == ActionType.VALIDATE_SUBMISSION

    def test_middleware_maps_profile_update(self):
        """Test that middleware correctly maps profile update action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("PUT", "/api/users/me")
        assert action == ActionType.UPDATE_PROFILE

        action = get_action_for_request("PATCH", "/api/users/me")
        assert action == ActionType.UPDATE_PROFILE

    def test_middleware_maps_account_delete(self):
        """Test that middleware correctly maps account delete action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("DELETE", "/api/users/me")
        assert action == ActionType.DELETE_ACCOUNT

    def test_middleware_maps_data_export(self):
        """Test that middleware correctly maps data export action."""
        from backend.middleware.audit_middleware import get_action_for_request

        action = get_action_for_request("GET", "/api/users/me/export")
        assert action == ActionType.EXPORT_DATA

    def test_get_client_ip_forwarded(self):
        """Test getting client IP from X-Forwarded-For header."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-for": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip == "203.0.113.195"

    def test_get_client_ip_forwarded_single(self):
        """Test getting client IP from X-Forwarded-For with single IP."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {"x-forwarded-for": "192.168.1.50"}
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.50"

    def test_get_client_ip_real_ip(self):
        """Test getting client IP from X-Real-IP header."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {"x-real-ip": "192.168.1.100"}
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_direct(self):
        """Test getting client IP directly from client."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"

        ip = get_client_ip(mock_request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_unknown(self):
        """Test getting client IP when unavailable."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip == "unknown"

    def test_get_client_ip_priority(self):
        """Test IP header priority (forwarded > real-ip > direct)."""
        from backend.middleware.audit_middleware import get_client_ip

        mock_request = MagicMock()
        mock_request.headers = {
            "x-forwarded-for": "1.1.1.1",
            "x-real-ip": "2.2.2.2",
        }
        mock_request.client = MagicMock()
        mock_request.client.host = "3.3.3.3"

        # Should prefer x-forwarded-for
        ip = get_client_ip(mock_request)
        assert ip == "1.1.1.1"

    def test_get_user_id_from_request_state(self):
        """Test getting user ID from request state."""
        from backend.middleware.audit_middleware import get_user_id_from_request

        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.state.user = MagicMock()
        mock_request.state.user.id = 42

        user_id = get_user_id_from_request(mock_request)
        assert user_id == 42

    def test_get_user_id_from_user_id_attr(self):
        """Test getting user ID from user_id attribute."""
        from backend.middleware.audit_middleware import get_user_id_from_request

        mock_request = MagicMock()
        mock_request.state = MagicMock(spec=["user_id"])
        mock_request.state.user_id = 99

        user_id = get_user_id_from_request(mock_request)
        assert user_id == 99

    def test_get_user_id_anonymous(self):
        """Test getting user ID when no user in state."""
        from backend.middleware.audit_middleware import get_user_id_from_request

        mock_request = MagicMock()
        mock_request.state = MagicMock(spec=[])  # No user attribute

        user_id = get_user_id_from_request(mock_request)
        assert user_id is None


class TestPathActionMapping:
    """Tests for the PATH_ACTION_MAP configuration."""

    def test_all_auth_paths_mapped(self):
        """Test that all auth paths are mapped to LOGIN."""
        from backend.middleware.audit_middleware import PATH_ACTION_MAP

        assert PATH_ACTION_MAP["/api/auth/google"] == ActionType.LOGIN
        assert PATH_ACTION_MAP["/api/auth/facebook"] == ActionType.LOGIN
        assert PATH_ACTION_MAP["/api/auth/linkedin"] == ActionType.LOGIN
        assert PATH_ACTION_MAP["/api/auth/github"] == ActionType.LOGIN
        assert PATH_ACTION_MAP["/api/auth/logout"] == ActionType.LOGOUT

    def test_chat_paths_mapped(self):
        """Test that chat paths are mapped correctly."""
        from backend.middleware.audit_middleware import PATH_ACTION_MAP

        assert PATH_ACTION_MAP["/api/chat/message"] == ActionType.CHAT_MESSAGE
        assert PATH_ACTION_MAP["/api/chat/summary"] == ActionType.GENERATE_SUMMARY
        assert PATH_ACTION_MAP["/api/chat/evaluate-diagram"] == ActionType.EVALUATE_DIAGRAM

    def test_submission_paths_mapped(self):
        """Test that submission paths are mapped correctly."""
        from backend.middleware.audit_middleware import PATH_ACTION_MAP

        assert PATH_ACTION_MAP["/api/submissions"] == ActionType.LIST_SUBMISSIONS
        assert PATH_ACTION_MAP["/api/submissions/validate"] == ActionType.VALIDATE_SUBMISSION


class TestSkipPaths:
    """Tests for the SKIP_PATHS configuration."""

    def test_skip_paths_includes_health(self):
        """Test that health endpoints are skipped."""
        from backend.middleware.audit_middleware import SKIP_PATHS

        assert "/" in SKIP_PATHS
        assert "/health" in SKIP_PATHS

    def test_skip_paths_includes_docs(self):
        """Test that documentation endpoints are skipped."""
        from backend.middleware.audit_middleware import SKIP_PATHS

        assert "/docs" in SKIP_PATHS
        assert "/redoc" in SKIP_PATHS
        assert "/openapi.json" in SKIP_PATHS


class TestAuditMiddlewareClass:
    """Tests for the AuditMiddleware class."""

    def test_middleware_instantiation(self):
        """Test that middleware can be instantiated."""
        from backend.middleware.audit_middleware import AuditMiddleware

        mock_app = MagicMock()
        middleware = AuditMiddleware(mock_app)
        assert middleware is not None


class TestUsageResponseModels:
    """Tests for the usage API response models."""

    def test_usage_cost_item_model(self):
        """Test UsageCostItem model structure."""
        from backend.api.user import UsageCostItem

        item = UsageCostItem(
            id=1,
            category="ai_input_tokens",
            quantity=1000.0,
            unit="tokens",
            unit_cost_usd=0.000003,
            total_cost_usd=0.003,
            details={"model": "claude-3-5-sonnet"},
            created_at=datetime.utcnow(),
        )

        assert item.id == 1
        assert item.category == "ai_input_tokens"
        assert item.quantity == 1000.0

    def test_usage_cost_summary_model(self):
        """Test UsageCostSummary model structure."""
        from backend.api.user import UsageCostSummary

        summary = UsageCostSummary(
            category="ai_output_tokens",
            total_quantity=5000.0,
            unit="tokens",
            total_cost_usd=0.075,
        )

        assert summary.category == "ai_output_tokens"
        assert summary.total_quantity == 5000.0
        assert summary.total_cost_usd == 0.075

    def test_usage_cost_response_model(self):
        """Test UsageCostResponse model structure."""
        from backend.api.user import UsageCostResponse, UsageCostSummary, UsageCostItem

        now = datetime.utcnow()
        response = UsageCostResponse(
            total_cost_usd=0.1,
            start_date=now - timedelta(days=30),
            end_date=now,
            by_category=[
                UsageCostSummary(
                    category="ai_input_tokens",
                    total_quantity=10000.0,
                    unit="tokens",
                    total_cost_usd=0.03,
                ),
            ],
            recent_items=[],
        )

        assert response.total_cost_usd == 0.1
        assert len(response.by_category) == 1
        assert response.by_category[0].category == "ai_input_tokens"

    def test_audit_log_item_model(self):
        """Test AuditLogItem model structure."""
        from backend.api.user import AuditLogItem

        item = AuditLogItem(
            id=1,
            action="login",
            resource_type=None,
            resource_id=None,
            details=None,
            request_path="/api/auth/google",
            request_method="POST",
            response_status=200,
            duration_ms=150,
            created_at=datetime.utcnow(),
        )

        assert item.id == 1
        assert item.action == "login"
        assert item.response_status == 200

    def test_audit_log_response_model(self):
        """Test AuditLogResponse model structure."""
        from backend.api.user import AuditLogResponse, AuditLogItem

        response = AuditLogResponse(
            total_count=5,
            items=[
                AuditLogItem(
                    id=1,
                    action="login",
                    resource_type=None,
                    resource_id=None,
                    details=None,
                    request_path="/api/auth/google",
                    request_method="POST",
                    response_status=200,
                    duration_ms=150,
                    created_at=datetime.utcnow(),
                ),
            ],
        )

        assert response.total_count == 5
        assert len(response.items) == 1
        assert response.items[0].action == "login"
