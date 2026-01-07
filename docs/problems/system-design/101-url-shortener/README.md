# URL Shortener System Design

## Problem Overview

Design a URL shortening service like TinyURL or bit.ly that can handle 500 million URL shortenings per month with a 100:1 read to write ratio.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution Architecture

### High-Level Design

```
                                    ┌─────────────────┐
                                    │   CDN/Edge      │
                                    │   (CloudFlare)  │
                                    └────────┬────────┘
                                             │
                        ┌────────────────────┼────────────────────┐
                        │                    │                    │
                        ▼                    ▼                    ▼
                 ┌──────────┐         ┌──────────┐         ┌──────────┐
                 │   LB 1   │         │   LB 2   │         │   LB 3   │
                 └────┬─────┘         └────┬─────┘         └────┬─────┘
                      │                    │                    │
         ┌────────────┼────────────────────┼────────────────────┼────────────┐
         │            │                    │                    │            │
         ▼            ▼                    ▼                    ▼            ▼
    ┌─────────┐  ┌─────────┐         ┌─────────┐         ┌─────────┐  ┌─────────┐
    │ API 1   │  │ API 2   │   ...   │ API N   │   ...   │ API M   │  │ API K   │
    └────┬────┘  └────┬────┘         └────┬────┘         └────┬────┘  └────┬────┘
         │            │                    │                    │            │
         └────────────┴──────────┬─────────┴────────────────────┴────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
        ┌──────────┐       ┌──────────┐       ┌──────────┐
        │  Redis   │       │  Redis   │       │  Redis   │
        │ Cluster  │       │ Cluster  │       │ Cluster  │
        └──────────┘       └──────────┘       └──────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
   ┌───────────┐           ┌───────────┐           ┌───────────┐
   │ PostgreSQL│           │ PostgreSQL│           │ PostgreSQL│
   │  Shard 1  │           │  Shard 2  │           │  Shard N  │
   └───────────┘           └───────────┘           └───────────┘
```

### Core Components

#### 1. Key Generation Service (KGS) - Optimal Approach

The **Key Generation Service (KGS)** pre-generates unique short codes for O(1) retrieval with zero collision handling at request time.

**Why KGS is optimal:**
- **O(1) key retrieval** - No database lookups or collision checks during URL creation
- **Cryptographically secure** - Uses `secrets` module for unpredictable codes
- **Horizontally scalable** - Multiple KGS instances can generate keys independently
- **No hot spots** - Distributed key pools prevent contention

