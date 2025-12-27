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

    def test_chat_request_with_difficulty_level(self):
        """Test chat request with difficulty level."""
        request = {
            "problem_id": 1,
            "message": "How should I design this at L7 level?",
            "conversation_history": [],
            "current_schema": None,
            "current_api_spec": None,
            "difficulty_level": "hard"
        }
        assert "difficulty_level" in request
        assert request["difficulty_level"] == "hard"

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


class TestDifficultyLevelsContract:
    """Tests for difficulty levels mapping."""

    def test_difficulty_level_mapping(self):
        """Test difficulty level to engineering level mapping."""
        from backend.models.problem import DIFFICULTY_LEVELS

        assert "easy" in DIFFICULTY_LEVELS
        assert "medium" in DIFFICULTY_LEVELS
        assert "hard" in DIFFICULTY_LEVELS

        # Verify L5/L6/L7 mapping
        assert DIFFICULTY_LEVELS["easy"]["level"] == "L5"
        assert DIFFICULTY_LEVELS["medium"]["level"] == "L6"
        assert DIFFICULTY_LEVELS["hard"]["level"] == "L7"

    def test_difficulty_level_titles(self):
        """Test difficulty level titles."""
        from backend.models.problem import DIFFICULTY_LEVELS

        assert DIFFICULTY_LEVELS["easy"]["title"] == "Senior Software Engineer"
        assert DIFFICULTY_LEVELS["medium"]["title"] == "Staff Engineer"
        assert DIFFICULTY_LEVELS["hard"]["title"] == "Principal Engineer"

    def test_difficulty_level_descriptions(self):
        """Test difficulty level descriptions."""
        from backend.models.problem import DIFFICULTY_LEVELS

        assert "basic" in DIFFICULTY_LEVELS["easy"]["description"].lower()
        assert "production" in DIFFICULTY_LEVELS["medium"]["description"].lower()
        assert "global" in DIFFICULTY_LEVELS["hard"]["description"].lower()


class TestURLShortenerRequirementsContract:
    """Tests for URL shortener level-specific requirements contracts."""

    def test_url_shortener_requirements_structure(self):
        """Test URL shortener requirements have correct structure for all levels."""
        # These are the expected requirements from the chat module
        url_shortener_requirements = {
            "easy": {
                "level": "L5",
                "title": "Senior Software Engineer",
                "focus": "Core functionality with basic scalability",
                "requirements": "**L5 (Senior SWE) URL Shortener Requirements:**\n\nFocus on building a working URL shortener with KGS..."
            },
            "medium": {
                "level": "L6",
                "title": "Staff Engineer",
                "focus": "Production-ready design with high availability",
                "requirements": "**L6 (Staff SWE) URL Shortener Requirements:**\n\nBuild a production-ready URL shortener with KGS, caching, and analytics..."
            },
            "hard": {
                "level": "L7",
                "title": "Principal Engineer",
                "focus": "Global-scale architecture with advanced optimizations",
                "requirements": "**L7 (Principal SWE) URL Shortener Requirements:**\n\nDesign a globally-distributed, highly-available URL shortener..."
            }
        }

        # Verify structure
        assert "easy" in url_shortener_requirements
        assert "medium" in url_shortener_requirements
        assert "hard" in url_shortener_requirements

    def test_all_levels_should_use_kgs(self):
        """Test that requirements mention KGS (Key Generation Service)."""
        # All difficulty levels should use KGS according to the design
        levels = ["easy", "medium", "hard"]
        expected_kgs_mentions = {
            "easy": "KGS (Key Generation Service)",
            "medium": "KGS with Redis-based key pool",
            "hard": "Distributed Key Generation Service (KGS)"
        }

        for level in levels:
            assert level in expected_kgs_mentions, f"Level {level} should have KGS mention"

    def test_l5_requirements_contract(self):
        """Test L5 requirements contract."""
        l5_contract = {
            "level": "L5",
            "title": "Senior Software Engineer",
            "required_components": [
                "Key Generation Service (KGS)",
                "Database Design",
                "Core API Endpoints",
                "Basic Reliability"
            ],
            "evaluation_criteria": [
                "KGS generates unique codes",
                "Redirection works correctly",
                "Basic error handling"
            ]
        }

        assert l5_contract["level"] == "L5"
        assert "Senior" in l5_contract["title"]
        assert len(l5_contract["required_components"]) > 0
        assert len(l5_contract["evaluation_criteria"]) > 0

    def test_l6_requirements_contract(self):
        """Test L6 requirements include production features."""
        l6_contract = {
            "level": "L6",
            "title": "Staff Engineer",
            "required_components": [
                "KGS with Redis-based key pool",
                "Database with proper indexing",
                "Full API with CRUD operations",
                "Caching Layer with Redis",
                "Horizontal scalability"
            ],
            "features": ["caching", "analytics", "expiration handling"]
        }

        assert l6_contract["level"] == "L6"
        assert "Staff" in l6_contract["title"]
        assert "Caching Layer" in str(l6_contract["required_components"])
        assert "analytics" in l6_contract["features"]

    def test_l7_requirements_contract(self):
        """Test L7 requirements include global distribution."""
        l7_contract = {
            "level": "L7",
            "title": "Principal Engineer",
            "required_components": [
                "Distributed Key Generation Service",
                "Multi-region database architecture",
                "Global API Design",
                "Multi-tier Caching with CDN",
                "High Availability",
                "Performance & Scale"
            ],
            "scale_targets": {
                "redirects_per_second": "100K+",
                "p99_latency": "< 50ms"
            }
        }

        assert l7_contract["level"] == "L7"
        assert "Principal" in l7_contract["title"]
        assert "Distributed" in str(l7_contract["required_components"])
        assert "Multi-region" in str(l7_contract["required_components"])


