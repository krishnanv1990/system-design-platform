"""
Two-Phase Commit (2PC) Implementation - Python Template

This template provides the basic structure for implementing the Two-Phase Commit
protocol for distributed transactions. You need to implement the TODO sections.

The 2PC protocol ensures atomic commits across distributed participants:
- Phase 1 (Prepare): Coordinator asks all participants if they can commit
- Phase 2 (Commit/Abort): Based on votes, coordinator tells all to commit or abort

Usage:
    python server.py --node-id coord --port 50051 --role coordinator --participants p1:50052,p2:50053
    python server.py --node-id p1 --port 50052 --role participant --coordinator coord:50051
"""

import argparse
import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from two_phase_commit.proto)
import two_phase_commit_pb2
import two_phase_commit_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionState(Enum):
    UNKNOWN = 0
    ACTIVE = 1
    PREPARING = 2
    PREPARED = 3
    COMMITTING = 4
    COMMITTED = 5
    ABORTING = 6
    ABORTED = 7


class NodeRole(Enum):
    COORDINATOR = "coordinator"
    PARTICIPANT = "participant"


@dataclass
class Operation:
    """Represents a single operation in a transaction."""
    op_type: str  # "read", "write", "delete"
    key: str
    value: Optional[str] = None
    participant_id: Optional[str] = None


@dataclass
class Transaction:
    """Represents a distributed transaction."""
    transaction_id: str
    state: TransactionState = TransactionState.ACTIVE
    participants: List[str] = field(default_factory=list)
    operations: Dict[str, List[Operation]] = field(default_factory=dict)  # participant_id -> operations
    participant_votes: Dict[str, bool] = field(default_factory=dict)
    created_at: float = 0.0
    timeout_ms: int = 5000


@dataclass
class ParticipantState:
    """State maintained by a participant for a transaction."""
    transaction_id: str
    state: TransactionState = TransactionState.ACTIVE
    operations: List[Operation] = field(default_factory=list)
    prepared_state: Optional[bytes] = None
    locks_held: Set[str] = field(default_factory=set)


