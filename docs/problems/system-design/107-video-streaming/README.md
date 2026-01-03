# Video Streaming Service Design (YouTube-like)

## Problem Overview

Design a video sharing and streaming platform supporting 2 billion monthly users, 500 hours of uploads per minute, and 100 million concurrent viewers.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Upload Pipeline                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Upload  │───▶│   Storage    │───▶│  Transcode   │───▶│   CDN        │          │
│  │  Service │    │   (Raw)      │    │   Workers    │    │   Origin     │          │
│  └──────────┘    └──────────────┘    └──────────────┘    └──────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Streaming Pipeline                                      │
│                                                                                      │
│  ┌──────────┐    ┌──────────────────────────────────────────────────┐              │
│  │  Client  │───▶│                    CDN                           │              │
│  │  Player  │    │  ┌─────────┐  ┌─────────┐  ┌─────────┐          │              │
│  └──────────┘    │  │  Edge   │  │  Edge   │  │  Edge   │          │              │
│       │          │  │  PoP 1  │  │  PoP 2  │  │  PoP N  │          │              │
│       │          │  └────┬────┘  └────┬────┘  └────┬────┘          │              │
│       │          └───────┼───────────┼───────────┼──────────────────┘              │
│       │                  │           │           │                                  │
│       │          ┌───────▼───────────▼───────────▼───────┐                         │
│       └─────────▶│              Origin Servers            │                         │
│                  └────────────────────┬──────────────────┘                         │
│                                       │                                             │
│                  ┌────────────────────▼──────────────────┐                         │
│                  │           Video Storage                │                         │
│                  │   (HLS/DASH segments, multiple res)    │                         │
│                  └────────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Video Upload and Processing

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

class VideoResolution(Enum):
    R_144P = (256, 144, 200)    # width, height, bitrate_kbps
    R_240P = (426, 240, 400)
    R_360P = (640, 360, 800)
    R_480P = (854, 480, 1200)
    R_720P = (1280, 720, 2500)
    R_1080P = (1920, 1080, 5000)
    R_1440P = (2560, 1440, 9000)
    R_4K = (3840, 2160, 18000)

@dataclass
class VideoMetadata:
    id: str
    user_id: str
    title: str
    description: str
    duration_seconds: int
    resolutions: List[VideoResolution]
    status: str  # processing, ready, failed
    thumbnail_url: str
    created_at: datetime

class VideoUploadService:
    async def upload(
        self,
        user_id: str,
        file: UploadFile,
        metadata: Dict
    ) -> str:
        """Handle video upload and trigger processing."""
        video_id = str(uuid.uuid4())

        # Store raw video
        raw_path = f"raw/{video_id}/{file.filename}"
        await self.storage.upload(raw_path, file)

        # Create metadata record
        video = VideoMetadata(
            id=video_id,
            user_id=user_id,
            title=metadata.get("title", "Untitled"),
            description=metadata.get("description", ""),
            duration_seconds=0,
            resolutions=[],
            status="processing",
            thumbnail_url="",
            created_at=datetime.utcnow()
        )
        await self.db.insert("videos", video)

        # Trigger transcoding pipeline
        await self.queue.publish("transcode", {
            "video_id": video_id,
            "raw_path": raw_path,
            "user_id": user_id
        })

        return video_id


class TranscodingService:
    """Transcodes videos to multiple resolutions using FFmpeg."""

    def __init__(self, storage, db):
        self.storage = storage
        self.db = db

    async def transcode(self, video_id: str, raw_path: str):
        """Transcode video to all target resolutions."""
        # Download raw video
        local_path = f"/tmp/{video_id}_raw"
        await self.storage.download(raw_path, local_path)

        # Probe video for info
        info = await self.probe_video(local_path)
        source_height = info["height"]

        # Determine target resolutions (up to source quality)
        targets = [r for r in VideoResolution if r.value[1] <= source_height]

        # Generate HLS segments for each resolution
        output_dir = f"/tmp/{video_id}_output"
        os.makedirs(output_dir, exist_ok=True)

        for resolution in targets:
            await self._transcode_resolution(
                local_path, output_dir, resolution
            )

        # Generate master playlist
        master_playlist = self._create_master_playlist(targets)
        await self.storage.upload(
            f"videos/{video_id}/master.m3u8",
            master_playlist
        )

        # Upload all segments
        for file in os.listdir(output_dir):
            await self.storage.upload(
                f"videos/{video_id}/{file}",
                open(f"{output_dir}/{file}", "rb")
            )

        # Update metadata
        await self.db.update("videos", video_id, {
            "status": "ready",
            "resolutions": [r.name for r in targets],
            "duration_seconds": info["duration"]
        })

    async def _transcode_resolution(
        self,
        input_path: str,
        output_dir: str,
        resolution: VideoResolution
    ):
        """Transcode to specific resolution using FFmpeg."""
        width, height, bitrate = resolution.value
        output_name = f"{resolution.name}"

        cmd = [
            "ffmpeg", "-i", input_path,
            "-vf", f"scale={width}:{height}",
            "-c:v", "libx264", "-preset", "fast",
            "-b:v", f"{bitrate}k",
            "-c:a", "aac", "-b:a", "128k",
            "-hls_time", "6",  # 6 second segments
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{output_dir}/{output_name}_%03d.ts",
            f"{output_dir}/{output_name}.m3u8"
        ]

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()

    def _create_master_playlist(self, resolutions: List[VideoResolution]) -> str:
        """Create HLS master playlist with all qualities."""
        lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

        for res in sorted(resolutions, key=lambda r: r.value[2], reverse=True):
            width, height, bitrate = res.value
            lines.append(
                f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate*1000},"
                f"RESOLUTION={width}x{height}"
            )
            lines.append(f"{res.name}.m3u8")

        return "\n".join(lines)
