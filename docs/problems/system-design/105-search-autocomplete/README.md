# Search Autocomplete System Design

## Problem Overview

Design a real-time search autocomplete/typeahead system that returns top suggestions based on prefix with sub-100ms latency, supporting 5 billion searches per day.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
                                    ┌─────────────────────────────────┐
                                    │           CDN/Edge              │
                                    │    (Cache popular prefixes)     │
                                    └───────────────┬─────────────────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              │                     │                     │
                              ▼                     ▼                     ▼
                        ┌───────────┐         ┌───────────┐         ┌───────────┐
                        │    LB     │         │    LB     │         │    LB     │
                        └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
                              │                     │                     │
         ┌────────────────────┼─────────────────────┼─────────────────────┼────────────────────┐
         │                    ▼                     ▼                     ▼                    │
         │              ┌───────────┐         ┌───────────┐         ┌───────────┐              │
         │              │ Suggest   │         │ Suggest   │         │ Suggest   │              │
         │              │ Service   │         │ Service   │         │ Service   │              │
         │              └─────┬─────┘         └─────┬─────┘         └─────┬─────┘              │
         │                    │                     │                     │                    │
         │              ┌─────▼─────────────────────▼─────────────────────▼─────┐              │
         │              │                  Trie Cluster                         │              │
         │              │  ┌─────────┐  ┌─────────┐  ┌─────────┐               │              │
         │              │  │ Trie    │  │ Trie    │  │ Trie    │               │              │
         │              │  │ Shard 1 │  │ Shard 2 │  │ Shard N │               │              │
         │              │  └─────────┘  └─────────┘  └─────────┘               │              │
         │              └──────────────────────────────────────────────────────┘              │
         │                                                                                     │
         │  ┌─────────────────────────────────────────────────────────────────────────────┐   │
         │  │                        Ranking & ML Service                                  │   │
         │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │   │
         │  │  │ Popularity      │  │ Personalization │  │ Trending        │              │   │
         │  │  │ Ranker          │  │ ML Model        │  │ Detector        │              │   │
         │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘              │   │
         │  └─────────────────────────────────────────────────────────────────────────────┘   │
         │                                                                                     │
         │  ┌─────────────────────────────────────────────────────────────────────────────┐   │
         │  │                        Data Pipeline (Offline)                               │   │
         │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │   │
         │  │  │ Query Log       │─▶│ Aggregation     │─▶│ Trie Builder    │              │   │
         │  │  │ Collector       │  │ (Dataflow)      │  │                 │              │   │
         │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘              │   │
         │  └─────────────────────────────────────────────────────────────────────────────┘   │
         │                                                                                     │
         │                              Autocomplete System                                    │
         └─────────────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Trie Data Structure

```python
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import heapq

@dataclass
class TrieNode:
    """Node in the autocomplete trie."""
    children: Dict[str, 'TrieNode'] = field(default_factory=dict)
    is_end: bool = False
    frequency: int = 0
    # Top-k suggestions cached at this node
    top_suggestions: List[Tuple[int, str]] = field(default_factory=list)


class AutocompleteTrie:
    """
    Trie optimized for autocomplete.
    Caches top-k suggestions at each node for O(1) lookup.
    """

    def __init__(self, k: int = 10):
        self.root = TrieNode()
        self.k = k

    def insert(self, word: str, frequency: int = 1):
        """Insert a word with its frequency."""
        node = self.root
        prefix = ""

        for char in word.lower():
            prefix += char
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

            # Update top-k at this prefix
            self._update_top_k(node, word, frequency)

        node.is_end = True
        node.frequency = frequency

    def _update_top_k(self, node: TrieNode, word: str, freq: int):
        """Maintain top-k suggestions at a node."""
        # Check if word already in suggestions
        for i, (f, w) in enumerate(node.top_suggestions):
            if w == word:
                node.top_suggestions[i] = (freq, word)
                node.top_suggestions.sort(reverse=True, key=lambda x: x[0])
                return

        # Add to heap
        if len(node.top_suggestions) < self.k:
            node.top_suggestions.append((freq, word))
            node.top_suggestions.sort(reverse=True, key=lambda x: x[0])
        elif freq > node.top_suggestions[-1][0]:
            node.top_suggestions[-1] = (freq, word)
            node.top_suggestions.sort(reverse=True, key=lambda x: x[0])

    def suggest(self, prefix: str, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top suggestions for a prefix. O(prefix_length) lookup."""
        node = self.root
        prefix = prefix.lower()

        # Navigate to prefix node
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]

        # Return cached top-k
        return [(w, f) for f, w in node.top_suggestions[:limit]]

    def serialize(self) -> bytes:
        """Serialize trie for storage/transfer."""
        import pickle
        return pickle.dumps(self.root)

    @classmethod
    def deserialize(cls, data: bytes, k: int = 10) -> 'AutocompleteTrie':
        """Deserialize trie from bytes."""
        import pickle
        trie = cls(k=k)
        trie.root = pickle.loads(data)
        return trie
```

