# Distributed Cache System Design

## Problem Overview

Design a distributed caching system like Redis or Memcached that supports 1 million operations per second with 100GB of cached data.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
                              ┌─────────────────────────────────────┐
                              │          Client Layer               │
                              │  ┌─────────┐ ┌─────────┐ ┌─────────┐│
                              │  │ Client  │ │ Client  │ │ Client  ││
                              │  │   SDK   │ │   SDK   │ │   SDK   ││
                              │  └────┬────┘ └────┬────┘ └────┬────┘│
                              └───────┼───────────┼───────────┼─────┘
                                      │           │           │
                 ┌────────────────────┼───────────┼───────────┼────────────────────┐
                 │                    ▼           ▼           ▼                    │
                 │              ┌─────────────────────────────────┐                │
                 │              │     Consistent Hash Router      │                │
                 │              │  (Client-side or Proxy Layer)   │                │
                 │              └──────────────┬──────────────────┘                │
                 │                             │                                    │
                 │    ┌────────────────────────┼────────────────────────┐          │
                 │    │                        │                        │          │
                 │    ▼                        ▼                        ▼          │
                 │ ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
                 │ │ Cache Node 1 │     │ Cache Node 2 │     │ Cache Node N │     │
                 │ │ ┌──────────┐ │     │ ┌──────────┐ │     │ ┌──────────┐ │     │
                 │ │ │  Memory  │ │     │ │  Memory  │ │     │ │  Memory  │ │     │
                 │ │ │  (LRU)   │ │     │ │  (LRU)   │ │     │ │  (LRU)   │ │     │
                 │ │ └──────────┘ │     │ └──────────┘ │     │ └──────────┘ │     │
                 │ │ ┌──────────┐ │     │ ┌──────────┐ │     │ ┌──────────┐ │     │
                 │ │ │ Replica  │◀┼─────┼▶│ Replica  │◀┼─────┼▶│ Replica  │ │     │
                 │ │ │  Sync    │ │     │ │  Sync    │ │     │ │  Sync    │ │     │
                 │ │ └──────────┘ │     │ └──────────┘ │     │ └──────────┘ │     │
                 │ └──────────────┘     └──────────────┘     └──────────────┘     │
                 │                                                                  │
                 │                    Cache Cluster                                 │
                 └──────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Data Structures

```python
from dataclasses import dataclass
from typing import Optional, Any, Dict
from collections import OrderedDict
import threading
import time
import hashlib

@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    key: str
    value: bytes
    ttl: Optional[int]  # Seconds, None = no expiry
    created_at: float
    accessed_at: float
    version: int
    size_bytes: int

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class LRUCache:
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size_bytes: int):
        self.max_size = max_size_bytes
        self.current_size = 0
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        self.stats = CacheStats()

    def get(self, key: str) -> Optional[bytes]:
        with self.lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None

            entry = self.cache[key]

            # Check expiration
            if entry.is_expired():
                self._delete_entry(key)
                self.stats.misses += 1
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.accessed_at = time.time()
            self.stats.hits += 1

            return entry.value

    def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        with self.lock:
            size = len(key) + len(value) + 100  # Entry overhead

            # Remove existing entry if present
            if key in self.cache:
                self._delete_entry(key)

            # Evict if necessary
            while self.current_size + size > self.max_size and self.cache:
                self._evict_oldest()

            # Check if single entry is too large
            if size > self.max_size:
                return False

            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                created_at=time.time(),
                accessed_at=time.time(),
                version=1,
                size_bytes=size
            )

            self.cache[key] = entry
            self.current_size += size
            return True

    def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                self._delete_entry(key)
                return True
            return False

    def _delete_entry(self, key: str):
        entry = self.cache.pop(key)
        self.current_size -= entry.size_bytes

    def _evict_oldest(self):
        key, entry = self.cache.popitem(last=False)
        self.current_size -= entry.size_bytes
        self.stats.evictions += 1


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

#### 2. Consistent Hashing

```python
import bisect
from typing import List, Tuple

