# Search Autocomplete - L7 (Principal Engineer) Solution

## Level Requirements

**Target Role:** Principal Engineer (L7)
**Focus:** Global-scale autocomplete with ML-powered relevance

### What's Expected at L7

- Multi-region with geo-aware serving
- ML-based ranking models
- Query understanding (intent, entities)
- Real-time learning from user behavior
- Semantic/vector-based suggestions
- Zero-downtime index updates
- Cost optimization at scale

---

## Database Schema

```json
{
  "storage_layers": {
    "regional_redis_cluster": {
      "purpose": "Low-latency prefix index per region",
      "data_structures": [
        {
          "name": "ac:{region}:{locale}:{prefix}",
          "type": "ZSET",
          "description": "Locale-aware prefix index",
          "score": "ML-computed relevance score"
        },
        {
          "name": "ac_vectors:{region}:{term_id}",
          "type": "HASH",
          "description": "Cached embedding vectors for semantic search"
        },
        {
          "name": "user_model:{user_id}",
          "type": "HASH",
          "description": "User preference model",
          "fields": {
            "category_affinities": "JSON of category scores",
            "search_embedding": "User interest vector",
            "last_searches": "Recent search terms",
            "click_history": "Recent clicks"
          }
        },
        {
          "name": "query_cache:{query_hash}",
          "type": "STRING",
          "description": "Full query result cache",
          "ttl": "5 minutes"
        },
        {
          "name": "trending:{region}:{locale}:{window}",
          "type": "ZSET",
          "description": "Real-time trending by region/locale"
        }
      ]
    },
    "vector_store": {
      "type": "Pinecone / Milvus / pgvector",
      "purpose": "Semantic similarity search",
      "indexes": [
        {
          "name": "term_embeddings",
          "dimensions": 768,
          "metric": "cosine",
          "metadata": ["category", "locale", "popularity"]
        },
        {
          "name": "query_embeddings",
          "dimensions": 768,
          "description": "For semantic query understanding"
        }
      ]
    },
    "elasticsearch_global": {
      "purpose": "Fuzzy matching and full-text fallback",
      "indexes": [
        {
          "name": "search_terms_{locale}",
          "mappings": {
            "term": {"type": "text", "analyzer": "locale_autocomplete"},
            "term_suggest": {"type": "completion"},
            "normalized": {"type": "keyword"},
            "category": {"type": "keyword"},
            "popularity": {"type": "float"},
            "embedding_id": {"type": "keyword"},
            "entities": {"type": "nested"}
          }
        }
      ]
    },
    "cockroachdb_global": {
      "purpose": "Global coordination and configuration",
      "tables": [
        {
          "name": "terms",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "term", "type": "VARCHAR(500)", "constraints": "NOT NULL"},
            {"name": "normalized", "type": "VARCHAR(500)", "constraints": "NOT NULL"},
            {"name": "locale", "type": "VARCHAR(10)", "constraints": "NOT NULL"},
            {"name": "category", "type": "VARCHAR(100)"},
            {"name": "entities", "type": "JSONB"},
            {"name": "embedding_version", "type": "INTEGER"},
            {"name": "ml_score", "type": "FLOAT"},
            {"name": "global_impressions", "type": "BIGINT"},
            {"name": "global_clicks", "type": "BIGINT"},
            {"name": "created_at", "type": "TIMESTAMPTZ"},
            {"name": "updated_at", "type": "TIMESTAMPTZ"}
          ]
        },
        {
          "name": "ml_models",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "name", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "version", "type": "INTEGER", "constraints": "NOT NULL"},
            {"name": "model_type", "type": "VARCHAR(50)"},
            {"name": "artifact_uri", "type": "VARCHAR(500)"},
            {"name": "metrics", "type": "JSONB"},
            {"name": "status", "type": "VARCHAR(20)"},
            {"name": "deployed_at", "type": "TIMESTAMPTZ"}
          ]
        },
        {
          "name": "feature_flags",
          "columns": [
            {"name": "key", "type": "VARCHAR(100)", "constraints": "PRIMARY KEY"},
            {"name": "value", "type": "JSONB"},
            {"name": "rules", "type": "JSONB"},
            {"name": "updated_at", "type": "TIMESTAMPTZ"}
          ]
        }
      ]
    },
    "kafka": {
      "topics": [
        {
          "name": "search-impressions",
          "partitions": 64,
          "retention": "24h"
        },
        {
          "name": "search-clicks",
          "partitions": 64,
          "retention": "7d"
        },
        {
          "name": "ml-features",
          "partitions": 32,
          "description": "Real-time feature updates"
        },
        {
          "name": "index-updates",
          "partitions": 32,
          "description": "Cross-region index sync"
        }
      ]
    },
    "ml_feature_store": {
      "type": "Feast + BigQuery",
      "feature_groups": [
        {
          "name": "term_features",
          "features": [
            "popularity_score_7d",
            "ctr_7d",
            "trend_velocity",
            "seasonal_factor",
            "category_popularity",
            "entity_scores"
          ]
        },
        {
          "name": "user_features",
          "features": [
            "category_affinities",
            "price_sensitivity",
            "brand_preferences",
            "search_recency",
            "conversion_probability"
          ]
        },
        {
          "name": "query_features",
          "features": [
            "query_intent",
            "query_entities",
            "query_embedding",
            "historical_ctr"
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
      "description": "ML-powered autocomplete with semantic understanding",
      "query_params": {
        "q": "string (required)",
        "limit": "integer (default: 10)",
        "locale": "string (default: en-US)",
        "user_id": "string (optional)",
        "session_id": "string (optional)",
        "context": "string (optional, e.g., 'homepage', 'category_page')",
        "category": "string (optional)",
        "include_semantic": "boolean (default: true)",
        "include_trending": "boolean (default: true)"
      },
      "responses": {
        "200": {
          "query": "running shoe",
          "intent": "product_search",
          "entities": [
            {"type": "product_type", "value": "shoes"},
            {"type": "activity", "value": "running"}
          ],
          "suggestions": [
            {
              "term": "running shoes for men",
              "display": "Running Shoes for Men",
              "score": 0.95,
              "category": "footwear",
              "source": "semantic",
              "metadata": {
                "result_count": 15000,
                "avg_price": 89.99,
                "top_brand": "Nike"
              }
            },
            {
              "term": "running shoes women",
              "display": "Running Shoes Women",
              "score": 0.92,
              "category": "footwear",
              "source": "prefix"
            }
          ],
          "trending": [
            {"term": "marathon running shoes", "trend_score": 2.5}
          ],
          "personalized_boosts": ["Nike", "Adidas"],
          "ml_model": "ranking_v3.2",
          "latency_ms": 12
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/semantic-search",
      "description": "Pure semantic/vector similarity search",
      "query_params": {
        "q": "string (required)",
        "limit": "integer",
        "locale": "string",
        "threshold": "float (similarity threshold)"
      },
      "responses": {
        "200": {
          "query": "comfortable footwear for jogging",
          "suggestions": [
            {"term": "running shoes", "similarity": 0.89},
            {"term": "cushioned sneakers", "similarity": 0.85},
            {"term": "athletic shoes", "similarity": 0.82}
          ]
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/query-understand",
      "description": "Parse query intent and entities",
      "request_body": {
        "query": "string",
        "locale": "string"
      },
      "responses": {
        "200": {
          "query": "cheap nike running shoes size 10",
          "intent": "product_search",
          "entities": [
            {"type": "brand", "value": "Nike", "confidence": 0.99},
            {"type": "product_type", "value": "running shoes", "confidence": 0.95},
            {"type": "size", "value": "10", "confidence": 0.98},
            {"type": "price_modifier", "value": "cheap", "confidence": 0.90}
          ],
          "normalized_query": "nike running shoes",
          "filters_suggested": {
            "brand": "Nike",
            "size": "10",
            "price_range": "low"
          }
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/personalized-trending",
      "description": "Personalized trending suggestions",
      "query_params": {
        "user_id": "string",
        "locale": "string",
        "limit": "integer"
      },
      "responses": {
        "200": {
          "trending": [
            {
              "term": "running shoes sale",
              "trend_score": 3.2,
              "personalization_score": 0.85,
              "reason": "Based on your recent searches"
            }
          ],
          "recommended_searches": [
            {"term": "Nike Air Max", "reason": "Popular in your category"}
          ]
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics/ml-performance",
      "description": "ML model performance metrics",
      "query_params": {
        "model_id": "string",
        "start_date": "ISO8601",
        "end_date": "ISO8601"
      },
      "responses": {
        "200": {
          "model": "ranking_v3.2",
          "metrics": {
            "mrr": 0.72,
            "ndcg@10": 0.68,
            "ctr": 0.38,
            "conversion_rate": 0.045,
            "avg_latency_ms": 8
          },
          "comparison_to_baseline": {
            "mrr_lift": "+12%",
            "ctr_lift": "+8%"
          },
          "feature_importance": {
            "popularity_score": 0.25,
            "semantic_similarity": 0.22,
            "user_affinity": 0.18,
            "ctr_history": 0.15,
            "recency": 0.10,
            "other": 0.10
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/index/sync",
      "description": "Trigger cross-region index sync",
      "request_body": {
        "source_region": "string",
        "target_regions": ["string"],
        "incremental": "boolean"
      },
      "responses": {
        "202": {"job_id": "uuid", "status": "started"}
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                        Search Autocomplete - L7 Global Architecture
    ════════════════════════════════════════════════════════════════════════════════════

                                    ┌────────────────────┐
                                    │    Global DNS      │
                                    │   (Latency-based   │
                                    │    routing)        │
                                    └─────────┬──────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
              ▼                               ▼                               ▼
    ┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
    │   US-EAST-1      │           │   EU-WEST-1      │           │   AP-SOUTH-1     │
    └──────────────────┘           └──────────────────┘           └──────────────────┘
              │                               │                               │
              ▼                               ▼                               ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           PER-REGION ARCHITECTURE                                │
    │                                                                                  │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                          EDGE LAYER                                         │ │
    │  │                                                                             │ │
    │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │ │
    │  │  │   CDN Cache     │  │   API Gateway   │  │   Rate Limiter  │             │ │
    │  │  │   (CloudFlare)  │  │                 │  │                 │             │ │
    │  │  │                 │  │ • Auth          │  │ • Per-user      │             │ │
    │  │  │ • Query cache   │  │ • Routing       │  │ • Per-IP        │             │ │
    │  │  │ • 60s TTL       │  │ • Experiment    │  │ • Adaptive      │             │ │
    │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘             │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                                         ▼                                        │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                    AUTOCOMPLETE SERVICE CLUSTER                             │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                    QUERY UNDERSTANDING LAYER                          │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │ │
    │  │  │  │ Intent Classifier│  │ Entity Extractor│  │ Query Normalizer│       │  │ │
    │  │  │  │ (BERT-based)    │  │ (NER model)     │  │                 │       │  │ │
    │  │  │  │                 │  │                 │  │ • Spell correct │       │  │ │
    │  │  │  │ • product_search│  │ • Brand         │  │ • Tokenize      │       │  │ │
    │  │  │  │ • navigation    │  │ • Category      │  │ • Stem/lemma    │       │  │ │
    │  │  │  │ • informational │  │ • Attribute     │  │                 │       │  │ │
    │  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                    RETRIEVAL LAYER (Parallel)                         │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────┐ │  │ │
    │  │  │  │ Prefix Match  │ │ Semantic      │ │ Fuzzy Match   │ │ Personal  │ │  │ │
    │  │  │  │ (Redis ZSET)  │ │ (Vector DB)   │ │ (ES Suggest)  │ │ (History) │ │  │ │
    │  │  │  │               │ │               │ │               │ │           │ │  │ │
    │  │  │  │ • Exact prefix│ │ • Embedding   │ │ • Typo tol    │ │ • Recent  │ │  │ │
    │  │  │  │ • < 2ms       │ │   similarity  │ │ • Phonetic    │ │   searches│ │  │ │
    │  │  │  │               │ │ • < 5ms       │ │ • < 3ms       │ │ • Clicks  │ │  │ │
    │  │  │  └───────────────┘ └───────────────┘ └───────────────┘ └───────────┘ │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                    ML RANKING LAYER                                   │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  ┌─────────────────────────────────────────────────────────────────┐ │  │ │
    │  │  │  │                  Learning-to-Rank Model                         │ │  │ │
    │  │  │  │                  (XGBoost / Neural Ranker)                       │ │  │ │
    │  │  │  │                                                                  │ │  │ │
    │  │  │  │  Features:                                                       │ │  │ │
    │  │  │  │  • Query-term similarity (semantic + lexical)                    │ │  │ │
    │  │  │  │  • Term popularity (global + locale)                             │ │  │ │
    │  │  │  │  • User-term affinity (personalization)                          │ │  │ │
    │  │  │  │  • CTR history                                                   │ │  │ │
    │  │  │  │  • Recency/trending signals                                      │ │  │ │
    │  │  │  │  • Context features (page, device)                               │ │  │ │
    │  │  │  │  • Entity match score                                            │ │  │ │
    │  │  │  └─────────────────────────────────────────────────────────────────┘ │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  ┌─────────────────────┐  ┌─────────────────────┐                    │  │ │
    │  │  │  │ Personalization     │  │ Diversity/Dedup     │                    │  │ │
    │  │  │  │ Module              │  │ Module              │                    │  │ │
    │  │  │  │                     │  │                     │                    │  │ │
    │  │  │  │ • Category boost    │  │ • MMR reranking     │                    │  │ │
    │  │  │  │ • Brand affinity    │  │ • Category diversity│                    │  │ │
    │  │  │  │ • Price preference  │  │ • Deduplication     │                    │  │ │
    │  │  │  └─────────────────────┘  └─────────────────────┘                    │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    └─────────────────────────────────────────┼────────────────────────────────────────┘
                                              │
              ┌───────────────────────────────┼───────────────────────────────┐
              │                               │                               │
              ▼                               ▼                               ▼
    ┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
    │   Redis Cluster     │      │   Vector DB         │      │   Elasticsearch     │
    │   (Regional)        │      │   (Pinecone/Milvus) │      │   (Global)          │
    │                     │      │                     │      │                     │
    │ • Prefix index      │      │ • Term embeddings   │      │ • Fuzzy search      │
    │ • User models       │      │ • Query embeddings  │      │ • Full-text         │
    │ • Query cache       │      │ • 768-dim vectors   │      │ • Locale-aware      │
    │ • Trending          │      │ • Cosine similarity │      │                     │
    └─────────────────────┘      └─────────────────────┘      └─────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           ML PLATFORM                                            │
    │                                                                                  │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
    │  │  Feature Store      │  │  Model Serving      │  │  Training Pipeline  │      │
    │  │  (Feast)            │  │  (TensorFlow Serving)│  │  (Vertex AI)        │      │
    │  │                     │  │                     │  │                     │      │
    │  │ • Real-time features│  │ • Ranking model     │  │ • Daily retraining  │      │
    │  │ • User features     │  │ • Intent classifier │  │ • Embedding update  │      │
    │  │ • Term features     │  │ • Entity extractor  │  │ • A/B analysis      │      │
    │  │ • < 5ms latency     │  │ • < 5ms inference   │  │                     │      │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
    │                                                                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │                    EMBEDDING SERVICE                                     │   │
    │  │                                                                          │   │
    │  │  • Sentence-BERT for query embeddings                                    │   │
    │  │  • Real-time encoding (< 10ms)                                           │   │
    │  │  • Cached common queries                                                 │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                        REAL-TIME LEARNING PIPELINE                               │
    │                                                                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │                    Kafka Streams / Flink                                 │   │
    │  │                                                                          │   │
    │  │  Impressions ───┐                                                        │   │
    │  │                 ├──► Feature Updates ──► Redis ──► Ranking Model         │   │
    │  │  Clicks ────────┘                                                        │   │
    │  │                                                                          │   │
    │  │  • Real-time CTR calculation                                             │   │
    │  │  • Trending detection                                                    │   │
    │  │  • User model updates                                                    │   │
    │  │  • Anomaly detection                                                     │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                        GLOBAL COORDINATION                                       │
    │                                                                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │                    CockroachDB (Multi-Region)                            │   │
    │  │                                                                          │   │
    │  │  • Term metadata (source of truth)                                       │   │
    │  │  • ML model registry                                                     │   │
    │  │  • Feature flags                                                         │   │
    │  │  • Cross-region sync coordination                                        │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────────────┘
```

