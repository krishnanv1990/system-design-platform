"""
Product Quantization (PQ) Implementation - Python Template

This template provides the structure for implementing Product Quantization
for vector compression and similarity search. PQ achieves high compression
ratios while enabling fast approximate distance computation.

Key Algorithm Concepts:
-----------------------
1. **Vector Decomposition**:
   - Split each D-dimensional vector into M subvectors of dimension D/M
   - Each subvector is quantized independently

2. **Codebook Training** (per subquantizer):
   - Run k-means on training subvectors to learn Ks centroids
   - Result: M codebooks, each with Ks centroids of dimension D/M

3. **Encoding**:
   - For each subvector, find nearest centroid in corresponding codebook
   - Store M code indices (each 0 to Ks-1) instead of D floats
   - Compression: D*4 bytes -> M*log2(Ks)/8 bytes (e.g., 128*4 -> 8*1 = 64x)

4. **Asymmetric Distance Computation (ADC)**:
   - Precompute distance table: M x Ks distances (query subvector to centroids)
   - For each database code: sum M table lookups
   - Much faster than computing full vector distances

Key Parameters:
- M: Number of subquantizers (typically 8, 16, 32)
- Ks: Centroids per subquantizer (typically 256 = 8 bits per code)
- D: Original vector dimension (must be divisible by M)

Trade-offs:
- More subquantizers (larger M) = better accuracy but more storage
- More centroids (larger Ks) = better accuracy but longer training
- Asymmetric distance is more accurate than symmetric

Paper Reference: "Product Quantization for Nearest Neighbor Search"
                 - Jegou, Douze, Schmid (TPAMI 2011)

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from product_quantization.proto)
import product_quantization_pb2
import product_quantization_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class VectorData:
    """Stores a vector with its metadata."""
    id: str
    values: List[float]
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class PQCode:
    """
    Compressed representation of a vector using PQ codes.

    Instead of storing D floats, we store M code indices.
    Each code index references a centroid in the corresponding codebook.
    """
    id: str
    codes: List[int]  # M code indices (each 0 to Ks-1)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Codebook:
    """
    Codebook for a single subquantizer.

    Contains Ks centroids, each of dimension dsub = D/M.
    Centroids are stored as a flattened list for efficiency.
    """
    subquantizer_id: int
    ks: int                     # Number of centroids
    dsub: int                   # Subvector dimension
    centroids: List[float]      # Flattened: ks * dsub values

    def get_centroid(self, code: int) -> List[float]:
        """Get the centroid vector for a given code index."""
        start = code * self.dsub
        return self.centroids[start:start + self.dsub]


@dataclass
class IndexConfig:
    """Configuration parameters for the PQ index."""
    dimension: int
    m: int = 8                     # Number of subquantizers
    ks: int = 256                  # Centroids per subquantizer
    distance_type: str = "euclidean"  # "euclidean", "inner_product"

    @property
    def dsub(self) -> int:
        """Dimension of each subvector."""
        return self.dimension // self.m

    @property
    def nbits(self) -> int:
        """Bits per code (log2(ks))."""
        return int(math.log2(self.ks))


class DistanceType(Enum):
    """Supported distance metrics."""
    EUCLIDEAN = "euclidean"
    INNER_PRODUCT = "inner_product"


# =============================================================================
# Product Quantization Index Implementation
# =============================================================================

class PQIndex:
    """
    Product Quantization Index for vector compression and search.

    This class manages codebooks and compressed codes, providing
    methods for training, encoding, decoding, and search.

    TODO: Implement the core PQ algorithms in the marked sections.
    """

    def __init__(self, config: IndexConfig):
        """
        Initialize the PQ index.

        Args:
            config: Index configuration parameters
        """
        self.config = config

        # Validate configuration
        if config.dimension % config.m != 0:
            raise ValueError(
                f"Dimension {config.dimension} must be divisible by M={config.m}"
            )

        self.codebooks: List[Codebook] = []
        self.codes: Dict[str, PQCode] = {}
        self.is_trained: bool = False

        # Optional: store original vectors for reranking
        self.original_vectors: Dict[str, List[float]] = {}
        self.store_originals: bool = False

        # Thread safety
        self.lock = threading.RLock()

    def _compute_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute distance between two vectors.

        TODO: Implement distance computation:
        - Euclidean: sum((a[i] - b[i])^2)  (squared, no sqrt for efficiency)
        - Inner Product: -dot(a, b)

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Distance value (lower = more similar)
        """
        # TODO: Implement distance computation
        return float('inf')

    def _split_vector(self, vector: List[float]) -> List[List[float]]:
        """
        Split a vector into M subvectors.

        Args:
            vector: D-dimensional vector

        Returns:
            List of M subvectors, each of dimension dsub
        """
        dsub = self.config.dsub
        return [
            vector[i * dsub:(i + 1) * dsub]
            for i in range(self.config.m)
        ]

    def _train_subquantizer(
        self,
        subvectors: List[List[float]],
        subquantizer_id: int,
        n_iterations: int = 25
    ) -> Tuple[Codebook, float]:
        """
        Train a single subquantizer using k-means.

        TODO: Implement k-means for subquantizer training:
        1. Initialize Ks centroids (random or k-means++)
        2. For n_iterations:
           a. Assign each subvector to nearest centroid
           b. Recompute centroids as mean of assigned vectors
        3. Return codebook and quantization error

        Args:
            subvectors: Training subvectors for this subquantizer
            subquantizer_id: Index of this subquantizer (0 to M-1)
            n_iterations: Number of k-means iterations

        Returns:
            Tuple of (trained Codebook, quantization_error)
        """
        # TODO: Implement k-means for subquantizer
        #
        # Hint: Similar to IVF k-means, but for subvectors only
        # 1. Randomly select Ks subvectors as initial centroids
        # 2. Iterate: assign + update centroids
        # 3. Compute final error = mean squared distance to assigned centroid

        ks = self.config.ks
        dsub = self.config.dsub

        # Placeholder: return empty codebook
        return Codebook(
            subquantizer_id=subquantizer_id,
            ks=ks,
            dsub=dsub,
            centroids=[0.0] * (ks * dsub)
        ), float('inf')

    def train_subquantizers(
        self,
        training_vectors: List[VectorData],
        n_iterations: int = 25
    ) -> Tuple[bool, List[float], float]:
        """
        Train all M subquantizers on training vectors.

        TODO: Implement subquantizer training:
        1. Split each training vector into M subvectors
        2. For each subquantizer m:
           - Collect all m-th subvectors from training data
           - Train subquantizer using k-means
           - Store resulting codebook

        Args:
            training_vectors: Vectors to use for training
            n_iterations: K-means iterations per subquantizer

        Returns:
            Tuple of (success, per_subquantizer_errors, total_error)
        """
        with self.lock:
            if len(training_vectors) < self.config.ks:
                logger.error(
                    f"Need at least {self.config.ks} training vectors, "
                    f"got {len(training_vectors)}"
                )
                return False, [], float('inf')

            # TODO: Implement subquantizer training
            #
            # Step 1: Split all training vectors
            # all_subvectors[m] = list of m-th subvector from each training vector
            #
            # Step 2: Train each subquantizer
            # For m in range(M):
            #   codebook, error = _train_subquantizer(all_subvectors[m], m, n_iterations)
            #   self.codebooks.append(codebook)
            #   errors.append(error)
            #
            # Step 3: Mark as trained
            # self.is_trained = True

            self.is_trained = False
            return False, [], float('inf')

    def encode_vector(self, vector: List[float]) -> Optional[List[int]]:
        """
        Encode a vector to PQ codes.

        TODO: Implement vector encoding:
        1. Split vector into M subvectors
        2. For each subvector:
           - Find nearest centroid in corresponding codebook
           - Store centroid index as code

        Args:
            vector: D-dimensional vector to encode

        Returns:
            List of M code indices, or None if not trained
        """
        with self.lock:
            if not self.is_trained:
                return None

            # TODO: Implement vector encoding
            #
            # codes = []
            # subvectors = self._split_vector(vector)
            # for m in range(self.config.m):
            #     # Find nearest centroid in codebook[m]
            #     best_code = 0
            #     best_dist = inf
            #     for k in range(self.config.ks):
            #         centroid = self.codebooks[m].get_centroid(k)
            #         dist = self._compute_distance(subvectors[m], centroid)
            #         if dist < best_dist:
            #             best_dist = dist
            #             best_code = k
            #     codes.append(best_code)
            # return codes

            return None

    def decode_vector(self, codes: List[int]) -> Optional[List[float]]:
        """
        Decode PQ codes back to approximate vector.

        TODO: Implement vector decoding:
        - Concatenate centroids from each codebook based on codes
        - Result is the quantized (approximate) vector

        Args:
            codes: List of M code indices

        Returns:
            Reconstructed D-dimensional vector, or None if not trained
        """
        with self.lock:
            if not self.is_trained:
                return None

            if len(codes) != self.config.m:
                return None

            # TODO: Implement vector decoding
            #
            # reconstructed = []
            # for m in range(self.config.m):
            #     centroid = self.codebooks[m].get_centroid(codes[m])
            #     reconstructed.extend(centroid)
            # return reconstructed

            return None

    def compute_distance_table(self, query: List[float]) -> List[List[float]]:
        """
        Compute distance table for asymmetric distance computation.

        TODO: Implement distance table computation:
        - For each subquantizer m and centroid k:
          - Compute distance(query_subvector[m], codebook[m].centroid[k])
        - Result: M x Ks table of precomputed distances

        This allows O(M) distance computation for each database vector
        instead of O(D).

        Args:
            query: Query vector

        Returns:
            Distance table as nested list [M][Ks]
        """
        # TODO: Implement distance table computation
        #
        # table = []
        # subvectors = self._split_vector(query)
        # for m in range(self.config.m):
        #     row = []
        #     for k in range(self.config.ks):
        #         centroid = self.codebooks[m].get_centroid(k)
        #         dist = self._compute_distance(subvectors[m], centroid)
        #         row.append(dist)
        #     table.append(row)
        # return table

        return []

    def _compute_asymmetric_distance(
        self,
        distance_table: List[List[float]],
        codes: List[int]
    ) -> float:
        """
        Compute asymmetric distance using precomputed table.

        TODO: Implement asymmetric distance:
        - Sum distance_table[m][codes[m]] for each subquantizer m
        - This is O(M) instead of O(D)

        Args:
            distance_table: Precomputed M x Ks distance table
            codes: PQ codes of database vector

        Returns:
            Approximate distance to query
        """
        # TODO: Implement asymmetric distance
        #
        # distance = 0.0
        # for m in range(self.config.m):
        #     distance += distance_table[m][codes[m]]
        # return distance

        return float('inf')

    def add_vector(
        self,
        vector_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[List[int]]]:
        """
        Add a vector to the index.

        Args:
            vector_id: Unique identifier
            vector: Vector values
            metadata: Optional metadata

        Returns:
            Tuple of (success, assigned_codes)
        """
        with self.lock:
            if not self.is_trained:
                return False, None

            codes = self.encode_vector(vector)
            if codes is None:
                return False, None

            self.codes[vector_id] = PQCode(
                id=vector_id,
                codes=codes,
                metadata=metadata or {}
            )

            if self.store_originals:
                self.original_vectors[vector_id] = vector.copy()

            return True, codes

    def remove_vector(self, vector_id: str) -> bool:
        """Remove a vector from the index."""
        with self.lock:
            if vector_id in self.codes:
                del self.codes[vector_id]
                if vector_id in self.original_vectors:
                    del self.original_vectors[vector_id]
                return True
            return False

    def search_with_pq(
        self,
        query: List[float],
        k: int,
        rerank: bool = False,
        rerank_k: Optional[int] = None
    ) -> List[Tuple[str, float, float]]:
        """
        Search for k nearest neighbors using PQ.

        TODO: Implement PQ search:
        1. Compute distance table for query
        2. For each code in database:
           - Compute asymmetric distance using table
        3. Return k nearest
        4. Optionally rerank with exact distances

        Args:
            query: Query vector
            k: Number of neighbors to return
            rerank: Whether to rerank with exact distances
            rerank_k: Number of candidates to rerank (default: 4*k)

        Returns:
            List of (vector_id, approx_distance, exact_distance) tuples
        """
        with self.lock:
            if not self.is_trained:
                return []

            # TODO: Implement PQ search
            #
            # Step 1: Compute distance table
            # distance_table = self.compute_distance_table(query)
            #
            # Step 2: Compute distances to all database vectors
            # candidates = []
            # for vector_id, pq_code in self.codes.items():
            #     approx_dist = self._compute_asymmetric_distance(
            #         distance_table, pq_code.codes
            #     )
            #     candidates.append((vector_id, approx_dist))
            #
            # Step 3: Sort and get top-k (or rerank_k if reranking)
            # candidates.sort(key=lambda x: x[1])
            # n_candidates = rerank_k if rerank else k
            # top_candidates = candidates[:n_candidates]
            #
            # Step 4: Optionally rerank with exact distances
            # if rerank and self.store_originals:
            #     results = []
            #     for vector_id, approx_dist in top_candidates:
            #         if vector_id in self.original_vectors:
            #             exact_dist = self._compute_distance(
            #                 query, self.original_vectors[vector_id]
            #             )
            #         else:
            #             exact_dist = approx_dist
            #         results.append((vector_id, approx_dist, exact_dist))
            #     results.sort(key=lambda x: x[2])
            #     return results[:k]
            #
            # return [(vid, d, d) for vid, d in top_candidates[:k]]

            return []

    def get_codebooks(self) -> List[Codebook]:
        """Get all codebooks."""
        with self.lock:
            return [
                Codebook(
                    subquantizer_id=cb.subquantizer_id,
                    ks=cb.ks,
                    dsub=cb.dsub,
                    centroids=cb.centroids.copy()
                )
                for cb in self.codebooks
            ]

    def get_stats(self) -> Dict:
        """Get index statistics."""
        with self.lock:
            original_size = len(self.codes) * self.config.dimension * 4  # bytes
            compressed_size = len(self.codes) * self.config.m  # bytes (assuming 8-bit codes)
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 0

            return {
                "total_vectors": len(self.codes),
                "dimension": self.config.dimension,
                "m": self.config.m,
                "ks": self.config.ks,
                "nbits": self.config.nbits,
                "is_trained": self.is_trained,
                "compression_ratio": compression_ratio,
            }


