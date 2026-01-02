"""
HNSW (Hierarchical Navigable Small World) Index Implementation - Python Template

This template provides the structure for implementing the HNSW algorithm for
approximate nearest neighbor search. HNSW builds a hierarchical graph structure
where:
- Each layer is a navigable small world graph (proximity graph)
- Higher layers have fewer nodes (similar to skip-list structure)
- Search starts from the top layer and greedily descends to find neighbors

Key Algorithm Concepts:
-----------------------
1. **Graph Structure**: Multiple layers of proximity graphs, with exponentially
   decreasing node count as layer increases.

2. **Insertion**: For each new vector:
   - Randomly assign a max layer level (exponentially distributed)
   - Search from entry point to find insertion position
   - Connect to M nearest neighbors at each layer

3. **Search**: Greedy traversal from top to bottom:
   - Start at entry point (top layer)
   - Greedily move to nearest neighbor until local minimum
   - Descend to next layer and repeat
   - At layer 0, collect ef_search candidates

4. **Neighbor Selection**: Use heuristics to select diverse, high-quality neighbors:
   - Simple: Select M nearest
   - Heuristic: Prefer neighbors that provide different directions

Key Parameters:
- M: Maximum connections per node (affects graph density and search quality)
- ef_construction: Dynamic candidate list size during construction
- ef_search: Dynamic candidate list size during search
- m_L: Level generation factor (typically 1/ln(M))

Paper Reference: "Efficient and Robust Approximate Nearest Neighbor Search
Using Hierarchical Navigable Small World Graphs" - Malkov & Yashunin (2016)

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import heapq
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

# Generated protobuf imports (will be generated from hnsw.proto)
import hnsw_pb2
import hnsw_pb2_grpc

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
class HNSWNodeData:
    """
    Represents a node in the HNSW graph.

    Each node exists at multiple layers (from 0 to its assigned level).
    Neighbors are stored separately for each layer.
    """
    id: str
    vector: List[float]
    level: int  # Maximum level this node appears in (0 = bottom layer only)
    neighbors_by_layer: Dict[int, List[str]] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class IndexConfig:
    """Configuration parameters for the HNSW index."""
    dimension: int
    m: int = 16                    # Max connections per node
    m_max_0: int = 32              # Max connections at layer 0 (typically 2*M)
    ef_construction: int = 200      # Construction search depth
    m_l: float = 0.0               # Level generation factor (computed if 0)
    distance_type: str = "euclidean"  # "euclidean", "cosine", "inner_product"


class DistanceType(Enum):
    """Supported distance metrics."""
    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    INNER_PRODUCT = "inner_product"


@dataclass
class SearchCandidate:
    """
    Candidate during search with distance.

    Uses negative distance for max-heap behavior with heapq (min-heap).
    """
    distance: float
    node_id: str

    def __lt__(self, other: 'SearchCandidate') -> bool:
        return self.distance < other.distance


# =============================================================================
# HNSW Index Implementation
# =============================================================================

class HNSWIndex:
    """
    HNSW Index for approximate nearest neighbor search.

    This class manages the hierarchical graph structure and provides
    methods for insertion, deletion, and k-NN search.

    TODO: Implement the core HNSW algorithms in the marked sections.
    """

    def __init__(self, config: IndexConfig):
        """
        Initialize the HNSW index.

        Args:
            config: Index configuration parameters
        """
        self.config = config
        self.nodes: Dict[str, HNSWNodeData] = {}
        self.entry_point: Optional[str] = None
        self.max_level: int = -1

        # Compute level generation multiplier if not set
        if config.m_l == 0:
            self.m_l = 1.0 / math.log(config.m)
        else:
            self.m_l = config.m_l

        # Thread safety
        self.lock = threading.RLock()

        # Statistics
        self.total_distance_computations = 0

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
        # For now, return a placeholder
        return float('inf')

    def _generate_random_level(self) -> int:
        """
        Generate a random level for a new node.

        The level follows an exponential distribution that creates
        the skip-list-like structure of HNSW.

        TODO: Implement level generation:
        - level = floor(-ln(uniform(0,1)) * m_L)
        - Higher levels should be exponentially rarer

        Returns:
            Random level (0 = appears only at bottom layer)
        """
        # TODO: Implement exponential level generation
        # Hint: Use random.random() and math.log()
        return 0

    def _search_layer(
        self,
        query: List[float],
        entry_point_ids: List[str],
        ef: int,
        layer: int
    ) -> List[SearchCandidate]:
        """
        Search a single layer of the HNSW graph.

        This is the core greedy search algorithm used during both
        construction and query time.

        TODO: Implement layer search:
        1. Initialize candidate set C and result set W with entry points
        2. While C is not empty:
           a. Get nearest element c from C
           b. Get furthest element f from W
           c. If distance(c, query) > distance(f, query), break
           d. For each neighbor e of c at this layer:
              - If e not visited:
                - Mark e as visited
                - If distance(e, query) < distance(f, query) or |W| < ef:
                  - Add e to C and W
                  - If |W| > ef, remove furthest from W
        3. Return W

        Args:
            query: Query vector
            entry_point_ids: Starting node IDs for search
            ef: Size of dynamic candidate list
            layer: Layer number to search

        Returns:
            List of SearchCandidates (nearest neighbors found)
        """
        # TODO: Implement greedy layer search
        # This is the most critical algorithm in HNSW

        # Hint: Use two heaps:
        # - candidates: min-heap of nodes to explore (by distance)
        # - results: max-heap of current best results (by distance)

        # Placeholder: return empty list
        return []

    def _select_neighbors_simple(
        self,
        query: List[float],
        candidates: List[SearchCandidate],
        m: int
    ) -> List[str]:
        """
        Select M nearest neighbors from candidates (simple strategy).

        TODO: Implement simple neighbor selection:
        - Sort candidates by distance
        - Return M nearest neighbor IDs

        Args:
            query: Query vector
            candidates: Candidate neighbors with distances
            m: Maximum number of neighbors to select

        Returns:
            List of selected neighbor IDs
        """
        # TODO: Implement simple neighbor selection
        return []

    def _select_neighbors_heuristic(
        self,
        query: List[float],
        candidates: List[SearchCandidate],
        m: int,
        layer: int,
        extend_candidates: bool = True,
        keep_pruned: bool = True
    ) -> List[str]:
        """
        Select neighbors using the heuristic strategy (Algorithm 4 from paper).

        The heuristic prefers neighbors that are not only close to the query
        but also provide diverse directions, improving search quality.

        TODO: Implement heuristic neighbor selection:
        1. For each candidate c (sorted by distance):
           - If distance(c, query) < distance(c, any selected neighbor):
             - Add c to selected neighbors
           - Else if keep_pruned and |selected| < M:
             - Add c to discarded list
        2. Fill remaining slots from discarded if keep_pruned

        Args:
            query: Query vector
            candidates: Candidate neighbors with distances
            m: Maximum number of neighbors to select
            layer: Current layer (for potential layer-specific logic)
            extend_candidates: Whether to extend candidates with their neighbors
            keep_pruned: Whether to keep pruned candidates as backup

        Returns:
            List of selected neighbor IDs
        """
        # TODO: Implement heuristic neighbor selection
        # This improves search quality by ensuring neighbor diversity
        return []

    def insert_vector(
        self,
        vector_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, int]:
        """
        Insert a new vector into the HNSW index.

        TODO: Implement vector insertion (Algorithm 1 from paper):
        1. If first node, make it entry point and return
        2. Generate random level l for new node
        3. If l > max_level, update entry point
        4. Start from entry point at top layer
        5. For layers from max_level down to l+1:
           - Search layer with ef=1 to find closest node
           - Use that node as entry point for next layer
        6. For layers from min(l, max_level) down to 0:
           - Search layer with ef=ef_construction
           - Select neighbors using heuristic
           - Add bidirectional connections
           - Shrink neighbor lists if needed

        Args:
            vector_id: Unique identifier for the vector
            vector: Vector values
            metadata: Optional metadata dictionary

        Returns:
            Tuple of (success, assigned_level)
        """
        with self.lock:
            # TODO: Implement vector insertion

            # Hint: Follow the paper's Algorithm 1 closely
            # Key steps:
            # 1. Handle empty index case (first insertion)
            # 2. Generate level for new node
            # 3. Search from top to find nearest neighbors at each layer
            # 4. Connect new node to neighbors
            # 5. Update entry point if needed

            return False, 0

    def search_knn(
        self,
        query: List[float],
        k: int,
        ef_search: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for k nearest neighbors.

        TODO: Implement k-NN search (Algorithm 5 from paper):
        1. Start from entry point at top layer
        2. For layers from max_level down to 1:
           - Search layer with ef=1 to find closest node
           - Use result as entry point for next layer
        3. At layer 0:
           - Search with ef=ef_search
           - Return k nearest from result set

        Args:
            query: Query vector
            k: Number of neighbors to return
            ef_search: Search candidate list size (default: use config)

        Returns:
            List of (vector_id, distance) tuples, sorted by distance
        """
        with self.lock:
            if ef_search is None:
                ef_search = max(k, self.config.ef_construction)

            # TODO: Implement k-NN search

            # Hint: Similar to insertion but simpler
            # - Search from top to layer 1 with ef=1
            # - At layer 0, use ef=ef_search
            # - Return k best results

            return []

    def delete_vector(self, vector_id: str) -> bool:
        """
        Delete a vector from the index.

        TODO: Implement vector deletion:
        1. Find the node
        2. Remove all edges to/from this node
        3. Repair graph by reconnecting orphaned neighbors
        4. Update entry point if needed

        Note: Full deletion in HNSW is complex. A simpler approach
        is to mark nodes as deleted and skip them during search.

        Args:
            vector_id: ID of vector to delete

        Returns:
            True if found and deleted, False otherwise
        """
        with self.lock:
            # TODO: Implement vector deletion
            # Consider using soft-delete (marking) for simplicity
            return False

    def get_vector(self, vector_id: str) -> Optional[VectorData]:
        """Get a vector by ID."""
        with self.lock:
            if vector_id in self.nodes:
                node = self.nodes[vector_id]
                return VectorData(
                    id=node.id,
                    values=node.vector.copy(),
                    metadata=node.metadata.copy()
                )
            return None

    def get_stats(self) -> Dict:
        """Get index statistics."""
        with self.lock:
            return {
                "total_vectors": len(self.nodes),
                "max_level": self.max_level,
                "dimension": self.config.dimension,
                "m": self.config.m,
                "ef_construction": self.config.ef_construction,
                "entry_point": self.entry_point,
            }


