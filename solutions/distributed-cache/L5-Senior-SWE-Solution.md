# Distributed Cache - L5 (Senior Software Engineer) Solution

## Level Requirements

**Target Role:** Senior Software Engineer (L5)
**Focus:** Core caching functionality with basic distributed patterns

### What's Expected at L5

- Implementation of basic caching operations (GET, SET, DELETE)
- Simple hash-based key distribution
- Redis or Memcached as underlying storage
- TTL-based expiration
- Basic cache-aside pattern implementation
- Understanding of cache hit/miss metrics

---

## Database Schema

```json
{
  "storage": "Redis",
  "data_structures": [
    {
      "name": "cache:{namespace}:{key}",
      "type": "STRING",
      "description": "Cached value with optional TTL",
      "ttl": "configurable per key",
      "example": {
        "key": "cache:users:user_123",
        "value": "{\"id\": 123, \"name\": \"John\", \"email\": \"john@example.com\"}",
        "ttl": 3600
      }
    },
    {
      "name": "cache_meta:{namespace}:{key}",
      "type": "HASH",
      "description": "Metadata for cache entries",
      "fields": {
        "created_at": "Unix timestamp",
        "access_count": "Number of reads",
        "last_accessed": "Last access timestamp",
        "size_bytes": "Size of cached value"
      }
    },
    {
      "name": "cache_stats:{namespace}",
      "type": "HASH",
      "description": "Namespace-level statistics",
      "fields": {
        "hits": "Cache hit count",
        "misses": "Cache miss count",
        "total_keys": "Number of cached keys",
        "total_bytes": "Total memory used"
      }
    }
  ],
  "persistence": {
    "type": "PostgreSQL",
    "purpose": "Configuration and audit logging",
    "tables": [
      {
        "name": "cache_namespaces",
        "columns": [
          {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
          {"name": "name", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
          {"name": "default_ttl", "type": "INTEGER", "constraints": "DEFAULT 3600"},
          {"name": "max_size_mb", "type": "INTEGER", "constraints": "DEFAULT 100"},
          {"name": "eviction_policy", "type": "VARCHAR(20)", "constraints": "DEFAULT 'LRU'"},
          {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
        ]
      },
      {
        "name": "cache_access_logs",
        "columns": [
          {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
          {"name": "namespace", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
          {"name": "key_pattern", "type": "VARCHAR(255)"},
          {"name": "operation", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
          {"name": "hit", "type": "BOOLEAN"},
          {"name": "latency_ms", "type": "FLOAT"},
          {"name": "timestamp", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
        ],
        "indexes": [
          {"columns": ["namespace", "timestamp"]}
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
      "method": "GET",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Get cached value",
      "responses": {
        "200": {
          "value": "any (JSON)",
          "metadata": {
            "ttl_remaining": 3500,
            "created_at": "2024-01-01T00:00:00Z"
          }
        },
        "404": {"error": "Key not found"},
        "400": {"error": "Invalid namespace"}
      },
      "headers_returned": {
        "X-Cache-Hit": "true",
        "X-Cache-TTL": "3500"
      }
    },
    {
      "method": "PUT",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Set cached value",
      "request_body": {
        "value": "any (required)",
        "ttl": "integer (optional, seconds)",
        "tags": "array of strings (optional)"
      },
      "responses": {
        "200": {"success": true, "key": "user_123"},
        "201": {"success": true, "key": "user_123", "created": true},
        "400": {"error": "Value too large"},
        "507": {"error": "Cache storage full"}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/cache/{namespace}/{key}",
      "description": "Delete cached value",
      "responses": {
        "200": {"success": true, "deleted": true},
        "404": {"error": "Key not found"}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/mget",
      "description": "Get multiple keys",
      "request_body": {
        "keys": ["key1", "key2", "key3"]
      },
      "responses": {
        "200": {
          "results": {
            "key1": {"value": "...", "found": true},
            "key2": {"value": null, "found": false},
            "key3": {"value": "...", "found": true}
          },
          "hits": 2,
          "misses": 1
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/cache/{namespace}/mset",
      "description": "Set multiple keys",
      "request_body": {
        "entries": [
          {"key": "key1", "value": "val1", "ttl": 3600},
          {"key": "key2", "value": "val2", "ttl": 7200}
        ]
      },
      "responses": {
        "200": {"success": true, "stored": 2}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/cache/{namespace}",
      "description": "Flush entire namespace",
      "query_params": {
        "pattern": "optional glob pattern (e.g., user_*)"
      },
      "responses": {
        "200": {"success": true, "deleted_count": 150}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/cache/{namespace}/stats",
      "description": "Get cache statistics",
      "responses": {
        "200": {
          "hits": 15000,
          "misses": 500,
          "hit_rate": 0.968,
          "total_keys": 1200,
          "memory_used_mb": 45.2,
          "evictions": 50
        }
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check",
      "responses": {
        "200": {
          "status": "healthy",
          "redis": "connected",
          "memory_usage": "45%"
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
                    Distributed Cache - L5 Architecture
    ══════════════════════════════════════════════════════════════════

    ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐
    │   Client    │────▶│    Nginx    │────▶│    Cache Service        │
    │  (App/API)  │     │  (Load      │     │    (Python/FastAPI)     │
    └─────────────┘     │   Balancer) │     └───────────┬─────────────┘
                        └─────────────┘                 │
                                                        │
                              ┌──────────────────────────┴─────────────┐
                              │                                        │
                              ▼                                        ▼
                    ┌─────────────────────┐              ┌─────────────────────┐
                    │       Redis         │              │    PostgreSQL       │
                    │   (Primary Cache)   │              │  (Config & Logs)    │
                    │                     │              │                     │
                    │ • Key-value store   │              │ • Namespace configs │
                    │ • TTL expiration    │              │ • Access logs       │
                    │ • LRU eviction      │              │ • Audit trail       │
                    └─────────────────────┘              └─────────────────────┘
```

