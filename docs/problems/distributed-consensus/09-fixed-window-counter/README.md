# Fixed Window Counter Rate Limiter

## Problem Overview

Implement a distributed fixed window counter rate limiter that tracks requests within fixed time windows.

**Difficulty:** Easy (L4 - Mid-Level Engineer)

---

## Best Solution

### Algorithm Overview

The fixed window counter algorithm works by:
1. Time is divided into fixed windows (e.g., 1 minute each)
2. Each window has a counter that tracks requests
3. When a new window starts, the counter resets to zero
4. Requests are rejected when counter exceeds the limit

**Note:** This algorithm has the "boundary problem" - 2x traffic can occur at window edges.

### Implementation

```python
import time
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class LimitConfig:
    limit_id: str
    max_requests: int
    window_size_ms: int

@dataclass
class WindowState:
    limit_id: str
    window_start: int       # milliseconds
    window_end: int
    current_count: int
    max_requests: int
    window_size_ms: int
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0

class FixedWindowLimiter:
    def __init__(self):
        self.configs: Dict[str, LimitConfig] = {}
        self.windows: Dict[str, WindowState] = {}

    def configure_limit(self, config: LimitConfig) -> WindowState:
        """Create or update a rate limit configuration."""
        now_ms = int(time.time() * 1000)

        self.configs[config.limit_id] = config

        if config.limit_id not in self.windows:
            window_start = self._get_window_start(now_ms, config.window_size_ms)
            self.windows[config.limit_id] = WindowState(
                limit_id=config.limit_id,
                window_start=window_start,
                window_end=window_start + config.window_size_ms,
                current_count=0,
                max_requests=config.max_requests,
                window_size_ms=config.window_size_ms
            )

        return self.windows[config.limit_id]

    def _get_window_start(self, now_ms: int, window_size_ms: int) -> int:
        """Calculate the start of the current window."""
        return (now_ms // window_size_ms) * window_size_ms

    def allow_request(self, limit_id: str, cost: int = 1) -> tuple:
        """
        Check if a request should be allowed.
        Returns: (allowed, current_count, remaining, reset_at)
        """
        if limit_id not in self.configs:
            return (False, 0, 0, 0)

        config = self.configs[limit_id]
        window = self.windows[limit_id]
        now_ms = int(time.time() * 1000)

        # Check if we've moved to a new window
        current_window_start = self._get_window_start(now_ms, config.window_size_ms)

        if current_window_start != window.window_start:
            # Reset for new window
            window.window_start = current_window_start
            window.window_end = current_window_start + config.window_size_ms
            window.current_count = 0

        window.total_requests += 1

        # Check limit
        if window.current_count + cost <= config.max_requests:
            window.current_count += cost
            window.total_allowed += 1
            remaining = config.max_requests - window.current_count
            return (True, window.current_count, remaining, window.window_end)
        else:
            window.total_rejected += 1
            return (False, window.current_count, 0, window.window_end)

    def get_window_status(self, limit_id: str) -> Optional[WindowState]:
        """Get current window status."""
        if limit_id not in self.windows:
            return None

        config = self.configs[limit_id]
        window = self.windows[limit_id]
        now_ms = int(time.time() * 1000)

        # Update window if needed
        current_window_start = self._get_window_start(now_ms, config.window_size_ms)
        if current_window_start != window.window_start:
            window.window_start = current_window_start
            window.window_end = current_window_start + config.window_size_ms
            window.current_count = 0

        return window

    def delete_limit(self, limit_id: str) -> bool:
        """Remove a rate limit."""
        if limit_id in self.configs:
            del self.configs[limit_id]
            del self.windows[limit_id]
            return True
        return False
```

### Distributed Implementation with Redis

```python
class DistributedFixedWindow:
    """Distributed fixed window using Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def allow_request(self, limit_id: str, max_requests: int,
                           window_size_ms: int, cost: int = 1) -> tuple:
        """
        Atomic fixed window check using Redis.
        """
        now_ms = int(time.time() * 1000)
        window_start = (now_ms // window_size_ms) * window_size_ms
        key = f"ratelimit:{limit_id}:{window_start}"

        # Atomic increment
        current = await self.redis.incr(key)

        if current == 1:
            # First request in window - set expiry
            await self.redis.pexpire(key, window_size_ms)

        if current <= max_requests:
            remaining = max_requests - current
            return (True, current, remaining, window_start + window_size_ms)
        else:
            # Over limit - decrement the counter we just incremented
            await self.redis.decr(key)
            return (False, current - 1, 0, window_start + window_size_ms)

    async def get_window_status(self, limit_id: str, max_requests: int,
                                window_size_ms: int) -> WindowState:
        """Get current window status."""
        now_ms = int(time.time() * 1000)
        window_start = (now_ms // window_size_ms) * window_size_ms
        key = f"ratelimit:{limit_id}:{window_start}"

        current = await self.redis.get(key) or 0

        return WindowState(
            limit_id=limit_id,
            window_start=window_start,
            window_end=window_start + window_size_ms,
            current_count=int(current),
            max_requests=max_requests,
            window_size_ms=window_size_ms
        )
```

---

## Platform Deployment

### Cluster Configuration