class TwoPhaseCommitNode:
    """
    Two-Phase Commit node implementation.

    TODO: Implement the core 2PC algorithm:
    1. Coordinator: Begin transaction, collect operations, run 2PC
    2. Participant: Execute operations, vote, commit/abort
    3. Handle timeouts and recovery
    """

    def __init__(self, node_id: str, port: int, role: NodeRole,
                 participants: List[str] = None, coordinator: str = None):
        self.node_id = node_id
        self.port = port
        self.role = role
        self.participants = participants or []
        self.coordinator_addr = coordinator

        # Transaction state
        self.transactions: Dict[str, Transaction] = {}
        self.participant_states: Dict[str, ParticipantState] = {}

        # Key-value store (state machine)
        self.kv_store: Dict[str, str] = {}

        # Write-ahead log for durability
        self.wal: List[Dict] = []

        # Locks for concurrency control
        self.key_locks: Dict[str, str] = {}  # key -> transaction_id

        # Synchronization
        self.lock = threading.RLock()

        # gRPC stubs for communication
        self.participant_stubs: Dict[str, two_phase_commit_pb2_grpc.ParticipantServiceStub] = {}
        self.coordinator_stub: Optional[two_phase_commit_pb2_grpc.CoordinatorServiceStub] = None

    async def initialize(self):
        """Initialize connections to other nodes."""
        if self.role == NodeRole.COORDINATOR:
            for participant in self.participants:
                channel = aio.insecure_channel(participant)
                self.participant_stubs[participant] = two_phase_commit_pb2_grpc.ParticipantServiceStub(channel)
            logger.info(f"Coordinator {self.node_id} initialized with participants: {self.participants}")
        else:
            if self.coordinator_addr:
                channel = aio.insecure_channel(self.coordinator_addr)
                self.coordinator_stub = two_phase_commit_pb2_grpc.CoordinatorServiceStub(channel)
            logger.info(f"Participant {self.node_id} initialized with coordinator: {self.coordinator_addr}")

    # =========================================================================
    # Coordinator Methods
    # =========================================================================

    async def begin_transaction(
        self, request: two_phase_commit_pb2.BeginTransactionRequest
    ) -> two_phase_commit_pb2.BeginTransactionResponse:
        """
        Begin a new distributed transaction.

        TODO: Implement transaction begin:
        1. Generate unique transaction ID
        2. Create transaction record
        3. Initialize participant list
        """
        response = two_phase_commit_pb2.BeginTransactionResponse()

        with self.lock:
            transaction_id = str(uuid.uuid4())

            # TODO: Implement transaction initialization
            response.success = True
            response.transaction_id = transaction_id

        return response

    async def execute_operation(
        self, request: two_phase_commit_pb2.ExecuteOperationRequest
    ) -> two_phase_commit_pb2.ExecuteOperationResponse:
        """
        Execute an operation within a transaction.

        TODO: Implement operation execution:
        1. Find target participant for the operation
        2. Forward operation to participant
        3. Track operation in transaction record
        """
        response = two_phase_commit_pb2.ExecuteOperationResponse()

        with self.lock:
            # TODO: Implement operation execution
            response.success = False
            response.error = "Not implemented"

        return response

    async def commit_transaction(
        self, request: two_phase_commit_pb2.CommitTransactionRequest
    ) -> two_phase_commit_pb2.CommitTransactionResponse:
        """
        Commit a distributed transaction using 2PC.

        TODO: Implement the Two-Phase Commit protocol:
        Phase 1 (Prepare):
        1. Send Prepare to all participants
        2. Wait for all votes (with timeout)
        3. If all vote COMMIT, proceed to Phase 2 commit
        4. If any vote ABORT or timeout, proceed to Phase 2 abort

        Phase 2 (Commit/Abort):
        1. Send Commit or Abort to all participants
        2. Wait for acknowledgments
        3. Mark transaction as complete
        """
        response = two_phase_commit_pb2.CommitTransactionResponse()

        with self.lock:
            transaction_id = request.transaction_id
            if transaction_id not in self.transactions:
                response.success = False
                response.error = "Transaction not found"
                return response

            # TODO: Implement 2PC protocol
            response.success = False
            response.error = "Not implemented"

        return response

    async def abort_transaction(
        self, request: two_phase_commit_pb2.AbortTransactionRequest
    ) -> two_phase_commit_pb2.AbortTransactionResponse:
        """
        Abort a distributed transaction.

        TODO: Implement transaction abort:
        1. Send Abort to all participants
        2. Release all locks
        3. Clean up transaction state
        """
        response = two_phase_commit_pb2.AbortTransactionResponse()

        with self.lock:
            # TODO: Implement abort logic
            response.success = True

        return response

    # =========================================================================
    # Participant Methods
    # =========================================================================

    async def handle_prepare(
        self, request: two_phase_commit_pb2.PrepareRequest
    ) -> two_phase_commit_pb2.PrepareResponse:
        """
        Handle Prepare request from coordinator.

        TODO: Implement prepare phase:
        1. Check if all operations can be executed
        2. Acquire necessary locks
        3. Write to WAL (prepare record)
        4. Vote COMMIT if ready, ABORT otherwise
        """
        response = two_phase_commit_pb2.PrepareResponse()

        with self.lock:
            transaction_id = request.transaction_id

            # TODO: Implement prepare logic
            # - Validate all operations can succeed
            # - Acquire locks on all affected keys
            # - Write PREPARE record to WAL
            # - Vote YES if ready, NO otherwise
            response.vote = False  # VOTE_ABORT

        return response

    async def handle_commit(
        self, request: two_phase_commit_pb2.CommitRequest
    ) -> two_phase_commit_pb2.CommitResponse:
        """
        Handle Commit request from coordinator.

        TODO: Implement commit phase:
        1. Apply all prepared operations to state
        2. Write COMMIT record to WAL
        3. Release all locks
        4. Clean up transaction state
        """
        response = two_phase_commit_pb2.CommitResponse()

        with self.lock:
            transaction_id = request.transaction_id

            # TODO: Implement commit logic
            response.success = True

        return response

    async def handle_abort(
        self, request: two_phase_commit_pb2.AbortRequest
    ) -> two_phase_commit_pb2.AbortResponse:
        """
        Handle Abort request from coordinator.

        TODO: Implement abort phase:
        1. Discard prepared operations
        2. Write ABORT record to WAL
        3. Release all locks
        4. Clean up transaction state
        """
        response = two_phase_commit_pb2.AbortResponse()

        with self.lock:
            transaction_id = request.transaction_id

            # TODO: Implement abort logic
            response.success = True

        return response

    async def execute_local(
        self, request: two_phase_commit_pb2.ExecuteLocalRequest
    ) -> two_phase_commit_pb2.ExecuteLocalResponse:
        """
        Execute an operation locally on this participant.

        TODO: Implement local operation execution:
        1. For reads: Return current value (with proper isolation)
        2. For writes: Stage the write (don't apply until commit)
        3. Track operation in participant state
        """
        response = two_phase_commit_pb2.ExecuteLocalResponse()

        with self.lock:
            # TODO: Implement local execution
            response.success = False
            response.error = "Not implemented"

        return response

    # =========================================================================
    # KeyValueService RPC Implementations
    # =========================================================================

    async def handle_get(self, request: two_phase_commit_pb2.GetRequest) -> two_phase_commit_pb2.GetResponse:
        """Handle Get RPC - returns value for key from state machine."""
        response = two_phase_commit_pb2.GetResponse()
        with self.lock:
            if request.key in self.kv_store:
                response.value = self.kv_store[request.key]
                response.found = True
            else:
                response.found = False
        return response

    async def handle_put(self, request: two_phase_commit_pb2.PutRequest) -> two_phase_commit_pb2.PutResponse:
        """
        Handle Put RPC - stores key-value pair.

        TODO: Implement transactional put:
        1. Require transaction_id
        2. Stage the write in transaction state
        3. Apply only on commit
        """
        response = two_phase_commit_pb2.PutResponse()
        with self.lock:
            if self.role != NodeRole.COORDINATOR:
                response.success = False
                response.error = "Not the coordinator"
                response.coordinator_hint = self.coordinator_addr or ""
                return response

            # TODO: Implement transactional put
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_delete(
        self, request: two_phase_commit_pb2.DeleteRequest
    ) -> two_phase_commit_pb2.DeleteResponse:
        """Handle Delete RPC - removes key."""
        response = two_phase_commit_pb2.DeleteResponse()
        with self.lock:
            if self.role != NodeRole.COORDINATOR:
                response.success = False
                response.error = "Not the coordinator"
                response.coordinator_hint = self.coordinator_addr or ""
                return response

            # TODO: Implement transactional delete
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_get_leader(
        self, request: two_phase_commit_pb2.GetLeaderRequest
    ) -> two_phase_commit_pb2.GetLeaderResponse:
        """Return coordinator information."""
        response = two_phase_commit_pb2.GetLeaderResponse()
        with self.lock:
            if self.role == NodeRole.COORDINATOR:
                response.coordinator_id = self.node_id
                response.is_coordinator = True
            else:
                response.coordinator_id = ""
                response.coordinator_address = self.coordinator_addr or ""
                response.is_coordinator = False
        return response

    async def handle_get_cluster_status(
        self, request: two_phase_commit_pb2.GetClusterStatusRequest
    ) -> two_phase_commit_pb2.GetClusterStatusResponse:
        """Return cluster status information."""
        response = two_phase_commit_pb2.GetClusterStatusResponse()
        with self.lock:
            response.node_id = self.node_id
            response.role = self.role.value

            if self.role == NodeRole.COORDINATOR:
                response.active_transactions = len([t for t in self.transactions.values()
                                                   if t.state == TransactionState.ACTIVE])
                response.committed_transactions = len([t for t in self.transactions.values()
                                                      if t.state == TransactionState.COMMITTED])
                response.aborted_transactions = len([t for t in self.transactions.values()
                                                    if t.state == TransactionState.ABORTED])

                for participant in self.participants:
                    member = two_phase_commit_pb2.ClusterMember()
                    member.address = participant
                    member.role = "participant"
                    response.members.append(member)
            else:
                response.prepared_transactions = len([s for s in self.participant_states.values()
                                                     if s.state == TransactionState.PREPARED])

        return response

    async def handle_get_transaction_status(
        self, request: two_phase_commit_pb2.GetTransactionStatusRequest
    ) -> two_phase_commit_pb2.GetTransactionStatusResponse:
        """Return transaction status."""
        response = two_phase_commit_pb2.GetTransactionStatusResponse()
        with self.lock:
            transaction_id = request.transaction_id
            if transaction_id in self.transactions:
                txn = self.transactions[transaction_id]
                response.found = True
                response.transaction_id = transaction_id
                response.state = txn.state.value
                response.participants.extend(txn.participants)
        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class CoordinatorServicer(two_phase_commit_pb2_grpc.CoordinatorServiceServicer):
    """gRPC service implementation for Coordinator."""

    def __init__(self, node: TwoPhaseCommitNode):
        self.node = node

    async def BeginTransaction(self, request, context):
        return await self.node.begin_transaction(request)

    async def CommitTransaction(self, request, context):
        return await self.node.commit_transaction(request)

    async def AbortTransaction(self, request, context):
        return await self.node.abort_transaction(request)

    async def GetTransactionStatus(self, request, context):
        return await self.node.handle_get_transaction_status(request)

    async def ExecuteOperation(self, request, context):
        return await self.node.execute_operation(request)