```python
import secrets
import redis.asyncio as redis
from typing import Optional
import asyncio

class KeyGenerationService:
    """
    Pre-generates unique, cryptographically secure short codes.
    Maintains a pool of available keys in Redis for O(1) retrieval.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        pool_name: str = "kgs:available_keys",
        used_pool: str = "kgs:used_keys",
        batch_size: int = 10000,
        min_pool_size: int = 5000
    ):
        self.redis = redis_client
        self.pool_name = pool_name
        self.used_pool = used_pool
        self.batch_size = batch_size
        self.min_pool_size = min_pool_size
        self._replenish_lock = asyncio.Lock()

    async def generate_batch(self) -> int:
        """
        Generate a batch of unique, cryptographically secure keys.
        Returns the number of keys added to the pool.
        """
        keys = set()
        attempts = 0
        max_attempts = self.batch_size * 2

        while len(keys) < self.batch_size and attempts < max_attempts:
            # Generate cryptographically secure 7-char code
            key = secrets.token_urlsafe(6)[:7]

            # Check not already used (rare with 62^7 space)
            if not await self.redis.sismember(self.used_pool, key):
                keys.add(key)
            attempts += 1

        if keys:
            # Atomic batch add to available pool
            await self.redis.sadd(self.pool_name, *keys)

        return len(keys)

    async def get_key(self) -> str:
        """
        Get a unique key from the pool. O(1) operation.
        Triggers async replenishment if pool is low.
        """
        # Atomic pop from available pool
        key = await self.redis.spop(self.pool_name)

        if key:
            key = key.decode() if isinstance(key, bytes) else key
            # Mark as used (for collision prevention)
            await self.redis.sadd(self.used_pool, key)

            # Check if replenishment needed (async, non-blocking)
            pool_size = await self.redis.scard(self.pool_name)
            if pool_size < self.min_pool_size:
                asyncio.create_task(self._replenish_if_needed())

            return key

        # Fallback: generate on-demand (should rarely happen)
        return await self._generate_single_key()

    async def _generate_single_key(self) -> str:
        """Generate a single key on-demand (fallback)."""
        while True:
            key = secrets.token_urlsafe(6)[:7]
            if not await self.redis.sismember(self.used_pool, key):
                await self.redis.sadd(self.used_pool, key)
                return key

    async def _replenish_if_needed(self):
        """Replenish pool if below threshold (with lock to prevent storms)."""
        if self._replenish_lock.locked():
            return  # Another replenishment in progress

        async with self._replenish_lock:
            pool_size = await self.redis.scard(self.pool_name)
            if pool_size < self.min_pool_size:
                await self.generate_batch()

    async def get_pool_stats(self) -> dict:
        """Get current pool statistics."""
        available = await self.redis.scard(self.pool_name)
        used = await self.redis.scard(self.used_pool)
        return {
            "available_keys": available,
            "used_keys": used,
            "pool_healthy": available >= self.min_pool_size
        }


# URL Shortener Service using KGS
class URLShortenerService:
    def __init__(self, kgs: KeyGenerationService, db, redis_client):
        self.kgs = kgs
        self.db = db
        self.redis = redis_client

    async def create_short_url(
        self,
        original_url: str,
        custom_alias: Optional[str] = None,
        expires_in: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> dict:
        """Create a shortened URL using KGS."""

        if custom_alias:
            # Check custom alias availability
            if await self.redis.exists(f"url:{custom_alias}"):
                raise ValueError("Custom alias already taken")
            short_code = custom_alias
        else:
            # Get pre-generated key from KGS - O(1)!
            short_code = await self.kgs.get_key()

        # Store URL mapping
        url_data = {
            "original_url": original_url,
            "short_code": short_code,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat() if expires_in else None
        }

        # Cache in Redis (primary store for reads)
        cache_ttl = expires_in or 86400 * 365  # 1 year default
        await self.redis.setex(
            f"url:{short_code}",
            cache_ttl,
            original_url
        )

        # Persist to database (async, for durability)
        await self.db.execute(
            """INSERT INTO urls (short_code, original_url, user_id, expires_at)
               VALUES ($1, $2, $3, $4)""",
            short_code, original_url, user_id, url_data.get("expires_at")
        )

        return {
            "short_code": short_code,
            "short_url": f"https://short.url/{short_code}",
            "original_url": original_url,
            "expires_at": url_data.get("expires_at")
        }
```

**Alternative Approaches (for comparison):**

| Approach | Pros | Cons |
|----------|------|------|
| **KGS (Recommended)** | O(1) retrieval, no collisions, secure | Requires pre-generation infrastructure |
| Counter + Base62 | Simple, sequential | Predictable URLs, requires distributed counter |
| Hash Truncation | Deterministic | Collision handling required, predictable |
| Random Generation | Simple | Collision checks on every request |

#### 2. Database Schema

```sql
-- URLs table (sharded by short_code hash)
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    click_count BIGINT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Sharding key: HASH(short_code) % num_shards
CREATE INDEX idx_urls_short_code ON urls(short_code);
CREATE INDEX idx_urls_user_id ON urls(user_id);
CREATE INDEX idx_urls_created_at ON urls(created_at);

-- Analytics table (time-series, partitioned by day)
CREATE TABLE url_analytics (
    id BIGSERIAL,
    short_code VARCHAR(10) NOT NULL,
    accessed_at TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    referer TEXT,
    country VARCHAR(2),
    device_type VARCHAR(20)
) PARTITION BY RANGE (accessed_at);
```

#### 3. API Design

```yaml
openapi: 3.0.0
paths:
  /api/v1/shorten:
    post:
      summary: Create short URL
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                url: { type: string, format: uri }
                custom_alias: { type: string, maxLength: 10 }
                expires_in: { type: integer, description: "TTL in seconds" }
      responses:
        201:
          content:
            application/json:
              schema:
                type: object
                properties:
                  short_url: { type: string }
                  short_code: { type: string }
                  expires_at: { type: string, format: date-time }

  /{short_code}:
    get:
      summary: Redirect to original URL
      parameters:
        - name: short_code
          in: path
          required: true
          schema: { type: string }
      responses:
        301:
          description: Permanent redirect
        404:
          description: URL not found or expired
```

#### 4. Caching Strategy

