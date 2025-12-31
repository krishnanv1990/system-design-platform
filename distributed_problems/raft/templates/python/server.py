"""
Raft Consensus Implementation - Python Template

This template provides the basic structure for implementing the Raft
consensus algorithm. You need to implement the TODO sections.

For the full Raft specification, see: https://raft.github.io/raft.pdf

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import random
import threading
import time
from concurrent import futures
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from raft.proto)
import raft_pb2
import raft_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class LogEntry:
    """Represents an entry in the Raft log."""
    index: int
    term: int
    command: bytes
    command_type: str


@dataclass
class RaftState:
    """Persistent and volatile state for a Raft node."""
    # Persistent state (should be saved to disk in production)
    current_term: int = 0
    voted_for: Optional[str] = None
    log: List[LogEntry] = field(default_factory=list)

    # Volatile state on all servers
    commit_index: int = 0
    last_applied: int = 0

    # Volatile state on leaders (reinitialized after election)
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)


class RaftNode:
    """
    Raft consensus node implementation.

    TODO: Implement the core Raft algorithm:
    1. Leader election
    2. Log replication
    3. Safety (election restriction, commitment rules)
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers  # List of "host:port" strings
        self.state = RaftState()
        self.node_state = NodeState.FOLLOWER
        self.leader_id: Optional[str] = None

        # Key-value store (state machine)
        self.kv_store: Dict[str, str] = {}

        # Timing configuration (in seconds)
        self.election_timeout_min = 0.15  # 150ms
        self.election_timeout_max = 0.30  # 300ms
        self.heartbeat_interval = 0.05    # 50ms

        # Synchronization
        self.lock = threading.RLock()
        self.election_timer: Optional[asyncio.TimerHandle] = None

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, raft_pb2_grpc.RaftServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            # Cloud Run URLs require SSL credentials
            if ".run.app" in peer:
                # Use SSL for Cloud Run endpoints
                import ssl
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
                logger.info(f"Using SSL for peer: {peer}")
            else:
                # Use insecure channel for local development
                channel = aio.insecure_channel(peer)
                logger.info(f"Using insecure channel for peer: {peer}")
            self.peer_stubs[peer] = raft_pb2_grpc.RaftServiceStub(channel)
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def get_last_log_index(self) -> int:
        """Get the index of the last log entry."""
        return self.state.log[-1].index if self.state.log else 0

    def get_last_log_term(self) -> int:
        """Get the term of the last log entry."""
        return self.state.log[-1].term if self.state.log else 0

    def reset_election_timer(self):
        """Reset the election timeout with a random duration."""
        # TODO: Implement election timer reset
        # - Cancel any existing timer
        # - Start a new timer with random timeout between
        #   election_timeout_min and election_timeout_max
        # - When timer fires, call start_election()
        pass

    async def start_election(self):
        """
        Start a new leader election.

        TODO: Implement the election process:
        1. Increment current_term
        2. Change state to CANDIDATE
        3. Vote for self
        4. Reset election timer
        5. Send RequestVote RPCs to all peers in parallel
        6. If votes received from majority, become leader
        7. If AppendEntries received from new leader, become follower
        8. If election timeout elapses, start new election
        """
        pass

    async def send_heartbeats(self):
        """
        Send heartbeat AppendEntries RPCs to all followers.

        TODO: Implement heartbeat mechanism:
        - Only run if this node is the leader
        - Send AppendEntries (empty for heartbeat) to all peers
        - Process responses to update match_index and next_index
        - Repeat at heartbeat_interval
        """
        pass

    def apply_command(self, command: bytes, command_type: str):
        """
        Apply a command to the state machine (key-value store).

        TODO: Implement command application:
        - Parse the command
        - Apply to kv_store (put/delete operations)
        """
        pass

    # =========================================================================
    # RaftService RPC Implementations
    # =========================================================================

    async def handle_request_vote(
        self, request: raft_pb2.RequestVoteRequest
    ) -> raft_pb2.RequestVoteResponse:
        """
        Handle RequestVote RPC from a candidate.

        TODO: Implement vote handling per Raft specification:
        1. Reply false if term < currentTerm
        2. If votedFor is null or candidateId, and candidate's log is at
           least as up-to-date as receiver's log, grant vote
        """
        with self.lock:
            response = raft_pb2.RequestVoteResponse()

            # TODO: Implement voting logic
            response.term = self.state.current_term
            response.vote_granted = False

            return response

    async def handle_append_entries(
        self, request: raft_pb2.AppendEntriesRequest
    ) -> raft_pb2.AppendEntriesResponse:
        """
        Handle AppendEntries RPC from leader.

        TODO: Implement log replication per Raft specification:
        1. Reply false if term < currentTerm
        2. Reply false if log doesn't contain an entry at prevLogIndex
           whose term matches prevLogTerm
        3. If an existing entry conflicts with a new one, delete the
           existing entry and all that follow it
        4. Append any new entries not already in the log
        5. If leaderCommit > commitIndex, set commitIndex =
           min(leaderCommit, index of last new entry)
        """
        with self.lock:
            response = raft_pb2.AppendEntriesResponse()

            # TODO: Implement AppendEntries logic
            response.term = self.state.current_term
            response.success = False
            response.match_index = self.get_last_log_index()

            return response

    async def handle_install_snapshot(
        self, request: raft_pb2.InstallSnapshotRequest
    ) -> raft_pb2.InstallSnapshotResponse:
        """
        Handle InstallSnapshot RPC from leader.

        TODO: Implement snapshot installation:
        1. Reply immediately if term < currentTerm
        2. Create new snapshot file if first chunk
        3. Write data into snapshot file at given offset
        4. Reply and wait for more chunks if done is false
        5. Save snapshot file, discard any existing snapshot
        6. If existing log entry has same index and term as last entry
           in snapshot, discard entries before it
        7. Discard entire log and reset state machine with snapshot
        """
        with self.lock:
            response = raft_pb2.InstallSnapshotResponse()
            response.term = self.state.current_term
            return response

    # =========================================================================
    # KeyValueService RPC Implementations
    # =========================================================================

    async def handle_get(self, request: raft_pb2.GetRequest) -> raft_pb2.GetResponse:
        """Handle Get RPC - returns value for key from state machine."""
        response = raft_pb2.GetResponse()
        with self.lock:
            if request.key in self.kv_store:
                response.value = self.kv_store[request.key]
                response.found = True
            else:
                response.found = False
        return response

    async def handle_put(self, request: raft_pb2.PutRequest) -> raft_pb2.PutResponse:
        """
        Handle Put RPC - stores key-value pair.

        TODO: Implement consensus-based put:
        1. If not leader, return leader_hint
        2. Append entry to local log
        3. Replicate to followers via AppendEntries
        4. Once committed (majority replicated), apply to state machine
        5. Return success to client
        """
        response = raft_pb2.PutResponse()
        with self.lock:
            if self.node_state != NodeState.LEADER:
                response.success = False
                response.error = "Not the leader"
                response.leader_hint = self.leader_id or ""
                return response

            # TODO: Implement consensus-based put
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_delete(
        self, request: raft_pb2.DeleteRequest
    ) -> raft_pb2.DeleteResponse:
        """
        Handle Delete RPC - removes key.

        TODO: Implement consensus-based delete (similar to put)
        """
        response = raft_pb2.DeleteResponse()
        with self.lock:
            if self.node_state != NodeState.LEADER:
                response.success = False
                response.error = "Not the leader"
                response.leader_hint = self.leader_id or ""
                return response

            # TODO: Implement consensus-based delete
            response.success = False
            response.error = "Not implemented"

        return response

    async def handle_get_leader(
        self, request: raft_pb2.GetLeaderRequest
    ) -> raft_pb2.GetLeaderResponse:
        """Return current leader information."""
        response = raft_pb2.GetLeaderResponse()
        with self.lock:
            response.leader_id = self.leader_id or ""
            response.is_leader = self.node_state == NodeState.LEADER
            if self.leader_id:
                # Find leader address from peers
                for peer in self.peers:
                    if self.leader_id in peer:
                        response.leader_address = peer
                        break
        return response

    async def handle_get_cluster_status(
        self, request: raft_pb2.GetClusterStatusRequest
    ) -> raft_pb2.GetClusterStatusResponse:
        """Return cluster status information."""
        response = raft_pb2.GetClusterStatusResponse()
        with self.lock:
            response.node_id = self.node_id
            response.state = self.node_state.value
            response.current_term = self.state.current_term
            response.voted_for = self.state.voted_for or ""
            response.commit_index = self.state.commit_index
            response.last_applied = self.state.last_applied
            response.log_length = len(self.state.log)
            response.last_log_term = self.get_last_log_term()

            # Add cluster members
            for peer in self.peers:
                member = raft_pb2.ClusterMember()
                member.address = peer
                if self.node_state == NodeState.LEADER:
                    member.match_index = self.state.match_index.get(peer, 0)
                    member.next_index = self.state.next_index.get(peer, 1)
                response.members.append(member)

        return response


# =============================================================================
# gRPC Service Implementations
# =============================================================================

class RaftServicer(raft_pb2_grpc.RaftServiceServicer):
    """gRPC service implementation for Raft RPCs."""

    def __init__(self, node: RaftNode):
        self.node = node

    async def RequestVote(self, request, context):
        return await self.node.handle_request_vote(request)

    async def AppendEntries(self, request, context):
        return await self.node.handle_append_entries(request)

    async def InstallSnapshot(self, request, context):
        return await self.node.handle_install_snapshot(request)


class KeyValueServicer(raft_pb2_grpc.KeyValueServiceServicer):
    """gRPC service implementation for Key-Value store."""

    def __init__(self, node: RaftNode):
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
    """Start the Raft node server."""
    node = RaftNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    raft_pb2_grpc.add_RaftServiceServicer_to_server(RaftServicer(node), server)
    raft_pb2_grpc.add_KeyValueServiceServicer_to_server(KeyValueServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Raft node {node_id} on {listen_addr}")
    await server.start()

    # Start election timer
    node.reset_election_timer()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Raft Consensus Node")
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
