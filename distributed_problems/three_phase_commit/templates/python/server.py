"""
Three-Phase Commit (3PC) Implementation - Python Template

This template provides the basic structure for implementing
the Three-Phase Commit protocol for distributed transactions.

Key concepts:
1. Phase 1 (CanCommit): Coordinator asks if participants can commit
2. Phase 2 (PreCommit): If all agree, coordinator sends pre-commit
3. Phase 3 (DoCommit): Coordinator sends final commit/abort

Improvement over 2PC: Non-blocking - participants can recover from
coordinator failure by communicating with each other.

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import grpc
from grpc import aio

# Generated protobuf imports
import three_phase_commit_pb2
import three_phase_commit_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionState(Enum):
    """Transaction states."""
    INITIATED = "INITIATED"
    WAITING = "WAITING"
    PRECOMMIT = "PRECOMMIT"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"


class ParticipantState(Enum):
    """Participant states."""
    INITIAL = "INITIAL"
    UNCERTAIN = "UNCERTAIN"      # Voted YES, waiting for PreCommit
    PRECOMMITTED = "PRECOMMITTED"  # Received PreCommit
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class Transaction:
    """Transaction record."""
    transaction_id: str
    state: TransactionState
    participants: List[str]
    coordinator: str
    data: Dict[str, str] = field(default_factory=dict)
    start_time: int = 0
    last_update: int = 0
    timeout_ms: int = 30000


@dataclass
class ParticipantInfo:
    """Participant's local state for a transaction."""
    node_id: str
    transaction_id: str
    state: ParticipantState
    vote: bool = False  # True = YES
    last_update: int = 0


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    node_id: str
    address: str
    is_healthy: bool = True
    is_coordinator: bool = False
    last_heartbeat: int = 0


