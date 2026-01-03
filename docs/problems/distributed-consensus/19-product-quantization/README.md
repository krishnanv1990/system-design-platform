# Product Quantization (PQ)

## Problem Overview

Implement Product Quantization for efficient vector compression and similarity search, achieving massive memory reduction while maintaining search quality.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Algorithm Overview

Product Quantization works by:
1. Splitting each vector into M subvectors
2. Quantizing each subvector using a separate codebook
3. Representing vectors as M code indices (huge compression)
4. Using precomputed distance tables for fast search

**Key parameters:**
- `M`: Number of subquantizers (subvectors)
- `Ks`: Number of centroids per subquantizer (typically 256)
- `nbits`: Bits per code (8 for Ks=256)

### Implementation

```python
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class Codebook:
    subquantizer_id: int
    ks: int               # Number of centroids
    dsub: int             # Subvector dimension
    centroids: np.ndarray # Shape: (ks, dsub)

@dataclass
class PQCode:
    id: str
    codes: np.ndarray     # Shape: (M,) with dtype uint8/uint16
    metadata: Dict[str, str]

@dataclass
class SearchResult:
    id: str
    distance: float
    exact_distance: float
    codes: np.ndarray
    metadata: Dict[str, str]

class ProductQuantizer:
    """Product Quantization for vector compression."""

    def __init__(self, dim: int, M: int = 8, Ks: int = 256,
                 distance_type: str = "euclidean"):
        if dim % M != 0:
            raise ValueError(f"Dimension {dim} must be divisible by M={M}")

        self.dim = dim
        self.M = M
        self.Ks = Ks
        self.dsub = dim // M
        self.distance_type = distance_type

        self.codebooks: List[Codebook] = []
        self.is_trained = False

        # Stored codes
        self.codes: Dict[str, PQCode] = {}
        self.vectors: Dict[str, np.ndarray] = {}  # For reranking

    def train(self, training_vectors: List[np.ndarray],
              n_iterations: int = 25) -> List[float]:
        """Train the codebooks using k-means on subvectors."""
        vectors = np.array(training_vectors, dtype=np.float32)
        errors = []

        self.codebooks = []

        for m in range(self.M):
            # Extract subvectors for this subquantizer
            start = m * self.dsub
            end = (m + 1) * self.dsub
            subvectors = vectors[:, start:end]

            # K-means clustering
            centroids = self._kmeans(subvectors, self.Ks, n_iterations)

            # Calculate quantization error
            error = self._compute_error(subvectors, centroids)
            errors.append(error)

            self.codebooks.append(Codebook(
                subquantizer_id=m,
                ks=self.Ks,
                dsub=self.dsub,
                centroids=centroids
            ))

        self.is_trained = True
        return errors

    def _kmeans(self, vectors: np.ndarray, k: int,
                n_iterations: int) -> np.ndarray:
        """Run k-means clustering."""
        # Initialize centroids randomly
        indices = np.random.choice(len(vectors), k, replace=False)
        centroids = vectors[indices].copy()

        for _ in range(n_iterations):
            # Assign to nearest centroid
            distances = self._compute_distances_to_centroids(vectors, centroids)
            assignments = np.argmin(distances, axis=1)

            # Update centroids
            for i in range(k):
                cluster_vectors = vectors[assignments == i]
                if len(cluster_vectors) > 0:
                    centroids[i] = cluster_vectors.mean(axis=0)

        return centroids

    def _compute_distances_to_centroids(self, vectors: np.ndarray,
                                        centroids: np.ndarray) -> np.ndarray:
        """Compute distances from vectors to centroids."""
        # Shape: (n_vectors, k)
        return np.linalg.norm(
            vectors[:, np.newaxis, :] - centroids[np.newaxis, :, :],
            axis=2
        )

    def _compute_error(self, vectors: np.ndarray,
                       centroids: np.ndarray) -> float:
        """Compute quantization error."""
        distances = self._compute_distances_to_centroids(vectors, centroids)
        return np.mean(np.min(distances, axis=1))

    def encode(self, vector: np.ndarray) -> np.ndarray:
        """Encode a vector to PQ codes."""
        if not self.is_trained:
            raise ValueError("Quantizer must be trained first")

        vector = np.array(vector, dtype=np.float32)
        codes = np.zeros(self.M, dtype=np.uint8 if self.Ks <= 256 else np.uint16)

        for m in range(self.M):
            start = m * self.dsub
            end = (m + 1) * self.dsub
            subvector = vector[start:end]

            # Find nearest centroid
            distances = np.linalg.norm(
                self.codebooks[m].centroids - subvector,
                axis=1
            )
            codes[m] = np.argmin(distances)

        return codes

    def decode(self, codes: np.ndarray) -> np.ndarray:
        """Decode PQ codes back to approximate vector."""
        if not self.is_trained:
            raise ValueError("Quantizer must be trained first")

        vector = np.zeros(self.dim, dtype=np.float32)

        for m in range(self.M):
            start = m * self.dsub
            end = (m + 1) * self.dsub
            vector[start:end] = self.codebooks[m].centroids[codes[m]]

        return vector

    def add(self, id: str, vector: np.ndarray,
            metadata: Dict[str, str] = None, store_vector: bool = False):
        """Add a vector to the index."""
        vector = np.array(vector, dtype=np.float32)
        codes = self.encode(vector)

        self.codes[id] = PQCode(
            id=id,
            codes=codes,
            metadata=metadata or {}
        )

        if store_vector:
            self.vectors[id] = vector

        return codes

    def compute_distance_table(self, query: np.ndarray) -> np.ndarray:
        """Precompute distance table for asymmetric search."""
        query = np.array(query, dtype=np.float32)

        # Shape: (M, Ks)
        distance_table = np.zeros((self.M, self.Ks), dtype=np.float32)

        for m in range(self.M):
            start = m * self.dsub
            end = (m + 1) * self.dsub
            subquery = query[start:end]

            # Distance from subquery to all centroids
            if self.distance_type == "euclidean":
                distance_table[m] = np.linalg.norm(
                    self.codebooks[m].centroids - subquery,
                    axis=1
                )
            elif self.distance_type == "inner_product":
                distance_table[m] = -np.dot(
                    self.codebooks[m].centroids,
                    subquery
                )

        return distance_table

    def search(self, query: np.ndarray, k: int,
               rerank: bool = False, rerank_k: int = None) -> List[SearchResult]:
        """Search for k nearest neighbors using asymmetric distance."""
        if not self.codes:
            return []

        query = np.array(query, dtype=np.float32)

        # Precompute distance table
        distance_table = self.compute_distance_table(query)

        # Compute approximate distances to all codes
        candidates = []
        for id, pq_code in self.codes.items():
            # Sum distances from each subquantizer
            approx_dist = sum(
                distance_table[m, pq_code.codes[m]]
                for m in range(self.M)
            )
            candidates.append((approx_dist, id, pq_code))

        # Sort by approximate distance
        candidates.sort(key=lambda x: x[0])

        # Reranking with exact distances
        if rerank and self.vectors:
            rerank_k = rerank_k or k * 10
            rerank_candidates = candidates[:rerank_k]

            for i, (approx_dist, id, pq_code) in enumerate(rerank_candidates):
                if id in self.vectors:
                    exact_dist = np.linalg.norm(query - self.vectors[id])
                    rerank_candidates[i] = (exact_dist, id, pq_code)

            rerank_candidates.sort(key=lambda x: x[0])
            candidates = rerank_candidates

        # Return top k
        results = []
        for approx_dist, id, pq_code in candidates[:k]:
            exact_dist = approx_dist
            if rerank and id in self.vectors:
                exact_dist = np.linalg.norm(query - self.vectors[id])

            results.append(SearchResult(
                id=id,
                distance=approx_dist,
                exact_distance=exact_dist,
                codes=pq_code.codes,
                metadata=pq_code.metadata
            ))

        return results

    def remove(self, id: str) -> bool:
        """Remove a vector from the index."""
        if id in self.codes:
            del self.codes[id]
            if id in self.vectors:
                del self.vectors[id]
            return True
        return False

    def get_compression_ratio(self) -> float:
        """Calculate compression ratio."""
        original_size = self.dim * 4  # float32
        compressed_size = self.M * (1 if self.Ks <= 256 else 2)  # uint8/uint16
        return original_size / compressed_size
```

