"""
Chandy-Lamport Snapshot Algorithm Implementation - Python Template

This template provides the basic structure for implementing the Chandy-Lamport
algorithm for capturing consistent global snapshots. You need to implement the TODO sections.

Based on: "Distributed Snapshots: Determining Global States of Distributed Systems"
by K. Mani Chandy and Leslie Lamport (1985)

The algorithm:
1. Initiator records local state and sends markers on all outgoing channels
2. On first marker receipt, process records state and forwards markers
3. Messages arriving before marker on each channel are recorded
4. Snapshot complete when all channels have received markers

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
from typing import Dict, List, Optional, Set

import grpc
from grpc import aio

# Generated protobuf imports
import chandy_lamport_pb2
import chandy_lamport_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChannelState:
    """Messages recorded on a channel during snapshot."""
    from_process: str
    to_process: str
    messages: List[chandy_lamport_pb2.ApplicationMessage] = field(default_factory=list)
    is_recording: bool = False


@dataclass
class SnapshotState:
    """State for an ongoing snapshot."""
    snapshot_id: str
    initiator_id: str
    local_state_recorded: bool = False
    local_state: Optional[bytes] = None
    logical_clock: int = 0
    account_balances: Dict[str, int] = field(default_factory=dict)
    kv_state: Dict[str, str] = field(default_factory=dict)
    channel_states: Dict[str, ChannelState] = field(default_factory=dict)
    markers_received: Set[str] = field(default_factory=set)
    recording_complete: bool = False
    initiated_at: float = 0.0
    completed_at: float = 0.0


class ChandyLamportNode:
    """
    Chandy-Lamport snapshot algorithm implementation.

    TODO: Implement the core algorithm:
    1. Initiating a snapshot (record local state, send markers)
    2. Handling marker receipt (record state, forward markers, record channels)
    3. Recording messages on channels
    4. Assembling global snapshot
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers

        # Logical clock (Lamport clock)
        self.logical_clock = 0

        # Snapshot state
        self.snapshots: Dict[str, SnapshotState] = {}
        self.current_snapshot_id: Optional[str] = None

        # Channels (for message recording)
        self.incoming_channels: Dict[str, ChannelState] = {}

        # Application state: Bank simulation
        self.account_balances: Dict[str, int] = {
            f"{node_id}_account": 1000  # Initial balance
        }

        # Application state: Key-value store
        self.kv_store: Dict[str, str] = {}

        # Statistics
        self.snapshots_initiated = 0
        self.snapshots_participated = 0

        # Synchronization
        self.lock = threading.RLock()

        # gRPC stubs
        self.peer_stubs: Dict[str, chandy_lamport_pb2_grpc.SnapshotServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = chandy_lamport_pb2_grpc.SnapshotServiceStub(channel)

            # Initialize incoming channel state
            peer_id = peer.split(':')[0]  # Extract node ID from address
            self.incoming_channels[peer_id] = ChannelState(
                from_process=peer_id,
                to_process=self.node_id
            )

        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def increment_clock(self) -> int:
        """Increment and return logical clock."""
        self.logical_clock += 1
        return self.logical_clock

    def update_clock(self, received_clock: int):
        """Update clock based on received timestamp."""
        self.logical_clock = max(self.logical_clock, received_clock) + 1

    # =========================================================================
    # Snapshot Initiation
    # =========================================================================

    async def initiate_snapshot(
        self, request: chandy_lamport_pb2.InitiateSnapshotRequest
    ) -> chandy_lamport_pb2.InitiateSnapshotResponse:
        """
        Initiate a new global snapshot.

        TODO: Implement snapshot initiation:
        1. Generate unique snapshot ID
        2. Record local state immediately
        3. Start recording on all incoming channels
        4. Send marker on all outgoing channels
        """
        response = chandy_lamport_pb2.InitiateSnapshotResponse()

        with self.lock:
            snapshot_id = request.snapshot_id or str(uuid.uuid4())

            # TODO: Implement snapshot initiation
            # - Record local state (account balances, kv_store, logical_clock)
            # - Create SnapshotState
            # - Start recording on all incoming channels
            # - Send markers to all peers

            self.snapshots_initiated += 1
            response.success = True
            response.snapshot_id = snapshot_id
            response.initiated_at = int(time.time() * 1000)

        return response

    # =========================================================================
    # Marker Handling
    # =========================================================================

    async def receive_marker(
        self, request: chandy_lamport_pb2.MarkerMessage
    ) -> chandy_lamport_pb2.MarkerResponse:
        """
        Handle incoming marker message.

        TODO: Implement marker handling:
        1. If first marker for this snapshot:
           - Record local state
           - Mark sender's channel as empty (no messages to record)
           - Start recording on other incoming channels
           - Send markers on all outgoing channels
        2. If not first marker:
           - Stop recording on sender's channel
           - Check if snapshot is complete (all channels done)
        """
        response = chandy_lamport_pb2.MarkerResponse()

        with self.lock:
            snapshot_id = request.snapshot_id
            sender_id = request.sender_id

            self.update_clock(request.logical_clock)

            # Check if this is the first marker for this snapshot
            first_marker = snapshot_id not in self.snapshots

            if first_marker:
                # TODO: Implement first marker handling
                # - Record local state
                # - Create snapshot state
                # - Mark sender channel as empty
                # - Start recording other channels
                # - Forward markers to all peers
                self.snapshots_participated += 1
                pass
            else:
                # TODO: Implement subsequent marker handling
                # - Stop recording on sender's channel
                # - Check if snapshot complete
                pass

            response.success = True
            response.first_marker = first_marker
            response.process_id = self.node_id

        return response

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def send_message(
        self, request: chandy_lamport_pb2.ApplicationMessage
    ) -> chandy_lamport_pb2.SendMessageResponse:
        """
        Handle sending an application message.

        TODO: For messages in transit during snapshot:
        - Include logical clock in message
        - Message might be recorded by receiver if channel is being recorded
        """
        response = chandy_lamport_pb2.SendMessageResponse()

        with self.lock:
            self.increment_clock()
            # TODO: Forward message to destination
            response.success = True

        return response

    def record_incoming_message(self, sender_id: str, message: chandy_lamport_pb2.ApplicationMessage):
        """
        Record a message if the channel is being recorded.

        TODO: Check if any active snapshot is recording this channel.
        If so, add the message to the channel state.
        """
        with self.lock:
            for snapshot in self.snapshots.values():
                if not snapshot.recording_complete:
                    channel_key = f"{sender_id}->{self.node_id}"
                    if channel_key in snapshot.channel_states:
                        channel = snapshot.channel_states[channel_key]
                        if channel.is_recording:
                            channel.messages.append(message)

    # =========================================================================
    # Snapshot Retrieval
    # =========================================================================

    async def get_snapshot(
        self, request: chandy_lamport_pb2.GetSnapshotRequest
    ) -> chandy_lamport_pb2.GetSnapshotResponse:
        """Return local snapshot state for a given snapshot ID."""
        response = chandy_lamport_pb2.GetSnapshotResponse()

        with self.lock:
            snapshot_id = request.snapshot_id
            if snapshot_id in self.snapshots:
                snapshot = self.snapshots[snapshot_id]
                response.found = True
                response.snapshot_id = snapshot_id
                response.recording_complete = snapshot.recording_complete

                # Build local state
                local_state = chandy_lamport_pb2.ProcessState()
                local_state.process_id = self.node_id
                local_state.logical_clock = snapshot.logical_clock
                for k, v in snapshot.account_balances.items():
                    local_state.account_balances[k] = v
                for k, v in snapshot.kv_state.items():
                    local_state.kv_state[k] = v
                response.local_state.CopyFrom(local_state)

                # Build channel states
                for channel in snapshot.channel_states.values():
                    cs = chandy_lamport_pb2.ChannelState()
                    cs.from_process = channel.from_process
                    cs.to_process = channel.to_process
                    cs.messages.extend(channel.messages)
                    response.channel_states.append(cs)
            else:
                response.found = False

        return response

    async def get_global_snapshot(
        self, request: chandy_lamport_pb2.GetGlobalSnapshotRequest
    ) -> chandy_lamport_pb2.GetGlobalSnapshotResponse:
        """
        Collect and return complete global snapshot.

        TODO: Implement global snapshot collection:
        1. Query all peers for their local snapshots
        2. Combine process states and channel states
        3. Verify snapshot consistency
        """
        response = chandy_lamport_pb2.GetGlobalSnapshotResponse()

        with self.lock:
            snapshot_id = request.snapshot_id
            if snapshot_id not in self.snapshots:
                response.success = False
                response.error = "Snapshot not found"
                return response

            # TODO: Collect snapshots from all peers and combine
            response.success = False
            response.error = "Not implemented"

        return response

    # =========================================================================
    # Bank Service (for testing)
    # =========================================================================

    async def handle_get_balance(
        self, request: chandy_lamport_pb2.GetBalanceRequest
    ) -> chandy_lamport_pb2.GetBalanceResponse:
        """Get account balance."""
        response = chandy_lamport_pb2.GetBalanceResponse()
        with self.lock:
            if request.account_id in self.account_balances:
                response.balance = self.account_balances[request.account_id]
                response.found = True
            else:
                response.found = False
        return response

    async def handle_transfer(
        self, request: chandy_lamport_pb2.TransferRequest
    ) -> chandy_lamport_pb2.TransferResponse:
        """Transfer money between accounts."""
        response = chandy_lamport_pb2.TransferResponse()
        with self.lock:
            from_account = request.from_account
            to_account = request.to_account
            amount = request.amount

            if from_account not in self.account_balances:
                response.success = False
                response.error = "Source account not found"
                return response

            if self.account_balances[from_account] < amount:
                response.success = False
                response.error = "Insufficient funds"
                return response

            # TODO: For cross-process transfers, send message to destination
            self.account_balances[from_account] -= amount
            if to_account in self.account_balances:
                self.account_balances[to_account] += amount

            response.success = True
            response.from_balance = self.account_balances[from_account]
            response.to_balance = self.account_balances.get(to_account, 0)

        return response

    async def handle_deposit(
        self, request: chandy_lamport_pb2.DepositRequest
    ) -> chandy_lamport_pb2.DepositResponse:
        """Deposit money to account."""
        response = chandy_lamport_pb2.DepositResponse()
        with self.lock:
            account_id = request.account_id
            if account_id not in self.account_balances:
                self.account_balances[account_id] = 0
            self.account_balances[account_id] += request.amount
            response.success = True
            response.new_balance = self.account_balances[account_id]
        return response

    # =========================================================================
    # KeyValue Service
    # =========================================================================

    async def handle_get(self, request: chandy_lamport_pb2.GetRequest) -> chandy_lamport_pb2.GetResponse:
        """Get value from KV store."""
        response = chandy_lamport_pb2.GetResponse()
        with self.lock:
            if request.key in self.kv_store:
                response.value = self.kv_store[request.key]
                response.found = True
            else:
                response.found = False
        return response

    async def handle_put(self, request: chandy_lamport_pb2.PutRequest) -> chandy_lamport_pb2.PutResponse:
        """Put value in KV store."""
        response = chandy_lamport_pb2.PutResponse()
        with self.lock:
            self.kv_store[request.key] = request.value
            response.success = True
        return response

    async def handle_delete(self, request: chandy_lamport_pb2.DeleteRequest) -> chandy_lamport_pb2.DeleteResponse:
        """Delete from KV store."""
        response = chandy_lamport_pb2.DeleteResponse()
        with self.lock:
            if request.key in self.kv_store:
                del self.kv_store[request.key]
            response.success = True
        return response

    async def handle_get_leader(
        self, request: chandy_lamport_pb2.GetLeaderRequest
    ) -> chandy_lamport_pb2.GetLeaderResponse:
        """Return initiator information."""
        response = chandy_lamport_pb2.GetLeaderResponse()
        response.initiator_id = self.node_id
        response.is_initiator = True  # Any node can initiate snapshots
        return response

    async def handle_get_cluster_status(
        self, request: chandy_lamport_pb2.GetClusterStatusRequest
    ) -> chandy_lamport_pb2.GetClusterStatusResponse:
        """Return cluster status."""
        response = chandy_lamport_pb2.GetClusterStatusResponse()
        with self.lock:
            response.node_id = self.node_id
            response.logical_clock = self.logical_clock
            response.is_recording = self.current_snapshot_id is not None
            response.current_snapshot_id = self.current_snapshot_id or ""
            response.snapshots_initiated = self.snapshots_initiated
            response.snapshots_participated = self.snapshots_participated

            for peer in self.peers:
                member = chandy_lamport_pb2.ClusterMember()
                member.address = peer
                member.is_healthy = True
                response.members.append(member)

        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class SnapshotServicer(chandy_lamport_pb2_grpc.SnapshotServiceServicer):
    def __init__(self, node: ChandyLamportNode):
        self.node = node

    async def InitiateSnapshot(self, request, context):
        return await self.node.initiate_snapshot(request)

    async def ReceiveMarker(self, request, context):
        return await self.node.receive_marker(request)

    async def SendMessage(self, request, context):
        return await self.node.send_message(request)

    async def GetSnapshot(self, request, context):
        return await self.node.get_snapshot(request)

    async def GetGlobalSnapshot(self, request, context):
        return await self.node.get_global_snapshot(request)


class BankServicer(chandy_lamport_pb2_grpc.BankServiceServicer):
    def __init__(self, node: ChandyLamportNode):
        self.node = node

    async def GetBalance(self, request, context):
        return await self.node.handle_get_balance(request)

    async def Transfer(self, request, context):
        return await self.node.handle_transfer(request)

    async def Deposit(self, request, context):
        return await self.node.handle_deposit(request)

    async def Withdraw(self, request, context):
        response = chandy_lamport_pb2.WithdrawResponse()
        response.success = False
        response.error = "Not implemented"
        return response


class KeyValueServicer(chandy_lamport_pb2_grpc.KeyValueServiceServicer):
    def __init__(self, node: ChandyLamportNode):
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
    """Start the Chandy-Lamport node server."""
    node = ChandyLamportNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    chandy_lamport_pb2_grpc.add_SnapshotServiceServicer_to_server(SnapshotServicer(node), server)
    chandy_lamport_pb2_grpc.add_BankServiceServicer_to_server(BankServicer(node), server)
    chandy_lamport_pb2_grpc.add_KeyValueServiceServicer_to_server(KeyValueServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Chandy-Lamport node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Chandy-Lamport Snapshot Node")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--peers", required=True,
                        help="Comma-separated list of peer addresses (host:port)")
    args = parser.parse_args()

    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    asyncio.run(serve(args.node_id, args.port, peers))


if __name__ == "__main__":
    main()
