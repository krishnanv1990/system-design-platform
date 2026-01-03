# Leaky Bucket Rate Limiter

## Problem Overview

Implement a distributed leaky bucket rate limiter that provides smooth, constant output rate regardless of input burstiness.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

The leaky bucket algorithm works by:
1. Requests enter a queue (bucket) with fixed capacity
2. Requests are processed (leak) at a constant rate
3. If the bucket is full, new requests are rejected
4. Provides smooth, consistent output rate

### Implementation

```python
import time
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, List
from collections import deque

@dataclass
class BucketConfig:
    bucket_id: str
    capacity: int           # Maximum queue size
    leak_rate: float        # Requests processed per second

@dataclass
class QueuedRequest:
    request_id: str
    enqueue_time: int       # milliseconds
    estimated_process_time: int

@dataclass
class BucketState:
    bucket_id: str
    queue_size: int
    capacity: int
    leak_rate: float
    last_leak_time: int
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    processed_requests: int = 0

class LeakyBucketLimiter:
    def __init__(self):
        self.buckets: Dict[str, BucketConfig] = {}
        self.queues: Dict[str, deque] = {}
        self.last_leak_times: Dict[str, int] = {}
        self.stats: Dict[str, Dict] = {}

    def configure_bucket(self, config: BucketConfig) -> BucketState:
        """Create or update a bucket configuration."""
        now_ms = int(time.time() * 1000)

        self.buckets[config.bucket_id] = config
        if config.bucket_id not in self.queues:
            self.queues[config.bucket_id] = deque()
            self.last_leak_times[config.bucket_id] = now_ms
            self.stats[config.bucket_id] = {
                "total_requests": 0,
                "allowed_requests": 0,
                "rejected_requests": 0,
                "processed_requests": 0
            }

        return self.get_bucket_status(config.bucket_id)

    def allow_request(self, bucket_id: str,
                     request_id: str = None) -> tuple:
        """
        Try to queue a request.
        Returns: (allowed, queue_position, estimated_wait_ms)
        """
        if bucket_id not in self.buckets:
            return (False, 0, 0)

        config = self.buckets[bucket_id]
        queue = self.queues[bucket_id]
        stats = self.stats[bucket_id]
        now_ms = int(time.time() * 1000)

        # Process leaked requests first
        self._process_leaks(bucket_id, now_ms)

        stats["total_requests"] += 1

        # Check if bucket is full
        if len(queue) >= config.capacity:
            stats["rejected_requests"] += 1
            return (False, 0, 0)

        # Calculate estimated processing time
        queue_position = len(queue)
        wait_time_ms = int((queue_position / config.leak_rate) * 1000)

        # Add to queue
        req = QueuedRequest(
            request_id=request_id or f"req_{now_ms}_{queue_position}",
            enqueue_time=now_ms,
            estimated_process_time=now_ms + wait_time_ms
        )
        queue.append(req)

        stats["allowed_requests"] += 1

        return (True, queue_position + 1, wait_time_ms)

    def _process_leaks(self, bucket_id: str, now_ms: int):
        """Process requests that have 'leaked' from the bucket."""
        config = self.buckets[bucket_id]
        queue = self.queues[bucket_id]
        stats = self.stats[bucket_id]
        last_leak = self.last_leak_times[bucket_id]

        elapsed_ms = now_ms - last_leak
        if elapsed_ms <= 0:
            return

        # Calculate how many requests should have leaked
        requests_to_process = int((elapsed_ms / 1000.0) * config.leak_rate)

        # Process requests
        processed = 0
        while queue and processed < requests_to_process:
            queue.popleft()
            processed += 1
            stats["processed_requests"] += 1

        # Update last leak time (only for processed amount)
        if processed > 0:
            leaked_time_ms = int((processed / config.leak_rate) * 1000)
            self.last_leak_times[bucket_id] = last_leak + leaked_time_ms

    def get_bucket_status(self, bucket_id: str) -> Optional[BucketState]:
        """Get current bucket status."""
        if bucket_id not in self.buckets:
            return None

        now_ms = int(time.time() * 1000)
        self._process_leaks(bucket_id, now_ms)

        config = self.buckets[bucket_id]
        queue = self.queues[bucket_id]
        stats = self.stats[bucket_id]

        return BucketState(
            bucket_id=bucket_id,
            queue_size=len(queue),
            capacity=config.capacity,
            leak_rate=config.leak_rate,
            last_leak_time=self.last_leak_times[bucket_id],
            total_requests=stats["total_requests"],
            allowed_requests=stats["allowed_requests"],
            rejected_requests=stats["rejected_requests"],
            processed_requests=stats["processed_requests"]
        )

    def get_queued_requests(self, bucket_id: str) -> List[QueuedRequest]:
        """Get list of queued requests."""
        if bucket_id not in self.queues:
            return []

        now_ms = int(time.time() * 1000)
        self._process_leaks(bucket_id, now_ms)

        return list(self.queues[bucket_id])

    def delete_bucket(self, bucket_id: str) -> bool:
        """Remove a bucket."""
        if bucket_id in self.buckets:
            del self.buckets[bucket_id]
            del self.queues[bucket_id]
            del self.last_leak_times[bucket_id]
            del self.stats[bucket_id]
            return True
        return False


class LeakyBucketProcessor:
    """Background processor that handles queued requests."""

    def __init__(self, limiter: LeakyBucketLimiter):
        self.limiter = limiter
        self.handlers: Dict[str, callable] = {}

    async def run(self):
        """Continuously process requests at the leak rate."""
        while True:
            for bucket_id, config in self.limiter.buckets.items():
                queue = self.limiter.queues.get(bucket_id)
                if queue:
                    request = queue[0]  # Peek at next request

                    # Check if it's time to process
                    now_ms = int(time.time() * 1000)
                    if now_ms >= request.estimated_process_time:
                        # Process the request
                        queue.popleft()
                        self.limiter.stats[bucket_id]["processed_requests"] += 1

                        if bucket_id in self.handlers:
                            await self.handlers[bucket_id](request)

            await asyncio.sleep(0.01)  # 10ms granularity
```

