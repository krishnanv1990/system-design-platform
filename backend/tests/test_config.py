"""
Tests for configuration settings.
"""

import pytest
from unittest.mock import patch
import os

from backend.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()

        assert settings.app_name == "System Design Platform"
        assert settings.debug is False
        assert settings.demo_mode is True
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expire_minutes == 60 * 24 * 7  # 7 days
        assert settings.gcp_region == "us-central1"

    def test_settings_from_env(self):
        """Test settings loaded from environment variables."""
        with patch.dict(os.environ, {
            "DEBUG": "true",
            "DEMO_MODE": "false",
            "GCP_PROJECT_ID": "my-project",
        }):
            settings = Settings()
            assert settings.gcp_project_id == "my-project"

    def test_rate_limit_defaults(self):
        """Test rate limit default values."""
        settings = Settings()

        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_submissions_per_hour == 5
        assert settings.rate_limit_submissions_unauth_per_hour == 2
        assert settings.rate_limit_validate_per_hour == 20
        assert settings.rate_limit_default_per_minute == 100

    def test_database_url_default(self):
        """Test database URL default value."""
        settings = Settings()
        assert "postgresql" in settings.database_url

    def test_jwt_settings(self):
        """Test JWT settings."""
        settings = Settings()

        assert settings.jwt_secret_key != ""
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expire_minutes > 0

    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should return same cached instance
        assert settings1 is settings2
