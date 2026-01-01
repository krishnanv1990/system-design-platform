"""
Distributed KV Store with Append-Only Log and Compaction - Python Template

This template provides the basic structure for implementing a
distributed key-value store using log-structured storage.

Architecture:
1. All writes are appended to an immutable log (fast writes)
2. An in-memory hash table maps keys to log offsets (fast reads)
3. Compaction removes outdated entries to reclaim space
4. Segments: log is divided into segments for easier management

Similar to: Bitcask (Riak), early Kafka

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import hashlib
import logging
import os
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

import grpc
from grpc import aio

# Generated protobuf imports
import kv_store_log_pb2
import kv_store_log_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SEGMENT_SIZE = 64 * 1024 * 1024  # 64MB per segment
COMPACTION_THRESHOLD = 0.5  # Compact when < 50% live data


class EntryType(Enum):
    PUT = 0
    DELETE = 1


@dataclass
class LogEntry:
    """A single entry in the log."""
    offset: int
    timestamp: int
    entry_type: EntryType
    key: str
    value: bytes
    checksum: int = 0


@dataclass
class KeyDirEntry:
    """In-memory index entry."""
    key: str
    segment_id: int
    offset: int
    size: int
    timestamp: int


@dataclass
class Segment:
    """Log segment metadata."""
    id: int
    filename: str
    start_offset: int
    end_offset: int
    size_bytes: int
    entry_count: int
    is_active: bool
    is_compacted: bool
    created_at: int
    last_modified: int


@dataclass
class NodeInfo:
    """Cluster node information."""
    node_id: str
    address: str
    is_healthy: bool = True
    is_leader: bool = False
    keys_count: int = 0
    log_offset: int = 0
    last_heartbeat: int = 0


class LogStructuredStore:
    """
    Log-structured key-value store.

    TODO: Implement log-structured storage:
    1. append() - Append entry to current segment
    2. get() - Look up key in KeyDir, read from segment
    3. compact() - Merge segments, remove dead entries
    4. recover() - Rebuild KeyDir from segments on startup
    """

    def __init__(self, node_id: str, data_dir: str = "./data"):
        self.node_id = node_id
        self.data_dir = data_dir
        self.lock = threading.RLock()

        # In-memory index (KeyDir)
        self.keydir: Dict[str, KeyDirEntry] = {}

        # Segment management
        self.segments: Dict[int, Segment] = {}
        self.active_segment_id = 0
        self.current_offset = 0

        # In-memory buffer for active segment
        self.active_buffer: List[LogEntry] = []
        self.buffer_size = 0

        # Statistics
        self.total_entries = 0
        self.live_entries = 0

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)

    def _compute_checksum(self, data: bytes) -> int:
        """Compute CRC32 checksum."""
        import zlib
        return zlib.crc32(data) & 0xffffffff

    def append(self, key: str, value: bytes, entry_type: EntryType = EntryType.PUT) -> int:
        """
        Append an entry to the log.

        TODO: Implement append:
        1. Create log entry with timestamp and checksum
        2. Append to active segment buffer
        3. Update KeyDir
        4. Return the offset

        Returns:
            Offset of the entry
        """
        # TODO: Implement this method
        return 0

    def get(self, key: str) -> Tuple[Optional[bytes], bool]:
        """
        Get a value by key.

        TODO: Implement get:
        1. Look up key in KeyDir
        2. If found, read from segment at offset
        3. Verify checksum
        4. Return (value, found)
        """
        # TODO: Implement this method
        return (None, False)

    def delete(self, key: str) -> bool:
        """
        Delete a key by appending a tombstone.

        TODO: Implement delete:
        1. Check if key exists in keydir
        2. If yes, append a DELETE entry
        3. Return True if key existed
        """
        # TODO: Implement this method
        return False

    def scan(self, start_key: str, end_key: str, limit: int = 100) -> List[Tuple[str, bytes]]:
        """
        Scan a range of keys.

        TODO: Implement scan:
        1. Iterate over sorted keys in keydir
        2. Filter by start_key and end_key
        3. Get value for each key
        4. Return up to limit results
        """
        # TODO: Implement this method
        return []

    def compact(self) -> Tuple[int, int]:
        """
        Compact segments to reclaim space.

        TODO: Implement compaction:
        1. Iterate through all entries in old segments
        2. Keep only entries in current KeyDir
        3. Write live entries to new segment
        4. Delete old segments
        5. Return (entries_processed, entries_removed)
        """
        # TODO: Implement this method
        return (0, 0)


class KVStoreNode:
    """Distributed KV Store node."""

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Storage engine
        self.store = LogStructuredStore(node_id)

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False
        self.term = 0

        # Compaction state
        self.is_compacting = False
        self.last_compaction = 0
        self.compaction_count = 0

        # gRPC stubs
        self.peer_stubs: Dict[str, kv_store_log_pb2_grpc.ReplicationServiceStub] = {}

    async def initialize(self):
        """Initialize connections."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = kv_store_log_pb2_grpc.ReplicationServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"KV Store node {self.node_id} initialized")

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)


