"""
Pytest configuration and fixtures for backend tests.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = 1
    user.google_id = "google-123"
    user.email = "test@example.com"
    user.name = "Test User"
    user.avatar_url = "https://example.com/avatar.jpg"
    user.created_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_problem():
    """Create a mock problem."""
    problem = MagicMock()
    problem.id = 1
    problem.title = "URL Shortener"
    problem.description = "Design a URL shortening service like bit.ly"
    problem.difficulty = "medium"
    problem.expected_schema = {"tables": {"urls": {"columns": {"id": "bigserial", "short_code": "varchar"}}}}
    problem.expected_api_spec = {"endpoints": [{"method": "POST", "path": "/shorten"}]}
    problem.hints = ["Consider using a hash function", "Think about collision handling"]
    problem.tags = ["distributed-systems", "hashing"]
    problem.created_at = datetime.utcnow()
    return problem


@pytest.fixture
def mock_submission(mock_user, mock_problem):
    """Create a mock submission."""
    submission = MagicMock()
    submission.id = 1
    submission.problem_id = mock_problem.id
    submission.user_id = mock_user.id
    submission.status = "pending"
    submission.schema_input = {"tables": {"urls": {}}}
    submission.api_spec_input = {"endpoints": []}
    submission.design_text = "My design description"
    submission.created_at = datetime.utcnow()
    submission.updated_at = datetime.utcnow()
    return submission


@pytest.fixture
def mock_test_result(mock_submission):
    """Create a mock test result."""
    test_result = MagicMock()
    test_result.id = 1
    test_result.submission_id = mock_submission.id
    test_result.test_type = "functional"
    test_result.test_name = "test_create_short_url"
    test_result.status = "passed"
    test_result.duration_ms = 150
    test_result.details = {"response": {"status": 200}}
    test_result.created_at = datetime.utcnow()
    return test_result


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    mock = MagicMock()
    mock.database_url = "sqlite:///:memory:"
    mock.jwt_secret_key = "test-secret-key"
    mock.jwt_algorithm = "HS256"
    mock.jwt_expire_minutes = 60
    mock.demo_mode = True
    mock.anthropic_api_key = "test-api-key"
    mock.gcp_project_id = "test-project"
    mock.gcp_region = "us-central1"
    mock.frontend_url = "http://localhost:5173"
    mock.backend_url = "http://localhost:8000"
    return mock