- **Cache-Aside Pattern:** Check Redis first, fallback to DB
- **TTL:** 24 hours for frequently accessed, 1 hour for others
- **Eviction:** LRU with 80% memory threshold
- **Hot Key Protection:** Local in-memory cache for top 1000 URLs

```python
async def get_original_url(short_code: str) -> str:
    # L1: Local cache (in-memory, top 1000)
    if url := local_cache.get(short_code):
        return url

    # L2: Distributed cache (Redis)
    if url := await redis.get(f"url:{short_code}"):
        local_cache.set(short_code, url)
        return url

    # L3: Database
    url = await db.fetch_one(
        "SELECT original_url FROM urls WHERE short_code = $1 AND is_active",
        short_code
    )
    if url:
        await redis.setex(f"url:{short_code}", 86400, url)
        local_cache.set(short_code, url)
    return url
```

#### 5. Rate Limiting

- **Anonymous:** 10 URLs/hour per IP
- **Authenticated:** 100 URLs/hour per user
- **Algorithm:** Token bucket with Redis

---

## Platform Deployment

### How the Platform Deploys This Solution

1. **Submission Validation**
   - AI validates the architecture design (components, API spec, schema)
   - Checks for required elements: database, caching, load balancer
   - Validates sharding and replication strategies

2. **Infrastructure Generation**
   - Generates Terraform/Cloud Run configuration
   - Sets up PostgreSQL with read replicas
   - Configures Redis cluster with persistence
   - Deploys API servers with auto-scaling

3. **Deployment Pipeline**
   ```
   User Submission → AI Validation → Terraform Generation →
   Cloud Build → Cloud Run Deployment → Health Checks → Testing
   ```

4. **Infrastructure Components Deployed**
   - **Compute:** Cloud Run services (auto-scaling 0-100 instances)
   - **Database:** Cloud SQL PostgreSQL (HA configuration)
   - **Cache:** Memorystore Redis (3-node cluster)
   - **Load Balancer:** Cloud Load Balancing with CDN
   - **Monitoring:** Cloud Monitoring + Logging

### Deployment Configuration

```hcl
# Generated Terraform (simplified)
resource "google_cloud_run_service" "url_shortener" {
  name     = "url-shortener-${var.submission_id}"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/${var.project}/url-shortener:${var.version}"
        resources {
          limits = {
            cpu    = "2"
            memory = "1Gi"
          }
        }
        env {
          name  = "DATABASE_URL"
          value = google_sql_database_instance.main.connection_name
        }
        env {
          name  = "REDIS_URL"
          value = google_redis_instance.cache.host
        }
      }
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "100"
      }
    }
  }
}
```

---

## Realistic Testing

### 1. Functional Testing (Automated)

The platform runs these tests against your deployed solution:

```python
# Test: Create and retrieve short URL
async def test_create_and_retrieve():
    # Create short URL
    response = await client.post("/api/v1/shorten", json={
        "url": "https://example.com/very/long/path"
    })
    assert response.status_code == 201
    short_code = response.json()["short_code"]

    # Retrieve and verify redirect
    redirect = await client.get(f"/{short_code}", follow_redirects=False)
    assert redirect.status_code == 301
    assert redirect.headers["Location"] == "https://example.com/very/long/path"

# Test: Custom alias
async def test_custom_alias():
    response = await client.post("/api/v1/shorten", json={
        "url": "https://example.com",
        "custom_alias": "mylink"
    })
    assert response.status_code == 201
    assert response.json()["short_code"] == "mylink"

# Test: URL expiration
async def test_expiration():
    response = await client.post("/api/v1/shorten", json={
        "url": "https://example.com",
        "expires_in": 1  # 1 second
    })
    short_code = response.json()["short_code"]
    await asyncio.sleep(2)
    redirect = await client.get(f"/{short_code}")
    assert redirect.status_code == 404

# Test: Collision handling
async def test_no_collisions():
    codes = set()
    for _ in range(10000):
        response = await client.post("/api/v1/shorten", json={
            "url": f"https://example.com/{uuid.uuid4()}"
        })
        code = response.json()["short_code"]
        assert code not in codes
        codes.add(code)
```

### 2. Performance Testing (Locust)

Deploy Locust workers alongside your solution to generate realistic load:

