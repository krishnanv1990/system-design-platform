"""
Distributed KV Store with B+ Tree - Python Template

This template provides the basic structure for implementing a
distributed key-value store using B+ Tree storage.

B+ Tree Architecture:
1. All values stored in leaf nodes (internal nodes only have keys)
2. Leaf nodes are linked for efficient range scans
3. Balanced tree ensures O(log n) operations
4. Page-based storage with buffer pool for caching
5. WAL for durability, transactions for ACID

Similar to: InnoDB, PostgreSQL, SQLite, BoltDB

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
import kv_store_btree_pb2
import kv_store_btree_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PAGE_SIZE = 4096
BRANCHING_FACTOR = 128
BUFFER_POOL_SIZE = 1000


class PageType(Enum):
    INTERNAL = 0
    LEAF = 1


class TransactionState(Enum):
    ACTIVE = 0
    COMMITTED = 1
    ABORTED = 2


class IsolationLevel(Enum):
    READ_UNCOMMITTED = 0
    READ_COMMITTED = 1
    REPEATABLE_READ = 2
    SERIALIZABLE = 3


@dataclass
class Page:
    """B+ Tree page."""
    page_id: int
    page_type: PageType
    level: int  # 0 = leaf
    keys: List[str] = field(default_factory=list)
    values: List[bytes] = field(default_factory=list)  # For leaf nodes
    children: List[int] = field(default_factory=list)  # For internal nodes
    next_leaf: Optional[int] = None
    prev_leaf: Optional[int] = None
    is_dirty: bool = False
    lsn: int = 0


@dataclass
class Transaction:
    """Transaction state."""
    transaction_id: int
    state: TransactionState
    start_lsn: int
    start_timestamp: int
    modified_keys: List[str] = field(default_factory=list)
    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED


@dataclass
class NodeInfo:
    """Cluster node information."""
    node_id: str
    address: str
    is_healthy: bool = True
    is_leader: bool = False
    lsn: int = 0
    last_heartbeat: int = 0


class BufferPool:
    """
    Buffer pool for caching B+ Tree pages.

    TODO: Implement buffer pool:
    1. get_page() - Get page from cache or read from disk
    2. put_page() - Add page to cache
    3. flush() - Write dirty pages to disk
    4. evict() - Remove pages using LRU policy
    """

    def __init__(self, max_size: int = BUFFER_POOL_SIZE):
        self.pages: Dict[int, Page] = {}
        self.max_size = max_size
        self.cache_hits = 0
        self.cache_misses = 0
        self.evictions = 0

    def get_page(self, page_id: int) -> Optional[Page]:
        """Get page from buffer pool."""
        if page_id in self.pages:
            self.cache_hits += 1
            return self.pages[page_id]
        self.cache_misses += 1
        return None

    def put_page(self, page: Page):
        """Put page into buffer pool."""
        if len(self.pages) >= self.max_size:
            self._evict()
        self.pages[page.page_id] = page

    def _evict(self):
        """Evict a page (simple FIFO for now)."""
        if self.pages:
            # Find non-dirty page to evict
            for page_id, page in list(self.pages.items()):
                if not page.is_dirty:
                    del self.pages[page_id]
                    self.evictions += 1
                    return

    def flush_all(self) -> int:
        """Flush all dirty pages."""
        flushed = 0
        for page in self.pages.values():
            if page.is_dirty:
                page.is_dirty = False
                flushed += 1
        return flushed

    @property
    def hit_ratio(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class BPlusTree:
    """
    B+ Tree implementation.

    TODO: Implement B+ Tree:
    1. insert() - Insert key-value, split nodes if needed
    2. search() - Find value by key
    3. delete() - Delete key, merge nodes if needed
    4. scan() - Range scan using leaf pointers
    """

    def __init__(self, node_id: str, branching_factor: int = BRANCHING_FACTOR):
        self.node_id = node_id
        self.branching_factor = branching_factor
        self.lock = threading.RLock()

        # Buffer pool
        self.buffer_pool = BufferPool()

        # Root page
        self.root_page_id = 0
        self.next_page_id = 1

        # Initialize root as leaf
        root = Page(
            page_id=0,
            page_type=PageType.LEAF,
            level=0,
        )
        self.buffer_pool.put_page(root)

        # WAL
        self.lsn = 0
        self.checkpoint_lsn = 0

        # Stats
        self.total_pages = 1
        self.height = 1
        self.total_keys = 0

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)

    def _new_page(self, page_type: PageType, level: int) -> Page:
        """Create a new page."""
        page = Page(
            page_id=self.next_page_id,
            page_type=page_type,
            level=level,
        )
        self.next_page_id += 1
        self.total_pages += 1
        self.buffer_pool.put_page(page)
        return page

    def insert(self, key: str, value: bytes) -> int:
        """
        Insert a key-value pair.

        TODO: Implement insert:
        1. Find the leaf page for this key
        2. Insert into leaf
        3. If leaf is full, split and propagate up
        4. Update WAL
        """
        with self.lock:
            self.lsn += 1

            # Find leaf page
            leaf = self._find_leaf(key)

            # Find insert position
            idx = bisect.bisect_left(leaf.keys, key)

            # Check if key exists
            if idx < len(leaf.keys) and leaf.keys[idx] == key:
                # Update existing
                leaf.values[idx] = value
            else:
                # Insert new
                leaf.keys.insert(idx, key)
                leaf.values.insert(idx, value)
                self.total_keys += 1

            leaf.is_dirty = True
            leaf.lsn = self.lsn

            # Check if split needed
            if len(leaf.keys) > self.branching_factor:
                self._split_leaf(leaf)

            return self.lsn

    def search(self, key: str) -> Tuple[Optional[bytes], bool]:
        """Search for a key."""
        with self.lock:
            leaf = self._find_leaf(key)
            idx = bisect.bisect_left(leaf.keys, key)

            if idx < len(leaf.keys) and leaf.keys[idx] == key:
                return (leaf.values[idx], True)
            return (None, False)

    def delete(self, key: str) -> Tuple[bool, int]:
        """Delete a key."""
        with self.lock:
            self.lsn += 1

            leaf = self._find_leaf(key)
            idx = bisect.bisect_left(leaf.keys, key)

            if idx < len(leaf.keys) and leaf.keys[idx] == key:
                leaf.keys.pop(idx)
                leaf.values.pop(idx)
                leaf.is_dirty = True
                leaf.lsn = self.lsn
                self.total_keys -= 1
                return (True, self.lsn)

            return (False, self.lsn)

    def scan(self, start_key: str, end_key: str, limit: int = 100) -> List[Tuple[str, bytes]]:
        """
        Scan a range of keys.

        TODO: Implement scan using leaf pointers for efficiency.
        """
        with self.lock:
            results = []
            leaf = self._find_leaf(start_key)

            while leaf is not None:
                for i, key in enumerate(leaf.keys):
                    if start_key and key < start_key:
                        continue
                    if end_key and key >= end_key:
                        return results
                    results.append((key, leaf.values[i]))
                    if len(results) >= limit:
                        return results

                # Move to next leaf
                if leaf.next_leaf is not None:
                    leaf = self.buffer_pool.get_page(leaf.next_leaf)
                else:
                    break

            return results

    def _find_leaf(self, key: str) -> Page:
        """Find the leaf page for a key."""
        page = self.buffer_pool.get_page(self.root_page_id)

        while page.page_type == PageType.INTERNAL:
            idx = bisect.bisect_right(page.keys, key)
            child_id = page.children[idx] if idx < len(page.children) else page.children[-1]
            page = self.buffer_pool.get_page(child_id)

        return page

    def _split_leaf(self, leaf: Page):
        """Split a leaf page."""
        mid = len(leaf.keys) // 2

        # Create new leaf
        new_leaf = self._new_page(PageType.LEAF, 0)
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.values = leaf.values[mid:]
        new_leaf.next_leaf = leaf.next_leaf
        new_leaf.prev_leaf = leaf.page_id

        # Update old leaf
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        leaf.next_leaf = new_leaf.page_id

        # Promote middle key to parent
        promoted_key = new_leaf.keys[0]
        self._insert_into_parent(leaf, promoted_key, new_leaf)

    def _insert_into_parent(self, left: Page, key: str, right: Page):
        """Insert into parent (simplified - creates new root if needed)."""
        # For simplicity, just create a new root
        if left.page_id == self.root_page_id:
            new_root = self._new_page(PageType.INTERNAL, self.height)
            new_root.keys = [key]
            new_root.children = [left.page_id, right.page_id]
            self.root_page_id = new_root.page_id
            self.height += 1


class KVStoreNode:
    """Distributed KV Store node."""

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Storage engine
        self.tree = BPlusTree(node_id)

        # Transactions
        self.transactions: Dict[int, Transaction] = {}
        self.next_tx_id = 1

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False
        self.term = 0

        # Stats
        self.committed_transactions = 0
        self.aborted_transactions = 0
        self.pages_read = 0
        self.pages_written = 0

        # gRPC stubs
        self.peer_stubs: Dict[str, kv_store_btree_pb2_grpc.ReplicationServiceStub] = {}

    async def initialize(self):
        """Initialize connections."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = kv_store_btree_pb2_grpc.ReplicationServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"B+ Tree KV Store node {self.node_id} initialized")

    def _current_time_ms(self) -> int:
        return int(time.time() * 1000)

    def begin_transaction(self, isolation: IsolationLevel = IsolationLevel.READ_COMMITTED) -> int:
        """Begin a new transaction."""
        with self.lock:
            tx_id = self.next_tx_id
            self.next_tx_id += 1

            self.transactions[tx_id] = Transaction(
                transaction_id=tx_id,
                state=TransactionState.ACTIVE,
                start_lsn=self.tree.lsn,
                start_timestamp=self._current_time_ms(),
                isolation_level=isolation,
            )
            return tx_id

    def commit_transaction(self, tx_id: int) -> Tuple[bool, int]:
        """Commit a transaction."""
        with self.lock:
            if tx_id not in self.transactions:
                return (False, 0)

            tx = self.transactions[tx_id]
            tx.state = TransactionState.COMMITTED
            self.committed_transactions += 1
            return (True, self.tree.lsn)

    def rollback_transaction(self, tx_id: int) -> bool:
        """Rollback a transaction."""
        with self.lock:
            if tx_id not in self.transactions:
                return False

            tx = self.transactions[tx_id]
            tx.state = TransactionState.ABORTED
            self.aborted_transactions += 1
            return True


