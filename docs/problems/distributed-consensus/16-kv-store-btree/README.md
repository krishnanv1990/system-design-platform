# KV Store with B+ Tree

## Problem Overview

Implement a distributed key-value store using B+ Tree storage for efficient range queries and ACID transactions.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Architecture Overview

B+ Tree storage (similar to InnoDB, PostgreSQL):
1. All values stored in leaf nodes (internal nodes only have keys)
2. Leaf nodes are linked for efficient range scans
3. Balanced tree ensures O(log n) operations
4. Page-based storage with buffer pool for caching
5. WAL for durability, transactions for ACID

### Implementation

```python
import os
import struct
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio

@dataclass
class Page:
    page_id: int
    page_type: str  # "INTERNAL", "LEAF", "OVERFLOW"
    level: int      # 0 = leaf, increases toward root
    keys: List[str]
    values: List[bytes]  # Only for leaf pages
    children: List[int]  # Only for internal pages
    next_leaf: int = 0
    prev_leaf: int = 0
    is_dirty: bool = False
    lsn: int = 0

class BufferPool:
    """LRU buffer pool for caching pages."""

    def __init__(self, size: int = 1000):
        self.size = size
        self.pages: Dict[int, Page] = {}
        self.lru_order: List[int] = []
        self.dirty_pages: set = set()
        self.hits = 0
        self.misses = 0

    def get(self, page_id: int) -> Optional[Page]:
        """Get a page from the buffer pool."""
        if page_id in self.pages:
            self.hits += 1
            self._update_lru(page_id)
            return self.pages[page_id]
        self.misses += 1
        return None

    def put(self, page: Page):
        """Put a page in the buffer pool."""
        if len(self.pages) >= self.size:
            self._evict()

        self.pages[page.page_id] = page
        self._update_lru(page.page_id)

    def mark_dirty(self, page_id: int):
        """Mark a page as dirty."""
        if page_id in self.pages:
            self.pages[page_id].is_dirty = True
            self.dirty_pages.add(page_id)

    def _update_lru(self, page_id: int):
        """Update LRU order."""
        if page_id in self.lru_order:
            self.lru_order.remove(page_id)
        self.lru_order.append(page_id)

    def _evict(self):
        """Evict LRU page."""
        for page_id in self.lru_order:
            if page_id not in self.dirty_pages:
                del self.pages[page_id]
                self.lru_order.remove(page_id)
                return

        # If all pages are dirty, flush and evict oldest
        oldest = self.lru_order[0]
        self.dirty_pages.discard(oldest)
        del self.pages[oldest]
        self.lru_order.pop(0)


class BPlusTree:
    """B+ Tree implementation with disk-based storage."""

    def __init__(self, directory: str, order: int = 100):
        self.directory = directory
        self.order = order  # Max keys per node
        self.min_keys = order // 2
        self.buffer_pool = BufferPool()
        self.root_page_id = 0
        self.next_page_id = 1
        self.height = 1
        self.lock = asyncio.Lock()

        os.makedirs(directory, exist_ok=True)

    async def open(self):
        """Open the B+ tree and load metadata."""
        meta_path = os.path.join(self.directory, "meta.dat")
        if os.path.exists(meta_path):
            with open(meta_path, 'rb') as f:
                data = f.read()
                self.root_page_id, self.next_page_id, self.height = struct.unpack('>iii', data)
        else:
            # Create root leaf page
            root = Page(
                page_id=0,
                page_type="LEAF",
                level=0,
                keys=[],
                values=[],
                children=[]
            )
            await self._write_page(root)
            self.buffer_pool.put(root)

    async def put(self, key: str, value: bytes) -> int:
        """Insert or update a key-value pair."""
        async with self.lock:
            lsn = int(time.time() * 1000)

            # Find leaf page
            leaf = await self._find_leaf(key)

            # Check if key exists
            idx = self._binary_search(leaf.keys, key)

            if idx < len(leaf.keys) and leaf.keys[idx] == key:
                # Update existing
                leaf.values[idx] = value
            else:
                # Insert new
                leaf.keys.insert(idx, key)
                leaf.values.insert(idx, value)

            leaf.lsn = lsn
            self.buffer_pool.mark_dirty(leaf.page_id)

            # Check if split needed
            if len(leaf.keys) > self.order:
                await self._split_leaf(leaf)

            return lsn

    async def get(self, key: str) -> Optional[bytes]:
        """Get a value by key."""
        leaf = await self._find_leaf(key)

        idx = self._binary_search(leaf.keys, key)

        if idx < len(leaf.keys) and leaf.keys[idx] == key:
            return leaf.values[idx]
        return None

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        async with self.lock:
            leaf = await self._find_leaf(key)

            idx = self._binary_search(leaf.keys, key)

            if idx >= len(leaf.keys) or leaf.keys[idx] != key:
                return False

            leaf.keys.pop(idx)
            leaf.values.pop(idx)
            self.buffer_pool.mark_dirty(leaf.page_id)

            # Handle underflow (simplified - no merge for brevity)
            return True

    async def scan(self, start_key: str, end_key: str = None,
                  limit: int = 100) -> List[Tuple[str, bytes]]:
        """Range scan from start_key to end_key."""
        results = []

        leaf = await self._find_leaf(start_key)
        idx = self._binary_search(leaf.keys, start_key)

        while leaf and len(results) < limit:
            while idx < len(leaf.keys) and len(results) < limit:
                key = leaf.keys[idx]

                if end_key and key >= end_key:
                    return results

                if key >= start_key:
                    results.append((key, leaf.values[idx]))

                idx += 1

            # Move to next leaf
            if leaf.next_leaf:
                leaf = await self._read_page(leaf.next_leaf)
                idx = 0
            else:
                break

        return results

    async def _find_leaf(self, key: str) -> Page:
        """Find the leaf page for a key."""
        page = await self._read_page(self.root_page_id)

        while page.page_type == "INTERNAL":
            idx = self._binary_search(page.keys, key)
            child_id = page.children[min(idx, len(page.children) - 1)]
            page = await self._read_page(child_id)

        return page

    async def _split_leaf(self, leaf: Page):
        """Split a full leaf page."""
        mid = len(leaf.keys) // 2

        # Create new leaf
        new_leaf = Page(
            page_id=self.next_page_id,
            page_type="LEAF",
            level=0,
            keys=leaf.keys[mid:],
            values=leaf.values[mid:],
            children=[],
            prev_leaf=leaf.page_id,
            next_leaf=leaf.next_leaf
        )
        self.next_page_id += 1

        # Update original leaf
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        leaf.next_leaf = new_leaf.page_id

        await self._write_page(new_leaf)
        await self._write_page(leaf)

        # Promote middle key to parent
        await self._insert_into_parent(leaf, new_leaf.keys[0], new_leaf)

    async def _insert_into_parent(self, left: Page, key: str, right: Page):
        """Insert a key into the parent node."""
        # Simplified - full implementation would handle parent splits
        if left.page_id == self.root_page_id:
            # Create new root
            new_root = Page(
                page_id=self.next_page_id,
                page_type="INTERNAL",
                level=self.height,
                keys=[key],
                values=[],
                children=[left.page_id, right.page_id]
            )
            self.next_page_id += 1
            self.root_page_id = new_root.page_id
            self.height += 1

            await self._write_page(new_root)

    def _binary_search(self, keys: List[str], target: str) -> int:
        """Binary search for insertion point."""
        left, right = 0, len(keys)
        while left < right:
            mid = (left + right) // 2
            if keys[mid] < target:
                left = mid + 1
            else:
                right = mid
        return left

    async def _read_page(self, page_id: int) -> Page:
        """Read a page from buffer pool or disk."""
        page = self.buffer_pool.get(page_id)
        if page:
            return page

        filename = os.path.join(self.directory, f"page_{page_id:08d}.dat")
        if not os.path.exists(filename):
            raise ValueError(f"Page {page_id} not found")

        # Read from disk (simplified)
        with open(filename, 'rb') as f:
            data = f.read()
            page = self._deserialize_page(page_id, data)

        self.buffer_pool.put(page)
        return page

    async def _write_page(self, page: Page):
        """Write a page to disk."""
        filename = os.path.join(self.directory, f"page_{page.page_id:08d}.dat")
        data = self._serialize_page(page)

        with open(filename, 'wb') as f:
            f.write(data)

        self.buffer_pool.put(page)
```

