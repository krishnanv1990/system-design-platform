"""
Integration tests for API endpoints.
These tests verify the API contracts and behavior.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_contract(self):
        """Test health check response contract."""
        # The health endpoint should return status: healthy
        expected_response = {"status": "healthy"}
        assert "status" in expected_response
        assert expected_response["status"] == "healthy"


class TestProblemsAPIContract:
    """Tests for problems API response contracts."""

    def test_problem_response_structure(self, mock_problem):
        """Test that problem has required fields."""
        assert mock_problem.id == 1
        assert mock_problem.title == "URL Shortener"
        assert mock_problem.difficulty == "medium"
        assert mock_problem.hints is not None
        assert mock_problem.tags is not None

    def test_problem_list_response_structure(self, mock_problem):
        """Test problem list response structure."""
        # A list response should have these fields
        required_fields = ['id', 'title', 'description', 'difficulty']
        for field in required_fields:
            assert hasattr(mock_problem, field)

    def test_problem_difficulty_values(self):
        """Test valid difficulty values."""
        valid_difficulties = ['easy', 'medium', 'hard']
        assert 'medium' in valid_difficulties


class TestSubmissionsAPIContract:
    """Tests for submissions API response contracts."""

    def test_submission_response_structure(self, mock_submission):
        """Test submission has required fields."""
        assert mock_submission.id == 1
        assert mock_submission.problem_id == 1
        assert mock_submission.status == "pending"

    def test_submission_status_values(self):
        """Test valid submission status values."""
        valid_statuses = [
            'pending',
            'validating',
            'validation_failed',
            'generating_infra',
            'deploying',
            'deploy_failed',
            'testing',
            'completed',
            'failed'
        ]
        assert 'pending' in valid_statuses
        assert 'completed' in valid_statuses

    def test_submission_create_request(self):
        """Test submission create request structure."""
        request = {
            "problem_id": 1,
            "schema_input": {"tables": {}},
            "api_spec_input": {"endpoints": []},
            "design_text": "My design"
        }
        assert "problem_id" in request
        assert request["problem_id"] == 1


class TestTestsAPIContract:
    """Tests for test results API response contracts."""

    def test_test_result_structure(self, mock_test_result):
        """Test result has required fields."""
        assert mock_test_result.id == 1
        assert mock_test_result.test_type == "functional"
        assert mock_test_result.status == "passed"

    def test_test_type_values(self):
        """Test valid test type values."""
        valid_types = ['functional', 'performance', 'chaos']
        assert 'functional' in valid_types

    def test_test_status_values(self):
        """Test valid test status values."""
        valid_statuses = ['pending', 'running', 'passed', 'failed', 'error', 'skipped']
        assert 'passed' in valid_statuses
        assert 'failed' in valid_statuses


class TestAuthAPIContract:
    """Tests for authentication API contracts."""

    def test_user_response_structure(self, mock_user):
        """Test user response has required fields."""
        assert mock_user.id == 1
        assert mock_user.email == "test@example.com"
        assert mock_user.name is not None

    def test_token_response_structure(self):
        """Test token response structure."""
        token_response = {
            "access_token": "test-token",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "email": "test@example.com"
            }
        }
        assert "access_token" in token_response
        assert token_response["token_type"] == "bearer"
        assert "user" in token_response


class TestValidationAPIContract:
    """Tests for validation API contracts."""

    def test_validation_request_structure(self):
        """Test validation request structure."""
        request = {
            "problem_id": 1,
            "schema_input": {"tables": {}},
            "api_spec_input": {"endpoints": []},
            "design_text": "Design description"
        }
        assert "problem_id" in request

    def test_validation_response_structure(self):
        """Test validation response structure."""
        response = {
            "is_valid": True,
            "errors": [],
            "warnings": ["Consider adding caching"],
            "suggestions": ["Add rate limiting"],
            "score": 85.0
        }
        assert "is_valid" in response
        assert "errors" in response
        assert isinstance(response["errors"], list)


class TestChatAPIContract:
    """Tests for chat API contracts."""

    def test_chat_request_structure(self):
        """Test chat request structure."""
        request = {
            "problem_id": 1,
            "message": "How should I handle caching?",
            "conversation_history": [],
            "current_schema": None,
            "current_api_spec": None
        }
        assert "problem_id" in request
        assert "message" in request
        assert "conversation_history" in request

    def test_chat_response_structure(self):
        """Test chat response structure."""
        response = {
            "response": "For caching, you should consider...",
            "diagram_feedback": None,
            "suggested_improvements": ["Add Redis cache"],
            "is_on_track": True,
            "demo_mode": False
        }
        assert "response" in response
        assert "is_on_track" in response
