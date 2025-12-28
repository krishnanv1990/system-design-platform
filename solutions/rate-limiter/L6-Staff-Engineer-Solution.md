# Rate Limiter - L6 (Staff Engineer) Solution

## Level Requirements

**Target Role:** Staff Engineer (L6)
**Focus:** Production-ready distributed rate limiting with high availability

### What's Expected at L6

- Multiple rate limiting algorithms (Token Bucket, Sliding Window Log, Sliding Window Counter)
- Distributed rate limiting across multiple servers
- Redis Cluster for high availability
- Hierarchical rate limits (per user, per API, global)
- Real-time analytics and dashboards
- Graceful degradation strategies

---

## Database Schema

```json
{
  "primary_storage": "Redis Cluster",
  "analytics": "ClickHouse",
  "configuration": "PostgreSQL",

  "redis_structures": [
    {
      "name": "rl:sliding:{client_id}:{resource}:{window}",
      "type": "ZSET",
      "description": "Sliding window log with timestamps",
      "members": "request_id with timestamp as score",
      "ttl": "2 * window_seconds"
    },
    {
      "name": "rl:counter:{client_id}:{resource}:{window_start}",
      "type": "STRING",
      "description": "Fixed window counter",
      "value": "request count",
      "ttl": "2 * window_seconds"
    },
    {
      "name": "rl:token:{client_id}",
      "type": "HASH",
      "fields": {
        "tokens": "float - available tokens",
        "last_refill": "timestamp",
        "tier": "string - rate limit tier"
      }
    },
    {
      "name": "rl:config:{tier}",
      "type": "HASH",
      "description": "Cached tier configuration",
      "fields": {
        "rps": "requests per second",
        "burst": "burst capacity",
        "daily_limit": "daily quota",
        "algorithm": "token_bucket|sliding_window|fixed_window"
      }
    },
    {
      "name": "rl:quota:{client_id}:{date}",
      "type": "STRING",
      "description": "Daily quota tracking",
      "ttl": "86400"
    }
  ],

  "postgresql_tables": [
    {
      "name": "rate_limit_tiers",
      "columns": [
        {"name": "id", "type": "SERIAL PRIMARY KEY"},
        {"name": "name", "type": "VARCHAR(50) UNIQUE NOT NULL"},
        {"name": "description", "type": "TEXT"},
        {"name": "requests_per_second", "type": "DECIMAL(10,2)"},
        {"name": "burst_capacity", "type": "INTEGER"},
        {"name": "daily_quota", "type": "BIGINT"},
        {"name": "monthly_quota", "type": "BIGINT"},
        {"name": "algorithm", "type": "VARCHAR(30) DEFAULT 'token_bucket'"},
        {"name": "priority", "type": "INTEGER DEFAULT 0"},
        {"name": "created_at", "type": "TIMESTAMPTZ DEFAULT NOW()"},
        {"name": "updated_at", "type": "TIMESTAMPTZ DEFAULT NOW()"}
      ]
    },
    {
      "name": "rate_limit_overrides",
      "columns": [
        {"name": "id", "type": "SERIAL PRIMARY KEY"},
        {"name": "client_id", "type": "VARCHAR(255) NOT NULL"},
        {"name": "resource", "type": "VARCHAR(100)"},
        {"name": "tier_id", "type": "INTEGER REFERENCES rate_limit_tiers(id)"},
        {"name": "custom_rps", "type": "DECIMAL(10,2)"},
        {"name": "custom_burst", "type": "INTEGER"},
        {"name": "expires_at", "type": "TIMESTAMPTZ"},
        {"name": "reason", "type": "TEXT"},
        {"name": "created_by", "type": "VARCHAR(100)"},
        {"name": "created_at", "type": "TIMESTAMPTZ DEFAULT NOW()"}
      ],
      "indexes": [
        {"columns": ["client_id", "resource"], "unique": true}
      ]
    },
    {
      "name": "rate_limit_events",
      "columns": [
        {"name": "id", "type": "BIGSERIAL PRIMARY KEY"},
        {"name": "client_id", "type": "VARCHAR(255) NOT NULL"},
        {"name": "resource", "type": "VARCHAR(100)"},
        {"name": "event_type", "type": "VARCHAR(20)"},
        {"name": "request_count", "type": "INTEGER"},
        {"name": "limit_value", "type": "INTEGER"},
        {"name": "metadata", "type": "JSONB"},
        {"name": "created_at", "type": "TIMESTAMPTZ DEFAULT NOW()"}
      ],
      "partitioning": "RANGE on created_at, monthly"
    }
  ],

  "clickhouse_tables": [
    {
      "name": "rate_limit_metrics",
      "columns": [
        {"name": "timestamp", "type": "DateTime64(3)"},
        {"name": "client_id", "type": "LowCardinality(String)"},
        {"name": "resource", "type": "LowCardinality(String)"},
        {"name": "tier", "type": "LowCardinality(String)"},
        {"name": "allowed", "type": "UInt8"},
        {"name": "tokens_remaining", "type": "Float32"},
        {"name": "latency_us", "type": "UInt32"},
        {"name": "region", "type": "LowCardinality(String)"}
      ],
      "engine": "MergeTree()",
      "partition_by": "toYYYYMMDD(timestamp)",
      "order_by": "(client_id, timestamp)",
      "ttl": "timestamp + INTERVAL 30 DAY"
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
    "title": "Distributed Rate Limiter API",
    "version": "2.0.0"
  },
  "endpoints": [
    {
      "method": "POST",
      "path": "/api/v1/check",
      "description": "Check and consume rate limit quota",
      "headers": {
        "X-Request-ID": "UUID for tracing"
      },
      "request_body": {
        "client_id": "string (required)",
        "resource": "string (default: 'default')",
        "cost": "integer (default: 1)",
        "metadata": {
          "ip": "string",
          "user_agent": "string",
          "endpoint": "string"
        }
      },
      "responses": {
        "200": {
          "allowed": true,
          "limit": 1000,
          "remaining": 850,
          "reset_at": "ISO8601",
          "retry_after": null,
          "quotas": {
            "per_second": {"limit": 10, "remaining": 8},
            "per_minute": {"limit": 100, "remaining": 75},
            "per_day": {"limit": 10000, "remaining": 9500}
          }
        },
        "429": {
          "allowed": false,
          "limit": 1000,
          "remaining": 0,
          "reset_at": "ISO8601",
          "retry_after": 1.5,
          "blocked_by": "per_second"
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/check/batch",
      "description": "Batch check multiple clients/resources",
      "request_body": {
        "checks": [
          {"client_id": "user_1", "resource": "api", "cost": 1},
          {"client_id": "user_2", "resource": "api", "cost": 1}
        ]
      },
      "responses": {
        "200": {
          "results": [
            {"client_id": "user_1", "allowed": true, "remaining": 99},
            {"client_id": "user_2", "allowed": false, "remaining": 0}
          ]
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/status/{client_id}",
      "description": "Get comprehensive rate limit status",
      "query_params": {
        "resource": "string (optional)",
        "include_history": "boolean"
      },
      "responses": {
        "200": {
          "client_id": "user_123",
          "tier": "pro",
          "limits": {
            "per_second": {"limit": 10, "remaining": 8, "reset_at": "..."},
            "per_minute": {"limit": 100, "remaining": 75, "reset_at": "..."},
            "per_day": {"limit": 10000, "remaining": 9500, "reset_at": "..."}
          },
          "history": {
            "last_hour": {"allowed": 250, "blocked": 5},
            "last_day": {"allowed": 5000, "blocked": 50}
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/tiers",
      "description": "Create or update rate limit tier",
      "request_body": {
        "name": "string",
        "requests_per_second": "number",
        "burst_capacity": "integer",
        "daily_quota": "integer",
        "algorithm": "token_bucket|sliding_window|fixed_window"
      },
      "responses": {
        "201": {"id": 1, "name": "enterprise", "created": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/overrides",
      "description": "Create client-specific override",
      "request_body": {
        "client_id": "string",
        "resource": "string (optional)",
        "custom_rps": "number",
        "custom_burst": "integer",
        "expires_at": "ISO8601",
        "reason": "string"
      },
      "responses": {
        "201": {"id": 1, "client_id": "vip_customer", "applied": true}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics",
      "description": "Get rate limiting analytics",
      "query_params": {
        "client_id": "string (optional)",
        "start_time": "ISO8601",
        "end_time": "ISO8601",
        "granularity": "minute|hour|day"
      },
      "responses": {
        "200": {
          "time_series": [
            {"timestamp": "...", "allowed": 1000, "blocked": 50}
          ],
          "top_blocked_clients": [...],
          "block_rate": 0.05
        }
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check with component status",
      "responses": {
        "200": {
          "status": "healthy",
          "redis_cluster": {"status": "healthy", "nodes": 6},
          "postgres": {"status": "healthy", "connections": 45},
          "version": "2.0.0"
        }
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                        Rate Limiter - L6 Production Architecture
    ════════════════════════════════════════════════════════════════════════════

                                ┌─────────────────────┐
                                │   Load Balancer     │
                                │   (L7 / HAProxy)    │
                                └──────────┬──────────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              │                            │                            │
              ▼                            ▼                            ▼
    ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
    │  Rate Limiter   │        │  Rate Limiter   │        │  Rate Limiter   │
    │  Instance 1     │        │  Instance 2     │        │  Instance 3     │
    │                 │        │                 │        │                 │
    │ • Token Bucket  │        │ • Token Bucket  │        │ • Token Bucket  │
    │ • Sliding Window│        │ • Sliding Window│        │ • Sliding Window│
    │ • Local Cache   │        │ • Local Cache   │        │ • Local Cache   │
    └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
             │                          │                          │
             └──────────────────────────┼──────────────────────────┘
                                        │
                           ┌────────────┴────────────┐
                           │                         │
                           ▼                         ▼
              ┌─────────────────────┐   ┌─────────────────────┐
              │    Redis Cluster    │   │     PostgreSQL      │
              │    (6 nodes)        │   │   (Primary-Replica) │
              │                     │   │                     │
              │ ┌─────┐ ┌─────┐    │   │ • Tier configs      │
              │ │ M1  │ │ M2  │    │   │ • Overrides         │
              │ │ R1  │ │ R2  │    │   │ • Event logs        │
              │ └─────┘ └─────┘    │   │                     │
              │ ┌─────┐            │   └─────────────────────┘
              │ │ M3  │            │
              │ │ R3  │            │
              │ └─────┘            │
              └─────────────────────┘
                           │
                           ▼
              ┌─────────────────────────────────────────────────┐
              │              Analytics Pipeline                  │
              │                                                  │
              │  ┌──────────┐   ┌──────────┐   ┌──────────┐     │
              │  │  Kafka   │──▶│  Flink   │──▶│ClickHouse│     │
              │  │ (Events) │   │(Aggregate)│   │(Analytics)│    │
              │  └──────────┘   └──────────┘   └──────────┘     │
              └─────────────────────────────────────────────────┘
```

