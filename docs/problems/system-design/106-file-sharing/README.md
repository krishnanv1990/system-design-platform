# File Sharing Service Design (Dropbox-like)

## Problem Overview

Design a cloud file storage and synchronization service like Dropbox that supports 500 million users with automatic sync across devices.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 Client Layer                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  Desktop App    │  │   Mobile App    │  │   Web Client    │                 │
│  │  (Sync Daemon)  │  │                 │  │                 │                 │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                 │
└───────────┼────────────────────┼────────────────────┼───────────────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API Gateway                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Authentication  │  Rate Limiting  │  Routing  │  SSL Termination       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│ Metadata      │          │ Block         │          │ Sync          │
│ Service       │          │ Service       │          │ Service       │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│ Metadata DB   │          │ Block Store   │          │ Message Queue │
│ (PostgreSQL)  │          │ (GCS/S3)      │          │ (Pub/Sub)     │
└───────────────┘          └───────────────┘          └───────────────┘
```

### Core Components

#### 1. Block-Level Storage

```python
import hashlib
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Block:
    hash: str  # SHA-256 of content
    size: int
    data: bytes

class BlockService:
    """
    Stores files as blocks for deduplication and efficient sync.
    Block size: 4MB (configurable)
    """
    BLOCK_SIZE = 4 * 1024 * 1024  # 4MB

    def __init__(self, storage_client):
        self.storage = storage_client

    def split_file(self, file_data: bytes) -> List[Block]:
        """Split file into blocks using content-defined chunking."""
        blocks = []
        for i in range(0, len(file_data), self.BLOCK_SIZE):
            chunk = file_data[i:i + self.BLOCK_SIZE]
            block_hash = hashlib.sha256(chunk).hexdigest()
            blocks.append(Block(hash=block_hash, size=len(chunk), data=chunk))
        return blocks

    async def upload_blocks(self, blocks: List[Block]) -> List[str]:
        """Upload blocks with deduplication."""
        uploaded = []
        for block in blocks:
            # Check if block already exists
            if not await self.storage.exists(block.hash):
                await self.storage.put(block.hash, block.data)
            uploaded.append(block.hash)
        return uploaded

    async def download_blocks(self, block_hashes: List[str]) -> bytes:
        """Download and reassemble blocks."""
        data = b""
        for hash in block_hashes:
            block_data = await self.storage.get(hash)
            data += block_data
        return data
```

#### 2. Metadata Service

```python
from datetime import datetime
from enum import Enum

class FileType(Enum):
    FILE = "file"
    FOLDER = "folder"

@dataclass
class FileMetadata:
    id: str
    user_id: str
    parent_id: Optional[str]
    name: str
    file_type: FileType
    size: int
    block_hashes: List[str]
    version: int
    checksum: str
    created_at: datetime
    modified_at: datetime
    is_deleted: bool = False

class MetadataService:
    async def create_file(
        self,
        user_id: str,
        parent_id: str,
        name: str,
        blocks: List[str],
        size: int,
        checksum: str
    ) -> FileMetadata:
        """Create file metadata entry."""
        file_id = str(uuid.uuid4())
        metadata = FileMetadata(
            id=file_id,
            user_id=user_id,
            parent_id=parent_id,
            name=name,
            file_type=FileType.FILE,
            size=size,
            block_hashes=blocks,
            version=1,
            checksum=checksum,
            created_at=datetime.utcnow(),
            modified_at=datetime.utcnow()
        )

        await self.db.insert("files", metadata)
        await self.notify_sync(user_id, "file_created", metadata)
        return metadata

    async def update_file(
        self,
        file_id: str,
        blocks: List[str],
        size: int,
        checksum: str,
        expected_version: int
    ) -> FileMetadata:
        """Update file with optimistic locking."""
        async with self.db.transaction():
            current = await self.db.get("files", file_id)

            if current.version != expected_version:
                raise ConflictError("Version mismatch")

            current.block_hashes = blocks
            current.size = size
            current.checksum = checksum
            current.version += 1
            current.modified_at = datetime.utcnow()

            await self.db.update("files", current)
            await self.create_version_history(current)
            await self.notify_sync(current.user_id, "file_updated", current)

            return current

    async def get_changes(
        self,
        user_id: str,
        cursor: str
    ) -> Tuple[List[FileMetadata], str]:
        """
        Get changes since cursor for sync.
        Returns (changes, new_cursor).
        """
        changes = await self.db.query("""
            SELECT * FROM files
            WHERE user_id = $1
            AND modified_at > $2
            ORDER BY modified_at
            LIMIT 1000
        """, user_id, cursor)

        new_cursor = changes[-1].modified_at if changes else cursor
        return changes, new_cursor
