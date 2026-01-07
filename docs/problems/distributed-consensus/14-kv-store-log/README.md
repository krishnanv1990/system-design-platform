# KV Store with Append-Only Log

## Problem Overview

Implement a distributed key-value store using log-structured storage with append-only writes and compaction.

**Difficulty:** Hard (L6 - Staff Engineer)

---

## Best Solution

### Architecture Overview

Log-structured storage (similar to Bitcask):
1. All writes are appended to an immutable log (fast writes)
2. An in-memory hash table maps keys to log offsets (fast reads)
3. Compaction removes outdated entries to reclaim space
4. Log is divided into segments for easier management

### Implementation

```python
import os
import struct
import hashlib
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, List
import mmap

@dataclass
class LogEntry:
    offset: int
    timestamp: int
    entry_type: str  # "PUT" or "DELETE"
    key: str
    value: bytes
    checksum: int

@dataclass
class KeyDirEntry:
    segment_id: int
    offset: int
    size: int
    timestamp: int

class Segment:
    """Represents a log segment file."""

    def __init__(self, segment_id: int, directory: str, max_size: int = 64 * 1024 * 1024):
        self.segment_id = segment_id
        self.directory = directory
        self.max_size = max_size
        self.filename = os.path.join(directory, f"segment_{segment_id:08d}.log")
        self.file = None
        self.current_offset = 0
        self.entry_count = 0

    def open(self, mode: str = 'a+b'):
        """Open the segment file."""
        self.file = open(self.filename, mode)
        self.file.seek(0, 2)  # Seek to end
        self.current_offset = self.file.tell()

    def close(self):
        """Close the segment file."""
        if self.file:
            self.file.close()
            self.file = None

    def append(self, entry_type: str, key: str, value: bytes) -> LogEntry:
        """Append an entry to the log."""
        timestamp = int(time.time() * 1000)
        key_bytes = key.encode('utf-8')
        type_byte = 0 if entry_type == "PUT" else 1

        # Format: [type:1][timestamp:8][key_len:4][value_len:4][key][value][checksum:4]
        header = struct.pack('>BQii', type_byte, timestamp, len(key_bytes), len(value))
        data = header + key_bytes + value

        checksum = self._compute_checksum(data)
        full_entry = data + struct.pack('>I', checksum)

        offset = self.current_offset
        self.file.write(full_entry)
        self.file.flush()
        os.fsync(self.file.fileno())

        self.current_offset += len(full_entry)
        self.entry_count += 1

        return LogEntry(
            offset=offset,
            timestamp=timestamp,
            entry_type=entry_type,
            key=key,
            value=value,
            checksum=checksum
        )

    def read_at(self, offset: int) -> Optional[LogEntry]:
        """Read an entry at a specific offset."""
        self.file.seek(offset)

        header = self.file.read(17)  # 1 + 8 + 4 + 4
        if len(header) < 17:
            return None

        type_byte, timestamp, key_len, value_len = struct.unpack('>BQii', header)
        entry_type = "PUT" if type_byte == 0 else "DELETE"

        key_bytes = self.file.read(key_len)
        value = self.file.read(value_len)
        checksum_bytes = self.file.read(4)

        checksum = struct.unpack('>I', checksum_bytes)[0]

        # Verify checksum
        data = header + key_bytes + value
        if checksum != self._compute_checksum(data):
            raise ValueError("Checksum mismatch")

        return LogEntry(
            offset=offset,
            timestamp=timestamp,
            entry_type=entry_type,
            key=key_bytes.decode('utf-8'),
            value=value,
            checksum=checksum
        )

    def _compute_checksum(self, data: bytes) -> int:
        """Compute CRC32 checksum."""
        import zlib
        return zlib.crc32(data) & 0xffffffff

    def is_full(self) -> bool:
        """Check if segment is full."""
        return self.current_offset >= self.max_size


class LogStructuredKVStore:
    """Key-value store with append-only log storage."""

    def __init__(self, directory: str):
        self.directory = directory
        self.keydir: Dict[str, KeyDirEntry] = {}  # In-memory index
        self.segments: Dict[int, Segment] = {}
        self.active_segment: Optional[Segment] = None
        self.next_segment_id = 0
        self.lock = asyncio.Lock()

        os.makedirs(directory, exist_ok=True)

    async def open(self):
        """Open the store and rebuild keydir from existing segments."""
        # Find existing segments
        for filename in sorted(os.listdir(self.directory)):
            if filename.startswith("segment_") and filename.endswith(".log"):
                segment_id = int(filename[8:16])
                segment = Segment(segment_id, self.directory)
                segment.open('r+b')
                self.segments[segment_id] = segment
                self.next_segment_id = max(self.next_segment_id, segment_id + 1)

                # Rebuild keydir from segment
                await self._rebuild_keydir_from_segment(segment)

        # Create active segment
        self._create_new_segment()

    async def _rebuild_keydir_from_segment(self, segment: Segment):
        """Rebuild keydir by reading all entries from a segment."""
        segment.file.seek(0)
        offset = 0

        while True:
            try:
                entry = segment.read_at(offset)
                if not entry:
                    break

                if entry.entry_type == "PUT":
                    entry_size = 17 + len(entry.key.encode()) + len(entry.value) + 4
                    self.keydir[entry.key] = KeyDirEntry(
                        segment_id=segment.segment_id,
                        offset=offset,
                        size=entry_size,
                        timestamp=entry.timestamp
                    )
                elif entry.entry_type == "DELETE":
                    if entry.key in self.keydir:
                        del self.keydir[entry.key]

                offset = segment.file.tell()
            except:
                break

    def _create_new_segment(self):
        """Create a new active segment."""
        segment = Segment(self.next_segment_id, self.directory)
        segment.open()
        self.segments[self.next_segment_id] = segment
        self.active_segment = segment
        self.next_segment_id += 1

    async def put(self, key: str, value: bytes) -> bool:
        """Store a key-value pair."""
        async with self.lock:
            if self.active_segment.is_full():
                self._create_new_segment()

            entry = self.active_segment.append("PUT", key, value)

            self.keydir[key] = KeyDirEntry(
                segment_id=self.active_segment.segment_id,
                offset=entry.offset,
                size=17 + len(key.encode()) + len(value) + 4,
                timestamp=entry.timestamp
            )

            return True

    async def get(self, key: str) -> Optional[bytes]:
        """Retrieve a value by key."""
        keydir_entry = self.keydir.get(key)
        if not keydir_entry:
            return None

        segment = self.segments.get(keydir_entry.segment_id)
        if not segment:
            return None

        entry = segment.read_at(keydir_entry.offset)
        return entry.value if entry else None

    async def delete(self, key: str) -> bool:
        """Delete a key (write tombstone)."""
        async with self.lock:
            if key not in self.keydir:
                return False

            if self.active_segment.is_full():
                self._create_new_segment()

            self.active_segment.append("DELETE", key, b"")

            del self.keydir[key]
            return True

    async def compact(self) -> int:
        """Compact old segments to reclaim space."""
        async with self.lock:
            # Skip active segment
            old_segments = [
                s for s in self.segments.values()
                if s.segment_id != self.active_segment.segment_id
            ]

            if not old_segments:
                return 0

            # Create new compacted segment
            compacted = Segment(self.next_segment_id, self.directory)
            compacted.open()

            entries_removed = 0
            new_keydir = {}

            # Copy only live entries
            for key, keydir_entry in self.keydir.items():
                if keydir_entry.segment_id == self.active_segment.segment_id:
                    new_keydir[key] = keydir_entry
                    continue

                segment = self.segments[keydir_entry.segment_id]
                entry = segment.read_at(keydir_entry.offset)

                if entry:
                    new_entry = compacted.append("PUT", key, entry.value)
                    new_keydir[key] = KeyDirEntry(
                        segment_id=compacted.segment_id,
                        offset=new_entry.offset,
                        size=17 + len(key.encode()) + len(entry.value) + 4,
                        timestamp=new_entry.timestamp
                    )

            # Update keydir
            self.keydir = new_keydir

            # Remove old segments
            for segment in old_segments:
                segment.close()
                os.remove(segment.filename)
                del self.segments[segment.segment_id]
                entries_removed += segment.entry_count

            self.segments[compacted.segment_id] = compacted
            self.next_segment_id += 1

            return entries_removed
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** with Raft replication
- Leader handles writes, followers replicate log
- Compaction runs independently on each node
- Tolerates 2 node failures (Raft quorum: 3/5)

### gRPC Services

```protobuf
service KVService {
    rpc Get(GetRequest) returns (GetResponse);
    rpc Put(PutRequest) returns (PutResponse);
    rpc Delete(DeleteRequest) returns (DeleteResponse);
    rpc Scan(ScanRequest) returns (ScanResponse);
}

