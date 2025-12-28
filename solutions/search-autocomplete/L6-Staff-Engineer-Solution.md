# Search Autocomplete - L6 (Staff Engineer) Solution

## Level Requirements

**Target Role:** Staff Engineer (L6)
**Focus:** Scalable autocomplete with advanced ranking and personalization

### What's Expected at L6

- Distributed trie with sharding
- Multi-signal ranking (popularity, recency, personalization)
- Fuzzy matching and typo tolerance
- Real-time index updates
- A/B testing for ranking algorithms
- Horizontal scaling

---

## Database Schema

```json
{
  "storage_layers": {
    "redis_cluster": {
      "type": "Redis Cluster",
      "sharding": "By prefix hash",
      "data_structures": [
        {
          "name": "ac:{shard}:{prefix}",
          "type": "ZSET",
          "description": "Sharded autocomplete index",
          "score": "Composite ranking score"
        },
        {
          "name": "ac_fuzzy:{shard}:{ngram}",
          "type": "SET",
          "description": "N-gram index for fuzzy matching"
        },
        {
          "name": "user_history:{user_id}",
          "type": "LIST",
          "description": "Recent user searches (last 100)",
          "max_length": 100
        },
        {
          "name": "term_metadata:{term_hash}",
          "type": "HASH",
          "fields": {
            "display_term": "Original case term",
            "category": "Product category",
            "popularity": "Global popularity score",
            "recency_score": "Time-decay score",
            "click_through_rate": "CTR from impressions"
          }
        },
        {
          "name": "realtime_updates",
          "type": "STREAM",
          "description": "Real-time index update events"
        }
      ]
    },
    "elasticsearch": {
      "purpose": "Fuzzy matching fallback and analytics",
      "indexes": [
        {
          "name": "search_terms",
          "mappings": {
            "term": {"type": "text", "analyzer": "autocomplete_analyzer"},
            "term_suggest": {"type": "completion", "contexts": [{"name": "category", "type": "category"}]},
            "normalized": {"type": "keyword"},
            "category": {"type": "keyword"},
            "popularity": {"type": "float"},
            "created_at": {"type": "date"}
          },
          "settings": {
            "analysis": {
              "analyzer": {
                "autocomplete_analyzer": {
                  "type": "custom",
                  "tokenizer": "standard",
                  "filter": ["lowercase", "edge_ngram_filter"]
                }
              },
              "filter": {
                "edge_ngram_filter": {
                  "type": "edge_ngram",
                  "min_gram": 2,
                  "max_gram": 20
                }
              }
            }
          }
        }
      ]
    },
    "postgresql": {
      "tables": [
        {
          "name": "search_terms",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "term", "type": "VARCHAR(255)", "constraints": "UNIQUE NOT NULL"},
            {"name": "normalized", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "category", "type": "VARCHAR(100)"},
            {"name": "base_weight", "type": "INTEGER", "constraints": "DEFAULT 1"},
            {"name": "popularity_score", "type": "FLOAT", "constraints": "DEFAULT 0"},
            {"name": "recency_score", "type": "FLOAT", "constraints": "DEFAULT 0"},
            {"name": "ctr", "type": "FLOAT", "constraints": "DEFAULT 0"},
            {"name": "impressions", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "clicks", "type": "BIGINT", "constraints": "DEFAULT 0"},
            {"name": "last_clicked", "type": "TIMESTAMP"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"},
            {"name": "updated_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"columns": ["normalized"], "type": "BTREE"},
            {"columns": ["category", "popularity_score"]}
          ]
        },
        {
          "name": "search_events",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "user_id", "type": "VARCHAR(255)"},
            {"name": "session_id", "type": "VARCHAR(255)"},
            {"name": "query", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "suggestions_shown", "type": "JSONB"},
            {"name": "selected_term", "type": "VARCHAR(255)"},
            {"name": "selected_position", "type": "INTEGER"},
            {"name": "ranking_algorithm", "type": "VARCHAR(50)"},
            {"name": "latency_ms", "type": "INTEGER"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "partitioning": {
            "type": "RANGE",
            "column": "created_at",
            "interval": "1 day"
          }
        },
        {
          "name": "ranking_experiments",
          "columns": [
            {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
            {"name": "name", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
            {"name": "variants", "type": "JSONB", "constraints": "NOT NULL"},
            {"name": "traffic_allocation", "type": "JSONB"},
            {"name": "metrics", "type": "JSONB"},
            {"name": "status", "type": "VARCHAR(20)", "constraints": "DEFAULT 'active'"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ]
        }
      ]
    },
    "kafka": {
      "topics": [
        {
          "name": "search-events",
          "partitions": 16,
          "description": "Real-time search events"
        },
        {
          "name": "index-updates",
          "partitions": 8,
          "description": "Index update events"
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
      "description": "Get personalized autocomplete suggestions",
      "query_params": {
        "q": "string (required)",
        "limit": "integer (default: 10)",
        "category": "string (optional)",
        "user_id": "string (optional, for personalization)",
        "session_id": "string (optional)",
        "fuzzy": "boolean (default: true)",
        "experiment_id": "string (optional)"
      },
      "responses": {
        "200": {
          "query": "iphne",
          "suggestions": [
            {
              "term": "iphone 15",
              "display": "iPhone 15",
              "score": 0.95,
              "category": "electronics",
              "source": "fuzzy_match",
              "metadata": {"correction": "iphone"}
            },
            {
              "term": "iphone 14",
              "display": "iPhone 14",
              "score": 0.88,
              "category": "electronics",
              "source": "prefix_match"
            }
          ],
          "personalized": true,
          "experiment": {"id": "ranking_v2", "variant": "ml_ranking"},
          "latency_ms": 8
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/events/impression",
      "description": "Record suggestion impressions",
      "request_body": {
        "query": "string",
        "suggestions": ["term1", "term2"],
        "user_id": "string (optional)",
        "session_id": "string"
      },
      "responses": {
        "200": {"recorded": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/events/click",
      "description": "Record suggestion click",
      "request_body": {
        "query": "string",
        "selected_term": "string",
        "position": "integer",
        "user_id": "string (optional)",
        "session_id": "string"
      },
      "responses": {
        "200": {"recorded": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/terms/batch",
      "description": "Batch add/update terms",
      "request_body": {
        "terms": [
          {"term": "new product", "category": "electronics", "weight": 100}
        ]
      },
      "responses": {
        "202": {"accepted": 100, "queued": true}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/experiments",
      "description": "Get active ranking experiments",
      "responses": {
        "200": {
          "experiments": [
            {
              "id": "ranking_v2",
              "variants": ["control", "ml_ranking"],
              "allocation": {"control": 50, "ml_ranking": 50}
            }
          ]
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics/performance",
      "description": "Get autocomplete performance metrics",
      "query_params": {
        "start_date": "ISO8601",
        "end_date": "ISO8601"
      },
      "responses": {
        "200": {
          "metrics": {
            "total_queries": 1000000,
            "avg_latency_ms": 8,
            "p99_latency_ms": 25,
            "click_through_rate": 0.35,
            "no_result_rate": 0.02,
            "fuzzy_match_rate": 0.15
          },
          "by_experiment": {
            "control": {"ctr": 0.32},
            "ml_ranking": {"ctr": 0.38}
          }
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
                      Search Autocomplete - L6 Architecture
    ═════════════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                            CLIENT LAYER                                  │
    │                                                                          │
    │  ┌───────────────────────────────────────────────────────────────────┐  │
    │  │  Client SDK / Browser                                              │  │
    │  │                                                                    │  │
    │  │  • Debounce (200ms)                                                │  │
    │  │  • Request deduplication                                           │  │
    │  │  • Local result caching                                            │  │
    │  │  • Impression/click tracking                                       │  │
    │  └───────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                          API GATEWAY                                     │
    │                                                                          │
    │  • Rate limiting (per user/IP)                                          │
    │  • Response caching (CDN integration)                                   │
    │  • A/B experiment routing                                               │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                     AUTOCOMPLETE SERVICE CLUSTER                         │
    │                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────┐    │
    │  │                     Query Processing Pipeline                    │    │
    │  │                                                                  │    │
    │  │  1. Parse & Normalize ─► 2. Experiment Assignment               │    │
    │  │           │                        │                             │    │
    │  │           ▼                        ▼                             │    │
    │  │  3. Parallel Fetch ──────────────────────────────────────────   │    │
    │  │     │              │                │                            │    │
    │  │     ▼              ▼                ▼                            │    │
    │  │  [Prefix Match] [Fuzzy Match] [Personal History]                │    │
    │  │     │              │                │                            │    │
    │  │     └──────────────┴────────────────┘                           │    │
    │  │                    │                                             │    │
    │  │                    ▼                                             │    │
    │  │  4. Merge & Rank (based on experiment variant)                   │    │
    │  │                    │                                             │    │
    │  │                    ▼                                             │    │
    │  │  5. Post-process (dedup, limit, format)                          │    │
    │  └─────────────────────────────────────────────────────────────────┘    │
    │                                                                          │
    │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
    │  │ Ranking Service  │  │ Personalization  │  │ A/B Experiment   │       │
    │  │                  │  │ Service          │  │ Service          │       │
    │  │ • Multi-signal   │  │ • User history   │  │ • Variant assign │       │
    │  │ • ML scoring     │  │ • Preferences    │  │ • Metric track   │       │
    │  │ • CTR prediction │  │ • Boost/demote   │  │                  │       │
    │  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
    │   Redis Cluster     │ │   Elasticsearch     │ │   PostgreSQL        │
    │   (Primary Index)   │ │   (Fuzzy Fallback)  │ │   (Source of Truth) │
    │                     │ │                     │ │                     │
    │ • Sharded by prefix │ │ • Completion suggest│ │ • Term metadata     │
    │ • ZSET per prefix   │ │ • Fuzzy queries     │ │ • Event logs        │
    │ • User history      │ │ • N-gram matching   │ │ • Experiments       │
    │ • Term metadata     │ │ • Spell correction  │ │                     │
    └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
                                     │
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                       REAL-TIME PROCESSING                               │
    │                                                                          │
    │  ┌─────────────────────┐              ┌─────────────────────┐           │
    │  │   Event Stream      │              │   Index Updater     │           │
    │  │   (Kafka)           │─────────────▶│   Service           │           │
    │  │                     │              │                     │           │
    │  │ • Search events     │              │ • Score updates     │           │
    │  │ • Click events      │              │ • New term indexing │           │
    │  │ • Impression events │              │ • CTR recalculation │           │
    │  └─────────────────────┘              └─────────────────────┘           │
    │                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────┐    │
    │  │                    Analytics Pipeline                            │    │
    │  │                                                                  │    │
    │  │  • CTR calculation per term                                      │    │
    │  │  • Experiment metrics aggregation                                │    │
    │  │  • Ranking model training data                                   │    │
    │  └─────────────────────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────────────────────┘
```

