# Search Autocomplete - L5 (Senior Software Engineer) Solution

## Level Requirements

**Target Role:** Senior Software Engineer (L5)
**Focus:** Core autocomplete functionality with basic prefix matching

### What's Expected at L5

- Trie-based prefix matching
- Basic ranking by popularity
- Redis-based caching
- RESTful API with debouncing support
- Basic analytics on search terms
- Understanding of latency requirements

---

## Database Schema

```json
{
  "storage": {
    "redis": {
      "data_structures": [
        {
          "name": "autocomplete:{prefix}",
          "type": "ZSET",
          "description": "Sorted set of suggestions for prefix",
          "score": "Popularity/weight score",
          "example": {
            "key": "autocomplete:iph",
            "members": [
              {"value": "iphone 15", "score": 10000},
              {"value": "iphone 14", "score": 8500},
              {"value": "iphone case", "score": 5000}
            ]
          }
        },
        {
          "name": "search_counts:{term}",
          "type": "STRING",
          "description": "Search frequency counter",
          "ttl": "7 days"
        },
        {
          "name": "trending:{date}",
          "type": "ZSET",
          "description": "Trending searches for the day",
          "score": "Search count"
        }
      ]
    },
    "postgresql": {
      "tables": [
        {
          "name": "search_terms",
          "description": "All searchable terms",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "term", "type": "VARCHAR(255)", "constraints": "UNIQUE NOT NULL"},
            {"name": "normalized_term", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "category", "type": "VARCHAR(100)"},
            {"name": "weight", "type": "INTEGER", "constraints": "DEFAULT 1"},
            {"name": "search_count", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "last_searched", "type": "TIMESTAMP"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"name": "idx_terms_normalized", "columns": ["normalized_term"], "type": "BTREE"},
            {"name": "idx_terms_prefix", "columns": ["normalized_term varchar_pattern_ops"], "type": "BTREE"}
          ]
        },
        {
          "name": "search_logs",
          "description": "Search analytics",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "term", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "user_id", "type": "VARCHAR(255)"},
            {"name": "session_id", "type": "VARCHAR(255)"},
            {"name": "result_count", "type": "INTEGER"},
            {"name": "selected_position", "type": "INTEGER"},
            {"name": "searched_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"name": "idx_logs_term_date", "columns": ["term", "searched_at"]}
          ]
        }
      ]
    }
  }
}
```

---

## API Specification