service StorageService {
    rpc TriggerCompaction(TriggerCompactionRequest) returns (TriggerCompactionResponse);
    rpc GetCompactionStatus(GetCompactionStatusRequest) returns (GetCompactionStatusResponse);
    rpc GetStorageStats(GetStorageStatsRequest) returns (GetStorageStatsResponse);
}
```

---

## Realistic Testing

```python
class TestLogStructuredKV:
    async def test_basic_operations(self, cluster):
        """Basic put/get/delete operations."""
        leader = await find_leader(cluster)

        await leader.Put(key="test", value=b"hello")
        response = await leader.Get(key="test")

        assert response.found
        assert response.value == b"hello"

        await leader.Delete(key="test")
        response = await leader.Get(key="test")
        assert not response.found

    async def test_compaction_reclaims_space(self, cluster):
        """Compaction removes obsolete entries."""
        leader = await find_leader(cluster)

        # Write same key multiple times
        for i in range(1000):
            await leader.Put(key="key", value=f"value_{i}".encode())

        stats_before = await leader.GetStorageStats()

        await leader.TriggerCompaction()
        await asyncio.sleep(2)

        stats_after = await leader.GetStorageStats()

        # Space should be reduced (only latest value kept)
        assert stats_after.total_storage_bytes < stats_before.total_storage_bytes

    async def test_crash_recovery(self, cluster):
        """Data survives crash and restart."""
        leader = await find_leader(cluster)

        for i in range(100):
            await leader.Put(key=f"key_{i}", value=f"value_{i}".encode())

        # Restart cluster
        await platform_api.restart_cluster(cluster)
        await asyncio.sleep(5)

        leader = await find_leader(cluster)

        for i in range(100):
            response = await leader.Get(key=f"key_{i}")
            assert response.found
            assert response.value == f"value_{i}".encode()
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Operations | Put/Get/Delete work correctly |
| Compaction | Reduces storage size |
| Crash Recovery | Data persisted across restarts |
| Replication | Consistent across nodes |
