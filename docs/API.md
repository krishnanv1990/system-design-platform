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

Currently no rate limiting is implemented. Consider adding for production:

- 100 requests per minute for authenticated users
- 10 requests per minute for unauthenticated endpoints
