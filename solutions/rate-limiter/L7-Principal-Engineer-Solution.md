# Rate Limiter - L7 (Principal Engineer) Solution

## Level Requirements

**Target Role:** Principal Engineer (L7)
**Focus:** Global-scale distributed rate limiting with advanced algorithms

### What's Expected at L7

- Multi-region distributed rate limiting
- Advanced algorithms: Sliding Window Log, Adaptive Rate Limiting
- ML-based anomaly detection and auto-adjustment
- Global synchronization with eventual consistency
- Sub-millisecond local decisions with async global sync
- Cost-aware rate limiting (different costs for different operations)
- Fairness algorithms preventing starvation
- Real-time analytics and predictive scaling

---

## Database Schema

```json
{
  "storage_layers": {
    "local_cache": {
      "type": "In-Memory (Thread-Safe)",
      "purpose": "Sub-millisecond local decisions",
      "data_structures": [
        {
          "name": "local_bucket:{client_id}:{resource}",
          "type": "TokenBucket",
          "fields": {
            "tokens": "Atomic float64",
            "last_update": "Unix timestamp nanoseconds",
            "config_version": "Configuration version for invalidation"
          }
        },
        {
          "name": "local_window:{client_id}:{window_id}",
          "type": "SlidingWindowLog",
          "fields": {
            "timestamps": "Circular buffer of request timestamps",
            "count": "Atomic counter"
          }
        }
      ],
      "eviction": "LRU with 100K entry limit per node"
    },
    "regional_store": {
      "type": "Redis Cluster",
      "purpose": "Regional coordination and persistence",
      "data_structures": [
        {
          "name": "region:{region}:bucket:{client_id}:{resource}",
          "type": "HASH",
          "fields": {
            "tokens": "Current token count",
            "last_update": "Last refill timestamp",
            "total_requests": "Request counter for analytics",
            "violations": "Violation counter"
          }
        },
        {
          "name": "region:{region}:sliding_log:{client_id}:{resource}",
          "type": "ZSET",
          "description": "Sorted set with timestamps as scores",
          "operations": ["ZADD", "ZREMRANGEBYSCORE", "ZCOUNT"]
        },
        {
          "name": "region:{region}:adaptive:{client_id}",
          "type": "HASH",
          "fields": {
            "current_limit": "Dynamically adjusted limit",
            "base_limit": "Original configured limit",
            "behavior_score": "ML-computed client behavior score",
            "last_adjustment": "Timestamp of last limit adjustment"
          }
        },
        {
          "name": "global_sync:{client_id}",
          "type": "STREAM",
          "description": "Cross-region synchronization events",
          "format": {
            "region": "Origin region",
            "delta": "Token consumption delta",
            "timestamp": "Event timestamp"
          }
        }
      ]
    },
    "global_store": {
      "type": "CockroachDB",
      "purpose": "Global configuration, analytics, audit",
      "tables": [
        {
          "name": "rate_limit_configs",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
            {"name": "client_id", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "resource", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "algorithm", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "base_rate", "type": "FLOAT", "constraints": "NOT NULL"},
            {"name": "burst_capacity", "type": "INT", "constraints": "NOT NULL"},
            {"name": "global_limit", "type": "INT", "constraints": "Global cross-region limit"},
            {"name": "cost_multipliers", "type": "JSONB", "constraints": "Operation-specific costs"},
            {"name": "priority", "type": "INT", "constraints": "Fairness priority (1-10)"},
            {"name": "adaptive_enabled", "type": "BOOLEAN", "constraints": "DEFAULT false"},
            {"name": "version", "type": "INT", "constraints": "NOT NULL DEFAULT 1"},
            {"name": "created_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"},
            {"name": "updated_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"}
          ],
          "indexes": [
            {"columns": ["client_id", "resource"], "unique": true},
            {"columns": ["version"]}
          ]
        },
        {
          "name": "rate_limit_events",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
            {"name": "client_id", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "resource", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "region", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "event_type", "type": "VARCHAR(50)", "constraints": "allowed/blocked/warning"},
            {"name": "tokens_consumed", "type": "FLOAT"},
            {"name": "tokens_remaining", "type": "FLOAT"},
            {"name": "latency_us", "type": "INT"},
            {"name": "timestamp", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"}
          ],
          "partitioning": {
            "type": "RANGE",
            "column": "timestamp",
            "interval": "1 day"
          },
          "retention": "30 days"
        },
        {
          "name": "anomaly_detections",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "client_id", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "anomaly_type", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "confidence_score", "type": "FLOAT", "constraints": "NOT NULL"},
            {"name": "baseline_metrics", "type": "JSONB"},
            {"name": "detected_metrics", "type": "JSONB"},
            {"name": "action_taken", "type": "VARCHAR(100)"},
            {"name": "detected_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"}
          ]
        },
        {
          "name": "fairness_quotas",
          "columns": [
            {"name": "client_id", "type": "VARCHAR(255)", "constraints": "PRIMARY KEY"},
            {"name": "priority_class", "type": "INT", "constraints": "NOT NULL"},
            {"name": "weight", "type": "FLOAT", "constraints": "NOT NULL DEFAULT 1.0"},
            {"name": "min_guaranteed", "type": "INT", "constraints": "Minimum guaranteed rate"},
            {"name": "max_burst", "type": "INT", "constraints": "Maximum burst allowed"},
            {"name": "borrowed_quota", "type": "INT", "constraints": "Quota borrowed from pool"},
            {"name": "last_active", "type": "TIMESTAMPTZ"}
          ]
        }
      ]
    },
    "ml_feature_store": {
      "type": "Redis + S3",
      "purpose": "ML model features and predictions",
      "structures": [
        {
          "name": "features:{client_id}",
          "type": "HASH",
          "fields": {
            "request_pattern": "Serialized request pattern vector",
            "time_series": "Recent request time series",
            "behavior_embedding": "128-dim behavior embedding"
          }
        },
        {
          "name": "predictions:{client_id}",
          "type": "HASH",
          "fields": {
            "predicted_load": "Predicted next-hour load",
            "anomaly_probability": "Anomaly probability score",
            "recommended_limit": "ML-recommended rate limit"
          }
        }
      ]
    }
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
      "description": "Check and consume rate limit with sub-millisecond response",
      "request_body": {
        "client_id": "string (required)",
        "resource": "string (default: 'default')",
        "operation": "string (for cost-based limiting)",
        "cost": "integer (optional, default: auto-calculated)",
        "priority": "string (optional: 'high', 'normal', 'low')",
        "idempotency_key": "string (optional, for exactly-once semantics)"
      },
      "responses": {
        "200": {
          "allowed": true,
          "remaining": 95,
          "limit": 100,
          "reset_at": "2024-01-01T00:01:00Z",
          "cost_charged": 1,
          "global_remaining": 950,
          "decision_source": "local_cache",
          "latency_us": 150
        },
        "429": {
          "allowed": false,
          "remaining": 0,
          "limit": 100,
          "reset_at": "2024-01-01T00:01:00Z",
          "retry_after": 45,
          "retry_after_ms": 45000,
          "reason": "regional_limit_exceeded",
          "global_remaining": 50,
          "queue_position": 15,
          "estimated_wait_ms": 2000
        }
      },
      "headers_returned": {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "95",
        "X-RateLimit-Reset": "1703779260",
        "X-RateLimit-Global-Remaining": "950",
        "X-RateLimit-Decision-Latency-Us": "150",
        "X-RateLimit-Policy": "adaptive-sliding-window",
        "Retry-After": "45 (only on 429)",
        "Retry-After-Ms": "45000 (precise milliseconds)"
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/batch-check",
      "description": "Check multiple resources atomically",
      "request_body": {
        "client_id": "string",
        "checks": [
          {"resource": "api", "cost": 1},
          {"resource": "compute", "cost": 5},
          {"resource": "storage", "cost": 2}
        ],
        "mode": "all_or_nothing | best_effort"
      },
      "responses": {
        "200": {
          "allowed": true,
          "results": [
            {"resource": "api", "allowed": true, "remaining": 95},
            {"resource": "compute", "allowed": true, "remaining": 45},
            {"resource": "storage", "allowed": true, "remaining": 198}
          ]
        },
        "207": {
          "partial": true,
          "results": [
            {"resource": "api", "allowed": true, "remaining": 95},
            {"resource": "compute", "allowed": false, "remaining": 0},
            {"resource": "storage", "allowed": true, "remaining": 198}
          ]
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/reserve",
      "description": "Reserve capacity for future requests",
      "request_body": {
        "client_id": "string",
        "resource": "string",
        "tokens_needed": "integer",
        "duration_seconds": "integer (max: 300)",
        "priority": "string"
      },
      "responses": {
        "200": {
          "reservation_id": "uuid",
          "tokens_reserved": 50,
          "expires_at": "2024-01-01T00:05:00Z",
          "position_in_queue": 0
        },
        "202": {
          "reservation_id": "uuid",
          "status": "queued",
          "position_in_queue": 5,
          "estimated_grant_at": "2024-01-01T00:02:00Z"
        }
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/reserve/{reservation_id}",
      "description": "Release unused reservation",
      "responses": {
        "200": {"released": true, "tokens_returned": 30}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/status/{client_id}",
      "description": "Get comprehensive rate limit status",
      "query_params": {
        "include_global": "boolean (default: true)",
        "include_predictions": "boolean (default: false)",
        "include_history": "boolean (default: false)"
      },
      "responses": {
        "200": {
          "client_id": "user_123",
          "limits": [
            {
              "resource": "api",
              "algorithm": "adaptive_sliding_window",
              "current_limit": 120,
              "base_limit": 100,
              "remaining": 87,
              "regional_remaining": 87,
              "global_remaining": 870,
              "reset_at": "2024-01-01T00:01:00Z",
              "adaptive_adjustment": "+20%",
              "behavior_score": 0.95
            }
          ],
          "predictions": {
            "next_hour_load": 450,
            "recommended_action": "none",
            "anomaly_probability": 0.02
          },
          "history": {
            "last_24h_requests": 12500,
            "last_24h_blocked": 15,
            "average_latency_us": 180
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/configs",
      "description": "Create or update rate limit configuration",
      "request_body": {
        "client_id": "string",
        "resource": "string",
        "algorithm": "token_bucket | sliding_window | sliding_log | adaptive",
        "base_rate": "float (tokens/second)",
        "burst_capacity": "integer",
        "global_limit": "integer (optional)",
        "cost_multipliers": {
          "read": 1,
          "write": 5,
          "delete": 10
        },
        "priority": "integer (1-10)",
        "adaptive_config": {
          "enabled": true,
          "min_limit": 50,
          "max_limit": 500,
          "adjustment_interval_seconds": 60,
          "good_behavior_bonus": 0.1,
          "bad_behavior_penalty": 0.2
        }
      },
      "responses": {
        "201": {"id": "uuid", "version": 1, "propagation_status": "propagating"},
        "200": {"id": "uuid", "version": 2, "propagation_status": "propagating"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics",
      "description": "Get rate limiting analytics",
      "query_params": {
        "client_id": "string (optional)",
        "resource": "string (optional)",
        "region": "string (optional)",
        "start_time": "ISO8601",
        "end_time": "ISO8601",
        "granularity": "minute | hour | day"
      },
      "responses": {
        "200": {
          "summary": {
            "total_requests": 1250000,
            "allowed": 1245000,
            "blocked": 5000,
            "block_rate": 0.004,
            "avg_latency_us": 175,
            "p99_latency_us": 450
          },
          "by_region": {
            "us-east-1": {"requests": 500000, "blocked": 2000},
            "eu-west-1": {"requests": 450000, "blocked": 1800},
            "ap-south-1": {"requests": 300000, "blocked": 1200}
          },
          "time_series": [
            {"timestamp": "2024-01-01T00:00:00Z", "requests": 5000, "blocked": 20}
          ],
          "anomalies_detected": 3
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/emergency/throttle",
      "description": "Emergency global throttle",
      "request_body": {
        "scope": "global | region | client",
        "target": "string (region name or client_id)",
        "reduction_percent": "integer (0-100)",
        "duration_seconds": "integer",
        "reason": "string"
      },
      "responses": {
        "200": {"applied": true, "expires_at": "2024-01-01T01:00:00Z"}
      }
    },
    {
      "method": "GET",
      "path": "/internal/sync",
      "description": "Internal: Cross-region sync endpoint",
      "responses": {
        "200": {
          "region": "us-east-1",
          "sync_lag_ms": 50,
          "pending_events": 12,
          "last_sync": "2024-01-01T00:00:59Z"
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
                            Rate Limiter - L7 Global Architecture
    ════════════════════════════════════════════════════════════════════════════════════

                                    ┌─────────────────────┐
                                    │   Global DNS        │
                                    │   (Route 53/Cloud   │
                                    │    DNS with         │
                                    │    GeoDNS)          │
                                    └──────────┬──────────┘
                                               │
              ┌────────────────────────────────┼────────────────────────────────┐
              │                                │                                │
              ▼                                ▼                                ▼
    ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
    │    US-EAST-1        │       │    EU-WEST-1        │       │    AP-SOUTH-1       │
    │    REGION           │       │    REGION           │       │    REGION           │
    └─────────────────────┘       └─────────────────────┘       └─────────────────────┘
              │                                │                                │
              ▼                                ▼                                ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                              EDGE LAYER (per region)                            │
    │  ┌─────────────────────────────────────────────────────────────────────────┐    │
    │  │                     Envoy/NGINX Service Mesh                             │    │
    │  │  • TLS Termination                                                       │    │
    │  │  • L7 Load Balancing (least connections + weighted)                      │    │
    │  │  • Circuit Breaker (Envoy)                                               │    │
    │  │  • Coarse Rate Limiting (IP-based, DDoS protection)                      │    │
    │  └─────────────────────────────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           RATE LIMITER SERVICE (per region)                     │
    │                                                                                 │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
    │  │   RL Instance 1     │  │   RL Instance 2     │  │   RL Instance N     │     │
    │  │   (Go/Rust)         │  │   (Go/Rust)         │  │   (Go/Rust)         │     │
    │  │                     │  │                     │  │                     │     │
    │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │     │
    │  │ │ Local Cache     │ │  │ │ Local Cache     │ │  │ │ Local Cache     │ │     │
    │  │ │ (In-Memory)     │ │  │ │ (In-Memory)     │ │  │ │ (In-Memory)     │ │     │
    │  │ │ • Token Buckets │ │  │ │ • Token Buckets │ │  │ │ • Token Buckets │ │     │
    │  │ │ • Sliding Logs  │ │  │ │ • Sliding Logs  │ │  │ │ • Sliding Logs  │ │     │
    │  │ │ • 100K entries  │ │  │ │ • 100K entries  │ │  │ │ • 100K entries  │ │     │
    │  │ │ • ~100μs reads  │ │  │ │ • ~100μs reads  │ │  │ │ • ~100μs reads  │ │     │
    │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ │     │
    │  │                     │  │                     │  │                     │     │
    │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │     │
    │  │ │ Algorithm Eng.  │ │  │ │ Algorithm Eng.  │ │  │ │ Algorithm Eng.  │ │     │
    │  │ │ • Token Bucket  │ │  │ │ • Token Bucket  │ │  │ │ • Token Bucket  │ │     │
    │  │ │ • Sliding Win   │ │  │ │ • Sliding Win   │ │  │ │ • Sliding Win   │ │     │
    │  │ │ • Sliding Log   │ │  │ │ • Sliding Log   │ │  │ │ • Sliding Log   │ │     │
    │  │ │ • Adaptive      │ │  │ │ • Adaptive      │ │  │ │ • Adaptive      │ │     │
    │  │ │ • Fair Queue    │ │  │ │ • Fair Queue    │ │  │ │ • Fair Queue    │ │     │
    │  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ │     │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │
    │                                                                                 │
    │  ┌──────────────────────────────────────────────────────────────────────────┐  │
    │  │                        Async Workers (per instance)                       │  │
    │  │  • Background sync to Redis (batched, every 10ms)                         │  │
    │  │  • Global sync publisher (cross-region events)                            │  │
    │  │  • Config watcher (version-based invalidation)                            │  │
    │  │  • Metrics exporter (Prometheus)                                          │  │
    │  └──────────────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
    ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
    │     Redis Cluster         │ │     ML Inference          │ │     Kafka/Pulsar          │
    │     (Regional)            │ │     Service               │ │     (Event Stream)        │
    │                           │ │                           │ │                           │
    │ • Authoritative state     │ │ • Anomaly detection       │ │ • Cross-region sync       │
    │ • 6-node cluster          │ │ • Load prediction         │ │ • Event sourcing          │
    │ • ~1ms latency            │ │ • Adaptive recommendations│ │ • Analytics pipeline      │
    │ • Sliding window logs     │ │ • Real-time scoring       │ │ • Audit trail             │
    │ • Pub/Sub for sync        │ │ • TensorFlow Serving      │ │                           │
    └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘
                    │                                                      │
                    │                                                      │
                    └──────────────────────────┬───────────────────────────┘
                                               │
                                               ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                          GLOBAL COORDINATION LAYER                              │
    │                                                                                 │
    │  ┌────────────────────────────┐     ┌────────────────────────────┐             │
    │  │     CockroachDB            │     │     Global Config          │             │
    │  │     (Multi-Region)         │     │     Service                │             │
    │  │                            │     │                            │             │
    │  │  • Configs (source truth)  │     │  • Version management      │             │
    │  │  • Analytics warehouse     │     │  • Propagation tracking    │             │
    │  │  • Audit logs              │     │  • A/B testing configs     │             │
    │  │  • Anomaly records         │     │  • Feature flags           │             │
    │  │  • Fairness quotas         │     │                            │             │
    │  └────────────────────────────┘     └────────────────────────────┘             │
    │                                                                                 │
    │  ┌──────────────────────────────────────────────────────────────────────────┐  │
    │  │                    Cross-Region Sync (Kafka/Pulsar)                       │  │
    │  │                                                                           │  │
    │  │   US-EAST-1 ◄────────────────────────────────────────────► EU-WEST-1     │  │
    │  │       ▲                                                         ▲         │  │
    │  │       │                                                         │         │  │
    │  │       └─────────────────────► AP-SOUTH-1 ◄─────────────────────┘         │  │
    │  │                                                                           │  │
    │  │   • Eventual consistency (50-200ms cross-region)                          │  │
    │  │   • CRDT-based token bucket merging                                       │  │
    │  │   • Conflict resolution: pessimistic (prefer blocking)                    │  │
    │  └──────────────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                               │
                                               ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           OBSERVABILITY & ML PLATFORM                           │
    │                                                                                 │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
    │  │   Prometheus +      │  │   ELK Stack /       │  │   ML Pipeline       │     │
    │  │   Grafana           │  │   Cloud Logging     │  │   (Vertex AI)       │     │
    │  │                     │  │                     │  │                     │     │
    │  │ • Latency histograms│  │ • Request logs      │  │ • Feature eng.      │     │
    │  │ • Block rate        │  │ • Audit trail       │  │ • Model training    │     │
    │  │ • Sync lag          │  │ • Anomaly alerts    │  │ • Online inference  │     │
    │  │ • Queue depths      │  │ • Debug traces      │  │ • A/B experiments   │     │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘     │
    └─────────────────────────────────────────────────────────────────────────────────┘
```

