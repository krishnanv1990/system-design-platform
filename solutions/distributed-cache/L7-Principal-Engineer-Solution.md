# Distributed Cache - L7 (Principal Engineer) Solution

## Level Requirements

**Target Role:** Principal Engineer (L7)
**Focus:** Global-scale caching with advanced consistency and optimization

### What's Expected at L7

- Multi-region cache with geo-routing
- Strong consistency options with linearizability
- Tiered storage (memory, SSD, remote)
- ML-based cache eviction and prefetching
- Zero-downtime migrations
- Cache coherence protocols
- Cost optimization (memory vs compute trade-offs)
- Observability at scale with distributed tracing

---

## Database Schema

```json
{
  "storage_tiers": {
    "tier_1_hot": {
      "type": "In-Memory (DRAM)",
      "location": "Per-instance local",
      "capacity": "10K entries per instance",
      "latency": "< 100μs",
      "eviction": "ML-predicted LRU",
      "data_structures": [
        {
          "name": "hot_cache:{key}",
          "type": "Native Object",
          "fields": {
            "value": "Deserialized object",
            "version": "Vector clock",
            "access_pattern": "Recent access timestamps",
            "predicted_next_access": "ML prediction"
          }
        }
      ]
    },
    "tier_2_warm": {
      "type": "Redis Cluster",
      "location": "Regional",
      "capacity": "100GB per region",
      "latency": "< 2ms",
      "data_structures": [
        {
          "name": "cache:{region}:{namespace}:{key}",
          "type": "STRING",
          "format": {
            "value": "Compressed serialized data",
            "version": "Vector clock JSON",
            "origin_region": "Region that owns this key",
            "replicated_at": "Timestamp"
          }
        },
        {
          "name": "cache_vector_clock:{namespace}:{key}",
          "type": "HASH",
          "description": "Vector clock for conflict resolution",
          "fields": {
            "region_1": "Logical timestamp",
            "region_2": "Logical timestamp",
            "region_3": "Logical timestamp"
          }
        },
        {
          "name": "replication_queue:{region}",
          "type": "STREAM",
          "description": "Cross-region replication events",
          "fields": {
            "key": "Cache key",
            "value": "Serialized value",
            "vector_clock": "Version",
            "operation": "SET | DELETE"
          }
        }
      ]
    },
    "tier_3_cold": {
      "type": "SSD-backed (Redis on Flash / Aerospike)",
      "location": "Regional",
      "capacity": "1TB per region",
      "latency": "< 10ms",
      "use_case": "Large values, infrequent access"
    },
    "tier_4_archive": {
      "type": "Object Storage (S3/GCS)",
      "location": "Global",
      "capacity": "Unlimited",
      "latency": "< 100ms",
      "use_case": "Historical data, compliance"
    },
    "global_coordination": {
      "type": "CockroachDB / Spanner",
      "purpose": "Strongly consistent metadata",
      "tables": [
        {
          "name": "cache_ownership",
          "description": "Key ownership for strong consistency",
          "columns": [
            {"name": "key_hash", "type": "BYTES", "constraints": "PRIMARY KEY"},
            {"name": "namespace", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "owner_region", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "lease_expires_at", "type": "TIMESTAMPTZ"},
            {"name": "vector_clock", "type": "JSONB"}
          ]
        },
        {
          "name": "cache_configs",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "namespace", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
            {"name": "consistency_level", "type": "VARCHAR(20)", "constraints": "DEFAULT 'eventual'"},
            {"name": "replication_factor", "type": "INTEGER", "constraints": "DEFAULT 3"},
            {"name": "tiering_policy", "type": "JSONB"},
            {"name": "ml_optimization_enabled", "type": "BOOLEAN", "constraints": "DEFAULT true"},
            {"name": "cost_budget_monthly", "type": "DECIMAL"},
            {"name": "version", "type": "INTEGER", "constraints": "NOT NULL"}
          ]
        },
        {
          "name": "ml_predictions",
          "columns": [
            {"name": "key_hash", "type": "BYTES", "constraints": "PRIMARY KEY"},
            {"name": "namespace", "type": "VARCHAR(100)"},
            {"name": "predicted_access_count", "type": "INTEGER"},
            {"name": "predicted_next_access", "type": "TIMESTAMPTZ"},
            {"name": "tier_recommendation", "type": "VARCHAR(20)"},
            {"name": "confidence_score", "type": "FLOAT"},
            {"name": "model_version", "type": "VARCHAR(50)"},
            {"name": "updated_at", "type": "TIMESTAMPTZ"}
          ]
        }
      ]
    },
    "ml_feature_store": {
      "type": "Redis + Feature Store",
      "structures": [
        {
          "name": "access_features:{key_hash}",
          "type": "HASH",
          "fields": {
            "hourly_access_histogram": "24-element array",
            "daily_access_pattern": "7-element array",
            "recency_score": "Decay-weighted access",
            "frequency_score": "Total access count",
            "size_bytes": "Value size",
            "last_100_access_times": "Circular buffer"
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
      "method": "GET",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Get with configurable consistency and tiering",
      "query_params": {
        "consistency": "eventual | session | linearizable",
        "max_staleness_ms": "integer (for eventual consistency)",
        "allow_cold_tier": "boolean (default: true)",
        "trace_id": "string (for distributed tracing)"
      },
      "responses": {
        "200": {
          "value": "any",
          "metadata": {
            "version": {"us-east-1": 5, "eu-west-1": 4},
            "tier": "hot | warm | cold | archive",
            "age_ms": 150,
            "origin_region": "us-east-1",
            "consistency_achieved": "linearizable",
            "trace_id": "abc123"
          }
        },
        "404": {"error": "Key not found"},
        "408": {"error": "Consistency timeout", "best_effort_value": "..."},
        "503": {"error": "Quorum unavailable"}
      },
      "headers_returned": {
        "X-Cache-Tier": "warm",
        "X-Cache-Version": "{\"us-east-1\":5,\"eu-west-1\":4}",
        "X-Cache-Origin": "us-east-1",
        "X-Cache-Age-Ms": "150",
        "X-Trace-Id": "abc123"
      }
    },
    {
      "method": "PUT",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Set with consistency and tiering options",
      "request_body": {
        "value": "any (required)",
        "ttl": "integer (optional)",
        "consistency": "eventual | session | linearizable",
        "tier_hint": "hot | warm | cold (optional)",
        "expected_version": "object (optional, for CAS)",
        "replication_regions": "array of regions (optional)",
        "trace_id": "string (optional)"
      },
      "responses": {
        "200": {
          "success": true,
          "version": {"us-east-1": 6, "eu-west-1": 5},
          "tier_assigned": "warm",
          "replication_status": {
            "us-east-1": "confirmed",
            "eu-west-1": "pending",
            "ap-south-1": "pending"
          }
        },
        "409": {
          "error": "Version conflict",
          "current_version": {"us-east-1": 5, "eu-west-1": 4},
          "your_version": {"us-east-1": 4}
        },
        "507": {"error": "Storage quota exceeded", "tier": "warm"}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/transact",
      "description": "Multi-key transaction with ACID guarantees",
      "request_body": {
        "operations": [
          {"op": "GET", "key": "key1"},
          {"op": "SET", "key": "key2", "value": "..."},
          {"op": "DELETE", "key": "key3"}
        ],
        "isolation": "serializable | snapshot",
        "timeout_ms": 5000
      },
      "responses": {
        "200": {
          "committed": true,
          "results": [
            {"key": "key1", "value": "...", "version": "..."},
            {"key": "key2", "success": true, "version": "..."},
            {"key": "key3", "deleted": true}
          ]
        },
        "409": {"error": "Transaction conflict", "conflicting_keys": ["key2"]}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/prefetch",
      "description": "ML-driven prefetch hints",
      "request_body": {
        "context": {
          "user_id": "string",
          "session_id": "string",
          "recent_keys": ["key1", "key2"]
        }
      },
      "responses": {
        "200": {
          "prefetched": ["key3", "key4", "key5"],
          "confidence_scores": [0.95, 0.87, 0.72],
          "model_version": "v2.3.1"
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/cache/{namespace}/analytics",
      "description": "Advanced cache analytics",
      "query_params": {
        "period": "1h | 24h | 7d | 30d",
        "granularity": "minute | hour | day",
        "include_predictions": "boolean",
        "include_cost_analysis": "boolean"
      },
      "responses": {
        "200": {
          "hit_rate_by_tier": {
            "hot": 0.35,
            "warm": 0.55,
            "cold": 0.08,
            "archive": 0.02
          },
          "latency_by_tier": {
            "hot": {"p50": 0.08, "p99": 0.2},
            "warm": {"p50": 1.2, "p99": 3.5},
            "cold": {"p50": 8, "p99": 25}
          },
          "ml_metrics": {
            "prefetch_accuracy": 0.82,
            "tier_prediction_accuracy": 0.91,
            "eviction_prediction_accuracy": 0.88
          },
          "cost_analysis": {
            "memory_cost": 1250.00,
            "storage_cost": 450.00,
            "network_cost": 320.00,
            "total_monthly": 2020.00,
            "cost_per_million_ops": 0.15,
            "optimization_savings": 340.00
          },
          "cross_region": {
            "replication_lag_ms": {"eu-west-1": 45, "ap-south-1": 120},
            "conflict_rate": 0.0001
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/migrate",
      "description": "Zero-downtime key migration",
      "request_body": {
        "source_namespace": "string",
        "target_namespace": "string",
        "key_pattern": "string (glob)",
        "strategy": "copy | move",
        "rate_limit_keys_per_second": 1000
      },
      "responses": {
        "202": {
          "migration_id": "uuid",
          "estimated_keys": 150000,
          "estimated_duration_seconds": 150
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/cache/topology",
      "description": "Global cache topology",
      "responses": {
        "200": {
          "regions": [
            {
              "name": "us-east-1",
              "status": "healthy",
              "nodes": 12,
              "memory_used_gb": 85,
              "memory_total_gb": 100,
              "keys": 5200000,
              "roles": ["primary", "read-replica"]
            }
          ],
          "global_keys": 15600000,
          "replication_topology": {
            "us-east-1": ["eu-west-1", "ap-south-1"],
            "eu-west-1": ["us-east-1"],
            "ap-south-1": ["us-east-1"]
          }
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
                          Distributed Cache - L7 Global Architecture
    ════════════════════════════════════════════════════════════════════════════════════

                                    ┌────────────────────┐
                                    │    Global DNS      │
                                    │   (GeoDNS + Health)│
                                    └─────────┬──────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
              ▼                               ▼                               ▼
    ┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
    │   US-EAST-1      │           │   EU-WEST-1      │           │   AP-SOUTH-1     │
    │   (Primary)      │           │   (Replica)      │           │   (Replica)      │
    └──────────────────┘           └──────────────────┘           └──────────────────┘
              │                               │                               │
              ▼                               ▼                               ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           PER-REGION ARCHITECTURE                                │
    │                                                                                  │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                          EDGE / INGRESS LAYER                               │ │
    │  │                                                                             │ │
    │  │  ┌─────────────────┐                          ┌─────────────────┐           │ │
    │  │  │   API Gateway   │                          │  Service Mesh   │           │ │
    │  │  │   (Envoy/Kong)  │                          │  (Istio/Linkerd)│           │ │
    │  │  │                 │                          │                 │           │ │
    │  │  │ • GeoDNS routing│                          │ • mTLS          │           │ │
    │  │  │ • Rate limiting │                          │ • Circuit break │           │ │
    │  │  │ • Auth/AuthZ    │                          │ • Tracing       │           │ │
    │  │  └─────────────────┘                          └─────────────────┘           │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                                         ▼                                        │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                        CACHE SERVICE LAYER                                  │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────┐  ┌──────────────────────┐                        │ │
    │  │  │  Cache Service Pod   │  │  Cache Service Pod   │  ... (Auto-scaled)     │ │
    │  │  │                      │  │                      │                        │ │
    │  │  │ ┌──────────────────┐ │  │ ┌──────────────────┐ │                        │ │
    │  │  │ │ TIER 1: HOT     │ │  │ │ TIER 1: HOT     │ │                        │ │
    │  │  │ │ (In-Memory)     │ │  │ │ (In-Memory)     │ │                        │ │
    │  │  │ │ • 10K entries   │ │  │ │ • 10K entries   │ │                        │ │
    │  │  │ │ • ML eviction   │ │  │ │ • ML eviction   │ │                        │ │
    │  │  │ │ • < 100μs       │ │  │ │ • < 100μs       │ │                        │ │
    │  │  │ └──────────────────┘ │  │ └──────────────────┘ │                        │ │
    │  │  │                      │  │                      │                        │ │
    │  │  │ ┌──────────────────┐ │  │ ┌──────────────────┐ │                        │ │
    │  │  │ │ Consistency Mgr │ │  │ │ Consistency Mgr │ │                        │ │
    │  │  │ │ • Vector clocks │ │  │ │ • Vector clocks │ │                        │ │
    │  │  │ │ • Quorum logic  │ │  │ │ • Quorum logic  │ │                        │ │
    │  │  │ │ • Conflict res  │ │  │ │ • Conflict res  │ │                        │ │
    │  │  │ └──────────────────┘ │  │ └──────────────────┘ │                        │ │
    │  │  │                      │  │                      │                        │ │
    │  │  │ ┌──────────────────┐ │  │ ┌──────────────────┐ │                        │ │
    │  │  │ │ ML Prefetcher   │ │  │ │ ML Prefetcher   │ │                        │ │
    │  │  │ │ • Access pred   │ │  │ │ • Access pred   │ │                        │ │
    │  │  │ │ • Tier optimize │ │  │ │ • Tier optimize │ │                        │ │
    │  │  │ └──────────────────┘ │  │ └──────────────────┘ │                        │ │
    │  │  └──────────────────────┘  └──────────────────────┘                        │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                    ┌────────────────────┼────────────────────┐                   │
    │                    │                    │                    │                   │
    │                    ▼                    ▼                    ▼                   │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                         STORAGE TIERS                                       │ │
    │  │                                                                             │ │
    │  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │ │
    │  │  │   TIER 2: WARM      │  │   TIER 3: COLD      │  │   TIER 4: ARCHIVE   │ │ │
    │  │  │   (Redis Cluster)   │  │   (Redis on Flash)  │  │   (S3/GCS)          │ │ │
    │  │  │                     │  │                     │  │                     │ │ │
    │  │  │ • 100GB             │  │ • 1TB               │  │ • Unlimited         │ │ │
    │  │  │ • < 2ms             │  │ • < 10ms            │  │ • < 100ms           │ │ │
    │  │  │ • High freq access  │  │ • Large values      │  │ • Historical        │ │ │
    │  │  │ • Vector clocks     │  │ • Infrequent        │  │ • Compliance        │ │ │
    │  │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    └─────────────────────────────────────────┼────────────────────────────────────────┘
                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                       CROSS-REGION COORDINATION                                  │
    │                                                                                  │
    │  ┌────────────────────────────────┐    ┌────────────────────────────────┐       │
    │  │   Global Metadata Store        │    │   Replication Stream           │       │
    │  │   (CockroachDB / Spanner)      │    │   (Kafka / Pulsar)             │       │
    │  │                                │    │                                │       │
    │  │ • Key ownership leases         │    │ • Async replication events     │       │
    │  │ • Vector clock coordination    │    │ • Ordered per-key              │       │
    │  │ • Config source of truth       │    │ • At-least-once delivery       │       │
    │  │ • Linearizable reads           │    │ • Conflict detection           │       │
    │  └────────────────────────────────┘    └────────────────────────────────┘       │
    │                                                                                  │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                    REPLICATION TOPOLOGY                                     │ │
    │  │                                                                             │ │
    │  │     US-EAST-1 (Primary)                                                     │ │
    │  │          │                                                                  │ │
    │  │          ├──────────────────► EU-WEST-1 (Async, ~50ms)                      │ │
    │  │          │                                                                  │ │
    │  │          └──────────────────► AP-SOUTH-1 (Async, ~150ms)                    │ │
    │  │                                                                             │ │
    │  │     For strong consistency: Synchronous replication to quorum (2 of 3)      │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                        ML & OBSERVABILITY PLATFORM                               │
    │                                                                                  │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
    │  │   ML Platform       │  │   Observability     │  │   Cost Optimizer    │      │
    │  │   (Vertex AI)       │  │   (Prometheus+Jaeger│  │   Service           │      │
    │  │                     │  │    +Grafana)        │  │                     │      │
    │  │ • Prefetch model    │  │                     │  │ • Tier cost tracking│      │
    │  │ • Eviction model    │  │ • Latency histo     │  │ • Usage forecasting │      │
    │  │ • Tier placement    │  │ • Hit rate by tier  │  │ • Auto-scaling      │      │
    │  │ • Access prediction │  │ • Distributed trace │  │ • Spot instance mgmt│      │
    │  │ • Online learning   │  │ • Anomaly detection │  │ • Budget alerts     │      │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
    └─────────────────────────────────────────────────────────────────────────────────┘
```

