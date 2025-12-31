"""
Raft Consensus Implementation - Python Solution

A complete implementation of the Raft consensus algorithm supporting:
- Leader election with randomized timeouts
- Log replication with consistency guarantees
- Heartbeat mechanism for leader authority
- Key-value store as the state machine

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import grpc
from grpc import aio

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
    current_term: int = 0
    voted_for: Optional[str] = None
    log: List[LogEntry] = field(default_factory=list)
    commit_index: int = 0
    last_applied: int = 0
    next_index: Dict[str, int] = field(default_factory=dict)
    match_index: Dict[str, int] = field(default_factory=dict)


class RaftNode:
    """Complete Raft consensus node implementation."""

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.state = RaftState()
        self.node_state = NodeState.FOLLOWER
        self.leader_id: Optional[str] = None
        self.kv_store: Dict[str, str] = {}

        # Timing configuration (in seconds)
        self.election_timeout_min = 0.15
        self.election_timeout_max = 0.30
        self.heartbeat_interval = 0.05

        # Synchronization
        self.lock = asyncio.Lock()
        self.election_deadline = time.time() + self._random_timeout()
        self.apply_event = asyncio.Event()
        self.stop_flag = False

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, raft_pb2_grpc.RaftServiceStub] = {}

        # Initialize log with dummy entry at index 0
        self.state.log.append(LogEntry(index=0, term=0, command=b"", command_type=""))

    def _random_timeout(self) -> float:
        return random.uniform(self.election_timeout_min, self.election_timeout_max)

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = raft_pb2_grpc.RaftServiceStub(channel)
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def get_last_log_index(self) -> int:
        return self.state.log[-1].index if self.state.log else 0

    def get_last_log_term(self) -> int:
        return self.state.log[-1].term if self.state.log else 0

    def reset_election_timer(self):
        """Reset the election timeout."""
        self.election_deadline = time.time() + self._random_timeout()

    def step_down(self, new_term: int):
        """Step down to follower state."""
        self.state.current_term = new_term
        self.state.voted_for = None
        self.node_state = NodeState.FOLLOWER
        self.reset_election_timer()

    async def election_timer_loop(self):
        """Background loop to check election timeout."""
        while not self.stop_flag:
            await asyncio.sleep(0.01)
            async with self.lock:
                if self.node_state != NodeState.LEADER and time.time() >= self.election_deadline:
                    await self.start_election()

    async def start_election(self):
        """Start a new leader election."""
        self.node_state = NodeState.CANDIDATE
        self.state.current_term += 1
        self.state.voted_for = self.node_id
        self.reset_election_timer()

        term = self.state.current_term
        last_idx = self.get_last_log_index()
        last_term = self.get_last_log_term()

        logger.info(f"Node {self.node_id} starting election for term {term}")

        votes_received = 1  # Vote for self
        majority = (len(self.peers) + 1) // 2 + 1

        async def request_vote(peer: str):
            nonlocal votes_received
            try:
                request = raft_pb2.RequestVoteRequest(
                    term=term,
                    candidate_id=self.node_id,
                    last_log_index=last_idx,
                    last_log_term=last_term
                )
                response = await asyncio.wait_for(
                    self.peer_stubs[peer].RequestVote(request),
                    timeout=0.1
                )
                async with self.lock:
                    if response.term > self.state.current_term:
                        self.step_down(response.term)
                    elif (self.node_state == NodeState.CANDIDATE and
                          response.vote_granted and
                          term == self.state.current_term):
                        votes_received += 1
                        if votes_received >= majority:
                            await self.become_leader()
            except Exception:
                pass

        tasks = [request_vote(peer) for peer in self.peers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def become_leader(self):
        """Transition to leader state."""
        if self.node_state != NodeState.CANDIDATE:
            return
        self.node_state = NodeState.LEADER
        self.leader_id = self.node_id
        logger.info(f"Node {self.node_id} became leader for term {self.state.current_term}")

        # Initialize leader state
        for peer in self.peers:
            self.state.next_index[peer] = self.get_last_log_index() + 1
            self.state.match_index[peer] = 0

    async def heartbeat_loop(self):
        """Background loop to send heartbeats as leader."""
        while not self.stop_flag:
            await asyncio.sleep(self.heartbeat_interval)
            async with self.lock:
                if self.node_state == NodeState.LEADER:
                    await self.send_append_entries_to_all()

    async def send_append_entries_to_all(self):
        """Send AppendEntries to all peers."""
        async def send_to_peer(peer: str):
            try:
                next_idx = self.state.next_index.get(peer, 1)
                prev_idx = next_idx - 1
                prev_term = self.state.log[prev_idx].term if prev_idx < len(self.state.log) else 0

                entries = []
                for i in range(next_idx, len(self.state.log)):
                    entry = self.state.log[i]
                    entries.append(raft_pb2.LogEntry(
                        index=entry.index,
                        term=entry.term,
                        command=entry.command,
                        command_type=entry.command_type
                    ))

                request = raft_pb2.AppendEntriesRequest(
                    term=self.state.current_term,
                    leader_id=self.node_id,
                    prev_log_index=prev_idx,
                    prev_log_term=prev_term,
                    entries=entries,
                    leader_commit=self.state.commit_index
                )

                response = await asyncio.wait_for(
                    self.peer_stubs[peer].AppendEntries(request),
                    timeout=0.1
                )

                async with self.lock:
                    if response.term > self.state.current_term:
                        self.step_down(response.term)
                    elif self.node_state == NodeState.LEADER:
                        if response.success:
                            self.state.next_index[peer] = prev_idx + len(entries) + 1
                            self.state.match_index[peer] = self.state.next_index[peer] - 1
                            self.update_commit_index()
                        else:
                            self.state.next_index[peer] = max(1, self.state.next_index[peer] - 1)
            except Exception:
                pass

        tasks = [send_to_peer(peer) for peer in self.peers]
        await asyncio.gather(*tasks, return_exceptions=True)

    def update_commit_index(self):
        """Update commit index based on majority replication."""
        for n in range(self.state.commit_index + 1, len(self.state.log)):
            if self.state.log[n].term != self.state.current_term:
                continue
            count = 1  # Count self
            for peer in self.peers:
                if self.state.match_index.get(peer, 0) >= n:
                    count += 1
            if count >= (len(self.peers) + 1) // 2 + 1:
                self.state.commit_index = n
                self.apply_to_state_machine()

    def apply_to_state_machine(self):
        """Apply committed entries to state machine."""
        while self.state.last_applied < self.state.commit_index:
            self.state.last_applied += 1
            entry = self.state.log[self.state.last_applied]
            cmd = entry.command.decode('utf-8')

            if entry.command_type == "put":
                sep = cmd.find(':')
                if sep != -1:
                    key, value = cmd[:sep], cmd[sep+1:]
                    self.kv_store[key] = value
            elif entry.command_type == "delete":
                self.kv_store.pop(cmd, None)

        self.apply_event.set()
        self.apply_event.clear()

    # =========================================================================
    # RaftService RPC Implementations
    # =========================================================================

    async def handle_request_vote(self, request) -> raft_pb2.RequestVoteResponse:
        async with self.lock:
            if request.term > self.state.current_term:
                self.step_down(request.term)

            log_ok = (request.last_log_term > self.get_last_log_term() or
                     (request.last_log_term == self.get_last_log_term() and
                      request.last_log_index >= self.get_last_log_index()))

            vote_granted = False
            if (request.term == self.state.current_term and
                log_ok and
                (self.state.voted_for is None or self.state.voted_for == request.candidate_id)):
                self.state.voted_for = request.candidate_id
                vote_granted = True
                self.reset_election_timer()

            return raft_pb2.RequestVoteResponse(
                term=self.state.current_term,
                vote_granted=vote_granted
            )

    async def handle_append_entries(self, request) -> raft_pb2.AppendEntriesResponse:
        async with self.lock:
            if request.term > self.state.current_term:
                self.step_down(request.term)

            if request.term < self.state.current_term:
                return raft_pb2.AppendEntriesResponse(
                    term=self.state.current_term,
                    success=False,
                    match_index=self.get_last_log_index()
                )

            self.leader_id = request.leader_id
            self.node_state = NodeState.FOLLOWER
            self.reset_election_timer()

            # Check log consistency
            if (request.prev_log_index >= len(self.state.log) or
                self.state.log[request.prev_log_index].term != request.prev_log_term):
                return raft_pb2.AppendEntriesResponse(
                    term=self.state.current_term,
                    success=False,
                    match_index=self.get_last_log_index()
                )

            # Append new entries
            log_ptr = request.prev_log_index + 1
            for entry in request.entries:
                if log_ptr < len(self.state.log):
                    if self.state.log[log_ptr].term != entry.term:
                        self.state.log = self.state.log[:log_ptr]
                if log_ptr >= len(self.state.log):
                    self.state.log.append(LogEntry(
                        index=entry.index,
                        term=entry.term,
                        command=entry.command,
                        command_type=entry.command_type
                    ))
                log_ptr += 1

            # Update commit index
            if request.leader_commit > self.state.commit_index:
                self.state.commit_index = min(request.leader_commit, self.get_last_log_index())
                self.apply_to_state_machine()

            return raft_pb2.AppendEntriesResponse(
                term=self.state.current_term,
                success=True,
                match_index=self.get_last_log_index()
            )

    async def handle_install_snapshot(self, request) -> raft_pb2.InstallSnapshotResponse:
        async with self.lock:
            if request.term > self.state.current_term:
                self.step_down(request.term)
            return raft_pb2.InstallSnapshotResponse(term=self.state.current_term)

    # =========================================================================
    # KeyValueService RPC Implementations
    # =========================================================================

    async def handle_get(self, request) -> raft_pb2.GetResponse:
        async with self.lock:
            if request.key in self.kv_store:
                return raft_pb2.GetResponse(value=self.kv_store[request.key], found=True)
            return raft_pb2.GetResponse(found=False)

    async def handle_put(self, request) -> raft_pb2.PutResponse:
        async with self.lock:
            if self.node_state != NodeState.LEADER:
                return raft_pb2.PutResponse(
                    success=False,
                    error="Not the leader",
                    leader_hint=self.leader_id or ""
                )

            # Append to log
            entry = LogEntry(
                index=self.get_last_log_index() + 1,
                term=self.state.current_term,
                command=f"{request.key}:{request.value}".encode('utf-8'),
                command_type="put"
            )
            self.state.log.append(entry)
            wait_idx = entry.index

        # Wait for commit
        while True:
            async with self.lock:
                if self.state.last_applied >= wait_idx:
                    return raft_pb2.PutResponse(success=True)
                if self.node_state != NodeState.LEADER:
                    return raft_pb2.PutResponse(
                        success=False,
                        error="Lost leadership",
                        leader_hint=self.leader_id or ""
                    )
            await asyncio.sleep(0.01)

    async def handle_delete(self, request) -> raft_pb2.DeleteResponse:
        async with self.lock:
            if self.node_state != NodeState.LEADER:
                return raft_pb2.DeleteResponse(
                    success=False,
                    error="Not the leader",
                    leader_hint=self.leader_id or ""
                )

            entry = LogEntry(
                index=self.get_last_log_index() + 1,
                term=self.state.current_term,
                command=request.key.encode('utf-8'),
                command_type="delete"
            )
            self.state.log.append(entry)
            wait_idx = entry.index

        while True:
            async with self.lock:
                if self.state.last_applied >= wait_idx:
                    return raft_pb2.DeleteResponse(success=True)
                if self.node_state != NodeState.LEADER:
                    return raft_pb2.DeleteResponse(
                        success=False,
                        error="Lost leadership",
                        leader_hint=self.leader_id or ""
                    )
            await asyncio.sleep(0.01)

    async def handle_get_leader(self, request) -> raft_pb2.GetLeaderResponse:
        async with self.lock:
            response = raft_pb2.GetLeaderResponse(
                leader_id=self.leader_id or "",
                is_leader=self.node_state == NodeState.LEADER
            )
            if self.leader_id:
                for peer in self.peers:
                    if self.leader_id in peer:
                        response.leader_address = peer
                        break
            if self.node_state == NodeState.LEADER:
                response.leader_address = f"localhost:{self.port}"
            return response

    async def handle_get_cluster_status(self, request) -> raft_pb2.GetClusterStatusResponse:
        async with self.lock:
            response = raft_pb2.GetClusterStatusResponse(
                node_id=self.node_id,
                state=self.node_state.value,
                current_term=self.state.current_term,
                voted_for=self.state.voted_for or "",
                commit_index=self.state.commit_index,
                last_applied=self.state.last_applied,
                log_length=len(self.state.log),
                last_log_term=self.get_last_log_term()
            )
            for peer in self.peers:
                member = raft_pb2.ClusterMember(address=peer)
                if self.node_state == NodeState.LEADER:
                    member.match_index = self.state.match_index.get(peer, 0)
                    member.next_index = self.state.next_index.get(peer, 1)
                response.members.append(member)
            return response


class RaftServicer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node: RaftNode):
        self.node = node

    async def RequestVote(self, request, context):
        return await self.node.handle_request_vote(request)

    async def AppendEntries(self, request, context):
        return await self.node.handle_append_entries(request)

    async def InstallSnapshot(self, request, context):
        return await self.node.handle_install_snapshot(request)


class KeyValueServicer(raft_pb2_grpc.KeyValueServiceServicer):
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

    # Start background loops
    asyncio.create_task(node.election_timer_loop())
    asyncio.create_task(node.heartbeat_loop())

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        node.stop_flag = True
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Raft Consensus Node")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--peers", required=True, help="Comma-separated peer addresses")
    args = parser.parse_args()

    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    asyncio.run(serve(args.node_id, args.port, peers))


if __name__ == "__main__":
    main()
