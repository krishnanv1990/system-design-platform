# Rate Limiter System Design

## Problem Overview

Design a distributed rate limiting service that controls API traffic with low latency and high accuracy across multiple servers.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution Architecture

### High-Level Design

```
                     ┌─────────────────────────────────────────────┐
                     │              API Gateway Layer              │
                     │  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
                     │  │  Kong   │ │  Kong   │ │  Kong   │       │
                     │  │ + Rate  │ │ + Rate  │ │ + Rate  │       │
                     │  │ Limiter │ │ Limiter │ │ Limiter │       │
                     │  └────┬────┘ └────┬────┘ └────┬────┘       │
                     └───────┼───────────┼───────────┼────────────┘
                             │           │           │
                             ▼           ▼           ▼
                     ┌─────────────────────────────────────────────┐
                     │           Redis Cluster (6 nodes)           │
                     │  ┌─────────────────────────────────────┐   │
                     │  │  Slot 0-5460  │ Slot 5461-10922    │   │
                     │  │    Master     │     Master          │   │
                     │  │    Replica    │     Replica         │   │
                     │  ├──────────────┼─────────────────────┤   │
                     │  │ Slot 10923-16383                    │   │
                     │  │     Master    │     Replica         │   │
                     │  └─────────────────────────────────────┘   │
                     └─────────────────────────────────────────────┘
                                          │
                                          ▼
                     ┌─────────────────────────────────────────────┐
                     │         Rate Limit Configuration DB         │
                     │              (PostgreSQL)                   │
                     │  ┌─────────────────────────────────────┐   │
                     │  │ rate_limits, api_keys, usage_logs   │   │
                     │  └─────────────────────────────────────┘   │
                     └─────────────────────────────────────────────┘
```

### Rate Limiting Algorithms

#### 1. Token Bucket (Recommended for API Rate Limiting)

```python
import time
import redis

class TokenBucket:
    """
    Token Bucket Algorithm
    - Tokens added at fixed rate
    - Burst capacity allowed
    - Smooth rate limiting
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_allowed(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,  # tokens per second
        tokens_requested: int = 1
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed and consume tokens.

        Returns: (allowed, metadata)
        """
        now = time.time()
        bucket_key = f"token_bucket:{key}"

        # Lua script for atomic operation
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or now

        -- Refill tokens based on elapsed time
        local elapsed = now - last_refill
        local refill = elapsed * refill_rate
        tokens = math.min(max_tokens, tokens + refill)

        local allowed = 0
        if tokens >= requested then
            tokens = tokens - requested
            allowed = 1
        end

        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)

        return {allowed, tokens, max_tokens - tokens}
        """

        result = self.redis.eval(
            lua_script,
            1,
            bucket_key,
            max_tokens,
            refill_rate,
            now,
            tokens_requested
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after = (tokens_requested - remaining) / refill_rate if not allowed else 0

        return allowed, {
            "remaining": remaining,
            "limit": max_tokens,
            "retry_after": retry_after
        }
```

#### 2. Sliding Window Counter (Best Accuracy)

```python
class SlidingWindowCounter:
    """
    Sliding Window Counter Algorithm
    - More accurate than fixed window
    - Memory efficient
    - Weighted average of current and previous window
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, dict]:
        now = time.time()
        current_window = int(now // window_seconds)
        previous_window = current_window - 1
        window_position = (now % window_seconds) / window_seconds

        lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local current_window = ARGV[2]
        local previous_window = ARGV[3]
        local window_position = tonumber(ARGV[4])

        local current_key = key .. ':' .. current_window
        local previous_key = key .. ':' .. previous_window

        local current_count = tonumber(redis.call('GET', current_key)) or 0
        local previous_count = tonumber(redis.call('GET', previous_key)) or 0

        -- Weighted count: previous * (1 - position) + current
        local weighted_count = previous_count * (1 - window_position) + current_count

        if weighted_count >= limit then
            return {0, weighted_count, limit}
        end

        redis.call('INCR', current_key)
        redis.call('EXPIRE', current_key, ARGV[5])

        return {1, weighted_count + 1, limit}
        """

        result = self.redis.eval(
            lua_script,
            1,
            f"sliding_window:{key}",
            limit,
            current_window,
            previous_window,
            window_position,
            window_seconds * 2
        )

        return bool(result[0]), {
            "current_count": int(result[1]),
            "limit": int(result[2]),
            "window_seconds": window_seconds
        }
```

#### 3. Sliding Window Log (Most Accurate, Memory Intensive)

