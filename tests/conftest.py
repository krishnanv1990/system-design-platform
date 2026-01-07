"""
Pytest configuration and fixtures for real integration tests.

This module provides fixtures for running tests against real GCP infrastructure.
Configuration is loaded from environment variables or .env files.
"""

import os
import pytest
import httpx
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import json

# Load environment from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==================== Configuration ====================

@dataclass
class TestConfig:
    """Test environment configuration."""
    # Service URLs
    frontend_url: str
    backend_url: str
    admin_url: str

    # Authentication
    oauth_client_id: Optional[str]
    oauth_client_secret: Optional[str]
    test_user_token: Optional[str]
    admin_token: Optional[str]

    # GCP Configuration
    gcp_project_id: str
    gcp_region: str
    artifact_registry: str

    # Database
    database_url: Optional[str]

    # Redis
    redis_url: Optional[str]

    # Test settings
    timeout_seconds: int
    retry_count: int

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Load configuration from environment variables."""
        return cls(
            frontend_url=os.getenv("TEST_FRONTEND_URL", "https://sdp-frontend-zziiwqh26q-uc.a.run.app"),
            backend_url=os.getenv("TEST_BACKEND_URL", "https://sdp-backend-zziiwqh26q-uc.a.run.app"),
            admin_url=os.getenv("TEST_ADMIN_URL", "https://sdp-admin-zziiwqh26q-uc.a.run.app"),
            oauth_client_id=os.getenv("OAUTH_CLIENT_ID"),
            oauth_client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
            test_user_token=os.getenv("TEST_USER_TOKEN"),
            admin_token=os.getenv("TEST_ADMIN_TOKEN"),
            gcp_project_id=os.getenv("GCP_PROJECT_ID", "system-design-platform-prod"),
            gcp_region=os.getenv("GCP_REGION", "us-central1"),
            artifact_registry=os.getenv("ARTIFACT_REGISTRY", "us-central1-docker.pkg.dev"),
            database_url=os.getenv("TEST_DATABASE_URL"),
            redis_url=os.getenv("TEST_REDIS_URL"),
            timeout_seconds=int(os.getenv("TEST_TIMEOUT_SECONDS", "30")),
            retry_count=int(os.getenv("TEST_RETRY_COUNT", "3")),
        )


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """Get test configuration."""
    return TestConfig.from_env()


# ==================== HTTP Clients ====================

@pytest.fixture(scope="session")
def sync_client(test_config: TestConfig) -> httpx.Client:
    """Create a synchronous HTTP client."""
    headers = {}
    if test_config.test_user_token:
        headers["Authorization"] = f"Bearer {test_config.test_user_token}"

    client = httpx.Client(
        base_url=test_config.backend_url,
        timeout=test_config.timeout_seconds,
        headers=headers,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def admin_client(test_config: TestConfig) -> httpx.Client:
    """Create an admin HTTP client."""
    headers = {}
    if test_config.admin_token:
        headers["Authorization"] = f"Bearer {test_config.admin_token}"

    client = httpx.Client(
        base_url=test_config.admin_url,
        timeout=test_config.timeout_seconds,
        headers=headers,
    )
    yield client
    client.close()


@pytest.fixture
async def async_client(test_config: TestConfig) -> httpx.AsyncClient:
    """Create an async HTTP client."""
    headers = {}
    if test_config.test_user_token:
        headers["Authorization"] = f"Bearer {test_config.test_user_token}"

    async with httpx.AsyncClient(
        base_url=test_config.backend_url,
        timeout=test_config.timeout_seconds,
        headers=headers,
    ) as client:
        yield client


@pytest.fixture
def unauthenticated_client(test_config: TestConfig) -> httpx.Client:
    """Create an unauthenticated HTTP client."""
    client = httpx.Client(
        base_url=test_config.backend_url,
        timeout=test_config.timeout_seconds,
    )
    yield client
    client.close()


# ==================== GCP Clients ====================

@pytest.fixture(scope="session")
def gcp_credentials():
    """Get GCP credentials for service account."""
    try:
        from google.oauth2 import service_account
        from google.auth import default

        # Try to use application default credentials
        credentials, project = default()
        return credentials
    except Exception:
        return None


@pytest.fixture(scope="session")
def cloud_run_client(test_config: TestConfig, gcp_credentials):
    """Create Cloud Run API client."""
    try:
        from google.cloud import run_v2
        if gcp_credentials:
            return run_v2.ServicesClient(credentials=gcp_credentials)
        return run_v2.ServicesClient()
    except ImportError:
        pytest.skip("google-cloud-run not installed")


@pytest.fixture(scope="session")
def cloud_build_client(test_config: TestConfig, gcp_credentials):
    """Create Cloud Build API client."""
    try:
        from google.cloud import cloudbuild_v1
        if gcp_credentials:
            return cloudbuild_v1.CloudBuildClient(credentials=gcp_credentials)
        return cloudbuild_v1.CloudBuildClient()
    except ImportError:
        pytest.skip("google-cloud-build not installed")


@pytest.fixture(scope="session")
def redis_client(test_config: TestConfig):
    """Create Redis client for cache testing."""
    if not test_config.redis_url:
        pytest.skip("TEST_REDIS_URL not configured")

    try:
        import redis
        client = redis.from_url(test_config.redis_url)
        client.ping()  # Verify connection
        yield client
        client.close()
    except ImportError:
        pytest.skip("redis package not installed")
    except Exception as e:
        pytest.skip(f"Could not connect to Redis: {e}")


@pytest.fixture(scope="session")
def db_connection(test_config: TestConfig):
    """Create database connection for integration testing."""
    if not test_config.database_url:
        pytest.skip("TEST_DATABASE_URL not configured")

    try:
        import asyncpg

        async def get_connection():
            return await asyncpg.connect(test_config.database_url)

        conn = asyncio.get_event_loop().run_until_complete(get_connection())
        yield conn
        asyncio.get_event_loop().run_until_complete(conn.close())
    except ImportError:
        pytest.skip("asyncpg not installed")
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")


# ==================== gRPC Fixtures ====================

@dataclass
class GrpcClusterNode:
    """Represents a node in a gRPC cluster."""
    node_id: str
    url: str
    port: int = 50051


@dataclass
class GrpcCluster:
    """Represents a deployed gRPC cluster for testing."""
    cluster_id: str
    nodes: List[GrpcClusterNode]
    problem_type: str

    @property
    def endpoints(self) -> List[str]:
        return [f"{node.url}:{node.port}" for node in self.nodes]


@pytest.fixture
async def grpc_cluster(test_config: TestConfig) -> GrpcCluster:
    """Provision a real 5-node gRPC cluster for testing."""
    # For now, return mock cluster endpoints from environment
    # In production, this would provision real Cloud Run services
    cluster_id = os.getenv("TEST_CLUSTER_ID", "test-cluster")

    nodes = []
    for i in range(5):
        node_url = os.getenv(
            f"TEST_GRPC_NODE_{i}_URL",
            f"https://raft-test-node{i}-zziiwqh26q-uc.a.run.app"
        )
        nodes.append(GrpcClusterNode(
            node_id=f"node-{i}",
            url=node_url,
            port=50051
        ))

    return GrpcCluster(
        cluster_id=cluster_id,
        nodes=nodes,
        problem_type="raft"
    )


@pytest.fixture
def grpc_channel_factory():
    """Factory for creating gRPC channels."""
    import grpc

    channels = []

    def create_channel(target: str, secure: bool = True):
        if secure:
            credentials = grpc.ssl_channel_credentials()
            channel = grpc.secure_channel(target, credentials)
        else:
            channel = grpc.insecure_channel(target)
        channels.append(channel)
        return channel

    yield create_channel

    for channel in channels:
        channel.close()


# ==================== Test Data Fixtures ====================

@pytest.fixture
def test_url_data() -> Dict[str, Any]:
    """Generate test data for URL shortener tests."""
    return {
        "original_url": f"https://example.com/test/{datetime.now().timestamp()}",
        "custom_code": None,
        "expires_at": None,
    }


@pytest.fixture
def test_file_data() -> Dict[str, Any]:
    """Generate test data for file sharing tests."""
    return {
        "filename": f"test_file_{datetime.now().timestamp()}.txt",
        "content": b"Test file content for integration testing",
        "content_type": "text/plain",
    }


# ==================== Cleanup Fixtures ====================

@pytest.fixture
def cleanup_urls(sync_client):
    """Track and cleanup created URLs after tests."""
    created_urls = []

    yield created_urls

    # Cleanup
    for short_code in created_urls:
        try:
            sync_client.delete(f"/api/v1/urls/{short_code}")
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def cleanup_files(sync_client):
    """Track and cleanup created files after tests."""
    created_files = []

    yield created_files

    # Cleanup
    for file_id in created_files:
        try:
            sync_client.delete(f"/api/v1/files/{file_id}")
        except Exception:
            pass


# ==================== Markers ====================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test (quick health check)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "chaos: mark test as chaos engineering test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers", "requires_auth: mark test as requiring authentication"
    )
    config.addinivalue_line(
        "markers", "requires_gcp: mark test as requiring GCP resources"
    )


# ==================== Session Fixtures ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def verify_test_environment(test_config: TestConfig):
    """Verify test environment is properly configured before running tests."""
    # Check backend is accessible
    try:
        response = httpx.get(f"{test_config.backend_url}/health", timeout=10)
        if response.status_code != 200:
            pytest.skip(f"Backend not healthy: {response.status_code}")
    except Exception as e:
        pytest.skip(f"Cannot reach backend: {e}")

    print(f"\n[Test Environment]")
    print(f"  Backend: {test_config.backend_url}")
    print(f"  Frontend: {test_config.frontend_url}")
    print(f"  GCP Project: {test_config.gcp_project_id}")
    print(f"  Region: {test_config.gcp_region}")
