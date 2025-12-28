# URL Shortener - L6 (Staff Engineer) Solution

## Level Requirements

**Target Role:** Staff Engineer (L6)
**Focus:** Production-ready design with high availability

### What's Expected at L6

- Everything from L5, plus:
- Key Generation Service (KGS) for unique, non-predictable codes
- Multi-region deployment strategy
- Comprehensive caching with Redis Cluster
- Analytics pipeline for click tracking
- Rate limiting and abuse prevention
- Detailed capacity planning
- Disaster recovery strategy
- Monitoring and alerting

---

## Database Schema

```json
{
  "tables": [
    {
      "name": "urls",
      "description": "Stores URL mappings with analytics",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "short_code", "type": "VARCHAR(10)", "constraints": "UNIQUE NOT NULL"},
        {"name": "original_url", "type": "TEXT", "constraints": "NOT NULL"},
        {"name": "user_id", "type": "BIGINT", "constraints": "REFERENCES users(id)"},
        {"name": "created_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "DEFAULT NOW()"},
        {"name": "expires_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "NULL"},
        {"name": "click_count", "type": "BIGINT", "constraints": "DEFAULT 0"},
        {"name": "last_accessed_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "NULL"},
        {"name": "is_active", "type": "BOOLEAN", "constraints": "DEFAULT TRUE"},
        {"name": "metadata", "type": "JSONB", "constraints": "DEFAULT '{}'"}
      ],
      "indexes": [
        {"name": "idx_urls_short_code", "columns": ["short_code"], "type": "HASH", "note": "Hash for O(1) lookups"},
        {"name": "idx_urls_user_id", "columns": ["user_id"], "type": "BTREE"},
        {"name": "idx_urls_expires_at", "columns": ["expires_at"], "type": "BTREE", "where": "expires_at IS NOT NULL"},
        {"name": "idx_urls_created_at", "columns": ["created_at"], "type": "BTREE"}
      ],
      "partitioning": {
        "type": "RANGE",
        "column": "created_at",
        "interval": "MONTHLY"
      }
    },
    {
      "name": "users",
      "description": "User accounts with rate limits",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "email", "type": "VARCHAR(255)", "constraints": "UNIQUE NOT NULL"},
        {"name": "api_key", "type": "VARCHAR(64)", "constraints": "UNIQUE NOT NULL"},
        {"name": "tier", "type": "VARCHAR(20)", "constraints": "DEFAULT 'free'"},
        {"name": "rate_limit", "type": "INTEGER", "constraints": "DEFAULT 100"},
        {"name": "urls_created", "type": "BIGINT", "constraints": "DEFAULT 0"},
        {"name": "created_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "DEFAULT NOW()"},
        {"name": "last_active_at", "type": "TIMESTAMP WITH TIME ZONE"}
      ],
      "indexes": [
        {"name": "idx_users_api_key", "columns": ["api_key"], "type": "HASH"},
        {"name": "idx_users_email", "columns": ["email"], "type": "BTREE"}
      ]
    },
    {
      "name": "kgs_keys",
      "description": "Pre-generated keys from Key Generation Service",
      "columns": [
        {"name": "short_code", "type": "VARCHAR(10)", "constraints": "PRIMARY KEY"},
        {"name": "is_used", "type": "BOOLEAN", "constraints": "DEFAULT FALSE"},
        {"name": "used_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "NULL"},
        {"name": "batch_id", "type": "INTEGER", "constraints": "NOT NULL"}
      ],
      "indexes": [
        {"name": "idx_kgs_unused", "columns": ["is_used"], "type": "BTREE", "where": "is_used = FALSE"}
      ]
    },
    {
      "name": "click_events",
      "description": "Analytics events for click tracking",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "short_code", "type": "VARCHAR(10)", "constraints": "NOT NULL"},
        {"name": "clicked_at", "type": "TIMESTAMP WITH TIME ZONE", "constraints": "DEFAULT NOW()"},
        {"name": "referrer", "type": "TEXT"},
        {"name": "user_agent", "type": "TEXT"},
        {"name": "ip_hash", "type": "VARCHAR(64)", "constraints": "NOT NULL"},
        {"name": "country", "type": "VARCHAR(2)"},
        {"name": "city", "type": "VARCHAR(100)"}
      ],
      "indexes": [
        {"name": "idx_clicks_short_code", "columns": ["short_code", "clicked_at"], "type": "BTREE"}
      ],
      "partitioning": {
        "type": "RANGE",
        "column": "clicked_at",
        "interval": "DAILY"
      }
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
    "title": "URL Shortener API - Production",
    "version": "2.0.0"
  },
  "security": [
    {"ApiKeyAuth": []},
    {"BearerAuth": []}
  ],
  "endpoints": [
    {
      "method": "POST",
      "path": "/api/v1/urls",
      "description": "Create a shortened URL",
      "headers": {
        "X-API-Key": "string (required for authenticated requests)",
        "X-Idempotency-Key": "string (optional, for retry safety)"
      },
      "request_body": {
        "original_url": "string (required)",
        "custom_alias": "string (optional, 4-10 chars)",
        "expires_in_days": "integer (optional, 1-3650)",
        "metadata": {
          "campaign": "string (optional)",
          "source": "string (optional)"
        }
      },
      "responses": {
        "201": {
          "short_url": "string",
          "short_code": "string",
          "original_url": "string",
          "expires_at": "timestamp",
          "qr_code_url": "string"
        },
        "400": {"error": "string", "code": "INVALID_URL | INVALID_ALIAS"},
        "409": {"error": "string", "code": "ALIAS_EXISTS"},
        "429": {"error": "string", "code": "RATE_LIMIT_EXCEEDED", "retry_after": "integer"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}",
      "description": "Get URL info and analytics",
      "responses": {
        "200": {
          "short_code": "string",
          "original_url": "string",
          "created_at": "timestamp",
          "expires_at": "timestamp",
          "click_count": "integer",
          "last_accessed_at": "timestamp",
          "analytics": {
            "clicks_24h": "integer",
            "clicks_7d": "integer",
            "top_countries": ["array"],
            "top_referrers": ["array"]
          }
        },
        "404": {"error": "URL not found"},
        "410": {"error": "URL has expired"}
      }
    },
    {
      "method": "GET",
      "path": "/{short_code}",
      "description": "Redirect to original URL (public endpoint)",
      "responses": {
        "301": "Permanent redirect (for SEO-friendly URLs)",
        "302": "Temporary redirect (default)",
        "404": {"error": "URL not found"},
        "410": {"error": "URL has expired"}
      }
    },
    {
      "method": "PATCH",
      "path": "/api/v1/urls/{short_code}",
      "description": "Update URL properties",
      "request_body": {
        "original_url": "string (optional)",
        "expires_at": "timestamp (optional)",
        "is_active": "boolean (optional)"
      },
      "responses": {
        "200": {"message": "URL updated", "url": "object"},
        "404": {"error": "URL not found"},
        "403": {"error": "Not authorized"}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/urls/{short_code}",
      "description": "Delete a shortened URL",
      "responses": {
        "204": "No content",
        "404": {"error": "URL not found"},
        "403": {"error": "Not authorized"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}/stats",
      "description": "Get detailed click statistics",
      "query_params": {
        "start_date": "ISO8601 date",
        "end_date": "ISO8601 date",
        "granularity": "hour | day | week"
      },
      "responses": {
        "200": {
          "total_clicks": "integer",
          "unique_visitors": "integer",
          "time_series": [{"timestamp": "string", "clicks": "integer"}],
          "geographic": [{"country": "string", "clicks": "integer"}],
          "referrers": [{"source": "string", "clicks": "integer"}],
          "devices": {"mobile": "integer", "desktop": "integer", "tablet": "integer"}
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/urls/bulk",
      "description": "Create multiple shortened URLs",
      "request_body": {
        "urls": [{"original_url": "string", "custom_alias": "string (optional)"}]
      },
      "responses": {
        "201": {"results": [{"original_url": "string", "short_url": "string", "status": "string"}]},
        "207": "Multi-status (partial success)"
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check with component status",
      "responses": {
        "200": {
          "status": "healthy",
          "components": {
            "database": "healthy",
            "cache": "healthy",
            "kgs": "healthy"
          },
          "version": "string"
        },
        "503": {"status": "unhealthy", "components": "object"}
      }
    }
  ],
  "rate_limits": {
    "anonymous": "10 requests/minute",
    "free_tier": "100 requests/minute",
    "pro_tier": "1000 requests/minute",
    "enterprise": "10000 requests/minute"
  }
}
```

