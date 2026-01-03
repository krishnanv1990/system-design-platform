# HNSW (Hierarchical Navigable Small World)

## Problem Overview

Implement the HNSW algorithm for approximate nearest neighbor search, building a hierarchical graph structure for efficient vector similarity search.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Algorithm Overview

HNSW builds a hierarchical graph structure where:
- Each layer is a proximity graph
- Higher layers have fewer nodes (skip-list like structure)
- Search starts from top layer and descends to find neighbors

**Key parameters:**
- `M`: Maximum number of connections per node
- `ef_construction`: Size of dynamic candidate list during construction
- `ef_search`: Size of dynamic candidate list during search

### Implementation

```python
import math
import random
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
import numpy as np

@dataclass
class HNSWNode:
    id: str
    vector: np.ndarray
    level: int  # Maximum level this node appears in
    neighbors: Dict[int, List[str]] = field(default_factory=dict)  # level -> neighbor ids

@dataclass
class SearchResult:
    id: str
    distance: float
    vector: np.ndarray
    metadata: Dict[str, str]

class HNSW:
    """Hierarchical Navigable Small World graph for ANN search."""

    def __init__(self, dim: int, M: int = 16, ef_construction: int = 200,
                 distance_type: str = "euclidean"):
        self.dim = dim
        self.M = M                          # Max neighbors per node
        self.M_max = M                      # Max neighbors for layers > 0
        self.M_max0 = 2 * M                 # Max neighbors for layer 0
        self.ef_construction = ef_construction
        self.ml = 1.0 / math.log(M)         # Level multiplier
        self.distance_type = distance_type

        self.nodes: Dict[str, HNSWNode] = {}
        self.entry_point: Optional[str] = None
        self.max_level = 0

    def _distance(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate distance between two vectors."""
        if self.distance_type == "euclidean":
            return np.linalg.norm(v1 - v2)
        elif self.distance_type == "cosine":
            return 1 - np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        elif self.distance_type == "inner_product":
            return -np.dot(v1, v2)
        else:
            raise ValueError(f"Unknown distance type: {self.distance_type}")

    def _random_level(self) -> int:
        """Generate random level for new node."""
        return int(-math.log(random.random()) * self.ml)

    def insert(self, id: str, vector: np.ndarray, metadata: Dict = None) -> int:
        """Insert a vector into the index."""
        vector = np.array(vector, dtype=np.float32)
        level = self._random_level()

        node = HNSWNode(
            id=id,
            vector=vector,
            level=level,
            neighbors={l: [] for l in range(level + 1)}
        )

        if self.entry_point is None:
            # First node
            self.entry_point = id
            self.max_level = level
            self.nodes[id] = node
            return level

        # Find entry point at top level
        current = self.entry_point
        current_node = self.nodes[current]

        # Traverse from top to node's level
        for lc in range(self.max_level, level, -1):
            current, _ = self._search_layer(
                vector, current, 1, lc
            )[0]

        # Insert at each level from level down to 0
        for lc in range(min(level, self.max_level), -1, -1):
            # Find ef_construction nearest neighbors
            neighbors = self._search_layer(
                vector, current, self.ef_construction, lc
            )

            # Select M best neighbors
            m = self.M_max0 if lc == 0 else self.M_max
            selected = self._select_neighbors(vector, neighbors, m)

            # Connect node to neighbors
            node.neighbors[lc] = [n for n, _ in selected]

            # Connect neighbors to node
            for neighbor_id, _ in selected:
                neighbor = self.nodes[neighbor_id]
                neighbor.neighbors[lc].append(id)

                # Shrink if too many connections
                max_neighbors = self.M_max0 if lc == 0 else self.M_max
                if len(neighbor.neighbors[lc]) > max_neighbors:
                    # Keep closest neighbors
                    candidates = [
                        (nid, self._distance(neighbor.vector, self.nodes[nid].vector))
                        for nid in neighbor.neighbors[lc]
                    ]
                    candidates.sort(key=lambda x: x[1])
                    neighbor.neighbors[lc] = [nid for nid, _ in candidates[:max_neighbors]]

            if neighbors:
                current = neighbors[0][0]

        self.nodes[id] = node

        # Update entry point if needed
        if level > self.max_level:
            self.entry_point = id
            self.max_level = level

        return level

    def search(self, query: np.ndarray, k: int, ef_search: int = None) -> List[SearchResult]:
        """Search for k nearest neighbors."""
        if not self.entry_point:
            return []

        query = np.array(query, dtype=np.float32)
        ef = ef_search or max(k, 10)

        # Start from entry point
        current = self.entry_point

        # Traverse from top level to level 1
        for lc in range(self.max_level, 0, -1):
            current, _ = self._search_layer(query, current, 1, lc)[0]

        # Search layer 0 with ef candidates
        candidates = self._search_layer(query, current, ef, 0)

        # Return top k
        results = []
        for node_id, dist in candidates[:k]:
            node = self.nodes[node_id]
            results.append(SearchResult(
                id=node_id,
                distance=dist,
                vector=node.vector,
                metadata={}
            ))

        return results

    def _search_layer(self, query: np.ndarray, entry: str,
                     ef: int, level: int) -> List[Tuple[str, float]]:
        """Search a single layer for nearest neighbors."""
        visited = {entry}
        entry_node = self.nodes[entry]
        entry_dist = self._distance(query, entry_node.vector)

        # Min-heap for candidates (distance, id)
        candidates = [(entry_dist, entry)]

        # Max-heap for results (negative distance for max behavior)
        results = [(-entry_dist, entry)]

        while candidates:
            c_dist, c_id = heapq.heappop(candidates)
            f_dist = -results[0][0]

            if c_dist > f_dist:
                break

            node = self.nodes[c_id]
            for neighbor_id in node.neighbors.get(level, []):
                if neighbor_id in visited:
                    continue

                visited.add(neighbor_id)
                neighbor = self.nodes[neighbor_id]
                neighbor_dist = self._distance(query, neighbor.vector)

                if neighbor_dist < f_dist or len(results) < ef:
                    heapq.heappush(candidates, (neighbor_dist, neighbor_id))
                    heapq.heappush(results, (-neighbor_dist, neighbor_id))

                    if len(results) > ef:
                        heapq.heappop(results)

                    f_dist = -results[0][0]

        # Return results sorted by distance
        return sorted([(id, -dist) for dist, id in results])

    def _select_neighbors(self, query: np.ndarray,
                         candidates: List[Tuple[str, float]],
                         m: int) -> List[Tuple[str, float]]:
        """Select M neighbors using simple heuristic."""
        return candidates[:m]

    def delete(self, id: str) -> bool:
        """Delete a node from the index."""
        if id not in self.nodes:
            return False

        node = self.nodes[id]

        # Remove connections
        for level, neighbors in node.neighbors.items():
            for neighbor_id in neighbors:
                if neighbor_id in self.nodes:
                    neighbor = self.nodes[neighbor_id]
                    if id in neighbor.neighbors.get(level, []):
                        neighbor.neighbors[level].remove(id)

        del self.nodes[id]

        # Update entry point if needed
        if id == self.entry_point:
            if self.nodes:
                self.entry_point = next(iter(self.nodes))
                self.max_level = self.nodes[self.entry_point].level
            else:
                self.entry_point = None
                self.max_level = 0

        return True
```