#### 2. Sharded Trie Service

```python
import hashlib
from typing import List

class ShardedTrieService:
    """
    Distributes trie across multiple shards based on prefix.
    Each shard handles a subset of the keyspace.
    """

    def __init__(self, num_shards: int):
        self.num_shards = num_shards
        self.shards: Dict[int, AutocompleteTrie] = {
            i: AutocompleteTrie() for i in range(num_shards)
        }

    def _get_shard(self, prefix: str) -> int:
        """Determine shard based on first character."""
        if not prefix:
            return 0
        # Simple range-based sharding by first char
        first_char = prefix[0].lower()
        char_code = ord(first_char) if first_char.isalpha() else 0
        return char_code % self.num_shards

    async def suggest(
        self,
        prefix: str,
        limit: int = 10,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Get suggestions with optional personalization.
        """
        if len(prefix) < 1:
            return []

        shard_id = self._get_shard(prefix)
        trie = self.shards[shard_id]

        # Get base suggestions from trie
        base_suggestions = trie.suggest(prefix, limit=limit * 2)

        # Apply ranking
        ranked = await self._rank_suggestions(
            base_suggestions,
            prefix,
            user_id
        )

        return ranked[:limit]

    async def _rank_suggestions(
        self,
        suggestions: List[Tuple[str, int]],
        prefix: str,
        user_id: Optional[str]
    ) -> List[Dict]:
        """
        Re-rank suggestions using multiple signals:
        - Base frequency
        - Recency/trending
        - Personalization
        - Prefix match quality
        """
        results = []

        for word, freq in suggestions:
            score = freq

            # Boost exact prefix matches
            if word.lower().startswith(prefix.lower()):
                score *= 1.2

            # Boost trending (from cache)
            trending_boost = await self._get_trending_boost(word)
            score *= (1 + trending_boost)

            # Personalization (if user_id provided)
            if user_id:
                personal_boost = await self._get_personal_boost(word, user_id)
                score *= (1 + personal_boost)

            results.append({
                "suggestion": word,
                "score": score,
                "frequency": freq
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results
```

#### 3. Real-Time Trending Detection

```python
from collections import defaultdict
import time

class TrendingDetector:
    """
    Detects trending queries using sliding window.
    Updates in near real-time from search logs.
    """

    def __init__(self, window_minutes: int = 60):
        self.window_seconds = window_minutes * 60
        self.query_counts: Dict[str, List[float]] = defaultdict(list)
        self.baseline_counts: Dict[str, float] = {}

    def record_query(self, query: str):
        """Record a query for trending analysis."""
        now = time.time()
        normalized = query.lower().strip()
        self.query_counts[normalized].append(now)

        # Prune old entries
        self._prune_old_entries(normalized)

    def _prune_old_entries(self, query: str):
        cutoff = time.time() - self.window_seconds
        self.query_counts[query] = [
            ts for ts in self.query_counts[query]
            if ts > cutoff
        ]

    def get_trending_score(self, query: str) -> float:
        """
        Calculate trending score.
        Score > 1 means query is trending above baseline.
        """
        normalized = query.lower().strip()
        current_count = len(self.query_counts.get(normalized, []))
        baseline = self.baseline_counts.get(normalized, 1)

        return current_count / baseline if baseline > 0 else 0

    def get_top_trending(self, limit: int = 100) -> List[Tuple[str, float]]:
        """Get top trending queries."""
        scores = [
            (query, self.get_trending_score(query))
            for query in self.query_counts.keys()
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]

    async def update_baselines(self):
        """
        Update baseline counts from historical data.
        Run periodically (e.g., hourly).
        """
        # Fetch from data warehouse
        historical = await self._fetch_historical_averages()
        self.baseline_counts.update(historical)
```

