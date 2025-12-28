# Rate Limiter - L5 (Senior Software Engineer) Solution

## Level Requirements

**Target Role:** Senior Software Engineer (L5)
**Focus:** Core rate limiting functionality with basic algorithms

### What's Expected at L5

- Implementation of basic rate limiting algorithms
- Token Bucket or Fixed Window Counter
- Redis-based distributed counting
- Simple API integration
- Basic monitoring and logging

---

## Database Schema

```json
{
  "storage": "Redis",
  "data_structures": [
    {
      "name": "rate_limit:{client_id}",
      "type": "STRING",
      "description": "Current request count for fixed window",
      "ttl": "window_size_seconds",
      "example": {
        "key": "rate_limit:user_123",
        "value": "45",
        "ttl": 60
      }
    },
    {
      "name": "token_bucket:{client_id}",
      "type": "HASH",
      "description": "Token bucket state",
      "fields": {
        "tokens": "Current available tokens (float)",
        "last_update": "Unix timestamp of last refill"
      },
      "example": {
        "key": "token_bucket:api_key_abc",
        "tokens": "87.5",
        "last_update": "1703779200.123"
      }
    },
    {
      "name": "rate_limit_config:{tier}",
      "type": "HASH",
      "description": "Configuration per tier",
      "fields": {
        "requests_per_second": "Max RPS",
        "burst_size": "Max burst capacity",
        "window_seconds": "Window duration"
      }
    }
  ],
  "persistence": {
    "type": "PostgreSQL",
    "tables": [
      {
        "name": "rate_limit_rules",
        "columns": [
          {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
          {"name": "name", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
          {"name": "tier", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
          {"name": "requests_per_window", "type": "INTEGER", "constraints": "NOT NULL"},
          {"name": "window_seconds", "type": "INTEGER", "constraints": "NOT NULL"},
          {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
        ]
      },
      {
        "name": "rate_limit_violations",
        "columns": [
          {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
          {"name": "client_id", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
          {"name": "rule_name", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
          {"name": "violated_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"},
          {"name": "request_count", "type": "INTEGER"}
        ],
        "indexes": [
          {"columns": ["client_id", "violated_at"]}
        ]
      }
    ]
  }
}
```

---

## API Specification

```json
{
  "endpoints": [
    {
      "method": "POST",
      "path": "/api/v1/check",
      "description": "Check if request is allowed",
      "request_body": {
        "client_id": "string (required)",
        "resource": "string (optional, default: 'default')",
        "cost": "integer (optional, default: 1)"
      },
      "responses": {
        "200": {
          "allowed": true,
          "remaining": 95,
          "reset_at": "2024-01-01T00:01:00Z",
          "limit": 100
        },
        "429": {
          "allowed": false,
          "remaining": 0,
          "reset_at": "2024-01-01T00:01:00Z",
          "retry_after": 45,
          "limit": 100
        }
      },
      "headers_returned": {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "95",
        "X-RateLimit-Reset": "1703779260",
        "Retry-After": "45 (only on 429)"
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/status/{client_id}",
      "description": "Get current rate limit status",
      "responses": {
        "200": {
          "client_id": "user_123",
          "limits": [
            {
              "resource": "api",
              "limit": 100,
              "remaining": 87,
              "reset_at": "2024-01-01T00:01:00Z"
            }
          ]
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/rules",
      "description": "Create rate limit rule",
      "request_body": {
        "name": "string",
        "tier": "string",
        "requests_per_window": "integer",
        "window_seconds": "integer"
      },
      "responses": {
        "201": {"id": 1, "name": "free_tier", "created": true}
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check",
      "responses": {
        "200": {"status": "healthy", "redis": "connected"}
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                        Rate Limiter - L5 Architecture
    ════════════════════════════════════════════════════════════════

    ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
    │   Client    │────▶│    Nginx    │────▶│   Rate Limiter      │
    │  (API User) │     │  (Reverse   │     │   Service           │
    └─────────────┘     │   Proxy)    │     │   (Python/FastAPI)  │
                        └─────────────┘     └──────────┬──────────┘
                                                       │
                              ┌────────────────────────┴───────────┐
                              │                                    │
                              ▼                                    ▼
                    ┌─────────────────┐              ┌─────────────────────┐
                    │      Redis      │              │    PostgreSQL       │
                    │   (Counters)    │              │  (Config & Logs)    │
                    │                 │              │                     │
                    │ • Token counts  │              │ • Rate limit rules  │
                    │ • Window state  │              │ • Violation logs    │
                    │ • TTL-based     │              │ • Audit trail       │
                    └─────────────────┘              └─────────────────────┘
```