class KVServicer(kv_store_log_pb2_grpc.KVServiceServicer):
    """gRPC service for KV operations."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def Get(self, request, context):
        """Handle Get RPC."""
        value, found = self.node.store.get(request.key)
        return kv_store_log_pb2.GetResponse(
            value=value or b"",
            found=found,
            timestamp=self.node._current_time_ms() if found else 0,
            served_by=self.node.node_id,
        )

    async def Put(self, request, context):
        """Handle Put RPC."""
        offset = self.node.store.append(request.key, request.value, EntryType.PUT)
        return kv_store_log_pb2.PutResponse(
            success=True,
            offset=offset,
            served_by=self.node.node_id,
        )

    async def Delete(self, request, context):
        """Handle Delete RPC."""
        existed = self.node.store.delete(request.key)
        return kv_store_log_pb2.DeleteResponse(
            success=True,
            existed=existed,
            served_by=self.node.node_id,
        )

    async def Scan(self, request, context):
        """Handle Scan RPC."""
        results = self.node.store.scan(request.start_key, request.end_key, request.limit or 100)
        entries = [
            kv_store_log_pb2.KeyValue(key=k, value=v, timestamp=0)
            for k, v in results
        ]
        return kv_store_log_pb2.ScanResponse(
            entries=entries,
            has_more=len(entries) >= (request.limit or 100),
        )

    async def BatchPut(self, request, context):
        """Handle BatchPut RPC."""
        count = 0
        for entry in request.entries:
            self.node.store.append(entry.key, entry.value, EntryType.PUT)
            count += 1
        return kv_store_log_pb2.BatchPutResponse(
            success=True,
            entries_written=count,
        )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return kv_store_log_pb2.GetLeaderResponse(
            node_id=self.node.node_id,
            node_address=f"localhost:{self.node.port}",
            is_leader=self.node.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.node.lock:
            members = [
                kv_store_log_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    is_leader=n.is_leader,
                    keys_count=n.keys_count,
                    log_offset=n.log_offset,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.node.nodes.values()
            ]

            return kv_store_log_pb2.GetClusterStatusResponse(
                node_id=self.node.node_id,
                node_address=f"localhost:{self.node.port}",
                is_leader=self.node.is_leader,
                total_nodes=len(self.node.nodes),
                healthy_nodes=sum(1 for n in self.node.nodes.values() if n.is_healthy),
                total_keys=len(self.node.store.keydir),
                total_segments=len(self.node.store.segments) + 1,
                storage_bytes=self.node.store.buffer_size,
                members=members,
            )


class StorageServicer(kv_store_log_pb2_grpc.StorageServiceServicer):
    """gRPC service for storage management."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def TriggerCompaction(self, request, context):
        """Handle TriggerCompaction RPC."""
        if self.node.is_compacting:
            return kv_store_log_pb2.TriggerCompactionResponse(
                started=False,
                error="Compaction already in progress",
            )

        self.node.is_compacting = True
        compaction_id = f"compact-{self.node._current_time_ms()}"

        # Run compaction
        processed, removed = self.node.store.compact()
        self.node.last_compaction = self.node._current_time_ms()
        self.node.compaction_count += 1
        self.node.is_compacting = False

        return kv_store_log_pb2.TriggerCompactionResponse(
            started=True,
            compaction_id=compaction_id,
        )

    async def GetCompactionStatus(self, request, context):
        """Handle GetCompactionStatus RPC."""
        return kv_store_log_pb2.GetCompactionStatusResponse(
            is_running=self.node.is_compacting,
            progress_percent=100.0 if not self.node.is_compacting else 0.0,
            started_at=self.node.last_compaction,
        )

    async def GetStorageStats(self, request, context):
        """Handle GetStorageStats RPC."""
        store = self.node.store
        return kv_store_log_pb2.GetStorageStatsResponse(
            total_keys=len(store.keydir),
            total_entries=store.total_entries,
            total_segments=len(store.segments) + 1,
            active_segment_size=store.buffer_size,
            total_storage_bytes=store.buffer_size,
            live_data_bytes=store.live_entries * 100,  # Estimate
            space_amplification=store.total_entries / max(store.live_entries, 1),
            last_compaction=self.node.last_compaction,
            compaction_count=self.node.compaction_count,
        )

    async def GetSegments(self, request, context):
        """Handle GetSegments RPC."""
        segments = [
            kv_store_log_pb2.Segment(
                id=0,
                filename="active",
                start_offset=0,
                end_offset=self.node.store.current_offset,
                size_bytes=self.node.store.buffer_size,
                entry_count=len(self.node.store.active_buffer),
                is_active=True,
                is_compacted=False,
                created_at=self.node._current_time_ms(),
                last_modified=self.node._current_time_ms(),
            )
        ]
        return kv_store_log_pb2.GetSegmentsResponse(
            segments=segments,
            total_count=len(segments),
        )


class ReplicationServicer(kv_store_log_pb2_grpc.ReplicationServiceServicer):
    """gRPC service for replication."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def AppendEntries(self, request, context):
        """Handle AppendEntries RPC."""
        # Apply entries
        for entry in request.entries:
            if entry.type == kv_store_log_pb2.PUT:
                self.node.store.append(entry.key, entry.value, EntryType.PUT)
            elif entry.type == kv_store_log_pb2.DELETE:
                self.node.store.delete(entry.key)

        return kv_store_log_pb2.AppendEntriesResponse(
            term=self.node.term,
            success=True,
            match_offset=self.node.store.current_offset,
        )

    async def RequestVote(self, request, context):
        """Handle RequestVote RPC."""
        vote_granted = request.term > self.node.term
        if vote_granted:
            self.node.term = request.term
        return kv_store_log_pb2.RequestVoteResponse(
            term=self.node.term,
            vote_granted=vote_granted,
        )

    async def InstallSnapshot(self, request, context):
        """Handle InstallSnapshot RPC."""
        return kv_store_log_pb2.InstallSnapshotResponse(
            term=self.node.term,
            success=True,
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
            self.node.nodes[request.node_id].log_offset = request.log_offset

        return kv_store_log_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.node._current_time_ms(),
        )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the KV store server."""
    node = KVStoreNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    kv_store_log_pb2_grpc.add_KVServiceServicer_to_server(KVServicer(node), server)
    kv_store_log_pb2_grpc.add_StorageServiceServicer_to_server(StorageServicer(node), server)
    kv_store_log_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Log-Structured KV Store node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Log-Structured KV Store Node")
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