```python
class SlidingWindowLog:
    """
    Sliding Window Log Algorithm
    - Stores timestamp of each request
    - Most accurate
    - Higher memory usage
    """

    def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - window_seconds
        log_key = f"sliding_log:{key}"

        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])

        -- Remove old entries
        redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

        -- Count current requests
        local count = redis.call('ZCARD', key)

        if count >= limit then
            -- Get oldest timestamp for retry-after calculation
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local retry_after = 0
            if oldest[2] then
                retry_after = oldest[2] + window_seconds - now
            end
            return {0, count, retry_after}
        end

        -- Add current request
        redis.call('ZADD', key, now, now .. ':' .. math.random())
        redis.call('EXPIRE', key, window_seconds)

        return {1, count + 1, 0}
        """

        result = self.redis.eval(
            lua_script,
            1,
            log_key,
            now,
            window_start,
            limit,
            window_seconds
        )

        return bool(result[0]), {
            "count": int(result[1]),
            "limit": limit,
            "retry_after": float(result[2])
        }
```

### Database Schema

```sql
-- Rate limit configurations
CREATE TABLE rate_limit_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    algorithm VARCHAR(50) NOT NULL,  -- token_bucket, sliding_window, fixed_window
    limit_value INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    burst_size INTEGER,  -- For token bucket
    refill_rate FLOAT,   -- For token bucket
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- API keys with rate limits
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100),
    tier VARCHAR(50) DEFAULT 'free',  -- free, pro, enterprise
    rate_limit_config_id INTEGER REFERENCES rate_limit_configs(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Rate limit tiers
CREATE TABLE rate_limit_tiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    requests_per_minute INTEGER,
    requests_per_hour INTEGER,
    requests_per_day INTEGER,
    burst_size INTEGER,
    cost_per_request DECIMAL(10, 6)
);

-- Usage logs (partitioned by day for analytics)
CREATE TABLE rate_limit_logs (
    id BIGSERIAL,
    api_key_id INTEGER,
    endpoint VARCHAR(200),
    allowed BOOLEAN,
    remaining INTEGER,
    timestamp TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (timestamp);
```

### API Endpoints

```yaml
openapi: 3.0.0
paths:
  /api/v1/check:
    post:
      summary: Check and consume rate limit
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [key, endpoint]
              properties:
                key: { type: string }
                endpoint: { type: string }
                cost: { type: integer, default: 1 }
      responses:
        200:
          headers:
            X-RateLimit-Limit: { schema: { type: integer } }
            X-RateLimit-Remaining: { schema: { type: integer } }
            X-RateLimit-Reset: { schema: { type: integer } }
          content:
            application/json:
              schema:
                type: object
                properties:
                  allowed: { type: boolean }
                  remaining: { type: integer }
                  retry_after: { type: number }

  /api/v1/status:
    get:
      summary: Get current rate limit status
      parameters:
        - name: key
          in: query
          required: true
          schema: { type: string }
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  limit: { type: integer }
                  remaining: { type: integer }
                  reset_at: { type: string, format: date-time }
```

---

## Platform Deployment

### Deployment Architecture

1. **Rate Limiter Service**
   - Deployed as Cloud Run service
   - Auto-scales based on request volume
   - Stateless (all state in Redis)

2. **Redis Cluster**
   - Memorystore for Redis (HA mode)
   - 3 primary + 3 replica configuration
   - Cross-zone replication

3. **Configuration Database**
   - Cloud SQL PostgreSQL
   - Stores tier configurations
   - Read replicas for config queries

### Deployment Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Submission  │────▶│ AI Validates │────▶│ Generate Infra  │
│   Design    │     │  Algorithm   │     │    Terraform    │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────────────────────┘
                    │
                    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Cloud Build │────▶│ Deploy Redis │────▶│  Deploy Rate    │
│   Image     │     │   Cluster    │     │  Limiter API    │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                    ┌──────────────────────────────┘
                    │
                    ▼
              ┌─────────────────┐
              │   Run Tests     │
              └─────────────────┘
```

---

## Realistic Testing

### 1. Functional Tests

```python
import pytest
import asyncio
import aiohttp