### Algorithm: Token Bucket

```python
import time
import redis

class TokenBucket:
    """
    Token Bucket rate limiter implementation.

    Tokens are added at a fixed rate up to a maximum (burst) capacity.
    Each request consumes one or more tokens.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_allowed(
        self,
        client_id: str,
        rate: float,  # tokens per second
        capacity: int,  # max burst size
        cost: int = 1
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed and consume tokens.

        Returns:
            (allowed: bool, info: dict with remaining, reset_at)
        """
        key = f"token_bucket:{client_id}"
        now = time.time()

        # Lua script for atomic operation
        lua_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])

        local bucket = redis.call('HGETALL', key)
        local tokens = capacity
        local last_update = now

        if #bucket > 0 then
            tokens = tonumber(bucket[2])
            last_update = tonumber(bucket[4])
        end

        -- Calculate tokens to add based on time elapsed
        local elapsed = now - last_update
        local new_tokens = elapsed * rate
        tokens = math.min(capacity, tokens + new_tokens)

        local allowed = 0
        if tokens >= cost then
            tokens = tokens - cost
            allowed = 1
        end

        -- Update bucket state
        redis.call('HSET', key, 'tokens', tokens, 'last_update', now)
        redis.call('EXPIRE', key, math.ceil(capacity / rate) + 1)

        return {allowed, tokens, capacity}
        """

        result = self.redis.eval(lua_script, 1, key, rate, capacity, now, cost)
        allowed = bool(result[0])
        remaining = int(result[1])

        return allowed, {
            "remaining": remaining,
            "limit": capacity,
            "reset_at": now + (capacity - remaining) / rate
        }
```

### Request Flow

1. Request arrives with client identifier (API key, user ID, IP)
2. Rate limiter looks up configuration for client tier
3. Token bucket state retrieved from Redis
4. Tokens refilled based on elapsed time
5. If sufficient tokens, consume and allow request
6. If insufficient tokens, reject with 429 and retry-after
7. Async: Log violations to PostgreSQL

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Allow under limit | Request when tokens available | 200 OK, allowed=true |
| F-02 | Block over limit | Request when no tokens | 429, allowed=false |
| F-03 | Token refill | Wait and retry | Tokens refilled, allowed |
| F-04 | Burst handling | Rapid burst requests | First N allowed, rest blocked |
| F-05 | Multi-client isolation | Different clients | Independent limits |
| F-06 | Custom cost | Request with cost=5 | Consumes 5 tokens |
| F-07 | Get status | Check remaining tokens | Accurate count returned |
| F-08 | Create rule | POST new rule | Rule stored in DB |
| F-09 | Headers present | Any response | Rate limit headers set |
| F-10 | Retry-After header | 429 response | Correct retry time |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Check latency | Single check operation | < 5ms p99 |
| P-02 | Throughput | Concurrent checks | > 10,000 checks/sec |
| P-03 | Redis round-trip | Lua script execution | < 1ms p99 |
| P-04 | Under load | 1000 concurrent clients | < 10ms p99 |
| P-05 | Memory usage | 1M active clients | < 500MB Redis |
| P-06 | Connection pool | Pool exhaustion test | Graceful queuing |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis failure | Kill Redis | Fail open or closed (configurable) |
| C-02 | High latency | Add 100ms Redis delay | Timeout, fail gracefully |
| C-03 | Clock skew | Adjust system time | Consistent behavior |
| C-04 | Memory pressure | Fill Redis memory | LRU eviction, no crash |
| C-05 | Network partition | Block Redis network | Retry with backoff |

---

## Capacity Estimates

- **Clients**: 100,000 active
- **Checks per second**: 10,000
- **Redis memory**: ~50MB (100K keys × 500 bytes)
- **Latency budget**: < 5ms p99