class ConsistentHashRing:
    """
    Consistent hash ring for distributing keys across nodes.
    Uses virtual nodes for better distribution.
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring: List[Tuple[int, str]] = []  # (hash, node_id)
        self.nodes: Dict[str, str] = {}  # node_id -> address

    def _hash(self, key: str) -> int:
        """Generate 32-bit hash for key."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)

    def add_node(self, node_id: str, address: str):
        """Add a node with virtual nodes to the ring."""
        self.nodes[node_id] = address

        for i in range(self.virtual_nodes):
            vnode_key = f"{node_id}:{i}"
            hash_val = self._hash(vnode_key)
            bisect.insort(self.ring, (hash_val, node_id))

    def remove_node(self, node_id: str):
        """Remove a node and its virtual nodes from the ring."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.ring = [(h, n) for h, n in self.ring if n != node_id]

    def get_node(self, key: str) -> Optional[str]:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_val = self._hash(key)
        idx = bisect.bisect_right(self.ring, (hash_val, ""))

        if idx == len(self.ring):
            idx = 0

        return self.ring[idx][1]

    def get_nodes(self, key: str, count: int = 3) -> List[str]:
        """Get N nodes for replication (primary + replicas)."""
        if not self.ring or count > len(self.nodes):
            return list(self.nodes.keys())[:count]

        hash_val = self._hash(key)
        idx = bisect.bisect_right(self.ring, (hash_val, ""))

        nodes = []
        seen = set()

        for i in range(len(self.ring)):
            node_id = self.ring[(idx + i) % len(self.ring)][1]
            if node_id not in seen:
                nodes.append(node_id)
                seen.add(node_id)
                if len(nodes) == count:
                    break

        return nodes
```

#### 3. Cache Protocol

```python
from enum import Enum
from typing import Union

class CacheCommand(Enum):
    GET = "GET"
    SET = "SET"
    DELETE = "DELETE"
    INCR = "INCR"
    DECR = "DECR"
    EXPIRE = "EXPIRE"
    TTL = "TTL"
    KEYS = "KEYS"
    MGET = "MGET"
    MSET = "MSET"


class CacheProtocol:
    """
    Simple binary protocol for cache operations.
    Format: [4-byte length][command][key length][key][value length][value][ttl]
    """

    @staticmethod
    def encode_get(key: str) -> bytes:
        key_bytes = key.encode('utf-8')
        return struct.pack('>B H', CacheCommand.GET.value, len(key_bytes)) + key_bytes

    @staticmethod
    def encode_set(key: str, value: bytes, ttl: Optional[int] = None) -> bytes:
        key_bytes = key.encode('utf-8')
        ttl_val = ttl if ttl else 0
        return (
            struct.pack('>B H', CacheCommand.SET.value, len(key_bytes)) +
            key_bytes +
            struct.pack('>I', len(value)) +
            value +
            struct.pack('>I', ttl_val)
        )

    @staticmethod
    def decode_response(data: bytes) -> Tuple[bool, Optional[bytes]]:
        success = struct.unpack('>?', data[0:1])[0]
        if len(data) > 1:
            value_len = struct.unpack('>I', data[1:5])[0]
            value = data[5:5+value_len]
            return success, value
        return success, None
```

#### 4. Replication

```python
class ReplicationManager:
    """
    Manages data replication across cache nodes.
    Uses async replication with configurable consistency.
    """

    def __init__(
        self,
        node_id: str,
        cluster: ConsistentHashRing,
        replication_factor: int = 3
    ):
        self.node_id = node_id
        self.cluster = cluster
        self.replication_factor = replication_factor
        self.pending_replications: Queue = Queue()
        self._start_replication_worker()

    async def replicate_write(
        self,
        key: str,
        value: bytes,
        ttl: Optional[int],
        sync: bool = False
    ) -> int:
        """
        Replicate a write to replica nodes.
        Returns number of successful replications.
        """
        replica_nodes = self.cluster.get_nodes(key, self.replication_factor)
        replica_nodes = [n for n in replica_nodes if n != self.node_id]

        if sync:
            # Synchronous replication (write concern)
            tasks = [
                self._replicate_to_node(node, key, value, ttl)
                for node in replica_nodes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return sum(1 for r in results if r is True)
        else:
            # Async replication
            for node in replica_nodes:
                self.pending_replications.put((node, key, value, ttl))
            return len(replica_nodes)

    async def _replicate_to_node(
        self,
        node_id: str,
        key: str,
        value: bytes,
        ttl: Optional[int]
    ) -> bool:
        """Send replication request to a single node."""
        try:
            address = self.cluster.nodes[node_id]
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{address}/replicate",
                    data=CacheProtocol.encode_set(key, value, ttl),
                    timeout=aiohttp.ClientTimeout(total=1)
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Replication to {node_id} failed: {e}")
            return False
```

### API Design

```yaml
openapi: 3.0.0
paths:
  /cache/{key}:
    get:
      summary: Get cached value
      parameters:
        - name: key
          in: path
          required: true
          schema: { type: string }
      responses:
        200:
          content:
            application/octet-stream:
              schema: { type: string, format: binary }
        404:
          description: Key not found

    put:
      summary: Set cached value
      parameters:
        - name: key
          in: path
          required: true
          schema: { type: string }
        - name: ttl
          in: query
          schema: { type: integer }
        - name: nx
          in: query
          description: Only set if not exists
          schema: { type: boolean }
        - name: xx
          in: query
          description: Only set if exists
          schema: { type: boolean }
      requestBody:
        content:
          application/octet-stream:
            schema: { type: string, format: binary }
      responses:
        200:
          description: Value set successfully

    delete:
      summary: Delete cached value
      parameters:
        - name: key
          in: path
          required: true
      responses:
        200:
          description: Key deleted
        404:
          description: Key not found

  /cache/_mget:
    post:
      summary: Get multiple keys
      requestBody:
        content:
          application/json:
            schema:
              type: array
              items: { type: string }
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                additionalProperties: { type: string }

  /cache/{key}/_incr:
    post:
      summary: Increment numeric value
      parameters:
        - name: key
          in: path
          required: true
        - name: delta
          in: query
          schema: { type: integer, default: 1 }
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  value: { type: integer }

  /cluster/status:
    get:
      summary: Get cluster status
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  nodes: { type: array }
                  total_keys: { type: integer }
                  memory_used: { type: integer }
                  hit_rate: { type: number }
```

---

## Platform Deployment

### Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     GCP Deployment                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Cloud Load Balancer                   │ │
│  └────────────────────────┬───────────────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────┼───────────────────────────────┐ │
│  │                        ▼                               │ │
│  │    ┌───────────┐ ┌───────────┐ ┌───────────┐          │ │
│  │    │ Cache     │ │ Cache     │ │ Cache     │          │ │
│  │    │ Node 1    │ │ Node 2    │ │ Node 3    │          │ │
│  │    │ (32GB)    │ │ (32GB)    │ │ (32GB)    │          │ │
│  │    └─────┬─────┘ └─────┬─────┘ └─────┬─────┘          │ │
│  │          │             │             │                 │ │
│  │    ┌─────▼─────────────▼─────────────▼─────┐          │ │
│  │    │         Internal VPC Network          │          │ │
│  │    └───────────────────────────────────────┘          │ │
│  │                                                        │ │
│  │         GKE Cluster (High-Memory Nodes)                │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Infrastructure as Code

```hcl
# GKE cluster for cache nodes
resource "google_container_cluster" "cache_cluster" {
  name     = "distributed-cache-${var.submission_id}"
  location = "us-central1"

  node_pool {
    name       = "cache-pool"
    node_count = var.node_count

    node_config {
      machine_type = "n2-highmem-8"  # 8 vCPU, 64GB RAM
      disk_size_gb = 100
      disk_type    = "pd-ssd"

      labels = {
        role = "cache-node"
      }
    }
  }
}

# Kubernetes StatefulSet for cache nodes
resource "kubernetes_stateful_set" "cache_nodes" {
  metadata {
    name = "cache-node"
  }

  spec {
    replicas     = var.node_count
    service_name = "cache"

    template {
      spec {
        container {
          name  = "cache"
          image = "gcr.io/${var.project}/distributed-cache:${var.version}"

          resources {
            limits = {
              memory = "60Gi"
              cpu    = "7"
            }
            requests = {
              memory = "60Gi"
              cpu    = "6"
            }
          }

          env {
            name  = "MAX_MEMORY_MB"
            value = "55000"  # 55GB per node
          }

          env {
            name = "NODE_ID"
            value_from {
              field_ref {
                field_path = "metadata.name"
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Realistic Testing

### 1. Functional Tests

```python
import pytest
import asyncio
import random
import string

class TestDistributedCache:
    """Functional tests for distributed cache."""

    async def test_basic_get_set(self, cache_client):
        """Test basic get/set operations."""
        key = f"test-{uuid.uuid4()}"
        value = b"hello world"

        # Set value
        await cache_client.set(key, value)

        # Get value
        result = await cache_client.get(key)
        assert result == value

    async def test_ttl_expiration(self, cache_client):
        """Test TTL expiration."""
        key = f"ttl-test-{uuid.uuid4()}"
        value = b"expires soon"

        await cache_client.set(key, value, ttl=2)

        # Should exist immediately
        assert await cache_client.get(key) == value

        # Should expire after TTL
        await asyncio.sleep(3)
        assert await cache_client.get(key) is None

    async def test_large_values(self, cache_client):
        """Test storing large values."""
        key = f"large-{uuid.uuid4()}"
        value = b"x" * (10 * 1024 * 1024)  # 10MB

        await cache_client.set(key, value)
        result = await cache_client.get(key)
        assert result == value

    async def test_concurrent_writes(self, cache_client):
        """Test concurrent write operations."""
        key = f"concurrent-{uuid.uuid4()}"

        async def write(i):
            await cache_client.set(key, f"value-{i}".encode())

        await asyncio.gather(*[write(i) for i in range(100)])

        # Should have some value
        result = await cache_client.get(key)
        assert result is not None

    async def test_atomic_increment(self, cache_client):
        """Test atomic increment operation."""
        key = f"counter-{uuid.uuid4()}"
        await cache_client.set(key, b"0")

        # Concurrent increments
        async def incr():
            return await cache_client.incr(key)

        results = await asyncio.gather(*[incr() for _ in range(100)])

        # All increments should succeed
        final = await cache_client.get(key)
        assert int(final) == 100

    async def test_eviction_under_memory_pressure(self, cache_client):
        """Test LRU eviction when memory is full."""
        # Fill cache with data
        base_key = f"evict-test-{uuid.uuid4()}"
        large_value = b"x" * (1024 * 1024)  # 1MB each

        # Write enough to trigger eviction
        for i in range(1000):
            await cache_client.set(f"{base_key}-{i}", large_value)

        # Old keys should be evicted
        old_key = f"{base_key}-0"
        result = await cache_client.get(old_key)
        # May or may not exist depending on cache size

        # New keys should exist
        new_key = f"{base_key}-999"
        assert await cache_client.get(new_key) is not None
```

### 2. Performance Testing

```python
# locustfile.py for cache performance testing
from locust import HttpUser, task, between
import random
import string

class CacheUser(HttpUser):
    wait_time = between(0.001, 0.01)  # Very fast requests

    def on_start(self):
        # Pre-populate some keys
        self.keys = []
        for i in range(1000):
            key = f"perf-test-{i}"
            value = ''.join(random.choices(string.ascii_letters, k=1000))
            self.client.put(
                f"/cache/{key}",
                data=value.encode(),
                name="/cache/[key] PUT"
            )
            self.keys.append(key)

    @task(80)
    def cache_get(self):
        """80% reads."""
        key = random.choice(self.keys)
        self.client.get(f"/cache/{key}", name="/cache/[key] GET")

    @task(15)
    def cache_set(self):
        """15% writes."""
        key = f"write-{random.randint(0, 10000)}"
        value = ''.join(random.choices(string.ascii_letters, k=1000))
        self.client.put(
            f"/cache/{key}",
            data=value.encode(),
            name="/cache/[key] PUT"
        )

    @task(5)
    def cache_delete(self):
        """5% deletes."""
        key = f"write-{random.randint(0, 10000)}"
        self.client.delete(f"/cache/{key}", name="/cache/[key] DELETE")
```

**Performance Targets:**
| Metric | Target |
|--------|--------|
| GET Latency (p50) | < 1ms |
| GET Latency (p99) | < 5ms |
| SET Latency (p50) | < 2ms |
| SET Latency (p99) | < 10ms |
| Throughput | > 100K ops/sec |
| Memory Efficiency | > 90% |

### 3. Cluster Tests

```python
class TestClusterBehavior:
    """Test distributed cluster behavior."""

    async def test_key_distribution(self, cache_cluster):
        """Verify even key distribution across nodes."""
        # Write 10,000 keys
        for i in range(10000):
            await cache_cluster.set(f"dist-test-{i}", b"value")

        # Check distribution across nodes
        stats = await cache_cluster.get_cluster_stats()
        key_counts = [node["key_count"] for node in stats["nodes"]]

        # Standard deviation should be low (even distribution)
        avg = sum(key_counts) / len(key_counts)
        variance = sum((x - avg) ** 2 for x in key_counts) / len(key_counts)
        std_dev = variance ** 0.5

        # Coefficient of variation should be < 10%
        cv = std_dev / avg
        assert cv < 0.1

    async def test_node_failure_recovery(self, cache_cluster):
        """Test behavior when a node fails."""
        # Write some data
        for i in range(1000):
            await cache_cluster.set(f"failover-{i}", f"value-{i}".encode())

        # Kill one node
        await cache_cluster.stop_node("cache-node-1")

        # Read data (should work via replicas)
        success = 0
        for i in range(1000):
            try:
                result = await cache_cluster.get(f"failover-{i}")
                if result:
                    success += 1
            except:
                pass

        # Should recover most data from replicas
        assert success > 900  # > 90% available

    async def test_node_addition(self, cache_cluster):
        """Test adding a new node to the cluster."""
        # Get initial key counts
        initial_stats = await cache_cluster.get_cluster_stats()
        initial_keys = sum(n["key_count"] for n in initial_stats["nodes"])

        # Add a new node
        await cache_cluster.add_node("cache-node-4")

        # Wait for rebalancing
        await asyncio.sleep(30)

        # Keys should be redistributed
        final_stats = await cache_cluster.get_cluster_stats()
        new_node = next(n for n in final_stats["nodes"] if n["id"] == "cache-node-4")

        # New node should have received some keys
        assert new_node["key_count"] > 0
```

### 4. Chaos Engineering Tests

```python
class CacheChaosTests:
    """Chaos engineering tests for cache resilience."""

    async def test_network_partition(self):
        """Test behavior during network partition."""
        # Create partition between nodes
        await platform_api.create_network_partition(
            group1=["cache-node-0", "cache-node-1"],
            group2=["cache-node-2"]
        )

        # Both partitions should continue serving requests
        # (with potential stale data on minority partition)
        responses = []
        for i in range(100):
            try:
                resp = await cache_client.get(f"partition-test-{i}")
                responses.append(resp)
            except:
                responses.append(None)

        # Should have some successful responses
        success_rate = sum(1 for r in responses if r) / len(responses)
        assert success_rate > 0.5

        # Heal partition
        await platform_api.heal_network_partition()

    async def test_memory_pressure(self):
        """Test behavior under memory pressure."""
        # Fill cache beyond capacity
        large_value = b"x" * (100 * 1024 * 1024)  # 100MB each

        for i in range(100):
            try:
                await cache_client.set(f"memory-test-{i}", large_value)
            except:
                pass

        # Cache should handle gracefully (eviction)
        stats = await cache_client.get_stats()
        assert stats["evictions"] > 0

        # Should still be responsive
        await cache_client.set("responsive-test", b"still works")
        assert await cache_client.get("responsive-test") == b"still works"

    async def test_slow_network(self):
        """Test behavior with degraded network."""
        # Inject latency
        await platform_api.inject_latency(
            between=["client", "cache-cluster"],
            latency_ms=50,
            duration_seconds=60
        )

        latencies = []
        for i in range(100):
            start = time.time()
            await cache_client.get(f"slow-test-{i}")
            latencies.append(time.time() - start)

        # Latency should increase but not timeout
        p99 = sorted(latencies)[98]
        assert p99 < 1.0  # Less than 1 second
```

### 5. Benchmarking Commands

```bash
# 1. Redis benchmark (if compatible protocol)
redis-benchmark -h cache-cluster.run.app -p 443 \
  -n 100000 -c 50 -t get,set --csv

# 2. Custom benchmark with hey
# Write test
hey -n 10000 -c 100 -m PUT \
  -D "test-value-data" \
  "https://cache-cluster.run.app/cache/benchmark-key"

# Read test
hey -n 100000 -c 200 \
  "https://cache-cluster.run.app/cache/benchmark-key"

# 3. Check cluster status
curl https://cache-cluster.run.app/cluster/status | jq .

# 4. Monitor memory usage
watch -n 1 'curl -s https://cache-cluster.run.app/cluster/status | jq ".nodes[].memory_used_mb"'
```

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| GET Latency (p50) | < 1ms | Performance test |
| GET Latency (p99) | < 5ms | Performance test |
| Throughput | > 100K ops/sec | Load test |
| Memory Efficiency | > 90% | Stress test |
| Availability (node failure) | > 99% | Chaos test |
| Key Distribution CV | < 10% | Cluster test |
| Replication Lag | < 10ms | Async replication test |

---

## Common Pitfalls

1. **No consistent hashing:** Random distribution causes poor cache locality
2. **Single replica:** No fault tolerance
3. **No eviction policy:** Memory exhaustion
4. **Synchronous replication:** High write latency
5. **No TTL on entries:** Stale data accumulation
6. **Missing connection pooling:** Connection overhead
7. **No hot key handling:** Single key overwhelms one node
