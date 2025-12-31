"""
Paxos Consensus Implementation - Python Template

This template provides the basic structure for implementing the Multi-Paxos
consensus algorithm. You need to implement the TODO sections.

For the full Paxos specification, see: "Paxos Made Simple" by Leslie Lamport

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from paxos.proto)
import paxos_pb2
import paxos_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeRole(Enum):
    PROPOSER = "proposer"
    ACCEPTOR = "acceptor"
    LEARNER = "learner"
    LEADER = "leader"


@dataclass
class ProposalNumber:
    """Represents a proposal number for ordering."""
    round: int
    proposer_id: str

    def __lt__(self, other: 'ProposalNumber') -> bool:
        if self.round != other.round:
            return self.round < other.round
        return self.proposer_id < other.proposer_id

    def __le__(self, other: 'ProposalNumber') -> bool:
        return self == other or self < other

    def __eq__(self, other: 'ProposalNumber') -> bool:
        return self.round == other.round and self.proposer_id == other.proposer_id

    def to_proto(self) -> paxos_pb2.ProposalNumber:
        return paxos_pb2.ProposalNumber(round=self.round, proposer_id=self.proposer_id)

    @classmethod
    def from_proto(cls, proto: paxos_pb2.ProposalNumber) -> 'ProposalNumber':
        return cls(round=proto.round, proposer_id=proto.proposer_id)


@dataclass
class AcceptorState:
    """State maintained by an acceptor for each slot."""
    highest_promised: Optional[ProposalNumber] = None
    accepted_proposal: Optional[ProposalNumber] = None
    accepted_value: Optional[bytes] = None


@dataclass
class PaxosState:
    """Persistent and volatile state for a Paxos node."""
    # Current round number for proposals
    current_round: int = 0

    # Per-slot acceptor state
    acceptor_states: Dict[int, AcceptorState] = field(default_factory=dict)

    # Learned values per slot
    learned_values: Dict[int, bytes] = field(default_factory=dict)

    # First slot that hasn't been chosen yet
    first_unchosen_slot: int = 0

    # Last slot that was executed on the state machine
    last_executed_slot: int = 0


class PaxosNode:
    """
    Paxos consensus node implementation.

    TODO: Implement the core Paxos algorithm:
    1. Phase 1 (Prepare): Proposer sends prepare, acceptors promise
    2. Phase 2 (Accept): Proposer sends accept, acceptors accept
    3. Learning: Once value is chosen, notify learners
    4. Multi-Paxos: Leader election and optimization
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.state = PaxosState()
        self.role = NodeRole.ACCEPTOR
        self.leader_id: Optional[str] = None

        # Key-value store (state machine)
        self.kv_store: Dict[str, str] = {}

        # Timing configuration
        self.heartbeat_interval = 0.1  # 100ms
        self.leader_timeout = 0.5     # 500ms

        # Synchronization
        self.lock = threading.RLock()

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, paxos_pb2_grpc.PaxosServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = paxos_pb2_grpc.PaxosServiceStub(channel)
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def get_acceptor_state(self, slot: int) -> AcceptorState:
        """Get or create acceptor state for a slot."""
        if slot not in self.state.acceptor_states:
            self.state.acceptor_states[slot] = AcceptorState()
        return self.state.acceptor_states[slot]

    def generate_proposal_number(self) -> ProposalNumber:
        """Generate a new proposal number higher than any seen."""
        self.state.current_round += 1
        return ProposalNumber(round=self.state.current_round, proposer_id=self.node_id)

    # =========================================================================
    # Phase 1: Prepare
    # =========================================================================

    async def send_prepare(self, slot: int, proposal: ProposalNumber) -> Tuple[bool, Optional[bytes]]:
        """
        Send Prepare requests to all acceptors.

        TODO: Implement Phase 1a of Paxos:
        1. Send Prepare(n) to all acceptors
        2. Wait for responses from a majority
        3. If majority promise, return (True, highest_accepted_value)
        4. If any acceptor has accepted a value, use that value
        """
        pass

    async def handle_prepare(
        self, request: paxos_pb2.PrepareRequest
    ) -> paxos_pb2.PrepareResponse:
        """
        Handle Prepare RPC from a proposer.

        TODO: Implement Phase 1b of Paxos:
        1. If n > highest_promised, update highest_promised and promise
        2. Return (promised=True, accepted_proposal, accepted_value)
        3. Otherwise return (promised=False, highest_promised)
        """
        with self.lock:
            response = paxos_pb2.PrepareResponse()
            slot = request.slot
            proposal = ProposalNumber.from_proto(request.proposal_number)
            acceptor_state = self.get_acceptor_state(slot)

            # TODO: Implement prepare logic
            response.promised = False

            return response

    # =========================================================================
    # Phase 2: Accept
    # =========================================================================

    async def send_accept(self, slot: int, proposal: ProposalNumber, value: bytes) -> bool:
        """
        Send Accept requests to all acceptors.

        TODO: Implement Phase 2a of Paxos:
        1. Send Accept(n, v) to all acceptors
        2. Wait for responses from a majority
        3. If majority accept, value is chosen - notify learners
        4. Return True if value was chosen
        """
        pass

    async def handle_accept(
        self, request: paxos_pb2.AcceptRequest
    ) -> paxos_pb2.AcceptResponse:
        """
        Handle Accept RPC from a proposer.

        TODO: Implement Phase 2b of Paxos:
        1. If n >= highest_promised, accept the value
        2. Update accepted_proposal and accepted_value
        3. Return (accepted=True)
        4. Otherwise return (accepted=False, highest_promised)
        """
        with self.lock:
            response = paxos_pb2.AcceptResponse()
            slot = request.slot
            proposal = ProposalNumber.from_proto(request.proposal_number)
            acceptor_state = self.get_acceptor_state(slot)

            # TODO: Implement accept logic
            response.accepted = False

            return response

    # =========================================================================
    # Learning
    # =========================================================================

    async def handle_learn(
        self, request: paxos_pb2.LearnRequest
    ) -> paxos_pb2.LearnResponse:
        """
        Handle Learn RPC - a value has been chosen.

        TODO: Implement learning:
        1. Store the learned value for the slot
        2. If this fills a gap, execute commands in order
        """
        with self.lock:
            response = paxos_pb2.LearnResponse()
            slot = request.slot
            value = request.value

            # TODO: Implement learn logic
            response.success = True

            return response

    def apply_command(self, command: bytes, command_type: str):
        """Apply a command to the state machine (key-value store)."""
        # TODO: Parse and apply the command
        pass

    # =========================================================================
    # Multi-Paxos Leader Election
    # =========================================================================

    async def handle_heartbeat(
        self, request: paxos_pb2.HeartbeatRequest
    ) -> paxos_pb2.HeartbeatResponse:
        """Handle heartbeat from current leader."""
        with self.lock:
            response = paxos_pb2.HeartbeatResponse()
            # TODO: Implement leader acknowledgment
            response.acknowledged = True
            return response

    async def run_as_leader(self):
        """
        Run as the Multi-Paxos leader.

        TODO: Implement Multi-Paxos optimization:
        1. Skip Phase 1 for consecutive slots after becoming leader
        2. Send heartbeats to maintain leadership
        3. Handle client requests directly
        """
        pass

    # =========================================================================
    # KeyValueService RPC Implementations
    # =========================================================================

    async def handle_get(self, request: paxos_pb2.GetRequest) -> paxos_pb2.GetResponse:
        """Handle Get RPC - returns value for key from state machine."""
        response = paxos_pb2.GetResponse()
        with self.lock:
            if request.key in self.kv_store:
                response.value = self.kv_store[request.key]
                response.found = True
            else:
                response.found = False
        return response

    async def handle_put(self, request: paxos_pb2.PutRequest) -> paxos_pb2.PutResponse:
        """
        Handle Put RPC - stores key-value pair.

        TODO: Implement consensus-based put:
        1. If not leader, return leader_hint
        2. Run Paxos to agree on this operation
        3. Apply to state machine once chosen
        """
        response = paxos_pb2.PutResponse()
        with self.lock:
            if self.role != NodeRole.LEADER:
                response.success = False
                response.error = "Not the leader"
                response.leader_hint = self.leader_id or ""
                return response

            # TODO: Implement consensus-based put
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_delete(
        self, request: paxos_pb2.DeleteRequest
    ) -> paxos_pb2.DeleteResponse:
        """Handle Delete RPC - removes key."""
        response = paxos_pb2.DeleteResponse()
        with self.lock:
            if self.role != NodeRole.LEADER:
                response.success = False
                response.error = "Not the leader"
                response.leader_hint = self.leader_id or ""
                return response

            # TODO: Implement consensus-based delete
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_get_leader(
        self, request: paxos_pb2.GetLeaderRequest
    ) -> paxos_pb2.GetLeaderResponse:
        """Return current leader information."""
        response = paxos_pb2.GetLeaderResponse()
        with self.lock:
            response.leader_id = self.leader_id or ""
            response.is_leader = self.role == NodeRole.LEADER
            if self.leader_id:
                for peer in self.peers:
                    if self.leader_id in peer:
                        response.leader_address = peer
                        break
        return response

    async def handle_get_cluster_status(
        self, request: paxos_pb2.GetClusterStatusRequest
    ) -> paxos_pb2.GetClusterStatusResponse:
        """Return cluster status information."""
        response = paxos_pb2.GetClusterStatusResponse()
        with self.lock:
            response.node_id = self.node_id
            response.role = self.role.value
            response.current_slot = self.state.first_unchosen_slot
            response.highest_promised_round = self.state.current_round
            response.first_unchosen_slot = self.state.first_unchosen_slot
            response.last_executed_slot = self.state.last_executed_slot

            for peer in self.peers:
                member = paxos_pb2.ClusterMember()
                member.address = peer
                response.members.append(member)

        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class PaxosServicer(paxos_pb2_grpc.PaxosServiceServicer):
    """gRPC service implementation for Paxos RPCs."""

    def __init__(self, node: PaxosNode):
        self.node = node

    async def Prepare(self, request, context):
        return await self.node.handle_prepare(request)

    async def Accept(self, request, context):
        return await self.node.handle_accept(request)

    async def Learn(self, request, context):
        return await self.node.handle_learn(request)

    async def Heartbeat(self, request, context):
        return await self.node.handle_heartbeat(request)


class KeyValueServicer(paxos_pb2_grpc.KeyValueServiceServicer):
    """gRPC service implementation for Key-Value store."""

    def __init__(self, node: PaxosNode):
        self.node = node

    async def Get(self, request, context):
        return await self.node.handle_get(request)

    async def Put(self, request, context):
        return await self.node.handle_put(request)

    async def Delete(self, request, context):
        return await self.node.handle_delete(request)

    async def GetLeader(self, request, context):
        return await self.node.handle_get_leader(request)

    async def GetClusterStatus(self, request, context):
        return await self.node.handle_get_cluster_status(request)


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the Paxos node server."""
    node = PaxosNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    paxos_pb2_grpc.add_PaxosServiceServicer_to_server(PaxosServicer(node), server)
    paxos_pb2_grpc.add_KeyValueServiceServicer_to_server(KeyValueServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Paxos node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Paxos Consensus Node")
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
