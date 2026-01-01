"""
CRDT (Conflict-free Replicated Data Types) Implementation - Python Template

This template provides the basic structure for implementing
distributed CRDTs for eventual consistency.

Key concepts:
1. Updates can happen concurrently on any replica
2. Replicas can merge states without conflicts
3. All replicas converge to the same state eventually

Implemented CRDTs:
- G-Counter (grow-only counter)
- PN-Counter (positive-negative counter)
- G-Set (grow-only set)
- OR-Set (observed-remove set)
- LWW-Register (last-writer-wins register)

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any

import grpc
from grpc import aio

# Generated protobuf imports
import crdt_pb2
import crdt_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CRDTType(Enum):
    G_COUNTER = "G_COUNTER"
    PN_COUNTER = "PN_COUNTER"
    G_SET = "G_SET"
    OR_SET = "OR_SET"
    LWW_REGISTER = "LWW_REGISTER"


@dataclass
class VectorClock:
    """Vector clock for causality tracking."""
    clock: Dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str):
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: 'VectorClock'):
        for node_id, timestamp in other.clock.items():
            self.clock[node_id] = max(self.clock.get(node_id, 0), timestamp)

    def __ge__(self, other: 'VectorClock') -> bool:
        """Check if this clock dominates or equals other."""
        for node_id, timestamp in other.clock.items():
            if self.clock.get(node_id, 0) < timestamp:
                return False
        return True


class BaseCRDT(ABC):
    """Base class for all CRDTs."""

    def __init__(self, crdt_id: str, node_id: str):
        self.crdt_id = crdt_id
        self.node_id = node_id
        self.created_at = int(time.time() * 1000)
        self.last_updated = self.created_at

    @abstractmethod
    def merge(self, other: 'BaseCRDT') -> None:
        """Merge another CRDT state into this one."""
        pass

    @abstractmethod
    def get_value(self) -> Any:
        """Get the current value."""
        pass

    @abstractmethod
    def to_proto(self) -> crdt_pb2.CRDTState:
        """Convert to protobuf representation."""
        pass


class GCounter(BaseCRDT):
    """
    Grow-only Counter CRDT.

    TODO: Implement G-Counter:
    1. Each node maintains its own count
    2. Value = sum of all node counts
    3. Merge = take max of each node's count
    """

    def __init__(self, crdt_id: str, node_id: str):
        super().__init__(crdt_id, node_id)
        self.counts: Dict[str, int] = {}

    def increment(self, amount: int = 1):
        """Increment the counter."""
        self.counts[self.node_id] = self.counts.get(self.node_id, 0) + amount
        self.last_updated = int(time.time() * 1000)

    def get_value(self) -> int:
        """Get the counter value."""
        return sum(self.counts.values())

    def merge(self, other: 'GCounter'):
        """Merge another G-Counter."""
        for node_id, count in other.counts.items():
            self.counts[node_id] = max(self.counts.get(node_id, 0), count)
        self.last_updated = int(time.time() * 1000)

    def to_proto(self) -> crdt_pb2.CRDTState:
        return crdt_pb2.CRDTState(
            crdt_id=self.crdt_id,
            type=crdt_pb2.G_COUNTER,
            g_counter=crdt_pb2.GCounterState(counts=self.counts),
            created_at=self.created_at,
            last_updated=self.last_updated,
        )


class PNCounter(BaseCRDT):
    """
    Positive-Negative Counter CRDT.

    TODO: Implement PN-Counter:
    1. Two G-Counters: one for increments, one for decrements
    2. Value = sum(positive) - sum(negative)
    3. Merge = merge both G-Counters independently
    """

    def __init__(self, crdt_id: str, node_id: str):
        super().__init__(crdt_id, node_id)
        self.positive: Dict[str, int] = {}
        self.negative: Dict[str, int] = {}

    def increment(self, amount: int = 1):
        """Increment the counter."""
        self.positive[self.node_id] = self.positive.get(self.node_id, 0) + amount
        self.last_updated = int(time.time() * 1000)

    def decrement(self, amount: int = 1):
        """Decrement the counter."""
        self.negative[self.node_id] = self.negative.get(self.node_id, 0) + amount
        self.last_updated = int(time.time() * 1000)

    def get_value(self) -> int:
        """Get the counter value."""
        return sum(self.positive.values()) - sum(self.negative.values())

    def merge(self, other: 'PNCounter'):
        """Merge another PN-Counter."""
        for node_id, count in other.positive.items():
            self.positive[node_id] = max(self.positive.get(node_id, 0), count)
        for node_id, count in other.negative.items():
            self.negative[node_id] = max(self.negative.get(node_id, 0), count)
        self.last_updated = int(time.time() * 1000)

    def to_proto(self) -> crdt_pb2.CRDTState:
        return crdt_pb2.CRDTState(
            crdt_id=self.crdt_id,
            type=crdt_pb2.PN_COUNTER,
            pn_counter=crdt_pb2.PNCounterState(
                positive=self.positive,
                negative=self.negative,
            ),
            created_at=self.created_at,
            last_updated=self.last_updated,
        )


class GSet(BaseCRDT):
    """
    Grow-only Set CRDT.

    TODO: Implement G-Set:
    1. Elements can only be added, never removed
    2. Merge = union of sets
    """

    def __init__(self, crdt_id: str, node_id: str):
        super().__init__(crdt_id, node_id)
        self.elements: Set[str] = set()

    def add(self, element: str):
        """Add an element to the set."""
        self.elements.add(element)
        self.last_updated = int(time.time() * 1000)

    def contains(self, element: str) -> bool:
        """Check if element is in set."""
        return element in self.elements

    def get_value(self) -> Set[str]:
        """Get the set elements."""
        return self.elements.copy()

    def merge(self, other: 'GSet'):
        """Merge another G-Set."""
        self.elements = self.elements.union(other.elements)
        self.last_updated = int(time.time() * 1000)

    def to_proto(self) -> crdt_pb2.CRDTState:
        return crdt_pb2.CRDTState(
            crdt_id=self.crdt_id,
            type=crdt_pb2.G_SET,
            g_set=crdt_pb2.GSetState(elements=list(self.elements)),
            created_at=self.created_at,
            last_updated=self.last_updated,
        )


@dataclass
class ORSetElement:
    """Element in an OR-Set with unique tag."""
    value: str
    unique_tag: str
    added_by: str


class ORSet(BaseCRDT):
    """
    Observed-Remove Set CRDT.

    TODO: Implement OR-Set:
    1. Each add creates a unique tag
    2. Remove adds the tag to tombstones
    3. Element is present if any add tag is not tombstoned
    4. Merge = union of adds, union of tombstones
    """

    def __init__(self, crdt_id: str, node_id: str):
        super().__init__(crdt_id, node_id)
        self.elements: Dict[str, ORSetElement] = {}  # tag -> element
        self.tombstones: Set[str] = set()

    def add(self, value: str):
        """Add an element to the set."""
        tag = str(uuid.uuid4())
        self.elements[tag] = ORSetElement(
            value=value,
            unique_tag=tag,
            added_by=self.node_id,
        )
        self.last_updated = int(time.time() * 1000)

    def remove(self, value: str) -> bool:
        """Remove an element from the set."""
        removed = False
        tags_to_remove = [
            tag for tag, elem in self.elements.items()
            if elem.value == value and tag not in self.tombstones
        ]
        for tag in tags_to_remove:
            self.tombstones.add(tag)
            removed = True
        if removed:
            self.last_updated = int(time.time() * 1000)
        return removed

    def contains(self, value: str) -> bool:
        """Check if element is in set."""
        for tag, elem in self.elements.items():
            if elem.value == value and tag not in self.tombstones:
                return True
        return False

    def get_value(self) -> Set[str]:
        """Get the set elements."""
        return {
            elem.value for tag, elem in self.elements.items()
            if tag not in self.tombstones
        }

    def merge(self, other: 'ORSet'):
        """Merge another OR-Set."""
        # Union of elements
        for tag, elem in other.elements.items():
            if tag not in self.elements:
                self.elements[tag] = elem
        # Union of tombstones
        self.tombstones = self.tombstones.union(other.tombstones)
        self.last_updated = int(time.time() * 1000)

    def to_proto(self) -> crdt_pb2.CRDTState:
        elements = [
            crdt_pb2.ORSetElement(
                value=elem.value,
                unique_tag=elem.unique_tag,
                added_by=elem.added_by,
            )
            for elem in self.elements.values()
        ]
        return crdt_pb2.CRDTState(
            crdt_id=self.crdt_id,
            type=crdt_pb2.OR_SET,
            or_set=crdt_pb2.ORSetState(
                elements=elements,
                tombstones=list(self.tombstones),
            ),
            created_at=self.created_at,
            last_updated=self.last_updated,
        )


class LWWRegister(BaseCRDT):
    """
    Last-Writer-Wins Register CRDT.

    TODO: Implement LWW-Register:
    1. Each write has a timestamp
    2. Highest timestamp wins
    3. Merge = keep value with highest timestamp
    """

    def __init__(self, crdt_id: str, node_id: str):
        super().__init__(crdt_id, node_id)
        self.value: str = ""
        self.timestamp: int = 0
        self.writer: str = ""

    def set(self, value: str, timestamp: Optional[int] = None):
        """Set the register value."""
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        if timestamp > self.timestamp:
            self.value = value
            self.timestamp = timestamp
            self.writer = self.node_id
            self.last_updated = int(time.time() * 1000)

    def get_value(self) -> str:
        """Get the register value."""
        return self.value

    def merge(self, other: 'LWWRegister'):
        """Merge another LWW-Register."""
        if other.timestamp > self.timestamp:
            self.value = other.value
            self.timestamp = other.timestamp
            self.writer = other.writer
        self.last_updated = int(time.time() * 1000)

    def to_proto(self) -> crdt_pb2.CRDTState:
        return crdt_pb2.CRDTState(
            crdt_id=self.crdt_id,
            type=crdt_pb2.LWW_REGISTER,
            lww_register=crdt_pb2.LWWRegisterState(
                value=self.value,
                timestamp=self.timestamp,
                writer=self.writer,
            ),
            created_at=self.created_at,
            last_updated=self.last_updated,
        )


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    node_id: str
    address: str
    is_healthy: bool = True
    crdts_count: int = 0
    last_heartbeat: int = 0


class CRDTNode:
    """CRDT Node implementation."""

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # CRDT storage
        self.crdts: Dict[str, BaseCRDT] = {}

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_coordinator = False
        self.total_merges = 0

        # gRPC stubs
        self.peer_stubs: Dict[str, crdt_pb2_grpc.ReplicationServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = crdt_pb2_grpc.ReplicationServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"CRDT Node {self.node_id} initialized with peers: {self.peers}")

    def create_crdt(self, crdt_id: str, crdt_type: CRDTType) -> BaseCRDT:
        """Create a new CRDT."""
        with self.lock:
            if crdt_id in self.crdts:
                return self.crdts[crdt_id]

            if crdt_type == CRDTType.G_COUNTER:
                crdt = GCounter(crdt_id, self.node_id)
            elif crdt_type == CRDTType.PN_COUNTER:
                crdt = PNCounter(crdt_id, self.node_id)
            elif crdt_type == CRDTType.G_SET:
                crdt = GSet(crdt_id, self.node_id)
            elif crdt_type == CRDTType.OR_SET:
                crdt = ORSet(crdt_id, self.node_id)
            elif crdt_type == CRDTType.LWW_REGISTER:
                crdt = LWWRegister(crdt_id, self.node_id)
            else:
                raise ValueError(f"Unknown CRDT type: {crdt_type}")

            self.crdts[crdt_id] = crdt
            return crdt

    def get_crdt(self, crdt_id: str) -> Optional[BaseCRDT]:
        """Get a CRDT by ID."""
        with self.lock:
            return self.crdts.get(crdt_id)

    def merge_crdt(self, state: crdt_pb2.CRDTState):
        """Merge a CRDT state from another node."""
        with self.lock:
            crdt_type = CRDTType(crdt_pb2.CRDTType.Name(state.type))
            crdt = self.create_crdt(state.crdt_id, crdt_type)

            # Create temporary CRDT from proto and merge
            # This is simplified - real implementation would deserialize properly
            self.total_merges += 1


class CRDTServicer(crdt_pb2_grpc.CRDTServiceServicer):
    """gRPC service for CRDT operations."""

    def __init__(self, node: CRDTNode):
        self.node = node

    async def IncrementCounter(self, request, context):
        """Handle IncrementCounter RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.counter_id)
            if not crdt:
                crdt = self.node.create_crdt(request.counter_id, CRDTType.G_COUNTER)

            if isinstance(crdt, (GCounter, PNCounter)):
                crdt.increment(request.amount or 1)
                return crdt_pb2.IncrementCounterResponse(
                    success=True,
                    value=crdt.get_value(),
                    served_by=self.node.node_id,
                )
        return crdt_pb2.IncrementCounterResponse(success=False, error="Invalid counter")

    async def DecrementCounter(self, request, context):
        """Handle DecrementCounter RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.counter_id)
            if not crdt:
                crdt = self.node.create_crdt(request.counter_id, CRDTType.PN_COUNTER)

            if isinstance(crdt, PNCounter):
                crdt.decrement(request.amount or 1)
                return crdt_pb2.DecrementCounterResponse(
                    success=True,
                    value=crdt.get_value(),
                    served_by=self.node.node_id,
                )
        return crdt_pb2.DecrementCounterResponse(success=False, error="Not a PN-Counter")

    async def GetCounter(self, request, context):
        """Handle GetCounter RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.counter_id)
            if crdt and isinstance(crdt, (GCounter, PNCounter)):
                return crdt_pb2.GetCounterResponse(
                    value=crdt.get_value(),
                    found=True,
                    type=crdt_pb2.G_COUNTER if isinstance(crdt, GCounter) else crdt_pb2.PN_COUNTER,
                )
        return crdt_pb2.GetCounterResponse(found=False)

    async def AddToSet(self, request, context):
        """Handle AddToSet RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.set_id)
            if not crdt:
                crdt = self.node.create_crdt(request.set_id, CRDTType.OR_SET)

            if isinstance(crdt, (GSet, ORSet)):
                crdt.add(request.element)
                elements = crdt.get_value()
                return crdt_pb2.AddToSetResponse(
                    success=True,
                    size=len(elements),
                    served_by=self.node.node_id,
                )
        return crdt_pb2.AddToSetResponse(success=False, error="Invalid set")

    async def RemoveFromSet(self, request, context):
        """Handle RemoveFromSet RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.set_id)
            if crdt and isinstance(crdt, ORSet):
                was_present = crdt.remove(request.element)
                return crdt_pb2.RemoveFromSetResponse(
                    success=True,
                    was_present=was_present,
                    size=len(crdt.get_value()),
                    served_by=self.node.node_id,
                )
        return crdt_pb2.RemoveFromSetResponse(success=False, error="Not an OR-Set")

    async def GetSet(self, request, context):
        """Handle GetSet RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.set_id)
            if crdt and isinstance(crdt, (GSet, ORSet)):
                elements = crdt.get_value()
                return crdt_pb2.GetSetResponse(
                    elements=list(elements),
                    size=len(elements),
                    found=True,
                    type=crdt_pb2.G_SET if isinstance(crdt, GSet) else crdt_pb2.OR_SET,
                )
        return crdt_pb2.GetSetResponse(found=False)

    async def ContainsInSet(self, request, context):
        """Handle ContainsInSet RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.set_id)
            if crdt and isinstance(crdt, (GSet, ORSet)):
                return crdt_pb2.ContainsInSetResponse(
                    contains=crdt.contains(request.element),
                    found=True,
                )
        return crdt_pb2.ContainsInSetResponse(found=False)

    async def SetRegister(self, request, context):
        """Handle SetRegister RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.register_id)
            if not crdt:
                crdt = self.node.create_crdt(request.register_id, CRDTType.LWW_REGISTER)

            if isinstance(crdt, LWWRegister):
                crdt.set(request.value, request.timestamp if request.timestamp else None)
                return crdt_pb2.SetRegisterResponse(
                    success=True,
                    served_by=self.node.node_id,
                )
        return crdt_pb2.SetRegisterResponse(success=False, error="Invalid register")

    async def GetRegister(self, request, context):
        """Handle GetRegister RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.register_id)
            if crdt and isinstance(crdt, LWWRegister):
                return crdt_pb2.GetRegisterResponse(
                    values=[crdt.get_value()],
                    found=True,
                    type=crdt_pb2.LWW_REGISTER,
                )
        return crdt_pb2.GetRegisterResponse(found=False)

    async def CreateCRDT(self, request, context):
        """Handle CreateCRDT RPC."""
        crdt_type = CRDTType(crdt_pb2.CRDTType.Name(request.type))
        with self.node.lock:
            already_exists = request.crdt_id in self.node.crdts
            self.node.create_crdt(request.crdt_id, crdt_type)
        return crdt_pb2.CreateCRDTResponse(
            success=True,
            already_exists=already_exists,
        )

    async def DeleteCRDT(self, request, context):
        """Handle DeleteCRDT RPC."""
        with self.node.lock:
            if request.crdt_id in self.node.crdts:
                del self.node.crdts[request.crdt_id]
                return crdt_pb2.DeleteCRDTResponse(success=True)
        return crdt_pb2.DeleteCRDTResponse(success=False, error="CRDT not found")

    async def GetCRDTState(self, request, context):
        """Handle GetCRDTState RPC."""
        with self.node.lock:
            crdt = self.node.crdts.get(request.crdt_id)
            if crdt:
                return crdt_pb2.GetCRDTStateResponse(
                    state=crdt.to_proto(),
                    found=True,
                )
        return crdt_pb2.GetCRDTStateResponse(found=False)

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return crdt_pb2.GetLeaderResponse(
            node_id=self.node.node_id,
            node_address=f"localhost:{self.node.port}",
            is_coordinator=self.node.is_coordinator,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.node.lock:
            members = [
                crdt_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    crdts_count=n.crdts_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.node.nodes.values()
            ]

            return crdt_pb2.GetClusterStatusResponse(
                node_id=self.node.node_id,
                node_address=f"localhost:{self.node.port}",
                is_coordinator=self.node.is_coordinator,
                total_nodes=len(self.node.nodes),
                healthy_nodes=sum(1 for n in self.node.nodes.values() if n.is_healthy),
                total_crdts=len(self.node.crdts),
                total_merges=self.node.total_merges,
                members=members,
            )


class ReplicationServicer(crdt_pb2_grpc.ReplicationServiceServicer):
    """gRPC service for CRDT replication."""

    def __init__(self, node: CRDTNode):
        self.node = node

    async def Merge(self, request, context):
        """Handle Merge RPC."""
        self.node.merge_crdt(request.state)
        crdt = self.node.get_crdt(request.state.crdt_id)
        return crdt_pb2.MergeResponse(
            success=True,
            merged_state=crdt.to_proto() if crdt else None,
        )

    async def SyncAll(self, request, context):
        """Handle SyncAll RPC."""
        merged = 0
        new = 0
        for state in request.states:
            if state.crdt_id in self.node.crdts:
                self.node.merge_crdt(state)
                merged += 1
            else:
                self.node.merge_crdt(state)
                new += 1

        return crdt_pb2.SyncAllResponse(
            success=True,
            merged_count=merged,
            new_count=new,
        )

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.node.lock:
            if request.node_id not in self.node.nodes:
                self.node.nodes[request.node_id] = NodeInfo(
                    node_id=request.node_id,
                    address="",
                )
            self.node.nodes[request.node_id].last_heartbeat = request.timestamp
            self.node.nodes[request.node_id].crdts_count = request.crdts_count

        return crdt_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=int(time.time() * 1000),
        )

    async def GetLocalCRDTs(self, request, context):
        """Handle GetLocalCRDTs RPC."""
        with self.node.lock:
            crdts = [crdt.to_proto() for crdt in self.node.crdts.values()]
            return crdt_pb2.GetLocalCRDTsResponse(
                crdts=crdts,
                total_count=len(crdts),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the CRDT server."""
    node = CRDTNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    crdt_pb2_grpc.add_CRDTServiceServicer_to_server(CRDTServicer(node), server)
    crdt_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting CRDT node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="CRDT Node")
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