---

## Platform Deployment

### Cluster Configuration

- Codebooks shared across all nodes
- Codes distributed via consistent hashing
- Query broadcasts to all shards

### gRPC Services

```protobuf
service PQService {
    rpc CreateIndex(CreateIndexRequest) returns (CreateIndexResponse);
    rpc Train(TrainRequest) returns (TrainResponse);
    rpc Encode(EncodeRequest) returns (EncodeResponse);
    rpc Decode(DecodeRequest) returns (DecodeResponse);
    rpc Add(AddRequest) returns (AddResponse);
    rpc BatchAdd(BatchAddRequest) returns (BatchAddResponse);
    rpc Search(SearchRequest) returns (SearchResponse);
    rpc Remove(RemoveRequest) returns (RemoveResponse);
    rpc GetStats(GetStatsRequest) returns (GetStatsResponse);
    rpc ComputeDistanceTable(ComputeDistanceTableRequest) returns (ComputeDistanceTableResponse);
}

service NodeService {
    rpc SyncCodebooks(SyncCodebooksRequest) returns (SyncCodebooksResponse);
    rpc ForwardSearch(ForwardSearchRequest) returns (ForwardSearchResponse);
}
```

---

## Realistic Testing

```python
class TestProductQuantization:
    async def test_compression_ratio(self, cluster):
        """PQ achieves expected compression."""
        node = cluster[0]

        # 128-dim, M=8 subquantizers
        await node.CreateIndex(dimension=128, m=8, ks=256)

        # Train
        training = [np.random.randn(128).tolist() for _ in range(10000)]
        await node.Train(training_vectors=[
            {"id": f"t_{i}", "values": v} for i, v in enumerate(training)
        ])

        stats = await node.GetStats()

        # 128 * 4 bytes = 512 bytes original
        # 8 * 1 byte = 8 bytes compressed
        # Ratio = 512 / 8 = 64x
        assert stats.stats.compression_ratio > 60

    async def test_reconstruction_error(self, cluster):
        """Decoded vectors are close to originals."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, m=8, ks=256)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(1000)]
        await node.Train(training_vectors=[
            {"id": f"t_{i}", "values": v.tolist()} for i, v in enumerate(vectors)
        ])

        # Test reconstruction
        errors = []
        for v in vectors[:100]:
            encode_resp = await node.Encode(vector=v.tolist())
            decode_resp = await node.Decode(codes=encode_resp.codes)

            reconstructed = np.array(decode_resp.vector)
            error = np.linalg.norm(v - reconstructed) / np.linalg.norm(v)
            errors.append(error)

        avg_error = np.mean(errors)
        # Relative error should be < 20%
        assert avg_error < 0.2

    async def test_search_with_reranking(self, cluster):
        """Reranking improves search quality."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, m=8, ks=256)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(10000)]
        await node.Train(training_vectors=[
            {"id": f"t_{i}", "values": v.tolist()} for i, v in enumerate(vectors[:1000])
        ])

        for i, v in enumerate(vectors):
            await node.Add(id=f"vec_{i}", vector=v.tolist())

        # Query
        query = np.random.randn(128).astype(np.float32)

        # Ground truth
        distances = [(i, np.linalg.norm(query - v)) for i, v in enumerate(vectors)]
        distances.sort(key=lambda x: x[1])
        ground_truth = set(f"vec_{i}" for i, _ in distances[:10])

        # Without reranking
        results_no_rerank = await node.Search(
            query_vector=query.tolist(), k=10, rerank=False
        )
        recall_no_rerank = len(ground_truth & set(r.id for r in results_no_rerank.results)) / 10

        # With reranking
        results_rerank = await node.Search(
            query_vector=query.tolist(), k=10, rerank=True, rerank_k=100
        )
        recall_rerank = len(ground_truth & set(r.id for r in results_rerank.results)) / 10

        # Reranking should improve recall
        assert recall_rerank >= recall_no_rerank

    async def test_asymmetric_search_speed(self, cluster):
        """Asymmetric search is fast due to distance tables."""
        node = cluster[0]

        await node.CreateIndex(dimension=128, m=8, ks=256)

        vectors = [np.random.randn(128).astype(np.float32) for _ in range(100000)]
        await node.Train(training_vectors=[
            {"id": f"t_{i}", "values": v.tolist()} for i, v in enumerate(vectors[:1000])
        ])

        for i, v in enumerate(vectors):
            await node.Add(id=f"vec_{i}", vector=v.tolist())

        query = np.random.randn(128).astype(np.float32)

        import time
        start = time.time()
        for _ in range(100):
            await node.Search(query_vector=query.tolist(), k=10)
        duration = time.time() - start

        avg_latency_ms = duration / 100 * 1000

        # Should be fast even with 100K vectors
        assert avg_latency_ms < 50  # < 50ms
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Compression | > 32x compression ratio |
| Reconstruction | < 20% relative error |
| Search Quality | Reranking improves recall |
| Search Speed | < 50ms for 100K vectors |

## Trade-offs

| Method | Memory | Speed | Accuracy |
|--------|--------|-------|----------|
| Brute Force | High | Slow | Exact |
| PQ | Very Low | Fast | Approximate |
| PQ + Reranking | Low | Medium | Good |
| IVF + PQ | Very Low | Very Fast | Approximate |