```

#### 3. Sync Service

```python
class SyncService:
    """
    Handles real-time synchronization across devices.
    Uses long-polling or WebSockets for notifications.
    """

    async def sync_changes(
        self,
        user_id: str,
        device_id: str,
        local_state: Dict[str, int]  # file_id -> version
    ) -> SyncResponse:
        """
        Compare local state with server and return required changes.
        """
        # Get server state
        server_files = await self.metadata.get_user_files(user_id)

        to_download = []
        to_upload = []
        conflicts = []

        for file in server_files:
            local_version = local_state.get(file.id, 0)

            if file.is_deleted and file.id in local_state:
                to_download.append({"file_id": file.id, "action": "delete"})
            elif local_version < file.version:
                to_download.append({
                    "file_id": file.id,
                    "action": "download",
                    "blocks": file.block_hashes
                })
            elif local_version > file.version:
                # Local has newer version (shouldn't happen normally)
                conflicts.append(file.id)

        # Check for local files not on server
        server_ids = {f.id for f in server_files}
        for file_id in local_state:
            if file_id not in server_ids:
                to_upload.append({"file_id": file_id, "action": "upload"})

        return SyncResponse(
            to_download=to_download,
            to_upload=to_upload,
            conflicts=conflicts
        )

    async def resolve_conflict(
        self,
        file_id: str,
        resolution: str,  # "keep_local", "keep_server", "keep_both"
        local_blocks: Optional[List[str]] = None
    ) -> FileMetadata:
        """Resolve sync conflict."""
        if resolution == "keep_local":
            # Upload local version
            return await self.metadata.update_file(
                file_id, local_blocks, force=True
            )
        elif resolution == "keep_server":
            # Tell client to download server version
            return await self.metadata.get_file(file_id)
        else:
            # Keep both - rename local file
            server_file = await self.metadata.get_file(file_id)
            new_name = f"{server_file.name} (conflict copy)"
            return await self.metadata.create_file(
                user_id=server_file.user_id,
                parent_id=server_file.parent_id,
                name=new_name,
                blocks=local_blocks
            )
```

#### 4. Sharing Service

```python
class Permission(Enum):
    VIEW = "view"
    EDIT = "edit"
    OWNER = "owner"

@dataclass
class Share:
    id: str
    file_id: str
    shared_with: str  # user_id or email
    permission: Permission
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime]

class SharingService:
    async def share_file(
        self,
        file_id: str,
        owner_id: str,
        share_with: str,
        permission: Permission
    ) -> Share:
        """Share file with another user."""
        # Verify ownership
        file = await self.metadata.get_file(file_id)
        if file.user_id != owner_id:
            raise PermissionError("Not the owner")

        share = Share(
            id=str(uuid.uuid4()),
            file_id=file_id,
            shared_with=share_with,
            permission=permission,
            created_by=owner_id,
            created_at=datetime.utcnow(),
            expires_at=None
        )

        await self.db.insert("shares", share)
        await self.notify_user(share_with, "file_shared", file)
        return share

    async def create_link(
        self,
        file_id: str,
        owner_id: str,
        expires_in: Optional[int] = None
    ) -> str:
        """Create shareable link."""
        token = secrets.token_urlsafe(32)
        link = ShareLink(
            token=token,
            file_id=file_id,
            created_by=owner_id,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in)
                if expires_in else None
        )

        await self.db.insert("share_links", link)
        return f"https://files.example.com/s/{token}"
