"""
Distributed KV Store with LSM Tree - Python Template

This template provides the basic structure for implementing a
distributed key-value store using Log-Structured Merge Tree.

LSM Tree Architecture:
1. MemTable: In-memory sorted structure (skip list / red-black tree)
2. WAL: Write-ahead log for durability
3. SSTables: Immutable sorted string tables on disk
4. Levels: SSTables organized in levels (L0, L1, ..., Ln)
5. Compaction: Merge SSTables across levels

Similar to: LevelDB, RocksDB, Cassandra, HBase

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import bisect
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

import grpc
from grpc import aio

# Generated protobuf imports
import kv_store_lsm_pb2
import kv_store_lsm_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MEMTABLE_SIZE = 4 * 1024 * 1024  # 4MB
LEVEL_SIZE_MULTIPLIER = 10


class WriteType(Enum):
    PUT = 0
    DELETE = 1


@dataclass
class WALEntry:
    """Write-ahead log entry."""
    sequence_number: int
    write_type: WriteType
    key: str
    value: bytes
    timestamp: int


@dataclass
class SSTableInfo:
    """SSTable metadata."""
    id: str
    level: int
    filename: str
    size_bytes: int
    entry_count: int
    min_key: str
    max_key: str
    min_sequence: int
    max_sequence: int
    created_at: int


@dataclass
class NodeInfo:
    """Cluster node information."""
    node_id: str
    address: str
    is_healthy: bool = True
    is_leader: bool = False
    sequence_number: int = 0
    last_heartbeat: int = 0


class MemTable:
    """
    In-memory sorted table.

    TODO: Implement MemTable:
    1. Use sorted data structure (skip list or sorted dict)
    2. put() - Insert or update key
    3. get() - Look up key
    4. scan() - Range scan
    5. flush() - Convert to SSTable
    """

    def __init__(self, max_size: int = MEMTABLE_SIZE):
        self.data: Dict[str, Tuple[bytes, int, WriteType]] = {}  # key -> (value, seq, type)
        self.size_bytes = 0
        self.max_size = max_size
        self.oldest_sequence = 0
        self.newest_sequence = 0

    def put(self, key: str, value: bytes, sequence: int):
        """Put a key-value pair."""
        old_size = len(self.data.get(key, (b"", 0, WriteType.PUT))[0])
        self.data[key] = (value, sequence, WriteType.PUT)
        self.size_bytes += len(key) + len(value) - old_size
        self.newest_sequence = max(self.newest_sequence, sequence)
        if self.oldest_sequence == 0:
            self.oldest_sequence = sequence

    def delete(self, key: str, sequence: int):
        """Mark a key as deleted (tombstone)."""
        self.data[key] = (b"", sequence, WriteType.DELETE)
        self.newest_sequence = max(self.newest_sequence, sequence)

    def get(self, key: str) -> Tuple[Optional[bytes], bool, WriteType]:
        """Get a value by key."""
        if key in self.data:
            value, seq, wtype = self.data[key]
            return (value, True, wtype)
        return (None, False, WriteType.PUT)

    def is_full(self) -> bool:
        """Check if memtable is full."""
        return self.size_bytes >= self.max_size

    def scan(self, start: str, end: str) -> List[Tuple[str, bytes, int]]:
        """Scan a range of keys."""
        results = []
        for key in sorted(self.data.keys()):
            if start and key < start:
                continue
            if end and key >= end:
                break
            value, seq, wtype = self.data[key]
            if wtype == WriteType.PUT:
                results.append((key, value, seq))
        return results


class LSMTree:
    """
    LSM Tree storage engine.

    TODO: Implement LSM Tree:
    1. Write path: WAL -> MemTable -> Immutable MemTable -> SSTable
    2. Read path: MemTable -> Immutable -> L0 SSTables -> L1 -> ... -> Ln
    3. Compaction: Merge SSTables within and across levels
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.lock = threading.RLock()

        # MemTables
        self.memtable = MemTable()
        self.immutable_memtable: Optional[MemTable] = None

        # SSTables by level
        self.levels: Dict[int, List[SSTableInfo]] = {i: [] for i in range(7)}

        # Sequence number
        self.sequence_number = 0

        # WAL (in-memory for simplicity)
        self.wal: List[WALEntry] = []

        # Stats
        self.bytes_compacted = 0
        self.compaction_count = 0

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)

    def _next_sequence(self) -> int:
        self.sequence_number += 1
        return self.sequence_number

    def put(self, key: str, value: bytes, sync: bool = False) -> int:
        """
        Put a key-value pair.

        TODO: Implement put:
        1. Write to WAL
        2. Write to MemTable
        3. If MemTable full, trigger flush
        """
        with self.lock:
            seq = self._next_sequence()

            # Write to WAL
            self.wal.append(WALEntry(
                sequence_number=seq,
                write_type=WriteType.PUT,
                key=key,
                value=value,
                timestamp=self._current_time_ms(),
            ))

            # Write to MemTable
            self.memtable.put(key, value, seq)

            # Check if need to flush
            if self.memtable.is_full():
                self._rotate_memtable()

            return seq

    def delete(self, key: str, sync: bool = False) -> int:
        """Delete a key."""
        with self.lock:
            seq = self._next_sequence()

            # Write tombstone to WAL
            self.wal.append(WALEntry(
                sequence_number=seq,
                write_type=WriteType.DELETE,
                key=key,
                value=b"",
                timestamp=self._current_time_ms(),
            ))

            # Write tombstone to MemTable
            self.memtable.delete(key, seq)

            return seq

    def get(self, key: str) -> Tuple[Optional[bytes], bool, str]:
        """
        Get a value by key.

        TODO: Implement get:
        1. Check MemTable
        2. Check Immutable MemTable
        3. Check L0 SSTables (most recent first)
        4. Check L1, L2, ... (use bloom filters)
        """
        with self.lock:
            # Check MemTable
            value, found, wtype = self.memtable.get(key)
            if found:
                if wtype == WriteType.DELETE:
                    return (None, False, "memtable")
                return (value, True, "memtable")

            # Check Immutable MemTable
            if self.immutable_memtable:
                value, found, wtype = self.immutable_memtable.get(key)
                if found:
                    if wtype == WriteType.DELETE:
                        return (None, False, "immutable")
                    return (value, True, "immutable")

            # In a real implementation, check SSTables here
            return (None, False, "not_found")

    def scan(self, start: str, end: str, limit: int = 100) -> List[Tuple[str, bytes, int]]:
        """Scan a range of keys."""
        with self.lock:
            results = {}

            # Scan MemTable
            for key, value, seq in self.memtable.scan(start, end):
                results[key] = (value, seq)

            # Scan Immutable
            if self.immutable_memtable:
                for key, value, seq in self.immutable_memtable.scan(start, end):
                    if key not in results or results[key][1] < seq:
                        results[key] = (value, seq)

            # Sort and limit
            sorted_results = sorted(results.items())[:limit]
            return [(k, v, s) for k, (v, s) in sorted_results]

    def _rotate_memtable(self):
        """Make current memtable immutable and create a new one."""
        if self.immutable_memtable is not None:
            # Flush immutable to SSTable first
            self._flush_immutable()

        self.immutable_memtable = self.memtable
        self.memtable = MemTable()

    def _flush_immutable(self):
        """Flush immutable memtable to SSTable."""
        if self.immutable_memtable is None:
            return

        # Create SSTable metadata
        sstable = SSTableInfo(
            id=str(uuid.uuid4())[:8],
            level=0,
            filename=f"l0_{uuid.uuid4()}.sst",
            size_bytes=self.immutable_memtable.size_bytes,
            entry_count=len(self.immutable_memtable.data),
            min_key=min(self.immutable_memtable.data.keys()) if self.immutable_memtable.data else "",
            max_key=max(self.immutable_memtable.data.keys()) if self.immutable_memtable.data else "",
            min_sequence=self.immutable_memtable.oldest_sequence,
            max_sequence=self.immutable_memtable.newest_sequence,
            created_at=self._current_time_ms(),
        )

        self.levels[0].append(sstable)
        self.immutable_memtable = None

        # Check if L0 needs compaction
        if len(self.levels[0]) >= 4:
            self._compact_level(0)

    def _compact_level(self, level: int):
        """Compact a level."""
        self.compaction_count += 1
        # Simplified: just merge L0 into L1
        if level == 0 and self.levels[0]:
            total_size = sum(s.size_bytes for s in self.levels[0])
            if self.levels[0]:
                merged = SSTableInfo(
                    id=str(uuid.uuid4())[:8],
                    level=1,
                    filename=f"l1_{uuid.uuid4()}.sst",
                    size_bytes=total_size,
                    entry_count=sum(s.entry_count for s in self.levels[0]),
                    min_key=min(s.min_key for s in self.levels[0]),
                    max_key=max(s.max_key for s in self.levels[0]),
                    min_sequence=min(s.min_sequence for s in self.levels[0]),
                    max_sequence=max(s.max_sequence for s in self.levels[0]),
                    created_at=self._current_time_ms(),
                )
                self.bytes_compacted += total_size
                self.levels[1].append(merged)
                self.levels[0] = []

    def flush(self) -> Optional[str]:
        """Force flush MemTable to disk."""
        with self.lock:
            if self.memtable.data:
                self._rotate_memtable()
            if self.immutable_memtable:
                self._flush_immutable()
            return self.levels[0][-1].id if self.levels[0] else None


