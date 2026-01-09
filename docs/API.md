# API Documentation

Complete API reference for the System Design Interview Platform.

## Base URL

- Development: `http://localhost:8000/api`
- Production: `https://api.your-domain.com/api`

## Authentication

All protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

Tokens are obtained through the Google OAuth flow.

---

## Endpoints

### Authentication

#### Initiate Google OAuth

```http
GET /api/auth/google
```

Redirects the user to Google's OAuth consent page.

**Response:** `302 Redirect` to Google OAuth URL

---

#### OAuth Callback

```http
GET /api/auth/google/callback
```

Handles the OAuth callback from Google.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | string | Authorization code from Google |

**Response:** `302 Redirect` to frontend with JWT token

```
Location: http://localhost:5173/auth/callback?token=<jwt_token>
```

---

#### Get Current User

```http
GET /api/auth/me
```

Returns information about the authenticated user.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_url": "https://lh3.googleusercontent.com/...",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### Logout

```http
POST /api/auth/logout
```

Logs out the current user (client-side token removal).

**Response:** `200 OK`
```json
{
  "message": "Successfully logged out"
}
```

---

### Problems

#### List Problems

```http
GET /api/problems
```

Returns a list of all available problems.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | integer | Number of records to skip (default: 0) |
| `limit` | integer | Max records to return (default: 20, max: 100) |
| `difficulty` | string | Filter by difficulty (easy/medium/hard) |
| `tag` | string | Filter by tag |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "title": "Design a URL Shortener",
    "description": "Design a URL shortening service like TinyURL...",
    "difficulty": "medium",
    "tags": ["distributed-systems", "caching", "database"],
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

#### Get Problem

```http
GET /api/problems/{id}
```

Returns detailed information about a specific problem.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Problem ID |

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Design a URL Shortener",
  "description": "Design a URL shortening service...",
  "difficulty": "medium",
  "expected_schema": {
    "required_tables": ["urls", "users"]
  },
  "expected_api_spec": {
    "required_endpoints": ["POST /api/v1/urls", "GET /api/v1/urls/{short_code}"]
  },
  "hints": [
    "Consider using Base62 encoding for short URLs",
    "Think about how to handle collisions"
  ],
  "tags": ["distributed-systems", "caching"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "Problem not found"
}
```

---

#### Create Problem (Admin)

```http
POST /api/problems
```

Creates a new problem. Requires authentication.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Design a Rate Limiter",
  "description": "Design a rate limiting service...",
  "difficulty": "medium",
  "expected_schema": {
    "required_tables": ["rate_limits"]
  },
  "expected_api_spec": {
    "required_endpoints": ["POST /api/v1/check-rate-limit"]
  },
  "validation_rules": {
    "must_include": ["sliding window", "token bucket"]
  },
  "hints": ["Consider Redis for distributed rate limiting"],
  "tags": ["distributed-systems", "algorithms"]
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "title": "Design a Rate Limiter",
  "description": "Design a rate limiting service...",
  ...
}
```

---

#### Update Problem (Admin)

```http
PUT /api/problems/{id}
```

Updates an existing problem.

**Request Body:** (all fields optional)
```json
{
  "title": "Updated Title",
  "description": "Updated description..."
}
```

**Response:** `200 OK`

---

#### Delete Problem (Admin)

```http
DELETE /api/problems/{id}
```

Deletes a problem.

**Response:** `204 No Content`

---

### Submissions

#### Create Submission

```http
POST /api/submissions
```

Creates a new submission and starts the evaluation pipeline.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "problem_id": 1,
  "schema_input": {
    "tables": {
      "urls": {
        "columns": {
          "id": { "type": "uuid", "primary_key": true },
          "short_code": { "type": "varchar(10)", "unique": true },
          "original_url": { "type": "text" },
          "created_at": { "type": "timestamp" }
        },
        "indexes": ["short_code"]
      }
    }
  },
  "api_spec_input": {
    "endpoints": [
      {
        "method": "POST",
        "path": "/api/v1/urls",
        "description": "Create shortened URL",
        "request_body": { "original_url": "string" },
        "responses": { "201": { "short_url": "string" } }
      }
    ]
  },
  "design_text": "The URL shortener will use a distributed architecture with the following components:\n\n1. API Gateway: Handles incoming requests...\n2. URL Service: Generates short codes using Base62 encoding...\n3. Database: PostgreSQL with read replicas...\n4. Cache: Redis cluster for frequently accessed URLs..."
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "problem_id": 1,
  "user_id": 1,
  "status": "pending",
  "error_message": null,
  "created_at": "2024-01-15T10:35:00Z"
}
```

---

#### List Submissions

```http
GET /api/submissions
```

Returns the current user's submissions.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | integer | Records to skip |
| `limit` | integer | Max records |
| `problem_id` | integer | Filter by problem |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "problem_id": 1,
    "user_id": 1,
    "status": "completed",
    "error_message": null,
    "created_at": "2024-01-15T10:35:00Z"
  }
]
```