### Cache-Aside Pattern Implementation

```python
import json
import time
from typing import Optional, Any, Dict
import redis
from dataclasses import dataclass

@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl: int
    access_count: int = 0

class DistributedCache:
    """
    L5 Distributed Cache implementation using Redis.

    Implements cache-aside pattern with TTL-based expiration.
    """

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl

    def get(self, namespace: str, key: str) -> Optional[Dict]:
        """
        Get value from cache.

        Returns:
            Dict with value and metadata, or None if not found
        """
        cache_key = f"cache:{namespace}:{key}"
        meta_key = f"cache_meta:{namespace}:{key}"
        stats_key = f"cache_stats:{namespace}"

        # Get value
        value = self.redis.get(cache_key)

        if value is None:
            # Cache miss
            self.redis.hincrby(stats_key, "misses", 1)
            return None

        # Cache hit
        self.redis.hincrby(stats_key, "hits", 1)

        # Update access metadata
        now = time.time()
        self.redis.hset(meta_key, mapping={
            "last_accessed": now,
            "access_count": self.redis.hincrby(meta_key, "access_count", 1)
        })

        # Get TTL remaining
        ttl_remaining = self.redis.ttl(cache_key)

        return {
            "value": json.loads(value),
            "metadata": {
                "ttl_remaining": ttl_remaining,
                "cache_hit": True
            }
        }

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> Dict:
        """
        Set value in cache.

        Args:
            namespace: Cache namespace for isolation
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time-to-live in seconds (optional)

        Returns:
            Dict with success status
        """
        cache_key = f"cache:{namespace}:{key}"
        meta_key = f"cache_meta:{namespace}:{key}"
        stats_key = f"cache_stats:{namespace}"

        ttl = ttl or self.default_ttl
        serialized = json.dumps(value)
        size_bytes = len(serialized.encode('utf-8'))

        # Check if key exists (for created flag)
        exists = self.redis.exists(cache_key)

        # Set value with TTL
        self.redis.setex(cache_key, ttl, serialized)

        # Set metadata
        now = time.time()
        self.redis.hset(meta_key, mapping={
            "created_at": now,
            "size_bytes": size_bytes,
            "access_count": 0,
            "last_accessed": now
        })
        self.redis.expire(meta_key, ttl)

        # Update stats
        if not exists:
            self.redis.hincrby(stats_key, "total_keys", 1)
        self.redis.hincrby(stats_key, "total_bytes", size_bytes)

        return {
            "success": True,
            "key": key,
            "created": not exists
        }

    def delete(self, namespace: str, key: str) -> Dict:
        """
        Delete value from cache.

        Returns:
            Dict with success status and deleted flag
        """
        cache_key = f"cache:{namespace}:{key}"
        meta_key = f"cache_meta:{namespace}:{key}"
        stats_key = f"cache_stats:{namespace}"

        # Get size before deletion for stats
        meta = self.redis.hgetall(meta_key)
        size_bytes = int(meta.get(b"size_bytes", 0))

        # Delete key and metadata
        deleted = self.redis.delete(cache_key, meta_key)

        if deleted > 0:
            self.redis.hincrby(stats_key, "total_keys", -1)
            self.redis.hincrby(stats_key, "total_bytes", -size_bytes)

        return {
            "success": True,
            "deleted": deleted > 0
        }

    def mget(self, namespace: str, keys: list) -> Dict:
        """
        Get multiple keys at once.

        Returns:
            Dict with results for each key
        """
        cache_keys = [f"cache:{namespace}:{k}" for k in keys]
        stats_key = f"cache_stats:{namespace}"

        # Pipeline for efficiency
        pipe = self.redis.pipeline()
        for ck in cache_keys:
            pipe.get(ck)
        values = pipe.execute()

        results = {}
        hits = 0
        misses = 0

        for key, value in zip(keys, values):
            if value is not None:
                results[key] = {
                    "value": json.loads(value),
                    "found": True
                }
                hits += 1
            else:
                results[key] = {
                    "value": None,
                    "found": False
                }
                misses += 1

        # Update stats
        self.redis.hincrby(stats_key, "hits", hits)
        self.redis.hincrby(stats_key, "misses", misses)

        return {
            "results": results,
            "hits": hits,
            "misses": misses
        }

    def mset(self, namespace: str, entries: list) -> Dict:
        """
        Set multiple keys at once.

        Args:
            entries: List of dicts with key, value, and optional ttl

        Returns:
            Dict with success status and count
        """
        pipe = self.redis.pipeline()
        stats_key = f"cache_stats:{namespace}"

        for entry in entries:
            key = entry["key"]
            value = entry["value"]
            ttl = entry.get("ttl", self.default_ttl)

            cache_key = f"cache:{namespace}:{key}"
            serialized = json.dumps(value)

            pipe.setex(cache_key, ttl, serialized)

        pipe.execute()

        # Update stats
        self.redis.hincrby(stats_key, "total_keys", len(entries))

        return {
            "success": True,
            "stored": len(entries)
        }

    def flush_namespace(
        self,
        namespace: str,
        pattern: Optional[str] = None
    ) -> Dict:
        """
        Delete all keys in namespace or matching pattern.

        Returns:
            Dict with deleted count
        """
        if pattern:
            search_pattern = f"cache:{namespace}:{pattern}"
        else:
            search_pattern = f"cache:{namespace}:*"

        # Use SCAN to avoid blocking
        deleted_count = 0
        cursor = 0

        while True:
            cursor, keys = self.redis.scan(
                cursor=cursor,
                match=search_pattern,
                count=100
            )

            if keys:
                deleted_count += self.redis.delete(*keys)

            if cursor == 0:
                break

        return {
            "success": True,
            "deleted_count": deleted_count
        }

    def get_stats(self, namespace: str) -> Dict:
        """
        Get cache statistics for namespace.

        Returns:
            Dict with hit rate, memory usage, etc.
        """
        stats_key = f"cache_stats:{namespace}"
        stats = self.redis.hgetall(stats_key)

        hits = int(stats.get(b"hits", 0))
        misses = int(stats.get(b"misses", 0))
        total = hits + misses

        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": hits / total if total > 0 else 0,
            "total_keys": int(stats.get(b"total_keys", 0)),
            "memory_used_bytes": int(stats.get(b"total_bytes", 0))
        }
```