class KVServicer(kv_store_btree_pb2_grpc.KVServiceServicer):
    """gRPC service for KV operations."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def Get(self, request, context):
        """Handle Get RPC."""
        value, found = self.node.tree.search(request.key)
        return kv_store_btree_pb2.GetResponse(
            value=value or b"",
            found=found,
            served_by=self.node.node_id,
        )

    async def Put(self, request, context):
        """Handle Put RPC."""
        lsn = self.node.tree.insert(request.key, request.value)
        return kv_store_btree_pb2.PutResponse(
            success=True,
            lsn=lsn,
            served_by=self.node.node_id,
        )

    async def Delete(self, request, context):
        """Handle Delete RPC."""
        existed, lsn = self.node.tree.delete(request.key)
        return kv_store_btree_pb2.DeleteResponse(
            success=True,
            existed=existed,
            lsn=lsn,
            served_by=self.node.node_id,
        )

    async def Scan(self, request, context):
        """Handle Scan RPC."""
        results = self.node.tree.scan(request.start_key, request.end_key, request.limit or 100)
        entries = [
            kv_store_btree_pb2.KeyValue(key=k, value=v)
            for k, v in results
        ]
        return kv_store_btree_pb2.ScanResponse(
            entries=entries,
            has_more=len(entries) >= (request.limit or 100),
        )

    async def BeginTransaction(self, request, context):
        """Handle BeginTransaction RPC."""
        iso = IsolationLevel(request.isolation_level) if request.isolation_level else IsolationLevel.READ_COMMITTED
        tx_id = self.node.begin_transaction(iso)
        return kv_store_btree_pb2.BeginTransactionResponse(
            success=True,
            transaction_id=tx_id,
        )

    async def CommitTransaction(self, request, context):
        """Handle CommitTransaction RPC."""
        success, lsn = self.node.commit_transaction(request.transaction_id)
        return kv_store_btree_pb2.CommitTransactionResponse(
            success=success,
            commit_lsn=lsn,
        )

    async def RollbackTransaction(self, request, context):
        """Handle RollbackTransaction RPC."""
        success = self.node.rollback_transaction(request.transaction_id)
        return kv_store_btree_pb2.RollbackTransactionResponse(success=success)

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return kv_store_btree_pb2.GetLeaderResponse(
            node_id=self.node.node_id,
            node_address=f"localhost:{self.node.port}",
            is_leader=self.node.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.node.lock:
            members = [
                kv_store_btree_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    is_leader=n.is_leader,
                    lsn=n.lsn,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.node.nodes.values()
            ]

            return kv_store_btree_pb2.GetClusterStatusResponse(
                node_id=self.node.node_id,
                node_address=f"localhost:{self.node.port}",
                is_leader=self.node.is_leader,
                total_nodes=len(self.node.nodes),
                healthy_nodes=sum(1 for n in self.node.nodes.values() if n.is_healthy),
                total_keys=self.node.tree.total_keys,
                current_lsn=self.node.tree.lsn,
                members=members,
            )


class StorageServicer(kv_store_btree_pb2_grpc.StorageServiceServicer):
    """gRPC service for storage management."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def Checkpoint(self, request, context):
        """Handle Checkpoint RPC."""
        flushed = self.node.tree.buffer_pool.flush_all()
        self.node.tree.checkpoint_lsn = self.node.tree.lsn
        return kv_store_btree_pb2.CheckpointResponse(
            success=True,
            checkpoint_lsn=self.node.tree.checkpoint_lsn,
            pages_flushed=flushed,
        )

    async def GetTreeStats(self, request, context):
        """Handle GetTreeStats RPC."""
        tree = self.node.tree
        return kv_store_btree_pb2.GetTreeStatsResponse(
            stats=kv_store_btree_pb2.TreeStats(
                root_page_id=tree.root_page_id,
                height=tree.height,
                total_pages=tree.total_pages,
                total_keys=tree.total_keys,
                branching_factor=tree.branching_factor,
            ),
        )

    async def GetBufferPoolStats(self, request, context):
        """Handle GetBufferPoolStats RPC."""
        bp = self.node.tree.buffer_pool
        return kv_store_btree_pb2.GetBufferPoolStatsResponse(
            stats=kv_store_btree_pb2.BufferPoolStats(
                pool_size_pages=bp.max_size,
                pages_in_use=len(bp.pages),
                dirty_pages=sum(1 for p in bp.pages.values() if p.is_dirty),
                cache_hits=bp.cache_hits,
                cache_misses=bp.cache_misses,
                hit_ratio=bp.hit_ratio,
                evictions=bp.evictions,
            ),
        )

    async def GetStorageStats(self, request, context):
        """Handle GetStorageStats RPC."""
        tree = self.node.tree
        bp = tree.buffer_pool

        return kv_store_btree_pb2.GetStorageStatsResponse(
            tree=kv_store_btree_pb2.TreeStats(
                root_page_id=tree.root_page_id,
                height=tree.height,
                total_pages=tree.total_pages,
                total_keys=tree.total_keys,
            ),
            buffer_pool=kv_store_btree_pb2.BufferPoolStats(
                pool_size_pages=bp.max_size,
                pages_in_use=len(bp.pages),
                cache_hits=bp.cache_hits,
                cache_misses=bp.cache_misses,
                hit_ratio=bp.hit_ratio,
            ),
            current_lsn=tree.lsn,
            checkpoint_lsn=tree.checkpoint_lsn,
            active_transactions=sum(1 for t in self.node.transactions.values() if t.state == TransactionState.ACTIVE),
            committed_transactions=self.node.committed_transactions,
            aborted_transactions=self.node.aborted_transactions,
            pages_read=self.node.pages_read,
            pages_written=self.node.pages_written,
        )