---

## System Design

### Architecture Overview

```
                              URL Shortener - L6 Production Architecture
    ┌─────────────────────────────────────────────────────────────────────────────────────┐
    │                                      CDN                                             │
    │                            (CloudFlare / CloudFront)                                 │
    │                        • Static assets & QR codes                                    │
    │                        • DDoS protection                                             │
    │                        • Edge caching for popular URLs                               │
    └─────────────────────────────────────────┬───────────────────────────────────────────┘
                                              │
    ┌─────────────────────────────────────────┴───────────────────────────────────────────┐
    │                              GLOBAL LOAD BALANCER                                    │
    │                            (Cloud Load Balancer)                                     │
    │                        • SSL termination                                             │
    │                        • Geographic routing                                          │
    │                        • Health checks                                               │
    └─────────────────────────────────────────┬───────────────────────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
    ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
    │    REGION: US-EAST    │   │   REGION: US-WEST     │   │   REGION: EU-WEST     │
    │                       │   │                       │   │                       │
    │  ┌─────────────────┐  │   │  ┌─────────────────┐  │   │  ┌─────────────────┐  │
    │  │   API Gateway   │  │   │  │   API Gateway   │  │   │  │   API Gateway   │  │
    │  │  (Rate Limiting)│  │   │  │  (Rate Limiting)│  │   │  │  (Rate Limiting)│  │
    │  └────────┬────────┘  │   │  └────────┬────────┘  │   │  └────────┬────────┘  │
    │           │           │   │           │           │   │           │           │
    │  ┌────────┴────────┐  │   │  ┌────────┴────────┐  │   │  ┌────────┴────────┐  │
    │  │  App Servers    │  │   │  │  App Servers    │  │   │  │  App Servers    │  │
    │  │  (Auto-scaled)  │  │   │  │  (Auto-scaled)  │  │   │  │  (Auto-scaled)  │  │
    │  │  min: 3, max: 50│  │   │  │  min: 3, max: 50│  │   │  │  min: 2, max: 30│  │
    │  └────────┬────────┘  │   │  └────────┬────────┘  │   │  └────────┬────────┘  │
    │           │           │   │           │           │   │           │           │
    │  ┌────────┴────────┐  │   │  ┌────────┴────────┐  │   │  ┌────────┴────────┐  │
    │  │  Redis Cluster  │  │   │  │  Redis Cluster  │  │   │  │  Redis Cluster  │  │
    │  │  (6 nodes)      │  │   │  │  (6 nodes)      │  │   │  │  (6 nodes)      │  │
    │  └─────────────────┘  │   │  └─────────────────┘  │   │  └─────────────────┘  │
    │                       │   │                       │   │                       │
    └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
                │                           │                           │
                └───────────────────────────┼───────────────────────────┘
                                            │
    ┌───────────────────────────────────────┴───────────────────────────────────────────┐
    │                              DATA LAYER                                            │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
    │  │                    PostgreSQL (Primary-Replica)                              │  │
    │  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                       │  │
    │  │  │   Primary   │───▶│  Replica 1  │    │  Replica 2  │  (Read replicas)     │  │
    │  │  │  (Writes)   │    │  (Reads)    │    │  (Reads)    │                       │  │
    │  │  └─────────────┘    └─────────────┘    └─────────────┘                       │  │
    │  └─────────────────────────────────────────────────────────────────────────────┘  │
    │                                                                                    │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
    │  │                    Key Generation Service (KGS)                              │  │
    │  │  ┌─────────────┐    ┌─────────────┐                                          │  │
    │  │  │  KGS Server │    │  Redis Pool │  (Pre-generated keys)                   │  │
    │  │  │  (Workers)  │───▶│  (1M keys)  │                                          │  │
    │  │  └─────────────┘    └─────────────┘                                          │  │
    │  └─────────────────────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────────────────────────────────────────────────────────────────┐
    │                              ANALYTICS PIPELINE                                    │
    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
    │  │   Kafka     │───▶│   Flink     │───▶│ClickHouse  │───▶│  Grafana    │        │
    │  │  (Events)   │    │ (Processing)│    │ (Analytics) │    │ (Dashboard) │        │
    │  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘        │
    └───────────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Key Generation Service (KGS)

```python
class KeyGenerationService:
    """
    Pre-generates unique, non-predictable short codes.
    Uses cryptographically secure random generation.
    """

    def __init__(self, redis_client, batch_size=10000):
        self.redis = redis_client
        self.batch_size = batch_size
        self.key_pool = "kgs:available_keys"
        self.used_keys = "kgs:used_keys"

    def generate_batch(self):
        """Generate a batch of unique keys."""
        import secrets
        keys = set()
        while len(keys) < self.batch_size:
            # Cryptographically secure random generation
            key = secrets.token_urlsafe(6)[:7]  # 7 chars
            if not self.redis.sismember(self.used_keys, key):
                keys.add(key)

        # Add to available pool atomically
        pipeline = self.redis.pipeline()
        pipeline.sadd(self.key_pool, *keys)
        pipeline.execute()

    def get_key(self) -> str:
        """Get a pre-generated key (O(1) operation)."""
        key = self.redis.spop(self.key_pool)
        if not key:
            # Fallback: generate on-demand
            key = secrets.token_urlsafe(6)[:7]

        self.redis.sadd(self.used_keys, key)
        return key

    def replenish_if_needed(self):
        """Background job to keep pool filled."""
        pool_size = self.redis.scard(self.key_pool)
        if pool_size < self.batch_size // 2:
            self.generate_batch()
