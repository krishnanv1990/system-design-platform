# Token Bucket Rate Limiter

## Problem Overview

Implement a distributed token bucket rate limiter that allows bursty traffic while maintaining an average rate limit.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

The token bucket algorithm works by:
1. A bucket holds tokens up to a maximum capacity
2. Tokens are added at a fixed rate (refill rate)
3. Each request consumes one or more tokens
4. If insufficient tokens, the request is rejected or delayed

### Implementation

```python
import time
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class BucketConfig:
    bucket_id: str
    capacity: int           # Maximum tokens
    refill_rate: float      # Tokens per second
    initial_tokens: int = None

    def __post_init__(self):
        if self.initial_tokens is None:
            self.initial_tokens = self.capacity

@dataclass
class BucketState:
    bucket_id: str
    current_tokens: float
    capacity: int
    refill_rate: float
    last_refill_time: int  # milliseconds
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0

class TokenBucketLimiter:
    def __init__(self):
        self.buckets: Dict[str, BucketState] = {}

    def configure_bucket(self, config: BucketConfig) -> BucketState:
        """Create or update a bucket configuration."""
        now_ms = int(time.time() * 1000)

        if config.bucket_id in self.buckets:
            # Update existing bucket
            bucket = self.buckets[config.bucket_id]
            bucket.capacity = config.capacity
            bucket.refill_rate = config.refill_rate
        else:
            # Create new bucket
            bucket = BucketState(
                bucket_id=config.bucket_id,
                current_tokens=config.initial_tokens,
                capacity=config.capacity,
                refill_rate=config.refill_rate,
                last_refill_time=now_ms
            )
            self.buckets[config.bucket_id] = bucket

        return bucket

    def allow_request(self, bucket_id: str, tokens_requested: int = 1) -> tuple:
        """
        Check if a request should be allowed.
        Returns: (allowed, tokens_remaining, retry_after_ms)
        """
        if bucket_id not in self.buckets:
            return (False, 0, 0)

        bucket = self.buckets[bucket_id]
        now_ms = int(time.time() * 1000)

        # Refill tokens based on elapsed time
        self._refill(bucket, now_ms)

        bucket.total_requests += 1

        if bucket.current_tokens >= tokens_requested:
            # Allow request and consume tokens
            bucket.current_tokens -= tokens_requested
            bucket.allowed_requests += 1
            return (True, bucket.current_tokens, 0)
        else:
            # Reject request
            bucket.rejected_requests += 1

            # Calculate retry time
            tokens_needed = tokens_requested - bucket.current_tokens
            retry_after_ms = int((tokens_needed / bucket.refill_rate) * 1000)

            return (False, bucket.current_tokens, retry_after_ms)

    def _refill(self, bucket: BucketState, now_ms: int):
        """Refill tokens based on elapsed time."""
        elapsed_ms = now_ms - bucket.last_refill_time

        if elapsed_ms > 0:
            # Calculate tokens to add
            tokens_to_add = (elapsed_ms / 1000.0) * bucket.refill_rate

            # Add tokens up to capacity
            bucket.current_tokens = min(
                bucket.capacity,
                bucket.current_tokens + tokens_to_add
            )
            bucket.last_refill_time = now_ms

    def get_bucket_status(self, bucket_id: str) -> Optional[BucketState]:
        """Get current bucket status."""
        if bucket_id not in self.buckets:
            return None

        bucket = self.buckets[bucket_id]
        now_ms = int(time.time() * 1000)
        self._refill(bucket, now_ms)

        return bucket

    def delete_bucket(self, bucket_id: str) -> bool:
        """Remove a bucket."""
        if bucket_id in self.buckets:
            del self.buckets[bucket_id]
            return True
        return False
```

### Distributed Implementation