```python
# locustfile.py - deployed in the same GCP project
from locust import HttpUser, task, between

class URLShortenerUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        # Pre-create some URLs to read
        self.short_codes = []
        for i in range(100):
            response = self.client.post("/api/v1/shorten", json={
                "url": f"https://example.com/page/{i}"
            })
            if response.status_code == 201:
                self.short_codes.append(response.json()["short_code"])

    @task(100)  # 100:1 read-to-write ratio
    def read_url(self):
        if self.short_codes:
            code = random.choice(self.short_codes)
            self.client.get(f"/{code}", name="/[short_code]")

    @task(1)
    def create_url(self):
        self.client.post("/api/v1/shorten", json={
            "url": f"https://example.com/{uuid.uuid4()}"
        })
```

**Performance Targets:**
- **p50 Latency:** < 10ms for reads
- **p99 Latency:** < 100ms for reads
- **Throughput:** > 10,000 RPS for reads
- **Error Rate:** < 0.1%

### 3. Chaos Testing (Real Infrastructure)

The platform injects real failures into your deployed infrastructure:

```python
# Chaos scenarios executed by the platform
class ChaosTests:
    async def test_database_failover(self):
        """Simulate primary database failure"""
        # Platform triggers Cloud SQL failover
        await gcp.trigger_sql_failover(instance_id)

        # Verify service continues with cache
        for _ in range(100):
            response = await client.get("/abc123")
            assert response.status_code in [301, 503]  # OK or graceful degradation

        # Verify recovery after failover completes
        await asyncio.sleep(60)
        response = await client.get("/abc123")
        assert response.status_code == 301

    async def test_cache_failure(self):
        """Simulate Redis cluster failure"""
        # Platform stops Redis instances
        await gcp.stop_redis_instance(instance_id)

        # Verify fallback to database
        response = await client.get("/abc123")
        assert response.status_code == 301

        # Verify latency degradation is graceful
        latencies = []
        for _ in range(100):
            start = time.time()
            await client.get("/abc123")
            latencies.append(time.time() - start)

        assert statistics.mean(latencies) < 0.5  # < 500ms even without cache

    async def test_traffic_spike(self):
        """Simulate viral link traffic spike"""
        # Generate 100x normal traffic to one URL
        async with aiohttp.ClientSession() as session:
            tasks = [
                session.get(f"{base_url}/viral123")
                for _ in range(10000)
            ]
            responses = await asyncio.gather(*tasks)

        success_rate = sum(1 for r in responses if r.status == 301) / len(responses)
        assert success_rate > 0.99  # 99% success under spike
```

### 4. Manual Testing Checklist

For realistic end-to-end validation:

```bash
# 1. Create a short URL
curl -X POST https://your-deployment.run.app/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com/search?q=test"}'

# 2. Test the redirect
curl -I https://your-deployment.run.app/abc1234

# 3. Test with custom alias
curl -X POST https://your-deployment.run.app/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "custom_alias": "test123"}'

# 4. Load test with hey
hey -n 10000 -c 100 https://your-deployment.run.app/abc1234

# 5. Check metrics
gcloud monitoring dashboards list --filter="url-shortener"
```

### 5. Integration with External Services

For realistic testing, the platform can:

```yaml
# Test configuration (platform-managed)
external_integrations:
  analytics:
    enabled: true
    verify: "click events are logged to BigQuery"

  geolocation:
    enabled: true
    mock_service: "https://ip-api.com/json"
    verify: "country codes are correctly resolved"

  rate_limiting:
    enabled: true
    test_scenarios:
      - exceed_limit_anonymous
      - exceed_limit_authenticated
      - distributed_rate_limit_sync
```

---

## Success Criteria

| Metric | Target | How Verified |
|--------|--------|--------------|
| Read Latency (p50) | < 10ms | Performance tests |
| Read Latency (p99) | < 100ms | Performance tests |
| Write Latency (p50) | < 50ms | Performance tests |
| Throughput | > 10K RPS | Load tests |
| Availability | 99.9% | Chaos tests |
| Cache Hit Rate | > 95% | Metrics dashboard |
| Error Rate | < 0.1% | All test types |

---

## Common Pitfalls

1. **Single point of failure:** No database replication
2. **Hot key problem:** Viral URLs overwhelming cache
3. **Collision handling:** Not checking for existing codes
4. **Missing rate limiting:** Vulnerable to abuse
5. **No TTL on cache:** Memory exhaustion
6. **Synchronous analytics:** Blocking redirects for logging
