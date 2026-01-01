"""
Rendezvous Hashing (Highest Random Weight) Implementation

Rendezvous hashing is a distributed hash technique that provides an alternative
to consistent hashing. For each key, it computes a weight for every node and
selects the node with the highest weight.

Key properties:
1. Deterministic: Same key always maps to the same node
2. Minimal disruption: Adding/removing nodes only affects keys that would
   map to those nodes
3. Even distribution: Keys are evenly distributed across nodes
4. Simple to implement: No need for virtual nodes or ring structure

Algorithm:
- For each key, compute weight(key, node) for all nodes
- Select the node with the highest weight
- Weight function: hash(key + node_id) converted to float

Your task: Implement the weight calculation and node selection logic.
"""

import grpc
from concurrent import futures
import hashlib
import struct
import os
import ssl
import threading
from typing import Dict, List, Tuple, Optional

import rendezvous_hashing_pb2 as pb2
import rendezvous_hashing_pb2_grpc as pb2_grpc


class RendezvousHashingNode:
    """
    Rendezvous Hashing implementation.

    Uses Highest Random Weight (HRW) algorithm to map keys to nodes.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.nodes: Dict[str, pb2.NodeInfo] = {}  # node_id -> NodeInfo
        self.local_store: Dict[str, bytes] = {}   # key -> value
        self.lock = threading.RLock()

    def calculate_weight(self, key: str, node_id: str, capacity_weight: float = 1.0) -> float:
        """
        Calculate the weight for a key-node pair.

        The weight should be deterministic and uniformly distributed.
        A common approach is to hash the concatenation of key and node_id,
        then convert to a floating point number.

        Args:
            key: The key to calculate weight for
            node_id: The node identifier
            capacity_weight: Optional multiplier for node capacity (default 1.0)

        Returns:
            A floating point weight value

        TODO: Implement the weight calculation
        Hint: Use hash(key + node_id), convert to a normalized float,
              and multiply by capacity_weight
        """
        # TODO: Implement weight calculation
        # 1. Concatenate key and node_id
        # 2. Hash the concatenated string (use MD5 or SHA256)
        # 3. Convert hash to a floating point number in range [0, 1)
        # 4. Multiply by capacity_weight
        pass

    def get_node_for_key(self, key: str) -> Tuple[Optional[str], float]:
        """
        Get the node with the highest weight for a given key.

        Args:
            key: The key to look up

        Returns:
            Tuple of (node_id, weight) or (None, 0.0) if no nodes exist

        TODO: Implement node selection using rendezvous hashing
        """
        with self.lock:
            if not self.nodes:
                return None, 0.0

            # TODO: Implement rendezvous hashing
            # 1. For each active node, calculate weight(key, node_id)
            # 2. Return the node with the highest weight
            pass

    def get_nodes_for_key(self, key: str, count: int) -> List[Tuple[str, float]]:
        """
        Get the top N nodes for a key (useful for replication).

        Args:
            key: The key to look up
            count: Number of nodes to return

        Returns:
            List of (node_id, weight) tuples, sorted by weight descending

        TODO: Implement multi-node selection
        """
        with self.lock:
            if not self.nodes:
                return []

            # TODO: Implement top-N node selection
            # 1. Calculate weights for all active nodes
            # 2. Sort by weight descending
            # 3. Return top 'count' nodes
            pass


class NodeRegistryServicer(pb2_grpc.NodeRegistryServiceServicer):
    """gRPC service for managing node registry."""

    def __init__(self, node: RendezvousHashingNode):
        self.node = node

    def AddNode(self, request, context):
        with self.node.lock:
            node_info = pb2.NodeInfo(
                node_id=request.node_id,
                address=request.address,
                port=request.port,
                capacity_weight=request.capacity_weight if request.capacity_weight > 0 else 1.0,
                is_active=True
            )
            self.node.nodes[request.node_id] = node_info
            return pb2.AddNodeResponse(
                success=True,
                message=f"Node {request.node_id} added successfully"
            )

    def RemoveNode(self, request, context):
        with self.node.lock:
            if request.node_id in self.node.nodes:
                del self.node.nodes[request.node_id]
                return pb2.RemoveNodeResponse(
                    success=True,
                    message=f"Node {request.node_id} removed",
                    keys_to_redistribute=0
                )
            return pb2.RemoveNodeResponse(
                success=False,
                message=f"Node {request.node_id} not found"
            )

    def ListNodes(self, request, context):
        with self.node.lock:
            return pb2.ListNodesResponse(nodes=list(self.node.nodes.values()))

    def GetNodeInfo(self, request, context):
        with self.node.lock:
            if request.node_id in self.node.nodes:
                return pb2.GetNodeInfoResponse(
                    node=self.node.nodes[request.node_id],
                    found=True
                )
            return pb2.GetNodeInfoResponse(found=False)


class RendezvousServicer(pb2_grpc.RendezvousServiceServicer):
    """gRPC service for rendezvous hashing operations."""

    def __init__(self, node: RendezvousHashingNode):
        self.node = node

    def GetNodeForKey(self, request, context):
        node_id, weight = self.node.get_node_for_key(request.key)
        if node_id:
            return pb2.GetNodeForKeyResponse(node_id=node_id, weight=weight)
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("No nodes available")
        return pb2.GetNodeForKeyResponse()

    def GetNodesForKey(self, request, context):
        nodes = self.node.get_nodes_for_key(request.key, request.count)
        return pb2.GetNodesForKeyResponse(
            nodes=[pb2.NodeWithWeight(node_id=n, weight=w) for n, w in nodes]
        )

    def CalculateWeight(self, request, context):
        with self.node.lock:
            capacity = 1.0
            if request.node_id in self.node.nodes:
                capacity = self.node.nodes[request.node_id].capacity_weight
            weight = self.node.calculate_weight(request.key, request.node_id, capacity)
            if weight is None:
                weight = 0.0
            return pb2.CalculateWeightResponse(weight=weight)


class KeyValueServicer(pb2_grpc.KeyValueServiceServicer):
    """gRPC service for key-value operations."""

    def __init__(self, node: RendezvousHashingNode):
        self.node = node

    def Put(self, request, context):
        with self.node.lock:
            # Store locally (in a real system, would forward to responsible node)
            self.node.local_store[request.key] = request.value
            return pb2.PutResponse(
                success=True,
                stored_on_nodes=[self.node.node_id]
            )

    def Get(self, request, context):
        with self.node.lock:
            if request.key in self.node.local_store:
                return pb2.GetResponse(
                    found=True,
                    value=self.node.local_store[request.key],
                    served_by_node=self.node.node_id
                )
            return pb2.GetResponse(found=False)

    def Delete(self, request, context):
        with self.node.lock:
            if request.key in self.node.local_store:
                del self.node.local_store[request.key]
                return pb2.DeleteResponse(success=True, deleted_from_nodes=1)
            return pb2.DeleteResponse(success=True, deleted_from_nodes=0)


def serve():
    """Start the gRPC server."""
    node_id = os.environ.get("NODE_ID", "node-0")
    port = os.environ.get("PORT", "50051")
    use_tls = os.environ.get("USE_TLS", "false").lower() == "true"

    node = RendezvousHashingNode(node_id)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_NodeRegistryServiceServicer_to_server(
        NodeRegistryServicer(node), server
    )
    pb2_grpc.add_RendezvousServiceServicer_to_server(
        RendezvousServicer(node), server
    )
    pb2_grpc.add_KeyValueServiceServicer_to_server(
        KeyValueServicer(node), server
    )

    if use_tls:
        # Load TLS credentials
        cert_path = os.environ.get("TLS_CERT_PATH", "/certs/server.crt")
        key_path = os.environ.get("TLS_KEY_PATH", "/certs/server.key")

        with open(cert_path, "rb") as f:
            cert = f.read()
        with open(key_path, "rb") as f:
            key = f.read()

        credentials = grpc.ssl_server_credentials([(key, cert)])
        server.add_secure_port(f"[::]:{port}", credentials)
        print(f"Rendezvous Hashing node {node_id} starting with TLS on port {port}")
    else:
        server.add_insecure_port(f"[::]:{port}")
        print(f"Rendezvous Hashing node {node_id} starting on port {port}")

    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