class KVStoreNode:
    """Distributed KV Store node."""

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Storage engine
        self.lsm = LSMTree(node_id)

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False
        self.term = 0

        # Compaction state
        self.is_compacting = False

        # gRPC stubs
        self.peer_stubs: Dict[str, kv_store_lsm_pb2_grpc.ReplicationServiceStub] = {}

    async def initialize(self):
        """Initialize connections."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = kv_store_lsm_pb2_grpc.ReplicationServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"LSM KV Store node {self.node_id} initialized")

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)


class KVServicer(kv_store_lsm_pb2_grpc.KVServiceServicer):
    """gRPC service for KV operations."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def Get(self, request, context):
        """Handle Get RPC."""
        value, found, source = self.node.lsm.get(request.key)
        return kv_store_lsm_pb2.GetResponse(
            value=value or b"",
            found=found,
            sequence_number=self.node.lsm.sequence_number,
            source=source,
            served_by=self.node.node_id,
        )

    async def Put(self, request, context):
        """Handle Put RPC."""
        seq = self.node.lsm.put(request.key, request.value, request.sync)
        return kv_store_lsm_pb2.PutResponse(
            success=True,
            sequence_number=seq,
            served_by=self.node.node_id,
        )

    async def Delete(self, request, context):
        """Handle Delete RPC."""
        seq = self.node.lsm.delete(request.key, request.sync)
        return kv_store_lsm_pb2.DeleteResponse(
            success=True,
            sequence_number=seq,
            served_by=self.node.node_id,
        )

    async def Scan(self, request, context):
        """Handle Scan RPC."""
        results = self.node.lsm.scan(request.start_key, request.end_key, request.limit or 100)
        entries = [
            kv_store_lsm_pb2.KeyValue(key=k, value=v, sequence_number=s)
            for k, v, s in results
        ]
        return kv_store_lsm_pb2.ScanResponse(
            entries=entries,
            has_more=len(entries) >= (request.limit or 100),
        )

    async def BatchWrite(self, request, context):
        """Handle BatchWrite RPC."""
        count = 0
        seq = 0
        for op in request.operations:
            if op.type == kv_store_lsm_pb2.PUT:
                seq = self.node.lsm.put(op.key, op.value, request.sync)
            elif op.type == kv_store_lsm_pb2.DELETE:
                seq = self.node.lsm.delete(op.key, request.sync)
            count += 1
        return kv_store_lsm_pb2.BatchWriteResponse(
            success=True,
            sequence_number=seq,
            operations_count=count,
        )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return kv_store_lsm_pb2.GetLeaderResponse(
            node_id=self.node.node_id,
            node_address=f"localhost:{self.node.port}",
            is_leader=self.node.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.node.lock:
            members = [
                kv_store_lsm_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    is_leader=n.is_leader,
                    sequence_number=n.sequence_number,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.node.nodes.values()
            ]

            return kv_store_lsm_pb2.GetClusterStatusResponse(
                node_id=self.node.node_id,
                node_address=f"localhost:{self.node.port}",
                is_leader=self.node.is_leader,
                total_nodes=len(self.node.nodes),
                healthy_nodes=sum(1 for n in self.node.nodes.values() if n.is_healthy),
                total_keys=len(self.node.lsm.memtable.data),
                sequence_number=self.node.lsm.sequence_number,
                members=members,
            )


class StorageServicer(kv_store_lsm_pb2_grpc.StorageServiceServicer):
    """gRPC service for storage management."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def FlushMemTable(self, request, context):
        """Handle FlushMemTable RPC."""
        sstable_id = self.node.lsm.flush()
        return kv_store_lsm_pb2.FlushMemTableResponse(
            success=True,
            sstable_id=sstable_id or "",
        )

    async def TriggerCompaction(self, request, context):
        """Handle TriggerCompaction RPC."""
        if self.node.is_compacting:
            return kv_store_lsm_pb2.TriggerCompactionResponse(
                started=False,
                error="Compaction in progress",
            )

        self.node.is_compacting = True
        level = request.level or 0
        self.node.lsm._compact_level(level)
        self.node.is_compacting = False

        return kv_store_lsm_pb2.TriggerCompactionResponse(
            started=True,
            compaction_id=f"compact-{self.node._current_time_ms()}",
        )

    async def GetCompactionStatus(self, request, context):
        """Handle GetCompactionStatus RPC."""
        return kv_store_lsm_pb2.GetCompactionStatusResponse(
            is_running=self.node.is_compacting,
            progress_percent=100.0 if not self.node.is_compacting else 0.0,
        )

    async def GetStorageStats(self, request, context):
        """Handle GetStorageStats RPC."""
        lsm = self.node.lsm
        total_sstables = sum(len(level) for level in lsm.levels.values())
        total_bytes = sum(s.size_bytes for level in lsm.levels.values() for s in level)

        return kv_store_lsm_pb2.GetStorageStatsResponse(
            total_keys=len(lsm.memtable.data),
            sequence_number=lsm.sequence_number,
            memtable=kv_store_lsm_pb2.MemTableState(
                entry_count=len(lsm.memtable.data),
                size_bytes=lsm.memtable.size_bytes,
                max_size_bytes=lsm.memtable.max_size,
                oldest_sequence=lsm.memtable.oldest_sequence,
                newest_sequence=lsm.memtable.newest_sequence,
            ),
            total_sstables=total_sstables,
            total_storage_bytes=total_bytes,
            compaction_count=lsm.compaction_count,
            bytes_compacted=lsm.bytes_compacted,
        )

    async def GetLevels(self, request, context):
        """Handle GetLevels RPC."""
        levels = []
        for level_num, sstables in self.node.lsm.levels.items():
            level_info = kv_store_lsm_pb2.LevelInfo(
                level=level_num,
                sstables=[
                    kv_store_lsm_pb2.SSTableInfo(
                        id=s.id,
                        level=s.level,
                        filename=s.filename,
                        size_bytes=s.size_bytes,
                        entry_count=s.entry_count,
                        min_key=s.min_key,
                        max_key=s.max_key,
                        created_at=s.created_at,
                    )
                    for s in sstables
                ],
                total_size_bytes=sum(s.size_bytes for s in sstables),
                total_entries=sum(s.entry_count for s in sstables),
            )
            levels.append(level_info)

        return kv_store_lsm_pb2.GetLevelsResponse(
            levels=levels,
            memtable=kv_store_lsm_pb2.MemTableState(
                entry_count=len(self.node.lsm.memtable.data),
                size_bytes=self.node.lsm.memtable.size_bytes,
            ),
            total_sstables=sum(len(l) for l in self.node.lsm.levels.values()),
        )


class ReplicationServicer(kv_store_lsm_pb2_grpc.ReplicationServiceServicer):
    """gRPC service for replication."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def AppendEntries(self, request, context):
        """Handle AppendEntries RPC."""
        for entry in request.entries:
            if entry.type == kv_store_lsm_pb2.PUT:
                self.node.lsm.put(entry.key, entry.value)
            elif entry.type == kv_store_lsm_pb2.DELETE:
                self.node.lsm.delete(entry.key)

        return kv_store_lsm_pb2.AppendEntriesResponse(
            term=self.node.term,
            success=True,
            match_sequence=self.node.lsm.sequence_number,
        )

    async def RequestVote(self, request, context):
        """Handle RequestVote RPC."""
        vote_granted = request.term > self.node.term
        if vote_granted:
            self.node.term = request.term
        return kv_store_lsm_pb2.RequestVoteResponse(
            term=self.node.term,
            vote_granted=vote_granted,
        )

    async def TransferSSTable(self, request, context):
        """Handle TransferSSTable RPC."""
        return kv_store_lsm_pb2.TransferSSTableResponse(success=True)

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.node.lock:
            if request.node_id not in self.node.nodes:
                self.node.nodes[request.node_id] = NodeInfo(
                    node_id=request.node_id,
                    address="",
                )
            self.node.nodes[request.node_id].last_heartbeat = request.timestamp
            self.node.nodes[request.node_id].sequence_number = request.sequence_number

        return kv_store_lsm_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.node._current_time_ms(),
        )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the LSM KV store server."""
    node = KVStoreNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    kv_store_lsm_pb2_grpc.add_KVServiceServicer_to_server(KVServicer(node), server)
    kv_store_lsm_pb2_grpc.add_StorageServiceServicer_to_server(StorageServicer(node), server)
    kv_store_lsm_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting LSM Tree KV Store node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="LSM Tree KV Store Node")
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
