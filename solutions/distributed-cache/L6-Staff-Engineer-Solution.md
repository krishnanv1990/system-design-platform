# Distributed Cache - L6 (Staff Engineer) Solution

## Level Requirements

**Target Role:** Staff Engineer (L6)
**Focus:** Scalable distributed caching with advanced patterns

### What's Expected at L6

- Consistent hashing for key distribution
- Redis Cluster with sharding
- Cache invalidation strategies
- Write-through and write-behind patterns
- Read replicas for scaling reads
- Pub/Sub for cache invalidation
- Monitoring and alerting
- Handling cache stampede

---

## Database Schema

```json
{
  "storage_layers": {
    "redis_cluster": {
      "type": "Redis Cluster",
      "nodes": "6 (3 masters + 3 replicas)",
      "data_structures": [
        {
          "name": "cache:{namespace}:{key}",
          "type": "STRING",
          "description": "Cached value with metadata embedded",
          "format": {
            "value": "Serialized data",
            "version": "Cache entry version for invalidation",
            "created_at": "Creation timestamp"
          }
        },
        {
          "name": "cache_lock:{namespace}:{key}",
          "type": "STRING",
          "description": "Distributed lock for cache population",
          "ttl": "30 seconds",
          "example": {"key": "cache_lock:users:user_123", "value": "node_1:thread_42"}
        },
        {
          "name": "cache_tags:{namespace}:{tag}",
          "type": "SET",
          "description": "Keys associated with a tag for bulk invalidation",
          "example": {
            "key": "cache_tags:products:category_electronics",
            "members": ["prod_1", "prod_2", "prod_3"]
          }
        },
        {
          "name": "invalidation_channel:{namespace}",
          "type": "PUBSUB",
          "description": "Channel for broadcasting invalidations",
          "message_format": {
            "type": "key | tag | pattern",
            "target": "key/tag/pattern value",
            "timestamp": "Unix timestamp"
          }
        },
        {
          "name": "hot_keys:{namespace}",
          "type": "ZSET",
          "description": "Tracking hot keys for optimization",
          "score": "Access count in current window"
        }
      ]
    },
    "local_cache": {
      "type": "In-Memory (per instance)",
      "purpose": "L1 cache for hot keys",
      "max_size": "1000 entries",
      "eviction": "LRU"
    },
    "persistence": {
      "type": "PostgreSQL",
      "tables": [
        {
          "name": "cache_configs",
          "columns": [
            {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
            {"name": "namespace", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
            {"name": "default_ttl", "type": "INTEGER", "constraints": "DEFAULT 3600"},
            {"name": "max_entry_size", "type": "INTEGER", "constraints": "DEFAULT 1048576"},
            {"name": "write_policy", "type": "VARCHAR(20)", "constraints": "DEFAULT 'write-through'"},
            {"name": "invalidation_strategy", "type": "VARCHAR(20)", "constraints": "DEFAULT 'pub-sub'"},
            {"name": "local_cache_enabled", "type": "BOOLEAN", "constraints": "DEFAULT true"},
            {"name": "compression_enabled", "type": "BOOLEAN", "constraints": "DEFAULT false"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ]
        },
        {
          "name": "cache_metrics",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "namespace", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "node_id", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "hits", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "misses", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "evictions", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "stampedes_prevented", "type": "INTEGER", "constraints": "DEFAULT 0"},
            {"name": "window_start", "type": "TIMESTAMP", "constraints": "NOT NULL"},
            {"name": "window_end", "type": "TIMESTAMP", "constraints": "NOT NULL"}
          ],
          "indexes": [
            {"columns": ["namespace", "window_start"]}
          ]
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
      "description": "Get cached value with consistency options",
      "query_params": {
        "consistency": "eventual | strong (default: eventual)",
        "refresh_ttl": "boolean (extend TTL on access)"
      },
      "responses": {
        "200": {
          "value": "any",
          "metadata": {
            "version": 3,
            "ttl_remaining": 3500,
            "created_at": "2024-01-01T00:00:00Z",
            "source": "local | redis | replica"
          }
        },
        "404": {"error": "Key not found"},
        "503": {"error": "Cache unavailable", "retry_after": 5}
      },
      "headers_returned": {
        "X-Cache-Hit": "true",
        "X-Cache-Source": "local | redis | replica",
        "X-Cache-Version": "3"
      }
    },
    {
      "method": "PUT",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Set cached value with write policy",
      "request_body": {
        "value": "any (required)",
        "ttl": "integer (optional)",
        "tags": "array of strings (optional)",
        "write_policy": "write-through | write-behind (optional)",
        "version": "integer (optional, for optimistic locking)"
      },
      "responses": {
        "200": {"success": true, "version": 4},
        "201": {"success": true, "version": 1, "created": true},
        "409": {"error": "Version conflict", "current_version": 3},
        "507": {"error": "Storage quota exceeded"}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Delete and invalidate across cluster",
      "query_params": {
        "broadcast": "boolean (default: true, send invalidation)"
      },
      "responses": {
        "200": {"success": true, "invalidation_sent": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/invalidate",
      "description": "Bulk invalidation by tag or pattern",
      "request_body": {
        "type": "tag | pattern",
        "value": "string (tag name or glob pattern)",
        "async": "boolean (default: false)"
      },
      "responses": {
        "200": {"invalidated": 150, "nodes_notified": 6},
        "202": {"job_id": "abc123", "status": "processing"}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/warm",
      "description": "Pre-warm cache with data",
      "request_body": {
        "entries": [
          {"key": "k1", "value": "v1", "ttl": 3600}
        ],
        "source": "optional callback URL for lazy loading"
      },
      "responses": {
        "200": {"warmed": 100, "failed": 0}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/cache/{namespace}/stats",
      "description": "Detailed cache statistics",
      "query_params": {
        "period": "1h | 24h | 7d"
      },
      "responses": {
        "200": {
          "overview": {
            "hit_rate": 0.94,
            "total_keys": 125000,
            "memory_used_mb": 512
          },
          "by_node": [
            {"node": "redis-1", "keys": 42000, "memory_mb": 170},
            {"node": "redis-2", "keys": 41500, "memory_mb": 168},
            {"node": "redis-3", "keys": 41500, "memory_mb": 174}
          ],
          "hot_keys": [
            {"key": "user_123", "hits": 15000},
            {"key": "product_456", "hits": 12000}
          ],
          "stampedes_prevented": 45
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/cache/cluster/health",
      "description": "Cluster health and topology",
      "responses": {
        "200": {
          "status": "healthy",
          "nodes": [
            {"id": "redis-1", "role": "master", "slots": "0-5460", "status": "ok"},
            {"id": "redis-2", "role": "master", "slots": "5461-10922", "status": "ok"},
            {"id": "redis-3", "role": "master", "slots": "10923-16383", "status": "ok"}
          ],
          "replication_lag_ms": 2
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
                     Distributed Cache - L6 Architecture
    ═══════════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────────┐
    │                          CLIENT APPLICATIONS                         │
    └────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         LOAD BALANCER (Nginx)                        │
    │                                                                      │
    │  • SSL Termination                                                   │
    │  • Health-based routing                                              │
    │  • Connection pooling                                                │
    └────────────────────────────────┬────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
    │  Cache Service  │    │  Cache Service  │    │  Cache Service  │
    │   Instance 1    │    │   Instance 2    │    │   Instance N    │
    │                 │    │                 │    │                 │
    │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
    │ │ Local Cache │ │    │ │ Local Cache │ │    │ │ Local Cache │ │
    │ │  (L1, LRU)  │ │    │ │  (L1, LRU)  │ │    │ │  (L1, LRU)  │ │
    │ │  1K entries │ │    │ │  1K entries │ │    │ │  1K entries │ │
    │ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
    │                 │    │                 │    │                 │
    │ • Consistent    │    │ • Consistent    │    │ • Consistent    │
    │   hash routing  │    │   hash routing  │    │   hash routing  │
    │ • Stampede lock │    │ • Stampede lock │    │ • Stampede lock │
    │ • Pub/Sub sub   │    │ • Pub/Sub sub   │    │ • Pub/Sub sub   │
    └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    │
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        REDIS CLUSTER (L2 Cache)                      │
    │                                                                      │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
    │  │   Master 1      │  │   Master 2      │  │   Master 3      │      │
    │  │  Slots 0-5460   │  │ Slots 5461-10922│  │Slots 10923-16383│      │
    │  │                 │  │                 │  │                 │      │
    │  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │      │
    │  │  │ Replica 1 │  │  │  │ Replica 2 │  │  │  │ Replica 3 │  │      │
    │  │  │ (Standby) │  │  │  │ (Standby) │  │  │  │ (Standby) │  │      │
    │  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │      │
    │  └─────────────────┘  └─────────────────┘  └─────────────────┘      │
    │                                                                      │
    │  • Automatic sharding via hash slots                                 │
    │  • Automatic failover                                                │
    │  • Read replicas for scaling                                         │
    │  • Pub/Sub for invalidation                                          │
    └─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Pub/Sub
                                    ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │                    INVALIDATION BROADCAST                            │
    │                                                                      │
    │  Channel: invalidation_channel:{namespace}                           │
    │                                                                      │
    │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
    │  │Instance 1│◄───│  Redis   │───►│Instance 2│    │Instance N│       │
    │  │  (sub)   │    │ Pub/Sub  │    │  (sub)   │    │  (sub)   │       │
    │  └──────────┘    └──────────┘    └──────────┘    └──────────┘       │
    │                                                                      │
    │  On receive: Invalidate local cache + tag index                      │
    └─────────────────────────────────────────────────────────────────────┘
```

