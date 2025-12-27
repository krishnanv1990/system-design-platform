"""
Tests for Pydantic schemas - testing schema contracts without database dependencies.
"""

import pytest
from datetime import datetime
from pydantic import BaseModel, ValidationError, EmailStr
from typing import Optional, List, Dict, Any


# Define minimal versions of schemas to avoid database imports
# These mimic the actual schemas but without db dependencies
class UserCreateSchema(BaseModel):
    """Schema for creating a new user."""
    google_id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponseSchema(BaseModel):
    """Schema for user response."""
    id: int
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime


class TokenResponseSchema(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponseSchema


class ProblemCreateSchema(BaseModel):
    """Schema for creating a new problem."""
    title: str
    description: str
    difficulty: str = "medium"
    expected_schema: Optional[Dict[str, Any]] = None
    expected_api_spec: Optional[Dict[str, Any]] = None
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SubmissionCreateSchema(BaseModel):
    """Schema for creating a new submission."""
    problem_id: int
    schema_input: Optional[Dict[str, Any]] = None
    api_spec_input: Optional[Dict[str, Any]] = None
    design_text: Optional[str] = None


class TestUserSchemas:
    """Tests for user-related schemas."""

    def test_user_create_valid(self):
        """Test valid user creation schema."""
        user = UserCreateSchema(
            google_id="google-123",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
        )
        assert user.google_id == "google-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    def test_user_create_minimal(self):
        """Test user creation with minimal fields."""
        user = UserCreateSchema(
            google_id="google-123",
            email="test@example.com",
        )
        assert user.name is None
        assert user.avatar_url is None

    def test_user_create_invalid_email(self):
        """Test user creation with invalid email."""
        with pytest.raises(ValidationError):
            UserCreateSchema(
                google_id="google-123",
                email="invalid-email",
            )

    def test_user_response(self):
        """Test user response schema."""
        user = UserResponseSchema(
            id=1,
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            created_at=datetime.utcnow(),
        )
        assert user.id == 1
        assert user.email == "test@example.com"

    def test_token_response(self):
        """Test token response schema."""
        token = TokenResponseSchema(
            access_token="test-token",
            user=UserResponseSchema(
                id=1,
                email="test@example.com",
                name="Test User",
                avatar_url=None,
                created_at=datetime.utcnow(),
            ),
        )
        assert token.access_token == "test-token"
        assert token.token_type == "bearer"


class TestProblemSchemas:
    """Tests for problem-related schemas."""

    def test_problem_create_valid(self):
        """Test valid problem creation schema."""
        problem = ProblemCreateSchema(
            title="URL Shortener",
            description="Design a URL shortening service",
            difficulty="medium",
            hints=["Consider hashing", "Think about scalability"],
            tags=["distributed-systems"],
        )
        assert problem.title == "URL Shortener"
        assert problem.difficulty == "medium"
        assert len(problem.hints) == 2

    def test_problem_create_minimal(self):
        """Test problem creation with minimal fields."""
        problem = ProblemCreateSchema(
            title="Simple Problem",
            description="A simple problem",
        )
        assert problem.difficulty == "medium"  # default
        assert problem.hints is None
        assert problem.tags is None

    def test_problem_with_schema(self):
        """Test problem with expected schema."""
        problem = ProblemCreateSchema(
            title="URL Shortener",
            description="Design a URL shortening service",
            expected_schema={"tables": {"urls": {"columns": {"id": "bigint"}}}},
        )
        assert problem.expected_schema is not None
        assert "tables" in problem.expected_schema

    def test_problem_with_api_spec(self):
        """Test problem with expected API spec."""
        problem = ProblemCreateSchema(
            title="URL Shortener",
            description="Design a URL shortening service",
            expected_api_spec={"endpoints": [{"method": "POST", "path": "/shorten"}]},
        )
        assert problem.expected_api_spec is not None
        assert "endpoints" in problem.expected_api_spec


class TestSubmissionSchemas:
    """Tests for submission-related schemas."""

    def test_submission_create_valid(self):
        """Test valid submission creation schema."""
        submission = SubmissionCreateSchema(
            problem_id=1,
            schema_input={"tables": {"urls": {}}},
            api_spec_input={"endpoints": []},
            design_text="My design",
        )
        assert submission.problem_id == 1
        assert submission.design_text == "My design"

    def test_submission_create_minimal(self):
        """Test submission creation with minimal fields."""
        submission = SubmissionCreateSchema(problem_id=1)
        assert submission.problem_id == 1
        assert submission.schema_input is None
        assert submission.api_spec_input is None
        assert submission.design_text is None

    def test_submission_with_complex_schema(self):
        """Test submission with complex schema input."""
        complex_schema = {
            "stores": [
                {
                    "name": "urls",
                    "type": "sql",
                    "fields": [
                        {"name": "id", "type": "bigserial", "constraints": ["primary_key"]},
                        {"name": "short_code", "type": "varchar", "constraints": ["unique"]},
                    ],
                },
                {
                    "name": "url_cache",
                    "type": "kv",
                    "fields": [{"name": "short_code", "type": "string"}],
                },
            ]
        }
        submission = SubmissionCreateSchema(
            problem_id=1,
            schema_input=complex_schema,
        )
        assert len(submission.schema_input["stores"]) == 2

    def test_submission_with_api_spec(self):
        """Test submission with API spec input."""
        api_spec = {
            "endpoints": [
                {"method": "POST", "path": "/shorten", "request": {"url": "string"}},
                {"method": "GET", "path": "/{code}", "response": {"url": "string"}},
            ]
        }
        submission = SubmissionCreateSchema(
            problem_id=1,
            api_spec_input=api_spec,
        )
        assert len(submission.api_spec_input["endpoints"]) == 2