### Algorithm: Adaptive Sliding Window with ML

```python
import time
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import Enum
import numpy as np

class DecisionSource(Enum):
    LOCAL_CACHE = "local_cache"
    REGIONAL_REDIS = "regional_redis"
    GLOBAL_LOOKUP = "global_lookup"

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    limit: int
    reset_at: float
    decision_source: DecisionSource
    latency_us: int
    global_remaining: Optional[int] = None
    adaptive_adjustment: Optional[str] = None
    queue_position: Optional[int] = None

@dataclass
class AdaptiveConfig:
    min_limit: int
    max_limit: int
    adjustment_interval: int  # seconds
    good_behavior_bonus: float  # 0.1 = +10%
    bad_behavior_penalty: float  # 0.2 = -20%

class AdaptiveSlidingWindowLimiter:
    """
    L7-grade adaptive sliding window rate limiter with ML integration.

    Features:
    - Sub-millisecond local decisions
    - Sliding window log for precise counting
    - ML-based adaptive limit adjustment
    - Cross-region synchronization
    - Fairness-aware scheduling
    """

    def __init__(
        self,
        local_cache: "LocalCache",
        redis_cluster: "RedisCluster",
        ml_client: "MLInferenceClient",
        sync_publisher: "CrossRegionPublisher",
        region: str
    ):
        self.local_cache = local_cache
        self.redis = redis_cluster
        self.ml_client = ml_client
        self.sync_publisher = sync_publisher
        self.region = region

        # Background sync state
        self._pending_syncs: Dict[str, List[Tuple[float, int]]] = {}
        self._sync_lock = asyncio.Lock()

    async def check(
        self,
        client_id: str,
        resource: str,
        cost: int = 1,
        priority: str = "normal"
    ) -> RateLimitResult:
        """
        Check rate limit with three-tier decision making:
        1. Local cache (sub-ms) - optimistic check
        2. Regional Redis (1-2ms) - authoritative regional
        3. Global sync (async) - cross-region consistency
        """
        start_time = time.perf_counter_ns()
        key = f"{client_id}:{resource}"

        # Tier 1: Local cache check (sub-millisecond)
        local_result = await self._check_local(key, cost)

        if local_result is not None:
            latency_us = (time.perf_counter_ns() - start_time) // 1000

            # Schedule async sync
            asyncio.create_task(self._schedule_sync(key, cost))

            return RateLimitResult(
                allowed=local_result["allowed"],
                remaining=local_result["remaining"],
                limit=local_result["limit"],
                reset_at=local_result["reset_at"],
                decision_source=DecisionSource.LOCAL_CACHE,
                latency_us=latency_us,
                adaptive_adjustment=local_result.get("adjustment")
            )

        # Tier 2: Regional Redis (authoritative)
        redis_result = await self._check_regional(key, cost, priority)
        latency_us = (time.perf_counter_ns() - start_time) // 1000

        # Update local cache
        await self._update_local_cache(key, redis_result)

        # Schedule cross-region sync
        asyncio.create_task(self._publish_cross_region(key, cost))

        return RateLimitResult(
            allowed=redis_result["allowed"],
            remaining=redis_result["remaining"],
            limit=redis_result["limit"],
            reset_at=redis_result["reset_at"],
            decision_source=DecisionSource.REGIONAL_REDIS,
            latency_us=latency_us,
            global_remaining=redis_result.get("global_remaining"),
            adaptive_adjustment=redis_result.get("adjustment"),
            queue_position=redis_result.get("queue_position")
        )

    async def _check_local(
        self,
        key: str,
        cost: int
    ) -> Optional[Dict]:
        """
        Optimistic local cache check.
        Returns None if cache miss or stale.
        """
        bucket = self.local_cache.get(key)

        if bucket is None:
            return None

        if bucket.is_stale():
            return None

        # Sliding window calculation
        now = time.time()
        window_start = now - bucket.window_seconds

        # Count requests in current window
        current_count = bucket.count_in_window(window_start)

        # Apply adaptive adjustment
        effective_limit = bucket.get_effective_limit()

        if current_count + cost <= effective_limit:
            bucket.record_request(now, cost)
            return {
                "allowed": True,
                "remaining": effective_limit - current_count - cost,
                "limit": effective_limit,
                "reset_at": now + bucket.window_seconds,
                "adjustment": bucket.get_adjustment_description()
            }

        return {
            "allowed": False,
            "remaining": 0,
            "limit": effective_limit,
            "reset_at": window_start + bucket.window_seconds,
            "adjustment": bucket.get_adjustment_description()
        }

    async def _check_regional(
        self,
        key: str,
        cost: int,
        priority: str
    ) -> Dict:
        """
        Authoritative check against regional Redis.
        Uses sliding window log algorithm with Lua script.
        """
        now = time.time()

        # Lua script for atomic sliding window
        lua_script = """
        local key = KEYS[1]
        local config_key = KEYS[2]
        local adaptive_key = KEYS[3]
        local now = tonumber(ARGV[1])
        local cost = tonumber(ARGV[2])
        local priority = ARGV[3]

        -- Get config
        local config = redis.call('HGETALL', config_key)
        local base_limit = tonumber(config[2]) or 100
        local window_seconds = tonumber(config[4]) or 60

        -- Get adaptive adjustment
        local adaptive = redis.call('HGETALL', adaptive_key)
        local current_limit = tonumber(adaptive[2]) or base_limit
        local behavior_score = tonumber(adaptive[4]) or 1.0

        -- Calculate effective limit with priority bonus
        local priority_multiplier = 1.0
        if priority == 'high' then
            priority_multiplier = 1.2
        elseif priority == 'low' then
            priority_multiplier = 0.8
        end
        local effective_limit = math.floor(current_limit * priority_multiplier)

        -- Sliding window log
        local window_start = now - window_seconds

        -- Remove old entries
        redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

        -- Count current window
        local current_count = redis.call('ZCARD', key)

        local allowed = 0
        local remaining = effective_limit - current_count

        if remaining >= cost then
            -- Add new entries
            for i = 1, cost do
                redis.call('ZADD', key, now, now .. ':' .. i .. ':' .. math.random())
            end
            allowed = 1
            remaining = remaining - cost

            -- Update stats
            redis.call('HINCRBY', adaptive_key, 'total_requests', cost)
        else
            -- Track violation
            redis.call('HINCRBY', adaptive_key, 'violations', 1)
            remaining = 0
        end

        -- Set TTL
        redis.call('EXPIRE', key, window_seconds + 10)

        return {allowed, remaining, effective_limit, window_start + window_seconds, current_limit, behavior_score}
        """

        client_id, resource = key.split(":", 1)
        config_key = f"config:{client_id}:{resource}"
        adaptive_key = f"adaptive:{client_id}"

        result = await self.redis.eval(
            lua_script,
            keys=[f"sliding_log:{key}", config_key, adaptive_key],
            args=[now, cost, priority]
        )

        return {
            "allowed": bool(result[0]),
            "remaining": int(result[1]),
            "limit": int(result[2]),
            "reset_at": float(result[3]),
            "adjustment": f"adaptive:{result[4]} (score:{result[5]:.2f})"
        }

    async def _schedule_sync(self, key: str, cost: int):
        """
        Batch syncs to Redis for efficiency.
        Syncs every 10ms or when batch reaches 100 items.
        """
        async with self._sync_lock:
            if key not in self._pending_syncs:
                self._pending_syncs[key] = []
            self._pending_syncs[key].append((time.time(), cost))

    async def _publish_cross_region(self, key: str, cost: int):
        """
        Publish consumption event for cross-region sync.
        """
        event = {
            "key": key,
            "region": self.region,
            "cost": cost,
            "timestamp": time.time()
        }
        await self.sync_publisher.publish("rate_limit_sync", event)

    async def run_adaptive_adjustment(self, client_id: str):
        """
        ML-based adaptive limit adjustment.
        Called periodically (every 60s) per client.
        """
        # Get ML predictions
        prediction = await self.ml_client.predict(client_id)

        # Get current stats
        stats = await self.redis.hgetall(f"adaptive:{client_id}")

        total_requests = int(stats.get("total_requests", 0))
        violations = int(stats.get("violations", 0))
        current_limit = int(stats.get("current_limit", 100))
        base_limit = int(stats.get("base_limit", 100))

        # Calculate behavior score
        if total_requests > 0:
            violation_rate = violations / total_requests
        else:
            violation_rate = 0

        # Adjust based on behavior and ML prediction
        new_limit = current_limit

        if violation_rate < 0.01 and prediction.anomaly_probability < 0.1:
            # Good behavior: increase limit
            new_limit = min(
                int(current_limit * 1.1),
                int(base_limit * 2)  # Max 2x base
            )
        elif violation_rate > 0.1 or prediction.anomaly_probability > 0.5:
            # Bad behavior or anomaly: decrease limit
            new_limit = max(
                int(current_limit * 0.8),
                int(base_limit * 0.5)  # Min 0.5x base
            )

        # Apply ML recommendation if confident
        if prediction.confidence > 0.8:
            new_limit = prediction.recommended_limit

        # Update adaptive config
        await self.redis.hset(
            f"adaptive:{client_id}",
            mapping={
                "current_limit": new_limit,
                "behavior_score": 1 - violation_rate,
                "last_adjustment": time.time(),
                "ml_confidence": prediction.confidence
            }
        )

        # Reset counters for next period
        await self.redis.hset(
            f"adaptive:{client_id}",
            mapping={"total_requests": 0, "violations": 0}
        )


class FairnessScheduler:
    """
    Weighted fair queuing for rate limit reservations.
    Prevents starvation while respecting priorities.
    """

    def __init__(self, redis_cluster: "RedisCluster"):
        self.redis = redis_cluster

    async def enqueue_reservation(
        self,
        client_id: str,
        tokens_needed: int,
        priority: int,
        duration: int
    ) -> Dict:
        """
        Add reservation to fair queue.
        Uses weighted fair queuing (WFQ).
        """
        now = time.time()

        # Get client weight from fairness config
        weight = await self._get_client_weight(client_id)

        # Calculate virtual finish time (lower = higher priority)
        # VFT = arrival_time + (tokens / weight) * (1 / priority)
        vft = now + (tokens_needed / weight) * (1 / priority)

        reservation = {
            "client_id": client_id,
            "tokens_needed": tokens_needed,
            "priority": priority,
            "duration": duration,
            "created_at": now,
            "vft": vft,
            "expires_at": now + duration
        }

        # Add to sorted set by VFT
        await self.redis.zadd(
            "fairness_queue",
            {f"{client_id}:{now}": vft}
        )

        # Store reservation details
        await self.redis.hset(
            f"reservation:{client_id}:{now}",
            mapping=reservation
        )

        # Get queue position
        position = await self.redis.zrank(
            "fairness_queue",
            f"{client_id}:{now}"
        )

        return {
            "reservation_id": f"{client_id}:{now}",
            "position": position,
            "estimated_grant_at": await self._estimate_grant_time(position)
        }

    async def _get_client_weight(self, client_id: str) -> float:
        """Get client's fairness weight (default 1.0)."""
        weight = await self.redis.hget(f"fairness:{client_id}", "weight")
        return float(weight) if weight else 1.0

    async def _estimate_grant_time(self, position: int) -> float:
        """Estimate when reservation will be granted."""
        # Assume 1000 tokens/second processing rate
        return time.time() + (position * 0.001)


class CrossRegionSynchronizer:
    """
    CRDT-based cross-region token bucket synchronization.
    Uses grow-only counter for consumption tracking.
    """

    async def merge_remote_state(
        self,
        local_state: Dict,
        remote_state: Dict
    ) -> Dict:
        """
        Merge remote region's state using CRDT semantics.
        - Counters: max of local and remote
        - Timestamps: max of local and remote
        - Tokens: recalculate based on merged consumption
        """
        merged = {}

        # Merge consumption counters (grow-only)
        local_consumed = local_state.get("total_consumed", 0)
        remote_consumed = remote_state.get("total_consumed", 0)
        merged["total_consumed"] = max(local_consumed, remote_consumed)

        # Merge timestamps
        local_time = local_state.get("last_update", 0)
        remote_time = remote_state.get("last_update", 0)
        merged["last_update"] = max(local_time, remote_time)

        # Recalculate available tokens
        capacity = local_state.get("capacity", 100)
        rate = local_state.get("rate", 10)  # tokens/second

        elapsed = time.time() - merged["last_update"]
        refilled = elapsed * rate

        merged["tokens"] = min(
            capacity,
            capacity - merged["total_consumed"] + refilled
        )

        return merged
```