---

## Platform Deployment

### Cluster Configuration

- 3+ node cluster with Raft replication
- Leader handles writes, replicates WAL entries
- Buffer pool on each node for caching

### gRPC Services

```protobuf
service KVService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
    rpc Scan(ScanRequest) returns (ScanResponse);
    rpc BeginTransaction(BeginTransactionRequest) returns (BeginTransactionResponse);
    rpc CommitTransaction(CommitTransactionRequest) returns (CommitTransactionResponse);
}

service StorageService {
    rpc Checkpoint(CheckpointRequest) returns (CheckpointResponse);
    rpc GetTreeStats(GetTreeStatsRequest) returns (GetTreeStatsResponse);
    rpc GetBufferPoolStats(GetBufferPoolStatsRequest) returns (GetBufferPoolStatsResponse);
}
```

---

## Realistic Testing

```python
class TestBPlusTree:
    async def test_basic_operations(self, cluster):
        """Put/Get work correctly."""
        leader = await find_leader(cluster)

        await leader.Put(key="hello", value=b"world")
        response = await leader.Get(key="hello")

        assert response.found
        assert response.value == b"world"

    async def test_range_scan(self, cluster):
        """Range scan returns sorted results."""
        leader = await find_leader(cluster)

        for i in range(100):
            await leader.Put(key=f"key_{i:03d}", value=f"value_{i}".encode())

        results = await leader.Scan(
            start_key="key_020",
            end_key="key_030"
        )

        assert len(results.entries) == 10
        assert results.entries[0].key == "key_020"
        assert results.entries[-1].key == "key_029"

    async def test_buffer_pool_hit_ratio(self, cluster):
        """Buffer pool provides good cache hit ratio."""
        leader = await find_leader(cluster)

        # Insert data
        for i in range(1000):
            await leader.Put(key=f"key_{i}", value=b"value")

        # Read same keys
        for i in range(1000):
            await leader.Get(key=f"key_{i % 100}")

        stats = await leader.GetBufferPoolStats()

        assert stats.stats.hit_ratio > 0.9  # > 90% hit ratio

    async def test_tree_balance(self, cluster):
        """Tree remains balanced after inserts."""
        leader = await find_leader(cluster)

        for i in range(10000):
            await leader.Put(key=f"key_{i:05d}", value=b"value")

        stats = await leader.GetTreeStats()

        # Height should be logarithmic
        # For order 100 and 10000 keys: log_100(10000) ≈ 2
        assert stats.stats.height <= 3
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Operations | Put/Get/Delete work correctly |
| Range Scan | Efficient O(log n + k) range queries |
| Buffer Pool | > 80% cache hit ratio |
| Tree Balance | Height = O(log n) |
