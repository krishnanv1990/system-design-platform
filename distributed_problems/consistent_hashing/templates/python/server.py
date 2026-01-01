"""
Consistent Hashing Implementation - Python Template

This template provides the basic structure for implementing a
consistent hash ring for distributed key-value storage.

Key concepts:
1. Hash Ring - Keys and nodes are mapped to a circular hash space
2. Virtual Nodes - Each physical node has multiple positions on the ring
3. Lookup - Find the first node clockwise from the key's hash position
4. Rebalancing - When nodes join/leave, only nearby keys need to move

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import bisect
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from consistent_hashing.proto)
import consistent_hashing_pb2
import consistent_hashing_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default number of virtual nodes per physical node
DEFAULT_VIRTUAL_NODES = 150
DEFAULT_REPLICATION_FACTOR = 3


@dataclass
class VirtualNode:
    """Represents a virtual node on the hash ring."""
    node_id: str
    virtual_id: int
    hash_value: int


@dataclass
class NodeInfo:
    """Information about a physical node."""
    node_id: str
    address: str
    virtual_nodes: int = DEFAULT_VIRTUAL_NODES
    keys_count: int = 0
    is_healthy: bool = True
    last_heartbeat: int = 0


@dataclass
class HashRingState:
    """State of the consistent hash ring."""
    # Physical nodes: node_id -> NodeInfo
    nodes: Dict[str, NodeInfo] = field(default_factory=dict)

    # Virtual nodes sorted by hash value for binary search
    vnodes: List[VirtualNode] = field(default_factory=list)
    vnode_hashes: List[int] = field(default_factory=list)

    # Configuration
    replication_factor: int = DEFAULT_REPLICATION_FACTOR
    virtual_nodes_per_node: int = DEFAULT_VIRTUAL_NODES


class ConsistentHashRing:
    """
    Consistent Hash Ring implementation.

    TODO: Implement the core consistent hashing algorithm:
    1. hash() - Hash a key to a position on the ring
    2. add_node() - Add a node with virtual nodes to the ring
    3. remove_node() - Remove a node and its virtual nodes
    4. get_node() - Find the node responsible for a key
    5. get_nodes() - Find N nodes for replication
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.state = HashRingState()
        self.lock = threading.RLock()

        # Local key-value store
        self.kv_store: Dict[str, str] = {}

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, consistent_hashing_pb2_grpc.NodeServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            # Cloud Run URLs require SSL credentials
            if ".run.app" in peer:
                import ssl
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
                logger.info(f"Using SSL for peer: {peer}")
            else:
                channel = aio.insecure_channel(peer)
                logger.info(f"Using insecure channel for peer: {peer}")
            self.peer_stubs[peer] = consistent_hashing_pb2_grpc.NodeServiceStub(channel)

        # Add self to the ring
        self_address = f"localhost:{self.port}"
        self.add_node(self.node_id, self_address, DEFAULT_VIRTUAL_NODES)
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def hash(self, key: str) -> int:
        """
        Hash a key to a position on the ring.

        TODO: Implement consistent hashing function:
        - Use a good hash function (MD5, SHA-1, etc.)
        - Return a value in the ring's hash space
        - Must be deterministic (same key always hashes to same position)
        """
        # Example implementation using MD5
        h = hashlib.md5(key.encode()).hexdigest()
        return int(h, 16)

    def _get_vnode_hash(self, node_id: str, virtual_id: int) -> int:
        """Generate hash for a virtual node."""
        key = f"{node_id}:{virtual_id}"
        return self.hash(key)

    def add_node(self, node_id: str, address: str, num_vnodes: int = DEFAULT_VIRTUAL_NODES) -> List[VirtualNode]:
        """
        Add a node to the hash ring.

        TODO: Implement node addition:
        1. Create virtual nodes for this physical node
        2. Insert virtual nodes into the ring (maintain sorted order)
        3. Return list of added virtual nodes

        Args:
            node_id: Unique identifier for the node
            address: Network address of the node
            num_vnodes: Number of virtual nodes to create

        Returns:
            List of VirtualNode objects that were added
        """
        with self.lock:
            # Check if node already exists
            if node_id in self.state.nodes:
                return []

            # Create node info
            node_info = NodeInfo(
                node_id=node_id,
                address=address,
                virtual_nodes=num_vnodes,
            )
            self.state.nodes[node_id] = node_info

            # Create virtual nodes
            added_vnodes = []
            for i in range(num_vnodes):
                vnode_hash = self._get_vnode_hash(node_id, i)
                vnode = VirtualNode(
                    node_id=node_id,
                    virtual_id=i,
                    hash_value=vnode_hash,
                )
                added_vnodes.append(vnode)

                # Insert maintaining sorted order
                idx = bisect.bisect_left(self.state.vnode_hashes, vnode_hash)
                self.state.vnode_hashes.insert(idx, vnode_hash)
                self.state.vnodes.insert(idx, vnode)

            logger.info(f"Added node {node_id} with {num_vnodes} virtual nodes")
            return added_vnodes

    def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the hash ring.

        TODO: Implement node removal:
        1. Remove all virtual nodes for this physical node
        2. Update the ring structure
        3. Return True if successful

        Args:
            node_id: Unique identifier of the node to remove

        Returns:
            True if node was removed, False if not found
        """
        with self.lock:
            if node_id not in self.state.nodes:
                return False

            # Remove virtual nodes
            new_vnodes = []
            new_hashes = []
            for vnode, h in zip(self.state.vnodes, self.state.vnode_hashes):
                if vnode.node_id != node_id:
                    new_vnodes.append(vnode)
                    new_hashes.append(h)

            self.state.vnodes = new_vnodes
            self.state.vnode_hashes = new_hashes
            del self.state.nodes[node_id]

            logger.info(f"Removed node {node_id}")
            return True

    def get_node(self, key: str) -> Optional[NodeInfo]:
        """
        Get the node responsible for a key.

        TODO: Implement key lookup:
        1. Hash the key to find its position on the ring
        2. Find the first node clockwise from that position
        3. Handle wrap-around (if key hash > max vnode hash, use first node)

        Args:
            key: The key to look up

        Returns:
            NodeInfo for the responsible node, or None if ring is empty
        """
        with self.lock:
            if not self.state.vnodes:
                return None

            key_hash = self.hash(key)

            # Binary search to find first vnode with hash >= key_hash
            idx = bisect.bisect_left(self.state.vnode_hashes, key_hash)

            # Wrap around if necessary
            if idx >= len(self.state.vnodes):
                idx = 0

            vnode = self.state.vnodes[idx]
            return self.state.nodes.get(vnode.node_id)

    def get_nodes(self, key: str, count: int = 3) -> List[NodeInfo]:
        """
        Get multiple nodes for a key (for replication).

        TODO: Implement multi-node lookup:
        1. Find the primary node for the key
        2. Walk clockwise to find additional unique physical nodes
        3. Return up to 'count' unique physical nodes

        Args:
            key: The key to look up
            count: Number of nodes to return

        Returns:
            List of NodeInfo for responsible nodes
        """
        with self.lock:
            if not self.state.vnodes:
                return []

            key_hash = self.hash(key)
            idx = bisect.bisect_left(self.state.vnode_hashes, key_hash)

            result = []
            seen_nodes = set()

            # Walk around the ring until we have enough unique nodes
            ring_size = len(self.state.vnodes)
            for i in range(ring_size):
                vnode = self.state.vnodes[(idx + i) % ring_size]
                if vnode.node_id not in seen_nodes:
                    seen_nodes.add(vnode.node_id)
                    node_info = self.state.nodes.get(vnode.node_id)
                    if node_info:
                        result.append(node_info)
                    if len(result) >= count:
                        break

            return result

    def get_key_hash(self, key: str) -> int:
        """Get the hash value for a key."""
        return self.hash(key)


class HashRingServicer(consistent_hashing_pb2_grpc.HashRingServiceServicer):
    """gRPC service implementation for hash ring operations."""

    def __init__(self, ring: ConsistentHashRing):
        self.ring = ring

    async def AddNode(self, request, context):
        """Handle AddNode RPC."""
        vnodes = self.ring.add_node(
            request.node_id,
            request.address,
            request.virtual_nodes or DEFAULT_VIRTUAL_NODES
        )
        return consistent_hashing_pb2.AddNodeResponse(
            success=True,
            added_vnodes=[
                consistent_hashing_pb2.VirtualNode(
                    node_id=v.node_id,
                    virtual_id=v.virtual_id,
                    hash_value=v.hash_value
                )
                for v in vnodes
            ]
        )

    async def RemoveNode(self, request, context):
        """Handle RemoveNode RPC."""
        success = self.ring.remove_node(request.node_id)
        return consistent_hashing_pb2.RemoveNodeResponse(
            success=success,
            error="" if success else "Node not found"
        )

    async def GetNode(self, request, context):
        """Handle GetNode RPC."""
        node = self.ring.get_node(request.key)
        if node:
            return consistent_hashing_pb2.GetNodeResponse(
                node_id=node.node_id,
                node_address=node.address,
                key_hash=self.ring.get_key_hash(request.key)
            )
        return consistent_hashing_pb2.GetNodeResponse(
            error="Ring is empty"
        )

    async def GetNodes(self, request, context):
        """Handle GetNodes RPC."""
        nodes = self.ring.get_nodes(request.key, request.count or 3)
        return consistent_hashing_pb2.GetNodesResponse(
            nodes=[
                consistent_hashing_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    virtual_nodes=n.virtual_nodes,
                    keys_count=n.keys_count,
                    is_healthy=n.is_healthy
                )
                for n in nodes
            ],
            key_hash=self.ring.get_key_hash(request.key)
        )

    async def GetRingState(self, request, context):
        """Handle GetRingState RPC."""
        with self.ring.lock:
            return consistent_hashing_pb2.GetRingStateResponse(
                nodes=[
                    consistent_hashing_pb2.NodeInfo(
                        node_id=n.node_id,
                        address=n.address,
                        virtual_nodes=n.virtual_nodes,
                        keys_count=n.keys_count,
                        is_healthy=n.is_healthy
                    )
                    for n in self.ring.state.nodes.values()
                ],
                vnodes=[
                    consistent_hashing_pb2.VirtualNode(
                        node_id=v.node_id,
                        virtual_id=v.virtual_id,
                        hash_value=v.hash_value
                    )
                    for v in self.ring.state.vnodes
                ],
                total_keys=sum(n.keys_count for n in self.ring.state.nodes.values()),
                replication_factor=self.ring.state.replication_factor
            )

    async def Rebalance(self, request, context):
        """Handle Rebalance RPC."""
        # TODO: Implement rebalancing logic
        return consistent_hashing_pb2.RebalanceResponse(
            success=True,
            keys_moved=0
        )


class KeyValueServicer(consistent_hashing_pb2_grpc.KeyValueServiceServicer):
    """gRPC service implementation for key-value operations."""

    def __init__(self, ring: ConsistentHashRing):
        self.ring = ring

    async def Get(self, request, context):
        """Handle Get RPC."""
        with self.ring.lock:
            value = self.ring.kv_store.get(request.key)
            return consistent_hashing_pb2.GetResponse(
                value=value or "",
                found=value is not None,
                served_by=self.ring.node_id
            )

    async def Put(self, request, context):
        """
        Handle Put RPC.

        TODO: Implement distributed put:
        1. Determine which node should store this key
        2. If this node is responsible, store locally
        3. If another node is responsible, forward the request
        4. Handle replication to multiple nodes
        """
        with self.ring.lock:
            self.ring.kv_store[request.key] = request.value
            self.ring.state.nodes[self.ring.node_id].keys_count = len(self.ring.kv_store)
            return consistent_hashing_pb2.PutResponse(
                success=True,
                stored_on=self.ring.node_id
            )

    async def Delete(self, request, context):
        """Handle Delete RPC."""
        with self.ring.lock:
            if request.key in self.ring.kv_store:
                del self.ring.kv_store[request.key]
                self.ring.state.nodes[self.ring.node_id].keys_count = len(self.ring.kv_store)
                return consistent_hashing_pb2.DeleteResponse(success=True)
            return consistent_hashing_pb2.DeleteResponse(
                success=False,
                error="Key not found"
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return consistent_hashing_pb2.GetLeaderResponse(
            node_id=self.ring.node_id,
            node_address=f"localhost:{self.ring.port}",
            is_coordinator=True  # In consistent hashing, there's typically no single leader
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.ring.lock:
            nodes = list(self.ring.state.nodes.values())
            total_keys = sum(n.keys_count for n in nodes)
            healthy_nodes = sum(1 for n in nodes if n.is_healthy)

            return consistent_hashing_pb2.GetClusterStatusResponse(
                node_id=self.ring.node_id,
                node_address=f"localhost:{self.ring.port}",
                is_coordinator=True,
                total_nodes=len(nodes),
                healthy_nodes=healthy_nodes,
                total_keys=total_keys,
                replication_factor=self.ring.state.replication_factor,
                virtual_nodes_per_node=self.ring.state.virtual_nodes_per_node,
                members=[
                    consistent_hashing_pb2.NodeInfo(
                        node_id=n.node_id,
                        address=n.address,
                        virtual_nodes=n.virtual_nodes,
                        keys_count=n.keys_count,
                        is_healthy=n.is_healthy
                    )
                    for n in nodes
                ]
            )


class NodeServicer(consistent_hashing_pb2_grpc.NodeServiceServicer):
    """gRPC service implementation for inter-node communication."""

    def __init__(self, ring: ConsistentHashRing):
        self.ring = ring

    async def TransferKeys(self, request, context):
        """Handle TransferKeys RPC."""
        with self.ring.lock:
            for kv in request.keys:
                self.ring.kv_store[kv.key] = kv.value
            self.ring.state.nodes[self.ring.node_id].keys_count = len(self.ring.kv_store)
            return consistent_hashing_pb2.TransferKeysResponse(
                success=True,
                keys_received=len(request.keys)
            )

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        import time
        return consistent_hashing_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=int(time.time() * 1000)
        )

    async def GetLocalKeys(self, request, context):
        """Handle GetLocalKeys RPC."""
        with self.ring.lock:
            keys = [
                consistent_hashing_pb2.KeyValuePair(
                    key=k,
                    value=v,
                    hash=self.ring.hash(k)
                )
                for k, v in self.ring.kv_store.items()
            ]
            return consistent_hashing_pb2.GetLocalKeysResponse(
                keys=keys,
                total_count=len(keys)
            )

    async def StoreLocal(self, request, context):
        """Handle StoreLocal RPC."""
        with self.ring.lock:
            self.ring.kv_store[request.key] = request.value
            self.ring.state.nodes[self.ring.node_id].keys_count = len(self.ring.kv_store)
            return consistent_hashing_pb2.StoreLocalResponse(success=True)

    async def DeleteLocal(self, request, context):
        """Handle DeleteLocal RPC."""
        with self.ring.lock:
            if request.key in self.ring.kv_store:
                del self.ring.kv_store[request.key]
                self.ring.state.nodes[self.ring.node_id].keys_count = len(self.ring.kv_store)
                return consistent_hashing_pb2.DeleteLocalResponse(success=True)
            return consistent_hashing_pb2.DeleteLocalResponse(
                success=False,
                error="Key not found"
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the consistent hashing server."""
    ring = ConsistentHashRing(node_id, port, peers)
    await ring.initialize()

    server = aio.server()
    consistent_hashing_pb2_grpc.add_HashRingServiceServicer_to_server(
        HashRingServicer(ring), server
    )
    consistent_hashing_pb2_grpc.add_KeyValueServiceServicer_to_server(
        KeyValueServicer(ring), server
    )
    consistent_hashing_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(ring), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Consistent Hashing node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Consistent Hashing Node")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument(
        "--peers",
        required=True,
        help="Comma-separated list of peer addresses (host:port)",
    )
    args = parser.parse_args()

    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    asyncio.run(serve(args.node_id, args.port, peers))


if __name__ == "__main__":
    main()