### Sliding Window Counter Algorithm

```python
import time
import redis
from typing import Tuple, Dict

class SlidingWindowCounter:
    """
    Sliding Window Counter implementation.

    Combines the memory efficiency of fixed windows with
    the smoothness of sliding windows using weighted averaging.
    """

    def __init__(self, redis_cluster: redis.RedisCluster):
        self.redis = redis_cluster

    def is_allowed(
        self,
        client_id: str,
        resource: str,
        limit: int,
        window_seconds: int,
        cost: int = 1
    ) -> Tuple[bool, Dict]:
        """
        Check if request is allowed using sliding window counter.

        The algorithm:
        1. Divide time into fixed windows
        2. Count requests in current and previous window
        3. Weight previous window by overlap percentage
        4. Compare weighted sum against limit
        """
        now = time.time()
        current_window = int(now // window_seconds)
        previous_window = current_window - 1
        window_elapsed = now % window_seconds
        previous_weight = 1 - (window_elapsed / window_seconds)

        current_key = f"rl:counter:{client_id}:{resource}:{current_window}"
        previous_key = f"rl:counter:{client_id}:{resource}:{previous_window}"

        lua_script = """
        local current_key = KEYS[1]
        local previous_key = KEYS[2]
        local limit = tonumber(ARGV[1])
        local cost = tonumber(ARGV[2])
        local previous_weight = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])

        local current_count = tonumber(redis.call('GET', current_key) or '0')
        local previous_count = tonumber(redis.call('GET', previous_key) or '0')

        local weighted_count = current_count + (previous_count * previous_weight)

        if weighted_count + cost <= limit then
            redis.call('INCRBY', current_key, cost)
            redis.call('EXPIRE', current_key, window_seconds * 2)
            return {1, current_count + cost, limit - current_count - cost}
        else
            return {0, current_count, 0}
        end
        """

        result = self.redis.eval(
            lua_script, 2,
            current_key, previous_key,
            limit, cost, previous_weight, window_seconds
        )

        allowed = bool(result[0])
        current = int(result[1])
        remaining = int(result[2])

        reset_at = (current_window + 1) * window_seconds

        return allowed, {
            "allowed": allowed,
            "limit": limit,
            "remaining": max(0, remaining),
            "reset_at": reset_at,
            "retry_after": reset_at - now if not allowed else None
        }
```