```json
{
  "endpoints": [
    {
      "method": "GET",
      "path": "/api/v1/autocomplete",
      "description": "Get autocomplete suggestions",
      "query_params": {
        "q": "string (required, prefix query)",
        "limit": "integer (optional, default: 10, max: 20)",
        "category": "string (optional, filter by category)"
      },
      "responses": {
        "200": {
          "query": "iph",
          "suggestions": [
            {"term": "iphone 15", "score": 10000, "category": "electronics"},
            {"term": "iphone 14", "score": 8500, "category": "electronics"},
            {"term": "iphone case", "score": 5000, "category": "accessories"}
          ],
          "latency_ms": 5
        },
        "400": {"error": "Query too short (min 2 characters)"}
      },
      "headers_returned": {
        "X-Response-Time": "5ms",
        "Cache-Control": "public, max-age=60"
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/search",
      "description": "Record a search (for analytics)",
      "request_body": {
        "term": "string (required)",
        "user_id": "string (optional)",
        "session_id": "string (optional)",
        "selected_position": "integer (optional)"
      },
      "responses": {
        "200": {"recorded": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/terms",
      "description": "Add new searchable term",
      "request_body": {
        "term": "string (required)",
        "category": "string (optional)",
        "weight": "integer (optional, default: 1)"
      },
      "responses": {
        "201": {"id": 12345, "term": "new product", "indexed": true}
      }
    },
    {
      "method": "DELETE",
      "path": "/api/v1/terms/{term}",
      "description": "Remove term from autocomplete",
      "responses": {
        "200": {"removed": true}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/trending",
      "description": "Get trending searches",
      "query_params": {
        "limit": "integer (default: 10)"
      },
      "responses": {
        "200": {
          "trending": [
            {"term": "black friday deals", "searches": 50000},
            {"term": "iphone 15", "searches": 35000}
          ]
        }
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check",
      "responses": {
        "200": {
          "status": "healthy",
          "redis": "connected",
          "index_size": 1000000
        }
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                    Search Autocomplete - L5 Architecture
    ═══════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────┐
    │                         CLIENT                                   │
    │                   (Browser / Mobile App)                         │
    │                                                                  │
    │  ┌─────────────────────────────────────────────────────────┐    │
    │  │  Debounced Input (300ms delay)                          │    │
    │  │                                                          │    │
    │  │  User types: "i" -> "ip" -> "iph" -> "ipho"             │    │
    │  │  API called:              "iph"    (after 300ms pause)   │    │
    │  └─────────────────────────────────────────────────────────┘    │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      LOAD BALANCER (Nginx)                       │
    │                                                                  │
    │  • SSL Termination                                               │
    │  • Response caching (60s TTL)                                    │
    │  • Rate limiting                                                 │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   AUTOCOMPLETE SERVICE                           │
    │                     (Python/FastAPI)                             │
    │                                                                  │
    │  ┌─────────────────────────────────────────────────────────┐    │
    │  │                   Request Handler                        │    │
    │  │                                                          │    │
    │  │  1. Normalize query (lowercase, trim)                    │    │
    │  │  2. Check minimum length (2 chars)                       │    │
    │  │  3. Query Redis ZSET                                     │    │
    │  │  4. Return top N results                                 │    │
    │  └─────────────────────────────────────────────────────────┘    │
    │                                                                  │
    │  ┌─────────────────────────────────────────────────────────┐    │
    │  │                   Analytics Handler                      │    │
    │  │                                                          │    │
    │  │  • Record search events                                  │    │
    │  │  • Update search counts                                  │    │
    │  │  • Update trending                                       │    │
    │  └─────────────────────────────────────────────────────────┘    │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
              ▼                                     ▼
    ┌─────────────────────┐              ┌─────────────────────┐
    │       Redis         │              │    PostgreSQL       │
    │   (Autocomplete)    │              │   (Source Data)     │
    │                     │              │                     │
    │ • ZSET per prefix   │              │ • search_terms      │
    │ • O(log N) lookups  │              │ • search_logs       │
    │ • Sorted by score   │              │ • Source of truth   │
    └─────────────────────┘              └─────────────────────┘

                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      INDEX BUILDER (Batch Job)                   │
    │                                                                  │
    │  Runs periodically to rebuild Redis index from PostgreSQL        │
    │                                                                  │
    │  For each term:                                                  │
    │    For prefix in generate_prefixes(term):                        │
    │      ZADD autocomplete:{prefix} {score} {term}                   │
    └─────────────────────────────────────────────────────────────────┘
```

### Trie/ZSET Implementation