### Vector Clock Consistency Implementation

```python
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json

class ConsistencyLevel(Enum):
    EVENTUAL = "eventual"
    SESSION = "session"
    LINEARIZABLE = "linearizable"

class CacheTier(Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"

@dataclass
class VectorClock:
    """
    Vector clock for tracking causality across regions.
    """
    timestamps: Dict[str, int] = field(default_factory=dict)

    def increment(self, region: str):
        self.timestamps[region] = self.timestamps.get(region, 0) + 1

    def merge(self, other: "VectorClock"):
        """Merge two vector clocks (take max of each component)."""
        for region, ts in other.timestamps.items():
            self.timestamps[region] = max(
                self.timestamps.get(region, 0),
                ts
            )

    def happens_before(self, other: "VectorClock") -> bool:
        """Check if this clock happens-before another."""
        # self < other iff all components <= and at least one <
        all_leq = True
        at_least_one_lt = False

        all_regions = set(self.timestamps.keys()) | set(other.timestamps.keys())

        for region in all_regions:
            self_ts = self.timestamps.get(region, 0)
            other_ts = other.timestamps.get(region, 0)

            if self_ts > other_ts:
                all_leq = False
            if self_ts < other_ts:
                at_least_one_lt = True

        return all_leq and at_least_one_lt

    def concurrent_with(self, other: "VectorClock") -> bool:
        """Check if two clocks are concurrent (neither happens-before)."""
        return not self.happens_before(other) and not other.happens_before(self)

    def to_dict(self) -> Dict[str, int]:
        return self.timestamps.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, int]) -> "VectorClock":
        return cls(timestamps=d.copy())


@dataclass
class CacheEntry:
    value: Any
    version: VectorClock
    tier: CacheTier
    created_at: float
    last_accessed: float
    access_count: int
    size_bytes: int
    origin_region: str
    ttl: int


@dataclass
class MLPrediction:
    next_access_probability: float
    recommended_tier: CacheTier
    eviction_priority: float  # Lower = evict first
    prefetch_candidates: List[str]
    confidence: float


class GlobalDistributedCache:
    """
    L7 Global Distributed Cache with:
    - Multi-tier storage (hot/warm/cold/archive)
    - Vector clock consistency
    - ML-driven optimization
    - Cross-region replication
    """

    def __init__(
        self,
        region: str,
        regions: List[str],
        hot_cache: "HotCache",
        warm_store: "RedisCluster",
        cold_store: "RedisOnFlash",
        archive_store: "ObjectStorage",
        global_metadata: "GlobalMetadataStore",
        replication_stream: "ReplicationStream",
        ml_service: "MLPredictionService"
    ):
        self.region = region
        self.regions = regions
        self.hot_cache = hot_cache
        self.warm_store = warm_store
        self.cold_store = cold_store
        self.archive_store = archive_store
        self.global_metadata = global_metadata
        self.replication_stream = replication_stream
        self.ml_service = ml_service

    async def get(
        self,
        namespace: str,
        key: str,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        max_staleness_ms: int = None,
        allow_cold_tier: bool = True
    ) -> Optional[Dict]:
        """
        Get value with configurable consistency.

        - EVENTUAL: Return local value, may be stale
        - SESSION: Return value at least as fresh as client's last write
        - LINEARIZABLE: Coordinate with owner region for latest value
        """
        full_key = f"{namespace}:{key}"
        start_time = time.time()

        # Tier 1: Hot cache (always checked first)
        entry = self.hot_cache.get(full_key)
        if entry and self._satisfies_consistency(entry, consistency, max_staleness_ms):
            self._record_access(full_key, CacheTier.HOT)
            return self._format_response(entry, CacheTier.HOT, start_time)

        # For linearizable, must check with owner
        if consistency == ConsistencyLevel.LINEARIZABLE:
            return await self._linearizable_read(namespace, key, start_time)

        # Tier 2: Warm store (Redis)
        entry = await self.warm_store.get(full_key)
        if entry:
            # Promote to hot cache
            self.hot_cache.set(full_key, entry)
            self._record_access(full_key, CacheTier.WARM)
            return self._format_response(entry, CacheTier.WARM, start_time)

        if not allow_cold_tier:
            return None

        # Tier 3: Cold store
        entry = await self.cold_store.get(full_key)
        if entry:
            # Consider promoting based on ML prediction
            await self._maybe_promote(full_key, entry)
            self._record_access(full_key, CacheTier.COLD)
            return self._format_response(entry, CacheTier.COLD, start_time)

        # Tier 4: Archive
        entry = await self.archive_store.get(full_key)
        if entry:
            self._record_access(full_key, CacheTier.ARCHIVE)
            return self._format_response(entry, CacheTier.ARCHIVE, start_time)

        return None

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: int = 3600,
        consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL,
        tier_hint: CacheTier = None,
        expected_version: Dict = None
    ) -> Dict:
        """
        Set value with configurable consistency.

        - EVENTUAL: Write locally, async replicate
        - LINEARIZABLE: Coordinate with quorum
        """
        full_key = f"{namespace}:{key}"

        # Get current version for vector clock
        current_entry = await self._get_current_entry(full_key)
        new_version = VectorClock()

        if current_entry:
            new_version = current_entry.version

            # Check expected version for CAS
            if expected_version:
                expected = VectorClock.from_dict(expected_version)
                if not expected.timestamps == new_version.timestamps:
                    return {
                        "success": False,
                        "error": "version_conflict",
                        "current_version": new_version.to_dict(),
                        "expected_version": expected_version
                    }

        # Increment our region's clock
        new_version.increment(self.region)

        # Determine tier
        tier = tier_hint or await self._determine_tier(full_key, value)

        # Create entry
        entry = CacheEntry(
            value=value,
            version=new_version,
            tier=tier,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=0,
            size_bytes=len(json.dumps(value).encode()),
            origin_region=self.region,
            ttl=ttl
        )

        # Write based on consistency level
        if consistency == ConsistencyLevel.LINEARIZABLE:
            result = await self._linearizable_write(full_key, entry)
        else:
            result = await self._eventual_write(full_key, entry)

        return result

    async def _linearizable_read(
        self,
        namespace: str,
        key: str,
        start_time: float
    ) -> Optional[Dict]:
        """
        Linearizable read: coordinate with owner region.
        """
        full_key = f"{namespace}:{key}"

        # Get owner region for this key
        owner = await self.global_metadata.get_owner(full_key)

        if owner == self.region:
            # We are the owner - read from warm store
            entry = await self.warm_store.get(full_key)
        else:
            # Forward to owner region
            entry = await self._forward_read(owner, full_key)

        if entry:
            # Update hot cache
            self.hot_cache.set(full_key, entry)
            return self._format_response(entry, CacheTier.WARM, start_time)

        return None

    async def _linearizable_write(
        self,
        key: str,
        entry: CacheEntry
    ) -> Dict:
        """
        Linearizable write: write to quorum of regions.
        """
        # Get ownership lease
        lease = await self.global_metadata.acquire_lease(key, self.region)

        if not lease:
            return {
                "success": False,
                "error": "could_not_acquire_lease"
            }

        try:
            # Write to local warm store
            await self._write_to_tier(key, entry)

            # Replicate to quorum (synchronous)
            quorum_size = len(self.regions) // 2 + 1
            acks = await self._replicate_sync(key, entry, quorum_size)

            if acks >= quorum_size:
                return {
                    "success": True,
                    "version": entry.version.to_dict(),
                    "tier_assigned": entry.tier.value,
                    "acks": acks
                }
            else:
                return {
                    "success": False,
                    "error": "quorum_not_reached",
                    "acks": acks,
                    "required": quorum_size
                }
        finally:
            await self.global_metadata.release_lease(key)

    async def _eventual_write(
        self,
        key: str,
        entry: CacheEntry
    ) -> Dict:
        """
        Eventual consistency write: local write + async replication.
        """
        # Write to appropriate tier
        await self._write_to_tier(key, entry)

        # Update hot cache
        self.hot_cache.set(key, entry)

        # Queue async replication
        await self.replication_stream.publish({
            "key": key,
            "entry": self._serialize_entry(entry),
            "origin": self.region,
            "timestamp": time.time()
        })

        return {
            "success": True,
            "version": entry.version.to_dict(),
            "tier_assigned": entry.tier.value,
            "replication_status": "queued"
        }

    async def _write_to_tier(self, key: str, entry: CacheEntry):
        """Write entry to appropriate tier."""
        if entry.tier == CacheTier.HOT:
            self.hot_cache.set(key, entry)
        elif entry.tier == CacheTier.WARM:
            await self.warm_store.set(key, entry)
        elif entry.tier == CacheTier.COLD:
            await self.cold_store.set(key, entry)
        elif entry.tier == CacheTier.ARCHIVE:
            await self.archive_store.set(key, entry)

    async def _determine_tier(self, key: str, value: Any) -> CacheTier:
        """Use ML to determine optimal tier."""
        prediction = await self.ml_service.predict_tier(key, value)

        if prediction.confidence > 0.8:
            return prediction.recommended_tier

        # Default logic based on size
        size = len(json.dumps(value).encode())

        if size < 1024:  # < 1KB
            return CacheTier.WARM
        elif size < 1024 * 1024:  # < 1MB
            return CacheTier.WARM
        else:
            return CacheTier.COLD

    async def _maybe_promote(self, key: str, entry: CacheEntry):
        """Promote entry to higher tier based on ML prediction."""
        prediction = await self.ml_service.predict_tier(key, entry.value)

        if prediction.recommended_tier.value < entry.tier.value:
            # Higher tier recommended
            entry.tier = prediction.recommended_tier
            await self._write_to_tier(key, entry)

    async def prefetch(self, context: Dict) -> List[str]:
        """
        ML-driven prefetching based on access patterns.
        """
        predictions = await self.ml_service.predict_prefetch(context)

        prefetched = []
        for key, confidence in predictions:
            if confidence > 0.7:  # Only prefetch high-confidence
                entry = await self._prefetch_key(key)
                if entry:
                    prefetched.append(key)

        return prefetched

    async def _prefetch_key(self, key: str) -> Optional[CacheEntry]:
        """Prefetch a key to hot cache."""
        # Try warm store first
        entry = await self.warm_store.get(key)

        if entry:
            self.hot_cache.set(key, entry)
            return entry

        return None

    def _satisfies_consistency(
        self,
        entry: CacheEntry,
        consistency: ConsistencyLevel,
        max_staleness_ms: int
    ) -> bool:
        """Check if entry satisfies consistency requirements."""
        if consistency == ConsistencyLevel.EVENTUAL:
            if max_staleness_ms:
                age_ms = (time.time() - entry.last_accessed) * 1000
                return age_ms <= max_staleness_ms
            return True

        if consistency == ConsistencyLevel.SESSION:
            # Would need session context to validate
            return True

        if consistency == ConsistencyLevel.LINEARIZABLE:
            return False  # Must always check authoritative source

        return True

    def _format_response(
        self,
        entry: CacheEntry,
        tier: CacheTier,
        start_time: float
    ) -> Dict:
        """Format cache response with metadata."""
        return {
            "value": entry.value,
            "metadata": {
                "version": entry.version.to_dict(),
                "tier": tier.value,
                "age_ms": int((time.time() - entry.created_at) * 1000),
                "origin_region": entry.origin_region,
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        }


class MLEvictionPolicy:
    """
    ML-based cache eviction that predicts which items
    to evict based on access patterns.
    """

    def __init__(self, model: "EvictionModel"):
        self.model = model

    async def select_for_eviction(
        self,
        candidates: List[Tuple[str, CacheEntry]],
        count: int
    ) -> List[str]:
        """
        Select items to evict based on ML predictions.

        Features used:
        - Recency (time since last access)
        - Frequency (access count)
        - Size
        - Time-of-day patterns
        - Entry age
        """
        predictions = []

        for key, entry in candidates:
            features = self._extract_features(entry)
            eviction_score = await self.model.predict_eviction_priority(features)
            predictions.append((key, eviction_score))

        # Sort by eviction priority (lower = evict first)
        predictions.sort(key=lambda x: x[1])

        return [key for key, _ in predictions[:count]]

    def _extract_features(self, entry: CacheEntry) -> Dict:
        """Extract ML features from cache entry."""
        now = time.time()

        return {
            "recency": now - entry.last_accessed,
            "frequency": entry.access_count,
            "size_bytes": entry.size_bytes,
            "age": now - entry.created_at,
            "tier": entry.tier.value,
            "hour_of_day": time.localtime().tm_hour,
            "day_of_week": time.localtime().tm_wday
        }
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Eventual read | GET with eventual consistency | Return local value |
| F-02 | Linearizable read | GET with linearizable | Coordinate with owner |
| F-03 | Session consistency | GET after write | See own write |
| F-04 | Vector clock merge | Concurrent writes | Clocks merged correctly |
| F-05 | Conflict detection | Concurrent concurrent writes | Conflict flagged |
| F-06 | Tier promotion | Cold key accessed frequently | Promoted to warm |
| F-07 | Tier demotion | Warm key unused | Demoted to cold |
| F-08 | ML eviction | Cache full | ML selects eviction |
| F-09 | ML prefetch | Access pattern | Related keys prefetched |
| F-10 | Quorum write | Linearizable write | Acks from majority |
| F-11 | Quorum failure | Region down | Write fails gracefully |
| F-12 | Cross-region replication | Write in US | Visible in EU |
| F-13 | Replication conflict | Concurrent cross-region | Vector clock resolution |
| F-14 | Transaction commit | Multi-key transaction | All or nothing |
| F-15 | Transaction abort | Conflict detected | Rollback |
| F-16 | Zero-downtime migration | Move keys | No read failures |
| F-17 | Archive retrieval | Old key access | Retrieved from S3 |
| F-18 | Lease acquisition | Write coordination | Lease granted |
| F-19 | Lease timeout | Owner fails | Lease released |
| F-20 | Cost tracking | Various operations | Costs accurately tracked |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Hot tier latency | Local memory read | < 100μs p99 |
| P-02 | Warm tier latency | Redis read | < 2ms p99 |
| P-03 | Cold tier latency | SSD read | < 10ms p99 |
| P-04 | Archive latency | S3 read | < 100ms p99 |
| P-05 | Linearizable read | Cross-region coordination | < 150ms p99 |
| P-06 | Linearizable write | Quorum write | < 200ms p99 |
| P-07 | Replication lag | Cross-region async | < 200ms p95 |
| P-08 | ML prediction | Tier/eviction decision | < 5ms p99 |
| P-09 | Prefetch accuracy | ML prefetch hit rate | > 70% |
| P-10 | Throughput per region | All tiers | > 500K RPS |
| P-11 | Global throughput | 3 regions | > 1.5M RPS |
| P-12 | Transaction throughput | Multi-key | > 10K TPS |
| P-13 | Migration throughput | Key migration | > 10K keys/s |
| P-14 | Vector clock overhead | Metadata size | < 100 bytes |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Region failure | Kill entire region | Other regions serve traffic |
| C-02 | Partial region failure | 50% nodes down | Degraded but functional |
| C-03 | Network partition | Split brain | Detect and handle |
| C-04 | Replication lag spike | 10s lag | Eventual consistency holds |
| C-05 | ML service down | Predictions unavailable | Fall back to LRU |
| C-06 | Metadata store down | CockroachDB unavailable | Use cached ownership |
| C-07 | Archive unavailable | S3 down | Graceful degradation |
| C-08 | Clock skew | 5s drift | Vector clocks handle |
| C-09 | Hot spot | 1M RPS single key | Replication/caching |
| C-10 | Memory pressure | 95% memory | ML eviction activates |
| C-11 | Cascading failure | Multiple components | Circuit breakers |
| C-12 | Data corruption | Invalid entries | Detection and recovery |
| C-13 | Split brain recovery | Partition heals | Vector clock merge |
| C-14 | Lease deadlock | Holder crashes | Timeout and release |
| C-15 | Migration interruption | Mid-migration failure | Resumable migration |

### Consistency Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| G-01 | Read-your-writes | Write then read | Always see own write |
| G-02 | Monotonic reads | Sequential reads | Never see older value |
| G-03 | Causal consistency | Related operations | Causally ordered |
| G-04 | Linearizability | Concurrent operations | Appear sequential |
| G-05 | Conflict resolution | Concurrent writes | Deterministic winner |

---

## Capacity Estimates

### Global Scale

- **Total entries**: 100M
- **Average value size**: 5KB
- **Total data**: ~500GB
- **Regions**: 3 (US, EU, APAC)
- **Global QPS**: 2M reads, 200K writes

### Per-Region Resources

- **Hot tier**: 10K entries × 20 instances = 200K entries, ~2GB
- **Warm tier**: 100GB Redis (20M entries)
- **Cold tier**: 1TB SSD-backed (50M entries)
- **Archive**: Unlimited S3

### Latency Targets

- **Hot tier**: < 100μs
- **Warm tier**: < 2ms
- **Cold tier**: < 10ms
- **Cross-region**: < 200ms
- **Linearizable**: < 300ms

### Cost Optimization

- **Memory cost**: $0.10/GB/hour → optimize with tiering
- **Network cost**: $0.02/GB → batch replication
- **Storage cost**: $0.023/GB/month → archive old data
- **ML inference**: $0.001/prediction → batch predictions

---

## Key Considerations for L7

1. **Consistency spectrum**: Support multiple consistency levels for different use cases
2. **Global scale**: Multi-region with intelligent geo-routing
3. **Cost efficiency**: Tiered storage with ML-driven placement
4. **Observability**: Distributed tracing across regions and tiers
5. **Operational excellence**: Zero-downtime migrations, automated failover
6. **ML integration**: Predictions for eviction, prefetch, and tier placement
7. **Conflict resolution**: Vector clocks for causality tracking
