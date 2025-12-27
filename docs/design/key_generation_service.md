# Key Generation Service (KGS) Architecture

## Overview

The Key Generation Service (KGS) is an advanced approach for URL shortening that pre-generates unique short codes in advance, eliminating the need to generate codes at request time. This significantly improves write latency and ensures uniqueness without expensive database checks.

## Current Design vs KGS Design

### Current Design (Hash-Based)

```
┌─────────┐     ┌─────────────┐     ┌──────────┐
│ Client  │────▶│ URL Service │────▶│ Database │
└─────────┘     │ (generate   │     │ (check   │
                │  hash/code) │     │  unique) │
                └─────────────┘     └──────────┘
```

**Pros:**
- Simple implementation
- No additional infrastructure

**Cons:**
- Hash collision handling required
- Database lookup on every write
- Potential for race conditions at scale

### KGS Design

```
┌─────────────────────────────────────────────────────────────┐
│                    KEY GENERATION SERVICE                    │
│  ┌───────────────┐    ┌──────────────────────────────────┐  │
│  │ Key Generator │───▶│ Pre-generated Keys Pool          │  │
│  │ (background)  │    │ ┌────────┐ ┌────────┐ ┌────────┐│  │
│  └───────────────┘    │ │unused  │ │unused  │ │unused  ││  │
│                       │ │ key1   │ │ key2   │ │ key3   ││  │
│                       │ └────────┘ └────────┘ └────────┘│  │
│                       └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼ fetch key
┌─────────┐     ┌─────────────────────────┐     ┌──────────┐
│ Client  │────▶│ URL Service             │────▶│ Database │
└─────────┘     │ (just store URL+key)    │     │ (no dupe │
                │                         │     │  check)  │
                └─────────────────────────┘     └──────────┘
```

## KGS Architecture Detail

### Components

```
┌──────────────────────────────────────────────────────────────────────┐
│                        KEY GENERATION SERVICE                         │
│                                                                        │
│  ┌─────────────────┐      ┌─────────────────────────────────────┐    │
│  │ Key Generator   │      │        Redis Cluster                 │    │
│  │ (Worker Pool)   │─────▶│  ┌────────────┐ ┌────────────┐      │    │
│  │                 │      │  │ unused:keys│ │ used:keys  │      │    │
│  │ - Generates     │      │  │ (SET)      │ │ (SET)      │      │    │
│  │   base62 codes  │      │  │            │ │            │      │    │
│  │ - Batch insert  │      │  │ abc123     │ │ xyz789     │      │    │
│  │ - Maintains     │      │  │ def456     │ │ ...        │      │    │
│  │   minimum pool  │      │  │ ...        │ │            │      │    │
│  └─────────────────┘      │  └────────────┘ └────────────┘      │    │
│                           └─────────────────────────────────────┘    │
│                                                                        │
│  ┌─────────────────┐      ┌─────────────────────────────────────┐    │
│  │ Key Allocator   │      │        PostgreSQL                    │    │
│  │ (API)           │─────▶│  ┌────────────────────────────────┐ │    │
│  │                 │      │  │ keys table                      │ │    │
│  │ GET /key        │      │  │ - key_id (PK)                   │ │    │
│  │ POST /keys/bulk │      │  │ - short_code (unique)           │ │    │
│  │ GET /stats      │      │  │ - status (unused/used/reserved) │ │    │
│  │                 │      │  │ - allocated_at                  │ │    │
│  └─────────────────┘      │  │ - allocated_to_service          │ │    │
│                           │  └────────────────────────────────┘ │    │
│                           └─────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Key Generation (Background Process)
   ┌────────────────────────────────────────────────────────┐
   │                                                         │
   │  [Generator] ─── generates 10K keys ───▶ [Redis SADD]  │
   │      │                                        │         │
   │      │         if pool < threshold            │         │
   │      └───────────────────────────────────────▶│         │
   │                                               │         │
   │  [PostgreSQL] ◀── persist for recovery ──────┘         │
   │                                                         │
   └────────────────────────────────────────────────────────┘

2. Key Allocation (Request Time)
   ┌────────────────────────────────────────────────────────┐
   │                                                         │
   │  [URL Service] ── SPOP ──▶ [Redis unused:keys]         │
   │       │              │                                  │
   │       │              └──── key: "abc123"                │
   │       │                                                 │
   │       └── SADD ──▶ [Redis used:keys] ── "abc123"       │
   │                                                         │
   └────────────────────────────────────────────────────────┘
```