```

#### 2. Adaptive Bitrate Streaming

```python
class StreamingService:
    """Handles video streaming with adaptive bitrate."""

    async def get_manifest(self, video_id: str) -> str:
        """Get HLS master playlist for video."""
        video = await self.db.get("videos", video_id)

        if video.status != "ready":
            raise VideoNotReadyError()

        # Increment view count asynchronously
        asyncio.create_task(self.increment_views(video_id))

        # Return CDN URL for manifest
        return f"{CDN_URL}/videos/{video_id}/master.m3u8"

    async def get_segment(
        self,
        video_id: str,
        resolution: str,
        segment_number: int
    ) -> str:
        """Get URL for specific video segment."""
        # Validate segment exists
        segment_path = f"videos/{video_id}/{resolution}_{segment_number:03d}.ts"

        if not await self.storage.exists(segment_path):
            raise SegmentNotFoundError()

        # Return signed CDN URL
        return await self.cdn.get_signed_url(
            segment_path,
            expires_in=3600
        )

    async def track_playback(
        self,
        video_id: str,
        user_id: str,
        position_seconds: int,
        quality: str
    ):
        """Track playback progress and quality switches."""
        await self.analytics.log("playback", {
            "video_id": video_id,
            "user_id": user_id,
            "position": position_seconds,
            "quality": quality,
            "timestamp": datetime.utcnow().isoformat()
        })