class TestRateLimiter:
    """Functional tests for rate limiter."""

    async def test_basic_rate_limiting(self, client):
        """Test that rate limiting kicks in after limit exceeded."""
        key = f"test-{uuid.uuid4()}"
        limit = 10

        # Make requests up to the limit
        for i in range(limit):
            response = await client.post("/api/v1/check", json={
                "key": key,
                "endpoint": "/api/test"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["allowed"] == True
            assert data["remaining"] == limit - i - 1

        # Next request should be rejected
        response = await client.post("/api/v1/check", json={
            "key": key,
            "endpoint": "/api/test"
        })
        assert response.json()["allowed"] == False
        assert response.json()["retry_after"] > 0

    async def test_window_reset(self, client):
        """Test that limits reset after window expires."""
        key = f"test-{uuid.uuid4()}"
        window_seconds = 2

        # Exhaust the limit
        for _ in range(10):
            await client.post("/api/v1/check", json={
                "key": key,
                "endpoint": "/api/test"
            })

        # Verify blocked
        response = await client.post("/api/v1/check", json={
            "key": key,
            "endpoint": "/api/test"
        })
        assert response.json()["allowed"] == False

        # Wait for window reset
        await asyncio.sleep(window_seconds + 0.5)

        # Should be allowed again
        response = await client.post("/api/v1/check", json={
            "key": key,
            "endpoint": "/api/test"
        })
        assert response.json()["allowed"] == True

    async def test_different_keys_independent(self, client):
        """Test that different keys have independent limits."""
        key1 = f"user1-{uuid.uuid4()}"
        key2 = f"user2-{uuid.uuid4()}"

        # Exhaust key1
        for _ in range(10):
            await client.post("/api/v1/check", json={
                "key": key1, "endpoint": "/api/test"
            })

        # key2 should still work
        response = await client.post("/api/v1/check", json={
            "key": key2, "endpoint": "/api/test"
        })
        assert response.json()["allowed"] == True

    async def test_burst_handling(self, client):
        """Test token bucket burst capacity."""
        key = f"burst-{uuid.uuid4()}"
        burst_size = 20

        # Rapid burst should be allowed
        tasks = [
            client.post("/api/v1/check", json={
                "key": key, "endpoint": "/api/test"
            })
            for _ in range(burst_size)
        ]
        responses = await asyncio.gather(*tasks)

        allowed_count = sum(1 for r in responses if r.json()["allowed"])
        assert allowed_count == burst_size
```

### 2. Performance Testing

Deploy Locust for load testing in the same GCP project:

```python
# locustfile.py
from locust import HttpUser, task, between, constant_throughput
import uuid

class RateLimiterUser(HttpUser):
    wait_time = constant_throughput(100)  # 100 RPS per user

    def on_start(self):
        self.api_key = f"perf-test-{uuid.uuid4()}"

    @task(10)
    def check_rate_limit(self):
        """Simulate rate limit checks."""
        self.client.post("/api/v1/check", json={
            "key": self.api_key,
            "endpoint": "/api/resource"
        }, name="/api/v1/check")

    @task(1)
    def get_status(self):
        """Check rate limit status."""
        self.client.get(
            f"/api/v1/status?key={self.api_key}",
            name="/api/v1/status"
        )


# Run with:
# locust -f locustfile.py --host=https://rate-limiter.run.app \
#        --users 100 --spawn-rate 10 --run-time 5m
```

**Performance Targets:**
| Metric | Target |
|--------|--------|
| Latency (p50) | < 5ms |
| Latency (p99) | < 20ms |
| Throughput | > 50,000 RPS |
| Accuracy | > 99.9% |

### 3. Distributed Consistency Tests

```python
class TestDistributedConsistency:
    """Test rate limiter accuracy across distributed nodes."""

    async def test_distributed_accuracy(self):
        """
        Verify that distributed rate limiting is accurate.
        Multiple clients hitting different nodes should still
        respect the global limit.
        """
        key = f"distributed-test-{uuid.uuid4()}"
        limit = 100
        num_clients = 10
        requests_per_client = 20  # Total 200 requests, limit is 100

        async def make_requests(session, node_url):
            allowed = 0
            for _ in range(requests_per_client):
                async with session.post(
                    f"{node_url}/api/v1/check",
                    json={"key": key, "endpoint": "/test"}
                ) as resp:
                    data = await resp.json()
                    if data["allowed"]:
                        allowed += 1
            return allowed

        # Hit different load balancer endpoints
        node_urls = [
            "https://rate-limiter-node1.run.app",
            "https://rate-limiter-node2.run.app",
            "https://rate-limiter-node3.run.app",
        ]

        async with aiohttp.ClientSession() as session:
            tasks = [
                make_requests(session, node_urls[i % len(node_urls)])
                for i in range(num_clients)
            ]
            results = await asyncio.gather(*tasks)

        total_allowed = sum(results)

        # Should be very close to the limit (allowing for race conditions)
        assert limit - 5 <= total_allowed <= limit + 5

    async def test_redis_cluster_failover(self):
        """Test behavior during Redis node failover."""
        key = f"failover-test-{uuid.uuid4()}"

        # Start making requests
        allowed_before = 0
        for _ in range(50):
            response = await client.post("/api/v1/check", json={
                "key": key, "endpoint": "/test"
            })
            if response.json()["allowed"]:
                allowed_before += 1

        # Trigger Redis failover (platform API)
        await platform_api.trigger_redis_failover()

        # Continue making requests during failover
        errors = 0
        allowed_during = 0
        for _ in range(100):
            try:
                response = await client.post("/api/v1/check", json={
                    "key": key, "endpoint": "/test"
                })
                if response.json()["allowed"]:
                    allowed_during += 1
            except:
                errors += 1
            await asyncio.sleep(0.1)

        # Should have minimal errors and maintain rough accuracy
        assert errors < 10  # Less than 10% errors during failover
        print(f"Allowed before: {allowed_before}, during: {allowed_during}, errors: {errors}")
```

### 4. Chaos Testing

```python
class ChaosTests:
    """Chaos engineering tests for rate limiter resilience."""

    async def test_redis_latency_spike(self):
        """Inject latency into Redis connections."""
        # Platform injects network latency
        await platform_api.inject_latency(
            service="redis",
            latency_ms=100,
            jitter_ms=50,
            duration_seconds=60
        )

        # Measure response times
        latencies = []
        for _ in range(100):
            start = time.time()
            await client.post("/api/v1/check", json={
                "key": "latency-test",
                "endpoint": "/test"
            })
            latencies.append(time.time() - start)

        # Should gracefully handle latency
        p99 = sorted(latencies)[98]
        assert p99 < 0.5  # Less than 500ms even with Redis latency

    async def test_redis_partition(self):
        """Simulate network partition to Redis cluster."""
        key = f"partition-test-{uuid.uuid4()}"

        # Make some successful requests
        for _ in range(10):
            await client.post("/api/v1/check", json={
                "key": key, "endpoint": "/test"
            })

        # Partition Redis (platform API)
        await platform_api.create_network_partition(
            source="rate-limiter",
            target="redis",
            duration_seconds=30
        )

        # Should fail gracefully (fail open or use local cache)
        responses = []
        for _ in range(10):
            try:
                resp = await client.post("/api/v1/check", json={
                    "key": key, "endpoint": "/test"
                })
                responses.append(resp.json())
            except Exception as e:
                responses.append({"error": str(e)})

        # Verify graceful degradation
        # Either fails open or returns cached result
        for r in responses:
            assert "error" not in r or "allowed" in r
```

### 5. Manual Testing Commands

```bash
# 1. Test basic rate limiting
for i in {1..15}; do
  curl -X POST https://rate-limiter.run.app/api/v1/check \
    -H "Content-Type: application/json" \
    -d '{"key": "test-key", "endpoint": "/api/test"}' | jq .
  sleep 0.1
done

# 2. Check headers
curl -i -X POST https://rate-limiter.run.app/api/v1/check \
  -H "Content-Type: application/json" \
  -d '{"key": "header-test", "endpoint": "/api/test"}'

# 3. Concurrent requests test
seq 1 100 | xargs -P 50 -I {} curl -s -X POST \
  https://rate-limiter.run.app/api/v1/check \
  -H "Content-Type: application/json" \
  -d '{"key": "concurrent-test", "endpoint": "/api/test"}' | grep -c '"allowed": true'

# 4. Monitor Redis metrics
gcloud redis instances describe rate-limiter-cache \
  --region=us-central1 --format="json" | jq '.memorySizeGb, .currentLocationId'
```

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| Latency (p50) | < 5ms | Performance test |
| Latency (p99) | < 20ms | Performance test |
| Accuracy | > 99.9% | Distributed test |
| Throughput | > 50K RPS | Load test |
| Availability | 99.99% | Chaos tests |
| Failover Time | < 30s | Chaos tests |

---

## Common Pitfalls

1. **Race conditions:** Not using atomic Redis operations
2. **Clock skew:** Issues with timestamp-based algorithms across servers
3. **Memory leaks:** Not expiring old keys in sliding window log
4. **Fail closed:** Blocking all requests when Redis is down
5. **Single Redis:** No replication or clustering
6. **Missing headers:** Not returning rate limit headers in responses