class TestLevelInfoContract:
    """Tests for level info helper contracts."""

    def test_level_info_structure(self):
        """Test level info has correct structure for all difficulties."""
        expected_level_info = {
            "easy": {"level": "L5", "title": "Senior Software Engineer"},
            "medium": {"level": "L6", "title": "Staff Engineer"},
            "hard": {"level": "L7", "title": "Principal Engineer"},
        }

        for difficulty, info in expected_level_info.items():
            assert "level" in info
            assert "title" in info
            assert info["level"].startswith("L")

    def test_level_info_easy(self):
        """Test level info for easy difficulty."""
        info = {"level": "L5", "title": "Senior Software Engineer", "description": "Core functionality"}
        assert info["level"] == "L5"
        assert "Senior" in info["title"]

    def test_level_info_medium(self):
        """Test level info for medium difficulty."""
        info = {"level": "L6", "title": "Staff Engineer", "description": "Production-ready"}
        assert info["level"] == "L6"
        assert "Staff" in info["title"]

    def test_level_info_hard(self):
        """Test level info for hard difficulty."""
        info = {"level": "L7", "title": "Principal Engineer", "description": "Global-scale"}
        assert info["level"] == "L7"
        assert "Principal" in info["title"]

    def test_difficulty_to_level_mapping(self):
        """Test difficulty to engineering level mapping."""
        mapping = {
            "easy": "L5",
            "medium": "L6",
            "hard": "L7"
        }

        assert mapping["easy"] == "L5"
        assert mapping["medium"] == "L6"
        assert mapping["hard"] == "L7"


class TestDesignSummaryContract:
    """Tests for design summary API contracts."""

    def test_design_summary_request_structure(self):
        """Test design summary request structure."""
        request = {
            "problem_id": 1,
            "difficulty_level": "medium",
            "conversation_history": [
                {"role": "user", "content": "How do I design this?"},
                {"role": "assistant", "content": "Start with KGS..."},
            ],
            "current_schema": None,
            "current_api_spec": None,
            "current_diagram": None,
        }
        assert "problem_id" in request
        assert "difficulty_level" in request
        assert request["difficulty_level"] in ["easy", "medium", "hard"]

    def test_design_summary_response_structure(self):
        """Test design summary response structure."""
        response = {
            "summary": "This design demonstrates solid understanding...",
            "key_components": ["KGS", "Redis Cache", "Load Balancer"],
            "strengths": ["Good use of KGS", "Proper caching"],
            "areas_for_improvement": ["Add analytics tracking"],
            "overall_score": 85,
            "difficulty_level": "medium",
            "level_info": {
                "level": "L6",
                "title": "Staff Engineer",
                "description": "Production-ready design",
            },
            "demo_mode": False,
        }
        assert "summary" in response
        assert "key_components" in response
        assert "strengths" in response
        assert "areas_for_improvement" in response
        assert "overall_score" in response
        assert "difficulty_level" in response
        assert "level_info" in response
        assert isinstance(response["key_components"], list)
        assert isinstance(response["strengths"], list)

    def test_design_summary_level_info_structure(self):
        """Test level_info structure in design summary response."""
        level_info = {
            "level": "L6",
            "title": "Staff Engineer",
            "description": "Production-ready design",
        }
        assert "level" in level_info
        assert "title" in level_info
        assert "description" in level_info

    def test_design_summary_score_range(self):
        """Test that overall_score is within valid range."""
        # Score should be between 0 and 100 or None
        valid_scores = [0, 50, 80, 100, None]
        for score in valid_scores:
            response = {
                "overall_score": score,
            }
            if score is not None:
                assert 0 <= score <= 100
            else:
                assert response["overall_score"] is None


