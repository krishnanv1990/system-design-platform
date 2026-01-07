# Test Conversion Plan: Simulated to Real Tests

## Executive Summary

This document outlines the strategy for converting simulated/mocked tests to real integration tests that run against deployed infrastructure on GCP.

---

## Current Test Inventory

### 1. Backend Unit/Integration Tests (20 files)
**Location:** `backend/tests/`
**Framework:** pytest 9.0.2 with asyncio

| File | Type | Mock Status | Conversion Priority |
|------|------|-------------|---------------------|
| test_config.py | Unit | Uses mocks | Keep as-is (unit tests) |
| test_jwt.py | Unit | Uses mocks | Keep as-is (unit tests) |
| test_schemas.py | Unit | Uses mocks | Keep as-is (unit tests) |
| test_auth_data_management.py | Integration | Mock DB | Convert to real DB |
| test_api_integration.py | Integration | TestClient | Convert to real endpoints |
| test_oauth.py | Integration | Mock OAuth | Add real OAuth flow tests |
| test_user_api.py | Integration | Mock DB | Convert to real DB |
| test_admin_api.py | Integration | Mock services | Convert to real services |
| test_distributed_api.py | Integration | **Mock gRPC** | **HIGH PRIORITY** - Convert to real gRPC |
| test_distributed_tests.py | Integration | **Mock runner** | **HIGH PRIORITY** - Convert to real runner |
| test_distributed_tests_new.py | Integration | Mock | Convert to real |
| test_distributed_tests_vector.py | Integration | Mock vectors | Convert to real vectors |
| test_distributed_templates.py | Unit | File-based | Keep as-is |
| test_system_design_problems.py | Unit | Config-based | Keep as-is |

### 2. Functional Tests (4 files)
**Location:** `tests/functional/`
**Framework:** httpx + pytest

| File | Lines | Current Status | Action |
|------|-------|----------------|--------|
| test_url_shortener.py | 55K | **Already real** - uses httpx against endpoints | Enhance with auth |
| test_file_sharing.py | 14K | **Already real** - uses httpx | Enhance with auth |
| test_chat_app.py | 18K | **Already real** - WebSocket tests | Add reconnection tests |
| test_raft_consensus.py | 25K | **Already real** - gRPC with proto compilation | Expand chaos scenarios |

### 3. Performance Tests (5 files)
**Location:** `tests/performance/`
**Framework:** Locust

| File | Status | Real Infrastructure |
|------|--------|---------------------|
| locustfile_url_shortener.py | Ready | Targets real Cloud Run URLs |
| locustfile_file_sharing.py | Ready | Targets real endpoints |
| locustfile_chat.py | Ready | WebSocket load testing |
| locustfile_distributed.py | Ready | Distributed load testing |
| locustfile_raft.py | Ready | Raft protocol stress testing |

### 4. Chaos Tests (9+ experiments)
**Location:** `tests/chaos/`
**Framework:** Chaos Toolkit

| Experiment | Status | Real Infrastructure Needed |
|------------|--------|----------------------------|
| experiment_url_shortener.json | Ready | Cloud Run service |
| experiment_database_failure.json | Ready | Cloud SQL instance |
| experiment_cache_failure.json | Ready | Memorystore Redis |
| experiment_raft_leader_failure.json | Ready | 5-node Raft cluster |
| experiment_raft_network_partition.json | Ready | VPC network controls |

### 5. E2E Browser Tests (3 files)
**Location:** `e2e/tests/`
**Framework:** Playwright

| File | Status | Action |
|------|--------|--------|
| auth.spec.ts | Real (demo mode) | Add real OAuth flow |
| navigation.spec.ts | Real | Enhance coverage |
| submission.spec.ts | Real | Add deployment verification |

---

## Conversion Strategy

### Phase 1: Infrastructure Setup (Week 1)