class ParticipantServicer(two_phase_commit_pb2_grpc.ParticipantServiceServicer):
    """gRPC service implementation for Participant."""

    def __init__(self, node: TwoPhaseCommitNode):
        self.node = node

    async def Prepare(self, request, context):
        return await self.node.handle_prepare(request)

    async def Commit(self, request, context):
        return await self.node.handle_commit(request)

    async def Abort(self, request, context):
        return await self.node.handle_abort(request)

    async def GetStatus(self, request, context):
        response = two_phase_commit_pb2.GetStatusResponse()
        with self.node.lock:
            if request.transaction_id in self.node.participant_states:
                state = self.node.participant_states[request.transaction_id]
                response.found = True
                response.state = state.state.value
            else:
                response.found = False
        return response

    async def ExecuteLocal(self, request, context):
        return await self.node.execute_local(request)


class KeyValueServicer(two_phase_commit_pb2_grpc.KeyValueServiceServicer):
    """gRPC service implementation for Key-Value store."""

    def __init__(self, node: TwoPhaseCommitNode):
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

async def serve(node_id: str, port: int, role: str, participants: List[str], coordinator: str):
    """Start the 2PC node server."""
    node_role = NodeRole.COORDINATOR if role == "coordinator" else NodeRole.PARTICIPANT
    node = TwoPhaseCommitNode(node_id, port, node_role, participants, coordinator)
    await node.initialize()

    server = aio.server()

    if node_role == NodeRole.COORDINATOR:
        two_phase_commit_pb2_grpc.add_CoordinatorServiceServicer_to_server(
            CoordinatorServicer(node), server)
    else:
        two_phase_commit_pb2_grpc.add_ParticipantServiceServicer_to_server(
            ParticipantServicer(node), server)

    two_phase_commit_pb2_grpc.add_KeyValueServiceServicer_to_server(
        KeyValueServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting 2PC {role} node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Two-Phase Commit Node")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--role", required=True, choices=["coordinator", "participant"],
                        help="Node role")
    parser.add_argument("--participants", default="",
                        help="Comma-separated list of participant addresses (for coordinator)")
    parser.add_argument("--coordinator", default="",
                        help="Coordinator address (for participant)")
    args = parser.parse_args()

    participants = [p.strip() for p in args.participants.split(",") if p.strip()]
    asyncio.run(serve(args.node_id, args.port, args.role, participants, args.coordinator))


if __name__ == "__main__":
    main()