### Key L7 Design Decisions

1. **Three-tier decision making**: Local cache for sub-ms decisions, regional Redis for authoritative state, async global sync for consistency.

2. **Sliding Window Log**: Precise request counting without the boundary issues of fixed windows.

3. **ML-based adaptation**: Automatically adjust limits based on client behavior patterns.

4. **CRDT-based sync**: Conflict-free replicated data types for eventual consistency across regions.

5. **Fair queuing**: Weighted fair queuing prevents starvation while respecting priorities.

6. **Cost-aware limiting**: Different operations consume different amounts of quota.

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Basic allow | Request within limit | 200, allowed=true, decision_source=local_cache |
| F-02 | Basic block | Request exceeds limit | 429, allowed=false, retry_after present |
| F-03 | Local cache hit | Repeated requests | Latency < 500μs, source=local_cache |
| F-04 | Cache miss fallback | New client request | source=regional_redis, cache updated |
| F-05 | Sliding window precision | Requests at window boundary | No boundary spike allowed |
| F-06 | Cost-aware limiting | High-cost operation | Consumes multiple tokens |
| F-07 | Priority boost | High priority request | Gets 20% more capacity |
| F-08 | Batch check all-or-nothing | Multiple resources | All succeed or all fail |
| F-09 | Batch check best-effort | Multiple resources | 207 with partial success |
| F-10 | Reservation creation | Reserve future capacity | Reservation ID returned |
| F-11 | Reservation consumption | Use reserved tokens | No limit check needed |
| F-12 | Reservation expiry | Unused reservation | Tokens returned to pool |
| F-13 | Cross-region sync | Request in region A | State visible in region B within 200ms |
| F-14 | Global limit enforcement | Multi-region requests | Global limit respected |
| F-15 | Adaptive increase | Good behavior | Limit increases by 10% |
| F-16 | Adaptive decrease | High violation rate | Limit decreases by 20% |
| F-17 | ML anomaly detection | Unusual pattern | Anomaly flagged, limit adjusted |
| F-18 | Fair queue ordering | Multiple reservations | Served by virtual finish time |
| F-19 | Starvation prevention | Low priority client | Eventually served |
| F-20 | Emergency throttle | Global reduction | All regions affected |
| F-21 | Config propagation | Update config | All instances updated within 1s |
| F-22 | Idempotency | Duplicate request ID | Only charged once |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Local cache latency | Cached check | < 200μs p99 |
| P-02 | Regional check latency | Redis check | < 2ms p99 |
| P-03 | Batch check latency | 10 resources | < 5ms p99 |
| P-04 | Throughput single node | Check requests | > 100,000 RPS |
| P-05 | Throughput cluster | Distributed | > 1M RPS |
| P-06 | Cross-region sync lag | Event propagation | < 200ms p95 |
| P-07 | Adaptive adjustment latency | ML inference | < 50ms p99 |
| P-08 | Memory per client | Local cache | < 1KB |
| P-09 | Redis ops per check | Commands | < 3 average |
| P-10 | Background sync batch | Efficiency | 100+ ops/batch |
| P-11 | Config reload | Hot reload | < 100ms |
| P-12 | Fair queue throughput | Reservations | > 10,000/s |
| P-13 | Global limit convergence | Multi-region | < 500ms |
| P-14 | Cold start time | New instance | < 5s to serving |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Local cache full | LRU eviction | Graceful eviction, no crash |
| C-02 | Redis cluster failover | Primary down | < 5s failover, no data loss |
| C-03 | Redis partition | Network split | Local decisions continue |
| C-04 | Cross-region partition | Region isolated | Local decisions, eventual sync |
| C-05 | ML service down | Inference fails | Fall back to static limits |
| C-06 | CockroachDB unavailable | Config store down | Use cached configs |
| C-07 | Kafka lag | Event backlog | Bounded queue, drop oldest |
| C-08 | Clock skew | Time drift 5s | Consistent within tolerance |
| C-09 | Hot client | 1M RPS single client | No impact on other clients |
| C-10 | Memory pressure | 90% memory | LRU eviction, stable |
| C-11 | CPU spike | 95% CPU | Graceful degradation |
| C-12 | Cascading failure | Multi-component | Circuit breakers engage |
| C-13 | Data corruption | Invalid state | Automatic recovery |
| C-14 | Split brain | Partition heal | CRDT merge, no duplicates |
| C-15 | DDoS simulation | 10x normal load | Edge rate limiting holds |