```yaml
# GCP Test Infrastructure
resources:
  cloud_run:
    - url-shortener-test
    - file-sharing-test
    - chat-app-test
    - distributed-test-coordinator

  cloud_sql:
    - test-postgres-instance
    - test-postgres-replica

  memorystore:
    - test-redis-cluster (5 nodes)

  gke:
    - distributed-problems-cluster (5 nodes)
    - locust-cluster (10 workers)
```

### Phase 2: Convert Mock-Based Tests (Week 2-3)

#### 2.1 Convert test_distributed_api.py

**Before (Mocked):**
```python
@pytest.fixture
def mock_grpc_client():
    with patch('services.distributed.GrpcClientManager') as mock:
        mock.return_value.connect.return_value = MagicMock()
        yield mock

async def test_deploy_raft(mock_grpc_client):
    # Uses mocked gRPC client
    result = await service.deploy("raft", submission_id)
    mock_grpc_client.connect.assert_called_once()
```

**After (Real):**
```python
@pytest.fixture
async def real_grpc_cluster():
    """Provision real 5-node cluster for testing."""
    cluster = await provision_test_cluster(
        problem_type="raft",
        node_count=5,
        region="us-central1"
    )
    yield cluster
    await cleanup_test_cluster(cluster.id)

async def test_deploy_raft(real_grpc_cluster):
    # Uses real gRPC connections
    client = GrpcClientManager(real_grpc_cluster.endpoints)
    await client.connect()

    # Verify leader election
    status = await client.get_cluster_status()
    assert status.leader_id is not None
    assert len([n for n in status.nodes if n.state == "follower"]) == 4
```

#### 2.2 Convert test_distributed_tests.py

**Before:**
```python
def test_run_functional_tests():
    runner = DistributedTestRunner(mock_cluster)
    results = runner.run_tests(TestType.FUNCTIONAL)
    assert all(r.passed for r in results)
```

**After:**
```python
async def test_run_functional_tests_real(deployed_cluster):
    """Run functional tests against real deployed cluster."""
    runner = DistributedTestRunner(
        cluster_endpoints=deployed_cluster.endpoints,
        timeout=300
    )

    results = await runner.run_tests(
        test_type=TestType.FUNCTIONAL,
        problem_id="raft"
    )

    assert all(r.passed for r in results)

    # Verify against real gRPC responses
    for result in results:
        assert result.response_time_ms < 100
        assert result.cluster_state == "healthy"
```

### Phase 3: Enhance Functional Tests (Week 4)

#### 3.1 Add Authentication to Functional Tests

```python
# tests/functional/conftest.py
@pytest.fixture
async def authenticated_client():
    """Get authenticated HTTP client for real endpoints."""
    base_url = os.environ.get("TEST_BASE_URL", "https://api.example.com")

    # Get real OAuth token
    token = await get_test_oauth_token(
        client_id=os.environ["TEST_CLIENT_ID"],
        client_secret=os.environ["TEST_CLIENT_SECRET"]
    )

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"}
    ) as client:
        yield client
```

#### 3.2 Add Deployment Verification

```python
async def test_url_shortener_deployment(authenticated_client):
    """Verify URL shortener is correctly deployed."""
    # Health check
    health = await authenticated_client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    # Database connectivity
    assert health.json()["database"] == "connected"

    # Redis connectivity
    assert health.json()["cache"] == "connected"

    # Create and verify URL
    response = await authenticated_client.post("/api/v1/shorten", json={
        "url": "https://example.com/test"
    })
    assert response.status_code == 201

    short_code = response.json()["short_code"]

    # Verify redirect works
    redirect = await authenticated_client.get(
        f"/{short_code}",
        follow_redirects=False
    )
    assert redirect.status_code == 301
```

### Phase 4: Chaos Engineering Integration (Week 5)

#### 4.1 Connect Chaos Probes to Real GCP