# =============================================================================
# HNSW Node (Server) Implementation
# =============================================================================

class HNSWNode:
    """
    HNSW server node for distributed vector search.

    Handles both local index operations and coordination with peers
    for distributed scenarios.
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        """
        Initialize the HNSW node.

        Args:
            node_id: Unique identifier for this node
            port: Port number to listen on
            peers: List of peer addresses (host:port)
        """
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.index: Optional[HNSWIndex] = None

        # Peer communication
        self.peer_stubs: Dict[str, hnsw_pb2_grpc.NodeServiceStub] = {}

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
                self.peer_stubs[peer] = hnsw_pb2_grpc.NodeServiceStub(channel)
                logger.info(f"Connected to peer: {peer}")
            except Exception as e:
                logger.error(f"Failed to connect to peer {peer}: {e}")

    # =========================================================================
    # HNSWService RPC Implementations
    # =========================================================================

    async def handle_create_index(
        self,
        request: hnsw_pb2.CreateIndexRequest
    ) -> hnsw_pb2.CreateIndexResponse:
        """Create a new HNSW index."""
        response = hnsw_pb2.CreateIndexResponse()

        with self.lock:
            try:
                config = IndexConfig(
                    dimension=request.dimension,
                    m=request.m if request.m > 0 else 16,
                    ef_construction=request.ef_construction if request.ef_construction > 0 else 200,
                    distance_type=request.distance_type or "euclidean"
                )
                self.index = HNSWIndex(config)
                response.success = True
                response.index_id = f"{self.node_id}_hnsw"
                logger.info(f"Created HNSW index with dimension={config.dimension}, M={config.m}")
            except Exception as e:
                response.success = False
                response.error = str(e)

        return response

    async def handle_insert(
        self,
        request: hnsw_pb2.InsertRequest
    ) -> hnsw_pb2.InsertResponse:
        """Insert a vector into the index."""
        response = hnsw_pb2.InsertResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            success, level = self.index.insert_vector(
                request.id,
                list(request.vector),
                dict(request.metadata)
            )
            response.success = success
            response.level = level
            if not success:
                response.error = "Insertion failed"

        return response

    async def handle_batch_insert(
        self,
        request: hnsw_pb2.BatchInsertRequest
    ) -> hnsw_pb2.BatchInsertResponse:
        """Insert multiple vectors in batch."""
        response = hnsw_pb2.BatchInsertResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            inserted = 0
            failed_ids = []

            for vector in request.vectors:
                success, _ = self.index.insert_vector(
                    vector.id,
                    list(vector.values),
                    dict(vector.metadata)
                )
                if success:
                    inserted += 1
                else:
                    failed_ids.append(vector.id)

            response.success = len(failed_ids) == 0
            response.inserted_count = inserted
            response.failed_ids.extend(failed_ids)

        return response

    async def handle_search(
        self,
        request: hnsw_pb2.SearchRequest
    ) -> hnsw_pb2.SearchResponse:
        """Search for k nearest neighbors."""
        response = hnsw_pb2.SearchResponse()

        with self.lock:
            if self.index is None:
                return response

            start_time = time.time()

            results = self.index.search_knn(
                list(request.query_vector),
                request.k,
                request.ef_search if request.ef_search > 0 else None
            )

            elapsed_us = int((time.time() - start_time) * 1_000_000)
            response.search_time_us = elapsed_us

            for vector_id, distance in results:
                result = hnsw_pb2.SearchResult()
                result.id = vector_id
                result.distance = distance

                # Optionally include vector values
                vec_data = self.index.get_vector(vector_id)
                if vec_data:
                    result.vector.extend(vec_data.values)
                    result.metadata.update(vec_data.metadata)

                response.results.append(result)

        return response

    async def handle_delete(
        self,
        request: hnsw_pb2.DeleteRequest
    ) -> hnsw_pb2.DeleteResponse:
        """Delete a vector from the index."""
        response = hnsw_pb2.DeleteResponse()

        with self.lock:
            if self.index is None:
                response.success = False
                response.error = "Index not created"
                return response

            found = self.index.delete_vector(request.id)
            response.success = found
            response.found = found

        return response

    async def handle_get_stats(
        self,
        request: hnsw_pb2.GetStatsRequest
    ) -> hnsw_pb2.GetStatsResponse:
        """Get index statistics."""
        response = hnsw_pb2.GetStatsResponse()

        with self.lock:
            if self.index:
                stats = self.index.get_stats()
                response.stats.total_vectors = stats["total_vectors"]
                response.stats.max_level = stats["max_level"]
                response.stats.dimension = stats["dimension"]
                response.stats.m = stats["m"]
                response.stats.ef_construction = stats["ef_construction"]

        return response

    async def handle_get_vector(
        self,
        request: hnsw_pb2.GetVectorRequest
    ) -> hnsw_pb2.GetVectorResponse:
        """Get a specific vector by ID."""
        response = hnsw_pb2.GetVectorResponse()

        with self.lock:
            if self.index:
                vec_data = self.index.get_vector(request.id)
                if vec_data:
                    response.found = True
                    response.vector.id = vec_data.id
                    response.vector.values.extend(vec_data.values)
                    response.vector.metadata.update(vec_data.metadata)

        return response

    # =========================================================================
    # NodeService RPC Implementations (Distributed)
    # =========================================================================

    async def handle_sync_graph(
        self,
        request: hnsw_pb2.SyncGraphRequest
    ) -> hnsw_pb2.SyncGraphResponse:
        """
        Synchronize graph structure from another node.

        TODO: Implement graph synchronization for distributed HNSW:
        - Merge incoming nodes with local graph
        - Handle conflicts and version differences
        """
        response = hnsw_pb2.SyncGraphResponse()
        response.success = False
        response.nodes_synced = 0
        # TODO: Implement graph synchronization
        return response

    async def handle_forward_search(
        self,
        request: hnsw_pb2.ForwardSearchRequest
    ) -> hnsw_pb2.ForwardSearchResponse:
        """
        Handle forwarded search request from another node.

        Used in distributed scenarios where search is sharded across nodes.
        """
        response = hnsw_pb2.ForwardSearchResponse()
        response.served_by = self.node_id

        with self.lock:
            if self.index:
                results = self.index.search_knn(
                    list(request.query_vector),
                    request.k,
                    request.ef_search if request.ef_search > 0 else None
                )

                for vector_id, distance in results:
                    result = hnsw_pb2.SearchResult()
                    result.id = vector_id
                    result.distance = distance
                    response.results.append(result)

        return response

    async def handle_heartbeat(
        self,
        request: hnsw_pb2.HeartbeatRequest
    ) -> hnsw_pb2.HeartbeatResponse:
        """Handle heartbeat from peer node."""
        response = hnsw_pb2.HeartbeatResponse()
        response.acknowledged = True
        response.timestamp = int(time.time() * 1000)
        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class HNSWServicer(hnsw_pb2_grpc.HNSWServiceServicer):
    """gRPC service implementation for HNSW operations."""

    def __init__(self, node: HNSWNode):
        self.node = node

    async def CreateIndex(self, request, context):
        return await self.node.handle_create_index(request)

    async def Insert(self, request, context):
        return await self.node.handle_insert(request)

    async def BatchInsert(self, request, context):
        return await self.node.handle_batch_insert(request)

    async def Search(self, request, context):
        return await self.node.handle_search(request)

    async def Delete(self, request, context):
        return await self.node.handle_delete(request)

    async def GetStats(self, request, context):
        return await self.node.handle_get_stats(request)

    async def GetVector(self, request, context):
        return await self.node.handle_get_vector(request)


class NodeServicer(hnsw_pb2_grpc.NodeServiceServicer):
    """gRPC service implementation for distributed node operations."""

    def __init__(self, node: HNSWNode):
        self.node = node

    async def SyncGraph(self, request, context):
        return await self.node.handle_sync_graph(request)

    async def ForwardSearch(self, request, context):
        return await self.node.handle_forward_search(request)

    async def Heartbeat(self, request, context):
        return await self.node.handle_heartbeat(request)


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the HNSW node server."""
    node = HNSWNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    hnsw_pb2_grpc.add_HNSWServiceServicer_to_server(HNSWServicer(node), server)
    hnsw_pb2_grpc.add_NodeServiceServicer_to_server(NodeServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting HNSW node {node_id} on {listen_addr}")
    logger.info(f"Peers: {peers}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(
        description="HNSW Vector Index Node",
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