## Database Schema

### Keys Table (PostgreSQL)

```sql
CREATE TABLE kgs_keys (
    key_id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(8) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'unused',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    allocated_at TIMESTAMP WITH TIME ZONE,
    allocated_to_service VARCHAR(100),
    allocated_to_url_id BIGINT
);

-- Index for fast unused key retrieval
CREATE INDEX idx_kgs_keys_unused ON kgs_keys(status)
    WHERE status = 'unused';

-- Partition by status for better performance
CREATE TABLE kgs_keys_unused PARTITION OF kgs_keys
    FOR VALUES IN ('unused');
CREATE TABLE kgs_keys_used PARTITION OF kgs_keys
    FOR VALUES IN ('used');
```

### URLs Table (with KGS)

```sql
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(8) NOT NULL UNIQUE,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    click_count BIGINT DEFAULT 0,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- No need to generate short_code - comes from KGS
```

## Implementation

### Key Generator (Python)

```python
import redis
import string
import random
from typing import List
import asyncio

class KeyGenerator:
    CHARSET = string.ascii_lowercase + string.ascii_uppercase + string.digits
    KEY_LENGTH = 7  # 62^7 = 3.5 trillion unique keys

    def __init__(self, redis_client: redis.Redis, min_pool_size: int = 100000):
        self.redis = redis_client
        self.min_pool_size = min_pool_size
        self.unused_key = "kgs:unused"
        self.used_key = "kgs:used"

    def generate_key(self) -> str:
        """Generate a single random key."""
        return ''.join(random.choices(self.CHARSET, k=self.KEY_LENGTH))

    def generate_batch(self, count: int = 10000) -> List[str]:
        """Generate a batch of unique keys."""
        keys = set()
        while len(keys) < count:
            keys.add(self.generate_key())
        return list(keys)

    async def maintain_pool(self):
        """Background task to maintain minimum pool size."""
        while True:
            pool_size = self.redis.scard(self.unused_key)

            if pool_size < self.min_pool_size:
                needed = self.min_pool_size - pool_size + 50000  # Buffer
                keys = self.generate_batch(needed)

                # Filter out any keys already used
                pipeline = self.redis.pipeline()
                for key in keys:
                    pipeline.sismember(self.used_key, key)
                used_results = pipeline.execute()

                new_keys = [k for k, used in zip(keys, used_results) if not used]

                if new_keys:
                    self.redis.sadd(self.unused_key, *new_keys)

            await asyncio.sleep(60)  # Check every minute


class KeyAllocator:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.unused_key = "kgs:unused"
        self.used_key = "kgs:used"

    def allocate_key(self) -> str:
        """Atomically allocate a key from the pool."""
        # SPOP atomically removes and returns a random member
        key = self.redis.spop(self.unused_key)

        if key is None:
            raise Exception("Key pool exhausted!")

        # Mark as used
        self.redis.sadd(self.used_key, key)

        return key.decode() if isinstance(key, bytes) else key

    def allocate_batch(self, count: int) -> List[str]:
        """Allocate multiple keys at once."""
        keys = self.redis.spop(self.unused_key, count)

        if keys:
            self.redis.sadd(self.used_key, *keys)
            return [k.decode() if isinstance(k, bytes) else k for k in keys]

        return []

    def return_key(self, key: str):
        """Return a key to the unused pool (for rollback scenarios)."""
        self.redis.srem(self.used_key, key)
        self.redis.sadd(self.unused_key, key)
```

### URL Service with KGS

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis

app = FastAPI()
redis_client = redis.Redis(host='redis', port=6379, db=0)
key_allocator = KeyAllocator(redis_client)

class URLCreate(BaseModel):
    original_url: str
    custom_code: str = None
    expires_in_hours: int = None

@app.post("/api/v1/urls")
async def create_short_url(request: URLCreate):
    if request.custom_code:
        # Use custom code if provided
        short_code = request.custom_code
        # Check if custom code is available
        if redis_client.sismember("kgs:used", short_code):
            raise HTTPException(status_code=409, detail="Custom code already in use")
    else:
        # Allocate from KGS - O(1) operation!
        short_code = key_allocator.allocate_key()

    # Store URL with pre-allocated key
    url_data = {
        "original_url": request.original_url,
        "short_code": short_code,
        "created_at": datetime.utcnow().isoformat()
    }

    # Store in database
    await db.urls.insert_one(url_data)

    return {
        "short_code": short_code,
        "short_url": f"https://short.url/{short_code}",
        "original_url": request.original_url
    }
