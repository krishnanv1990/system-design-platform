"""
Inverted File Index (IVF) Implementation - Python Template

This template provides the structure for implementing the IVF algorithm for
vector similarity search. IVF is a clustering-based index that accelerates
search by partitioning the vector space using k-means clustering.

Key Algorithm Concepts:
-----------------------
1. **Training Phase** (K-Means Clustering):
   - Cluster training vectors into n_clusters groups
   - Each cluster is represented by its centroid
   - Centroids partition the vector space into Voronoi cells

2. **Indexing Phase**:
   - For each new vector, find the nearest centroid
   - Assign vector to that cluster's inverted list
   - Each inverted list contains vectors belonging to that cluster

3. **Search Phase**:
   - For query vector, find n_probe nearest centroids
   - Search only within those n_probe inverted lists
   - This dramatically reduces search space vs exhaustive search

Key Parameters:
- n_clusters: Number of clusters (typically sqrt(n) to n/10)
- n_probe: Number of clusters to search (trade-off accuracy vs speed)
- n_iterations: K-means iterations during training

Trade-offs:
- More clusters = faster search, but more memory and longer training
- Higher n_probe = better accuracy, but slower search
- Fewer training vectors = faster training, but worse cluster quality

Paper Reference: "Billion-scale similarity search with GPUs" - Johnson et al.
See also: Faiss IVFFlat implementation

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
from typing import Dict, List, Optional, Set, Tuple

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from inverted_file_index.proto)
import inverted_file_index_pb2
import inverted_file_index_pb2_grpc

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
class Centroid:
    """
    Represents a cluster centroid.

    The centroid is the mean of all vectors assigned to this cluster.
    """
    cluster_id: int
    values: List[float]
    vector_count: int = 0


@dataclass
class InvertedList:
    """
    Inverted list for a cluster.

    Contains all vectors assigned to this cluster, enabling
    fast retrieval during search.
    """
    cluster_id: int
    vectors: Dict[str, VectorData] = field(default_factory=dict)

    def add(self, vector: VectorData):
        """Add a vector to this inverted list."""
        self.vectors[vector.id] = vector

    def remove(self, vector_id: str) -> bool:
        """Remove a vector from this inverted list."""
        if vector_id in self.vectors:
            del self.vectors[vector_id]
            return True
        return False

    def __len__(self) -> int:
        return len(self.vectors)


@dataclass
class IndexConfig:
    """Configuration parameters for the IVF index."""
    dimension: int
    n_clusters: int = 100          # Number of clusters
    distance_type: str = "euclidean"  # "euclidean", "cosine", "inner_product"


class DistanceType(Enum):
    """Supported distance metrics."""
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    INNER_PRODUCT = "inner_product"


# =============================================================================
# IVF Index Implementation
# =============================================================================

class IVFIndex:
    """
    Inverted File Index for approximate nearest neighbor search.

    This class manages cluster centroids and inverted lists, providing
    methods for training, indexing, and search.

    TODO: Implement the core IVF algorithms in the marked sections.
    """

    def __init__(self, config: IndexConfig):
        """
        Initialize the IVF index.

        Args:
            config: Index configuration parameters
        """
        self.config = config
        self.centroids: List[Centroid] = []
        self.inverted_lists: Dict[int, InvertedList] = {}
        self.is_trained: bool = False

        # Vector ID to cluster mapping for fast deletion
        self.vector_to_cluster: Dict[str, int] = {}

        # Thread safety
        self.lock = threading.RLock()

        # Statistics
        self.total_vectors: int = 0

    def _compute_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute distance between two vectors.

        TODO: Implement distance computation for supported metrics:
        - Euclidean: sqrt(sum((a[i] - b[i])^2))
        - Cosine: 1 - (dot(a,b) / (||a|| * ||b||))
        - Inner Product: -dot(a,b) (negative for similarity->distance)

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Distance value (lower = more similar)
        """
        # TODO: Implement distance computation
        # Hint: Use self.config.distance_type to determine which metric to use
        return float('inf')

    def _find_nearest_centroid(self, vector: List[float]) -> Tuple[int, float]:
        """
        Find the nearest centroid to a vector.

        TODO: Implement nearest centroid search:
        - Compute distance from vector to each centroid
        - Return cluster_id and distance of nearest centroid

        Args:
            vector: Query vector

        Returns:
            Tuple of (cluster_id, distance)
        """
        # TODO: Implement nearest centroid search
        return 0, float('inf')

    def _find_nearest_centroids(
        self,
        vector: List[float],
        n_probe: int
    ) -> List[Tuple[int, float]]:
        """
        Find the n_probe nearest centroids to a vector.

        TODO: Implement n-nearest centroids search:
        - Compute distance from vector to each centroid
        - Return n_probe nearest (cluster_id, distance) pairs
        - Sort by distance ascending

        Args:
            vector: Query vector
            n_probe: Number of centroids to return

        Returns:
            List of (cluster_id, distance) tuples, sorted by distance
        """
        # TODO: Implement n-nearest centroids search
        # Hint: Compute all distances, then use heapq.nsmallest or sorted()
        return []

    def train_kmeans(
        self,
        training_vectors: List[VectorData],
        n_iterations: int = 25,
        n_init: int = 1
    ) -> Tuple[bool, float]:
        """
        Train the index using k-means clustering.

        TODO: Implement k-means clustering:
        1. Initialize centroids (random selection or k-means++)
        2. Repeat for n_iterations:
           a. Assignment: Assign each vector to nearest centroid
           b. Update: Recompute centroids as mean of assigned vectors
           c. Track inertia (sum of squared distances)
        3. Optionally run n_init times and keep best result

        Args:
            training_vectors: Vectors to use for training
            n_iterations: Number of k-means iterations
            n_init: Number of k-means runs (keep best)

        Returns:
            Tuple of (success, final_inertia)
        """
        with self.lock:
            if len(training_vectors) < self.config.n_clusters:
                logger.error("Not enough training vectors")
                return False, float('inf')

            # TODO: Implement k-means clustering
            #
            # Step 1: Initialize centroids
            # Option A: Random selection from training vectors
            # Option B: K-means++ initialization (better but more complex)
            #
            # Step 2: K-means iterations
            # For each iteration:
            #   - Create empty lists for each cluster
            #   - Assign each vector to nearest centroid
            #   - Recompute centroid as mean of assigned vectors
            #   - Handle empty clusters (reinitialize randomly)
            #
            # Step 3: Initialize inverted lists
            # For each cluster, create an empty InvertedList
            #
            # Hint: Track inertia = sum of (distance to assigned centroid)^2

            self.is_trained = False
            return False, float('inf')

    def assign_to_cluster(self, vector: VectorData) -> Tuple[bool, int]:
        """
        Assign a vector to its nearest cluster.

        TODO: Implement cluster assignment:
        1. Find nearest centroid
        2. Add vector to corresponding inverted list
        3. Update vector_to_cluster mapping
        4. Increment total_vectors count

        Args:
            vector: Vector to assign

        Returns:
            Tuple of (success, assigned_cluster_id)
        """
        with self.lock:
            if not self.is_trained:
                return False, -1

            # TODO: Implement cluster assignment
            # 1. Find nearest centroid using _find_nearest_centroid()
            # 2. Add vector to inverted_lists[cluster_id]
            # 3. Store mapping in vector_to_cluster
            # 4. Increment centroid.vector_count

            return False, -1

    def add_vector(
        self,
        vector_id: str,
        values: List[float],
        metadata: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, int]:
        """
        Add a vector to the index.

        Args:
            vector_id: Unique identifier
            values: Vector values
            metadata: Optional metadata

        Returns:
            Tuple of (success, assigned_cluster)
        """
        vector = VectorData(
            id=vector_id,
            values=values,
            metadata=metadata or {}
        )
        return self.assign_to_cluster(vector)

    def remove_vector(self, vector_id: str) -> bool:
        """
        Remove a vector from the index.

        TODO: Implement vector removal:
        1. Find cluster from vector_to_cluster mapping
        2. Remove from inverted list
        3. Clean up mapping
        4. Update counts

        Args:
            vector_id: ID of vector to remove

        Returns:
            True if found and removed
        """
        with self.lock:
            # TODO: Implement vector removal
            return False

    def search_cluster(
        self,
        query: List[float],
        cluster_id: int,
        k: int
    ) -> List[Tuple[str, float, int]]:
        """
        Search for k nearest neighbors within a single cluster.

        TODO: Implement within-cluster search:
        - Compute distance from query to each vector in the cluster
        - Return k nearest (vector_id, distance, cluster_id) tuples

        Args:
            query: Query vector
            cluster_id: Cluster to search
            k: Number of neighbors to return

        Returns:
            List of (vector_id, distance, cluster_id) tuples
        """
        # TODO: Implement within-cluster search
        # Hint: This is exhaustive search within the inverted list
        return []

    def search(
        self,
        query: List[float],
        k: int,
        n_probe: int = 1
    ) -> List[Tuple[str, float, int]]:
        """
        Search for k nearest neighbors across n_probe clusters.

        TODO: Implement IVF search:
        1. Find n_probe nearest centroids
        2. Search within each of those clusters
        3. Merge results and return k nearest overall

        Args:
            query: Query vector
            k: Number of neighbors to return
            n_probe: Number of clusters to search

        Returns:
            List of (vector_id, distance, cluster_id) tuples
        """
        with self.lock:
            if not self.is_trained:
                return []

            # TODO: Implement IVF search
            # 1. Find n_probe nearest centroids using _find_nearest_centroids()
            # 2. For each centroid, call search_cluster()
            # 3. Merge all results and keep k nearest
            # Hint: Use a heap or sorted list to efficiently find k smallest

            return []

    def get_centroids(self) -> List[Centroid]:
        """Get all centroids."""
        with self.lock:
            return [
                Centroid(
                    cluster_id=c.cluster_id,
                    values=c.values.copy(),
                    vector_count=c.vector_count
                )
                for c in self.centroids
            ]

    def get_cluster_vectors(
        self,
        cluster_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[VectorData]:
        """Get vectors in a specific cluster with pagination."""
        with self.lock:
            if cluster_id not in self.inverted_lists:
                return []

            inv_list = self.inverted_lists[cluster_id]
            vectors = list(inv_list.vectors.values())
            return vectors[offset:offset + limit]

    def get_stats(self) -> Dict:
        """Get index statistics."""
        with self.lock:
            cluster_sizes = [
                len(self.inverted_lists.get(i, InvertedList(i)))
                for i in range(len(self.centroids))
            ]
            return {
                "total_vectors": self.total_vectors,
                "n_clusters": len(self.centroids),
                "dimension": self.config.dimension,
                "is_trained": self.is_trained,
                "cluster_sizes": cluster_sizes,
            }


# =============================================================================
# IVF Node (Server) Implementation
# =============================================================================

class IVFNode:
    """
    IVF server node for distributed vector search.

    Handles both local index operations and coordination with peers
    for distributed scenarios.
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        """
        Initialize the IVF node.

        Args:
            node_id: Unique identifier for this node
            port: Port number to listen on
            peers: List of peer addresses (host:port)
        """
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.index: Optional[IVFIndex] = None

        # Which clusters this node owns (for distributed mode)
        self.owned_clusters: Set[int] = set()

        # Peer communication
        self.peer_stubs: Dict[str, inverted_file_index_pb2_grpc.NodeServiceStub] = {}

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
                self.peer_stubs[peer] = inverted_file_index_pb2_grpc.NodeServiceStub(channel)
                logger.info(f"Connected to peer: {peer}")
            except Exception as e:
                logger.error(f"Failed to connect to peer {peer}: {e}")

    # =========================================================================
    # IVFService RPC Implementations
    # =========================================================================

    async def handle_create_index(
        self,
        request: inverted_file_index_pb2.CreateIndexRequest
    ) -> inverted_file_index_pb2.CreateIndexResponse:
        """Create a new IVF index."""
        response = inverted_file_index_pb2.CreateIndexResponse()

        with self.lock:
            try:
                config = IndexConfig(
                    dimension=request.dimension,
                    n_clusters=request.n_clusters if request.n_clusters > 0 else 100,
                    distance_type=request.distance_type or "euclidean"
                )
                self.index = IVFIndex(config)
                response.success = True
                response.index_id = f"{self.node_id}_ivf"
                logger.info(f"Created IVF index: dim={config.dimension}, clusters={config.n_clusters}")
            except Exception as e:
                response.success = False
                response.error = str(e)

        return response

    async def handle_train(
        self,
        request: inverted_file_index_pb2.TrainRequest
    ) -> inverted_file_index_pb2.TrainResponse:
        """Train the index on training vectors."""
        response = inverted_file_index_pb2.TrainResponse()

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
            n_init = request.n_init if request.n_init > 0 else 1

            success, inertia = self.index.train_kmeans(
                training_vectors,
                n_iterations,
                n_init
            )

            response.success = success
            response.n_clusters = len(self.index.centroids)
            response.inertia = inertia

            if not success:
                response.error = "Training failed"

        return response

    async def handle_add(
        self,
        request: inverted_file_index_pb2.AddRequest
    ) -> inverted_file_index_pb2.AddResponse:
        """Add a vector to the index."""
        response = inverted_file_index_pb2.AddResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            if not self.index.is_trained:
                response.success = False
                response.error = "Index not trained"
                return response

            success, cluster = self.index.add_vector(
                request.id,
                list(request.vector),
                dict(request.metadata)
            )

            response.success = success
            response.assigned_cluster = cluster

        return response

    async def handle_batch_add(
        self,
        request: inverted_file_index_pb2.BatchAddRequest
    ) -> inverted_file_index_pb2.BatchAddResponse:
        """Add multiple vectors in batch."""
        response = inverted_file_index_pb2.BatchAddResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            if not self.index.is_trained:
                response.success = False
                response.error = "Index not trained"
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
        request: inverted_file_index_pb2.SearchRequest
    ) -> inverted_file_index_pb2.SearchResponse:
        """Search for k nearest neighbors."""
        response = inverted_file_index_pb2.SearchResponse()

        with self.lock:
            if self.index is None or not self.index.is_trained:
                return response

            start_time = time.time()

            n_probe = request.n_probe if request.n_probe > 0 else 1
            results = self.index.search(
                list(request.query_vector),
                request.k,
                n_probe
            )

            elapsed_us = int((time.time() - start_time) * 1_000_000)
            response.search_time_us = elapsed_us

            clusters_searched = set()
            for vector_id, distance, cluster_id in results:
                result = inverted_file_index_pb2.SearchResult()
                result.id = vector_id
                result.distance = distance
                result.cluster_id = cluster_id
                response.results.append(result)
                clusters_searched.add(cluster_id)

            response.clusters_searched.extend(sorted(clusters_searched))

        return response

    async def handle_remove(
        self,
        request: inverted_file_index_pb2.RemoveRequest
    ) -> inverted_file_index_pb2.RemoveResponse:
        """Remove a vector from the index."""
        response = inverted_file_index_pb2.RemoveResponse()

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
        request: inverted_file_index_pb2.GetStatsRequest
    ) -> inverted_file_index_pb2.GetStatsResponse:
        """Get index statistics."""
        response = inverted_file_index_pb2.GetStatsResponse()

        with self.lock:
            if self.index:
                stats = self.index.get_stats()
                response.stats.total_vectors = stats["total_vectors"]
                response.stats.n_clusters = stats["n_clusters"]
                response.stats.dimension = stats["dimension"]
                response.stats.is_trained = stats["is_trained"]
                response.stats.cluster_sizes.extend(stats["cluster_sizes"])

        return response

    async def handle_get_centroids(
        self,
        request: inverted_file_index_pb2.GetCentroidsRequest
    ) -> inverted_file_index_pb2.GetCentroidsResponse:
        """Get all centroids."""
        response = inverted_file_index_pb2.GetCentroidsResponse()

        with self.lock:
            if self.index:
                for centroid in self.index.get_centroids():
                    c = inverted_file_index_pb2.Centroid()
                    c.cluster_id = centroid.cluster_id
                    c.values.extend(centroid.values)
                    c.vector_count = centroid.vector_count
                    response.centroids.append(c)

        return response

    async def handle_get_cluster_vectors(
        self,
        request: inverted_file_index_pb2.GetClusterVectorsRequest
    ) -> inverted_file_index_pb2.GetClusterVectorsResponse:
        """Get vectors in a specific cluster."""
        response = inverted_file_index_pb2.GetClusterVectorsResponse()

        with self.lock:
            if self.index:
                vectors = self.index.get_cluster_vectors(
                    request.cluster_id,
                    request.limit if request.limit > 0 else 100,
                    request.offset
                )

                for vec in vectors:
                    v = inverted_file_index_pb2.Vector()
                    v.id = vec.id
                    v.values.extend(vec.values)
                    v.metadata.update(vec.metadata)
                    response.vectors.append(v)

                if self.index.inverted_lists.get(request.cluster_id):
                    response.total_in_cluster = len(
                        self.index.inverted_lists[request.cluster_id]
                    )

        return response

    # =========================================================================
    # NodeService RPC Implementations (Distributed)
    # =========================================================================

    async def handle_sync_centroids(
        self,
        request: inverted_file_index_pb2.SyncCentroidsRequest
    ) -> inverted_file_index_pb2.SyncCentroidsResponse:
        """
        Synchronize centroids from another node.

        TODO: Implement centroid synchronization for distributed IVF:
        - Update local centroids with received centroids
        - Handle version conflicts
        """
        response = inverted_file_index_pb2.SyncCentroidsResponse()
        response.success = False
        response.centroids_synced = 0
        # TODO: Implement centroid synchronization
        return response

    async def handle_forward_search(
        self,
        request: inverted_file_index_pb2.ForwardSearchRequest
    ) -> inverted_file_index_pb2.ForwardSearchResponse:
        """
        Handle forwarded search for specific clusters.

        Used when clusters are sharded across nodes.
        """
        response = inverted_file_index_pb2.ForwardSearchResponse()
        response.served_by = self.node_id

        with self.lock:
            if self.index and self.index.is_trained:
                # Search only in target clusters
                all_results = []
                for cluster_id in request.target_clusters:
                    results = self.index.search_cluster(
                        list(request.query_vector),
                        cluster_id,
                        request.k
                    )
                    all_results.extend(results)

                # Sort and take k best
                all_results.sort(key=lambda x: x[1])
                for vector_id, distance, cluster_id in all_results[:request.k]:
                    result = inverted_file_index_pb2.SearchResult()
                    result.id = vector_id
                    result.distance = distance
                    result.cluster_id = cluster_id
                    response.results.append(result)

        return response

    async def handle_transfer_vectors(
        self,
        request: inverted_file_index_pb2.TransferVectorsRequest
    ) -> inverted_file_index_pb2.TransferVectorsResponse:
        """
        Transfer vectors during cluster rebalancing.

        TODO: Implement vector transfer between nodes.
        """
        response = inverted_file_index_pb2.TransferVectorsResponse()
        response.success = False
        response.transferred_count = 0
        # TODO: Implement vector transfer
        return response

    async def handle_heartbeat(
        self,
        request: inverted_file_index_pb2.HeartbeatRequest
    ) -> inverted_file_index_pb2.HeartbeatResponse:
        """Handle heartbeat from peer node."""
        response = inverted_file_index_pb2.HeartbeatResponse()
        response.acknowledged = True
        response.timestamp = int(time.time() * 1000)
        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class IVFServicer(inverted_file_index_pb2_grpc.IVFServiceServicer):
    """gRPC service implementation for IVF operations."""

    def __init__(self, node: IVFNode):
        self.node = node

    async def CreateIndex(self, request, context):
        return await self.node.handle_create_index(request)

    async def Train(self, request, context):
        return await self.node.handle_train(request)

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

    async def GetCentroids(self, request, context):
        return await self.node.handle_get_centroids(request)

    async def GetClusterVectors(self, request, context):
        return await self.node.handle_get_cluster_vectors(request)


class NodeServicer(inverted_file_index_pb2_grpc.NodeServiceServicer):
    """gRPC service implementation for distributed node operations."""

    def __init__(self, node: IVFNode):
        self.node = node

    async def SyncCentroids(self, request, context):
        return await self.node.handle_sync_centroids(request)

    async def ForwardSearch(self, request, context):
        return await self.node.handle_forward_search(request)

    async def TransferVectors(self, request, context):
        return await self.node.handle_transfer_vectors(request)

    async def Heartbeat(self, request, context):
        return await self.node.handle_heartbeat(request)


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the IVF node server."""
    node = IVFNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    inverted_file_index_pb2_grpc.add_IVFServiceServicer_to_server(
        IVFServicer(node), server
    )
    inverted_file_index_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(node), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting IVF node {node_id} on {listen_addr}")
    logger.info(f"Peers: {peers}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(
        description="IVF Vector Index Node",
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
