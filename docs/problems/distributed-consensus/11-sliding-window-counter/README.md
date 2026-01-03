# Sliding Window Counter Rate Limiter

## Problem Overview

Implement a distributed sliding window counter rate limiter that provides a good balance between accuracy and memory efficiency.

**Difficulty:** Medium (L5 - Senior Engineer)

---

## Best Solution

### Algorithm Overview

The sliding window counter is a hybrid approach:
1. Maintains counters for current and previous windows
2. Uses weighted average based on position in current window
3. Formula: `count = prev_count * (1 - elapsed/window) + curr_count`

**Trade-off:** Low memory (only 2 counters) with good accuracy.

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
    window_size_ms: int
    max_requests: int
    current_window_start: int
    current_count: int
    previous_window_start: int
    previous_count: int
    sliding_estimate: float
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0

class SlidingWindowCounterLimiter:
    def __init__(self):
        self.configs: Dict[str, LimitConfig] = {}
        self.windows: Dict[str, dict] = {}
        self.stats: Dict[str, Dict] = {}

    def configure_limit(self, config: LimitConfig) -> WindowState:
        """Create or update a rate limit configuration."""
        now_ms = int(time.time() * 1000)
        window_start = self._get_window_start(now_ms, config.window_size_ms)

        self.configs[config.limit_id] = config

        if config.limit_id not in self.windows:
            self.windows[config.limit_id] = {
                "current_start": window_start,
                "current_count": 0,
                "previous_start": window_start - config.window_size_ms,
                "previous_count": 0
            }
            self.stats[config.limit_id] = {
                "total_requests": 0,
                "total_allowed": 0,
                "total_rejected": 0
            }

        return self.get_window_status(config.limit_id)

    def _get_window_start(self, now_ms: int, window_size_ms: int) -> int:
        """Calculate the start of the current window."""
        return (now_ms // window_size_ms) * window_size_ms

    def _maybe_rotate_window(self, limit_id: str, now_ms: int):
        """Rotate windows if we've moved to a new window."""
        config = self.configs[limit_id]
        window = self.windows[limit_id]

        current_window_start = self._get_window_start(now_ms, config.window_size_ms)

        if current_window_start != window["current_start"]:
            # Check if we skipped more than one window
            windows_skipped = (current_window_start - window["current_start"]) // config.window_size_ms

            if windows_skipped >= 2:
                # Both windows should be 0
                window["previous_start"] = current_window_start - config.window_size_ms
                window["previous_count"] = 0
            else:
                # Normal rotation
                window["previous_start"] = window["current_start"]
                window["previous_count"] = window["current_count"]

            window["current_start"] = current_window_start
            window["current_count"] = 0

    def _calculate_sliding_count(self, limit_id: str, now_ms: int) -> float:
        """Calculate the weighted sliding window count."""
        config = self.configs[limit_id]
        window = self.windows[limit_id]

        # Calculate weight of previous window
        elapsed_in_current = now_ms - window["current_start"]
        previous_weight = 1.0 - (elapsed_in_current / config.window_size_ms)

        # Weighted sum
        sliding_count = (
            window["previous_count"] * previous_weight +
            window["current_count"]
        )

        return sliding_count

    def allow_request(self, limit_id: str, cost: int = 1,
                     timestamp: int = None) -> tuple:
        """
        Check if a request should be allowed.
        Returns: (allowed, sliding_count, remaining, reset_at)
        """
        if limit_id not in self.configs:
            return (False, 0, 0, 0)

        config = self.configs[limit_id]
        window = self.windows[limit_id]
        stats = self.stats[limit_id]

        now_ms = timestamp or int(time.time() * 1000)

        # Rotate windows if needed
        self._maybe_rotate_window(limit_id, now_ms)

        stats["total_requests"] += 1

        # Calculate current sliding count
        sliding_count = self._calculate_sliding_count(limit_id, now_ms)

        if sliding_count + cost <= config.max_requests:
            # Allow and increment current window counter
            window["current_count"] += cost
            stats["total_allowed"] += 1

            new_sliding = self._calculate_sliding_count(limit_id, now_ms)
            remaining = max(0, int(config.max_requests - new_sliding))
            reset_at = window["current_start"] + config.window_size_ms

            return (True, new_sliding, remaining, reset_at)
        else:
            stats["total_rejected"] += 1
            reset_at = window["current_start"] + config.window_size_ms
            return (False, sliding_count, 0, reset_at)

    def get_window_status(self, limit_id: str) -> Optional[WindowState]:
        """Get current window status."""
        if limit_id not in self.configs:
            return None

        config = self.configs[limit_id]
        window = self.windows[limit_id]
        stats = self.stats[limit_id]

        now_ms = int(time.time() * 1000)
        self._maybe_rotate_window(limit_id, now_ms)

        sliding_count = self._calculate_sliding_count(limit_id, now_ms)

        return WindowState(
            limit_id=limit_id,
            window_size_ms=config.window_size_ms,
            max_requests=config.max_requests,
            current_window_start=window["current_start"],
            current_count=window["current_count"],
            previous_window_start=window["previous_start"],
            previous_count=window["previous_count"],
            sliding_estimate=sliding_count,
            total_requests=stats["total_requests"],
            total_allowed=stats["total_allowed"],
            total_rejected=stats["total_rejected"]
        )

    def delete_limit(self, limit_id: str) -> bool:
        """Remove a rate limit."""
        if limit_id in self.configs:
            del self.configs[limit_id]
            del self.windows[limit_id]
            del self.stats[limit_id]
            return True
        return False
```

### Distributed Implementation with Redis

```python
class DistributedSlidingWindowCounter:
    """Distributed sliding window counter using Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def allow_request(self, limit_id: str, max_requests: int,
                           window_size_ms: int, cost: int = 1) -> tuple:
        """
        Atomic sliding window counter using Redis Lua script.
        """
        lua_script = """
        local limit_id = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_size = tonumber(ARGV[2])
        local max_requests = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])

        local current_window = math.floor(now / window_size) * window_size
        local previous_window = current_window - window_size

        local current_key = limit_id .. ':' .. current_window
        local previous_key = limit_id .. ':' .. previous_window

        local current_count = tonumber(redis.call('GET', current_key) or 0)
        local previous_count = tonumber(redis.call('GET', previous_key) or 0)

        -- Calculate weight
        local elapsed = now - current_window
        local previous_weight = 1 - (elapsed / window_size)

        -- Weighted count
        local sliding_count = previous_count * previous_weight + current_count

        if sliding_count + cost <= max_requests then
            redis.call('INCRBY', current_key, cost)
            redis.call('PEXPIRE', current_key, window_size * 2)

            local new_sliding = previous_count * previous_weight + current_count + cost
            local remaining = math.max(0, max_requests - new_sliding)

            return {1, new_sliding, remaining, current_window + window_size}
        else
            return {0, sliding_count, 0, current_window + window_size}
        end
        """

        now_ms = int(time.time() * 1000)

        result = await self.redis.eval(
            lua_script,
            keys=[f"ratelimit:sw:{limit_id}"],
            args=[now_ms, window_size_ms, max_requests, cost]
        )

        return (bool(result[0]), result[1], int(result[2]), int(result[3]))
```

---

## Platform Deployment

### Cluster Configuration

- 3+ node cluster
- Redis for distributed counters
- Only 2 keys per limit (current + previous window)

### gRPC Services

```protobuf
service RateLimiterService {
    rpc AllowRequest(AllowRequestRequest) returns (AllowRequestResponse);
    rpc GetWindowStatus(GetWindowStatusRequest) returns (GetWindowStatusResponse);
    rpc ConfigureLimit(ConfigureLimitRequest) returns (ConfigureLimitResponse);
    rpc DeleteLimit(DeleteLimitRequest) returns (DeleteLimitResponse);
}
```

---

## Realistic Testing

### Functional Tests

```python
class TestSlidingWindowCounter:
    async def test_basic_limiting(self, cluster):
        """Requests within limit are allowed."""
        await cluster[0].ConfigureLimit(
            limit_id="test",
            max_requests=10,
            window_size_ms=10000
        )

        # First 10 requests should pass
        for i in range(10):
            response = await cluster[0].AllowRequest(limit_id="test")
            assert response.allowed

        # 11th should fail
        response = await cluster[0].AllowRequest(limit_id="test")
        assert not response.allowed

    async def test_sliding_behavior(self, cluster):
        """Counter slides between windows."""
        window_ms = 2000  # 2 second window

        await cluster[0].ConfigureLimit(
            limit_id="slide",
            max_requests=10,
            window_size_ms=window_ms
        )

        # Make 10 requests at start of window
        for i in range(10):
            await cluster[0].AllowRequest(limit_id="slide")

        # Should be blocked
        response = await cluster[0].AllowRequest(limit_id="slide")
        assert not response.allowed

        # Wait 1 second (half the window)
        await asyncio.sleep(1.0)

        # Previous window weight = 0.5, so effective count = 10 * 0.5 + 0 = 5
        # Should allow 5 more
        for i in range(5):
            response = await cluster[0].AllowRequest(limit_id="slide")
            assert response.allowed

        # Should be blocked again
        response = await cluster[0].AllowRequest(limit_id="slide")
        assert not response.allowed

    async def test_weighted_calculation(self, cluster):
        """Verify weighted average calculation."""
        window_ms = 1000  # 1 second window

        await cluster[0].ConfigureLimit(
            limit_id="weighted",
            max_requests=100,
            window_size_ms=window_ms
        )

        # Make 50 requests
        for i in range(50):
            await cluster[0].AllowRequest(limit_id="weighted")

        # Wait for new window + 500ms (weight = 0.5)
        await asyncio.sleep(1.5)

        status = await cluster[0].GetWindowStatus(limit_id="weighted")

        # Previous count = 50, weight = 0.5, current = 0
        # Sliding estimate should be ~25
        assert 20 <= status.window.sliding_estimate <= 30

    async def test_smoother_than_fixed(self, cluster):
        """Better than fixed window at boundaries."""
        window_ms = 1000

        await cluster[0].ConfigureLimit(
            limit_id="boundary",
            max_requests=10,
            window_size_ms=window_ms
        )

        # Make 10 requests near end of window
        for i in range(10):
            await cluster[0].AllowRequest(limit_id="boundary")

        # Cross window boundary
        await asyncio.sleep(0.1)

        # Unlike fixed window, we can't make 10 more immediately
        # Because sliding count includes weighted previous window
        response = await cluster[0].AllowRequest(limit_id="boundary")

        # Should still be blocked (or allow only a few)
        # Previous weight ~0.9, so ~9 from previous window
        # Much better than fixed window which would allow 10

    async def test_memory_efficiency(self, cluster):
        """Uses constant memory (only 2 counters)."""
        window_ms = 60000  # 1 minute

        await cluster[0].ConfigureLimit(
            limit_id="memory",
            max_requests=100000,
            window_size_ms=window_ms
        )

        # Make lots of requests
        for i in range(10000):
            await cluster[0].AllowRequest(limit_id="memory")

        # Status should show only 2 counters
        status = await cluster[0].GetWindowStatus(limit_id="memory")

        # current_count and previous_count are the only stored values
        assert status.window.current_count <= 10000
        assert isinstance(status.window.previous_count, int)

    async def test_distributed_consistency(self, cluster):
        """Multiple nodes share counters correctly."""
        await cluster[0].ConfigureLimit(
            limit_id="distributed",
            max_requests=30,
            window_size_ms=60000
        )

        # Each node makes requests concurrently
        tasks = []
        for node in cluster:
            for _ in range(15):
                tasks.append(node.AllowRequest(limit_id="distributed"))

        results = await asyncio.gather(*tasks)

        # Should allow exactly 30
        allowed = sum(1 for r in results if r.allowed)
        assert allowed == 30
```

### Comparison Tests

```python
async def test_comparison_with_other_algorithms(self, cluster):
    """Compare sliding counter with fixed window."""
    window_ms = 2000

    # Fixed window (for comparison)
    await cluster[0].ConfigureLimit(
        limit_id="fixed",
        max_requests=10,
        window_size_ms=window_ms
    )

    # Sliding counter
    await cluster[0].ConfigureLimit(
        limit_id="sliding",
        max_requests=10,
        window_size_ms=window_ms
    )

    # Make 10 requests each
    for i in range(10):
        await cluster[0].AllowRequest(limit_id="fixed")
        await cluster[0].AllowRequest(limit_id="sliding")

    # Wait 1 second (half window)
    await asyncio.sleep(1.0)

    # Try more requests
    fixed_allowed = 0
    sliding_allowed = 0

    for i in range(10):
        if (await cluster[0].AllowRequest(limit_id="fixed")).allowed:
            fixed_allowed += 1
        if (await cluster[0].AllowRequest(limit_id="sliding")).allowed:
            sliding_allowed += 1

    # Fixed window: might allow many (if window rotated)
    # Sliding counter: should allow ~5 (weighted)
    print(f"Fixed allowed: {fixed_allowed}")
    print(f"Sliding allowed: {sliding_allowed}")

    # Sliding counter is more consistent
```

---

## Success Criteria

| Test | Criteria |
|------|----------|
| Basic Limiting | Enforces max_requests with weighted average |
| Sliding Behavior | Smooth transition between windows |
| Memory Efficiency | Only 2 counters per limit |
| Distributed | Consistent across nodes |

## Trade-offs vs Other Algorithms

| Algorithm | Memory | Accuracy | Complexity |
|-----------|--------|----------|------------|
| Fixed Window | O(1) | Low (boundary problem) | Simple |
| Sliding Log | O(n) | High (precise) | Medium |
| **Sliding Counter** | **O(1)** | **Medium-High** | **Medium** |
| Token Bucket | O(1) | High | Medium |