```

### Database Schema

```sql
-- Users
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    storage_used BIGINT DEFAULT 0,
    storage_limit BIGINT DEFAULT 2147483648,  -- 2GB
    created_at TIMESTAMP DEFAULT NOW()
);

-- Files and folders metadata
CREATE TABLE files (
    id UUID PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    parent_id UUID REFERENCES files(id),
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    size BIGINT DEFAULT 0,
    block_hashes TEXT[],
    checksum VARCHAR(64),
    version INTEGER DEFAULT 1,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, parent_id, name)
);

CREATE INDEX idx_files_user_modified ON files(user_id, modified_at);
CREATE INDEX idx_files_parent ON files(parent_id);

-- Version history
CREATE TABLE file_versions (
    id BIGSERIAL PRIMARY KEY,
    file_id UUID REFERENCES files(id),
    version INTEGER NOT NULL,
    size BIGINT,
    block_hashes TEXT[],
    checksum VARCHAR(64),
    modified_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Shares
CREATE TABLE shares (
    id UUID PRIMARY KEY,
    file_id UUID REFERENCES files(id),
    shared_with VARCHAR(255) NOT NULL,
    permission VARCHAR(20) NOT NULL,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Block references (for garbage collection)
CREATE TABLE block_refs (
    block_hash VARCHAR(64) PRIMARY KEY,
    ref_count INTEGER DEFAULT 1,
    size BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Platform Deployment

### Infrastructure Components

1. **Metadata Service:** Cloud Run (auto-scaling)
2. **Block Storage:** Cloud Storage (multi-region)
3. **Metadata DB:** Cloud SQL PostgreSQL (HA)
4. **Sync Notifications:** Pub/Sub + WebSocket gateway
5. **CDN:** Cloud CDN for downloads

---

## Realistic Testing

### 1. Functional Tests

```python
class TestFileSharing:
    async def test_upload_download(self, client):
        """Test file upload and download."""
        content = b"Hello, World!" * 1000
        checksum = hashlib.sha256(content).hexdigest()

        # Upload
        upload_resp = await client.post("/api/v1/files", files={
            "file": ("test.txt", content)
        })
        file_id = upload_resp.json()["id"]

        # Download
        download_resp = await client.get(f"/api/v1/files/{file_id}/content")
        assert download_resp.content == content
        assert hashlib.sha256(download_resp.content).hexdigest() == checksum

    async def test_deduplication(self, client):
        """Test block-level deduplication."""
        content = b"Duplicate content" * 10000

        # Upload twice
        r1 = await client.post("/api/v1/files", files={
            "file": ("file1.txt", content)
        })
        r2 = await client.post("/api/v1/files", files={
            "file": ("file2.txt", content)
        })

        # Storage should only increase once
        stats = await client.get("/api/v1/storage/stats")
        # Block storage should show deduplication
        assert stats.json()["unique_blocks_size"] < len(content) * 2

    async def test_sync_across_devices(self, client):
        """Test file sync between devices."""
        # Upload from device 1
        content = b"Sync test content"
        await client.post("/api/v1/files",
            files={"file": ("sync.txt", content)},
            headers={"X-Device-ID": "device1"}
        )

        # Sync from device 2
        changes = await client.get("/api/v1/sync?cursor=0",
            headers={"X-Device-ID": "device2"}
        )

        assert len(changes.json()["to_download"]) == 1
        assert changes.json()["to_download"][0]["name"] == "sync.txt"

    async def test_conflict_resolution(self, client):
        """Test conflict detection and resolution."""
        # Create file
        r = await client.post("/api/v1/files", files={
            "file": ("conflict.txt", b"original")
        })
        file_id = r.json()["id"]
        version = r.json()["version"]

        # Simulate concurrent updates
        await client.put(f"/api/v1/files/{file_id}",
            files={"file": ("conflict.txt", b"update1")},
            params={"expected_version": version}
        )

        # This should fail with conflict
        r2 = await client.put(f"/api/v1/files/{file_id}",
            files={"file": ("conflict.txt", b"update2")},
            params={"expected_version": version}
        )
        assert r2.status_code == 409

    async def test_version_history(self, client):
        """Test file version history."""
        r = await client.post("/api/v1/files", files={
            "file": ("versions.txt", b"v1")
        })
        file_id = r.json()["id"]

        # Update multiple times
        for i in range(2, 6):
            await client.put(f"/api/v1/files/{file_id}",
                files={"file": ("versions.txt", f"v{i}".encode())}
            )

        # Check versions
        versions = await client.get(f"/api/v1/files/{file_id}/versions")
        assert len(versions.json()) == 5

        # Restore old version
        await client.post(f"/api/v1/files/{file_id}/restore",
            json={"version": 2}
        )
        content = await client.get(f"/api/v1/files/{file_id}/content")
        assert content.content == b"v2"
```

### 2. Large File Tests

```python
class TestLargeFiles:
    async def test_chunked_upload(self, client):
        """Test large file upload with chunking."""
        # 100MB file
        large_content = os.urandom(100 * 1024 * 1024)

        # Initiate chunked upload
        init = await client.post("/api/v1/uploads", json={
            "filename": "large.bin",
            "size": len(large_content),
            "checksum": hashlib.sha256(large_content).hexdigest()
        })
        upload_id = init.json()["upload_id"]

        # Upload chunks
        chunk_size = 5 * 1024 * 1024  # 5MB chunks
        for i in range(0, len(large_content), chunk_size):
            chunk = large_content[i:i + chunk_size]
            await client.put(
                f"/api/v1/uploads/{upload_id}/chunks/{i // chunk_size}",
                content=chunk
            )

        # Complete upload
        complete = await client.post(f"/api/v1/uploads/{upload_id}/complete")
        assert complete.status_code == 200

        # Verify download
        file_id = complete.json()["file_id"]
        downloaded = await client.get(f"/api/v1/files/{file_id}/content")
        assert downloaded.content == large_content

    async def test_resumable_upload(self, client):
        """Test upload resume after interruption."""
        content = os.urandom(50 * 1024 * 1024)

        init = await client.post("/api/v1/uploads", json={
            "filename": "resume.bin",
            "size": len(content)
        })
        upload_id = init.json()["upload_id"]

        # Upload first half
        await client.put(
            f"/api/v1/uploads/{upload_id}/chunks/0",
            content=content[:25*1024*1024]
        )

        # Simulate interruption - check progress
        status = await client.get(f"/api/v1/uploads/{upload_id}")
        assert status.json()["uploaded_bytes"] == 25*1024*1024

        # Resume from where we left off
        await client.put(
            f"/api/v1/uploads/{upload_id}/chunks/1",
            content=content[25*1024*1024:]
        )

        complete = await client.post(f"/api/v1/uploads/{upload_id}/complete")
        assert complete.status_code == 200
```

### 3. Chaos Tests

```python
class FileStorageChaosTests:
    async def test_storage_node_failure(self):
        """Test file availability during storage failure."""
        # Upload file
        content = b"Critical data"
        r = await client.post("/api/v1/files", files={
            "file": ("critical.txt", content)
        })
        file_id = r.json()["id"]

        # Simulate storage node failure
        await platform_api.fail_storage_region("us-central1")

        # File should still be accessible (multi-region)
        download = await client.get(f"/api/v1/files/{file_id}/content")
        assert download.status_code == 200
        assert download.content == content

    async def test_metadata_db_failover(self):
        """Test behavior during database failover."""
        # Trigger failover
        await platform_api.trigger_sql_failover()

        # Should recover within acceptable time
        start = time.time()
        while time.time() - start < 60:
            try:
                r = await client.get("/api/v1/files")
                if r.status_code == 200:
                    break
            except:
                pass
            await asyncio.sleep(1)

        # Should be back within 60 seconds
        r = await client.get("/api/v1/files")
        assert r.status_code == 200
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Upload Throughput | > 100 MB/s |
| Download Throughput | > 200 MB/s |
| Sync Latency | < 5 seconds |
| Deduplication Ratio | > 50% |
| Availability | 99.99% |
