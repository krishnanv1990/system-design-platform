# URL Shortener - L5 (Senior Software Engineer) Solution

## Level Requirements

**Target Role:** Senior Software Engineer (L5)
**Focus:** Core functionality with basic scalability

### What's Expected at L5

- Working URL shortening with Base62 encoding
- Basic database schema with proper indexing
- RESTful API design
- Simple caching strategy
- Basic error handling
- Understanding of read-heavy workload patterns

---

## Database Schema

```json
{
  "tables": [
    {
      "name": "urls",
      "description": "Stores URL mappings",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "short_code", "type": "VARCHAR(10)", "constraints": "UNIQUE NOT NULL"},
        {"name": "original_url", "type": "TEXT", "constraints": "NOT NULL"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"},
        {"name": "expires_at", "type": "TIMESTAMP", "constraints": "NULL"},
        {"name": "click_count", "type": "BIGINT", "constraints": "DEFAULT 0"}
      ],
      "indexes": [
        {"name": "idx_urls_short_code", "columns": ["short_code"], "type": "BTREE"},
        {"name": "idx_urls_expires_at", "columns": ["expires_at"], "type": "BTREE"}
      ]
    },
    {
      "name": "users",
      "description": "Optional user accounts for URL management",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "email", "type": "VARCHAR(255)", "constraints": "UNIQUE NOT NULL"},
        {"name": "api_key", "type": "VARCHAR(64)", "constraints": "UNIQUE NOT NULL"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
      ],
      "indexes": [
        {"name": "idx_users_api_key", "columns": ["api_key"], "type": "BTREE"}
      ]
    }
  ]
}
```

---