### Consistent Hashing Implementation

```python
import hashlib
import bisect
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import threading
import time
import redis
import json

@dataclass
class CacheNode:
    id: str
    host: str
    port: int
    weight: int = 1

class ConsistentHashRing:
    """
    Consistent hash ring for key distribution across Redis nodes.
    Uses virtual nodes for better distribution.
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, CacheNode] = {}
        self.sorted_keys: List[int] = []
        self._lock = threading.RLock()

    def _hash(self, key: str) -> int:
        """Generate consistent hash for a key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: CacheNode):
        """Add a node with virtual nodes to the ring."""
        with self._lock:
            for i in range(self.virtual_nodes * node.weight):
                virtual_key = f"{node.id}:{i}"
                hash_val = self._hash(virtual_key)
                self.ring[hash_val] = node
                bisect.insort(self.sorted_keys, hash_val)

    def remove_node(self, node: CacheNode):
        """Remove a node and its virtual nodes from the ring."""
        with self._lock:
            for i in range(self.virtual_nodes * node.weight):
                virtual_key = f"{node.id}:{i}"
                hash_val = self._hash(virtual_key)
                if hash_val in self.ring:
                    del self.ring[hash_val]
                    self.sorted_keys.remove(hash_val)

    def get_node(self, key: str) -> Optional[CacheNode]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_val = self._hash(key)

        with self._lock:
            idx = bisect.bisect(self.sorted_keys, hash_val)
            if idx == len(self.sorted_keys):
                idx = 0
            return self.ring[self.sorted_keys[idx]]


class LocalCache:
    """
    L1 local in-memory cache with LRU eviction.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_order: List[str] = []
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            return None

    def set(self, key: str, value: Any):
        with self._lock:
            if key in self.cache:
                self.access_order.remove(key)
            elif len(self.cache) >= self.max_size:
                # Evict least recently used
                lru_key = self.access_order.pop(0)
                del self.cache[lru_key]

            self.cache[key] = value
            self.access_order.append(key)

    def invalidate(self, key: str):
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                self.access_order.remove(key)

    def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching glob pattern."""
        import fnmatch
        with self._lock:
            keys_to_remove = [k for k in self.cache if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_remove:
                del self.cache[key]
                self.access_order.remove(key)


class DistributedCacheL6:
    """
    L6 Distributed Cache with:
    - Two-tier caching (local + Redis)
    - Consistent hashing
    - Cache stampede prevention
    - Pub/Sub invalidation
    - Write-through/write-behind policies
    """

    def __init__(
        self,
        redis_cluster: redis.RedisCluster,
        hash_ring: ConsistentHashRing,
        local_cache: LocalCache,
        namespace: str
    ):
        self.redis = redis_cluster
        self.hash_ring = hash_ring
        self.local_cache = local_cache
        self.namespace = namespace
        self._pubsub = None
        self._setup_invalidation_listener()

    def _setup_invalidation_listener(self):
        """Subscribe to invalidation channel."""
        self._pubsub = self.redis.pubsub()
        channel = f"invalidation_channel:{self.namespace}"
        self._pubsub.subscribe(**{channel: self._handle_invalidation})
        # Run in background thread
        self._pubsub.run_in_thread(sleep_time=0.01)

    def _handle_invalidation(self, message):
        """Handle invalidation messages from other instances."""
        if message["type"] != "message":
            return

        data = json.loads(message["data"])
        inv_type = data["type"]
        target = data["target"]

        if inv_type == "key":
            self.local_cache.invalidate(f"{self.namespace}:{target}")
        elif inv_type == "pattern":
            self.local_cache.invalidate_pattern(f"{self.namespace}:{target}")
        elif inv_type == "tag":
            # Get all keys with this tag and invalidate
            tag_key = f"cache_tags:{self.namespace}:{target}"
            keys = self.redis.smembers(tag_key)
            for key in keys:
                self.local_cache.invalidate(f"{self.namespace}:{key.decode()}")

    def get(
        self,
        key: str,
        consistency: str = "eventual",
        refresh_ttl: bool = False
    ) -> Optional[Dict]:
        """
        Get value with two-tier lookup.

        1. Check local cache (L1)
        2. Check Redis cluster (L2)
        3. Return with source metadata
        """
        full_key = f"cache:{self.namespace}:{key}"

        # L1: Local cache
        local_value = self.local_cache.get(full_key)
        if local_value and consistency == "eventual":
            return {
                "value": local_value["value"],
                "metadata": {
                    "source": "local",
                    "version": local_value.get("version", 1),
                    "ttl_remaining": local_value.get("ttl_remaining")
                }
            }

        # L2: Redis cluster
        redis_value = self.redis.get(full_key)

        if redis_value is None:
            return None

        data = json.loads(redis_value)
        ttl = self.redis.ttl(full_key)

        # Refresh TTL if requested
        if refresh_ttl and ttl > 0:
            self.redis.expire(full_key, ttl)

        # Update local cache
        self.local_cache.set(full_key, {
            "value": data["value"],
            "version": data.get("version", 1),
            "ttl_remaining": ttl
        })

        return {
            "value": data["value"],
            "metadata": {
                "source": "redis",
                "version": data.get("version", 1),
                "ttl_remaining": ttl
            }
        }

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tags: List[str] = None,
        version: int = None
    ) -> Dict:
        """
        Set value with write-through to Redis and local cache.

        Supports:
        - Optimistic locking with version
        - Tag-based grouping for bulk invalidation
        """
        full_key = f"cache:{self.namespace}:{key}"

        # Optimistic locking check
        if version is not None:
            current = self.redis.get(full_key)
            if current:
                current_data = json.loads(current)
                if current_data.get("version", 0) != version:
                    return {
                        "success": False,
                        "error": "version_conflict",
                        "current_version": current_data.get("version")
                    }

        # Determine new version
        new_version = (version or 0) + 1

        # Prepare data
        data = {
            "value": value,
            "version": new_version,
            "created_at": time.time()
        }

        # Write to Redis
        pipe = self.redis.pipeline()
        pipe.setex(full_key, ttl, json.dumps(data))

        # Handle tags
        if tags:
            for tag in tags:
                tag_key = f"cache_tags:{self.namespace}:{tag}"
                pipe.sadd(tag_key, key)
                pipe.expire(tag_key, ttl)

        # Track for hot keys
        pipe.zincrby(f"hot_keys:{self.namespace}", 1, key)

        pipe.execute()

        # Update local cache
        self.local_cache.set(full_key, {
            "value": value,
            "version": new_version,
            "ttl_remaining": ttl
        })

        return {
            "success": True,
            "version": new_version
        }

    def delete(self, key: str, broadcast: bool = True) -> Dict:
        """
        Delete key and optionally broadcast invalidation.
        """
        full_key = f"cache:{self.namespace}:{key}"

        # Delete from Redis
        deleted = self.redis.delete(full_key)

        # Invalidate local cache
        self.local_cache.invalidate(full_key)

        # Broadcast invalidation
        if broadcast:
            self._broadcast_invalidation("key", key)

        return {
            "success": True,
            "deleted": deleted > 0,
            "invalidation_sent": broadcast
        }

    def invalidate_by_tag(self, tag: str) -> Dict:
        """
        Invalidate all keys with a specific tag.
        """
        tag_key = f"cache_tags:{self.namespace}:{tag}"

        # Get all keys with this tag
        keys = self.redis.smembers(tag_key)

        # Delete all keys
        if keys:
            full_keys = [f"cache:{self.namespace}:{k.decode()}" for k in keys]
            self.redis.delete(*full_keys)

        # Delete tag index
        self.redis.delete(tag_key)

        # Broadcast invalidation
        self._broadcast_invalidation("tag", tag)

        return {
            "invalidated": len(keys),
            "tag": tag
        }

    def _broadcast_invalidation(self, inv_type: str, target: str):
        """Broadcast invalidation to all instances via Pub/Sub."""
        channel = f"invalidation_channel:{self.namespace}"
        message = json.dumps({
            "type": inv_type,
            "target": target,
            "timestamp": time.time()
        })
        self.redis.publish(channel, message)

    def get_with_stampede_protection(
        self,
        key: str,
        fetch_func: callable,
        ttl: int = 3600,
        lock_timeout: int = 30
    ) -> Dict:
        """
        Get with cache stampede protection using distributed lock.

        If cache miss, only one instance fetches from source.
        Others wait for the result.
        """
        full_key = f"cache:{self.namespace}:{key}"
        lock_key = f"cache_lock:{self.namespace}:{key}"

        # Try to get from cache
        result = self.get(key)
        if result:
            return result

        # Cache miss - try to acquire lock
        lock_acquired = self.redis.set(
            lock_key,
            "locked",
            ex=lock_timeout,
            nx=True
        )

        if lock_acquired:
            try:
                # We got the lock - fetch from source
                value = fetch_func()
                self.set(key, value, ttl=ttl)
                return {
                    "value": value,
                    "metadata": {"source": "fetched"}
                }
            finally:
                self.redis.delete(lock_key)
        else:
            # Another instance is fetching - wait and retry
            for _ in range(lock_timeout * 10):  # Check every 100ms
                time.sleep(0.1)
                result = self.get(key)
                if result:
                    return result

            # Timeout - fetch ourselves
            value = fetch_func()
            self.set(key, value, ttl=ttl)
            return {
                "value": value,
                "metadata": {"source": "fetched_after_timeout"}
            }
```