```python
import redis
from typing import List, Dict, Optional
import time

class AutocompleteService:
    """
    L5 Autocomplete Service using Redis Sorted Sets.

    Each prefix maps to a sorted set of completions,
    scored by popularity.
    """

    MIN_PREFIX_LENGTH = 2
    MAX_RESULTS = 20
    PREFIX_KEY_TEMPLATE = "autocomplete:{prefix}"

    def __init__(self, redis_client: redis.Redis, db_connection):
        self.redis = redis_client
        self.db = db_connection

    def get_suggestions(
        self,
        query: str,
        limit: int = 10,
        category: str = None
    ) -> Dict:
        """
        Get autocomplete suggestions for a prefix.

        Time complexity: O(log N + M) where M is the number of results
        """
        start_time = time.time()

        # Normalize query
        normalized = self._normalize(query)

        if len(normalized) < self.MIN_PREFIX_LENGTH:
            return {
                "query": query,
                "suggestions": [],
                "error": "Query too short"
            }

        # Get from Redis
        key = self.PREFIX_KEY_TEMPLATE.format(prefix=normalized)

        # ZREVRANGE returns highest scores first
        results = self.redis.zrevrange(
            key,
            0,
            limit - 1,
            withscores=True
        )

        suggestions = []
        for term, score in results:
            term_str = term.decode() if isinstance(term, bytes) else term

            # Optional category filter
            if category:
                term_category = self._get_category(term_str)
                if term_category != category:
                    continue

            suggestions.append({
                "term": term_str,
                "score": int(score)
            })

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "query": query,
            "suggestions": suggestions[:limit],
            "latency_ms": latency_ms
        }

    def add_term(
        self,
        term: str,
        weight: int = 1,
        category: str = None
    ) -> Dict:
        """
        Add a term to the autocomplete index.

        Generates all prefixes and adds to corresponding ZSETs.
        """
        normalized = self._normalize(term)

        # Generate all prefixes (min length 2)
        prefixes = self._generate_prefixes(normalized)

        # Add to Redis
        pipe = self.redis.pipeline()
        for prefix in prefixes:
            key = self.PREFIX_KEY_TEMPLATE.format(prefix=prefix)
            pipe.zadd(key, {term: weight})
        pipe.execute()

        # Store in PostgreSQL
        self._store_term(term, normalized, category, weight)

        return {"term": term, "indexed": True, "prefixes": len(prefixes)}

    def remove_term(self, term: str) -> Dict:
        """
        Remove a term from the autocomplete index.
        """
        normalized = self._normalize(term)
        prefixes = self._generate_prefixes(normalized)

        # Remove from Redis
        pipe = self.redis.pipeline()
        for prefix in prefixes:
            key = self.PREFIX_KEY_TEMPLATE.format(prefix=prefix)
            pipe.zrem(key, term)
        pipe.execute()

        # Mark as removed in PostgreSQL
        self._remove_term(term)

        return {"removed": True}

    def record_search(
        self,
        term: str,
        user_id: str = None,
        selected_position: int = None
    ):
        """
        Record a search event for analytics and ranking updates.
        """
        normalized = self._normalize(term)

        # Increment search count
        count_key = f"search_counts:{normalized}"
        new_count = self.redis.incr(count_key)
        self.redis.expire(count_key, 7 * 24 * 3600)  # 7 days

        # Update trending
        today = time.strftime("%Y-%m-%d")
        trending_key = f"trending:{today}"
        self.redis.zincrby(trending_key, 1, term)
        self.redis.expire(trending_key, 24 * 3600)

        # Update score in autocomplete index
        if new_count % 100 == 0:  # Batch updates
            self._update_term_score(term, new_count)

        # Log to PostgreSQL (async)
        self._log_search(term, user_id, selected_position)

    def get_trending(self, limit: int = 10) -> List[Dict]:
        """
        Get trending searches for today.
        """
        today = time.strftime("%Y-%m-%d")
        trending_key = f"trending:{today}"

        results = self.redis.zrevrange(
            trending_key,
            0,
            limit - 1,
            withscores=True
        )

        return [
            {"term": term.decode(), "searches": int(score)}
            for term, score in results
        ]

    def _normalize(self, text: str) -> str:
        """Normalize text for consistent matching."""
        return text.lower().strip()

    def _generate_prefixes(self, term: str) -> List[str]:
        """Generate all valid prefixes for a term."""
        prefixes = []
        for i in range(self.MIN_PREFIX_LENGTH, len(term) + 1):
            prefixes.append(term[:i])
        return prefixes

    def _update_term_score(self, term: str, new_score: int):
        """Update term score in all prefix ZSETs."""
        normalized = self._normalize(term)
        prefixes = self._generate_prefixes(normalized)

        pipe = self.redis.pipeline()
        for prefix in prefixes:
            key = self.PREFIX_KEY_TEMPLATE.format(prefix=prefix)
            pipe.zadd(key, {term: new_score})
        pipe.execute()


class IndexBuilder:
    """
    Batch job to rebuild autocomplete index from PostgreSQL.
    """

    def __init__(self, redis_client: redis.Redis, db_connection):
        self.redis = redis_client
        self.db = db_connection

    def rebuild_index(self, batch_size: int = 1000):
        """
        Rebuild entire autocomplete index.
        """
        # Clear existing index
        keys = self.redis.keys("autocomplete:*")
        if keys:
            self.redis.delete(*keys)

        # Fetch all terms
        offset = 0
        while True:
            terms = self._fetch_terms(offset, batch_size)
            if not terms:
                break

            # Index batch
            self._index_batch(terms)
            offset += batch_size

    def _fetch_terms(self, offset: int, limit: int) -> List[Dict]:
        """Fetch terms from PostgreSQL."""
        query = """
            SELECT term, normalized_term, weight + search_count as score
            FROM search_terms
            WHERE weight > 0
            ORDER BY id
            LIMIT %s OFFSET %s
        """
        return self.db.fetch_all(query, (limit, offset))

    def _index_batch(self, terms: List[Dict]):
        """Index a batch of terms."""
        pipe = self.redis.pipeline()

        for term_data in terms:
            term = term_data["term"]
            normalized = term_data["normalized_term"]
            score = term_data["score"]

            # Generate prefixes
            for i in range(2, len(normalized) + 1):
                prefix = normalized[:i]
                key = f"autocomplete:{prefix}"
                pipe.zadd(key, {term: score})

        pipe.execute()
```