```python
class DistributedTokenBucket:
    """Distributed token bucket using Redis for shared state."""

    def __init__(self, redis_client, node_id: str):
        self.redis = redis_client
        self.node_id = node_id

    async def allow_request(self, bucket_id: str,
                           tokens_requested: int = 1) -> tuple:
        """
        Atomic token bucket check using Redis Lua script.
        """
        lua_script = """
        local bucket_key = KEYS[1]
        local tokens_requested = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local refill_rate = tonumber(ARGV[3])
        local now_ms = tonumber(ARGV[4])

        -- Get current state
        local current_tokens = tonumber(redis.call('HGET', bucket_key, 'tokens') or capacity)
        local last_refill = tonumber(redis.call('HGET', bucket_key, 'last_refill') or now_ms)

        -- Calculate refill
        local elapsed_ms = now_ms - last_refill
        local tokens_to_add = (elapsed_ms / 1000.0) * refill_rate
        current_tokens = math.min(capacity, current_tokens + tokens_to_add)

        local allowed = 0
        local remaining = current_tokens
        local retry_after = 0

        if current_tokens >= tokens_requested then
            current_tokens = current_tokens - tokens_requested
            allowed = 1
            remaining = current_tokens
        else
            local tokens_needed = tokens_requested - current_tokens
            retry_after = math.ceil((tokens_needed / refill_rate) * 1000)
        end

        -- Update state
        redis.call('HSET', bucket_key, 'tokens', current_tokens)
        redis.call('HSET', bucket_key, 'last_refill', now_ms)
        redis.call('EXPIRE', bucket_key, 3600)  -- 1 hour TTL

        return {allowed, remaining, retry_after}
        """

        config = await self.get_bucket_config(bucket_id)
        if not config:
            return (False, 0, 0)

        now_ms = int(time.time() * 1000)

        result = await self.redis.eval(
            lua_script,
            keys=[f"bucket:{bucket_id}"],
            args=[tokens_requested, config.capacity,
                  config.refill_rate, now_ms]
        )

        return (bool(result[0]), result[1], result[2])

    async def configure_bucket(self, config: BucketConfig):
        """Store bucket configuration."""
        await self.redis.hset(f"bucket_config:{config.bucket_id}", mapping={
            "capacity": config.capacity,
            "refill_rate": config.refill_rate,
            "initial_tokens": config.initial_tokens or config.capacity
        })

    async def get_bucket_config(self, bucket_id: str) -> Optional[BucketConfig]:
        """Get bucket configuration."""
        data = await self.redis.hgetall(f"bucket_config:{bucket_id}")
        if not data:
            return None

        return BucketConfig(
            bucket_id=bucket_id,
            capacity=int(data[b'capacity']),
            refill_rate=float(data[b'refill_rate']),
            initial_tokens=int(data[b'initial_tokens'])
        )
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** for high availability and distributed rate limiting
- Shared state via Redis or consensus protocol
- Each node handles local bucket operations
- Tolerates 2 node failures

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
class TestTokenBucket:
    async def test_basic_rate_limiting(self, cluster):
        """Requests within limit are allowed."""
        await cluster[0].ConfigureBucket(
            bucket_id="test",
            capacity=10,
            refill_rate=1.0  # 1 token per second
        )

        # First 10 requests should pass
        for i in range(10):
            response = await cluster[0].AllowRequest(bucket_id="test")
            assert response.allowed

        # 11th request should fail
        response = await cluster[0].AllowRequest(bucket_id="test")
        assert not response.allowed
        assert response.retry_after_ms > 0

    async def test_token_refill(self, cluster):
        """Tokens refill over time."""
        await cluster[0].ConfigureBucket(
            bucket_id="test",
            capacity=5,
            refill_rate=10.0  # 10 tokens per second
        )

        # Exhaust tokens
        for i in range(5):
            await cluster[0].AllowRequest(bucket_id="test")

        response = await cluster[0].AllowRequest(bucket_id="test")
        assert not response.allowed

        # Wait for refill
        await asyncio.sleep(0.5)  # Should add 5 tokens

        response = await cluster[0].AllowRequest(bucket_id="test")
        assert response.allowed

    async def test_burst_handling(self, cluster):
        """Token bucket allows bursts up to capacity."""
        await cluster[0].ConfigureBucket(
            bucket_id="burst_test",
            capacity=100,
            refill_rate=10.0  # 10/sec steady, but 100 burst
        )

        # All 100 should pass immediately (burst)
        results = await asyncio.gather(*[
            cluster[0].AllowRequest(bucket_id="burst_test")
            for _ in range(100)
        ])

        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 100

        # Next request should fail
        response = await cluster[0].AllowRequest(bucket_id="burst_test")
        assert not response.allowed

    async def test_distributed_consistency(self, cluster):
        """All nodes enforce the same limit."""
        await cluster[0].ConfigureBucket(
            bucket_id="shared",
            capacity=30,
            refill_rate=0  # No refill for deterministic test
        )

        # Each node makes 10 requests
        tasks = []
        for node in cluster:  # 3 nodes
            for _ in range(15):
                tasks.append(node.AllowRequest(bucket_id="shared"))

        results = await asyncio.gather(*tasks)

        # Exactly 30 should be allowed
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 30

    async def test_multiple_token_consumption(self, cluster):
        """Requests can consume multiple tokens."""
        await cluster[0].ConfigureBucket(
            bucket_id="multi",
            capacity=100,
            refill_rate=0
        )

        # Request 25 tokens 4 times
        for i in range(4):
            response = await cluster[0].AllowRequest(
                bucket_id="multi",
                tokens_requested=25
            )
            assert response.allowed

        # 5th request should fail
        response = await cluster[0].AllowRequest(
            bucket_id="multi",
            tokens_requested=25
        )
        assert not response.allowed
```

### Performance Tests

```python
async def test_high_throughput(self, cluster):
    """Rate limiter handles high request rates."""
    await cluster[0].ConfigureBucket(
        bucket_id="perf",
        capacity=10000,
        refill_rate=10000
    )

    start = time.time()
    tasks = [
        cluster[0].AllowRequest(bucket_id="perf")
        for _ in range(10000)
    ]
    await asyncio.gather(*tasks)
    duration = time.time() - start

    # Should handle 10K requests in < 2 seconds
    assert duration < 2.0
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Limiting | Blocks requests over capacity |
| Token Refill | Tokens regenerate at configured rate |
| Burst Handling | Allows bursts up to capacity |
| Distributed | Consistent limits across nodes |
| Throughput | > 5000 requests/second |