```python
# tests/chaos/probes.py
async def check_service_health(service_name: str) -> bool:
    """Real GCP service health check."""
    from google.cloud import run_v2

    client = run_v2.ServicesAsyncClient()
    service = await client.get_service(
        name=f"projects/{PROJECT}/locations/{REGION}/services/{service_name}"
    )

    return service.latest_ready_revision is not None

async def check_database_connectivity() -> bool:
    """Real Cloud SQL connectivity check."""
    import asyncpg

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    result = await conn.fetchval("SELECT 1")
    await conn.close()

    return result == 1
```

#### 4.2 Real Chaos Actions

```python
# tests/chaos/actions.py
async def trigger_database_failover(instance_name: str):
    """Trigger real Cloud SQL failover."""
    from google.cloud import sqladmin_v1

    client = sqladmin_v1.SqlAdminServiceAsyncClient()

    operation = await client.failover(
        request={"project": PROJECT, "instance": instance_name}
    )

    # Wait for failover to complete
    await operation.result(timeout=300)

async def inject_network_latency(service_name: str, latency_ms: int):
    """Inject network latency using Traffic Director."""
    from google.cloud import networkservices_v1

    # Configure fault injection
    fault_config = {
        "delay": {
            "fixed_delay": f"{latency_ms}ms",
            "percentage": 100
        }
    }

    await update_traffic_policy(service_name, fault_config)
```

---

## Test Execution Strategy

### Local Development
```bash
# Run unit tests only (fast, no infra needed)
pytest backend/tests/test_config.py backend/tests/test_jwt.py backend/tests/test_schemas.py -v

# Run integration tests with local Docker
docker-compose -f docker-compose.test.yml up -d
pytest backend/tests/ -v --ignore=backend/tests/test_config.py
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: pytest backend/tests/test_*.py -v --ignore-glob="*integration*"

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:15
      redis:
        image: redis:7
    steps:
      - name: Run integration tests
        run: pytest backend/tests/ -v
        env:
          DATABASE_URL: postgresql://test@localhost/test
          REDIS_URL: redis://localhost:6379

  functional-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - name: Deploy to test environment
        run: ./scripts/deploy-test.sh
      - name: Run functional tests
        run: pytest tests/functional/ -v
        env:
          TEST_BASE_URL: ${{ secrets.TEST_BASE_URL }}

  performance-tests:
    runs-on: ubuntu-latest
    needs: functional-tests
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Run Locust tests
        run: |
          locust -f tests/performance/locustfile_url_shortener.py \
            --headless -u 100 -r 10 -t 60s \
            --host=${{ secrets.TEST_BASE_URL }}

  chaos-tests:
    runs-on: ubuntu-latest
    needs: performance-tests
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Run chaos experiments
        run: chaos run tests/chaos/experiment_url_shortener.json
        env:
          GCP_PROJECT: ${{ secrets.GCP_PROJECT }}
```

### Production Verification
```bash
# Smoke tests after deployment
pytest tests/functional/ -v -m smoke --base-url=https://production.example.com

# Full regression
pytest tests/functional/ tests/performance/ -v --base-url=https://production.example.com
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Unit Test Coverage | 85% | 90% |
| Integration Test Coverage | 70% | 85% |
| Functional Test Coverage | 60% | 95% |
| Mock-to-Real Ratio | 70:30 | 30:70 |
| CI Pipeline Time | N/A | < 15 min |
| Chaos Test Coverage | 5 scenarios | 15 scenarios |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Test infrastructure costs | High | Use preemptible VMs, auto-shutdown |
| Flaky tests | Medium | Add retries, improve isolation |
| Long CI times | Medium | Parallelize, cache dependencies |
| Data leakage | High | Separate test/prod projects |

---

## Timeline

- **Week 1:** Infrastructure setup, environment configuration
- **Week 2-3:** Convert mock-based distributed tests
- **Week 4:** Enhance functional tests with auth
- **Week 5:** Chaos engineering integration
- **Week 6:** Documentation, training, handoff

---

## Next Steps

1. Review and approve this plan
2. Create GCP test project and resources
3. Begin Phase 1 infrastructure setup
4. Update CI/CD pipeline configuration