### ML-Powered Ranking Implementation

```python
import asyncio
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time

@dataclass
class QueryUnderstanding:
    intent: str
    entities: List[Dict]
    normalized_query: str
    query_embedding: np.ndarray
    confidence: float

@dataclass
class SuggestionCandidate:
    term: str
    display_term: str
    category: str
    source: str
    embedding: np.ndarray
    features: Dict[str, float]
    ml_score: float = 0.0

class AutocompleteServiceL7:
    """
    L7 Autocomplete with ML-powered ranking and semantic understanding.
    """

    def __init__(
        self,
        redis_cluster,
        vector_store,
        elasticsearch,
        model_service,
        feature_store,
        embedding_service
    ):
        self.redis = redis_cluster
        self.vector_store = vector_store
        self.es = elasticsearch
        self.models = model_service
        self.features = feature_store
        self.embeddings = embedding_service

    async def get_suggestions(
        self,
        query: str,
        locale: str = "en-US",
        user_id: str = None,
        session_id: str = None,
        context: str = None,
        limit: int = 10,
        include_semantic: bool = True,
        include_trending: bool = True
    ) -> Dict:
        """
        Get ML-ranked autocomplete suggestions.
        """
        start_time = time.time()

        # Step 1: Query Understanding
        query_understanding = await self._understand_query(query, locale)

        # Step 2: Parallel Retrieval from multiple sources
        retrieval_tasks = [
            self._get_prefix_matches(query_understanding, locale),
            self._get_fuzzy_matches(query_understanding, locale),
        ]

        if include_semantic:
            retrieval_tasks.append(
                self._get_semantic_matches(query_understanding, locale)
            )

        if user_id:
            retrieval_tasks.append(
                self._get_personalized_matches(query_understanding, user_id)
            )

        results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)

        # Merge candidates
        candidates = []
        for result in results:
            if isinstance(result, list):
                candidates.extend(result)

        # Deduplicate
        candidates = self._deduplicate(candidates)

        # Step 3: Feature Enrichment
        candidates = await self._enrich_features(
            candidates,
            query_understanding,
            user_id,
            context
        )

        # Step 4: ML Ranking
        ranked_candidates = await self._ml_rank(
            candidates,
            query_understanding,
            user_id
        )

        # Step 5: Post-processing (diversity, dedup)
        final_suggestions = self._post_process(ranked_candidates, limit)

        # Step 6: Get trending if requested
        trending = []
        if include_trending:
            trending = await self._get_personalized_trending(user_id, locale)

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "query": query,
            "intent": query_understanding.intent,
            "entities": query_understanding.entities,
            "suggestions": [self._format_suggestion(s) for s in final_suggestions],
            "trending": trending[:3],
            "personalized": user_id is not None,
            "ml_model": self.models.get_current_version("ranking"),
            "latency_ms": latency_ms
        }

    async def _understand_query(
        self,
        query: str,
        locale: str
    ) -> QueryUnderstanding:
        """
        Parse query intent and extract entities.
        """
        # Parallel: intent classification, entity extraction, embedding
        intent_task = self.models.predict_intent(query, locale)
        entity_task = self.models.extract_entities(query, locale)
        embedding_task = self.embeddings.encode(query)

        intent, entities, embedding = await asyncio.gather(
            intent_task,
            entity_task,
            embedding_task
        )

        # Normalize query (spell correct, lowercase, etc.)
        normalized = await self._normalize_query(query, locale)

        return QueryUnderstanding(
            intent=intent["label"],
            entities=entities,
            normalized_query=normalized,
            query_embedding=embedding,
            confidence=intent["confidence"]
        )

    async def _get_prefix_matches(
        self,
        query_understanding: QueryUnderstanding,
        locale: str
    ) -> List[SuggestionCandidate]:
        """
        Get exact prefix matches from Redis.
        """
        prefix = query_understanding.normalized_query.lower()
        region = self._get_region()

        key = f"ac:{region}:{locale}:{prefix}"
        results = self.redis.zrevrange(key, 0, 50, withscores=True)

        candidates = []
        for term_bytes, score in results:
            term = term_bytes.decode() if isinstance(term_bytes, bytes) else term_bytes

            # Get cached embedding
            embedding = await self._get_term_embedding(term)

            candidates.append(SuggestionCandidate(
                term=term,
                display_term=await self._get_display_term(term),
                category=await self._get_term_category(term),
                source="prefix",
                embedding=embedding,
                features={"base_score": score}
            ))

        return candidates

    async def _get_semantic_matches(
        self,
        query_understanding: QueryUnderstanding,
        locale: str
    ) -> List[SuggestionCandidate]:
        """
        Get semantically similar terms using vector search.
        """
        # Query vector store
        results = await self.vector_store.search(
            index="term_embeddings",
            vector=query_understanding.query_embedding,
            top_k=30,
            filter={"locale": locale}
        )

        candidates = []
        for match in results:
            # Skip if similarity too low
            if match["score"] < 0.7:
                continue

            candidates.append(SuggestionCandidate(
                term=match["metadata"]["term"],
                display_term=match["metadata"]["display_term"],
                category=match["metadata"]["category"],
                source="semantic",
                embedding=np.array(match["vector"]),
                features={
                    "semantic_similarity": match["score"],
                    "popularity": match["metadata"].get("popularity", 0)
                }
            ))

        return candidates

    async def _get_personalized_matches(
        self,
        query_understanding: QueryUnderstanding,
        user_id: str
    ) -> List[SuggestionCandidate]:
        """
        Get matches boosted by user history and preferences.
        """
        # Get user model
        user_model_key = f"user_model:{user_id}"
        user_model = self.redis.hgetall(user_model_key)

        if not user_model:
            return []

        # Get recent searches that match query
        recent_searches = user_model.get(b"last_searches", b"[]")
        recent_searches = json.loads(recent_searches.decode())

        prefix = query_understanding.normalized_query.lower()
        candidates = []

        for search in recent_searches:
            if search.lower().startswith(prefix):
                embedding = await self._get_term_embedding(search)
                candidates.append(SuggestionCandidate(
                    term=search,
                    display_term=search,
                    category="",
                    source="history",
                    embedding=embedding,
                    features={"personalization_score": 1.0}
                ))

        return candidates

    async def _enrich_features(
        self,
        candidates: List[SuggestionCandidate],
        query_understanding: QueryUnderstanding,
        user_id: str,
        context: str
    ) -> List[SuggestionCandidate]:
        """
        Enrich candidates with features for ML ranking.
        """
        # Get batch features from feature store
        term_ids = [c.term for c in candidates]

        term_features = await self.features.get_batch_features(
            entity_name="term",
            entity_ids=term_ids,
            feature_names=[
                "popularity_score_7d",
                "ctr_7d",
                "trend_velocity",
                "seasonal_factor"
            ]
        )

        user_features = {}
        if user_id:
            user_features = await self.features.get_features(
                entity_name="user",
                entity_id=user_id,
                feature_names=[
                    "category_affinities",
                    "brand_preferences",
                    "price_sensitivity"
                ]
            )

        for candidate in candidates:
            # Add term features
            tf = term_features.get(candidate.term, {})
            candidate.features.update({
                "popularity_7d": tf.get("popularity_score_7d", 0),
                "ctr_7d": tf.get("ctr_7d", 0),
                "trend_velocity": tf.get("trend_velocity", 0),
                "seasonal_factor": tf.get("seasonal_factor", 1.0)
            })

            # Add query-term features
            candidate.features["query_term_similarity"] = self._cosine_similarity(
                query_understanding.query_embedding,
                candidate.embedding
            )

            # Add user-term features
            if user_features:
                category_affinities = user_features.get("category_affinities", {})
                candidate.features["user_category_affinity"] = category_affinities.get(
                    candidate.category, 0
                )

            # Add context features
            candidate.features["context"] = self._encode_context(context)

            # Add entity match features
            candidate.features["entity_match"] = self._calculate_entity_match(
                query_understanding.entities,
                candidate.term
            )

        return candidates

    async def _ml_rank(
        self,
        candidates: List[SuggestionCandidate],
        query_understanding: QueryUnderstanding,
        user_id: str
    ) -> List[SuggestionCandidate]:
        """
        Apply ML ranking model to score candidates.
        """
        if not candidates:
            return []

        # Prepare feature vectors
        feature_vectors = []
        for candidate in candidates:
            features = [
                candidate.features.get("query_term_similarity", 0),
                candidate.features.get("popularity_7d", 0),
                candidate.features.get("ctr_7d", 0),
                candidate.features.get("trend_velocity", 0),
                candidate.features.get("seasonal_factor", 1.0),
                candidate.features.get("user_category_affinity", 0),
                candidate.features.get("entity_match", 0),
                candidate.features.get("personalization_score", 0),
                1.0 if candidate.source == "prefix" else 0.5,  # Source feature
            ]
            feature_vectors.append(features)

        # Batch prediction
        scores = await self.models.predict_ranking(
            model_name="ranking_model",
            features=feature_vectors
        )

        for candidate, score in zip(candidates, scores):
            candidate.ml_score = score

        # Sort by ML score
        candidates.sort(key=lambda x: x.ml_score, reverse=True)

        return candidates

    def _post_process(
        self,
        candidates: List[SuggestionCandidate],
        limit: int
    ) -> List[SuggestionCandidate]:
        """
        Post-process: diversity, deduplication, limit.
        """
        # MMR-style diversity: avoid too similar suggestions
        selected = []
        selected_embeddings = []

        for candidate in candidates:
            if len(selected) >= limit:
                break

            # Check diversity
            if selected_embeddings:
                max_sim = max(
                    self._cosine_similarity(candidate.embedding, e)
                    for e in selected_embeddings
                )
                if max_sim > 0.95:  # Too similar
                    continue

            selected.append(candidate)
            selected_embeddings.append(candidate.embedding)

        return selected

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate cosine similarity between vectors."""
        if v1 is None or v2 is None:
            return 0.0
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))


class RealTimeLearningPipeline:
    """
    Process events to update features and models in real-time.
    """

    def __init__(
        self,
        kafka_consumer,
        redis_cluster,
        feature_store
    ):
        self.kafka = kafka_consumer
        self.redis = redis_cluster
        self.features = feature_store

    async def process_click_event(self, event: Dict):
        """Update features based on click event."""
        term = event["selected_term"]
        position = event["position"]
        user_id = event.get("user_id")

        # Update term CTR
        await self._update_term_ctr(term)

        # Update user model
        if user_id:
            await self._update_user_model(user_id, term, event)

        # Update trending
        await self._update_trending(term, event.get("locale", "en-US"))

    async def _update_term_ctr(self, term: str):
        """Real-time CTR update with exponential decay."""
        # Increment click count
        click_key = f"term_clicks:{term}"
        impression_key = f"term_impressions:{term}"

        clicks = self.redis.incr(click_key)
        impressions = int(self.redis.get(impression_key) or 1)

        # Calculate smoothed CTR
        ctr = clicks / max(impressions, 1)

        # Update feature store
        await self.features.update_feature(
            entity_name="term",
            entity_id=term,
            feature_name="ctr_realtime",
            value=ctr
        )

    async def _update_user_model(
        self,
        user_id: str,
        term: str,
        event: Dict
    ):
        """Update user preference model."""
        user_key = f"user_model:{user_id}"

        # Update recent searches
        self.redis.lpush(f"{user_key}:searches", term)
        self.redis.ltrim(f"{user_key}:searches", 0, 99)

        # Update category affinity
        category = await self._get_term_category(term)
        if category:
            self.redis.hincrby(f"{user_key}:categories", category, 1)

    async def _update_trending(self, term: str, locale: str):
        """Update trending scores."""
        region = self._get_region()
        window = int(time.time() // 3600)  # Hourly window

        key = f"trending:{region}:{locale}:{window}"
        self.redis.zincrby(key, 1, term)
        self.redis.expire(key, 7200)  # 2 hour expiry
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Intent classification | Product search query | Intent = "product_search" |
| F-02 | Entity extraction | "Nike shoes size 10" | Brand, type, size extracted |
| F-03 | Semantic match | "comfortable footwear" | Returns "running shoes" |
| F-04 | Cross-region serving | US query from EU | Served from EU region |
| F-05 | Locale-aware | Query in French | French suggestions |
| F-06 | Personalization | User with history | History items boosted |
| F-07 | ML ranking | Multiple candidates | ML score determines order |
| F-08 | Diversity | Similar terms | Diverse results returned |
| F-09 | Real-time learning | Click event | CTR updated immediately |
| F-10 | Trending | Popular searches | Shown in results |
| F-11 | Entity boost | Brand mentioned | Brand products boosted |
| F-12 | Zero-shot | New query | Semantic fallback works |
| F-13 | Spell correction | "iphne" | Corrected to "iphone" |
| F-14 | Multi-source merge | All sources | Properly deduplicated |
| F-15 | Feature enrichment | All features | Complete feature vector |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Total latency | End-to-end | < 25ms p99 |
| P-02 | Intent model | Classification | < 5ms |
| P-03 | Entity model | Extraction | < 5ms |
| P-04 | Embedding | Query encoding | < 8ms |
| P-05 | Vector search | Semantic match | < 5ms |
| P-06 | Feature fetch | Feature store | < 3ms |
| P-07 | ML ranking | Batch scoring | < 5ms |
| P-08 | Throughput | Global QPS | > 500K |
| P-09 | Cross-region | Inter-region | < 50ms |
| P-10 | Cache hit rate | Query cache | > 80% |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | ML service down | Model unavailable | Fallback to heuristic |
| C-02 | Vector DB down | Pinecone unavailable | Skip semantic search |
| C-03 | Region failure | US-EAST down | Route to EU-WEST |
| C-04 | Feature store lag | Stale features | Use cached features |
| C-05 | Embedding service | Slow encoding | Timeout, skip semantic |
| C-06 | Kafka backlog | Event lag | Eventual consistency |
| C-07 | Hot query | 1M QPS single query | Cache absorbs |
| C-08 | Model deployment | New model rollout | Zero-downtime |
| C-09 | Index corruption | Invalid data | Rebuild from source |
| C-10 | Cross-region sync | Sync failure | Regions independent |

### ML Model Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| M-01 | Ranking accuracy | MRR metric | > 0.70 |
| M-02 | Intent accuracy | Classification | > 90% |
| M-03 | Entity recall | NER extraction | > 85% |
| M-04 | Embedding quality | Semantic similarity | Correlation > 0.8 |
| M-05 | Online learning | Feature updates | CTR improves |
| M-06 | Cold start | New terms | Reasonable ranking |
| M-07 | Bias detection | Fairness check | No systematic bias |

---

## Capacity Estimates

### Global Scale

- **Terms**: 100M across all locales
- **Queries per second**: 500K globally
- **Regions**: 3 (US, EU, APAC)
- **Locales**: 20+
- **Users**: 500M

### Per-Region Resources

- **Redis cluster**: 12 nodes, 100GB total
- **Vector DB**: 50GB embeddings
- **ML serving**: 20 GPU instances
- **Application**: 100 instances (auto-scaled)

### ML Platform

- **Embedding dimensions**: 768
- **Ranking model size**: 100MB
- **Feature store**: 500GB
- **Training data**: 10TB (90-day)

### Latency Budget

- **Query understanding**: < 10ms
- **Retrieval (parallel)**: < 5ms
- **Feature enrichment**: < 5ms
- **ML ranking**: < 5ms
- **Total**: < 25ms p99

---

## Key Considerations for L7

1. **ML integration**: Query understanding, semantic search, learning-to-rank
2. **Global scale**: Multi-region with locale-aware serving
3. **Real-time learning**: Continuous feature updates from user behavior
4. **Semantic search**: Vector embeddings for conceptual matching
5. **Personalization**: User models for preference-based ranking
6. **Observability**: ML model monitoring, A/B testing
7. **Cost efficiency**: Caching, model optimization, infrastructure scaling