### Request Flow

**Autocomplete Request:**
1. Client sends prefix query (after debounce)
2. Load balancer checks response cache
3. If cache miss, forward to service
4. Service normalizes query
5. Query Redis ZSET for prefix
6. Return top N results by score
7. Cache response (60s TTL)

**Search Recording:**
1. User selects suggestion or submits search
2. API records search event
3. Increment search count in Redis
4. Update trending ZSET
5. Periodically update autocomplete scores
6. Log to PostgreSQL for analytics

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Basic prefix | Query "iph" | Returns "iphone" suggestions |
| F-02 | Case insensitive | Query "IPH" | Same as "iph" |
| F-03 | Min length | Query "i" | Error: too short |
| F-04 | No results | Query "xyz123" | Empty suggestions |
| F-05 | Limit respected | Limit=5 | Max 5 results |
| F-06 | Sorted by score | Multiple results | Highest score first |
| F-07 | Add term | POST new term | Term indexed |
| F-08 | Remove term | DELETE term | Term removed |
| F-09 | Record search | POST search | Count incremented |
| F-10 | Trending | GET trending | Today's top searches |
| F-11 | Category filter | Filter by category | Only matching |
| F-12 | Unicode support | Query "café" | Returns matches |
| F-13 | Special chars | Query "c++" | Handled correctly |
| F-14 | Whitespace | Query " iph " | Trimmed and works |
| F-15 | Long prefix | Full term as query | Returns exact match |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Response latency | Single query | < 10ms p99 |
| P-02 | Throughput | Concurrent queries | > 10,000 QPS |
| P-03 | Index size | 1M terms | < 2GB Redis |
| P-04 | Index build | Full rebuild | < 5 minutes |
| P-05 | Cache hit rate | With caching | > 80% |
| P-06 | Memory per prefix | Average | < 1KB |
| P-07 | Large result set | Popular prefix | < 20ms |
| P-08 | Connection pool | High concurrency | No exhaustion |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis down | Kill Redis | Error response, no crash |
| C-02 | High load | 10x traffic | Graceful degradation |
| C-03 | Memory full | Redis OOM | LRU eviction |
| C-04 | Network latency | 100ms delay | Timeout handling |
| C-05 | Concurrent writes | Many adds | No corruption |
| C-06 | Index corruption | Invalid data | Rebuild recovers |

---

## Capacity Estimates

- **Terms**: 1M searchable terms
- **Prefixes per term**: ~10 average
- **Total Redis keys**: ~10M
- **Redis memory**: ~500MB - 1GB
- **Queries per second**: 10,000
- **Latency target**: < 10ms p99
- **Cache hit rate**: > 80%