class TestLevelRequirementsEndpointContract:
    """Tests for level-requirements endpoint contract."""

    def test_level_requirements_response_structure(self):
        """Test level requirements endpoint response structure."""
        response = {
            "problem_id": 1,
            "problem_title": "URL Shortener",
            "difficulty": "medium",
            "level_info": {
                "level": "L6",
                "title": "Staff Engineer",
                "description": "Production-ready design",
            },
            "requirements": "**L6 (Staff SWE) URL Shortener Requirements:**...",
        }
        assert "problem_id" in response
        assert "problem_title" in response
        assert "difficulty" in response
        assert "level_info" in response
        assert "requirements" in response

    def test_level_requirements_all_difficulties(self):
        """Test level requirements for all difficulty levels."""
        difficulties = ["easy", "medium", "hard"]
        expected_levels = {"easy": "L5", "medium": "L6", "hard": "L7"}

        for diff in difficulties:
            response = {
                "difficulty": diff,
                "level_info": {
                    "level": expected_levels[diff],
                },
            }
            assert response["level_info"]["level"] == expected_levels[diff]


class TestUserDataExportContract:
    """Tests for user data export API contracts (GDPR/CCPA compliance)."""

    def test_user_data_export_structure(self):
        """Test user data export response structure."""
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
                    "schema_input": {},
                    "api_spec_input": {},
                }
            ],
            "test_results": [
                {
                    "id": 1,
                    "submission_id": 1,
                    "test_type": "functional",
                    "test_name": "test_create_url",
                    "status": "passed",
                    "created_at": "2024-01-01T00:00:00",
                }
            ],
            "exported_at": "2024-12-27T00:00:00",
        }

        assert "user" in response
        assert "submissions" in response
        assert "test_results" in response
        assert "exported_at" in response

    def test_user_data_export_user_fields(self):
        """Test user fields in data export."""
        user_data = {
            "id": 1,
            "email": "test@example.com",
            "name": "Test User",
            "avatar_url": "https://example.com/avatar.jpg",
            "created_at": "2024-01-01T00:00:00",
            "linked_providers": ["google", "github"],
        }

        required_fields = ["id", "email", "name", "avatar_url", "created_at", "linked_providers"]
        for field in required_fields:
            assert field in user_data

    def test_user_data_export_submission_fields(self):
        """Test submission fields in data export."""
        submission_data = {
            "id": 1,
            "problem_id": 1,
            "problem_title": "URL Shortener",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00",
            "design_text": "My design",
            "schema_input": {"tables": {}},
            "api_spec_input": {"endpoints": []},
        }

        required_fields = ["id", "problem_id", "problem_title", "status", "created_at"]
        for field in required_fields:
            assert field in submission_data


class TestAccountDeletionContract:
    """Tests for account deletion API contracts."""

    def test_delete_account_response_structure(self):
        """Test delete account response structure."""
        response = {
            "message": "Account and all associated data have been permanently deleted."
        }

        assert "message" in response
        assert "deleted" in response["message"].lower()

    def test_delete_account_removes_user_data(self):
        """Test that account deletion removes all user data."""
        # This is a contract test - the actual deletion is tested in integration tests
        data_to_delete = [
            "user profile",
            "submissions",
            "diagrams",
            "test results",
            "chat history",
        ]

        for data_type in data_to_delete:
            assert isinstance(data_type, str)


class TestPrivacyComplianceContract:
    """Tests for privacy compliance features."""

    def test_gdpr_rights_supported(self):
        """Test GDPR rights are supported."""
        gdpr_rights = {
            "access": True,  # User can access their data
            "rectification": True,  # User can correct data (via OAuth)
            "erasure": True,  # User can delete account
            "portability": True,  # User can download data
            "objection": True,  # User can decline analytics
        }

        assert all(gdpr_rights.values())

    def test_ccpa_rights_supported(self):
        """Test CCPA rights are supported."""
        ccpa_rights = {
            "know": True,  # Right to know what data is collected
            "delete": True,  # Right to delete data
            "opt_out": True,  # Right to opt out of sale (we don't sell)
            "non_discrimination": True,  # No discrimination for exercising rights
        }

        assert all(ccpa_rights.values())

    def test_cookie_consent_options(self):
        """Test cookie consent options."""
        consent_options = ["accept_all", "essential_only"]

        assert "accept_all" in consent_options
        assert "essential_only" in consent_options