```

#### 2. Rate Limiter (Token Bucket)

```python
class RateLimiter:
    """
    Distributed rate limiter using Redis.
    Implements token bucket algorithm.
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if request is allowed.
        Returns (is_allowed, remaining_tokens)
        """
        lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])

        local bucket = redis.call('HGETALL', key)
        local tokens = limit
        local last_update = now

        if #bucket > 0 then
            tokens = tonumber(bucket[2])
            last_update = tonumber(bucket[4])
        end

        local elapsed = now - last_update
        local refill = elapsed * (limit / window)
        tokens = math.min(limit, tokens + refill)

        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
            redis.call('EXPIRE', key, window)
            return {1, math.floor(tokens)}
        else
            return {0, 0}
        end
        """
        result = self.redis.eval(lua_script, 1, key, limit, window_seconds, time.time())
        return bool(result[0]), result[1]
```

#### 3. Analytics Pipeline

- **Event Collection**: Async click events pushed to Kafka
- **Stream Processing**: Apache Flink aggregates in real-time
- **Storage**: ClickHouse for time-series analytics
- **Visualization**: Grafana dashboards

### Caching Strategy (Multi-tier)

1. **CDN Edge Cache** (TTL: 5 min)
   - Popular URLs cached at edge
   - Reduces latency to <10ms

2. **Redis Cluster** (TTL: 1 hour)
   - Regional caches
   - 6-node cluster per region
   - LRU eviction policy

3. **Application Cache** (TTL: 30 sec)
   - In-process LRU cache
   - Reduces Redis calls

### Data Replication Strategy

- **PostgreSQL**: Primary-Replica with streaming replication
- **Redis**: Cluster mode with 3 masters, 3 replicas
- **Cross-region**: Async replication with <1 sec lag

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Create Short URL | POST valid URL | 201 with short_url |
| F-02 | Custom Alias | POST with custom alias | 201 with specified alias |
| F-03 | Duplicate Alias | POST existing alias | 409 Conflict |
| F-04 | Invalid URL | POST malformed URL | 400 Bad Request |
| F-05 | Redirect Valid | GET /{short_code} | 302 Redirect |
| F-06 | Redirect Expired | GET expired URL | 410 Gone |
| F-07 | Get URL Stats | GET /api/v1/urls/{code}/stats | 200 with analytics |
| F-08 | Bulk Create | POST /api/v1/urls/bulk | 201/207 results |
| F-09 | Update URL | PATCH /api/v1/urls/{code} | 200 Updated |
| F-10 | Delete URL | DELETE /api/v1/urls/{code} | 204 No Content |
| F-11 | Rate Limit Hit | Exceed rate limit | 429 with retry_after |
| F-12 | API Key Auth | Request with invalid key | 401 Unauthorized |
| F-13 | Idempotency | Retry with same key | Same response |
| F-14 | KGS Key Uniqueness | Create 100K URLs | All unique codes |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Redirect Latency (cache hit) | Measure with warm cache | < 10ms p99 |
| P-02 | Redirect Latency (cache miss) | Measure with cold cache | < 50ms p99 |
| P-03 | Create Latency | URL creation time | < 100ms p99 |
| P-04 | Read Throughput | Concurrent redirects | > 50,000 RPS |
| P-05 | Write Throughput | Concurrent creates | > 5,000 RPS |
| P-06 | KGS Throughput | Key generation rate | > 10,000 keys/sec |
| P-07 | Cache Hit Ratio | Monitor hit rate | > 95% |
| P-08 | DB Connection Pool | Pool utilization | < 70% |
| P-09 | Bulk Create | 1000 URLs in batch | < 5 sec |
| P-10 | Analytics Query | 30-day stats query | < 500ms |

### Chaos/Reliability Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis Cluster Failover | Kill master node | Automatic failover, < 5 sec |
| C-02 | DB Primary Failover | Kill primary DB | Replica promotion, < 30 sec |
| C-03 | Region Outage | Simulate region failure | Traffic routes to other regions |
| C-04 | KGS Failure | Kill KGS service | Fallback to on-demand generation |
| C-05 | Network Partition | Split brain scenario | Consistent reads, no data loss |
| C-06 | Kafka Failure | Kill Kafka broker | Events buffered, no loss |
| C-07 | 10x Traffic Spike | Sudden traffic increase | Auto-scale, graceful handling |
| C-08 | Slow Consumer | Analytics lag | Back-pressure, no data loss |
| C-09 | Certificate Expiry | Expired SSL cert | Alert triggered, manual renewal |
| C-10 | DNS Failure | DNS resolution fails | Cached DNS, retry logic |

### Load Test Scenarios

```yaml
# k6 load test configuration
scenarios:
  constant_load:
    executor: constant-arrival-rate
    rate: 10000
    duration: 30m
    preAllocatedVUs: 100

  spike_test:
    executor: ramping-arrival-rate
    startRate: 1000
    stages:
      - duration: 5m
        target: 1000
      - duration: 1m
        target: 50000  # 50x spike
      - duration: 5m
        target: 50000
      - duration: 1m
        target: 1000

  soak_test:
    executor: constant-arrival-rate
    rate: 5000
    duration: 4h
```

---

## Capacity Planning

| Metric | Value | Calculation |
|--------|-------|-------------|
| Monthly URLs Created | 500M | Given |
| Daily URLs Created | ~17M | 500M / 30 |
| Write QPS (peak) | ~400 | 17M / 43200 * 2 |
| Read:Write Ratio | 100:1 | Given |
| Read QPS (peak) | ~40,000 | 400 * 100 |
| Storage (URLs) | 250GB | 500M * 500 bytes |
| Storage (Analytics) | 1TB/month | 100 bytes * 10B clicks |
| Cache Size | 50GB | 10% hot data |
| Bandwidth | 500 Mbps | 40K RPS * 1.5KB |

---

## Monitoring & Alerting

### Key Metrics

- **Latency**: p50, p95, p99 for redirects and creates
- **Error Rate**: 4xx, 5xx by endpoint
- **Throughput**: RPS by region
- **Cache**: Hit ratio, eviction rate
- **Database**: Query time, connection pool, replication lag
- **KGS**: Pool size, generation rate

### Alert Thresholds

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Latency | p99 > 200ms for 5 min | Warning |
| Very High Latency | p99 > 500ms for 2 min | Critical |
| Error Rate | > 1% for 5 min | Warning |
| High Error Rate | > 5% for 2 min | Critical |
| KGS Pool Low | < 100K keys | Warning |
| KGS Pool Critical | < 10K keys | Critical |
| DB Replication Lag | > 5 sec | Warning |
| Cache Hit Ratio | < 90% | Warning |