```

## Scaling Considerations

### For 1 Billion URLs

```
Key Space Calculation:
- 7-character base62 keys: 62^7 = 3.5 trillion combinations
- With 1 billion URLs: 0.03% utilization
- Collision probability: virtually zero

Pool Sizing:
- Peak writes: 10,000/second
- Pool buffer: 10 minutes worth = 6 million keys
- Min pool size: 10 million unused keys

Redis Memory:
- Each key: ~10 bytes (7 chars + overhead)
- 10 million keys: ~100 MB
- Used keys set: grows over time, can be archived
```

### Multi-Region Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                     GLOBAL KGS ARCHITECTURE                      │
│                                                                   │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │ KGS us-east     │     │ KGS us-west     │                    │
│  │ Range: a-m      │     │ Range: n-z      │                    │
│  │ (prefix-based)  │     │ (prefix-based)  │                    │
│  └────────┬────────┘     └────────┬────────┘                    │
│           │                       │                              │
│           └───────────┬───────────┘                              │
│                       │                                          │
│                       ▼                                          │
│           ┌───────────────────────┐                              │
│           │ Global Key Registry   │                              │
│           │ (eventual consistency)│                              │
│           └───────────────────────┘                              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Range-Based Key Allocation

```python
class RangeBasedKGS:
    """
    Each region gets a prefix to avoid cross-region conflicts.
    """
    REGION_PREFIXES = {
        'us-east-1': 'a',
        'us-west-2': 'b',
        'eu-west-1': 'c',
        'ap-south-1': 'd',
    }

    def __init__(self, region: str):
        self.prefix = self.REGION_PREFIXES[region]
        self.counter = 0

    def generate_key(self) -> str:
        # Prefix + 6 random chars
        suffix = ''.join(random.choices(self.CHARSET, k=6))
        return f"{self.prefix}{suffix}"
```

## Comparison: KGS vs Hash-Based

| Aspect | Hash-Based | KGS |
|--------|-----------|-----|
| Write Latency | ~5-10ms (hash + db check) | ~1-2ms (just SPOP) |
| Uniqueness | Requires DB constraint | Guaranteed by pool |
| Race Conditions | Possible at high scale | Eliminated |
| Cold Start | None | Need to pre-populate |
| Complexity | Low | Medium |
| Infrastructure | Just DB | Redis + Generator |
| Recovery | Simple | Need pool restoration |
| Custom Codes | Easy | Requires validation |

## Failure Scenarios

### Redis Failure
```
1. Fallback to PostgreSQL keys table
2. Allocate from unused partition
3. Mark as used with UPDATE
4. Slower but functional
```

### Key Pool Exhaustion
```
1. Alert when pool < 10% threshold
2. Emergency key generation
3. Rate limit writes if needed
4. Never reject requests silently
```

### Data Recovery
```
1. Keys in Redis are also persisted to PostgreSQL
2. On Redis restart:
   - Load unused keys from PostgreSQL
   - Rebuild Redis sets
3. Use Redis AOF persistence for faster recovery
```

## Monitoring

### Key Metrics

```yaml
# Prometheus metrics
kgs_pool_size:
  type: gauge
  description: "Number of unused keys in pool"
  labels: [region]

kgs_allocation_rate:
  type: counter
  description: "Keys allocated per second"
  labels: [region, status]

kgs_generation_rate:
  type: counter
  description: "Keys generated per second"
  labels: [region]

kgs_pool_exhaustion_risk:
  type: gauge
  description: "Minutes until pool exhaustion at current rate"
  labels: [region]
```

### Alerts

```yaml
- alert: KGSPoolLow
  expr: kgs_pool_size < 1000000
  for: 5m
  annotations:
    summary: "KGS pool running low"

- alert: KGSPoolCritical
  expr: kgs_pool_size < 100000
  for: 1m
  annotations:
    summary: "KGS pool critically low - immediate action required"
```

## Conclusion

The KGS approach is recommended for:
- High-write throughput (>1000 URLs/second)
- Strict latency requirements (<5ms p99)
- Systems that need guaranteed uniqueness
- Multi-region deployments

The simpler hash-based approach works for:
- Lower scale (<100 URLs/second)
- Simpler infrastructure requirements
- Single-region deployments
