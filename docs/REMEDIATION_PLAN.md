# Repository Remediation Plan

**Created:** 2026-01-09
**Reference:** [REPOSITORY_ANALYSIS.md](./REPOSITORY_ANALYSIS.md)
**Total Phases:** 8
**Estimated Items:** 53

This plan provides step-by-step instructions for fixing all issues identified in the repository analysis. Each phase is self-contained and can be executed independently.

---

## Table of Contents

1. [Phase 1: Critical Code Fixes](#phase-1-critical-code-fixes)
2. [Phase 2: Redundant Code Elimination](#phase-2-redundant-code-elimination)
3. [Phase 3: Structure Cleanup](#phase-3-structure-cleanup)
4. [Phase 4: Documentation Updates](#phase-4-documentation-updates)
5. [Phase 5: New Documentation Creation](#phase-5-new-documentation-creation)
6. [Phase 6: Code Docstrings](#phase-6-code-docstrings)
7. [Phase 7: TypeScript Improvements](#phase-7-typescript-improvements)
8. [Phase 8: Tooling & Configuration](#phase-8-tooling--configuration)

---

## Phase 1: Critical Code Fixes

**Priority:** HIGH
**Scope:** Fix security issues, replace debug statements, fix exception handling

### Task 1.1: Replace Print Statements with Logging

**Files to modify:**

#### 1.1.1 `backend/auth/jwt_handler.py`

```bash
# Read the file first
Read backend/auth/jwt_handler.py
```

**Changes:**
1. Add logging import at top of file (after other imports):
```python
import logging

logger = logging.getLogger(__name__)
```

2. Replace line ~45:
```python
# FROM:
print(f"Token validation failed: {e}")
# TO:
logger.error(f"Token validation failed: {e}")
```

3. Replace line ~67:
```python
# FROM:
print(f"Token refresh failed: {e}")
# TO:
logger.error(f"Token refresh failed: {e}")
```

#### 1.1.2 `backend/services/orchestrator.py`

```bash
Read backend/services/orchestrator.py
```

**Changes:**
1. Ensure logging import exists, add if missing:
```python
import logging

logger = logging.getLogger(__name__)
```

2. Replace line ~156:
```python
# FROM:
print(f"Deployment started: {deployment_id}")
# TO:
logger.info(f"Deployment started: {deployment_id}")
```

#### 1.1.3 `backend/services/test_runner.py`

```bash
Read backend/services/test_runner.py
```

**Changes:**
1. Ensure logging import exists
2. Replace line ~89:
```python
# FROM:
print(f"Test execution: {test_id}")
# TO:
logger.info(f"Test execution: {test_id}")
```

#### 1.1.4 `tests/functional/conftest.py`

```bash
Read tests/functional/conftest.py
```

**Changes:**
1. Add logging import
2. Replace line ~144:
```python
# FROM:
print(f"Would cleanup {len(ids)} {resource_type}: {ids[:5]}...")
# TO:
logger.debug(f"Would cleanup {len(ids)} {resource_type}: {ids[:5]}...")
```

**Verification:**
```bash
grep -rn "print(" backend/auth/jwt_handler.py backend/services/orchestrator.py backend/services/test_runner.py tests/functional/conftest.py
# Should return no matches (or only legitimate print statements)
```

---

### Task 1.2: Fix Bare Exception Handlers

**Files to modify:**

#### 1.2.1 `backend/auth/oauth_providers.py` (line ~89)

```bash
Read backend/auth/oauth_providers.py
```

**Change:**
```python
# FROM:
except Exception:
    pass
# TO:
except (httpx.HTTPError, ValueError) as e:
    logger.warning(f"OAuth token exchange failed: {e}")
```

#### 1.2.2 `backend/services/ai_service.py` (line ~134)

```bash
Read backend/services/ai_service.py
```

**Change:**
```python
# FROM:
except Exception:
# TO:
except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
    logger.error(f"AI service error: {e}")
```

#### 1.2.3 `backend/services/deployment_service.py` (line ~201)

```bash
Read backend/services/deployment_service.py
```

**Change:**
```python
# FROM:
except Exception as e:
    pass  # or unused
# TO:
except (subprocess.SubprocessError, OSError) as e:
    logger.error(f"Deployment failed: {e}")
    raise DeploymentError(f"Deployment failed: {e}") from e
```

#### 1.2.4 `tests/conftest.py` (line ~156)

```bash
Read tests/conftest.py
```

**Change:**
```python
# FROM:
except Exception:
# TO:
except (ImportError, ConnectionError) as e:
    logger.debug(f"Optional dependency not available: {e}")
```

#### 1.2.5 `tests/functional/conftest.py` (line ~55)

```bash
Read tests/functional/conftest.py
```

**Change:**
```python
# FROM:
except Exception:
    pass
# TO:
except httpx.HTTPError:
    pass  # Token retrieval is optional
```

**Verification:**
```bash
grep -rn "except Exception:" backend/ tests/
# Review remaining matches - should be intentional catch-alls with comments
```

---

### Task 1.3: Remove Hardcoded Credentials

#### 1.3.1 `backend/config.py` (line ~67)

```bash
Read backend/config.py
```

**Change:**
```python
# FROM:
gcp_project_id: str = "system-design-platform-prod"
# TO:
gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")

# Add validation in __post_init__ or similar:
def validate(self):
    if not self.gcp_project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
```

#### 1.3.2 `tests/conftest.py` (lines ~60-62)

```bash
Read tests/conftest.py
```

**Change:**
```python
# FROM:
frontend_url=os.getenv("TEST_FRONTEND_URL", "https://sdp-frontend-zziiwqh26q-uc.a.run.app"),
backend_url=os.getenv("TEST_BACKEND_URL", "https://sdp-backend-zziiwqh26q-uc.a.run.app"),
admin_url=os.getenv("TEST_ADMIN_URL", "https://sdp-admin-zziiwqh26q-uc.a.run.app"),

# TO:
frontend_url=os.getenv("TEST_FRONTEND_URL", "http://localhost:3000"),
backend_url=os.getenv("TEST_BACKEND_URL", "http://localhost:8000"),
admin_url=os.getenv("TEST_ADMIN_URL", "http://localhost:3001"),
```

#### 1.3.3 `tests/functional/conftest.py` (lines ~20-23)

```bash
Read tests/functional/conftest.py
```

**Apply same changes as 1.3.2**

**Verification:**
```bash
grep -rn "zziiwqh26q" .
# Should return no matches in code files (may appear in state/log files)
```

---

### Task 1.4: Commit Phase 1

```bash
git add -A
git commit -m "Fix critical code issues: logging, exceptions, credentials

- Replace print() with proper logging in 4 files
- Fix bare exception handlers with specific exception types
- Remove hardcoded Cloud Run URLs from test configs
- Add GCP_PROJECT_ID validation

Phase 1 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2: Redundant Code Elimination

**Priority:** HIGH
**Scope:** Extract shared code, eliminate duplicates

### Task 2.1: Create Shared GrpcClientManager

#### 2.1.1 Create shared module

```bash
mkdir -p backend/solutions/distributed/shared
```

**Create file:** `backend/solutions/distributed/shared/__init__.py`
```python
"""Shared utilities for distributed consensus solutions."""

from .grpc_client import GrpcClientManager

__all__ = ["GrpcClientManager"]
```

**Create file:** `backend/solutions/distributed/shared/grpc_client.py`

```bash
# First, read one of the existing implementations to use as base
Read backend/solutions/distributed/01_raft/grpc_client.py
```

```python
"""
Shared gRPC client manager for distributed consensus solutions.

This module provides a singleton pattern for managing gRPC channel connections
to cluster nodes, with automatic retry and connection pooling.
"""

import grpc
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NodeConfig:
    """Configuration for a cluster node."""
    node_id: str
    host: str
    port: int = 50051
    secure: bool = True


class GrpcClientManager:
    """
    Manages gRPC connections to distributed cluster nodes.

    Implements singleton pattern per cluster to ensure connection reuse.
    Supports both secure (TLS) and insecure connections.

    Usage:
        manager = GrpcClientManager.get_instance("my-cluster")
        channel = manager.get_channel("node-1", "localhost", 50051)
        stub = MyServiceStub(channel)
    """

    _instances: Dict[str, "GrpcClientManager"] = {}

    def __init__(self, cluster_id: str):
        """Initialize manager for a specific cluster."""
        self.cluster_id = cluster_id
        self._channels: Dict[str, grpc.Channel] = {}
        self._node_configs: Dict[str, NodeConfig] = {}

    @classmethod
    def get_instance(cls, cluster_id: str) -> "GrpcClientManager":
        """Get or create singleton instance for cluster."""
        if cluster_id not in cls._instances:
            cls._instances[cluster_id] = cls(cluster_id)
        return cls._instances[cluster_id]

    def get_channel(
        self,
        node_id: str,
        host: str,
        port: int = 50051,
        secure: bool = True
    ) -> grpc.Channel:
        """
        Get or create a gRPC channel for a node.

        Args:
            node_id: Unique identifier for the node
            host: Hostname or IP address
            port: gRPC port (default: 50051)
            secure: Use TLS if True (default: True)

        Returns:
            grpc.Channel connected to the node
        """
        if node_id not in self._channels:
            target = f"{host}:{port}"
            if secure:
                credentials = grpc.ssl_channel_credentials()
                channel = grpc.secure_channel(target, credentials)
            else:
                channel = grpc.insecure_channel(target)

            self._channels[node_id] = channel
            self._node_configs[node_id] = NodeConfig(
                node_id=node_id, host=host, port=port, secure=secure
            )
            logger.debug(f"Created channel for {node_id} at {target}")

        return self._channels[node_id]

    def close_channel(self, node_id: str) -> None:
        """Close a specific channel."""
        if node_id in self._channels:
            self._channels[node_id].close()
            del self._channels[node_id]
            del self._node_configs[node_id]
            logger.debug(f"Closed channel for {node_id}")

    def close_all(self) -> None:
        """Close all channels for this cluster."""
        for node_id in list(self._channels.keys()):
            self.close_channel(node_id)
        logger.info(f"Closed all channels for cluster {self.cluster_id}")

    @classmethod
    def reset_all(cls) -> None:
        """Reset all instances (useful for testing)."""
        for instance in cls._instances.values():
            instance.close_all()
        cls._instances.clear()

    @property
    def connected_nodes(self) -> List[str]:
        """List of currently connected node IDs."""
        return list(self._channels.keys())
```

#### 2.1.2 Update existing implementations to use shared module

For each of the 9 files, replace the local GrpcClientManager with an import:

**Files to update:**
- `backend/solutions/distributed/01_raft/grpc_client.py`
- `backend/solutions/distributed/02_multi_paxos/grpc_client.py`
- `backend/solutions/distributed/03_viewstamped_replication/grpc_client.py`
- `backend/solutions/distributed/04_zab/grpc_client.py`
- `backend/solutions/distributed/05_chain_replication/grpc_client.py`
- `backend/solutions/distributed/06_pbft/grpc_client.py`
- `backend/solutions/distributed/07_gossip/grpc_client.py`
- `backend/solutions/distributed/08_crdt/grpc_client.py`
- `backend/solutions/distributed/09_two_phase_commit/grpc_client.py`

**For each file, replace content with:**

```python
"""
gRPC client module for [ALGORITHM_NAME] implementation.

Re-exports the shared GrpcClientManager for backwards compatibility.
"""

from backend.solutions.distributed.shared import GrpcClientManager

__all__ = ["GrpcClientManager"]

# For any algorithm-specific extensions, subclass here:
# class RaftGrpcClientManager(GrpcClientManager):
#     """Raft-specific gRPC client extensions."""
#     pass
```

**Verification:**
```bash
python -c "from backend.solutions.distributed.shared import GrpcClientManager; print('Import successful')"
```

---

### Task 2.2: Refactor OAuth URL Functions

```bash
Read backend/auth/oauth_providers.py
```

**Create dataclass for OAuth config:**

```python
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlencode

@dataclass
class OAuthProviderConfig:
    """Configuration for an OAuth provider."""
    name: str
    auth_url: str
    token_url: str
    client_id: str
    client_secret: str
    scopes: List[str]
    redirect_uri: str


def get_oauth_url(config: OAuthProviderConfig, state: str) -> str:
    """
    Generate OAuth authorization URL for any provider.

    Args:
        config: OAuth provider configuration
        state: CSRF state token

    Returns:
        Authorization URL with query parameters
    """
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "response_type": "code",
    }
    return f"{config.auth_url}?{urlencode(params)}"


# Provider configurations (loaded from environment)
OAUTH_PROVIDERS = {
    "google": OAuthProviderConfig(
        name="google",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        scopes=["openid", "email", "profile"],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
    ),
    "github": OAuthProviderConfig(
        name="github",
        auth_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        client_id=os.getenv("GITHUB_CLIENT_ID", ""),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
        scopes=["user:email"],
        redirect_uri=os.getenv("GITHUB_REDIRECT_URI", ""),
    ),
    # Add facebook, linkedin similarly
}


# Backwards-compatible functions
def get_google_auth_url(state: str) -> str:
    """Generate Google OAuth URL. Deprecated: use get_oauth_url() instead."""
    return get_oauth_url(OAUTH_PROVIDERS["google"], state)

def get_github_auth_url(state: str) -> str:
    """Generate GitHub OAuth URL. Deprecated: use get_oauth_url() instead."""
    return get_oauth_url(OAUTH_PROVIDERS["github"], state)

# ... similar for facebook, linkedin
```

---

### Task 2.3: Consolidate Test Fixtures

#### 2.3.1 Update `/tests/conftest.py` to be the single source

```bash
Read tests/conftest.py
Read backend/tests/conftest.py
```

Ensure `/tests/conftest.py` has all fixtures and `/backend/tests/conftest.py` imports from it:

**Update `backend/tests/conftest.py`:**

```python
"""
Pytest configuration for backend unit tests.

Imports shared fixtures from the main tests/conftest.py and adds
backend-specific fixtures for unit testing.
"""

# Import shared fixtures
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.conftest import (
    test_config,
    sync_client,
    async_client,
    unauthenticated_client,
    gcp_credentials,
    event_loop,
)

# Backend-specific fixtures below
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests."""
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock(return_value=True)
    redis.delete = MagicMock(return_value=1)
    return redis
```

---

### Task 2.4: Create Single Source for Enums

**Create file:** `backend/models/enums.py`

```python
"""
Shared enumerations for the System Design Platform.

This module is the single source of truth for all enum definitions.
Import from here rather than defining enums in multiple places.
"""

from enum import Enum


class TestType(str, Enum):
    """Types of tests that can be run against submissions."""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    CHAOS = "chaos"
    E2E = "e2e"


class TestStatus(str, Enum):
    """Status of a test execution."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class SubmissionStatus(str, Enum):
    """Status of a submission."""
    PENDING = "pending"
    VALIDATING = "validating"
    BUILDING = "building"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProblemDifficulty(str, Enum):
    """Difficulty levels for problems."""
    L5 = "L5"
    L6 = "L6"
    L7 = "L7"


class ProblemCategory(str, Enum):
    """Categories of problems."""
    SYSTEM_DESIGN = "system_design"
    DISTRIBUTED_CONSENSUS = "distributed_consensus"
```

**Update imports in all files that define these enums:**

Files to update:
- `backend/models/submission.py` - Import from enums.py
- `backend/schemas/submission.py` - Import from enums.py
- `backend/services/test_runner.py` - Import from enums.py
- `backend/services/orchestrator.py` - Import from enums.py

**Example update for `backend/models/submission.py`:**

```python
# FROM:
class TestType(str, Enum):
    UNIT = "unit"
    ...

# TO:
from backend.models.enums import TestType, TestStatus, SubmissionStatus
```

---

### Task 2.5: Consolidate Validation Logic

```bash
Read backend/services/validation_service.py
Read backend/api/submissions.py
Read backend/solutions/url_shortener/validator.py
```

**Create shared validation module:** `backend/utils/validators.py`

```python
"""
Shared validation utilities.

Centralizes all validation logic to avoid duplication across services.
"""

import re
from typing import Optional
from urllib.parse import urlparse


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate a URL string.

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False, f"Invalid scheme: {parsed.scheme}. Must be http or https"

        if not parsed.netloc:
            return False, "URL must have a valid domain"

        # Check for valid domain format
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$'
        if not re.match(domain_pattern, parsed.netloc.split(':')[0]):
            return False, f"Invalid domain format: {parsed.netloc}"

        return True, None

    except Exception as e:
        return False, f"URL parsing error: {e}"


def validate_short_code(code: str) -> tuple[bool, Optional[str]]:
    """
    Validate a short code for URL shortener.

    Args:
        code: Short code to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not code:
        return False, "Short code cannot be empty"

    if len(code) < 4 or len(code) > 10:
        return False, "Short code must be 4-10 characters"

    if not re.match(r'^[a-zA-Z0-9_-]+$', code):
        return False, "Short code can only contain alphanumeric characters, hyphens, and underscores"

    return True, None
```

**Update files to use shared validators:**

```python
# In backend/services/validation_service.py, backend/api/submissions.py, etc.
from backend.utils.validators import validate_url, validate_short_code
```

---

### Task 2.6: Commit Phase 2

```bash
git add -A
git commit -m "Eliminate redundant code: shared modules and single sources of truth

- Create shared GrpcClientManager in backend/solutions/distributed/shared/
- Refactor OAuth URL functions to use generic get_oauth_url()
- Consolidate test fixtures in tests/conftest.py
- Create backend/models/enums.py as single source for all enums
- Create backend/utils/validators.py for shared validation logic

Phase 2 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3: Structure Cleanup

**Priority:** MEDIUM
**Scope:** Remove duplicates, consolidate configurations

### Task 3.1: Handle Root Dockerfile

```bash
Read Dockerfile
Read backend/Dockerfile
```

**Decision tree:**
1. If root Dockerfile is used by any CI/CD → Document its purpose
2. If not used → Remove it

**Action (if unused):**
```bash
git rm Dockerfile
```

**Or add documentation comment if needed:**
```dockerfile
# Dockerfile at root - DEPRECATED
# Use service-specific Dockerfiles instead:
# - backend/Dockerfile
# - frontend/Dockerfile
# - admin/Dockerfile
#
# This file is kept for local development convenience only.
```

---

### Task 3.2: Remove Duplicate requirements.txt

```bash
diff requirements.txt backend/requirements.txt
```

**If identical or subset:**
```bash
git rm requirements.txt
```

**Update any references to use `backend/requirements.txt`**

---

### Task 3.3: Document Test Organization

**Create file:** `tests/README.md`

```markdown
# Test Organization

This document explains the test directory structure.

## Directory Structure

```
tests/                      # Integration, functional, and chaos tests
├── conftest.py            # Shared fixtures for all test types
├── functional/            # End-to-end functional tests
│   ├── conftest.py       # Functional test fixtures
│   └── test_*.py         # Functional test files
├── chaos/                 # Chaos engineering tests
│   ├── actions.py        # Chaos actions (failure injection)
│   ├── probes.py         # Health probes
│   └── experiments/      # Chaos experiment definitions
└── integration/          # Integration tests

backend/tests/             # Backend unit tests
├── conftest.py           # Backend-specific fixtures (imports from tests/)
├── test_*.py             # Unit test files
└── mocks/                # Mock implementations
```

## Test Types

| Type | Location | Purpose | Markers |
|------|----------|---------|---------|
| Unit | `backend/tests/` | Test individual functions/classes | None |
| Integration | `tests/integration/` | Test service interactions | `@pytest.mark.integration` |
| Functional | `tests/functional/` | End-to-end API tests | `@pytest.mark.e2e` |
| Chaos | `tests/chaos/` | Failure injection tests | `@pytest.mark.chaos` |

## Running Tests

```bash
# All backend unit tests
pytest backend/tests/

# Integration tests only
pytest tests/ -m integration

# Functional tests (requires deployed services)
TEST_BACKEND_URL=https://... pytest tests/functional/

# Chaos tests (requires GCP)
pytest tests/chaos/ -m chaos
```

## Fixtures

Shared fixtures are defined in `tests/conftest.py`. Backend tests import these.
See `tests/conftest.py` for available fixtures.
```

---

### Task 3.4: Consolidate Solution Directories

```bash
# Check what's in /solutions/
ls -la solutions/
```

**If `/solutions/` only has templates:**
1. Move templates to `backend/solutions/templates/`
2. Remove `/solutions/` directory

```bash
mkdir -p backend/solutions/templates
mv solutions/* backend/solutions/templates/
rmdir solutions
```

**Update any imports that reference `/solutions/`**

---

### Task 3.5: Commit Phase 3

```bash
git add -A
git commit -m "Clean up repository structure

- Remove/document unused root Dockerfile
- Remove duplicate requirements.txt
- Add tests/README.md documenting test organization
- Consolidate solution directories

Phase 3 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4: Documentation Updates

**Priority:** HIGH
**Scope:** Fix incorrect docs, update outdated information

### Task 4.1: Fix API.md Rate Limiting Section

```bash
Read docs/API.md offset=630 limit=20
```

**Replace the rate limiting section (around line 638):**

```markdown
## Rate Limiting

The API implements rate limiting to prevent abuse. Limits are configured per endpoint type:

| Endpoint Type | Authenticated | Unauthenticated |
|--------------|---------------|-----------------|
| Submissions | 5/hour | 2/hour |
| Validation | 20/hour | 10/hour |
| General API | 100/minute | 20/minute |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

When rate limited, the API returns:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 3600
}
```

Configuration is done via environment variables:
- `RATE_LIMIT_ENABLED`: Enable/disable rate limiting (default: true)
- `RATE_LIMIT_SUBMISSIONS_PER_HOUR`: Submission limit (default: 5)
- `RATE_LIMIT_VALIDATE_PER_HOUR`: Validation limit (default: 20)
```

---

### Task 4.2: Add Distributed API Documentation to API.md

**Add new section to `docs/API.md`:**

```markdown
## Distributed Consensus API

Endpoints for distributed consensus problems (Raft, Paxos, etc.).

### List Distributed Problems

```
GET /api/distributed/problems
```

**Response:**
```json
{
  "problems": [
    {
      "id": "01-raft",
      "title": "Raft Consensus",
      "difficulty": "L6",
      "category": "distributed_consensus",
      "description": "Implement the Raft consensus algorithm"
    }
  ]
}
```

### Get Distributed Problem

```
GET /api/distributed/problems/{problem_id}
```

**Response:**
```json
{
  "id": "01-raft",
  "title": "Raft Consensus",
  "difficulty": "L6",
  "description": "...",
  "requirements": [...],
  "grpc_service_definition": "...",
  "test_scenarios": [...]
}
```

### Create Distributed Submission

```
POST /api/distributed/submissions
```

**Request:**
```json
{
  "problem_id": "01-raft",
  "language": "python",
  "code": "...",
  "cluster_size": 5
}
```

**Response:**
```json
{
  "submission_id": "sub_abc123",
  "status": "pending",
  "cluster_id": "cluster_xyz",
  "nodes": [
    {"node_id": "node-0", "url": "..."},
    {"node_id": "node-1", "url": "..."}
  ]
}
```

### Get Language Templates

```
GET /api/distributed/{submission_id}/language-templates
```

**Response:**
```json
{
  "templates": {
    "python": "# Python template...",
    "go": "// Go template...",
    "rust": "// Rust template..."
  }
}
```
```

---

### Task 4.3: Add WebSocket Documentation to API.md

**Add new section:**

```markdown
## WebSocket API

Real-time updates for submission status.

### Connection

```
WS /ws/submissions/{submission_id}
```

**Authentication:** Include token in query string or header:
```
/ws/submissions/sub_abc123?token=<auth_token>
```

### Message Types

**Server → Client:**

```json
// Status update
{
  "type": "status",
  "status": "building",
  "progress": 45,
  "message": "Building container image..."
}

// Test result
{
  "type": "test_result",
  "test_name": "leader_election",
  "status": "passed",
  "duration_ms": 1234
}

// Error
{
  "type": "error",
  "code": "BUILD_FAILED",
  "message": "Compilation error on line 45"
}

// Completion
{
  "type": "complete",
  "final_status": "passed",
  "summary": {...}
}
```

**Client → Server:**

```json
// Heartbeat (keep connection alive)
{
  "type": "ping"
}
```

### Connection Lifecycle

1. Client connects to WebSocket URL
2. Server sends initial status
3. Server pushes updates as they occur
4. Client sends ping every 30s to keep alive
5. Server sends completion message when done
6. Either side can close connection
```

---

### Task 4.4: Update ARCHITECTURE.md with Missing Services

```bash
Read docs/ARCHITECTURE.md
```

**Add section for new services:**

```markdown
## Service Layer (Extended)

### WarmPoolService

Manages pre-warmed container instances for sub-second deployment.

```
┌─────────────────────────────────────────┐
│           WarmPoolService               │
├─────────────────────────────────────────┤
│ - Maintains pool of idle containers     │
│ - Assigns containers to submissions     │
│ - Monitors pool health                  │
│ - Auto-scales based on demand           │
└─────────────────────────────────────────┘
```

**Key methods:**
- `acquire_container(problem_type)` - Get warm container
- `release_container(container_id)` - Return to pool
- `scale_pool(target_size)` - Adjust pool size

### FastDeploymentService

Handles rapid deployment to Cloud Run for distributed consensus testing.

**Deployment modes:**
1. **Warm Pool** - Use pre-provisioned containers (~500ms)
2. **Cloud Run** - Fresh deployment (~30s)
3. **Local** - Development mode

### ErrorAnalyzer

AI-powered analysis of submission failures.

```python
class ErrorAnalyzer:
    async def analyze(self, error: str, code: str) -> Analysis:
        """
        Analyze error and provide suggestions.

        Returns:
            - error_type: Category of error
            - root_cause: Likely cause
            - suggestions: List of fixes
            - similar_errors: Related past errors
        """
```

### AuditService

Tracks all significant events for compliance and debugging.

**Logged events:**
- Submission creation/completion
- Authentication attempts
- Admin actions
- System errors

### CleanupScheduler

Background service for resource cleanup.

**Scheduled tasks:**
- Delete expired containers (every 5 min)
- Clean old submissions (daily)
- Prune build cache (weekly)
```

---

### Task 4.5: Fix DEPLOYMENT.md

```bash
Read docs/DEPLOYMENT.md offset=60 limit=30
```

**Replace manual table creation with Alembic approach:**

```markdown
## Database Migrations

We use Alembic for database migrations.

### Setup

```bash
# Initialize Alembic (already done)
cd backend
alembic init alembic

# Create a migration
alembic revision --autogenerate -m "Add new table"

# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

### Creating Migrations

```bash
# After modifying models
alembic revision --autogenerate -m "Description of changes"

# Review generated migration in alembic/versions/
# Then apply
alembic upgrade head
```

### Production Migrations

```bash
# Set DATABASE_URL for production
export DATABASE_URL="postgresql://..."

# Run migrations
alembic upgrade head
```

**Note:** Never modify production database schema manually. Always use migrations.
```

---

### Task 4.6: Fix NEXT_STEPS.md CONTRIBUTING.md Reference

```bash
Read docs/NEXT_STEPS.md offset=330 limit=10
```

**Either:**
1. Remove the reference to CONTRIBUTING.md, OR
2. Create the file (see Phase 5)

---

### Task 4.7: Commit Phase 4

```bash
git add -A
git commit -m "Update documentation: fix inaccuracies and add missing sections

- Fix rate limiting documentation in API.md (was incorrectly stating 'not implemented')
- Add distributed consensus API documentation
- Add WebSocket API documentation
- Update ARCHITECTURE.md with WarmPoolService, ErrorAnalyzer, etc.
- Fix DEPLOYMENT.md to show Alembic approach

Phase 4 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 5: New Documentation Creation

**Priority:** HIGH
**Scope:** Create missing documentation files

### Task 5.1: Create DISTRIBUTED_CONSENSUS.md

**Create file:** `docs/DISTRIBUTED_CONSENSUS.md`

```markdown
# Distributed Consensus Architecture

This document describes the architecture for distributed consensus problems.

## Overview

Distributed consensus problems (Raft, Paxos, etc.) require deploying user code
across multiple nodes that communicate via gRPC.

```
┌─────────────────────────────────────────────────────────────┐
│                    Submission Flow                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Code    Build      Deploy         Test                │
│  ────────► Container ► 5 Nodes ► Chaos Scenarios           │
│                          │                                  │
│                    ┌─────┴─────┐                           │
│                    ▼     ▼     ▼                           │
│                 Node0  Node1  Node2...                     │
│                    │     │     │                           │
│                    └──gRPC────┘                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Cluster Architecture

Each submission deploys a 5-node cluster:

| Node | Role | Purpose |
|------|------|---------|
| node-0 | Initial Leader | Starts as leader candidate |
| node-1 to node-4 | Followers | Join cluster, participate in consensus |

### Node Communication

Nodes communicate via gRPC using the service definition provided in each problem.

```protobuf
service ConsensusNode {
  rpc RequestVote(VoteRequest) returns (VoteResponse);
  rpc AppendEntries(AppendRequest) returns (AppendResponse);
  rpc ClientRequest(ClientRequest) returns (ClientResponse);
}
```

## Build Pipeline

1. **Code Validation** - Syntax check, import verification
2. **Container Build** - Multi-stage Docker build
3. **Image Push** - Push to Artifact Registry
4. **Cluster Deploy** - Deploy 5 Cloud Run services
5. **Health Check** - Verify all nodes responding
6. **Test Execution** - Run test scenarios

### Build Configuration

```yaml
# cloudbuild-distributed.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '$_IMAGE', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '$_IMAGE']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: 'gcloud'
    args: ['run', 'deploy', ...]
```

## Test Scenarios

Each problem includes chaos scenarios:

| Scenario | Description |
|----------|-------------|
| `leader_election` | Kill leader, verify new election |
| `network_partition` | Split cluster, verify consistency |
| `log_replication` | Write to leader, verify replication |
| `client_redirect` | Client contacts follower, verify redirect |

## Language Support

Templates provided for:
- Python (reference implementation)
- Go
- Rust
- Java

See `/api/distributed/{submission_id}/language-templates` for templates.

## Local Development

```bash
# Start local 5-node cluster
docker-compose -f docker-compose.distributed.yml up

# Run tests against local cluster
pytest tests/distributed/ --cluster-url=localhost
```
```

---

### Task 5.2: Create WEBSOCKET.md

**Create file:** `docs/WEBSOCKET.md`

```markdown
# WebSocket Real-Time Updates

This document describes the WebSocket system for real-time submission updates.

## Overview

The WebSocket API provides real-time updates during submission processing,
eliminating the need for polling.

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Client  │────►│  WebSocket   │────►│   Backend    │
│          │◄────│   Server     │◄────│   Services   │
└──────────┘     └──────────────┘     └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │    Redis     │
                │   Pub/Sub    │
                └──────────────┘
```

## Connection Flow

1. Client submits code via REST API
2. Client receives `submission_id`
3. Client connects to WebSocket: `/ws/submissions/{submission_id}`
4. Server authenticates connection
5. Server subscribes to Redis channel for submission
6. Server pushes updates as they occur
7. Server sends completion message
8. Connection closes

## Message Protocol

### Server Messages

```typescript
interface StatusMessage {
  type: 'status';
  status: 'pending' | 'building' | 'testing' | 'completed' | 'failed';
  progress: number;  // 0-100
  message: string;
}

interface TestResultMessage {
  type: 'test_result';
  test_name: string;
  status: 'passed' | 'failed' | 'skipped';
  duration_ms: number;
  error?: string;
}

interface LogMessage {
  type: 'log';
  level: 'info' | 'warn' | 'error';
  message: string;
  timestamp: string;
}

interface CompleteMessage {
  type: 'complete';
  final_status: 'passed' | 'failed';
  summary: {
    total_tests: number;
    passed: number;
    failed: number;
    duration_ms: number;
  };
}
```

### Client Messages

```typescript
interface PingMessage {
  type: 'ping';
}

interface CancelMessage {
  type: 'cancel';  // Request cancellation
}
```

## Authentication

Include auth token in connection:

```javascript
// Option 1: Query parameter
const ws = new WebSocket(`wss://api.example.com/ws/submissions/${id}?token=${token}`);

// Option 2: Subprotocol (recommended)
const ws = new WebSocket(`wss://api.example.com/ws/submissions/${id}`, [token]);
```

## Client Implementation

```javascript
class SubmissionWatcher {
  constructor(submissionId, token) {
    this.ws = new WebSocket(
      `wss://api.example.com/ws/submissions/${submissionId}?token=${token}`
    );

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    // Send heartbeat every 30s
    this.heartbeat = setInterval(() => {
      this.ws.send(JSON.stringify({ type: 'ping' }));
    }, 30000);
  }

  handleMessage(message) {
    switch (message.type) {
      case 'status':
        console.log(`Status: ${message.status} (${message.progress}%)`);
        break;
      case 'test_result':
        console.log(`Test ${message.test_name}: ${message.status}`);
        break;
      case 'complete':
        console.log('Submission complete!', message.summary);
        this.close();
        break;
    }
  }

  close() {
    clearInterval(this.heartbeat);
    this.ws.close();
  }
}
```

## Error Handling

| Error Code | Description | Action |
|------------|-------------|--------|
| 4001 | Invalid token | Re-authenticate |
| 4004 | Submission not found | Check ID |
| 4029 | Rate limited | Wait and retry |
| 1011 | Server error | Reconnect with backoff |

## Reconnection Strategy

```javascript
function connectWithRetry(url, maxAttempts = 5) {
  let attempts = 0;

  function connect() {
    const ws = new WebSocket(url);

    ws.onclose = (event) => {
      if (event.code !== 1000 && attempts < maxAttempts) {
        attempts++;
        const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
        setTimeout(connect, delay);
      }
    };

    return ws;
  }

  return connect();
}
```
```

---

### Task 5.3: Create CONTRIBUTING.md

**Create file:** `docs/CONTRIBUTING.md`

```markdown
# Contributing to System Design Platform

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   cd backend && pip install -r requirements.txt
   cd frontend && npm install
   ```
3. Set up environment variables (copy `.env.example` to `.env`)
4. Start development servers:
   ```bash
   # Backend
   cd backend && uvicorn main:app --reload

   # Frontend
   cd frontend && npm run dev
   ```

## Code Style

### Python
- Follow PEP 8
- Use type hints for all functions
- Run `black` and `isort` before committing
- Maximum line length: 88 characters

### TypeScript
- Use strict mode
- Avoid `any` type - define proper interfaces
- Run `eslint` and `prettier` before committing

## Testing

- Write tests for new features
- Maintain test coverage above 80%
- Run tests before submitting PR:
  ```bash
  pytest backend/tests/
  npm test --prefix frontend
  ```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Update documentation if needed
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit PR with clear description

## Commit Messages

Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

## Adding New Problems

See `docs/problems/TEMPLATE.md` for the problem documentation template.

1. Create directory: `docs/problems/{category}/{id}-{name}/`
2. Add `README.md` with problem description
3. Add solution templates in `backend/solutions/`
4. Add test cases
5. Update problem registry

## Questions?

Open an issue or reach out to the maintainers.
```

---

### Task 5.4: Create AUDIT_AND_SECURITY.md

**Create file:** `docs/AUDIT_AND_SECURITY.md`

```markdown
# Audit and Security

This document describes the audit logging and security features.

## Audit Logging

All significant events are logged for compliance and debugging.

### Logged Events

| Event Type | Description | Data Captured |
|------------|-------------|---------------|
| `auth.login` | User login | user_id, provider, ip |
| `auth.logout` | User logout | user_id |
| `auth.failed` | Failed auth attempt | ip, reason |
| `submission.created` | New submission | user_id, problem_id |
| `submission.completed` | Submission finished | submission_id, status |
| `admin.action` | Admin operation | admin_id, action, target |
| `system.error` | System error | service, error, stack |

### Audit Log Schema

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,
  user_id UUID REFERENCES users(id),
  ip_address INET,
  user_agent TEXT,
  data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_event ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

### Querying Audit Logs

```python
# Get recent failed logins
logs = await AuditService.query(
    event_type="auth.failed",
    since=datetime.now() - timedelta(hours=1)
)

# Get user activity
logs = await AuditService.query(
    user_id=user_id,
    limit=100
)
```

## Security Measures

### Authentication

- OAuth 2.0 with Google, GitHub, LinkedIn, Facebook
- JWT tokens with 24h expiry
- Refresh tokens with 7d expiry
- Token rotation on refresh

### Authorization

- Role-based access control (RBAC)
- Roles: `user`, `admin`, `reviewer`
- Permission checks on all endpoints

### Rate Limiting

- Per-user and per-IP limits
- Configurable per endpoint
- Redis-backed for distributed deployments

### Input Validation

- All inputs validated and sanitized
- SQL injection prevention via ORM
- XSS prevention via output encoding

### Code Execution

- User code runs in isolated containers
- No network access (except to cluster nodes)
- Resource limits (CPU, memory, time)
- Read-only filesystem (except /tmp)

### Secrets Management

- Secrets stored in environment variables
- Never logged or exposed in errors
- Rotated regularly

## Incident Response

1. Detect via monitoring/alerts
2. Assess severity and scope
3. Contain the incident
4. Investigate root cause
5. Remediate and recover
6. Document and review
```

---

### Task 5.5: Commit Phase 5

```bash
git add -A
git commit -m "Create missing documentation files

- Add DISTRIBUTED_CONSENSUS.md - cluster architecture and build pipeline
- Add WEBSOCKET.md - real-time update protocol
- Add CONTRIBUTING.md - contribution guidelines
- Add AUDIT_AND_SECURITY.md - security and audit logging

Phase 5 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 6: Code Docstrings

**Priority:** MEDIUM
**Scope:** Add missing docstrings to code files

### Task 6.1: Add Docstrings to Middleware

#### 6.1.1 `backend/middleware/audit_middleware.py`

```bash
Read backend/middleware/audit_middleware.py
```

**Add module docstring at top:**

```python
"""
Audit logging middleware for FastAPI.

This middleware captures and logs all HTTP requests for compliance
and debugging purposes. Logs include request/response metadata,
timing information, and user context.

Usage:
    app.add_middleware(AuditMiddleware)

Configuration:
    - AUDIT_LOG_ENABLED: Enable/disable audit logging
    - AUDIT_LOG_LEVEL: Minimum level to log (info, warn, error)
"""
```

**Add docstrings to functions/classes:**

```python
class AuditMiddleware:
    """
    FastAPI middleware for audit logging.

    Captures request metadata, response status, and timing for all
    HTTP requests. Logs are written to the audit service.

    Attributes:
        app: The FastAPI application instance
        exclude_paths: Paths to exclude from logging (e.g., /health)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and log audit entry.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response from handler
        """
```

#### 6.1.2 `backend/middleware/rate_limiter.py`

```bash
Read backend/middleware/rate_limiter.py
```

**Add module docstring:**

```python
"""
Rate limiting middleware for FastAPI.

Implements token bucket rate limiting with Redis backend for
distributed deployments. Limits can be configured per endpoint
and per user/IP.

Configuration:
    - RATE_LIMIT_ENABLED: Enable/disable rate limiting
    - RATE_LIMIT_DEFAULT_PER_MINUTE: Default limit for all endpoints
    - REDIS_URL: Redis connection URL for distributed state

Usage:
    app.add_middleware(RateLimitMiddleware)

    # Or with custom config
    app.add_middleware(RateLimitMiddleware, limits={
        "/api/submissions": 5,  # 5 per hour
        "/api/validate": 20,    # 20 per hour
    })
"""
```

---

### Task 6.2: Add Docstrings to WebSocket Module

```bash
Read backend/websocket/routes.py
```

**Add module docstring:**

```python
"""
WebSocket routes for real-time submission updates.

This module provides WebSocket endpoints for clients to receive
real-time updates during submission processing. Updates include
status changes, test results, and completion notifications.

Endpoints:
    /ws/submissions/{submission_id} - Subscribe to submission updates

Authentication:
    Token can be provided via query parameter or subprotocol.

Example:
    ws = websocket.connect(f"/ws/submissions/{id}?token={token}")
    async for message in ws:
        handle_update(message)
"""
```

---

### Task 6.3: Add Docstrings to Prompts Module

```bash
ls backend/prompts/
Read backend/prompts/__init__.py  # or main prompt file
```

**Add docstrings to each prompt function:**

```python
"""
AI prompt templates for the System Design Platform.

This module contains prompt templates used by the AI service for
code analysis, error explanation, and feedback generation.
"""


def get_code_review_prompt(code: str, problem_type: str) -> str:
    """
    Generate prompt for AI code review.

    Args:
        code: User-submitted code to review
        problem_type: Type of problem (url_shortener, raft, etc.)

    Returns:
        Formatted prompt for AI model

    Example:
        prompt = get_code_review_prompt(user_code, "url_shortener")
        response = await ai_service.generate(prompt)
    """


def get_error_analysis_prompt(error: str, code: str, context: dict) -> str:
    """
    Generate prompt for error analysis.

    Args:
        error: Error message or stack trace
        code: Code that produced the error
        context: Additional context (test name, expected behavior)

    Returns:
        Formatted prompt for AI error analysis
    """
```

---

### Task 6.4: Add Docstrings to Error Analyzer

```bash
Read backend/services/error_analyzer.py
```

**Add comprehensive docstrings:**

```python
"""
AI-powered error analysis service.

This service analyzes submission errors using AI to provide
helpful feedback to users. It categorizes errors, identifies
root causes, and suggests fixes.
"""


class ErrorAnalyzer:
    """
    Analyzes errors from submission test failures.

    Uses AI models to understand error messages and provide
    actionable feedback to users. Maintains a cache of common
    errors for faster responses.

    Attributes:
        ai_service: AI service for generating analysis
        cache: Redis cache for common error patterns

    Example:
        analyzer = ErrorAnalyzer(ai_service)
        result = await analyzer.analyze(error, code)
        print(result.suggestions)
    """

    async def analyze(
        self,
        error: str,
        code: str,
        problem_type: str = None
    ) -> ErrorAnalysis:
        """
        Analyze an error and provide suggestions.

        Args:
            error: Error message or stack trace
            code: User code that produced the error
            problem_type: Optional problem type for context

        Returns:
            ErrorAnalysis with category, root cause, and suggestions

        Raises:
            AIServiceError: If AI service is unavailable
        """
```

---

### Task 6.5: Commit Phase 6

```bash
git add -A
git commit -m "Add docstrings to middleware, websocket, and service modules

- Add module and function docstrings to audit_middleware.py
- Add module and function docstrings to rate_limiter.py
- Add module and function docstrings to websocket/routes.py
- Add module and function docstrings to prompts/*.py
- Add class and method docstrings to error_analyzer.py

Phase 6 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 7: TypeScript Improvements

**Priority:** MEDIUM
**Scope:** Replace `any` types, add proper interfaces

### Task 7.1: Fix Frontend API Client Types

```bash
Read frontend/src/api/client.ts
```

**Add proper interfaces:**

```typescript
// Add at top of file or in types/api.ts

interface ApiResponse<T> {
  data: T;
  status: number;
  message?: string;
}

interface Problem {
  id: string;
  title: string;
  description: string;
  difficulty: 'L5' | 'L6' | 'L7';
  category: 'system_design' | 'distributed_consensus';
}

interface Submission {
  id: string;
  problem_id: string;
  status: 'pending' | 'building' | 'testing' | 'completed' | 'failed';
  code: string;
  created_at: string;
  results?: TestResults;
}

interface TestResults {
  total: number;
  passed: number;
  failed: number;
  tests: TestResult[];
}

interface TestResult {
  name: string;
  status: 'passed' | 'failed' | 'skipped';
  duration_ms: number;
  error?: string;
}
```

**Replace `any` with proper types:**

```typescript
// FROM:
async function getProblems(): Promise<any> {
  const response: any = await fetch('/api/problems');
  return response.json();
}

// TO:
async function getProblems(): Promise<ApiResponse<Problem[]>> {
  const response = await fetch('/api/problems');
  return response.json() as Promise<ApiResponse<Problem[]>>;
}
```

---

### Task 7.2: Fix DesignEditor Component Types

```bash
Read frontend/src/components/DesignEditor.tsx
```

**Define proper props interface:**

```typescript
interface DesignEditorProps {
  problemId: string;
  initialCode?: string;
  language?: 'python' | 'go' | 'rust' | 'java';
  onSubmit: (code: string) => Promise<void>;
  onSave?: (code: string) => void;
  readOnly?: boolean;
}

// Replace any props
const DesignEditor: React.FC<DesignEditorProps> = ({
  problemId,
  initialCode = '',
  language = 'python',
  onSubmit,
  onSave,
  readOnly = false,
}) => {
  // ...
};
```

---

### Task 7.3: Fix Admin API Client Types

```bash
Read admin/src/api/client.ts
```

**Apply same changes as frontend client (Task 7.1)**

---

### Task 7.4: Add Type Hints to Python Utils

```bash
Read backend/utils/helpers.py
```

**Add type hints to all functions:**

```python
from typing import Any, Dict, List, Optional, TypeVar, Callable
from datetime import datetime

T = TypeVar('T')


def safe_get(data: Dict[str, Any], key: str, default: T = None) -> Optional[T]:
    """Safely get value from dict with default."""
    return data.get(key, default)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string."""
    return dt.strftime(fmt)


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """Split list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Callable[..., T]:
    """Decorator for retrying functions with exponential backoff."""
    # ...
```

---

### Task 7.5: Commit Phase 7

```bash
git add -A
git commit -m "Add TypeScript interfaces and Python type hints

- Define proper API response interfaces in frontend
- Replace 'any' types with specific interfaces
- Add type hints to backend/utils/helpers.py
- Add types to DesignEditor component props

Phase 7 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 8: Tooling & Configuration

**Priority:** LOW
**Scope:** Set up linting, formatting, pre-commit hooks

### Task 8.1: Configure Python Linting

**Update `pyproject.toml`:**

```toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
exclude = '''
/(
    \.git
    | \.venv
    | build
    | dist
    | migrations
)/
'''

[tool.isort]
profile = "black"
line_length = 88
skip = [".git", ".venv", "migrations"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.flake8]
max-line-length = 88
extend-ignore = ["E203", "E501", "W503"]
exclude = [".git", ".venv", "migrations"]
```

---

### Task 8.2: Configure TypeScript Linting

**Update `frontend/.eslintrc.js`:**

```javascript
module.exports = {
  extends: [
    'react-app',
    'react-app/jest',
    'plugin:@typescript-eslint/recommended',
  ],
  rules: {
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/explicit-function-return-type': 'warn',
    '@typescript-eslint/no-unused-vars': 'error',
  },
};
```

---

### Task 8.3: Add Pre-commit Hooks

**Create `.pre-commit-config.yaml`:**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest backend/tests/ -x -q
        language: system
        pass_filenames: false
        always_run: true
```

**Setup instructions:**
```bash
pip install pre-commit
pre-commit install
```

---

### Task 8.4: Fix Import Ordering

Run isort on all Python files:

```bash
cd backend && isort .
```

Run ESLint fix on TypeScript:

```bash
cd frontend && npm run lint -- --fix
cd admin && npm run lint -- --fix
```

---

### Task 8.5: Final Commit

```bash
git add -A
git commit -m "Add linting configuration and pre-commit hooks

- Configure black, isort, flake8, mypy in pyproject.toml
- Configure ESLint for TypeScript strict mode
- Add .pre-commit-config.yaml
- Fix import ordering in all files

Phase 8 of REMEDIATION_PLAN.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Execution Checklist

Use this checklist to track progress:

```
Phase 1: Critical Code Fixes
[ ] Task 1.1: Replace print statements with logging
[ ] Task 1.2: Fix bare exception handlers
[ ] Task 1.3: Remove hardcoded credentials
[ ] Task 1.4: Commit Phase 1

Phase 2: Redundant Code Elimination
[ ] Task 2.1: Create shared GrpcClientManager
[ ] Task 2.2: Refactor OAuth URL functions
[ ] Task 2.3: Consolidate test fixtures
[ ] Task 2.4: Create single source for enums
[ ] Task 2.5: Consolidate validation logic
[ ] Task 2.6: Commit Phase 2

Phase 3: Structure Cleanup
[ ] Task 3.1: Handle root Dockerfile
[ ] Task 3.2: Remove duplicate requirements.txt
[ ] Task 3.3: Document test organization
[ ] Task 3.4: Consolidate solution directories
[ ] Task 3.5: Commit Phase 3

Phase 4: Documentation Updates
[ ] Task 4.1: Fix API.md rate limiting section
[ ] Task 4.2: Add distributed API documentation
[ ] Task 4.3: Add WebSocket documentation
[ ] Task 4.4: Update ARCHITECTURE.md
[ ] Task 4.5: Fix DEPLOYMENT.md
[ ] Task 4.6: Fix NEXT_STEPS.md reference
[ ] Task 4.7: Commit Phase 4

Phase 5: New Documentation Creation
[ ] Task 5.1: Create DISTRIBUTED_CONSENSUS.md
[ ] Task 5.2: Create WEBSOCKET.md
[ ] Task 5.3: Create CONTRIBUTING.md
[ ] Task 5.4: Create AUDIT_AND_SECURITY.md
[ ] Task 5.5: Commit Phase 5

Phase 6: Code Docstrings
[ ] Task 6.1: Add docstrings to middleware
[ ] Task 6.2: Add docstrings to websocket module
[ ] Task 6.3: Add docstrings to prompts module
[ ] Task 6.4: Add docstrings to error analyzer
[ ] Task 6.5: Commit Phase 6

Phase 7: TypeScript Improvements
[ ] Task 7.1: Fix frontend API client types
[ ] Task 7.2: Fix DesignEditor component types
[ ] Task 7.3: Fix admin API client types
[ ] Task 7.4: Add type hints to Python utils
[ ] Task 7.5: Commit Phase 7

Phase 8: Tooling & Configuration
[ ] Task 8.1: Configure Python linting
[ ] Task 8.2: Configure TypeScript linting
[ ] Task 8.3: Add pre-commit hooks
[ ] Task 8.4: Fix import ordering
[ ] Task 8.5: Final commit
```

---

## Verification Commands

After completing all phases, run these verification commands:

```bash
# Python linting
black --check backend/
isort --check backend/
flake8 backend/

# TypeScript linting
cd frontend && npm run lint
cd admin && npm run lint

# Tests
pytest backend/tests/
npm test --prefix frontend

# Build verification
docker build -t test-backend backend/
docker build -t test-frontend frontend/

# Documentation check
# Verify all links in docs work
find docs/ -name "*.md" -exec grep -l "\[.*\](.*)" {} \;
```

---

## Notes for Claude

1. **Read before editing**: Always read a file before modifying it
2. **Verify changes**: After each modification, verify it works
3. **Incremental commits**: Commit after each phase, not at the end
4. **Run tests**: Run relevant tests after each phase
5. **Handle errors**: If a file doesn't exist or differs from expected, adapt accordingly
6. **Skip if done**: If a task is already complete, skip it and note in commit
