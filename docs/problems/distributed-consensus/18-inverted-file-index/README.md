# Inverted File Index (IVF)

## Problem Overview

Implement the Inverted File Index (IVF) algorithm for approximate nearest neighbor search using clustering-based partitioning.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution

### Algorithm Overview

IVF works by:
1. **Training:** Cluster vectors using k-means to create centroids
2. **Assignment:** Assign each vector to its nearest centroid
3. **Search:** Find nearest centroids, then search within those clusters

**Key parameters:**
- `n_clusters`: Number of clusters/centroids (typically √n)
- `n_probe`: Number of clusters to search (trade-off accuracy vs speed)

### Implementation

```python
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

@dataclass
class Vector:
    id: str
    values: np.ndarray
    metadata: Dict[str, str]

@dataclass
class Centroid:
    cluster_id: int
    values: np.ndarray
    vector_count: int

@dataclass
class SearchResult:
    id: str
    distance: float
    cluster_id: int
    vector: np.ndarray
    metadata: Dict[str, str]

class IVFIndex:
    """Inverted File Index for approximate nearest neighbor search."""

    def __init__(self, dim: int, n_clusters: int = 100,
                 distance_type: str = "euclidean"):
        self.dim = dim
        self.n_clusters = n_clusters
        self.distance_type = distance_type

        self.centroids: List[Centroid] = []
        self.clusters: Dict[int, List[Vector]] = defaultdict(list)
        self.is_trained = False
        self.total_vectors = 0

    def _distance(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate distance between two vectors."""
        if self.distance_type == "euclidean":
            return np.linalg.norm(v1 - v2)
        elif self.distance_type == "cosine":
            return 1 - np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        elif self.distance_type == "inner_product":
            return -np.dot(v1, v2)
        return np.linalg.norm(v1 - v2)

    def train(self, training_vectors: List[np.ndarray],
              n_iterations: int = 25) -> float:
        """Train the index using k-means clustering."""
        if len(training_vectors) < self.n_clusters:
            raise ValueError("Not enough training vectors")

        vectors = np.array(training_vectors)

        # Initialize centroids randomly
        indices = np.random.choice(len(vectors), self.n_clusters, replace=False)
        centroids = vectors[indices].copy()

        # K-means iterations
        for _ in range(n_iterations):
            # Assign vectors to nearest centroid
            assignments = []
            for v in vectors:
                distances = [self._distance(v, c) for c in centroids]
                assignments.append(np.argmin(distances))

            # Update centroids
            for i in range(self.n_clusters):
                cluster_vectors = vectors[np.array(assignments) == i]
                if len(cluster_vectors) > 0:
                    centroids[i] = cluster_vectors.mean(axis=0)

        # Store centroids
        self.centroids = [
            Centroid(
                cluster_id=i,
                values=centroids[i],
                vector_count=0
            )
            for i in range(self.n_clusters)
        ]

        # Calculate inertia (sum of squared distances)
        inertia = 0
        for v, c in zip(vectors, assignments):
            inertia += self._distance(v, centroids[c]) ** 2

        self.is_trained = True
        return inertia

    def add(self, id: str, vector: np.ndarray,
            metadata: Dict[str, str] = None) -> int:
        """Add a vector to the index."""
        if not self.is_trained:
            raise ValueError("Index must be trained first")

        vector = np.array(vector, dtype=np.float32)

        # Find nearest centroid
        distances = [
            self._distance(vector, c.values)
            for c in self.centroids
        ]
        cluster_id = np.argmin(distances)

        # Add to cluster
        vec = Vector(
            id=id,
            values=vector,
            metadata=metadata or {}
        )
        self.clusters[cluster_id].append(vec)
        self.centroids[cluster_id].vector_count += 1
        self.total_vectors += 1

        return cluster_id

    def search(self, query: np.ndarray, k: int, n_probe: int = 1,
               filter_metadata: Dict[str, str] = None) -> List[SearchResult]:
        """Search for k nearest neighbors."""
        if not self.is_trained:
            raise ValueError("Index must be trained first")

        query = np.array(query, dtype=np.float32)

        # Find n_probe nearest centroids
        centroid_distances = [
            (i, self._distance(query, c.values))
            for i, c in enumerate(self.centroids)
        ]
        centroid_distances.sort(key=lambda x: x[1])
        probe_clusters = [c[0] for c in centroid_distances[:n_probe]]

        # Search within selected clusters
        candidates = []
        for cluster_id in probe_clusters:
            for vec in self.clusters[cluster_id]:
                # Apply metadata filter
                if filter_metadata:
                    match = all(
                        vec.metadata.get(k) == v
                        for k, v in filter_metadata.items()
                    )
                    if not match:
                        continue

                dist = self._distance(query, vec.values)
                candidates.append((dist, vec, cluster_id))

        # Sort and return top k
        candidates.sort(key=lambda x: x[0])

        results = []
        for dist, vec, cluster_id in candidates[:k]:
            results.append(SearchResult(
                id=vec.id,
                distance=dist,
                cluster_id=cluster_id,
                vector=vec.values,
                metadata=vec.metadata
            ))

        return results

    def remove(self, id: str) -> bool:
        """Remove a vector from the index."""
        for cluster_id, vectors in self.clusters.items():
            for i, vec in enumerate(vectors):
                if vec.id == id:
                    vectors.pop(i)
                    self.centroids[cluster_id].vector_count -= 1
                    self.total_vectors -= 1
                    return True
        return False

    def get_cluster_vectors(self, cluster_id: int,
                           limit: int = 100, offset: int = 0) -> List[Vector]:
        """Get vectors in a specific cluster."""
        if cluster_id not in self.clusters:
            return []

        return self.clusters[cluster_id][offset:offset + limit]

    def get_stats(self) -> Dict:
        """Get index statistics."""
        cluster_sizes = [c.vector_count for c in self.centroids]

        return {
            "total_vectors": self.total_vectors,
            "n_clusters": self.n_clusters,
            "dimension": self.dim,
            "is_trained": self.is_trained,
            "cluster_sizes": cluster_sizes,
            "avg_cluster_size": np.mean(cluster_sizes) if cluster_sizes else 0,
            "max_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
            "min_cluster_size": min(cluster_sizes) if cluster_sizes else 0,
        }
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** for distributed IVF index
- Each node owns subset of centroids (C/5 centroids per node)
- Query routing based on centroid ownership
- Replication factor 2 for fault tolerance

### gRPC Services

```protobuf
service IVFService {
    rpc CreateIndex(CreateIndexRequest) returns (CreateIndexResponse);
    rpc Train(TrainRequest) returns (TrainResponse);
    rpc Add(AddRequest) returns (AddResponse);
    rpc BatchAdd(BatchAddRequest) returns (BatchAddResponse);
    rpc Search(SearchRequest) returns (SearchResponse);
    rpc Remove(RemoveRequest) returns (RemoveResponse);
    rpc GetStats(GetStatsRequest) returns (GetStatsResponse);
    rpc GetCentroids(GetCentroidsRequest) returns (GetCentroidsResponse);
}