#### 4. Query Log Processing Pipeline

```python
# Apache Beam / Dataflow pipeline
import apache_beam as beam
from apache_beam.transforms import window

class AggregateQueries(beam.DoFn):
    def process(self, element, window=beam.DoFn.WindowParam):
        query, count = element
        yield {
            "query": query,
            "count": count,
            "window_start": window.start.to_utc_datetime().isoformat(),
            "window_end": window.end.to_utc_datetime().isoformat()
        }

def create_aggregation_pipeline(input_topic, output_table):
    """
    Pipeline to aggregate query logs for trie updates.
    Runs continuously on Dataflow.
    """
    with beam.Pipeline() as p:
        (p
         | "Read from Pub/Sub" >> beam.io.ReadFromPubSub(topic=input_topic)
         | "Parse JSON" >> beam.Map(json.loads)
         | "Extract Query" >> beam.Map(lambda x: x["query"].lower().strip())
         | "Window" >> beam.WindowInto(window.FixedWindows(3600))  # 1 hour
         | "Count" >> beam.combiners.Count.PerElement()
         | "Format" >> beam.ParDo(AggregateQueries())
         | "Write to BigQuery" >> beam.io.WriteToBigQuery(
             output_table,
             schema="query:STRING,count:INTEGER,window_start:TIMESTAMP,window_end:TIMESTAMP"
         ))
```

### Database Schema

```sql
-- Aggregated query frequencies
CREATE TABLE query_frequencies (
    query TEXT PRIMARY KEY,
    total_count BIGINT NOT NULL,
    daily_count BIGINT,
    weekly_count BIGINT,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Trending queries (materialized view, refreshed frequently)
CREATE MATERIALIZED VIEW trending_queries AS
SELECT
    query,
    current_hour_count,
    previous_hour_count,
    CASE WHEN previous_hour_count > 0
         THEN current_hour_count::float / previous_hour_count
         ELSE current_hour_count
    END as trending_score
FROM (
    SELECT
        query,
        SUM(CASE WHEN window_start > NOW() - INTERVAL '1 hour' THEN count ELSE 0 END) as current_hour_count,
        SUM(CASE WHEN window_start BETWEEN NOW() - INTERVAL '2 hours' AND NOW() - INTERVAL '1 hour'
            THEN count ELSE 0 END) as previous_hour_count
    FROM query_aggregations
    GROUP BY query
) t
WHERE current_hour_count > 100
ORDER BY trending_score DESC
LIMIT 10000;

-- User search history for personalization
CREATE TABLE user_search_history (
    user_id BIGINT,
    query TEXT,
    search_count INTEGER DEFAULT 1,
    last_searched TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, query)
);
```

### API Design

```yaml
openapi: 3.0.0
paths:
  /api/v1/suggest:
    get:
      summary: Get autocomplete suggestions
      parameters:
        - name: q
          in: query
          required: true
          description: Search prefix
          schema: { type: string, minLength: 1 }
        - name: limit
          in: query
          schema: { type: integer, default: 10, max: 20 }
        - name: user_id
          in: query
          description: User ID for personalization
          schema: { type: string }
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  suggestions:
                    type: array
                    items:
                      type: object
                      properties:
                        text: { type: string }
                        score: { type: number }
                        type: { enum: [query, trending, personal] }
```