class ThreePhaseCommitNode:
    """
    Three-Phase Commit implementation.

    TODO: Implement the 3PC protocol:
    1. can_commit() - Phase 1: Check if this node can commit
    2. pre_commit() - Phase 2: Prepare to commit
    3. do_commit() - Phase 3: Actually commit
    4. do_abort() - Abort the transaction
    5. recovery() - Recover from coordinator failure
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Transaction storage (as coordinator)
        self.transactions: Dict[str, Transaction] = {}

        # Participant state (as participant)
        self.participant_states: Dict[str, ParticipantInfo] = {}

        # Local data store (simulated)
        self.data_store: Dict[str, str] = {}
        self.pending_writes: Dict[str, Dict[str, str]] = {}  # tx_id -> writes

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_coordinator = False
        self.current_term = 0

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, tuple] = {}  # peer -> (participant_stub, node_stub)

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = (
                three_phase_commit_pb2_grpc.ParticipantServiceStub(channel),
                three_phase_commit_pb2_grpc.NodeServiceStub(channel),
            )

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )

        # Simple leader election: lowest node_id is coordinator
        all_nodes = [self.node_id] + [p.split(":")[0] for p in self.peers if p]
        all_nodes.sort()
        if all_nodes and all_nodes[0] == self.node_id:
            self.is_coordinator = True

        logger.info(f"Node {self.node_id} initialized, is_coordinator={self.is_coordinator}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    # =========================================================================
    # Coordinator Methods
    # =========================================================================

    async def begin_transaction(self, participants: List[str], data: Dict[str, str]) -> Transaction:
        """
        Begin a new distributed transaction.

        TODO: Implement transaction initiation:
        1. Create transaction record
        2. Store pending writes
        3. Return transaction info
        """
        tx_id = str(uuid.uuid4())
        now = self._current_time_ms()

        tx = Transaction(
            transaction_id=tx_id,
            state=TransactionState.INITIATED,
            participants=participants,
            coordinator=self.node_id,
            data=data,
            start_time=now,
            last_update=now,
        )

        with self.lock:
            self.transactions[tx_id] = tx
            self.pending_writes[tx_id] = data.copy()

        logger.info(f"Started transaction {tx_id} with participants {participants}")
        return tx

    async def commit_transaction(self, tx_id: str) -> tuple:
        """
        Execute 3PC to commit a transaction.

        TODO: Implement 3PC commit:
        Phase 1: Send CanCommit to all participants
        Phase 2: If all vote YES, send PreCommit
        Phase 3: Send DoCommit

        Returns:
            Tuple of (success, final_state, participant_states)
        """
        # TODO: Implement this method
        # 1. Phase 1 (CanCommit): Send CanCommit to all participants
        # 2. If all vote YES, proceed to Phase 2
        # 3. Phase 2 (PreCommit): Send PreCommit to all participants
        # 4. If all acknowledge, proceed to Phase 3
        # 5. Phase 3 (DoCommit): Send DoCommit to all participants
        # 6. Return (success, final_state, participant_states)
        return (False, None, {})

    async def _abort_transaction(self, tx_id: str, reason: str):
        """
        Send abort to all participants.

        TODO: Implement abort:
        1. Update transaction state to ABORTING
        2. Send DoAbort to all participants
        3. Update transaction state to ABORTED
        """
        # TODO: Implement this method
        pass

    # =========================================================================
    # Participant Methods (local execution)
    # =========================================================================

    def _local_can_commit(self, tx_id: str, data: Dict[str, str]) -> bool:
        """
        Local CanCommit check.

        TODO: Implement validation:
        1. Check if transaction can be committed
        2. Validate data
        3. Acquire any necessary locks
        4. Store pending writes
        5. Return True if can commit, False otherwise
        """
        # TODO: Implement this method
        return False

    def _local_pre_commit(self, tx_id: str) -> bool:
        """
        Local PreCommit handling.

        TODO: Implement pre-commit:
        1. Update participant state to PRECOMMITTED
        2. Return True if successful
        """
        # TODO: Implement this method
        return False

    def _local_do_commit(self, tx_id: str) -> bool:
        """
        Local DoCommit execution.

        TODO: Implement commit:
        1. Apply pending writes to data store
        2. Release locks
        3. Clean up transaction state
        4. Update participant state to COMMITTED
        """
        # TODO: Implement this method
        return False

    def _local_do_abort(self, tx_id: str) -> bool:
        """
        Local DoAbort execution.

        TODO: Implement abort:
        1. Discard pending writes
        2. Release locks
        3. Update participant state to ABORTED
        """
        # TODO: Implement this method
        return False


class CoordinatorServicer(three_phase_commit_pb2_grpc.CoordinatorServiceServicer):
    """gRPC service for coordinator operations."""

    def __init__(self, node: ThreePhaseCommitNode):
        self.node = node

    async def BeginTransaction(self, request, context):
        """Handle BeginTransaction RPC."""
        participants = list(request.participants) or [self.node.node_id]
        data = dict(request.data)

        tx = await self.node.begin_transaction(participants, data)

        return three_phase_commit_pb2.BeginTransactionResponse(
            success=True,
            transaction_id=tx.transaction_id,
        )

    async def CommitTransaction(self, request, context):
        """Handle CommitTransaction RPC."""
        success, final_state, participant_states = await self.node.commit_transaction(
            request.transaction_id
        )

        state_map = {
            p: three_phase_commit_pb2.ParticipantState.Value(f"P_{s.name}")
            for p, s in participant_states.items()
        } if isinstance(list(participant_states.values())[0] if participant_states else True, ParticipantState) else {}

        return three_phase_commit_pb2.CommitTransactionResponse(
            success=success,
            final_state=three_phase_commit_pb2.TransactionState.Value(final_state.name) if final_state else 0,
        )

    async def AbortTransaction(self, request, context):
        """Handle AbortTransaction RPC."""
        await self.node._abort_transaction(request.transaction_id, request.reason)
        return three_phase_commit_pb2.AbortTransactionResponse(success=True)

    async def GetTransactionStatus(self, request, context):
        """Handle GetTransactionStatus RPC."""
        with self.node.lock:
            if request.transaction_id in self.node.transactions:
                tx = self.node.transactions[request.transaction_id]
                return three_phase_commit_pb2.GetTransactionStatusResponse(
                    transaction=three_phase_commit_pb2.Transaction(
                        transaction_id=tx.transaction_id,
                        state=three_phase_commit_pb2.TransactionState.Value(tx.state.name),
                        participants=tx.participants,
                        coordinator=tx.coordinator,
                        start_time=tx.start_time,
                        last_update=tx.last_update,
                        data=tx.data,
                    ),
                    found=True,
                )
        return three_phase_commit_pb2.GetTransactionStatusResponse(found=False)

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return three_phase_commit_pb2.GetLeaderResponse(
            node_id=self.node.node_id,
            node_address=f"localhost:{self.node.port}",
            is_coordinator=self.node.is_coordinator,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.node.lock:
            members = [
                three_phase_commit_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    is_coordinator=n.is_coordinator,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.node.nodes.values()
            ]

            active = sum(1 for t in self.node.transactions.values()
                        if t.state not in [TransactionState.COMMITTED, TransactionState.ABORTED])
            committed = sum(1 for t in self.node.transactions.values()
                           if t.state == TransactionState.COMMITTED)
            aborted = sum(1 for t in self.node.transactions.values()
                         if t.state == TransactionState.ABORTED)

            return three_phase_commit_pb2.GetClusterStatusResponse(
                node_id=self.node.node_id,
                node_address=f"localhost:{self.node.port}",
                is_coordinator=self.node.is_coordinator,
                total_nodes=len(self.node.nodes),
                healthy_nodes=sum(1 for n in self.node.nodes.values() if n.is_healthy),
                active_transactions=active,
                committed_transactions=committed,
                aborted_transactions=aborted,
                members=members,
            )


class ParticipantServicer(three_phase_commit_pb2_grpc.ParticipantServiceServicer):
    """gRPC service for participant operations."""

    def __init__(self, node: ThreePhaseCommitNode):
        self.node = node

    async def CanCommit(self, request, context):
        """Handle CanCommit RPC (Phase 1)."""
        vote = self.node._local_can_commit(request.transaction_id, dict(request.data))
        return three_phase_commit_pb2.CanCommitResponse(vote=vote)

    async def PreCommit(self, request, context):
        """Handle PreCommit RPC (Phase 2)."""
        ack = self.node._local_pre_commit(request.transaction_id)
        return three_phase_commit_pb2.PreCommitResponse(acknowledged=ack)

    async def DoCommit(self, request, context):
        """Handle DoCommit RPC (Phase 3)."""
        success = self.node._local_do_commit(request.transaction_id)
        return three_phase_commit_pb2.DoCommitResponse(success=success)

    async def DoAbort(self, request, context):
        """Handle DoAbort RPC."""
        self.node._local_do_abort(request.transaction_id)
        return three_phase_commit_pb2.DoAbortResponse(acknowledged=True)

    async def GetState(self, request, context):
        """Handle GetState RPC."""
        with self.node.lock:
            if request.transaction_id in self.node.participant_states:
                info = self.node.participant_states[request.transaction_id]
                return three_phase_commit_pb2.GetStateResponse(
                    info=three_phase_commit_pb2.ParticipantInfo(
                        node_id=info.node_id,
                        transaction_id=info.transaction_id,
                        state=three_phase_commit_pb2.ParticipantState.Value(f"P_{info.state.name}"),
                        vote=info.vote,
                        last_update=info.last_update,
                    ),
                    found=True,
                )
        return three_phase_commit_pb2.GetStateResponse(found=False)


class NodeServicer(three_phase_commit_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, node: ThreePhaseCommitNode):
        self.node = node

    async def QueryState(self, request, context):
        """Handle QueryState RPC for recovery."""
        with self.node.lock:
            if request.transaction_id in self.node.participant_states:
                state = self.node.participant_states[request.transaction_id].state
                return three_phase_commit_pb2.QueryStateResponse(
                    state=three_phase_commit_pb2.ParticipantState.Value(f"P_{state.name}"),
                    found=True,
                )
        return three_phase_commit_pb2.QueryStateResponse(found=False)

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.node.lock:
            if request.node_id not in self.node.nodes:
                self.node.nodes[request.node_id] = NodeInfo(
                    node_id=request.node_id,
                    address="",
                )
            self.node.nodes[request.node_id].last_heartbeat = request.timestamp
            self.node.nodes[request.node_id].is_coordinator = request.is_coordinator

        return three_phase_commit_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.node._current_time_ms(),
        )

    async def ElectCoordinator(self, request, context):
        """Handle ElectCoordinator RPC."""
        # Simple election: grant vote if candidate term is higher
        with self.node.lock:
            if request.term > self.node.current_term:
                self.node.current_term = request.term
                return three_phase_commit_pb2.ElectCoordinatorResponse(
                    vote_granted=True,
                    current_term=self.node.current_term,
                )
        return three_phase_commit_pb2.ElectCoordinatorResponse(
            vote_granted=False,
            current_term=self.node.current_term,
        )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the 3PC server."""
    node = ThreePhaseCommitNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    three_phase_commit_pb2_grpc.add_CoordinatorServiceServicer_to_server(
        CoordinatorServicer(node), server
    )
    three_phase_commit_pb2_grpc.add_ParticipantServiceServicer_to_server(
        ParticipantServicer(node), server
    )
    three_phase_commit_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(node), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting 3PC node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Three-Phase Commit Node")
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
