"""
Tests for the Audit Service.
Tests audit logging, usage cost tracking, and cost calculations.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models.audit_log import (
    AuditLog,
    UsageCost,
    ActionType,
    CostCategory,
    COST_RATES,
)
from backend.services.audit_service import AuditService


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_action_type_enum_values(self):
        """Test that ActionType enum has expected values."""
        assert ActionType.LOGIN == "login"
        assert ActionType.LOGOUT == "logout"
        assert ActionType.AI_CHAT == "ai_chat"
        assert ActionType.EVALUATE_DIAGRAM == "evaluate_diagram"
        assert ActionType.GENERATE_SUMMARY == "generate_summary"
        assert ActionType.CREATE_SUBMISSION == "create_submission"
        assert ActionType.VIEW_PROBLEM == "view_problem"

    def test_cost_category_enum_values(self):
        """Test that CostCategory enum has expected values."""
        assert CostCategory.AI_INPUT_TOKENS == "ai_input_tokens"
        assert CostCategory.AI_OUTPUT_TOKENS == "ai_output_tokens"
        assert CostCategory.GCP_COMPUTE == "gcp_compute"
        assert CostCategory.GCP_STORAGE == "gcp_storage"

    def test_cost_rates_defined(self):
        """Test that cost rates are defined for all categories."""
        assert CostCategory.AI_INPUT_TOKENS in COST_RATES
        assert CostCategory.AI_OUTPUT_TOKENS in COST_RATES
        assert CostCategory.GCP_COMPUTE in COST_RATES
        assert CostCategory.GCP_STORAGE in COST_RATES
        assert CostCategory.GCP_NETWORK in COST_RATES
        assert CostCategory.GCP_DATABASE in COST_RATES

    def test_cost_rates_are_decimals(self):
        """Test that cost rates are Decimal types for precision."""
        for rate in COST_RATES.values():
            assert isinstance(rate, Decimal)

    def test_audit_log_repr(self):
        """Test AuditLog string representation."""
        log = AuditLog(id=1, user_id=42, action="login")
        assert "id=1" in repr(log)
        assert "user_id=42" in repr(log)
        assert "action='login'" in repr(log)

    def test_usage_cost_repr(self):
        """Test UsageCost string representation."""
        cost = UsageCost(id=1, user_id=42, category="ai_input_tokens", total_cost_usd=Decimal("0.50"))
        assert "id=1" in repr(cost)
        assert "user_id=42" in repr(cost)
        assert "category='ai_input_tokens'" in repr(cost)


class TestAuditService:
    """Tests for AuditService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock(spec=Session)
        return db

    @pytest.fixture
    def audit_service(self, mock_db):
        """Create an AuditService instance with mock db."""
        return AuditService(mock_db)

    def test_log_action_basic(self, mock_db, audit_service):
        """Test basic action logging."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.log_action(
            action=ActionType.LOGIN,
            user_id=1,
        )

        # Verify db.add was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Check the audit log was created
        added_log = mock_db.add.call_args[0][0]
        assert isinstance(added_log, AuditLog)
        assert added_log.action == ActionType.LOGIN.value
        assert added_log.user_id == 1

    def test_log_action_with_details(self, mock_db, audit_service):
        """Test action logging with full details."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.log_action(
            action=ActionType.VIEW_PROBLEM,
            user_id=5,
            resource_type="problem",
            resource_id=42,
            ip_address="192.168.1.1",
            user_agent="TestBrowser/1.0",
            request_path="/api/problems/42",
            request_method="GET",
            response_status=200,
            duration_ms=150,
            details={"extra": "info"},
        )

        added_log = mock_db.add.call_args[0][0]
        assert added_log.resource_type == "problem"
        assert added_log.resource_id == 42
        assert added_log.ip_address == "192.168.1.1"
        assert added_log.request_method == "GET"
        assert added_log.response_status == 200
        assert added_log.duration_ms == 150
        assert added_log.details == {"extra": "info"}

    def test_log_action_anonymous_user(self, mock_db, audit_service):
        """Test action logging for anonymous user."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.log_action(
            action=ActionType.VIEW_PROBLEM,
            user_id=None,  # Anonymous
        )

        added_log = mock_db.add.call_args[0][0]
        assert added_log.user_id is None

    def test_track_ai_usage(self, mock_db, audit_service):
        """Test AI usage tracking."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.track_ai_usage(
            user_id=1,
            audit_log_id=100,
            input_tokens=1000,
            output_tokens=500,
            model="claude-3-5-sonnet-20241022",
        )

        # Should create 2 usage cost entries (input and output)
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

        # Check the created costs
        calls = mock_db.add.call_args_list
        input_cost = calls[0][0][0]
        output_cost = calls[1][0][0]

        assert isinstance(input_cost, UsageCost)
        assert isinstance(output_cost, UsageCost)

        assert input_cost.category == CostCategory.AI_INPUT_TOKENS.value
        assert input_cost.quantity == 1000
        assert input_cost.unit == "tokens"

        assert output_cost.category == CostCategory.AI_OUTPUT_TOKENS.value
        assert output_cost.quantity == 500

    def test_track_ai_usage_cost_calculation(self, mock_db, audit_service):
        """Test that AI usage costs are calculated correctly."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        # Calculate expected costs
        input_tokens = 1_000_000  # 1 million tokens
        output_tokens = 1_000_000  # 1 million tokens

        expected_input_cost = Decimal("3.00")  # $3 per million
        expected_output_cost = Decimal("15.00")  # $15 per million

        result = audit_service.track_ai_usage(
            user_id=1,
            audit_log_id=100,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model="claude-3-5-sonnet-20241022",
        )

        calls = mock_db.add.call_args_list
        input_cost = calls[0][0][0]
        output_cost = calls[1][0][0]

        # Check costs are calculated correctly
        assert input_cost.total_cost_usd == expected_input_cost
        assert output_cost.total_cost_usd == expected_output_cost

    def test_track_ai_usage_with_details(self, mock_db, audit_service):
        """Test AI usage tracking with additional details."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.track_ai_usage(
            user_id=1,
            audit_log_id=100,
            input_tokens=500,
            output_tokens=250,
            model="claude-3-5-sonnet-20241022",
            details={"prompt_type": "chat"},
        )

        calls = mock_db.add.call_args_list
        input_cost = calls[0][0][0]

        assert input_cost.details["model"] == "claude-3-5-sonnet-20241022"
        assert input_cost.details["prompt_type"] == "chat"

    def test_track_gcp_usage(self, mock_db, audit_service):
        """Test GCP usage tracking."""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = audit_service.track_gcp_usage(
            user_id=1,
            audit_log_id=100,
            category=CostCategory.GCP_COMPUTE,
            quantity=3600,  # 1 hour in seconds
            unit="seconds",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        added_cost = mock_db.add.call_args[0][0]
        assert isinstance(added_cost, UsageCost)
        assert added_cost.category == CostCategory.GCP_COMPUTE.value
        assert added_cost.quantity == 3600

    def test_get_user_costs(self, mock_db, audit_service):
        """Test getting user costs summary."""
        # Create mock grouped query results
        mock_results = [
            MagicMock(
                category="ai_input_tokens",
                total_quantity=Decimal("10000"),
                total_cost=Decimal("0.03"),
                count=5,
            ),
            MagicMock(
                category="ai_output_tokens",
                total_quantity=Decimal("5000"),
                total_cost=Decimal("0.075"),
                count=5,
            ),
        ]

        # Setup mock query chain
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_db.query.return_value = mock_query

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        result = audit_service.get_user_costs(
            user_id=1,
            start_date=start_date,
            end_date=end_date,
        )

        assert "total_cost_usd" in result
        assert "categories" in result
        assert result["total_cost_usd"] == 0.105  # 0.03 + 0.075
        assert "ai_input_tokens" in result["categories"]
        assert "ai_output_tokens" in result["categories"]

    def test_get_user_actions(self, mock_db, audit_service):
        """Test getting user actions."""
        mock_logs = [
            MagicMock(
                id=1,
                action="login",
                created_at=datetime.utcnow(),
            ),
            MagicMock(
                id=2,
                action="view_problem",
                created_at=datetime.utcnow() - timedelta(hours=1),
            ),
        ]

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_logs
        mock_db.query.return_value = mock_query

        result = audit_service.get_user_actions(
            user_id=1,
            limit=50,
        )

        assert len(result) == 2
        assert result[0].action == "login"
        assert result[1].action == "view_problem"


class TestAuditServiceIntegration:
    """Integration-style tests for AuditService."""

    def test_full_ai_chat_workflow(self):
        """Test a complete AI chat tracking workflow."""
        mock_db = MagicMock(spec=Session)
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        audit_service = AuditService(mock_db)

        # Step 1: Log the chat action
        audit_log = audit_service.log_action(
            action=ActionType.AI_CHAT,
            user_id=1,
            resource_type="chat",
            ip_address="10.0.0.1",
            request_path="/api/chat/",
            request_method="POST",
            response_status=200,
            duration_ms=2500,
        )

        # Step 2: Track the AI usage
        # Simulate the refresh setting the id
        mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', 1)

        # Re-run to get the log with id set
        audit_log = audit_service.log_action(
            action=ActionType.AI_CHAT,
            user_id=1,
        )

        costs = audit_service.track_ai_usage(
            user_id=1,
            audit_log_id=1,  # Use the log id
            input_tokens=2500,
            output_tokens=1500,
            model="claude-3-5-sonnet-20241022",
            details={"conversation_turn": 3},
        )

        # Verify the workflow completed
        # 2 log_action calls + 1 track_ai_usage call with 2 costs = 4 adds
        assert mock_db.add.call_count >= 3
        assert mock_db.commit.call_count >= 2


class TestCostRateAccuracy:
    """Tests to verify cost rate accuracy."""

    def test_claude_35_sonnet_input_rate(self):
        """Test Claude 3.5 Sonnet input token rate."""
        # Claude 3.5 Sonnet: $3 per million input tokens
        rate = COST_RATES[CostCategory.AI_INPUT_TOKENS]
        assert rate == Decimal("0.000003")

        # 1 million tokens should cost $3
        tokens = 1_000_000
        cost = rate * tokens
        assert cost == Decimal("3.00")

    def test_claude_35_sonnet_output_rate(self):
        """Test Claude 3.5 Sonnet output token rate."""
        # Claude 3.5 Sonnet: $15 per million output tokens
        rate = COST_RATES[CostCategory.AI_OUTPUT_TOKENS]
        assert rate == Decimal("0.000015")

        # 1 million tokens should cost $15
        tokens = 1_000_000
        cost = rate * tokens
        assert cost == Decimal("15.00")

    def test_typical_chat_cost(self):
        """Test cost calculation for a typical chat interaction."""
        input_rate = COST_RATES[CostCategory.AI_INPUT_TOKENS]
        output_rate = COST_RATES[CostCategory.AI_OUTPUT_TOKENS]

        # Typical chat: 1000 input tokens, 500 output tokens
        input_tokens = 1000
        output_tokens = 500

        input_cost = input_rate * input_tokens
        output_cost = output_rate * output_tokens
        total_cost = input_cost + output_cost

        # Should be $0.003 + $0.0075 = $0.0105
        assert input_cost == Decimal("0.003")
        assert output_cost == Decimal("0.0075")
        assert total_cost == Decimal("0.0105")
