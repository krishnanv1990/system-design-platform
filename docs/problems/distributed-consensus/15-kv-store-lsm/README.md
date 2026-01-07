# KV Store with LSM Tree

## Problem Overview

Implement a distributed key-value store using a Log-Structured Merge Tree (LSM Tree) for high write throughput with efficient reads.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution

### Architecture Overview

LSM Tree structure:
1. **MemTable:** In-memory sorted structure (red-black tree, skip list)
2. **WAL:** Write-ahead log for durability
3. **SSTables:** Immutable sorted string tables on disk
4. **Levels:** SSTables organized in levels (L0, L1, ..., Ln)
5. **Compaction:** Merge SSTables across levels to reduce read amplification

### Implementation

```python
import os
import struct
from typing import Dict, List, Optional, Iterator
from sortedcontainers import SortedDict
from dataclasses import dataclass
import asyncio
import time
import bloomfilter

@dataclass
class SSTableInfo:
    id: str
    level: int
    filename: str
    size_bytes: int
    entry_count: int
    min_key: str
    max_key: str
    bloom_filter: Optional[bloomfilter.BloomFilter]

class MemTable:
    """In-memory sorted table."""

    def __init__(self, max_size: int = 4 * 1024 * 1024):
        self.data: SortedDict = SortedDict()
        self.max_size = max_size
        self.size = 0
        self.sequence_number = 0

    def put(self, key: str, value: bytes) -> int:
        """Put a key-value pair."""
        old_size = len(self.data.get(key, b''))
        self.data[key] = ('PUT', value)
        self.size += len(key) + len(value) - old_size
        self.sequence_number += 1
        return self.sequence_number

    def delete(self, key: str) -> int:
        """Delete a key (write tombstone)."""
        self.data[key] = ('DELETE', b'')
        self.sequence_number += 1
        return self.sequence_number

    def get(self, key: str) -> tuple:
        """Get value for key. Returns (found, value, is_tombstone)."""
        if key in self.data:
            op, value = self.data[key]
            return (True, value, op == 'DELETE')
        return (False, None, False)

    def is_full(self) -> bool:
        """Check if memtable is full."""
        return self.size >= self.max_size

    def items(self) -> Iterator:
        """Iterate over all items."""
        for key, (op, value) in self.data.items():
            yield (key, op, value)


class SSTable:
    """Immutable sorted string table on disk."""

    @staticmethod
    def write(filename: str, entries: List[tuple], level: int) -> SSTableInfo:
        """Write entries to an SSTable file."""
        # Build bloom filter
        bf = bloomfilter.BloomFilter(len(entries) or 1, 0.01)

        with open(filename, 'wb') as f:
            # Write entries
            min_key = None
            max_key = None

            for key, op, value in entries:
                bf.add(key)

                if min_key is None:
                    min_key = key
                max_key = key

                key_bytes = key.encode()
                type_byte = 0 if op == 'PUT' else 1

                # Format: [type:1][key_len:4][value_len:4][key][value]
                entry = struct.pack('>Bii', type_byte, len(key_bytes), len(value))
                entry += key_bytes + value
                f.write(entry)

        file_size = os.path.getsize(filename)

        return SSTableInfo(
            id=os.path.basename(filename),
            level=level,
            filename=filename,
            size_bytes=file_size,
            entry_count=len(entries),
            min_key=min_key or "",
            max_key=max_key or "",
            bloom_filter=bf
        )

    @staticmethod
    def read_all(filename: str) -> List[tuple]:
        """Read all entries from an SSTable."""
        entries = []

        with open(filename, 'rb') as f:
            while True:
                header = f.read(9)
                if len(header) < 9:
                    break

                type_byte, key_len, value_len = struct.unpack('>Bii', header)
                op = 'PUT' if type_byte == 0 else 'DELETE'

                key = f.read(key_len).decode()
                value = f.read(value_len)

                entries.append((key, op, value))

        return entries

    @staticmethod
    def search(filename: str, target_key: str, bloom_filter=None) -> Optional[tuple]:
        """Search for a key in an SSTable."""
        # Check bloom filter first
        if bloom_filter and target_key not in bloom_filter:
            return None

        # Binary search would be better, but linear for simplicity
        with open(filename, 'rb') as f:
            while True:
                header = f.read(9)
                if len(header) < 9:
                    break

                type_byte, key_len, value_len = struct.unpack('>Bii', header)
                op = 'PUT' if type_byte == 0 else 'DELETE'

                key = f.read(key_len).decode()
                value = f.read(value_len)

                if key == target_key:
                    return (op, value)
                elif key > target_key:
                    return None  # Keys are sorted

        return None


class LSMTree:
    """Log-Structured Merge Tree implementation."""

    def __init__(self, directory: str):
        self.directory = directory
        self.memtable = MemTable()
        self.immutable_memtable: Optional[MemTable] = None
        self.levels: List[List[SSTableInfo]] = [[] for _ in range(7)]  # L0-L6
        self.wal_file = None
        self.lock = asyncio.Lock()
        self.compaction_running = False

        os.makedirs(directory, exist_ok=True)

    async def open(self):
        """Open WAL and recover state."""
        wal_path = os.path.join(self.directory, "wal.log")
        await self._recover_from_wal(wal_path)
        self.wal_file = open(wal_path, 'ab')
        await self._load_sstables()

    async def put(self, key: str, value: bytes, sync: bool = False) -> int:
        """Put a key-value pair."""
        async with self.lock:
            # Write to WAL first
            self._write_wal('PUT', key, value)
            if sync:
                self.wal_file.flush()
                os.fsync(self.wal_file.fileno())

            seq = self.memtable.put(key, value)

            if self.memtable.is_full():
                await self._flush_memtable()

            return seq

    async def get(self, key: str) -> Optional[bytes]:
        """Get a value by key."""
        # Check memtable first
        found, value, is_tombstone = self.memtable.get(key)
        if found:
            return None if is_tombstone else value

        # Check immutable memtable
        if self.immutable_memtable:
            found, value, is_tombstone = self.immutable_memtable.get(key)
            if found:
                return None if is_tombstone else value

        # Check SSTables (L0 to Ln)
        for level_idx, level in enumerate(self.levels):
            for sstable in reversed(level):  # Newer first
                result = SSTable.search(
                    sstable.filename,
                    key,
                    sstable.bloom_filter
                )
                if result:
                    op, value = result
                    return None if op == 'DELETE' else value

        return None

    async def delete(self, key: str) -> int:
        """Delete a key (write tombstone)."""
        async with self.lock:
            self._write_wal('DELETE', key, b'')
            return self.memtable.delete(key)

    async def _flush_memtable(self):
        """Flush memtable to L0 SSTable."""
        self.immutable_memtable = self.memtable
        self.memtable = MemTable()

        # Write SSTable
        entries = list(self.immutable_memtable.items())
        sstable_id = f"sstable_{int(time.time() * 1000)}_L0"
        filename = os.path.join(self.directory, f"{sstable_id}.sst")

        sstable_info = SSTable.write(filename, entries, level=0)
        self.levels[0].append(sstable_info)

        self.immutable_memtable = None

        # Clear WAL
        self.wal_file.close()
        wal_path = os.path.join(self.directory, "wal.log")
        self.wal_file = open(wal_path, 'wb')

        # Trigger compaction if needed
        if len(self.levels[0]) >= 4:
            asyncio.create_task(self._compact())

    async def _compact(self):
        """Compact SSTables."""
        if self.compaction_running:
            return

        self.compaction_running = True

        try:
            # L0 -> L1 compaction (all L0 files overlap)
            if len(self.levels[0]) >= 4:
                await self._compact_level(0)

            # L1+ size-based compaction
            for level in range(1, len(self.levels) - 1):
                level_size = sum(s.size_bytes for s in self.levels[level])
                threshold = (10 ** level) * 10 * 1024 * 1024  # 10MB * 10^level

                if level_size > threshold:
                    await self._compact_level(level)

        finally:
            self.compaction_running = False

    async def _compact_level(self, level: int):
        """Compact a level into the next."""
        async with self.lock:
            # Merge all entries from both levels
            entries = {}

            # Read current level
            for sstable in self.levels[level]:
                for key, op, value in SSTable.read_all(sstable.filename):
                    entries[key] = (op, value)

            # Read overlapping from next level
            next_level = level + 1
            for sstable in self.levels[next_level]:
                for key, op, value in SSTable.read_all(sstable.filename):
                    if key not in entries:  # Current level wins
                        entries[key] = (op, value)

            # Write new SSTable at next level
            sorted_entries = [
                (k, op, v) for k, (op, v) in sorted(entries.items())
            ]

            sstable_id = f"sstable_{int(time.time() * 1000)}_L{next_level}"
            filename = os.path.join(self.directory, f"{sstable_id}.sst")

            new_sstable = SSTable.write(filename, sorted_entries, level=next_level)

            # Remove old SSTables
            for sstable in self.levels[level]:
                os.remove(sstable.filename)
            for sstable in self.levels[next_level]:
                os.remove(sstable.filename)

            self.levels[level] = []
            self.levels[next_level] = [new_sstable]

    def _write_wal(self, op: str, key: str, value: bytes):
        """Write entry to WAL."""
        key_bytes = key.encode()
        type_byte = 0 if op == 'PUT' else 1
        entry = struct.pack('>Bii', type_byte, len(key_bytes), len(value))
        entry += key_bytes + value
        self.wal_file.write(entry)
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** with Raft replication
- Leader handles writes, replicates WAL entries
- Background compaction on each node
- Tolerates 2 node failures (Raft quorum: 3/5)

### gRPC Services

```protobuf
service KVService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
    rpc Scan(ScanRequest) returns (ScanResponse);
    rpc BatchWrite(BatchWriteRequest) returns (BatchWriteResponse);
}

