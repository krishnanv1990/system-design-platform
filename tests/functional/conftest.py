"""
Pytest configuration for functional tests.

Provides fixtures for running functional tests against real deployed services.
Uses the main tests/conftest.py fixtures and extends them for functional testing.
"""

import os
import pytest
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime


# ==================== Environment Configuration ====================

def get_test_url(service: str = "backend") -> str:
    """Get the test URL for a service."""
    urls = {
        "backend": os.getenv("TEST_BACKEND_URL", os.getenv("TEST_TARGET_URL", "https://sdp-backend-zziiwqh26q-uc.a.run.app")),
        "frontend": os.getenv("TEST_FRONTEND_URL", "https://sdp-frontend-zziiwqh26q-uc.a.run.app"),
        "admin": os.getenv("TEST_ADMIN_URL", "https://sdp-admin-zziiwqh26q-uc.a.run.app"),
    }
    return urls.get(service, urls["backend"])


# ==================== Authentication Fixtures ====================

@pytest.fixture(scope="session")
def auth_token() -> Optional[str]:
    """Get authentication token for tests."""
    # Try environment variable first
    token = os.getenv("TEST_AUTH_TOKEN") or os.getenv("TEST_USER_TOKEN")
    if token:
        return token

    # Try to get token from OAuth flow if credentials provided
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")

    if client_id and client_secret:
        try:
            # Use client credentials flow for service-to-service auth
            response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("access_token")
        except Exception:
            pass

    return None


@pytest.fixture(scope="session")
def admin_token() -> Optional[str]:
    """Get admin authentication token for tests."""
    return os.getenv("TEST_ADMIN_TOKEN")


# ==================== HTTP Client Fixtures ====================

@pytest.fixture
def base_url() -> str:
    """Get the base URL for functional tests."""
    return get_test_url("backend")


@pytest.fixture
def client(base_url: str, auth_token: Optional[str]) -> httpx.Client:
    """Create authenticated HTTP client for tests."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
        headers=headers,
    ) as client:
        yield client


@pytest.fixture
def unauthenticated_client(base_url: str) -> httpx.Client:
    """Create unauthenticated HTTP client for tests."""
    with httpx.Client(
        base_url=base_url,
        timeout=30.0,
    ) as client:
        yield client


@pytest.fixture
async def async_client(base_url: str, auth_token: Optional[str]) -> httpx.AsyncClient:
    """Create async authenticated HTTP client."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=30.0,
        headers=headers,
    ) as client:
        yield client


# ==================== Test Data Fixtures ====================

@pytest.fixture
def unique_test_id() -> str:
    """Generate a unique ID for test data."""
    return f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


@pytest.fixture
def test_url(unique_test_id: str) -> str:
    """Generate a unique test URL."""
    return f"https://example.com/functional-test/{unique_test_id}"


@pytest.fixture
def cleanup_resources():
    """Track resources created during tests for cleanup."""
    resources: Dict[str, List[str]] = {
        "short_codes": [],
        "file_ids": [],
        "message_ids": [],
    }

    yield resources

    # Cleanup would happen here in a real implementation
    # For now, we just log what would be cleaned up
    for resource_type, ids in resources.items():
        if ids:
            print(f"Would cleanup {len(ids)} {resource_type}: {ids[:5]}...")


# ==================== Retry Configuration ====================

@pytest.fixture
def retry_config() -> Dict[str, Any]:
    """Configuration for retry behavior."""
    return {
        "max_retries": int(os.getenv("TEST_MAX_RETRIES", "3")),
        "retry_delay": float(os.getenv("TEST_RETRY_DELAY", "1.0")),
        "timeout": float(os.getenv("TEST_TIMEOUT", "30.0")),
    }


# ==================== Skip Conditions ====================

def pytest_runtest_setup(item):
    """Skip tests based on markers and environment."""
    # Skip auth-required tests if no token
    if "requires_auth" in [marker.name for marker in item.iter_markers()]:
        token = os.getenv("TEST_AUTH_TOKEN") or os.getenv("TEST_USER_TOKEN")
        if not token:
            pytest.skip("Test requires authentication (set TEST_AUTH_TOKEN)")

    # Skip GCP-required tests if not configured
    if "requires_gcp" in [marker.name for marker in item.iter_markers()]:
        project = os.getenv("GCP_PROJECT_ID") or os.getenv("GCP_PROJECT")
        if not project:
            pytest.skip("Test requires GCP (set GCP_PROJECT_ID)")


# ==================== Test Helpers ====================

def wait_for_service(url: str, timeout: int = 60, interval: int = 5) -> bool:
    """Wait for a service to become available."""
    import time

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = httpx.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval)

    return False


@pytest.fixture(scope="session", autouse=True)
def ensure_service_available(base_url: str = None):
    """Ensure the test service is available before running tests."""
    url = base_url or get_test_url("backend")

    try:
        response = httpx.get(f"{url}/health", timeout=10)
        if response.status_code != 200:
            pytest.skip(f"Service not healthy at {url}")
    except Exception as e:
        pytest.skip(f"Cannot reach service at {url}: {e}")