### Multi-Signal Ranking Implementation

```python
import asyncio
import hashlib
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import redis
from elasticsearch import AsyncElasticsearch

@dataclass
class SuggestionCandidate:
    term: str
    display_term: str
    category: str
    popularity_score: float
    recency_score: float
    ctr_score: float
    personalization_score: float
    fuzzy_distance: int
    source: str  # 'prefix', 'fuzzy', 'history'

@dataclass
class RankingWeights:
    popularity: float = 0.3
    recency: float = 0.2
    ctr: float = 0.25
    personalization: float = 0.15
    fuzzy_penalty: float = 0.1

class AutocompleteServiceL6:
    """
    L6 Autocomplete with multi-signal ranking and fuzzy matching.
    """

    def __init__(
        self,
        redis_cluster: redis.RedisCluster,
        elasticsearch: AsyncElasticsearch,
        db_connection,
        kafka_producer
    ):
        self.redis = redis_cluster
        self.es = elasticsearch
        self.db = db_connection
        self.kafka = kafka_producer

    async def get_suggestions(
        self,
        query: str,
        limit: int = 10,
        category: str = None,
        user_id: str = None,
        fuzzy: bool = True,
        experiment_variant: str = None
    ) -> Dict:
        """
        Get ranked autocomplete suggestions with personalization.
        """
        start_time = time.time()
        normalized = self._normalize(query)

        if len(normalized) < 2:
            return {"query": query, "suggestions": [], "error": "Query too short"}

        # Determine ranking weights based on experiment
        weights = self._get_ranking_weights(experiment_variant)

        # Parallel fetch from multiple sources
        prefix_task = self._get_prefix_matches(normalized, category)
        fuzzy_task = self._get_fuzzy_matches(normalized, category) if fuzzy else asyncio.sleep(0)
        history_task = self._get_user_history(user_id, normalized) if user_id else asyncio.sleep(0)

        results = await asyncio.gather(
            prefix_task,
            fuzzy_task,
            history_task,
            return_exceptions=True
        )

        prefix_matches = results[0] if not isinstance(results[0], Exception) else []
        fuzzy_matches = results[1] if not isinstance(results[1], Exception) else []
        history_matches = results[2] if not isinstance(results[2], Exception) else []

        # Merge and deduplicate
        candidates = self._merge_candidates(
            prefix_matches,
            fuzzy_matches,
            history_matches
        )

        # Score and rank
        ranked = self._rank_candidates(candidates, weights, user_id)

        # Take top N
        top_suggestions = ranked[:limit]

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "query": query,
            "suggestions": [self._format_suggestion(s) for s in top_suggestions],
            "personalized": user_id is not None,
            "latency_ms": latency_ms
        }

    async def _get_prefix_matches(
        self,
        prefix: str,
        category: str = None
    ) -> List[SuggestionCandidate]:
        """
        Get exact prefix matches from Redis.
        """
        shard = self._get_shard(prefix)
        key = f"ac:{shard}:{prefix}"

        # Get top candidates with scores
        results = self.redis.zrevrange(key, 0, 50, withscores=True)

        candidates = []
        for term_bytes, score in results:
            term = term_bytes.decode() if isinstance(term_bytes, bytes) else term_bytes

            # Get metadata
            metadata = await self._get_term_metadata(term)

            if category and metadata.get("category") != category:
                continue

            candidates.append(SuggestionCandidate(
                term=term,
                display_term=metadata.get("display_term", term),
                category=metadata.get("category", ""),
                popularity_score=metadata.get("popularity", 0),
                recency_score=metadata.get("recency_score", 0),
                ctr_score=metadata.get("ctr", 0),
                personalization_score=0,
                fuzzy_distance=0,
                source="prefix"
            ))

        return candidates

    async def _get_fuzzy_matches(
        self,
        query: str,
        category: str = None
    ) -> List[SuggestionCandidate]:
        """
        Get fuzzy matches from Elasticsearch.
        """
        es_query = {
            "suggest": {
                "term_suggest": {
                    "prefix": query,
                    "completion": {
                        "field": "term_suggest",
                        "fuzzy": {
                            "fuzziness": "AUTO"
                        },
                        "size": 20
                    }
                }
            }
        }

        if category:
            es_query["suggest"]["term_suggest"]["completion"]["contexts"] = {
                "category": [category]
            }

        response = await self.es.search(index="search_terms", body=es_query)

        candidates = []
        suggestions = response.get("suggest", {}).get("term_suggest", [{}])[0].get("options", [])

        for option in suggestions:
            source = option["_source"]
            text = option["text"]

            # Calculate edit distance
            distance = self._levenshtein_distance(query, source["normalized"])

            if distance > 0:  # Only include actual fuzzy matches
                candidates.append(SuggestionCandidate(
                    term=source["normalized"],
                    display_term=source["term"],
                    category=source.get("category", ""),
                    popularity_score=source.get("popularity", 0),
                    recency_score=0,
                    ctr_score=0,
                    personalization_score=0,
                    fuzzy_distance=distance,
                    source="fuzzy"
                ))

        return candidates

    async def _get_user_history(
        self,
        user_id: str,
        prefix: str
    ) -> List[SuggestionCandidate]:
        """
        Get matching items from user's search history.
        """
        key = f"user_history:{user_id}"
        history = self.redis.lrange(key, 0, 100)

        candidates = []
        for term_bytes in history:
            term = term_bytes.decode() if isinstance(term_bytes, bytes) else term_bytes
            normalized = self._normalize(term)

            if normalized.startswith(prefix):
                candidates.append(SuggestionCandidate(
                    term=normalized,
                    display_term=term,
                    category="",
                    popularity_score=0,
                    recency_score=0,
                    ctr_score=0,
                    personalization_score=1.0,  # High score for personal history
                    fuzzy_distance=0,
                    source="history"
                ))

        return candidates

    def _merge_candidates(
        self,
        *candidate_lists: List[SuggestionCandidate]
    ) -> List[SuggestionCandidate]:
        """
        Merge candidate lists, deduplicating by term.
        """
        seen = {}

        for candidates in candidate_lists:
            for candidate in candidates:
                key = candidate.term.lower()
                if key not in seen:
                    seen[key] = candidate
                else:
                    # Merge scores from different sources
                    existing = seen[key]
                    existing.personalization_score = max(
                        existing.personalization_score,
                        candidate.personalization_score
                    )
                    if candidate.source == "prefix":
                        existing.source = "prefix"  # Prefer prefix source

        return list(seen.values())

    def _rank_candidates(
        self,
        candidates: List[SuggestionCandidate],
        weights: RankingWeights,
        user_id: str = None
    ) -> List[SuggestionCandidate]:
        """
        Score and rank candidates using multi-signal formula.
        """
        scored_candidates = []

        for candidate in candidates:
            # Calculate composite score
            score = (
                weights.popularity * self._normalize_score(candidate.popularity_score) +
                weights.recency * self._normalize_score(candidate.recency_score) +
                weights.ctr * self._normalize_score(candidate.ctr_score) +
                weights.personalization * candidate.personalization_score -
                weights.fuzzy_penalty * (candidate.fuzzy_distance / 5.0)  # Penalize fuzzy
            )

            candidate.final_score = max(0, min(1, score))
            scored_candidates.append(candidate)

        # Sort by final score
        scored_candidates.sort(key=lambda x: x.final_score, reverse=True)

        return scored_candidates

    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1 range."""
        # Assuming scores are already in reasonable ranges
        return max(0, min(1, score))

    def _get_ranking_weights(self, experiment_variant: str = None) -> RankingWeights:
        """Get ranking weights based on experiment variant."""
        if experiment_variant == "ml_ranking":
            return RankingWeights(
                popularity=0.25,
                recency=0.15,
                ctr=0.35,
                personalization=0.20,
                fuzzy_penalty=0.05
            )
        elif experiment_variant == "personalized":
            return RankingWeights(
                popularity=0.20,
                recency=0.15,
                ctr=0.20,
                personalization=0.40,
                fuzzy_penalty=0.05
            )
        else:  # control
            return RankingWeights()

    def _get_shard(self, prefix: str) -> int:
        """Get shard number for prefix (consistent hashing)."""
        hash_val = int(hashlib.md5(prefix.encode()).hexdigest(), 16)
        return hash_val % 16  # 16 shards

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate edit distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


class RealTimeIndexUpdater:
    """
    Processes events from Kafka to update index in real-time.
    """

    def __init__(
        self,
        redis_cluster: redis.RedisCluster,
        elasticsearch: AsyncElasticsearch,
        db_connection
    ):
        self.redis = redis_cluster
        self.es = elasticsearch
        self.db = db_connection

    async def process_click_event(self, event: Dict):
        """Update scores based on click event."""
        term = event["selected_term"]
        position = event["position"]

        # Update click count
        term_hash = hashlib.md5(term.lower().encode()).hexdigest()
        meta_key = f"term_metadata:{term_hash}"

        self.redis.hincrby(meta_key, "clicks", 1)
        self.redis.hset(meta_key, "last_clicked", time.time())

        # Recalculate CTR
        metadata = self.redis.hgetall(meta_key)
        impressions = int(metadata.get(b"impressions", 1))
        clicks = int(metadata.get(b"clicks", 1))
        ctr = clicks / impressions

        self.redis.hset(meta_key, "ctr", ctr)

        # Update score in prefix index
        await self._update_prefix_scores(term, ctr)

    async def process_impression_event(self, event: Dict):
        """Update impression counts."""
        for term in event["suggestions"]:
            term_hash = hashlib.md5(term.lower().encode()).hexdigest()
            meta_key = f"term_metadata:{term_hash}"
            self.redis.hincrby(meta_key, "impressions", 1)

    async def _update_prefix_scores(self, term: str, ctr: float):
        """Update term score in all prefix ZSETs."""
        normalized = term.lower()
        shard = self._get_shard(normalized)

        # Calculate new composite score
        meta_key = f"term_metadata:{hashlib.md5(normalized.encode()).hexdigest()}"
        metadata = self.redis.hgetall(meta_key)

        popularity = float(metadata.get(b"popularity", 0))
        recency = float(metadata.get(b"recency_score", 0))

        composite_score = popularity * 0.4 + recency * 0.3 + ctr * 0.3

        # Update in prefix ZSETs
        for i in range(2, len(normalized) + 1):
            prefix = normalized[:i]
            key = f"ac:{shard}:{prefix}"
            self.redis.zadd(key, {term: composite_score})
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Prefix match | Exact prefix query | Matching terms returned |
| F-02 | Fuzzy match | Typo "iphne" | Returns "iphone" |
| F-03 | Personalization | User history match | History items ranked higher |
| F-04 | Multi-signal ranking | Various signals | Proper weighted ranking |
| F-05 | Category filter | Filter by category | Only matching category |
| F-06 | Experiment variant | Different variants | Different rankings |
| F-07 | Click tracking | Record click | CTR updated |
| F-08 | Impression tracking | Record impressions | Counts updated |
| F-09 | Real-time update | New popular term | Score increases |
| F-10 | Shard routing | Different prefixes | Correct shard used |
| F-11 | Merge sources | Multi-source results | Deduplicated list |
| F-12 | Fuzzy penalty | Fuzzy vs exact | Exact ranked higher |
| F-13 | Empty history | New user | Works without history |
| F-14 | Long query | Full term query | Returns matches |
| F-15 | Batch indexing | Add 1000 terms | All indexed |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Response latency | Single query | < 20ms p99 |
| P-02 | Parallel fetch | All sources | < 15ms total |
| P-03 | Throughput | Concurrent queries | > 50,000 QPS |
| P-04 | Fuzzy latency | ES fuzzy query | < 10ms |
| P-05 | Personalization | History lookup | < 2ms |
| P-06 | Index update | Real-time event | < 100ms |
| P-07 | Shard balance | Query distribution | Even across shards |
| P-08 | Cache efficiency | Hot queries | > 90% hit rate |
| P-09 | ES suggestion | Completion suggester | < 5ms |
| P-10 | Ranking computation | Score calculation | < 1ms |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis shard down | One shard fails | Other shards serve |
| C-02 | ES unavailable | ES cluster down | Fallback to Redis only |
| C-03 | Kafka lag | Event backlog | Eventual consistency |
| C-04 | High latency | Network issues | Timeout and degrade |
| C-05 | Index corruption | Invalid data | Rebuild from source |
| C-06 | Hot key | Popular prefix | Caching absorbs |
| C-07 | Memory pressure | High load | LRU eviction |
| C-08 | Split brain | Network partition | Consistent behavior |

---

## Capacity Estimates

- **Terms**: 10M searchable terms
- **Queries per second**: 50,000
- **Redis cluster**: 6 nodes (3 masters, 3 replicas)
- **Redis memory**: ~5GB per shard
- **Elasticsearch**: 3-node cluster, 50GB
- **Latency target**: < 20ms p99
- **Fuzzy match rate**: ~15% of queries
- **Personalization coverage**: ~60% of users