---

## Platform Deployment

### Deployment Architecture

The platform deploys the autocomplete system as follows:

1. **Trie Shards:** Deployed as StatefulSet on GKE with memory-optimized nodes
2. **Suggestion API:** Cloud Run services for auto-scaling
3. **Data Pipeline:** Dataflow jobs for query aggregation
4. **Caching:** Redis for hot prefixes, CDN edge caching

```hcl
# GKE deployment for trie shards
resource "kubernetes_stateful_set" "trie_shards" {
  metadata {
    name = "autocomplete-trie"
  }
  spec {
    replicas = 16  # 16 shards
    template {
      spec {
        container {
          name  = "trie"
          image = "gcr.io/${var.project}/autocomplete-trie:${var.version}"
          resources {
            limits = {
              memory = "32Gi"  # In-memory trie
              cpu    = "4"
            }
          }
        }
      }
    }
  }
}
```

---

## Realistic Testing

### 1. Functional Tests

```python
class TestAutocomplete:
    async def test_basic_suggestions(self, client):
        """Test basic prefix matching."""
        # Seed data
        await seed_queries([
            ("facebook", 1000000),
            ("face recognition", 500000),
            ("facetime", 800000),
            ("facebook login", 900000)
        ])

        response = await client.get("/api/v1/suggest?q=face")
        suggestions = response.json()["suggestions"]

        assert len(suggestions) >= 4
        assert suggestions[0]["text"] == "facebook"  # Highest frequency

    async def test_case_insensitive(self, client):
        """Test case insensitive matching."""
        r1 = await client.get("/api/v1/suggest?q=Face")
        r2 = await client.get("/api/v1/suggest?q=face")
        r3 = await client.get("/api/v1/suggest?q=FACE")

        assert r1.json() == r2.json() == r3.json()

    async def test_personalization(self, client):
        """Test personalized suggestions."""
        user_id = "user123"

        # Record user's search history
        await record_user_search(user_id, "python tutorial")
        await record_user_search(user_id, "python tutorial")
        await record_user_search(user_id, "python tutorial")

        # Get suggestions
        response = await client.get(f"/api/v1/suggest?q=pyt&user_id={user_id}")
        suggestions = response.json()["suggestions"]

        # Personal history should be boosted
        personal = [s for s in suggestions if s.get("type") == "personal"]
        assert any("python tutorial" in s["text"] for s in personal)

    async def test_trending_boost(self, client):
        """Test that trending queries are boosted."""
        # Simulate trending query
        for _ in range(10000):
            await record_query("breaking news event")

        response = await client.get("/api/v1/suggest?q=break")
        suggestions = response.json()["suggestions"]

        trending = [s for s in suggestions if s.get("type") == "trending"]
        assert len(trending) > 0

    async def test_latency(self, client):
        """Test response latency."""
        latencies = []
        for _ in range(100):
            start = time.time()
            await client.get("/api/v1/suggest?q=test")
            latencies.append(time.time() - start)

        p50 = sorted(latencies)[50]
        p99 = sorted(latencies)[99]

        assert p50 < 0.05  # 50ms
        assert p99 < 0.1   # 100ms
```

### 2. Load Testing

```python
from locust import HttpUser, task, between

class AutocompleteUser(HttpUser):
    wait_time = between(0.01, 0.05)  # Fast keystrokes

    def on_start(self):
        self.queries = [
            "facebook", "google", "amazon", "apple", "microsoft",
            "how to", "what is", "where to", "best", "top 10"
        ]

    @task
    def type_ahead(self):
        """Simulate typing a query."""
        query = random.choice(self.queries)
        # Simulate progressive typing
        for i in range(1, len(query) + 1):
            prefix = query[:i]
            self.client.get(
                f"/api/v1/suggest?q={prefix}",
                name="/api/v1/suggest?q=[prefix]"
            )
            time.sleep(random.uniform(0.05, 0.15))  # Typing speed

    @task
    def quick_query(self):
        """Quick prefix lookup."""
        prefix = random.choice(["a", "b", "c", "the", "how"])
        self.client.get(f"/api/v1/suggest?q={prefix}")
```