---

#### Get Submission Details

```http
GET /api/submissions/{id}
```

Returns detailed information about a submission.

**Response:** `200 OK`
```json
{
  "id": 1,
  "problem_id": 1,
  "user_id": 1,
  "schema_input": { ... },
  "api_spec_input": { ... },
  "design_text": "...",
  "generated_terraform": "resource \"google_cloud_run_service\" ...",
  "deployment_id": "submission-1-url-shortener",
  "namespace": "candidate-1-sub-1",
  "status": "completed",
  "error_message": null,
  "validation_feedback": {
    "is_valid": true,
    "score": 85,
    "errors": [],
    "warnings": ["Consider adding rate limiting"],
    "suggestions": ["Add cache invalidation strategy"],
    "feedback": {
      "scalability": { "score": 90, "comments": "Good horizontal scaling approach" },
      "reliability": { "score": 80, "comments": "Consider adding circuit breakers" },
      "data_model": { "score": 85, "comments": "Schema is well-designed" },
      "api_design": { "score": 85, "comments": "RESTful API follows best practices" },
      "overall": "Strong design with room for improvement in reliability"
    }
  },
  "created_at": "2024-01-15T10:35:00Z",
  "updated_at": "2024-01-15T10:40:00Z"
}
```

---

#### Validate Submission

```http
POST /api/submissions/validate
```

Validates a submission without creating it. Useful for getting feedback before final submission.

**Request Body:**
```json
{
  "problem_id": 1,
  "schema_input": { ... },
  "api_spec_input": { ... },
  "design_text": "..."
}
```

**Response:** `200 OK`
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": ["Consider adding indexes on foreign keys"],
  "suggestions": ["Add caching layer for better performance"],
  "score": 75
}
```

---

#### Delete Submission

```http
DELETE /api/submissions/{id}
```

Deletes a pending submission.

**Response:** `204 No Content`

**Error Response:** `400 Bad Request`
```json
{
  "detail": "Cannot delete submission that is already being processed"
}
```

---

### Tests

#### Get Submission Tests

```http
GET /api/tests/submission/{submission_id}
```

Returns all test results for a submission.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `test_type` | string | Filter by type (functional/performance/chaos) |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "submission_id": 1,
    "test_type": "functional",
    "test_name": "Create Short URL",
    "status": "passed",
    "details": {
      "stdout": "test_create_short_url PASSED",
      "spec": { "method": "POST", "path": "/api/v1/urls" }
    },
    "duration_ms": 245,
    "chaos_scenario": null,
    "created_at": "2024-01-15T10:38:00Z"
  },
  {
    "id": 2,
    "submission_id": 1,
    "test_type": "performance",
    "test_name": "Load Test - 100 Users",
    "status": "passed",
    "details": {
      "stats": {
        "requests": 5000,
        "avg_response_time": 45.2,
        "requests_per_second": 250,
        "failure_rate": 0.1
      },
      "thresholds": {
        "max_latency_ms": 500,
        "min_rps": 100
      }
    },
    "duration_ms": 60000,
    "chaos_scenario": null,
    "created_at": "2024-01-15T10:39:00Z"
  },
  {
    "id": 3,
    "submission_id": 1,
    "test_type": "chaos",
    "test_name": "Service Failure Recovery",
    "status": "passed",
    "details": {
      "experiment": { "title": "Service Failure", ... },
      "journal": { ... }
    },
    "duration_ms": 35000,
    "chaos_scenario": "service_failure",
    "created_at": "2024-01-15T10:40:00Z"
  }
]
```

---

#### Get Test Summary

```http
GET /api/tests/submission/{submission_id}/summary
```

Returns a summary of all tests for a submission.

**Response:** `200 OK`
```json
{
  "submission_id": 1,
  "total_tests": 10,
  "passed": 8,
  "failed": 1,
  "errors": 0,
  "skipped": 1,
  "functional_tests": [ ... ],
  "performance_tests": [ ... ],
  "chaos_tests": [ ... ],
  "overall_status": "partial"
}
```

---

#### Get Test Result

```http
GET /api/tests/{test_id}
```

