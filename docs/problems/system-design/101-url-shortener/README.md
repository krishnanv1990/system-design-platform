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

#### 1. Short Code Generation
- **Algorithm:** Base62 encoding (a-z, A-Z, 0-9)
- **Length:** 7 characters = 62^7 = 3.5 trillion unique URLs
- **Generation Strategy:**
  - Option A: Counter-based with range allocation (recommended)
  - Option B: Random generation with collision detection
  - Option C: Hash-based (MD5/SHA256 truncated)

```python
# Base62 Encoding
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def encode_base62(num: int) -> str:
    if num == 0:
        return CHARSET[0]
    result = []
    while num:
        num, remainder = divmod(num, 62)
        result.append(CHARSET[remainder])
    return ''.join(reversed(result)).zfill(7)

def decode_base62(code: str) -> int:
    num = 0
    for char in code:
        num = num * 62 + CHARSET.index(char)
    return num
```

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