```

#### 3. Recommendation Engine

```python
class RecommendationService:
    """Video recommendation using collaborative filtering."""

    async def get_recommendations(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[VideoMetadata]:
        """Get personalized video recommendations."""
        # Get user's watch history
        history = await self.get_watch_history(user_id)

        # Find similar users (collaborative filtering)
        similar_users = await self.find_similar_users(user_id, history)

        # Get videos watched by similar users but not by current user
        candidates = await self.get_candidate_videos(
            user_id, similar_users
        )

        # Score and rank
        scored = []
        for video in candidates:
            score = await self.calculate_score(video, user_id, history)
            scored.append((video, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [v for v, s in scored[:limit]]

    async def calculate_score(
        self,
        video: VideoMetadata,
        user_id: str,
        history: List[str]
    ) -> float:
        """Calculate recommendation score for a video."""
        score = 0.0

        # Engagement metrics
        stats = await self.get_video_stats(video.id)
        score += stats.view_count * 0.001
        score += stats.like_ratio * 10

        # Freshness (newer videos get boost)
        age_days = (datetime.utcnow() - video.created_at).days
        score *= max(0.5, 1.0 - age_days / 365)

        # Category similarity to watch history
        similarity = await self.calculate_category_similarity(
            video, history
        )
        score *= (1 + similarity)

        return score
```

### Database Schema

```sql
-- Videos
CREATE TABLE videos (
    id UUID PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_seconds INTEGER,
    status VARCHAR(50) DEFAULT 'processing',
    resolutions TEXT[],
    thumbnail_url TEXT,
    view_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    dislike_count BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP
);

CREATE INDEX idx_videos_user ON videos(user_id);
CREATE INDEX idx_videos_created ON videos(created_at DESC);

-- Video segments (for analytics)
CREATE TABLE video_segments (
    video_id UUID REFERENCES videos(id),
    resolution VARCHAR(20),
    segment_number INTEGER,
    duration_ms INTEGER,
    size_bytes BIGINT,
    PRIMARY KEY (video_id, resolution, segment_number)
);

-- Watch history
CREATE TABLE watch_history (
    id BIGSERIAL,
    user_id BIGINT REFERENCES users(id),
    video_id UUID REFERENCES videos(id),
    watched_seconds INTEGER,
    completed BOOLEAN DEFAULT FALSE,
    watched_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, video_id, watched_at)
) PARTITION BY RANGE (watched_at);

-- Video engagement
CREATE TABLE video_likes (
    user_id BIGINT REFERENCES users(id),
    video_id UUID REFERENCES videos(id),
    is_like BOOLEAN,  -- true = like, false = dislike
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, video_id)
);

-- Comments
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,
    video_id UUID REFERENCES videos(id),
    user_id BIGINT REFERENCES users(id),
    parent_id BIGINT REFERENCES comments(id),
    content TEXT NOT NULL,
    like_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Platform Deployment

### Infrastructure

1. **Upload Service:** Cloud Run with large timeout
2. **Transcoding:** GKE with GPU nodes for FFmpeg
3. **Video Storage:** Cloud Storage (multi-region)
4. **CDN:** Cloud CDN with custom origin
5. **Streaming API:** Cloud Run with caching

---

## Realistic Testing

### 1. Upload and Transcoding Tests

```python
class TestVideoUpload:
    async def test_upload_and_transcode(self, client):
        """Test full upload-to-playback pipeline."""
        # Upload video
        with open("test_video.mp4", "rb") as f:
            response = await client.post("/api/v1/videos", files={
                "file": f
            }, data={"title": "Test Video"})

        video_id = response.json()["id"]
        assert response.json()["status"] == "processing"

        # Wait for transcoding (poll status)
        for _ in range(60):  # 5 minute timeout
            status = await client.get(f"/api/v1/videos/{video_id}")
            if status.json()["status"] == "ready":
                break
            await asyncio.sleep(5)

        assert status.json()["status"] == "ready"
        assert len(status.json()["resolutions"]) > 0

    async def test_large_video_upload(self, client):
        """Test chunked upload for large videos."""
        # 1GB video
        video_size = 1024 * 1024 * 1024

        # Initiate upload
        init = await client.post("/api/v1/videos/upload/init", json={
            "filename": "large_video.mp4",
            "size": video_size,
            "title": "Large Video"
        })
        upload_id = init.json()["upload_id"]

        # Upload in 10MB chunks
        chunk_size = 10 * 1024 * 1024
        with open("large_test.mp4", "rb") as f:
            chunk_num = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                await client.put(
                    f"/api/v1/videos/upload/{upload_id}/chunks/{chunk_num}",
                    content=chunk
                )
                chunk_num += 1

        # Complete upload
        complete = await client.post(f"/api/v1/videos/upload/{upload_id}/complete")
        assert complete.status_code == 200
```

### 2. Streaming Tests

```python
class TestVideoStreaming:
    async def test_adaptive_streaming(self, client):
        """Test HLS streaming with quality switching."""
        video_id = await create_test_video()

        # Get manifest
        manifest = await client.get(f"/api/v1/videos/{video_id}/manifest")
        assert "#EXTM3U" in manifest.text

        # Parse available qualities
        qualities = re.findall(r'RESOLUTION=(\d+x\d+)', manifest.text)
        assert len(qualities) > 1

        # Fetch segments at different qualities
        for quality in ["R_480P", "R_720P"]:
            segment = await client.get(
                f"/api/v1/videos/{video_id}/segments/{quality}/0"
            )
            assert segment.status_code == 200
            assert segment.headers["content-type"] == "video/MP2T"

    async def test_cdn_caching(self, client):
        """Test CDN cache performance."""
        video_id = await create_test_video()

        # First request - cache miss
        start = time.time()
        r1 = await client.get(f"/cdn/videos/{video_id}/R_720P_000.ts")
        first_latency = time.time() - start

        # Second request - cache hit
        start = time.time()
        r2 = await client.get(f"/cdn/videos/{video_id}/R_720P_000.ts")
        cached_latency = time.time() - start

        # Cache hit should be faster
        assert cached_latency < first_latency * 0.5
        assert r2.headers.get("x-cache") == "HIT"
```

### 3. Load Testing

```python
from locust import HttpUser, task

class VideoStreamingUser(HttpUser):
    @task(10)
    def watch_video(self):
        """Simulate watching a video."""
        video_id = random.choice(VIDEO_IDS)

        # Get manifest
        self.client.get(f"/api/v1/videos/{video_id}/manifest")

        # Fetch 10 segments (1 minute of video)
        for i in range(10):
            self.client.get(
                f"/cdn/videos/{video_id}/R_720P_{i:03d}.ts",
                name="/cdn/[segment]"
            )
            time.sleep(6)  # Segment duration

    @task(1)
    def upload_video(self):
        """Simulate video upload."""
        with open("test_video.mp4", "rb") as f:
            self.client.post("/api/v1/videos", files={"file": f})
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Stream Start Time | < 2 seconds |
| Buffering Rate | < 1% of playback |
| Transcode Time | < 2x video duration |
| CDN Cache Hit | > 95% |
| Concurrent Viewers | > 100K per video |