Returns a specific test result.

**Response:** `200 OK`
```json
{
  "id": 1,
  "submission_id": 1,
  "test_type": "functional",
  "test_name": "Create Short URL",
  "status": "passed",
  "details": { ... },
  "duration_ms": 245,
  "chaos_scenario": null,
  "created_at": "2024-01-15T10:38:00Z"
}
```

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful deletion) |
| 400 | Bad Request (invalid input) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

For validation errors:
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Submission Status Values

| Status | Description |
|--------|-------------|
| `pending` | Submission received, waiting to process |
| `validating` | AI is validating the design |
| `validation_failed` | Design validation failed |
| `generating_infra` | Generating Terraform code |
| `deploying` | Deploying infrastructure to GCP |
| `deploy_failed` | Deployment failed |
| `testing` | Running tests |
| `completed` | All processing complete |
| `failed` | Processing failed |

## Test Types

| Type | Description |
|------|-------------|
| `functional` | API endpoint tests |
| `performance` | Load and latency tests |
| `chaos` | Failure scenario tests |

## Test Status Values

| Status | Description |
|--------|-------------|
| `pending` | Test not yet started |
| `running` | Test in progress |
| `passed` | Test passed |
| `failed` | Test failed |
| `error` | Test encountered error |
| `skipped` | Test was skipped |

## Rate Limiting

The API implements rate limiting to prevent abuse. Limits are configured per endpoint type:

| Endpoint Type | Authenticated | Unauthenticated |
|--------------|---------------|-----------------|
| Submissions | 5/hour | 2/hour |
| Validation | 20/hour | 10/hour |
| General API | 100/minute | 20/minute |

### Rate Limit Headers

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### Rate Limit Exceeded Response

When rate limited, the API returns `429 Too Many Requests`:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 3600
}
```

### Configuration

Rate limiting is configured via environment variables:
- `RATE_LIMIT_ENABLED`: Enable/disable rate limiting (default: `true`)
- `RATE_LIMIT_SUBMISSIONS_PER_HOUR`: Submission limit (default: `5`)
- `RATE_LIMIT_VALIDATE_PER_HOUR`: Validation limit (default: `20`)
- `REDIS_URL`: Redis URL for distributed rate limiting (optional)

---

## Distributed Consensus API

The distributed consensus API provides endpoints for solving distributed systems problems with real code execution.

### List Distributed Problems

```http
GET /api/distributed/problems
```

Returns all available distributed consensus problems.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "title": "Implement Raft Consensus",
    "description": "Implement the Raft consensus algorithm...",
    "difficulty": "hard",
    "problem_type": "distributed_consensus",
    "supported_languages": ["python", "go", "java", "cpp", "rust"],
    "cluster_size": 3,
    "tags": ["distributed-systems", "consensus", "raft"],
    "created_at": "2025-01-01T00:00:00Z"
  }
]
```

---

### Get Distributed Problem

```http
GET /api/distributed/problems/{problem_id}
```

Returns detailed information about a distributed problem including test cases and starter code.

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Implement Raft Consensus",
  "description": "Implement the Raft consensus algorithm...",
  "difficulty": "hard",
  "problem_type": "distributed_consensus",
  "supported_languages": ["python", "go", "java", "cpp", "rust"],
  "cluster_size": 3,
  "test_cases": [
    {
      "name": "Leader Election",
      "description": "Test leader election when cluster starts"
    }
  ],
  "starter_code": {
    "python": "# Python starter code...",
    "go": "// Go starter code..."
  },
  "proto_definition": "syntax = \"proto3\";...",
  "tags": ["distributed-systems", "consensus", "raft"],
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### Get Code Template

```http
GET /api/distributed/problems/{problem_id}/template/{language}
```

Returns the starter code template for a specific language.

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `problem_id` | integer | Problem ID |
| `language` | string | Programming language (python/go/java/cpp/rust) |

**Response:** `200 OK`
```json
{
  "language": "python",
  "template": "import grpc\n..."
}
```

---

### Get Saved Code

```http
GET /api/distributed/problems/{problem_id}/saved-code/{language}
```

Returns the user's saved code for a problem.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** `200 OK`
```json
{
  "language": "python",
  "source_code": "# User's saved code...",
  "saved_at": "2024-01-15T10:30:00Z"
}
```

---

### Save Code

```http
POST /api/distributed/problems/{problem_id}/save-code
```

