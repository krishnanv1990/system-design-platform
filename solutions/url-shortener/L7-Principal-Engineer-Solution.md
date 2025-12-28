# URL Shortener - L7 (Principal Engineer) Solution

## Level Requirements

**Target Role:** Principal Engineer (L7)
**Focus:** Global-scale architecture with advanced optimizations

### What's Expected at L7

- Everything from L5 and L6, plus:
- Global multi-region active-active architecture
- Advanced sharding strategies (consistent hashing)
- Custom protocol optimizations
- Zero-downtime deployments and migrations
- Advanced security (DDoS mitigation, fraud detection)
- Cost optimization strategies
- Compliance (GDPR, SOC2)
- ML-based analytics and spam detection
- Edge computing for ultra-low latency
- Disaster recovery with RPO/RTO guarantees

---

## Database Schema

```json
{
  "primary_database": "CockroachDB (Distributed SQL)",
  "analytics_database": "ClickHouse (Columnar)",
  "cache_layer": "Redis Cluster + Local LRU",
  "message_queue": "Apache Kafka",

  "tables": [
    {
      "name": "urls",
      "database": "CockroachDB",
      "description": "Globally distributed URL mappings",
      "columns": [
        {"name": "short_code", "type": "STRING(10)", "constraints": "PRIMARY KEY"},
        {"name": "original_url", "type": "STRING", "constraints": "NOT NULL"},
        {"name": "original_url_hash", "type": "BYTES", "constraints": "NOT NULL", "note": "SHA-256 for dedup"},
        {"name": "user_id", "type": "UUID", "constraints": "REFERENCES users(id)"},
        {"name": "created_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"},
        {"name": "expires_at", "type": "TIMESTAMPTZ"},
        {"name": "click_count", "type": "INT8", "constraints": "DEFAULT 0"},
        {"name": "last_accessed_at", "type": "TIMESTAMPTZ"},
        {"name": "is_active", "type": "BOOL", "constraints": "DEFAULT true"},
        {"name": "redirect_type", "type": "INT2", "constraints": "DEFAULT 302"},
        {"name": "metadata", "type": "JSONB", "constraints": "DEFAULT '{}'"},
        {"name": "geo_restrictions", "type": "STRING[]", "note": "Country codes"},
        {"name": "password_hash", "type": "BYTES", "note": "Optional link protection"},
        {"name": "spam_score", "type": "FLOAT4", "constraints": "DEFAULT 0"},
        {"name": "created_region", "type": "STRING(20)", "constraints": "NOT NULL"}
      ],
      "indexes": [
        {"name": "idx_urls_short_code_region", "columns": ["short_code", "created_region"], "type": "STORING", "storing": ["original_url", "expires_at", "is_active"]},
        {"name": "idx_urls_user_id", "columns": ["user_id", "created_at DESC"]},
        {"name": "idx_urls_original_hash", "columns": ["original_url_hash"], "note": "For deduplication lookups"},
        {"name": "idx_urls_expires", "columns": ["expires_at"], "where": "expires_at IS NOT NULL AND is_active = true"}
      ],
      "partitioning": {
        "type": "HASH",
        "column": "short_code",
        "partitions": 256,
        "note": "Consistent hashing for predictable data placement"
      },
      "locality": {
        "type": "REGIONAL BY ROW",
        "column": "created_region",
        "regions": ["us-east1", "us-west1", "europe-west1", "asia-east1"]
      }
    },
    {
      "name": "users",
      "database": "CockroachDB",
      "description": "User accounts with enterprise features",
      "columns": [
        {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
        {"name": "email", "type": "STRING(255)", "constraints": "UNIQUE NOT NULL"},
        {"name": "api_key_hash", "type": "BYTES", "constraints": "UNIQUE NOT NULL"},
        {"name": "organization_id", "type": "UUID", "constraints": "REFERENCES organizations(id)"},
        {"name": "tier", "type": "STRING(20)", "constraints": "DEFAULT 'free'"},
        {"name": "rate_limit_override", "type": "INT4"},
        {"name": "monthly_quota", "type": "INT8"},
        {"name": "urls_created_total", "type": "INT8", "constraints": "DEFAULT 0"},
        {"name": "created_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"},
        {"name": "last_active_at", "type": "TIMESTAMPTZ"},
        {"name": "settings", "type": "JSONB", "constraints": "DEFAULT '{}'"},
        {"name": "gdpr_consent_at", "type": "TIMESTAMPTZ"},
        {"name": "data_retention_days", "type": "INT4", "constraints": "DEFAULT 365"}
      ]
    },
    {
      "name": "organizations",
      "database": "CockroachDB",
      "description": "Enterprise organization accounts",
      "columns": [
        {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
        {"name": "name", "type": "STRING(255)", "constraints": "NOT NULL"},
        {"name": "custom_domain", "type": "STRING(255)", "constraints": "UNIQUE"},
        {"name": "sso_config", "type": "JSONB"},
        {"name": "tier", "type": "STRING(20)", "constraints": "DEFAULT 'enterprise'"},
        {"name": "monthly_quota", "type": "INT8"},
        {"name": "custom_rate_limits", "type": "JSONB"},
        {"name": "webhook_url", "type": "STRING"},
        {"name": "created_at", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"}
      ]
    },
    {
      "name": "kgs_keys",
      "database": "CockroachDB",
      "description": "Distributed key generation with region affinity",
      "columns": [
        {"name": "short_code", "type": "STRING(10)", "constraints": "PRIMARY KEY"},
        {"name": "region", "type": "STRING(20)", "constraints": "NOT NULL"},
        {"name": "allocated_at", "type": "TIMESTAMPTZ"},
        {"name": "batch_id", "type": "INT8", "constraints": "NOT NULL"}
      ],
      "partitioning": {
        "type": "LIST",
        "column": "region",
        "partitions": {
          "us_east": ["us-east1", "us-east4"],
          "us_west": ["us-west1", "us-west2"],
          "europe": ["europe-west1", "europe-west4"],
          "asia": ["asia-east1", "asia-northeast1"]
        }
      }
    },
    {
      "name": "click_events",
      "database": "ClickHouse",
      "description": "High-volume analytics with columnar storage",
      "columns": [
        {"name": "event_id", "type": "UUID", "constraints": "DEFAULT generateUUIDv4()"},
        {"name": "short_code", "type": "LowCardinality(String)"},
        {"name": "clicked_at", "type": "DateTime64(3)"},
        {"name": "user_id", "type": "Nullable(UUID)"},
        {"name": "referrer_domain", "type": "LowCardinality(String)"},
        {"name": "user_agent", "type": "String"},
        {"name": "ip_hash", "type": "FixedString(32)"},
        {"name": "country", "type": "LowCardinality(FixedString(2))"},
        {"name": "city", "type": "LowCardinality(String)"},
        {"name": "device_type", "type": "Enum8('desktop'=1, 'mobile'=2, 'tablet'=3, 'bot'=4)"},
        {"name": "browser", "type": "LowCardinality(String)"},
        {"name": "os", "type": "LowCardinality(String)"},
        {"name": "is_unique", "type": "UInt8"},
        {"name": "response_time_ms", "type": "UInt16"},
        {"name": "region", "type": "LowCardinality(String)"}
      ],
      "engine": "MergeTree()",
      "partition_by": "toYYYYMMDD(clicked_at)",
      "order_by": "(short_code, clicked_at)",
      "ttl": "clicked_at + INTERVAL 90 DAY",
      "settings": {
        "index_granularity": 8192,
        "enable_mixed_granularity_parts": 1
      }
    },
    {
      "name": "spam_signals",
      "database": "ClickHouse",
      "description": "ML feature store for spam detection",
      "columns": [
        {"name": "short_code", "type": "String"},
        {"name": "computed_at", "type": "DateTime"},
        {"name": "click_velocity", "type": "Float32"},
        {"name": "unique_ip_ratio", "type": "Float32"},
        {"name": "bot_traffic_ratio", "type": "Float32"},
        {"name": "geographic_entropy", "type": "Float32"},
        {"name": "referrer_diversity", "type": "Float32"},
        {"name": "predicted_spam_score", "type": "Float32"},
        {"name": "model_version", "type": "String"}
      ],
      "engine": "ReplacingMergeTree(computed_at)",
      "order_by": "short_code"
    },
    {
      "name": "audit_log",
      "database": "CockroachDB",
      "description": "Compliance audit trail",
      "columns": [
        {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
        {"name": "timestamp", "type": "TIMESTAMPTZ", "constraints": "DEFAULT now()"},
        {"name": "actor_id", "type": "UUID"},
        {"name": "actor_type", "type": "STRING(20)"},
        {"name": "action", "type": "STRING(50)", "constraints": "NOT NULL"},
        {"name": "resource_type", "type": "STRING(50)"},
        {"name": "resource_id", "type": "STRING(100)"},
        {"name": "old_value", "type": "JSONB"},
        {"name": "new_value", "type": "JSONB"},
        {"name": "ip_address", "type": "INET"},
        {"name": "user_agent", "type": "STRING"},
        {"name": "region", "type": "STRING(20)"}
      ],
      "retention": "7 years (compliance requirement)"
    }
  ]
}
```