---

## Platform Deployment

### Cluster Configuration

- Single node for index (or sharded across nodes)
- Each shard holds portion of vectors
- Query aggregation for distributed search

### gRPC Services

```protobuf
service HNSWService {
    rpc CreateIndex(CreateIndexRequest) returns (CreateIndexResponse);
    rpc Insert(InsertRequest) returns (InsertResponse);
    rpc BatchInsert(BatchInsertRequest) returns (BatchInsertResponse);
    rpc Search(SearchRequest) returns (SearchResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
    rpc GetStats(GetStatsRequest) returns (GetStatsResponse);
}

service NodeService {
    rpc SyncGraph(SyncGraphRequest) returns (SyncGraphResponse);
    rpc ForwardSearch(ForwardSearchRequest) returns (ForwardSearchResponse);
}
```

---

## Realistic Testing

```python
class TestHNSW:
    async def test_basic_search(self, cluster):
        """Search returns nearest neighbors."""
        node = cluster[0]

        # Create index
        await node.CreateIndex(dimension=128, m=16)

        # Insert vectors
        vectors = [np.random.randn(128).astype(np.float32) for _ in range(1000)]
        for i, vec in enumerate(vectors):
            await node.Insert(id=f"vec_{i}", vector=vec.tolist())

        # Search
        query = vectors[0]
        results = await node.Search(query_vector=query.tolist(), k=10)

        # First result should be the query itself
        assert results.results[0].id == "vec_0"
        assert results.results[0].distance < 0.001

    async def test_recall_quality(self, cluster):
        """Measure recall quality."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, m=16)

        # Insert vectors
        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10000)]
        for i, vec in enumerate(vectors):
            await node.Insert(id=f"vec_{i}", vector=vec.tolist())

        # Compute ground truth for random queries
        queries = [np.random.randn(128).astype(np.float32) for _ in range(100)]
        recall_sum = 0

        for query in queries:
            # Brute force ground truth
            distances = [(i, np.linalg.norm(query - v)) for i, v in enumerate(vectors)]
            distances.sort(key=lambda x: x[1])
            ground_truth = set(f"vec_{i}" for i, _ in distances[:10])

            # HNSW search
            results = await node.Search(query_vector=query.tolist(), k=10, ef_search=50)
            hnsw_results = set(r.id for r in results.results)

            # Recall = intersection / ground_truth
            recall = len(ground_truth & hnsw_results) / len(ground_truth)
            recall_sum += recall

        avg_recall = recall_sum / len(queries)
        assert avg_recall > 0.95  # > 95% recall

    async def test_search_performance(self, cluster):
        """Search latency is acceptable."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, m=16)

        # Insert 100K vectors
        for i in range(100000):
            vec = np.random.randn(128).astype(np.float32)
            await node.Insert(id=f"vec_{i}", vector=vec.tolist())

        # Measure search time
        query = np.random.randn(128).astype(np.float32)

        import time
        start = time.time()
        for _ in range(100):
            await node.Search(query_vector=query.tolist(), k=10)
        duration = time.time() - start

        avg_latency_ms = duration / 100 * 1000
        assert avg_latency_ms < 10  # < 10ms per query
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Search | Returns correct neighbors |
| Recall | > 95% at k=10 |
| Latency | < 10ms for 100K vectors |
| Memory | Reasonable overhead per vector |