Saves the user's code progress for a problem.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "language": "python",
  "source_code": "# User's code..."
}
```

**Response:** `200 OK`
```json
{
  "message": "Code saved successfully"
}
```

---

### Create Distributed Submission

```http
POST /api/distributed/submissions
```

Submits code for compilation and testing against a distributed cluster.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "problem_id": 1,
  "language": "python",
  "source_code": "import grpc\n..."
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "problem_id": 1,
  "user_id": 1,
  "submission_type": "distributed_consensus",
  "language": "python",
  "source_code": "...",
  "status": "building",
  "build_logs": "Queuing build job...\n",
  "build_artifact_url": null,
  "cluster_node_urls": null,
  "error_message": null,
  "created_at": "2024-01-15T10:35:00Z"
}
```

---

### List Distributed Submissions

```http
GET /api/distributed/submissions
```

Returns the current user's distributed submissions.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `problem_id` | integer | Filter by problem (optional) |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "problem_id": 1,
    "user_id": 1,
    "submission_type": "distributed_consensus",
    "language": "python",
    "status": "completed",
    "build_logs": "...",
    "cluster_node_urls": ["https://node-0.run.app", "https://node-1.run.app"],
    "error_message": null,
    "created_at": "2024-01-15T10:35:00Z"
  }
]
```

---

### Get Distributed Submission

```http
GET /api/distributed/submissions/{submission_id}
```

Returns details of a specific distributed submission.

**Response:** `200 OK`
```json
{
  "id": 1,
  "problem_id": 1,
  "user_id": 1,
  "submission_type": "distributed_consensus",
  "language": "python",
  "source_code": "...",
  "status": "testing",
  "build_logs": "Build successful...",
  "build_artifact_url": "gs://bucket/artifact.tar.gz",
  "cluster_node_urls": ["https://node-0.run.app", "https://node-1.run.app", "https://node-2.run.app"],
  "error_message": null,
  "created_at": "2024-01-15T10:35:00Z"
}
```

---

### Get Build Logs

```http
GET /api/distributed/submissions/{submission_id}/build-logs
```

Returns the build logs for a submission.

**Response:** `200 OK`
```json
{
  "logs": "Step 1/5: Compiling code...\nStep 2/5: Running unit tests...\n..."
}
```

---

### Get Submission Tests

```http
GET /api/distributed/submissions/{submission_id}/tests
```

Returns the test results for a distributed submission.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "submission_id": 1,
    "test_type": "functional",
    "test_name": "Leader Election",
    "status": "passed",
    "details": { "stdout": "Leader elected successfully" },
    "duration_ms": 1250,
    "chaos_scenario": null,
    "created_at": "2024-01-15T10:40:00Z"
  }
]
```

---

### Teardown Cluster

```http
POST /api/distributed/submissions/{submission_id}/teardown
```

Tears down the deployed cluster for a submission.

**Response:** `200 OK`
```json
{
  "message": "Cluster teardown initiated"
}
```

---

## Distributed Submission Status Values

| Status | Description |
|--------|-------------|
| `building` | Code is being compiled |
| `build_failed` | Compilation failed |
| `deploying` | Cluster is being deployed |
| `deploy_failed` | Deployment failed |
| `testing` | Running distributed tests |
| `completed` | All tests complete |
| `failed` | Submission failed |

---

## WebSocket API

The platform supports real-time updates via WebSocket connections.

### Submission Updates

```
WS /ws/submissions/{submission_id}?token=<jwt_token>
```

Connect to receive live updates for a specific submission.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `token` | string | JWT auth token (required unless demo mode) |

**Connection:**
```javascript
const ws = new WebSocket('wss://api.example.com/ws/submissions/123?token=xxx');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message);
};
```

**Server Messages:**

Status Update:
```json
{
  "type": "status_update",
  "submission_id": 123,
  "status": "testing",
  "timestamp": "2024-01-15T10:38:00Z"
}
```

Test Result:
```json
{
  "type": "test_result",
  "submission_id": 123,
  "test_name": "Leader Election",
  "status": "passed",
  "duration_ms": 1250,
  "timestamp": "2024-01-15T10:40:00Z"
}
```

Error Analysis:
```json
{
  "type": "error_analysis",
  "submission_id": 123,
  "error": "Connection refused",
  "analysis": "The node failed to connect...",
  "suggestions": ["Check network configuration"],
  "timestamp": "2024-01-15T10:41:00Z"
}
```

**Keepalive:**
- Server sends `ping` every 5 minutes
- Client should respond with `pong`
- Connection closes if client doesn't respond

**Close Codes:**
| Code | Reason |
|------|--------|
| 4003 | Unauthorized - Invalid or missing token |
| 1000 | Normal closure |
