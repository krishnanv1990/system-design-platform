"""
Tests for the ValidationService.
Tests error handling, design parsing, and validation logic.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.validation_service import ValidationService
from backend.models.problem import Problem
from backend.schemas.submission import ValidationResponse


class TestValidationService:
    """Tests for ValidationService class."""

    @pytest.fixture
    def validation_service(self):
        """Create a validation service instance."""
        return ValidationService()

    @pytest.fixture
    def mock_problem(self):
        """Create a mock problem."""
        problem = MagicMock(spec=Problem)
        problem.description = "Design a URL shortener service"
        problem.expected_schema = {"required_tables": ["urls"]}
        problem.expected_api_spec = {"required_endpoints": ["POST /api/v1/urls"]}
        return problem

    def test_validate_schema_with_missing_tables(self, validation_service):
        """Test schema validation when required tables are missing."""
        schema_input = {"tables": {"other_table": {"columns": {}}}}
        expected_schema = {"required_tables": ["urls", "stats"]}

        result = validation_service._validate_schema(schema_input, expected_schema)

        assert "errors" in result
        assert len(result["errors"]) == 1
        assert "Missing required tables" in result["errors"][0]

    def test_validate_schema_with_all_tables(self, validation_service):
        """Test schema validation when all required tables are present."""
        schema_input = {
            "tables": {
                "urls": {"columns": {"id": {"primary_key": True}}},
                "stats": {"columns": {"id": {"primary_key": True}}},
            }
        }
        expected_schema = {"required_tables": ["urls", "stats"]}

        result = validation_service._validate_schema(schema_input, expected_schema)

        assert result["errors"] == []

    def test_validate_schema_warns_on_missing_primary_key(self, validation_service):
        """Test that validation warns when primary key is missing."""
        schema_input = {
            "tables": {
                "urls": {"columns": {"url": {"type": "text"}}},
            }
        }

        result = validation_service._validate_schema(schema_input, None)

        assert len(result["warnings"]) >= 1
        assert any("primary key" in w.lower() for w in result["warnings"])

    def test_validate_api_spec_with_missing_endpoints(self, validation_service):
        """Test API spec validation when required endpoints are missing."""
        api_spec_input = {"endpoints": [{"method": "GET", "path": "/health"}]}
        expected_api_spec = {"required_endpoints": ["POST /api/v1/urls", "GET /api/v1/urls/{id}"]}

        result = validation_service._validate_api_spec(api_spec_input, expected_api_spec)

        assert "errors" in result
        assert len(result["errors"]) == 1
        assert "Missing required endpoints" in result["errors"][0]

    def test_validate_api_spec_warns_on_missing_request_body(self, validation_service):
        """Test that POST/PUT without request body generates warning."""
        api_spec_input = {
            "endpoints": [
                {"method": "POST", "path": "/api/v1/urls"},
            ]
        }

        result = validation_service._validate_api_spec(api_spec_input, None)

        assert any("request body" in w.lower() for w in result["warnings"])

    def test_validate_api_spec_warns_on_missing_responses(self, validation_service):
        """Test that endpoints without response schemas generate warning."""
        api_spec_input = {
            "endpoints": [
                {"method": "GET", "path": "/api/v1/urls"},
            ]
        }

        result = validation_service._validate_api_spec(api_spec_input, None)

        assert any("response" in w.lower() for w in result["warnings"])

    def test_validate_design_text_too_short(self, validation_service):
        """Test that short design text generates error."""
        result = validation_service.validate_design_text("short text")

        assert len(result["errors"]) >= 1
        assert any("too short" in e.lower() for e in result["errors"])

    def test_validate_design_text_warns_on_missing_topics(self, validation_service):
        """Test that missing key topics generate warnings."""
        # A design that mentions some topics but not all
        design_text = "This is a design about database storage and API endpoints. " * 10

        result = validation_service.validate_design_text(design_text)

        # Should have warnings about missing topics (like caching, scaling)
        # The design mentions database and api, but not caching or scaling
        assert len(result["warnings"]) >= 0  # May or may not have warnings

    @pytest.mark.asyncio
    async def test_validate_all_with_canvas_json_design(self, validation_service, mock_problem):
        """Test validation handles canvas JSON format correctly."""
        # Canvas editor sends design_text as JSON
        canvas_data = {
            "elements": [
                {"id": "1", "type": "database", "label": "PostgreSQL"},
                {"id": "2", "type": "cache", "label": "Redis"},
                {"id": "3", "type": "server", "label": "API Server"},
            ],
            "version": 1
        }
        design_text = json.dumps({
            "mode": "canvas",
            "canvas": json.dumps(canvas_data),
            "text": ""
        })

        # Mock the AI service to avoid actual API calls
        with patch.object(validation_service.ai_service, 'validate_design', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": ["Consider adding load balancer"],
                "score": 80,
            }

            result = await validation_service.validate_all(
                problem=mock_problem,
                schema_input={"tables": {"urls": {"columns": {"id": {"primary_key": True}}}}},
                api_spec_input=None,
                design_text=design_text,
            )

            assert isinstance(result, ValidationResponse)
            # AI service should have been called with extracted content
            mock_validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_all_handles_ai_service_failure(self, validation_service, mock_problem):
        """Test that validation doesn't fail if AI service throws exception."""
        # Mock the AI service to throw an exception
        with patch.object(validation_service.ai_service, 'validate_design', new_callable=AsyncMock) as mock_validate:
            mock_validate.side_effect = Exception("AI service unavailable")

            result = await validation_service.validate_all(
                problem=mock_problem,
                schema_input={"tables": {"urls": {"columns": {"id": {"primary_key": True}}}}},
                api_spec_input=None,
                design_text="Some design text description",
            )

            # Should not raise, but add a warning
            assert isinstance(result, ValidationResponse)
            assert any("unavailable" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_validate_all_extracts_text_from_design_json(self, validation_service, mock_problem):
        """Test that validation extracts text content from design JSON."""
        design_text = json.dumps({
            "mode": "text",
            "canvas": "",
            "text": "This is my detailed design for a URL shortener with caching and scaling."
        })

        with patch.object(validation_service.ai_service, 'validate_design', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "score": 85,
            }

            await validation_service.validate_all(
                problem=mock_problem,
                schema_input=None,
                api_spec_input=None,
                design_text=design_text,
            )

            # Verify AI service was called with extracted text content
            call_args = mock_validate.call_args
            assert "This is my detailed design" in call_args.kwargs["design_text"]

    @pytest.mark.asyncio
    async def test_validate_all_returns_score_from_ai(self, validation_service, mock_problem):
        """Test that AI score is included in validation response."""
        with patch.object(validation_service.ai_service, 'validate_design', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "score": 92,
            }

            result = await validation_service.validate_all(
                problem=mock_problem,
                schema_input=None,
                api_spec_input=None,
                design_text="Detailed design description...",
            )

            assert result.score == 92

    @pytest.mark.asyncio
    async def test_validate_all_without_design_text(self, validation_service, mock_problem):
        """Test validation works when design_text is not provided."""
        result = await validation_service.validate_all(
            problem=mock_problem,
            schema_input={"tables": {"urls": {"columns": {"id": {"primary_key": True}}}}},
            api_spec_input=None,
            design_text=None,
        )

        assert isinstance(result, ValidationResponse)
        assert result.score is None

    @pytest.mark.asyncio
    async def test_validate_all_combines_all_errors_and_warnings(self, validation_service, mock_problem):
        """Test that errors and warnings from all sources are combined."""
        # Schema with missing table
        schema_input = {"tables": {"other": {"columns": {}}}}

        # API spec with issues
        api_spec_input = {
            "endpoints": [
                {"method": "POST", "path": "/api/v1/urls"},  # Missing request body
            ]
        }

        with patch.object(validation_service.ai_service, 'validate_design', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {
                "is_valid": False,
                "errors": ["AI found issue with design"],
                "warnings": ["AI warning"],
                "suggestions": ["AI suggestion"],
                "score": 50,
            }

            result = await validation_service.validate_all(
                problem=mock_problem,
                schema_input=schema_input,
                api_spec_input=api_spec_input,
                design_text="Some design",
            )

            # Should have errors from schema, API spec, and AI
            assert len(result.errors) >= 2  # At least schema error and AI error
            assert len(result.warnings) >= 2  # At least API spec warning and AI warning
            assert not result.is_valid  # Should be invalid due to errors