service NodeService {
    rpc SyncCentroids(SyncCentroidsRequest) returns (SyncCentroidsResponse);
    rpc ForwardSearch(ForwardSearchRequest) returns (ForwardSearchResponse);
}
```

---

## Realistic Testing

```python
class TestIVF:
    async def test_training(self, cluster):
        """Index trains correctly."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, n_clusters=100)

        # Generate training data
        training_vectors = [
            {"id": f"train_{i}", "values": np.random.randn(128).tolist()}
            for i in range(10000)
        ]

        response = await node.Train(training_vectors=training_vectors)

        assert response.success
        assert response.n_clusters == 100

    async def test_search_with_n_probe(self, cluster):
        """Higher n_probe improves recall."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, n_clusters=100)

        # Train and add vectors
        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10000)]

        await node.Train(
            training_vectors=[{"id": f"v_{i}", "values": v.tolist()} for i, v in enumerate(vectors[:1000])]
        )

        for i, v in enumerate(vectors):
            await node.Add(id=f"vec_{i}", vector=v.tolist())

        # Test with different n_probe values
        query = np.random.randn(128).astype(np.float32)

        # Ground truth
        distances = [(i, np.linalg.norm(query - v)) for i, v in enumerate(vectors)]
        distances.sort(key=lambda x: x[1])
        ground_truth = set(f"vec_{i}" for i, _ in distances[:10])

        # n_probe = 1
        results_1 = await node.Search(query_vector=query.tolist(), k=10, n_probe=1)
        recall_1 = len(ground_truth & set(r.id for r in results_1.results)) / 10

        # n_probe = 10
        results_10 = await node.Search(query_vector=query.tolist(), k=10, n_probe=10)
        recall_10 = len(ground_truth & set(r.id for r in results_10.results)) / 10

        # Higher n_probe should give better recall
        assert recall_10 >= recall_1

    async def test_cluster_balance(self, cluster):
        """Clusters should be reasonably balanced."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, n_clusters=100)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10000)]
        await node.Train(
            training_vectors=[{"id": f"v_{i}", "values": v.tolist()} for i, v in enumerate(vectors[:1000])]
        )

        for i, v in enumerate(vectors):
            await node.Add(id=f"vec_{i}", vector=v.tolist())

        stats = await node.GetStats()

        # Check balance
        avg_size = stats.stats.total_vectors / stats.stats.n_clusters
        max_size = max(stats.stats.cluster_sizes)

        # Max cluster shouldn't be more than 5x average
        assert max_size < 5 * avg_size
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Training | Converges with low inertia |
| Search | Higher n_probe improves recall |
| Cluster Balance | Max cluster < 5x average |
| Performance | O(n_probe * cluster_size) search |