class ReplicationServicer(kv_store_btree_pb2_grpc.ReplicationServiceServicer):
    """gRPC service for replication."""

    def __init__(self, node: KVStoreNode):
        self.node = node

    async def AppendEntries(self, request, context):
        """Handle AppendEntries RPC."""
        return kv_store_btree_pb2.AppendEntriesResponse(
            term=self.node.term,
            success=True,
            match_lsn=self.node.tree.lsn,
        )

    async def RequestVote(self, request, context):
        """Handle RequestVote RPC."""
        vote_granted = request.term > self.node.term
        if vote_granted:
            self.node.term = request.term
        return kv_store_btree_pb2.RequestVoteResponse(
            term=self.node.term,
            vote_granted=vote_granted,
        )

    async def TransferPage(self, request, context):
        """Handle TransferPage RPC."""
        return kv_store_btree_pb2.TransferPageResponse(success=True)

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.node.lock:
            if request.node_id not in self.node.nodes:
                self.node.nodes[request.node_id] = NodeInfo(
                    node_id=request.node_id,
                    address="",
                )
            self.node.nodes[request.node_id].last_heartbeat = request.timestamp
            self.node.nodes[request.node_id].lsn = request.lsn

        return kv_store_btree_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.node._current_time_ms(),
        )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the B+ Tree KV store server."""
    node = KVStoreNode(node_id, port, peers)
    await node.initialize()

    server = aio.server()
    kv_store_btree_pb2_grpc.add_KVServiceServicer_to_server(KVServicer(node), server)
    kv_store_btree_pb2_grpc.add_StorageServiceServicer_to_server(StorageServicer(node), server)
    kv_store_btree_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationServicer(node), server)

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting B+ Tree KV Store node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="B+ Tree KV Store Node")
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