### Hierarchical Rate Limiting

```python
class HierarchicalRateLimiter:
    """
    Multi-level rate limiting: per-second, per-minute, per-day.
    All levels must pass for request to be allowed.
    """

    def __init__(self, redis_cluster):
        self.redis = redis_cluster
        self.levels = [
            {"name": "per_second", "window": 1, "limit_key": "rps"},
            {"name": "per_minute", "window": 60, "limit_key": "rpm"},
            {"name": "per_hour", "window": 3600, "limit_key": "rph"},
            {"name": "per_day", "window": 86400, "limit_key": "rpd"},
        ]

    async def check(
        self,
        client_id: str,
        tier_config: dict,
        cost: int = 1
    ) -> dict:
        """
        Check all rate limit levels.
        Returns combined result with per-level details.
        """
        results = {}
        blocked_by = None

        for level in self.levels:
            limit = tier_config.get(level["limit_key"], float("inf"))
            if limit == float("inf"):
                continue

            allowed, info = await self._check_level(
                client_id, level["name"], limit, level["window"], cost
            )

            results[level["name"]] = {
                "limit": limit,
                "remaining": info["remaining"],
                "reset_at": info["reset_at"]
            }

            if not allowed and blocked_by is None:
                blocked_by = level["name"]

        return {
            "allowed": blocked_by is None,
            "blocked_by": blocked_by,
            "quotas": results,
            "retry_after": self._calculate_retry_after(results, blocked_by)
        }
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Token bucket basic | Allow within limit | 200, allowed=true |
| F-02 | Token bucket exhaust | Exceed burst | 429 after burst |
| F-03 | Sliding window accuracy | Check boundary behavior | Smooth rate limiting |
| F-04 | Hierarchical limits | Multi-level limiting | Blocked at correct level |
| F-05 | Client isolation | Different clients | Independent limits |
| F-06 | Tier configuration | Apply tier settings | Correct limits applied |
| F-07 | Override priority | Client override | Override takes precedence |
| F-08 | Batch check | Multiple checks | All results returned |
| F-09 | Quota tracking | Daily quota | Accurate daily count |
| F-10 | Analytics recording | Check events logged | Events in ClickHouse |
| F-11 | Cluster failover | Node failure | Automatic failover |
| F-12 | Config hot reload | Update tier | Applied without restart |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Single check latency | One client, one resource | < 2ms p99 |
| P-02 | Batch check latency | 100 checks in batch | < 20ms p99 |
| P-03 | Throughput | Max checks per second | > 100,000/sec |
| P-04 | Concurrent clients | 10,000 simultaneous | < 5ms p99 |
| P-05 | Cluster distribution | Even key distribution | < 10% variance |
| P-06 | Memory efficiency | 1M active clients | < 2GB Redis |
| P-07 | Analytics pipeline | Event processing lag | < 5 seconds |
| P-08 | Config lookup | Tier config retrieval | < 0.5ms (cached) |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis master failure | Kill master node | Replica promotes, < 5s |
| C-02 | Network partition | Split cluster | Consistent behavior |
| C-03 | Thundering herd | 10x traffic spike | Graceful rate limiting |
| C-04 | Clock drift | 5 second skew | Correct window calculation |
| C-05 | Memory pressure | Redis near capacity | LRU eviction, no crash |
| C-06 | Slow client | 10s response delay | Timeout, count request |
| C-07 | Config service down | PostgreSQL failure | Use cached config |
| C-08 | Analytics lag | Kafka consumer slow | Back-pressure, no data loss |
| C-09 | Full quota reset | Midnight quota reset | Atomic reset, no race |
| C-10 | Hot key | One client 50% traffic | Handled without hotspot |

---

## Monitoring & Alerting

### Key Metrics

- **Request rate**: Checks per second by tier
- **Block rate**: Percentage of blocked requests
- **Latency**: p50, p95, p99 check latency
- **Redis cluster health**: Node status, replication lag
- **Quota utilization**: Percentage of quota used

### Alert Thresholds

| Alert | Condition | Severity |
|-------|-----------|----------|
| High block rate | > 10% blocked | Warning |
| Very high block rate | > 25% blocked | Critical |
| Redis node down | Node unreachable | Critical |
| High latency | p99 > 10ms | Warning |
| Quota exhaustion | > 90% quota used | Warning |