service StorageService {
    rpc FlushMemTable(FlushMemTableRequest) returns (FlushMemTableResponse);
    rpc TriggerCompaction(TriggerCompactionRequest) returns (TriggerCompactionResponse);
    rpc GetLevels(GetLevelsRequest) returns (GetLevelsResponse);
}
```

---

## Realistic Testing

```python
class TestLSMTree:
    async def test_basic_operations(self, cluster):
        """Put/Get work correctly."""
        leader = await find_leader(cluster)

        await leader.Put(key="hello", value=b"world")
        response = await leader.Get(key="hello")

        assert response.found
        assert response.value == b"world"

    async def test_compaction_merges_levels(self, cluster):
        """Compaction merges SSTables correctly."""
        leader = await find_leader(cluster)

        # Write enough to trigger multiple flushes
        for i in range(10000):
            await leader.Put(key=f"key_{i:05d}", value=f"value_{i}".encode())

        # Check levels before compaction
        levels_before = await leader.GetLevels()
        l0_count = len(levels_before.levels[0].sstables)

        # Trigger compaction
        await leader.TriggerCompaction()
        await asyncio.sleep(5)

        # L0 should have fewer SSTables
        levels_after = await leader.GetLevels()
        assert len(levels_after.levels[0].sstables) < l0_count

    async def test_bloom_filter_effectiveness(self, cluster):
        """Bloom filter reduces unnecessary disk reads."""
        leader = await find_leader(cluster)

        # Insert keys
        for i in range(1000):
            await leader.Put(key=f"key_{i}", value=b"value")

        # Force flush
        await leader.FlushMemTable()

        # Query non-existent keys
        stats_before = await leader.GetStorageStats()

        for i in range(1000):
            await leader.Get(key=f"nonexistent_{i}")

        stats_after = await leader.GetStorageStats()

        # Most queries should be filtered by bloom filter
        # Read amplification should be low
        assert stats_after.read_amplification < 2.0
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Operations | Put/Get/Delete work correctly |
| Compaction | Merges levels properly |
| Bloom Filter | Low false positive rate |
| Write Throughput | > 10,000 writes/second |