- **5-node cluster** for high availability and distributed rate limiting
- Shared state via Redis for distributed counting
- Each node can handle limit checks
- Tolerates 2 node failures

### gRPC Services

```protobuf
service RateLimiterService {
    rpc AllowRequest(AllowRequestRequest) returns (AllowRequestResponse);
    rpc GetWindowStatus(GetWindowStatusRequest) returns (GetWindowStatusResponse);
    rpc ConfigureLimit(ConfigureLimitRequest) returns (ConfigureLimitResponse);
    rpc DeleteLimit(DeleteLimitRequest) returns (DeleteLimitResponse);
    rpc GetLeader(GetLeaderRequest) returns (GetLeaderResponse);
    rpc GetClusterStatus(GetClusterStatusRequest) returns (GetClusterStatusResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestFixedWindowCounter:
    async def test_basic_limiting(self, cluster):
        """Requests within window limit are allowed."""
        await cluster[0].ConfigureLimit(
            limit_id="test",
            max_requests=10,
            window_size_ms=60000  # 1 minute
        )

        # First 10 requests should pass
        for i in range(10):
            response = await cluster[0].AllowRequest(limit_id="test")
            assert response.allowed
            assert response.remaining == 10 - (i + 1)

        # 11th should fail
        response = await cluster[0].AllowRequest(limit_id="test")
        assert not response.allowed
        assert response.remaining == 0

    async def test_window_reset(self, cluster):
        """Counter resets when window changes."""
        window_ms = 1000  # 1 second window

        await cluster[0].ConfigureLimit(
            limit_id="reset_test",
            max_requests=5,
            window_size_ms=window_ms
        )

        # Exhaust limit
        for i in range(5):
            await cluster[0].AllowRequest(limit_id="reset_test")

        response = await cluster[0].AllowRequest(limit_id="reset_test")
        assert not response.allowed

        # Wait for new window
        await asyncio.sleep(1.1)

        # Should be allowed again
        response = await cluster[0].AllowRequest(limit_id="reset_test")
        assert response.allowed
        assert response.current_count == 1

    async def test_boundary_problem(self, cluster):
        """Demonstrate the boundary problem of fixed windows."""
        window_ms = 2000  # 2 second window

        await cluster[0].ConfigureLimit(
            limit_id="boundary",
            max_requests=10,
            window_size_ms=window_ms
        )

        # Wait until we're near end of window (last 100ms)
        now = time.time() * 1000
        window_start = (int(now) // window_ms) * window_ms
        time_to_boundary = window_start + window_ms - now

        if time_to_boundary > 100:
            await asyncio.sleep((time_to_boundary - 100) / 1000)

        # Make 10 requests at end of window
        for i in range(10):
            response = await cluster[0].AllowRequest(limit_id="boundary")
            assert response.allowed

        # Wait for new window (cross boundary)
        await asyncio.sleep(0.15)

        # Make 10 more requests at start of new window
        for i in range(10):
            response = await cluster[0].AllowRequest(limit_id="boundary")
            assert response.allowed

        # We just made 20 requests in ~200ms despite 10/2sec limit!
        # This is the boundary problem

    async def test_distributed_accuracy(self, cluster):
        """Multiple nodes share the same counter."""
        await cluster[0].ConfigureLimit(
            limit_id="distributed",
            max_requests=30,
            window_size_ms=60000
        )

        # Each of 3 nodes makes 10 requests
        tasks = []
        for node in cluster:  # 3 nodes
            for _ in range(12):
                tasks.append(node.AllowRequest(limit_id="distributed"))

        results = await asyncio.gather(*tasks)

        # Exactly 30 should be allowed
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 30

    async def test_cost_based_requests(self, cluster):
        """Requests can have variable costs."""
        await cluster[0].ConfigureLimit(
            limit_id="cost",
            max_requests=100,
            window_size_ms=60000
        )

        # Request with cost of 25 (4 times = 100)
        for i in range(4):
            response = await cluster[0].AllowRequest(
                limit_id="cost",
                cost=25
            )
            assert response.allowed

        # Next request should fail
        response = await cluster[0].AllowRequest(
            limit_id="cost",
            cost=1
        )
        assert not response.allowed
```

### Performance Tests

```python
async def test_high_throughput(self, cluster):
    """Fixed window handles high request rates."""
    await cluster[0].ConfigureLimit(
        limit_id="perf",
        max_requests=100000,
        window_size_ms=60000
    )

    start = time.time()
    tasks = [
        cluster[0].AllowRequest(limit_id="perf")
        for _ in range(10000)
    ]
    await asyncio.gather(*tasks)
    duration = time.time() - start

    # Should handle 10K requests very quickly
    assert duration < 1.0
    print(f"Throughput: {10000/duration:.0f} req/sec")
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Limiting | Enforces max_requests per window |
| Window Reset | Counter resets at window boundary |
| Distributed | Accurate across multiple nodes |
| Throughput | > 10,000 requests/second |

## Known Limitations

The fixed window counter has a "boundary problem":
- At the boundary between two windows, up to 2x the limit can be allowed
- Example: 10 req/min limit allows 20 requests if 10 are at 0:59 and 10 at 1:00

Consider using sliding window algorithms for stricter limits.
