# Sliding Window Log Rate Limiter

## Problem Overview

Implement a distributed sliding window log rate limiter that provides precise rate limiting with no boundary issues.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

The sliding window log algorithm works by:
1. Each request's timestamp is stored in a sorted log
2. When a request arrives, remove entries older than the window
3. Count remaining entries; if under limit, allow and add new entry
4. Provides precise rate limiting with no boundary issues

**Trade-off:** More memory usage (stores all timestamps) but more accurate.

### Implementation

```python
import time
from dataclasses import dataclass
from typing import Dict, Optional, List
from sortedcontainers import SortedList

@dataclass
class LimitConfig:
    limit_id: str
    max_requests: int
    window_size_ms: int

@dataclass
class LogEntry:
    timestamp: int          # milliseconds
    request_id: str

@dataclass
class LogState:
    limit_id: str
    window_size_ms: int
    max_requests: int
    entries: List[LogEntry]
    current_count: int
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0

class SlidingWindowLogLimiter:
    def __init__(self):
        self.configs: Dict[str, LimitConfig] = {}
        self.logs: Dict[str, SortedList] = {}  # Sorted by timestamp
        self.stats: Dict[str, Dict] = {}

    def configure_limit(self, config: LimitConfig) -> LogState:
        """Create or update a rate limit configuration."""
        self.configs[config.limit_id] = config

        if config.limit_id not in self.logs:
            self.logs[config.limit_id] = SortedList(key=lambda x: x.timestamp)
            self.stats[config.limit_id] = {
                "total_requests": 0,
                "total_allowed": 0,
                "total_rejected": 0
            }

        return self.get_log_status(config.limit_id)

    def allow_request(self, limit_id: str,
                     request_id: str = None,
                     timestamp: int = None) -> tuple:
        """
        Check if a request should be allowed.
        Returns: (allowed, current_count, remaining, oldest_entry)
        """
        if limit_id not in self.configs:
            return (False, 0, 0, 0)

        config = self.configs[limit_id]
        log = self.logs[limit_id]
        stats = self.stats[limit_id]

        now_ms = timestamp or int(time.time() * 1000)
        window_start = now_ms - config.window_size_ms

        # Remove expired entries
        self._cleanup_expired(limit_id, window_start)

        stats["total_requests"] += 1

        # Check count
        current_count = len(log)

        if current_count < config.max_requests:
            # Add entry
            entry = LogEntry(
                timestamp=now_ms,
                request_id=request_id or f"req_{now_ms}"
            )
            log.add(entry)

            stats["total_allowed"] += 1
            remaining = config.max_requests - len(log)
            oldest = log[0].timestamp if log else now_ms

            return (True, len(log), remaining, oldest)
        else:
            stats["total_rejected"] += 1
            oldest = log[0].timestamp if log else now_ms
            return (False, current_count, 0, oldest)

    def _cleanup_expired(self, limit_id: str, window_start: int):
        """Remove entries older than window_start."""
        log = self.logs[limit_id]

        # Remove entries with timestamp < window_start
        while log and log[0].timestamp < window_start:
            log.pop(0)

    def get_log_status(self, limit_id: str,
                       include_entries: bool = False) -> Optional[LogState]:
        """Get current log status."""
        if limit_id not in self.configs:
            return None

        config = self.configs[limit_id]
        log = self.logs[limit_id]
        stats = self.stats[limit_id]

        now_ms = int(time.time() * 1000)
        window_start = now_ms - config.window_size_ms
        self._cleanup_expired(limit_id, window_start)

        entries = list(log) if include_entries else []

        return LogState(
            limit_id=limit_id,
            window_size_ms=config.window_size_ms,
            max_requests=config.max_requests,
            entries=entries,
            current_count=len(log),
            total_requests=stats["total_requests"],
            total_allowed=stats["total_allowed"],
            total_rejected=stats["total_rejected"]
        )

    def delete_limit(self, limit_id: str) -> bool:
        """Remove a rate limit."""
        if limit_id in self.configs:
            del self.configs[limit_id]
            del self.logs[limit_id]
            del self.stats[limit_id]
            return True
        return False
```

