"""
Application configuration settings.
Loads environment variables and provides typed access to all config values.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "System Design Platform"
    debug: bool = False
    demo_mode: bool = True  # Set to True to disable authentication for demo

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/system_design_db"

    # Authentication
    google_client_id: str = ""
    google_client_secret: str = ""
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Claude AI
    anthropic_api_key: str = ""

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    gcp_credentials_path: str = ""

    # Frontend URL (for OAuth redirect)
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_submissions_per_hour: int = 5  # Authenticated users
    rate_limit_submissions_unauth_per_hour: int = 2  # Unauthenticated
    rate_limit_validate_per_hour: int = 20  # Validation endpoint
    rate_limit_default_per_minute: int = 100  # Default for GET requests
    redis_url: str = ""  # Optional Redis URL for distributed rate limiting

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