### Global Consistency Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| G-01 | Global limit accuracy | 1000 global limit | Never exceed by >5% |
| G-02 | Region isolation | Region A overloaded | Region B unaffected |
| G-03 | Sync convergence | 3-region writes | Converge within 500ms |
| G-04 | CRDT merge | Concurrent updates | Consistent final state |
| G-05 | Config consistency | Update propagation | All regions same config |

---

## Capacity Estimates

### Global Scale

- **Clients**: 10M unique
- **Regions**: 3 (US, EU, APAC)
- **Checks per second**: 1M globally
- **Cross-region events**: 100K/s

### Per-Region Resources

- **Rate Limiter instances**: 20 (auto-scaled)
- **Redis Cluster**: 6 nodes, 128GB total
- **Local cache per instance**: 100K entries, ~100MB

### Storage

- **Redis (per region)**: 50GB
- **CockroachDB**: 500GB (configs + 30-day analytics)
- **Kafka**: 1TB retention

### Latency Budget

- **Local decision**: < 200μs
- **Regional decision**: < 2ms
- **Global sync**: < 200ms (eventual)
- **ML inference**: < 50ms

---

## Key Considerations for L7

1. **Global-local tradeoff**: Sub-millisecond local decisions with eventual global consistency
2. **ML integration**: Adaptive rate limiting based on behavior patterns
3. **Multi-tenancy**: Isolation and fairness across millions of clients
4. **Observability at scale**: Distributed tracing, metrics aggregation
5. **Cost optimization**: Efficient resource usage, batched operations
6. **Failure domains**: Independent regions, graceful degradation
7. **Security**: Rate limiting as DDoS protection, anomaly detection