### Distributed Implementation with Redis

```python
class DistributedSlidingWindowLog:
    """Distributed sliding window log using Redis sorted sets."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def allow_request(self, limit_id: str, max_requests: int,
                           window_size_ms: int,
                           request_id: str = None) -> tuple:
        """
        Atomic sliding window check using Redis sorted sets.
        """
        now_ms = int(time.time() * 1000)
        window_start = now_ms - window_size_ms
        key = f"ratelimit:log:{limit_id}"
        request_id = request_id or f"{now_ms}:{id(now_ms)}"

        # Lua script for atomic operation
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local max_requests = tonumber(ARGV[3])
        local request_id = ARGV[4]

        -- Remove expired entries
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start - 1)

        -- Count current entries
        local count = redis.call('ZCARD', key)

        if count < max_requests then
            -- Add new entry (score = timestamp)
            redis.call('ZADD', key, now, request_id)
            redis.call('PEXPIRE', key, ARGV[5])

            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local oldest_ts = oldest[2] or now

            return {1, count + 1, max_requests - count - 1, oldest_ts}
        else
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local oldest_ts = oldest[2] or now
            return {0, count, 0, oldest_ts}
        end
        """

        result = await self.redis.eval(
            lua_script,
            keys=[key],
            args=[now_ms, window_start, max_requests, request_id, window_size_ms]
        )

        return (bool(result[0]), result[1], result[2], result[3])

    async def get_log_status(self, limit_id: str,
                            window_size_ms: int) -> LogState:
        """Get current log status."""
        now_ms = int(time.time() * 1000)
        window_start = now_ms - window_size_ms
        key = f"ratelimit:log:{limit_id}"

        # Remove expired and get count
        await self.redis.zremrangebyscore(key, 0, window_start - 1)
        entries = await self.redis.zrange(key, 0, -1, withscores=True)

        return LogState(
            limit_id=limit_id,
            window_size_ms=window_size_ms,
            max_requests=0,  # Unknown without config
            entries=[
                LogEntry(timestamp=int(score), request_id=member.decode())
                for member, score in entries
            ],
            current_count=len(entries)
        )
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** for high availability and distributed rate limiting
- Redis sorted sets for distributed log storage
- Automatic cleanup of expired entries
- Tolerates 2 node failures

### gRPC Services

```protobuf
service RateLimiterService {
    rpc AllowRequest(AllowRequestRequest) returns (AllowRequestResponse);
    rpc GetLogStatus(GetLogStatusRequest) returns (GetLogStatusResponse);
    rpc ConfigureLimit(ConfigureLimitRequest) returns (ConfigureLimitResponse);
    rpc DeleteLimit(DeleteLimitRequest) returns (DeleteLimitResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestSlidingWindowLog:
    async def test_basic_limiting(self, cluster):
        """Requests within sliding window limit are allowed."""
        await cluster[0].ConfigureLimit(
            limit_id="test",
            max_requests=10,
            window_size_ms=10000  # 10 seconds
        )

        # First 10 requests should pass
        for i in range(10):
            response = await cluster[0].AllowRequest(limit_id="test")
            assert response.allowed

        # 11th should fail
        response = await cluster[0].AllowRequest(limit_id="test")
        assert not response.allowed

    async def test_sliding_window_behavior(self, cluster):
        """Window slides continuously (no boundary problem)."""
        window_ms = 2000  # 2 second window

        await cluster[0].ConfigureLimit(
            limit_id="slide",
            max_requests=10,
            window_size_ms=window_ms
        )

        # Make 5 requests
        for i in range(5):
            await cluster[0].AllowRequest(limit_id="slide")

        # Wait 1 second (half the window)
        await asyncio.sleep(1.0)

        # Make 5 more requests (total 10 in last 2 seconds)
        for i in range(5):
            response = await cluster[0].AllowRequest(limit_id="slide")
            assert response.allowed

        # Next should fail
        response = await cluster[0].AllowRequest(limit_id="slide")
        assert not response.allowed

        # Wait 1 more second (first 5 requests expire)
        await asyncio.sleep(1.1)

        # Should allow 5 more
        for i in range(5):
            response = await cluster[0].AllowRequest(limit_id="slide")
            assert response.allowed

    async def test_no_boundary_problem(self, cluster):
        """Unlike fixed window, no spike at boundaries."""
        window_ms = 2000

        await cluster[0].ConfigureLimit(
            limit_id="boundary",
            max_requests=10,
            window_size_ms=window_ms
        )

        # Make 10 requests
        for i in range(10):
            await cluster[0].AllowRequest(limit_id="boundary")

        # Immediately try more - should fail
        response = await cluster[0].AllowRequest(limit_id="boundary")
        assert not response.allowed

        # Wait just 1 second (half window) - should still fail
        await asyncio.sleep(1.0)
        response = await cluster[0].AllowRequest(limit_id="boundary")
        assert not response.allowed

        # No boundary exploitation possible!

    async def test_precise_timing(self, cluster):
        """Requests become allowed exactly when window slides."""
        window_ms = 1000  # 1 second

        await cluster[0].ConfigureLimit(
            limit_id="precise",
            max_requests=5,
            window_size_ms=window_ms
        )

        # Make 5 requests
        start = time.time()
        for i in range(5):
            await cluster[0].AllowRequest(limit_id="precise")

        # Should be blocked
        response = await cluster[0].AllowRequest(limit_id="precise")
        assert not response.allowed

        # Wait until first request expires
        elapsed = time.time() - start
        wait_time = 1.0 - elapsed + 0.05  # 50ms buffer
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        # Now should be allowed
        response = await cluster[0].AllowRequest(limit_id="precise")
        assert response.allowed

    async def test_distributed_consistency(self, cluster):
        """Multiple nodes share the same log."""
        await cluster[0].ConfigureLimit(
            limit_id="distributed",
            max_requests=30,
            window_size_ms=60000
        )

        # Each node makes requests
        tasks = []
        for node in cluster:
            for _ in range(15):
                tasks.append(node.AllowRequest(limit_id="distributed"))

        results = await asyncio.gather(*tasks)

        # Exactly 30 should be allowed
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 30
```

### Memory Usage Tests

```python
async def test_memory_cleanup(self, cluster):
    """Expired entries are cleaned up."""
    window_ms = 500  # 500ms window

    await cluster[0].ConfigureLimit(
        limit_id="cleanup",
        max_requests=1000,
        window_size_ms=window_ms
    )

    # Make many requests
    for i in range(100):
        await cluster[0].AllowRequest(limit_id="cleanup")

    # Check entry count
    status = await cluster[0].GetLogStatus(
        limit_id="cleanup",
        include_entries=True
    )
    assert len(status.log.entries) == 100

    # Wait for expiry
    await asyncio.sleep(0.6)

    # Entries should be cleaned
    status = await cluster[0].GetLogStatus(
        limit_id="cleanup",
        include_entries=True
    )
    assert len(status.log.entries) == 0
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Limiting | Enforces max_requests in sliding window |
| Sliding Behavior | No boundary exploitation possible |
| Precise Timing | Requests allowed exactly when window slides |
| Distributed | Consistent across multiple nodes |

## Memory Considerations

The sliding window log stores every request timestamp, which can be memory-intensive:
- **Memory per limit:** ~16-24 bytes per request
- **Example:** 1000 requests/sec × 60 sec window = 960KB - 1.4MB per limit

Consider sliding window counter for lower memory usage with slight accuracy trade-off.
