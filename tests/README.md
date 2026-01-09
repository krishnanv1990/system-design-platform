# Test Organization

This document explains the test directory structure for the System Design Platform.

## Directory Structure

```
tests/                          # Integration, functional, and chaos tests
├── conftest.py                # Shared fixtures for all test types
├── functional/                # End-to-end functional tests
│   ├── conftest.py           # Functional test fixtures
│   ├── test_url_shortener.py # URL shortener API tests
│   ├── test_file_sharing.py  # File sharing tests
│   └── test_chat_app.py      # Chat application tests
├── chaos/                     # Chaos engineering tests
│   ├── actions.py            # Chaos actions (failure injection)
│   ├── probes.py             # Health probes
│   └── experiments/          # Chaos experiment JSON definitions
├── integration/              # Integration tests
└── performance/              # Performance/load tests
    └── locustfile_*.py       # Locust load test files

backend/tests/                 # Backend unit tests
├── conftest.py               # Backend-specific fixtures
├── test_*.py                 # Unit test files
└── mocks/                    # Mock implementations
```

## Test Types

| Type | Location | Purpose | Markers |
|------|----------|---------|---------|
| Unit | `backend/tests/` | Test individual functions/classes in isolation | None |
| Integration | `tests/integration/` | Test service interactions | `@pytest.mark.integration` |
| Functional | `tests/functional/` | End-to-end API tests against deployed services | `@pytest.mark.e2e` |
| Chaos | `tests/chaos/` | Failure injection and resilience tests | `@pytest.mark.chaos` |
| Performance | `tests/performance/` | Load and stress testing with Locust | `@pytest.mark.performance` |

## Running Tests

### Unit Tests (Backend)
```bash
# Run all backend unit tests
pytest backend/tests/

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Run specific test file
pytest backend/tests/test_submissions.py -v
```

### Functional Tests
```bash
# Requires deployed services - set environment variables
export TEST_BACKEND_URL=https://your-backend-url
export TEST_AUTH_TOKEN=your-auth-token  # Optional

# Run functional tests
pytest tests/functional/ -v

# Run without auth-required tests
pytest tests/functional/ -v -m "not requires_auth"
```

### Chaos Tests
```bash
# Requires GCP configuration
export GCP_PROJECT_ID=your-project
export GCP_REGION=us-central1

# Run chaos tests
pytest tests/chaos/ -v -m chaos

# Run specific experiment
chaos run tests/chaos/experiments/experiment_url_shortener.json
```

### Performance Tests
```bash
# Run Locust load test
locust -f tests/performance/locustfile_url_shortener.py \
    --host=$TEST_BACKEND_URL \
    --users=10 --spawn-rate=2 --run-time=30s --headless
```

## Fixtures

### Shared Fixtures (`tests/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_config` | session | Environment configuration |
| `sync_client` | session | Authenticated HTTP client |
| `async_client` | function | Async HTTP client |
| `unauthenticated_client` | function | Client without auth |
| `gcp_credentials` | session | GCP service account credentials |
| `grpc_cluster` | function | 5-node gRPC cluster for distributed tests |
| `redis_client` | session | Redis client for cache testing |

### Functional Test Fixtures (`tests/functional/conftest.py`)

| Fixture | Description |
|---------|-------------|
| `auth_token` | OAuth/JWT token for authenticated requests |
| `cleanup_resources` | Tracks created resources for cleanup |
| `unique_test_id` | Generates unique IDs for test data |

## Custom Markers

Register markers in `pytest.ini` or `pyproject.toml`:

```ini
[pytest]
markers =
    smoke: Quick health check tests
    integration: Integration tests
    e2e: End-to-end tests
    chaos: Chaos engineering tests
    performance: Performance tests
    requires_auth: Tests requiring authentication
    requires_gcp: Tests requiring GCP resources
```

## Environment Variables

| Variable | Description | Required For |
|----------|-------------|--------------|
| `TEST_BACKEND_URL` | Backend service URL | Functional, Chaos |
| `TEST_FRONTEND_URL` | Frontend service URL | E2E |
| `TEST_AUTH_TOKEN` | Authentication token | Auth-required tests |
| `GCP_PROJECT_ID` | GCP project | Chaos, Integration |
| `GCP_REGION` | GCP region | Chaos, Integration |
| `TEST_DATABASE_URL` | Database connection | Integration |
| `TEST_REDIS_URL` | Redis connection | Integration |

## Writing New Tests

### Unit Test Example
```python
# backend/tests/test_example.py
import pytest
from backend.services.example import ExampleService

def test_example_function():
    service = ExampleService()
    result = service.process("input")
    assert result == "expected"
```

### Functional Test Example
```python
# tests/functional/test_example.py
import pytest

@pytest.mark.e2e
def test_api_endpoint(client):
    response = client.get("/api/v1/resource")
    assert response.status_code == 200
    assert "data" in response.json()
```

### Chaos Test Example
```python
# tests/chaos/test_resilience.py
import pytest

@pytest.mark.chaos
@pytest.mark.requires_gcp
async def test_service_recovery(test_config):
    # Inject failure
    await simulate_service_failure()

    # Verify recovery
    assert await check_service_health()
```

## CI/CD Integration

Tests run automatically in GitHub Actions:
- Unit tests: On every PR
- Integration tests: On merge to main
- Chaos tests: Scheduled (weekly)
- Performance tests: Manual trigger or scheduled