**Performance Targets:**
| Metric | Target |
|--------|--------|
| p50 Latency | < 20ms |
| p99 Latency | < 100ms |
| Throughput | > 100K RPS |
| Cache Hit Rate | > 80% |

### 3. Data Pipeline Tests

```python
class TestDataPipeline:
    async def test_query_aggregation(self):
        """Test that queries are correctly aggregated."""
        # Send test queries to Pub/Sub
        queries = ["test query 1"] * 100 + ["test query 2"] * 50

        for q in queries:
            await pubsub.publish("query-logs", {"query": q})

        # Wait for pipeline processing
        await asyncio.sleep(120)

        # Verify aggregation
        result = await bigquery.query("""
            SELECT query, count
            FROM query_aggregations
            WHERE query IN ('test query 1', 'test query 2')
        """)

        assert result["test query 1"] == 100
        assert result["test query 2"] == 50

    async def test_trie_update(self):
        """Test that trie is updated with new data."""
        # Inject new popular query
        for _ in range(10000):
            await record_query("brand new trending topic")

        # Trigger trie rebuild
        await trigger_trie_update()

        # Verify it appears in suggestions
        response = await client.get("/api/v1/suggest?q=brand new")
        suggestions = [s["text"] for s in response.json()["suggestions"]]
        assert "brand new trending topic" in suggestions
```

### 4. Chaos Tests

```python
class AutocompleteChaosTests:
    async def test_shard_failure(self):
        """Test behavior when a trie shard fails."""
        # Kill one shard
        await platform_api.kill_pod("autocomplete-trie-5")

        # Queries to that shard range should failover
        response = await client.get("/api/v1/suggest?q=facebook")

        # Should return results (from replica or degraded)
        assert response.status_code == 200

    async def test_cache_cold_start(self):
        """Test performance with cold cache."""
        # Clear all caches
        await redis.flushall()

        # Measure cold start latency
        latencies = []
        for prefix in ["a", "b", "c", "d", "e"]:
            start = time.time()
            await client.get(f"/api/v1/suggest?q={prefix}")
            latencies.append(time.time() - start)

        # Even cold, should be under 200ms
        assert max(latencies) < 0.2

    async def test_traffic_spike(self):
        """Test handling of viral query."""
        # Simulate everyone searching same thing
        tasks = [
            client.get("/api/v1/suggest?q=breaking")
            for _ in range(10000)
        ]

        responses = await asyncio.gather(*tasks)
        success_rate = sum(1 for r in responses if r.status_code == 200) / len(responses)

        assert success_rate > 0.99
```

### 5. Manual Testing

```bash
# Test basic autocomplete
curl "https://autocomplete.run.app/api/v1/suggest?q=goo"

# Test with user personalization
curl "https://autocomplete.run.app/api/v1/suggest?q=py&user_id=123"

# Load test with hey
hey -n 100000 -c 500 "https://autocomplete.run.app/api/v1/suggest?q=test"

# Check latency distribution
hey -n 10000 -c 100 "https://autocomplete.run.app/api/v1/suggest?q=a" | grep -A 10 "Latency distribution"
```

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| p50 Latency | < 20ms | Load test |
| p99 Latency | < 100ms | Load test |
| Throughput | > 100K RPS | Load test |
| Relevance | > 80% CTR | A/B test |
| Freshness | < 1 hour | Pipeline test |
| Availability | > 99.99% | Chaos test |

---

## Common Pitfalls

1. **No caching:** Every request hits trie
2. **Single trie:** Memory limits, no sharding
3. **No personalization:** Generic results only
4. **Stale data:** Trie not updated frequently
5. **No trending:** Missing real-time signals
6. **Poor latency:** Complex ranking on every request