### Request Flow

**Cache Read (GET):**
1. Client requests value by namespace and key
2. Service checks Redis for cached value
3. If hit: Return value, update access stats
4. If miss: Return 404, increment miss counter
5. Client handles miss by fetching from source and caching

**Cache Write (SET):**
1. Client sends value with optional TTL
2. Service serializes value to JSON
3. Service stores in Redis with TTL
4. Service updates metadata and stats
5. Return success response

**Cache-Aside Pattern (Client-Side):**
```python
def get_user(user_id: str) -> User:
    # Try cache first
    cached = cache.get("users", user_id)
    if cached:
        return User(**cached["value"])

    # Cache miss - fetch from database
    user = db.query(User).filter(User.id == user_id).first()

    if user:
        # Store in cache for future requests
        cache.set("users", user_id, user.to_dict(), ttl=3600)

    return user
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Get existing key | GET cached value | 200, value returned |
| F-02 | Get missing key | GET non-existent key | 404, not found |
| F-03 | Set new key | PUT new value | 201, created=true |
| F-04 | Update existing key | PUT existing key | 200, created=false |
| F-05 | Delete key | DELETE cached key | 200, deleted=true |
| F-06 | Delete missing key | DELETE non-existent | 404, not found |
| F-07 | TTL expiration | GET after TTL | 404, key expired |
| F-08 | Custom TTL | SET with ttl=60 | Expires in 60 seconds |
| F-09 | Multi-get | MGET 5 keys | Mixed hits/misses |
| F-10 | Multi-set | MSET 5 entries | All stored |
| F-11 | Flush namespace | DELETE namespace | All keys deleted |
| F-12 | Pattern flush | DELETE with pattern | Matching keys deleted |
| F-13 | Stats accuracy | Check stats | Hit rate matches |
| F-14 | Large value | SET 1MB value | Success or size error |
| F-15 | JSON serialization | SET complex object | Serialized correctly |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | GET latency | Single key read | < 5ms p99 |
| P-02 | SET latency | Single key write | < 10ms p99 |
| P-03 | MGET latency | 100 keys | < 20ms p99 |
| P-04 | MSET latency | 100 entries | < 30ms p99 |
| P-05 | Throughput reads | Concurrent GETs | > 50,000 RPS |
| P-06 | Throughput writes | Concurrent SETs | > 20,000 RPS |
| P-07 | Memory efficiency | 1M keys | < 2GB Redis |
| P-08 | Connection pool | 1000 concurrent | No exhaustion |
| P-09 | Large value GET | 1MB value | < 50ms |
| P-10 | Pattern scan | 100K keys | < 5s full scan |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis down | Kill Redis | Error response, no crash |
| C-02 | Redis restart | Restart Redis | Auto-reconnect |
| C-03 | Memory full | Fill Redis memory | LRU eviction kicks in |
| C-04 | Network latency | Add 100ms delay | Timeout handling |
| C-05 | Connection storm | 10K connections | Queue or reject |
| C-06 | Slow queries | Long-running ops | Timeout, continue serving |

---

## Capacity Estimates

- **Keys**: 1M active
- **Average value size**: 1KB
- **Total memory**: ~1GB for values + overhead
- **Read QPS**: 50,000
- **Write QPS**: 5,000
- **Hit rate target**: > 90%
- **Latency budget**: < 10ms p99