## API Specification

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "URL Shortener API",
    "version": "1.0.0"
  },
  "endpoints": [
    {
      "method": "POST",
      "path": "/api/v1/urls",
      "description": "Create a shortened URL",
      "request_body": {
        "original_url": "string (required)",
        "custom_alias": "string (optional)",
        "expires_in_days": "integer (optional, default: 365)"
      },
      "responses": {
        "201": {
          "short_url": "string",
          "short_code": "string",
          "original_url": "string",
          "expires_at": "timestamp"
        },
        "400": {"error": "Invalid URL format"},
        "409": {"error": "Custom alias already exists"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}",
      "description": "Get URL info without redirecting",
      "responses": {
        "200": {
          "short_code": "string",
          "original_url": "string",
          "created_at": "timestamp",
          "expires_at": "timestamp",
          "click_count": "integer"
        },
        "404": {"error": "URL not found"},
        "410": {"error": "URL has expired"}
      }
    },
    {
      "method": "GET",
      "path": "/{short_code}",
      "description": "Redirect to original URL",
      "responses": {
        "302": "Redirect to original URL",
        "404": {"error": "URL not found"},
        "410": {"error": "URL has expired"}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/urls/{short_code}",
      "description": "Delete a shortened URL",
      "responses": {
        "204": "No content",
        "404": {"error": "URL not found"}
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check endpoint",
      "responses": {
        "200": {"status": "healthy", "timestamp": "ISO8601"}
      }
    }
  ]
}
```

---

## System Design

### Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│   Nginx     │────▶│  App Server │
│  (Browser)  │     │   (LB)      │     │  (FastAPI)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         │                     │                     │
                         ▼                     ▼                     ▼
                  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
                  │    Redis    │       │ PostgreSQL  │       │   Metrics   │
                  │   (Cache)   │       │    (DB)     │       │ (Prometheus)│
                  └─────────────┘       └─────────────┘       └─────────────┘
```

### Components

1. **Load Balancer (Nginx)**
   - Terminates SSL/TLS
   - Routes traffic to application servers
   - Basic rate limiting

2. **Application Server (FastAPI)**
   - Handles URL creation and redirection
   - Implements Base62 encoding for short codes
   - Validates input URLs
   - Manages cache interactions

3. **Database (PostgreSQL)**
   - Stores URL mappings
   - Handles persistence
   - ACID compliance for data integrity

4. **Cache (Redis)**
   - Caches hot URLs (frequently accessed)
   - TTL-based expiration
   - Read-through caching pattern

### URL Shortening Algorithm

```python
import string
import random

ALPHABET = string.ascii_letters + string.digits  # Base62

def generate_short_code(length=7):
    """Generate a random Base62 short code."""
    return ''.join(random.choices(ALPHABET, k=length))

def encode_base62(num):
    """Encode a number to Base62."""
    if num == 0:
        return ALPHABET[0]

    result = []
    while num:
        result.append(ALPHABET[num % 62])
        num //= 62
    return ''.join(reversed(result))
```

### Request Flow

**URL Creation:**
1. Client sends POST request with original URL
2. Server validates URL format
3. Server generates unique short code (Base62)
4. Server stores mapping in PostgreSQL
5. Server returns short URL to client

**URL Redirection:**
1. Client requests short URL
2. Server checks Redis cache
3. If cache miss, query PostgreSQL
4. Update cache with result
5. Increment click counter (async)
6. Return 302 redirect

### Caching Strategy

- **Cache-aside pattern**: Check cache first, fallback to DB
- **TTL**: 1 hour for cached entries
- **Write-through**: Update cache on URL creation
- **Hot URLs**: Most accessed URLs stay in cache

---

## Design Diagram (Text Description)

```
                                    URL Shortener - L5 Architecture
                                    ================================

    ┌──────────────────────────────────────────────────────────────────────────────┐
    │                                  INTERNET                                     │
    └──────────────────────────────────────┬───────────────────────────────────────┘
                                           │
                                           ▼
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │                              LOAD BALANCER                                    │
    │                          (Nginx / Cloud LB)                                   │
    │                                                                               │
    │  • SSL Termination                                                            │
    │  • Basic Rate Limiting (100 req/min per IP)                                   │
    │  • Health Checks                                                              │
    └──────────────────────────────────────┬───────────────────────────────────────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        │                  │                  │
                        ▼                  ▼                  ▼
    ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
    │     APP SERVER 1        │ │     APP SERVER 2        │ │     APP SERVER 3        │
    │      (FastAPI)          │ │      (FastAPI)          │ │      (FastAPI)          │
    │                         │ │                         │ │                         │
    │  • URL Validation       │ │  • URL Validation       │ │  • URL Validation       │
    │  • Base62 Encoding      │ │  • Base62 Encoding      │ │  • Base62 Encoding      │
    │  • Redirect Logic       │ │  • Redirect Logic       │ │  • Redirect Logic       │
    └────────────┬────────────┘ └────────────┬────────────┘ └────────────┬────────────┘
                 │                           │                           │
                 └───────────────────────────┼───────────────────────────┘
                                             │
                          ┌──────────────────┴──────────────────┐
                          │                                     │
                          ▼                                     ▼
    ┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
    │              REDIS                   │   │           POSTGRESQL                 │
    │            (Cache)                   │   │           (Primary DB)               │
    │                                      │   │                                      │
    │  • Hot URL Cache                     │   │  • urls table                        │
    │  • TTL: 1 hour                       │   │  • users table                       │
    │  • LRU Eviction                      │   │  • B-tree indexes                    │
    └─────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Create Short URL | POST valid URL to /api/v1/urls | 201 with short_url in response |
| F-02 | Create with Custom Alias | POST URL with custom_alias | 201 with specified alias |
| F-03 | Duplicate Custom Alias | POST URL with existing alias | 409 Conflict |
| F-04 | Invalid URL Format | POST malformed URL | 400 Bad Request |
| F-05 | Redirect Valid URL | GET /{short_code} | 302 Redirect to original |
| F-06 | Redirect Expired URL | GET expired short_code | 410 Gone |
| F-07 | Redirect Non-existent | GET invalid short_code | 404 Not Found |
| F-08 | Get URL Info | GET /api/v1/urls/{code} | 200 with URL details |
| F-09 | Delete URL | DELETE /api/v1/urls/{code} | 204 No Content |
| F-10 | Click Count Increment | Multiple redirects | click_count increases |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Redirect Latency | Measure redirect response time | < 50ms p99 |
| P-02 | Create Latency | Measure URL creation time | < 100ms p99 |
| P-03 | Throughput - Reads | Concurrent redirect requests | > 1000 RPS |
| P-04 | Throughput - Writes | Concurrent create requests | > 100 RPS |
| P-05 | Cache Hit Ratio | Monitor Redis hit rate | > 80% |
| P-06 | Database Connections | Monitor connection pool | < 80% utilized |

### Chaos/Reliability Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Cache Failure | Kill Redis instance | Fallback to DB, degraded performance |
| C-02 | App Server Crash | Kill one app server | LB routes to healthy servers |
| C-03 | High Load | 10x normal traffic | Graceful degradation, no crashes |
| C-04 | Slow Database | Add DB latency | Timeouts handled, errors logged |
| C-05 | Network Partition | Block DB network | Error responses, no data corruption |

---

## Capacity Estimates (L5 Level)

- **Storage**: ~500 bytes per URL × 100M URLs = 50GB
- **Read QPS**: 10,000 (100:1 read-to-write ratio)
- **Write QPS**: 100
- **Cache Size**: 10GB (20% hot URLs)
- **Bandwidth**: ~100 Mbps

---

## Key Considerations for L5

1. **Correctness over optimization**: Focus on working solution first
2. **Basic scalability**: Understand horizontal scaling concepts
3. **Simple caching**: Know when and what to cache
4. **Error handling**: Graceful degradation on failures
5. **Monitoring basics**: Health checks and basic metrics