---

## Platform Deployment

### Cluster Configuration

- 3+ node cluster
- Each node maintains its own queue (or shared via Redis)
- Processing happens at consistent rate
- gRPC for request submission

### gRPC Services

```protobuf
service RateLimiterService {
    rpc AllowRequest(AllowRequestRequest) returns (AllowRequestResponse);
    rpc GetBucketStatus(GetBucketStatusRequest) returns (GetBucketStatusResponse);
    rpc ConfigureBucket(ConfigureBucketRequest) returns (ConfigureBucketResponse);
    rpc DeleteBucket(DeleteBucketRequest) returns (DeleteBucketResponse);
    rpc GetLeader(GetLeaderRequest) returns (GetLeaderResponse);
    rpc GetClusterStatus(GetClusterStatusRequest) returns (GetClusterStatusResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestLeakyBucket:
    async def test_constant_output_rate(self, cluster):
        """Requests are processed at constant rate."""
        await cluster[0].ConfigureBucket(
            bucket_id="test",
            capacity=100,
            leak_rate=10.0  # 10 requests per second
        )

        # Submit 50 requests
        for i in range(50):
            await cluster[0].AllowRequest(bucket_id="test")

        # Wait and check processing rate
        start = time.time()
        initial_status = await cluster[0].GetBucketStatus(bucket_id="test")
        initial_processed = initial_status.bucket.processed_requests

        await asyncio.sleep(2.0)  # Wait 2 seconds

        final_status = await cluster[0].GetBucketStatus(bucket_id="test")
        final_processed = final_status.bucket.processed_requests

        # Should process ~20 requests in 2 seconds
        processed = final_processed - initial_processed
        assert 18 <= processed <= 22

    async def test_queue_rejection(self, cluster):
        """Requests rejected when queue is full."""
        await cluster[0].ConfigureBucket(
            bucket_id="test",
            capacity=10,
            leak_rate=1.0  # Very slow processing
        )

        # Fill the queue
        for i in range(10):
            response = await cluster[0].AllowRequest(bucket_id="test")
            assert response.allowed

        # 11th request should be rejected
        response = await cluster[0].AllowRequest(bucket_id="test")
        assert not response.allowed

    async def test_estimated_wait_time(self, cluster):
        """Wait time estimate is accurate."""
        await cluster[0].ConfigureBucket(
            bucket_id="test",
            capacity=100,
            leak_rate=10.0  # 10/sec = 100ms per request
        )

        # First request: immediate
        response1 = await cluster[0].AllowRequest(bucket_id="test")
        assert response1.estimated_wait_ms == 0

        # 11th request: should wait ~1 second
        for i in range(9):
            await cluster[0].AllowRequest(bucket_id="test")

        response10 = await cluster[0].AllowRequest(bucket_id="test")
        # Queue position 10, at 10/sec = 1000ms wait
        assert 900 <= response10.estimated_wait_ms <= 1100

    async def test_smooth_output(self, cluster):
        """Output rate is smooth despite bursty input."""
        await cluster[0].ConfigureBucket(
            bucket_id="smooth",
            capacity=100,
            leak_rate=10.0
        )

        # Burst of 50 requests
        for i in range(50):
            await cluster[0].AllowRequest(bucket_id="smooth")

        # Monitor processing over time
        processing_times = []
        last_processed = 0

        for _ in range(5):  # Check every 500ms for 2.5 seconds
            await asyncio.sleep(0.5)
            status = await cluster[0].GetBucketStatus(bucket_id="smooth")
            processed = status.bucket.processed_requests - last_processed
            processing_times.append(processed)
            last_processed = status.bucket.processed_requests

        # Each 500ms interval should process ~5 requests (10/sec)
        for count in processing_times:
            assert 4 <= count <= 6

    async def test_queue_drains(self, cluster):
        """Queue eventually drains completely."""
        await cluster[0].ConfigureBucket(
            bucket_id="drain",
            capacity=20,
            leak_rate=100.0  # Fast processing
        )

        # Add 20 requests
        for i in range(20):
            await cluster[0].AllowRequest(bucket_id="drain")

        status = await cluster[0].GetBucketStatus(bucket_id="drain")
        assert status.bucket.queue_size == 20

        # Wait for drain
        await asyncio.sleep(0.5)

        status = await cluster[0].GetBucketStatus(bucket_id="drain")
        assert status.bucket.queue_size == 0
        assert status.bucket.processed_requests == 20
```

### Comparison with Token Bucket

```python
async def test_leaky_vs_token_bucket_behavior(self, cluster):
    """Demonstrate difference from token bucket."""
    # Leaky bucket: constant output regardless of burst
    await cluster[0].ConfigureBucket(
        bucket_id="leaky",
        capacity=100,
        leak_rate=10.0
    )

    # Submit burst of 50
    for i in range(50):
        await cluster[0].AllowRequest(bucket_id="leaky")

    # First request is queued, not immediately processed
    # Unlike token bucket, all requests wait in queue
    status = await cluster[0].GetBucketStatus(bucket_id="leaky")
    assert status.bucket.queue_size == 50
    assert status.bucket.processed_requests == 0

    # After 1 second, only 10 should be processed
    await asyncio.sleep(1.0)
    status = await cluster[0].GetBucketStatus(bucket_id="leaky")
    assert 9 <= status.bucket.processed_requests <= 11
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Constant Rate | Output rate matches leak_rate |
| Queue Rejection | Rejects when queue full |
| Wait Estimation | Accurate wait time prediction |
| Smooth Output | Even distribution over time |