---

## API Specification

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "URL Shortener API - Enterprise",
    "version": "3.0.0",
    "description": "Global-scale URL shortening service with enterprise features"
  },
  "servers": [
    {"url": "https://api.short.url/v3", "description": "Global endpoint (GeoDNS)"},
    {"url": "https://us.api.short.url/v3", "description": "US region"},
    {"url": "https://eu.api.short.url/v3", "description": "EU region (GDPR)"},
    {"url": "https://ap.api.short.url/v3", "description": "Asia-Pacific region"}
  ],
  "security": [
    {"ApiKeyAuth": []},
    {"OAuth2": ["read", "write", "admin"]}
  ],
  "endpoints": [
    {
      "method": "POST",
      "path": "/urls",
      "description": "Create shortened URL with advanced options",
      "headers": {
        "Authorization": "Bearer {token} or X-API-Key: {key}",
        "X-Idempotency-Key": "UUID (required for retries)",
        "X-Request-ID": "UUID (optional, for tracing)",
        "X-Preferred-Region": "string (optional, geo hint)"
      },
      "request_body": {
        "original_url": "string (required, max 2048 chars)",
        "custom_alias": "string (optional, 4-20 chars, alphanumeric)",
        "expires_at": "ISO8601 timestamp (optional)",
        "redirect_type": "301 | 302 | 307 | 308 (default: 302)",
        "password": "string (optional, link protection)",
        "geo_restrictions": {
          "allow": ["US", "CA", "GB"],
          "deny": ["CN", "RU"]
        },
        "metadata": {
          "campaign_id": "string",
          "source": "string",
          "medium": "string",
          "custom": {}
        },
        "options": {
          "enable_analytics": "boolean (default: true)",
          "enable_qr": "boolean (default: true)",
          "deduplicate": "boolean (default: false)"
        }
      },
      "responses": {
        "201": {
          "data": {
            "short_code": "string",
            "short_url": "string",
            "original_url": "string",
            "created_at": "ISO8601",
            "expires_at": "ISO8601 | null",
            "qr_code": {
              "svg": "string (data URI)",
              "png_url": "string"
            }
          },
          "meta": {
            "region": "string",
            "request_id": "UUID"
          }
        },
        "400": {"error": {"code": "VALIDATION_ERROR", "message": "string", "details": []}},
        "401": {"error": {"code": "UNAUTHORIZED", "message": "string"}},
        "403": {"error": {"code": "FORBIDDEN", "message": "string"}},
        "409": {"error": {"code": "CONFLICT", "message": "Alias already exists"}},
        "422": {"error": {"code": "SPAM_DETECTED", "message": "URL flagged as spam"}},
        "429": {"error": {"code": "RATE_LIMITED", "retry_after": "integer", "limit": "string"}}
      }
    },
    {
      "method": "GET",
      "path": "/urls/{short_code}",
      "description": "Get URL details with analytics",
      "query_params": {
        "include": "analytics,qr_code (comma-separated)"
      },
      "responses": {
        "200": {
          "data": {
            "short_code": "string",
            "original_url": "string",
            "created_at": "ISO8601",
            "expires_at": "ISO8601 | null",
            "is_active": "boolean",
            "redirect_type": "integer",
            "click_count": "integer",
            "analytics": {
              "total_clicks": "integer",
              "unique_visitors": "integer",
              "clicks_today": "integer",
              "clicks_this_week": "integer",
              "top_countries": [{"code": "string", "count": "integer"}],
              "top_referrers": [{"domain": "string", "count": "integer"}],
              "devices": {"desktop": "integer", "mobile": "integer", "tablet": "integer"},
              "hourly_distribution": [{"hour": "integer", "count": "integer"}]
            },
            "qr_code": {
              "svg": "string",
              "png_url": "string"
            }
          }
        }
      }
    },
    {
      "method": "GET",
      "path": "/{short_code}",
      "description": "Redirect endpoint (public, ultra-low latency)",
      "headers": {
        "X-Forwarded-For": "IP for geo lookup",
        "User-Agent": "For device detection"
      },
      "responses": {
        "301": {"description": "Permanent redirect"},
        "302": {"description": "Temporary redirect (default)"},
        "307": {"description": "Temporary redirect (preserve method)"},
        "308": {"description": "Permanent redirect (preserve method)"},
        "401": {"description": "Password required (if protected)"},
        "403": {"description": "Geo-restricted"},
        "404": {"description": "Not found"},
        "410": {"description": "Expired"}
      },
      "performance": {
        "target_latency_p50": "5ms",
        "target_latency_p99": "20ms",
        "edge_cached": true
      }
    },
    {
      "method": "POST",
      "path": "/urls/{short_code}/verify-password",
      "description": "Verify password for protected links",
      "request_body": {
        "password": "string"
      },
      "responses": {
        "200": {"redirect_url": "string", "token": "string (JWT, valid 1 hour)"},
        "401": {"error": "Invalid password"}
      }
    },
    {
      "method": "GET",
      "path": "/urls/{short_code}/analytics",
      "description": "Detailed analytics with custom date ranges",
      "query_params": {
        "start_date": "ISO8601",
        "end_date": "ISO8601",
        "granularity": "minute | hour | day | week | month",
        "group_by": "country | referrer | device | browser",
        "limit": "integer (max 1000)"
      },
      "responses": {
        "200": {
          "data": {
            "time_series": [{"timestamp": "ISO8601", "clicks": "integer", "unique": "integer"}],
            "aggregations": {},
            "funnel": {}
          },
          "meta": {
            "query_time_ms": "integer",
            "rows_scanned": "integer"
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/urls/bulk",
      "description": "Bulk URL creation (up to 1000)",
      "request_body": {
        "urls": [{"original_url": "string", "custom_alias": "string"}],
        "defaults": {
          "expires_in_days": "integer",
          "metadata": {}
        }
      },
      "responses": {
        "201": {"data": {"successful": [], "failed": []}},
        "207": {"data": {"successful": [], "failed": []}}
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Comprehensive health check",
      "responses": {
        "200": {
          "status": "healthy | degraded | unhealthy",
          "version": "string",
          "region": "string",
          "components": {
            "database": {"status": "string", "latency_ms": "integer"},
            "cache": {"status": "string", "hit_ratio": "float"},
            "kgs": {"status": "string", "pool_size": "integer"},
            "analytics": {"status": "string", "lag_seconds": "integer"}
          },
          "timestamp": "ISO8601"
        }
      }
    },
    {
      "method": "POST",
      "path": "/webhooks",
      "description": "Configure webhooks for events",
      "request_body": {
        "url": "string (HTTPS required)",
        "events": ["url.created", "url.clicked", "url.expired", "quota.warning"],
        "secret": "string (for HMAC verification)"
      }
    },
    {
      "method": "GET",
      "path": "/export",
      "description": "GDPR data export",
      "responses": {
        "202": {"job_id": "UUID", "estimated_time_seconds": "integer"},
        "200": {"download_url": "string (signed, expires in 1 hour)"}
      }
    },
    {
      "method": "DELETE",
      "path": "/account",
      "description": "GDPR right to deletion",
      "responses": {
        "202": {"message": "Deletion scheduled", "completion_date": "ISO8601"}
      }
    }
  ],
  "rate_limits": {
    "free": {"requests_per_minute": 60, "urls_per_day": 100},
    "pro": {"requests_per_minute": 600, "urls_per_day": 10000},
    "business": {"requests_per_minute": 3000, "urls_per_day": 100000},
    "enterprise": {"requests_per_minute": "custom", "urls_per_day": "unlimited"}
  }
}
```

---

## System Design

### Global Architecture

```
                         URL Shortener - L7 Global Architecture
    ════════════════════════════════════════════════════════════════════════════════

                                    ┌─────────────────┐
                                    │   GeoDNS        │
                                    │  (Route 53)     │
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
              ▼                              ▼                              ▼
    ┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
    │   EDGE: Americas    │      │   EDGE: Europe      │      │   EDGE: Asia-Pac    │
    │   (50+ PoPs)        │      │   (30+ PoPs)        │      │   (40+ PoPs)        │
    │                     │      │                     │      │                     │
    │ • CloudFlare Workers│      │ • CloudFlare Workers│      │ • CloudFlare Workers│
    │ • Edge KV Cache     │      │ • Edge KV Cache     │      │ • Edge KV Cache     │
    │ • DDoS Mitigation   │      │ • DDoS Mitigation   │      │ • DDoS Mitigation   │
    │ • Bot Detection     │      │ • Bot Detection     │      │ • Bot Detection     │
    └──────────┬──────────┘      └──────────┬──────────┘      └──────────┬──────────┘
               │                            │                            │
    ═══════════╪════════════════════════════╪════════════════════════════╪═══════════
               │                            │                            │
               ▼                            ▼                            ▼
    ╔═══════════════════════════════════════════════════════════════════════════════╗
    ║                         REGIONAL CLUSTERS                                      ║
    ╠═══════════════════════════════════════════════════════════════════════════════╣
    ║                                                                                ║
    ║  ┌────────────────────────────────────────────────────────────────────────┐   ║
    ║  │                      US-EAST (Primary)                                  │   ║
    ║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │   ║
    ║  │  │ API Gateway  │  │ API Gateway  │  │ API Gateway  │                  │   ║
    ║  │  │ (Kong/Envoy) │  │ (Kong/Envoy) │  │ (Kong/Envoy) │                  │   ║
    ║  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │   ║
    ║  │         └─────────────────┼─────────────────┘                          │   ║
    ║  │                           │                                            │   ║
    ║  │  ┌────────────────────────┴────────────────────────┐                   │   ║
    ║  │  │              Kubernetes Cluster                  │                   │   ║
    ║  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│                   │   ║
    ║  │  │  │URL Svc  │ │Redirect │ │Analytics│ │ KGS     ││                   │   ║
    ║  │  │  │(50 pods)│ │Svc (100)│ │Svc (20) │ │Svc (10) ││                   │   ║
    ║  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘│                   │   ║
    ║  │  └─────────────────────────────────────────────────┘                   │   ║
    ║  │                           │                                            │   ║
    ║  │  ┌────────────────────────┴────────────────────────┐                   │   ║
    ║  │  │              Data Layer                          │                   │   ║
    ║  │  │  ┌──────────────┐      ┌──────────────┐         │                   │   ║
    ║  │  │  │ Redis Cluster│      │ CockroachDB  │         │                   │   ║
    ║  │  │  │ (12 nodes)   │      │ (9 nodes)    │         │                   │   ║
    ║  │  │  └──────────────┘      └──────────────┘         │                   │   ║
    ║  │  └─────────────────────────────────────────────────┘                   │   ║
    ║  └────────────────────────────────────────────────────────────────────────┘   ║
    ║                                                                                ║
    ║  ┌────────────────────────────────────────────────────────────────────────┐   ║
    ║  │                      EU-WEST (GDPR Region)                              │   ║
    ║  │  [Similar structure - data stays in EU]                                 │   ║
    ║  └────────────────────────────────────────────────────────────────────────┘   ║
    ║                                                                                ║
    ║  ┌────────────────────────────────────────────────────────────────────────┐   ║
    ║  │                      ASIA-EAST                                          │   ║
    ║  │  [Similar structure]                                                    │   ║
    ║  └────────────────────────────────────────────────────────────────────────┘   ║
    ╚═══════════════════════════════════════════════════════════════════════════════╝

    ╔═══════════════════════════════════════════════════════════════════════════════╗
    ║                         GLOBAL DATA PLANE                                      ║
    ╠═══════════════════════════════════════════════════════════════════════════════╣
    ║                                                                                ║
    ║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
    ║  │                  CockroachDB Global Cluster                              │  ║
    ║  │                                                                          │  ║
    ║  │    US-EAST           US-WEST          EU-WEST         ASIA-EAST          │  ║
    ║  │   ┌───────┐         ┌───────┐        ┌───────┐       ┌───────┐           │  ║
    ║  │   │Node 1 │◄───────►│Node 4 │◄──────►│Node 7 │◄─────►│Node 10│           │  ║
    ║  │   │Node 2 │         │Node 5 │        │Node 8 │       │Node 11│           │  ║
    ║  │   │Node 3 │         │Node 6 │        │Node 9 │       │Node 12│           │  ║
    ║  │   └───────┘         └───────┘        └───────┘       └───────┘           │  ║
    ║  │              Raft Consensus + Multi-region Replication                   │  ║
    ║  └─────────────────────────────────────────────────────────────────────────┘  ║
    ║                                                                                ║
    ╚═══════════════════════════════════════════════════════════════════════════════╝

    ╔═══════════════════════════════════════════════════════════════════════════════╗
    ║                      ANALYTICS & ML PIPELINE                                   ║
    ╠═══════════════════════════════════════════════════════════════════════════════╣
    ║                                                                                ║
    ║  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐  ║
    ║  │  Kafka   │───►│  Flink   │───►│ClickHouse│───►│   ML     │───►│ Grafana │  ║
    ║  │ (Events) │    │(Process) │    │(Analytics)│    │ Models   │    │(Dashbd) │  ║
    ║  │ 3 DC rep │    │(Stateful)│    │(Sharded)  │    │(Spam/Bot)│    │         │  ║
    ║  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └─────────┘  ║
    ║       │                                               │                       ║
    ║       └───────────────────────────────────────────────┘                       ║
    ║                    Feedback loop for spam detection                           ║
    ╚═══════════════════════════════════════════════════════════════════════════════╝
```

### Edge Computing Layer (CloudFlare Workers)

```javascript
// Edge worker for ultra-low latency redirects
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const shortCode = url.pathname.slice(1);

    if (!shortCode || shortCode.includes('/')) {
      return fetch(request); // Pass to origin
    }

    // Check edge KV cache first (< 1ms)
    const cached = await env.URL_CACHE.get(shortCode, { type: 'json' });
    if (cached) {
      // Async analytics (fire and forget)
      env.ANALYTICS.writeDataPoint({
        blobs: [shortCode, request.headers.get('CF-IPCountry')],
        indexes: [shortCode]
      });

      if (cached.expires_at && Date.now() > cached.expires_at) {
        return new Response('Gone', { status: 410 });
      }

      return Response.redirect(cached.original_url, cached.redirect_type || 302);
    }

    // Cache miss - fetch from regional origin
    const response = await fetch(`${env.ORIGIN_URL}/internal/resolve/${shortCode}`, {
      headers: { 'X-Edge-Request': 'true' }
    });

    if (response.ok) {
      const data = await response.json();
      // Cache at edge with TTL
      await env.URL_CACHE.put(shortCode, JSON.stringify(data), {
        expirationTtl: 3600 // 1 hour
      });
      return Response.redirect(data.original_url, data.redirect_type || 302);
    }

    return response;
  }
};
```

### Consistent Hashing for Sharding

```python
import hashlib
from bisect import bisect_left
from typing import List, Optional

class ConsistentHash:
    """
    Consistent hashing ring for data distribution.
    Used for both cache and database sharding.
    """

    def __init__(self, nodes: List[str], virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []

        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        """Generate hash for key."""
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        """Add a node with virtual nodes for better distribution."""
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_val = self._hash(virtual_key)
            self.ring[hash_val] = node
            self.sorted_keys.append(hash_val)
        self.sorted_keys.sort()

    def remove_node(self, node: str):
        """Remove a node and its virtual nodes."""
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_val = self._hash(virtual_key)
            del self.ring[hash_val]
            self.sorted_keys.remove(hash_val)

    def get_node(self, key: str) -> str:
        """Get the node responsible for a key."""
        if not self.ring:
            return None

        hash_val = self._hash(key)
        idx = bisect_left(self.sorted_keys, hash_val)

        if idx == len(self.sorted_keys):
            idx = 0

        return self.ring[self.sorted_keys[idx]]

    def get_nodes(self, key: str, count: int = 3) -> List[str]:
        """Get multiple nodes for replication."""
        nodes = []
        if not self.ring:
            return nodes

        hash_val = self._hash(key)
        idx = bisect_left(self.sorted_keys, hash_val)

        seen = set()
        while len(nodes) < count and len(seen) < len(self.ring):
            if idx >= len(self.sorted_keys):
                idx = 0
            node = self.ring[self.sorted_keys[idx]]
            if node not in seen:
                nodes.append(node)
                seen.add(node)
            idx += 1

        return nodes
```

### ML-Based Spam Detection

```python
import numpy as np
from sklearn.ensemble import IsolationForest
from dataclasses import dataclass

@dataclass
class URLFeatures:
    url_length: int
    domain_age_days: int
    has_ip_address: bool
    suspicious_tld: bool
    entropy: float
    special_char_ratio: float
    digit_ratio: float
    subdomain_count: int

class SpamDetector:
    """
    ML-based spam and malicious URL detection.
    Uses ensemble of models for high accuracy.
    """

    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        self.known_malicious_patterns = self._load_patterns()

    def extract_features(self, url: str) -> URLFeatures:
        """Extract features from URL for ML model."""
        from urllib.parse import urlparse
        import math

        parsed = urlparse(url)
        domain = parsed.netloc

        # Calculate entropy
        prob = [float(url.count(c)) / len(url) for c in set(url)]
        entropy = -sum([p * math.log2(p) for p in prob if p > 0])

        return URLFeatures(
            url_length=len(url),
            domain_age_days=self._get_domain_age(domain),
            has_ip_address=self._is_ip_address(domain),
            suspicious_tld=self._is_suspicious_tld(domain),
            entropy=entropy,
            special_char_ratio=sum(1 for c in url if not c.isalnum()) / len(url),
            digit_ratio=sum(1 for c in url if c.isdigit()) / len(url),
            subdomain_count=domain.count('.')
        )

    def predict_spam_score(self, url: str) -> float:
        """
        Returns spam probability score (0-1).
        Higher score = more likely spam.
        """
        features = self.extract_features(url)
        feature_vector = np.array([[
            features.url_length,
            features.entropy,
            features.special_char_ratio,
            features.digit_ratio,
            features.subdomain_count,
            int(features.has_ip_address),
            int(features.suspicious_tld)
        ]])

        # Isolation Forest returns -1 for outliers, 1 for inliers
        anomaly_score = self.isolation_forest.decision_function(feature_vector)[0]

        # Convert to 0-1 probability
        spam_score = 1 / (1 + np.exp(anomaly_score))

        # Boost score for known patterns
        if self._matches_known_pattern(url):
            spam_score = max(spam_score, 0.9)

        return spam_score
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Create URL | POST with valid URL | 201 Created |
| F-02 | Custom Alias | POST with custom alias | 201 with alias |
| F-03 | Duplicate Alias | POST existing alias | 409 Conflict |
| F-04 | Password Protected | Create with password | 201, requires auth |
| F-05 | Geo Restriction | Create with geo rules | Enforced on redirect |
| F-06 | Redirect 301/302/307/308 | Different redirect types | Correct status code |
| F-07 | Expired URL | Access expired URL | 410 Gone |
| F-08 | Bulk Create | Create 1000 URLs | 201/207 partial |
| F-09 | Analytics Query | Complex date range | Correct aggregations |
| F-10 | Webhook Delivery | URL events | Webhook called |
| F-11 | GDPR Export | Request data export | ZIP with all data |
| F-12 | GDPR Delete | Request deletion | Data purged |
| F-13 | Spam Detection | Submit malicious URL | 422 Rejected |
| F-14 | Rate Limiting | Exceed limits | 429 with headers |
| F-15 | Idempotency | Retry with same key | Same response |
| F-16 | Custom Domain | Organization domain | Works correctly |
| F-17 | SSO Login | Enterprise SSO | Authenticated |
| F-18 | API Versioning | v2 vs v3 endpoints | Both work |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Edge Redirect (cache hit) | Redirect from edge | < 5ms p99 |
| P-02 | Edge Redirect (cache miss) | With origin fetch | < 50ms p99 |
| P-03 | URL Creation | Create new URL | < 100ms p99 |
| P-04 | Bulk Creation | 1000 URLs | < 10s total |
| P-05 | Analytics Query (1 day) | Single day stats | < 100ms |
| P-06 | Analytics Query (90 days) | 90-day aggregation | < 2s |
| P-07 | Global Read Throughput | All regions combined | > 1M RPS |
| P-08 | Global Write Throughput | All regions combined | > 100K RPS |
| P-09 | KGS Key Generation | Key generation rate | > 100K/sec |
| P-10 | Cross-region Replication | Data sync latency | < 500ms |
| P-11 | Edge Cache Hit Ratio | Edge KV performance | > 99% |
| P-12 | Database Query | URL lookup | < 5ms p99 |

### Chaos/Reliability Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Region Failover | Kill entire region | Traffic reroutes, < 30s |
| C-02 | Database Node Failure | Kill CockroachDB node | Auto-rebalance, no downtime |
| C-03 | Edge PoP Failure | Simulate PoP outage | Traffic to next PoP |
| C-04 | Kafka Broker Failure | Kill Kafka broker | Automatic failover |
| C-05 | Network Partition | Split brain between regions | Consistent reads, eventual writes |
| C-06 | DNS Failure | DNS provider outage | Fallback DNS, cached records |
| C-07 | Certificate Rotation | Rotate SSL certs | Zero downtime rotation |
| C-08 | 100x Traffic Spike | Sudden viral link | Auto-scale, edge absorbs |
| C-09 | DDoS Attack | Simulated L7 DDoS | Edge mitigation, origin protected |
| C-10 | Data Corruption | Inject corrupt data | Detected, quarantined |
| C-11 | Clock Skew | NTP failure simulation | System remains consistent |
| C-12 | Slow Dependency | Add latency to DB | Circuit breaker activates |

### Security Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| S-01 | SQL Injection | Malicious input | Sanitized, no injection |
| S-02 | XSS in Custom Alias | Script in alias | Rejected |
| S-03 | SSRF Attempt | Internal URL target | Blocked |
| S-04 | Rate Limit Bypass | Distributed attack | Still limited |
| S-05 | API Key Enumeration | Brute force keys | Locked out |
| S-06 | JWT Tampering | Modified token | Rejected |
| S-07 | Open Redirect | Phishing attempt | Validated |
| S-08 | Privilege Escalation | Access other's URLs | 403 Forbidden |

---

## Disaster Recovery

### RPO/RTO Targets

| Scenario | RPO | RTO |
|----------|-----|-----|
| Single node failure | 0 | < 10 sec |
| Availability zone failure | 0 | < 30 sec |
| Region failure | < 1 sec | < 5 min |
| Global database corruption | < 1 min | < 1 hour |
| Complete data loss | < 5 min | < 4 hours |

### Backup Strategy

- **Continuous**: Raft-based replication (RPO = 0)
- **Hourly**: Incremental backups to GCS
- **Daily**: Full backups with point-in-time recovery
- **Weekly**: Cross-region backup verification
- **Monthly**: DR drill and recovery test

---

## Cost Optimization

| Component | Strategy | Estimated Savings |
|-----------|----------|-------------------|
| Edge Computing | Cache hot URLs at edge | 70% origin traffic reduction |
| Database | Reserved instances, auto-pause dev | 40% DB cost |
| Storage | Tiered storage, lifecycle policies | 50% storage cost |
| Compute | Spot instances for batch jobs | 60% compute cost |
| Analytics | ClickHouse compression | 80% analytics storage |

---

## Compliance

### GDPR Requirements
- Data residency (EU data stays in EU)
- Right to access (export endpoint)
- Right to deletion (with audit trail)
- Data minimization (configurable retention)
- Consent management (tracked in DB)

### SOC 2 Controls
- Encryption at rest and in transit
- Access logging and audit trails
- Incident response procedures
- Change management process
- Vendor risk management

### Security Certifications
- ISO 27001 compliant infrastructure
- PCI DSS (for payment processing)
- HIPAA BAA available (healthcare customers)