### Request Flow

**Read with Stampede Protection:**
1. Client requests key
2. Check local cache (L1) - if hit, return
3. Check Redis cluster (L2) - if hit, update L1 and return
4. Cache miss - attempt to acquire distributed lock
5. If lock acquired: fetch from source, cache, release lock
6. If lock not acquired: wait and poll for result
7. Return value with source metadata

**Write with Invalidation:**
1. Client writes value with optional tags
2. Write to Redis with version and TTL
3. Update tag indexes
4. Update local cache
5. Broadcast invalidation via Pub/Sub
6. Other instances receive and invalidate local caches

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | L1 cache hit | Get hot key | Source=local, < 1ms |
| F-02 | L2 cache hit | Get warm key | Source=redis, L1 updated |
| F-03 | Cache miss | Get non-existent | 404, miss counted |
| F-04 | Version conflict | SET with old version | 409, current version returned |
| F-05 | Tag association | SET with tags | Tags indexed correctly |
| F-06 | Tag invalidation | Invalidate by tag | All tagged keys deleted |
| F-07 | Pub/Sub invalidation | Delete on node 1 | Node 2 L1 cache invalidated |
| F-08 | Stampede lock | 100 concurrent misses | Only 1 fetch executed |
| F-09 | Consistent hash | Key routing | Same key always hits same shard |
| F-10 | Node removal | Remove node from ring | Keys redistributed correctly |
| F-11 | Write-through | SET operation | Both Redis and L1 updated |
| F-12 | TTL refresh | GET with refresh_ttl | TTL extended |
| F-13 | Pattern invalidation | Invalidate user_* | All matching keys deleted |
| F-14 | Hot key tracking | Access patterns | Hot keys identified |
| F-15 | Cluster health | Health check | All nodes status returned |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | L1 hit latency | Local cache read | < 100μs p99 |
| P-02 | L2 hit latency | Redis read | < 2ms p99 |
| P-03 | Write latency | SET with tags | < 5ms p99 |
| P-04 | Invalidation propagation | Pub/Sub delay | < 50ms p99 |
| P-05 | Stampede handling | 1000 concurrent | Only 1 source fetch |
| P-06 | Tag invalidation | 10K keys with tag | < 500ms |
| P-07 | Throughput L1 | Local cache ops | > 500K RPS |
| P-08 | Throughput L2 | Redis ops | > 100K RPS |
| P-09 | Hash ring lookup | Key to node | < 10μs |
| P-10 | Cluster rebalance | Add/remove node | < 5s |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Master failover | Kill Redis master | Replica promoted, < 5s |
| C-02 | Node partition | Network split | Cluster continues serving |
| C-03 | Pub/Sub failure | Kill Pub/Sub | Eventual consistency via TTL |
| C-04 | L1 overflow | Exceed max size | LRU eviction, no crash |
| C-05 | Stampede timeout | Fetch takes 60s | Other instances timeout, fetch |
| C-06 | Version storm | Rapid updates | Version increments correctly |
| C-07 | Tag explosion | 100K keys per tag | Invalidation completes |
| C-08 | Hash ring churn | Rapid node add/remove | Keys remain accessible |

---

## Capacity Estimates

- **Total keys**: 10M
- **Average value size**: 2KB
- **Redis memory**: ~25GB per master (with overhead)
- **Local cache**: 1K entries × N instances
- **Read QPS**: 200K (50% L1, 50% L2)
- **Write QPS**: 20K
- **Invalidation events**: 5K/s
- **Hit rate target**: > 95%