# =============================================================================
# PQ Node (Server) Implementation
# =============================================================================

class PQNode:
    """
    PQ server node for distributed vector search.

    Handles both local index operations and coordination with peers
    for distributed scenarios.
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        """
        Initialize the PQ node.

        Args:
            node_id: Unique identifier for this node
            port: Port number to listen on
            peers: List of peer addresses (host:port)
        """
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.index: Optional[PQIndex] = None

        # Peer communication
        self.peer_stubs: Dict[str, product_quantization_pb2_grpc.NodeServiceStub] = {}

        # Synchronization
        self.lock = threading.RLock()

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            try:
                if ".run.app" in peer:
                    ssl_creds = grpc.ssl_channel_credentials()
                    channel = aio.secure_channel(peer, ssl_creds)
                else:
                    channel = aio.insecure_channel(peer)
                self.peer_stubs[peer] = product_quantization_pb2_grpc.NodeServiceStub(channel)
                logger.info(f"Connected to peer: {peer}")
            except Exception as e:
                logger.error(f"Failed to connect to peer {peer}: {e}")

    # =========================================================================
    # PQService RPC Implementations
    # =========================================================================

    async def handle_create_index(
        self,
        request: product_quantization_pb2.CreateIndexRequest
    ) -> product_quantization_pb2.CreateIndexResponse:
        """Create a new PQ index."""
        response = product_quantization_pb2.CreateIndexResponse()

        with self.lock:
            try:
                config = IndexConfig(
                    dimension=request.dimension,
                    m=request.m if request.m > 0 else 8,
                    ks=request.ks if request.ks > 0 else 256,
                    distance_type=request.distance_type or "euclidean"
                )
                self.index = PQIndex(config)
                response.success = True
                response.index_id = f"{self.node_id}_pq"
                response.dsub = config.dsub
                logger.info(
                    f"Created PQ index: dim={config.dimension}, "
                    f"M={config.m}, Ks={config.ks}, dsub={config.dsub}"
                )
            except Exception as e:
                response.success = False
                response.error = str(e)

        return response

    async def handle_train(
        self,
        request: product_quantization_pb2.TrainRequest
    ) -> product_quantization_pb2.TrainResponse:
        """Train the quantizer on training vectors."""
        response = product_quantization_pb2.TrainResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            training_vectors = [
                VectorData(
                    id=v.id,
                    values=list(v.values),
                    metadata=dict(v.metadata)
                )
                for v in request.training_vectors
            ]

            n_iterations = request.n_iterations if request.n_iterations > 0 else 25

            success, errors, total_error = self.index.train_subquantizers(
                training_vectors,
                n_iterations
            )

            response.success = success
            response.quantization_errors.extend(errors)
            response.total_error = total_error

            if not success:
                response.error = "Training failed"

        return response

    async def handle_encode(
        self,
        request: product_quantization_pb2.EncodeRequest
    ) -> product_quantization_pb2.EncodeResponse:
        """Encode a vector to PQ codes."""
        response = product_quantization_pb2.EncodeResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            codes = self.index.encode_vector(list(request.vector))
            if codes is not None:
                response.success = True
                response.codes.extend(codes)
            else:
                response.success = False
                response.error = "Encoding failed (not trained?)"

        return response

    async def handle_decode(
        self,
        request: product_quantization_pb2.DecodeRequest
    ) -> product_quantization_pb2.DecodeResponse:
        """Decode PQ codes back to approximate vector."""
        response = product_quantization_pb2.DecodeResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            vector = self.index.decode_vector(list(request.codes))
            if vector is not None:
                response.success = True
                response.vector.extend(vector)
            else:
                response.success = False
                response.error = "Decoding failed"

        return response

    async def handle_add(
        self,
        request: product_quantization_pb2.AddRequest
    ) -> product_quantization_pb2.AddResponse:
        """Add a vector to the index."""
        response = product_quantization_pb2.AddResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            success, codes = self.index.add_vector(
                request.id,
                list(request.vector),
                dict(request.metadata)
            )

            response.success = success
            if codes is not None:
                response.codes.extend(codes)
            if not success:
                response.error = "Add failed (not trained?)"

        return response

    async def handle_batch_add(
        self,
        request: product_quantization_pb2.BatchAddRequest
    ) -> product_quantization_pb2.BatchAddResponse:
        """Add multiple vectors in batch."""
        response = product_quantization_pb2.BatchAddResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            added = 0
            failed_ids = []

            for vector in request.vectors:
                success, _ = self.index.add_vector(
                    vector.id,
                    list(vector.values),
                    dict(vector.metadata)
                )
                if success:
                    added += 1
                else:
                    failed_ids.append(vector.id)

            response.success = len(failed_ids) == 0
            response.added_count = added
            response.failed_ids.extend(failed_ids)

        return response

    async def handle_search(
        self,
        request: product_quantization_pb2.SearchRequest
    ) -> product_quantization_pb2.SearchResponse:
        """Search for k nearest neighbors using PQ."""
        response = product_quantization_pb2.SearchResponse()

        with self.lock:
            if self.index is None or not self.index.is_trained:
                return response

            start_time = time.time()

            rerank_k = request.rerank_k if request.rerank_k > 0 else 4 * request.k
            results = self.index.search_with_pq(
                list(request.query_vector),
                request.k,
                request.rerank,
                rerank_k
            )

            elapsed_us = int((time.time() - start_time) * 1_000_000)
            response.search_time_us = elapsed_us
            response.used_reranking = request.rerank

            for vector_id, approx_dist, exact_dist in results:
                result = product_quantization_pb2.SearchResult()
                result.id = vector_id
                result.distance = approx_dist
                result.exact_distance = exact_dist

                if vector_id in self.index.codes:
                    result.codes.extend(self.index.codes[vector_id].codes)

                response.results.append(result)

        return response

    async def handle_remove(
        self,
        request: product_quantization_pb2.RemoveRequest
    ) -> product_quantization_pb2.RemoveResponse:
        """Remove a vector from the index."""
        response = product_quantization_pb2.RemoveResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            found = self.index.remove_vector(request.id)
            response.success = found
            response.found = found

        return response

    async def handle_get_stats(
        self,
        request: product_quantization_pb2.GetStatsRequest
    ) -> product_quantization_pb2.GetStatsResponse:
        """Get index statistics."""
        response = product_quantization_pb2.GetStatsResponse()

        with self.lock:
            if self.index:
                stats = self.index.get_stats()
                response.stats.total_vectors = stats["total_vectors"]
                response.stats.dimension = stats["dimension"]
                response.stats.m = stats["m"]
                response.stats.ks = stats["ks"]
                response.stats.nbits = stats["nbits"]
                response.stats.is_trained = stats["is_trained"]
                response.stats.compression_ratio = stats["compression_ratio"]

        return response

    async def handle_get_codebooks(
        self,
        request: product_quantization_pb2.GetCodebooksRequest
    ) -> product_quantization_pb2.GetCodebooksResponse:
        """Get all codebooks."""
        response = product_quantization_pb2.GetCodebooksResponse()

        with self.lock:
            if self.index:
                for codebook in self.index.get_codebooks():
                    cb = product_quantization_pb2.Codebook()
                    cb.subquantizer_id = codebook.subquantizer_id
                    cb.ks = codebook.ks
                    cb.dsub = codebook.dsub
                    cb.centroids.extend(codebook.centroids)
                    response.codebooks.append(cb)

        return response

    async def handle_compute_distance_table(
        self,
        request: product_quantization_pb2.ComputeDistanceTableRequest
    ) -> product_quantization_pb2.ComputeDistanceTableResponse:
        """Compute distance table for a query vector."""
        response = product_quantization_pb2.ComputeDistanceTableResponse()

        with self.lock:
            if self.index and self.index.is_trained:
                table = self.index.compute_distance_table(list(request.query_vector))
                # Flatten table for response
                for row in table:
                    response.distance_table.extend(row)
                response.m = self.index.config.m
                response.ks = self.index.config.ks

        return response

    # =========================================================================
    # NodeService RPC Implementations (Distributed)
    # =========================================================================

    async def handle_sync_codebooks(
        self,
        request: product_quantization_pb2.SyncCodebooksRequest
    ) -> product_quantization_pb2.SyncCodebooksResponse:
        """
        Synchronize codebooks from another node.

        TODO: Implement codebook synchronization for distributed PQ:
        - Update local codebooks with received codebooks
        - Handle version conflicts
        """
        response = product_quantization_pb2.SyncCodebooksResponse()
        response.success = False
        response.codebooks_synced = 0
        # TODO: Implement codebook synchronization
        return response

    async def handle_forward_search(
        self,
        request: product_quantization_pb2.ForwardSearchRequest
    ) -> product_quantization_pb2.ForwardSearchResponse:
        """
        Handle forwarded search request.

        Can include precomputed distance table for efficiency.
        """
        response = product_quantization_pb2.ForwardSearchResponse()
        response.served_by = self.node_id

        with self.lock:
            if self.index and self.index.is_trained:
                # Use provided distance table or compute new one
                if len(request.distance_table) > 0:
                    # Reconstruct table from flat list
                    m = self.index.config.m
                    ks = self.index.config.ks
                    table = [
                        list(request.distance_table[i * ks:(i + 1) * ks])
                        for i in range(m)
                    ]

                    # Search using provided table
                    candidates = []
                    for vector_id, pq_code in self.index.codes.items():
                        dist = self.index._compute_asymmetric_distance(
                            table, pq_code.codes
                        )
                        candidates.append((vector_id, dist))

                    candidates.sort(key=lambda x: x[1])
                    for vector_id, dist in candidates[:request.k]:
                        result = product_quantization_pb2.SearchResult()
                        result.id = vector_id
                        result.distance = dist
                        response.results.append(result)
                else:
                    # Full search
                    results = self.index.search_with_pq(
                        list(request.query_vector),
                        request.k
                    )
                    for vector_id, approx_dist, exact_dist in results:
                        result = product_quantization_pb2.SearchResult()
                        result.id = vector_id
                        result.distance = approx_dist
                        response.results.append(result)

        return response

    async def handle_transfer_codes(
        self,
        request: product_quantization_pb2.TransferCodesRequest
    ) -> product_quantization_pb2.TransferCodesResponse:
        """
        Transfer PQ codes during rebalancing.

        TODO: Implement code transfer between nodes.
        """
        response = product_quantization_pb2.TransferCodesResponse()
        response.success = False
        response.transferred_count = 0
        # TODO: Implement code transfer
        return response

    async def handle_heartbeat(
        self,
        request: product_quantization_pb2.HeartbeatRequest
    ) -> product_quantization_pb2.HeartbeatResponse:
        """Handle heartbeat from peer node."""
        response = product_quantization_pb2.HeartbeatResponse()
        response.acknowledged = True
        response.timestamp = int(time.time() * 1000)
        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class PQServicer(product_quantization_pb2_grpc.PQServiceServicer):
    """gRPC service implementation for PQ operations."""

    def __init__(self, node: PQNode):
        self.node = node

    async def CreateIndex(self, request, context):
        return await self.node.handle_create_index(request)

    async def Train(self, request, context):
        return await self.node.handle_train(request)

    async def Encode(self, request, context):
        return await self.node.handle_encode(request)

    async def Decode(self, request, context):
        return await self.node.handle_decode(request)

    async def Add(self, request, context):
        return await self.node.handle_add(request)

    async def BatchAdd(self, request, context):
        return await self.node.handle_batch_add(request)

    async def Search(self, request, context):
        return await self.node.handle_search(request)

    async def Remove(self, request, context):
        return await self.node.handle_remove(request)

    async def GetStats(self, request, context):
        return await self.node.handle_get_stats(request)

    async def GetCodebooks(self, request, context):
        return await self.node.handle_get_codebooks(request)

    async def ComputeDistanceTable(self, request, context):
        return await self.node.handle_compute_distance_table(request)


class NodeServicer(product_quantization_pb2_grpc.NodeServiceServicer):
    """gRPC service implementation for distributed node operations."""

    def __init__(self, node: PQNode):
        self.node = node

    async def SyncCodebooks(self, request, context):
        return await self.node.handle_sync_codebooks(request)

    async def ForwardSearch(self, request, context):
        return await self.node.handle_forward_search(request)

    async def TransferCodes(self, request, context):
        return await self.node.handle_transfer_codes(request)

    async def Heartbeat(self, request, context):
        return await self.node.handle_heartbeat(request)


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the PQ node server."""
    node = PQNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    product_quantization_pb2_grpc.add_PQServiceServicer_to_server(
        PQServicer(node), server
    )
    product_quantization_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(node), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting PQ node {node_id} on {listen_addr}")
    logger.info(f"Peers: {peers}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(
        description="Product Quantization Vector Index Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
  python server.py --node-id node1 --port 50051 --peers ""
        """
    )
    parser.add_argument(
        "--node-id",
        required=True,
        help="Unique node identifier"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port to listen on"
    )
    parser.add_argument(
        "--peers",
        default="",
        help="Comma-separated list of peer addresses (host:port)"
    )

    args = parser.parse_args()
    peers = [p.strip() for p in args.peers.split(",") if p.strip()]

    asyncio.run(serve(args.node_id, args.port, peers))


if __name__ == "__main__":
    main()
