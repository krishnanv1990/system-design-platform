# URL Shortener - L6/L7 Google SWE Level Solution

A production-grade, globally-distributed URL shortening service designed for Google-scale operations with enterprise features including multi-tenancy, billing, monitoring, security, and analytics.

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Quick Start - Copy to Platform](#quick-start---copy-to-platform)
3. [System Architecture](#system-architecture)
4. [Design Deep Dive](#design-deep-dive)
5. [Operational Excellence](#operational-excellence)
6. [Test Scenarios](#test-scenarios)

---

## Executive Summary

### Scale Requirements
| Metric | Target |
|--------|--------|
| URLs Created | 500M/month |
| Redirects | 50B/month (100:1 read/write) |
| P50 Latency | < 10ms |
| P99 Latency | < 100ms |
| Availability | 99.99% (52 min downtime/year) |
| Data Durability | 99.999999999% (11 nines) |

### L6/L7 Differentiators
This solution goes beyond basic functionality to include:
- **Multi-tenancy**: Organizations, API keys, usage quotas
- **Billing**: Usage tracking, tier-based pricing, overage handling
- **Observability**: Structured logging, metrics, distributed tracing, SLOs
- **Security**: Rate limiting, abuse detection, URL scanning, authentication
- **Analytics**: Click tracking, geographic data, referrer analysis
- **Global Scale**: Multi-region, edge caching, database sharding
- **Operational**: Admin APIs, feature flags, circuit breakers, runbooks

---

## Quick Start - Copy to Platform

### Database Schema (JSON)

```json
{
  "stores": [
    {
      "name": "urls",
      "type": "sql",
      "description": "Primary URL storage with sharding support",
      "fields": [
        {"name": "id", "type": "bigserial", "constraints": ["primary_key"]},
        {"name": "short_code", "type": "varchar(12)", "constraints": ["unique", "not_null", "indexed"]},
        {"name": "original_url", "type": "text", "constraints": ["not_null"]},
        {"name": "organization_id", "type": "uuid", "constraints": ["not_null", "indexed", "foreign_key"]},
        {"name": "created_by", "type": "uuid", "constraints": ["indexed", "foreign_key"]},
        {"name": "created_at", "type": "timestamp with time zone", "constraints": ["not_null"]},
        {"name": "updated_at", "type": "timestamp with time zone", "constraints": []},
        {"name": "expires_at", "type": "timestamp with time zone", "constraints": ["indexed"]},
        {"name": "is_active", "type": "boolean", "constraints": ["not_null"], "default": true},
        {"name": "click_count", "type": "bigint", "constraints": [], "default": 0},
        {"name": "metadata", "type": "jsonb", "constraints": [], "description": "Custom tags, campaign info"},
        {"name": "url_hash", "type": "varchar(64)", "constraints": ["indexed"], "description": "SHA-256 for dedup"}
      ],
      "indexes": ["short_code", "organization_id", "expires_at", "created_at", "url_hash"],
      "partitioning": "RANGE on created_at (monthly partitions)"
    },
    {
      "name": "organizations",
      "type": "sql",
      "description": "Multi-tenant organization management",
      "fields": [
        {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
        {"name": "name", "type": "varchar(255)", "constraints": ["not_null"]},
        {"name": "tier", "type": "varchar(20)", "constraints": ["not_null"], "description": "free|pro|enterprise"},
        {"name": "status", "type": "varchar(20)", "constraints": ["not_null"], "default": "active"},
        {"name": "monthly_quota", "type": "bigint", "constraints": ["not_null"]},
        {"name": "rate_limit_per_second", "type": "integer", "constraints": ["not_null"]},
        {"name": "created_at", "type": "timestamp with time zone", "constraints": ["not_null"]},
        {"name": "settings", "type": "jsonb", "constraints": [], "description": "Custom domain, branding"}
      ],
      "indexes": ["tier", "status"]
    },
    {
      "name": "api_keys",
      "type": "sql",
      "description": "API key management with scopes",
      "fields": [
        {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
        {"name": "organization_id", "type": "uuid", "constraints": ["not_null", "indexed", "foreign_key"]},
        {"name": "key_hash", "type": "varchar(64)", "constraints": ["unique", "not_null", "indexed"]},
        {"name": "key_prefix", "type": "varchar(8)", "constraints": ["not_null"]},
        {"name": "name", "type": "varchar(255)", "constraints": ["not_null"]},
        {"name": "scopes", "type": "text[]", "constraints": [], "description": "read, write, delete, admin"},
        {"name": "rate_limit_override", "type": "integer", "constraints": []},
        {"name": "expires_at", "type": "timestamp with time zone", "constraints": []},
        {"name": "last_used_at", "type": "timestamp with time zone", "constraints": []},
        {"name": "is_active", "type": "boolean", "constraints": ["not_null"], "default": true},
        {"name": "created_at", "type": "timestamp with time zone", "constraints": ["not_null"]}
      ],
      "indexes": ["organization_id", "key_hash", "is_active"]
    },
    {
      "name": "click_events",
      "type": "sql",
      "description": "Analytics click tracking (time-series partitioned)",
      "fields": [
        {"name": "id", "type": "bigserial", "constraints": ["primary_key"]},
        {"name": "url_id", "type": "bigint", "constraints": ["not_null", "indexed", "foreign_key"]},
        {"name": "short_code", "type": "varchar(12)", "constraints": ["not_null", "indexed"]},
        {"name": "clicked_at", "type": "timestamp with time zone", "constraints": ["not_null", "indexed"]},
        {"name": "ip_hash", "type": "varchar(64)", "constraints": [], "description": "Hashed IP for privacy"},
        {"name": "country_code", "type": "varchar(2)", "constraints": ["indexed"]},
        {"name": "region", "type": "varchar(100)", "constraints": []},
        {"name": "city", "type": "varchar(100)", "constraints": []},
        {"name": "device_type", "type": "varchar(20)", "constraints": ["indexed"]},
        {"name": "browser", "type": "varchar(50)", "constraints": []},
        {"name": "os", "type": "varchar(50)", "constraints": []},
        {"name": "referrer_domain", "type": "varchar(255)", "constraints": ["indexed"]}
      ],
      "indexes": ["url_id", "short_code", "clicked_at", "country_code", "device_type"],
      "partitioning": "RANGE on clicked_at (daily partitions, 90-day retention)"
    },
    {
      "name": "usage_records",
      "type": "sql",
      "description": "Billing usage tracking",
      "fields": [
        {"name": "id", "type": "bigserial", "constraints": ["primary_key"]},
        {"name": "organization_id", "type": "uuid", "constraints": ["not_null", "indexed", "foreign_key"]},
        {"name": "period_start", "type": "date", "constraints": ["not_null", "indexed"]},
        {"name": "period_end", "type": "date", "constraints": ["not_null"]},
        {"name": "urls_created", "type": "bigint", "constraints": ["not_null"], "default": 0},
        {"name": "redirects_served", "type": "bigint", "constraints": ["not_null"], "default": 0},
        {"name": "api_calls", "type": "bigint", "constraints": ["not_null"], "default": 0},
        {"name": "billable_amount_cents", "type": "integer", "constraints": []},
        {"name": "created_at", "type": "timestamp with time zone", "constraints": ["not_null"]}
      ],
      "indexes": ["organization_id", "period_start"]
    },
    {
      "name": "audit_logs",
      "type": "sql",
      "description": "Security and compliance audit trail",
      "fields": [
        {"name": "id", "type": "bigserial", "constraints": ["primary_key"]},
        {"name": "organization_id", "type": "uuid", "constraints": ["indexed"]},
        {"name": "actor_id", "type": "uuid", "constraints": ["indexed"]},
        {"name": "actor_type", "type": "varchar(20)", "constraints": []},
        {"name": "action", "type": "varchar(50)", "constraints": ["not_null", "indexed"]},
        {"name": "resource_type", "type": "varchar(50)", "constraints": ["not_null"]},
        {"name": "resource_id", "type": "varchar(100)", "constraints": []},
        {"name": "request_id", "type": "uuid", "constraints": ["indexed"]},
        {"name": "changes", "type": "jsonb", "constraints": []},
        {"name": "created_at", "type": "timestamp with time zone", "constraints": ["not_null", "indexed"]}
      ],
      "indexes": ["organization_id", "actor_id", "action", "created_at", "request_id"]
    },
    {
      "name": "url_cache",
      "type": "key-value",
      "description": "Redis cluster for caching and rate limiting",
      "fields": [
        {"name": "url:{short_code}", "type": "hash", "description": "Cached URL data, TTL: 1 hour"},
        {"name": "kgs:pool:{shard}", "type": "set", "description": "Pre-generated keys by shard"},
        {"name": "rate:{org}:{window}", "type": "string", "description": "Rate limit counter"},
        {"name": "rate:{ip}:{window}", "type": "string", "description": "IP-based rate limit"},
        {"name": "quota:{org}:{month}", "type": "hash", "description": "Monthly usage counters"},
        {"name": "circuit:{service}", "type": "hash", "description": "Circuit breaker state"},
        {"name": "blocklist:ip", "type": "set", "description": "Blocked IPs"},
        {"name": "blocklist:url", "type": "set", "description": "Blocked URL patterns"}
      ]
    },
    {
      "name": "event_streams",
      "type": "document",
      "description": "Kafka/Pub-Sub for async processing",
      "fields": [
        {"name": "topic: url-clicks", "type": "stream", "description": "Real-time click events"},
        {"name": "topic: usage-events", "type": "stream", "description": "Billing usage events"},
        {"name": "topic: audit-events", "type": "stream", "description": "Audit log events"}
      ]
    }
  ]
}
```

### API Specification (JSON)

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "URL Shortener API",
    "version": "2.0.0",
    "description": "Enterprise URL shortening service with analytics, billing, and multi-tenancy"
  },
  "servers": [
    {"url": "https://api.short.url/v2", "description": "Production"}
  ],
  "security": [{"ApiKeyAuth": []}],
  "paths": {
    "/health": {
      "get": {
        "summary": "Health check",
        "tags": ["Operations"],
        "security": [],
        "responses": {
          "200": {"description": "Healthy"},
          "503": {"description": "Unhealthy"}
        }
      }
    },
    "/health/deep": {
      "get": {
        "summary": "Deep health check (all dependencies)",
        "tags": ["Operations"],
        "security": [],
        "responses": {
          "200": {"description": "All systems healthy"},
          "503": {"description": "Dependency failure"}
        }
      }
    },
    "/": {
      "get": {
        "summary": "Service info",
        "tags": ["Operations"],
        "security": [],
        "responses": {
          "200": {"description": "Service information"}
        }
      }
    },
    "/api/v1/urls": {
      "post": {
        "summary": "Create short URL",
        "tags": ["URLs"],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["original_url"],
                "properties": {
                  "original_url": {"type": "string", "format": "uri", "maxLength": 2048},
                  "custom_code": {"type": "string", "pattern": "^[a-zA-Z0-9_-]{4,20}$"},
                  "expires_at": {"type": "string", "format": "date-time"},
                  "expires_in_seconds": {"type": "integer", "minimum": 60},
                  "expires_in_hours": {"type": "integer", "minimum": 1},
                  "metadata": {"type": "object"}
                }
              }
            }
          }
        },
        "responses": {
          "201": {"description": "URL created"},
          "400": {"description": "Invalid request"},
          "401": {"description": "Unauthorized"},
          "403": {"description": "Quota exceeded"},
          "409": {"description": "Custom code exists"},
          "429": {"description": "Rate limited"}
        }
      },
      "get": {
        "summary": "List URLs",
        "tags": ["URLs"],
        "parameters": [
          {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
          {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20}}
        ],
        "responses": {
          "200": {"description": "URL list"}
        }
      }
    },
    "/api/v1/urls/{short_code}": {
      "get": {
        "summary": "Get URL details",
        "tags": ["URLs"],
        "parameters": [{"name": "short_code", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {
          "200": {"description": "URL details"},
          "404": {"description": "Not found"}
        }
      },
      "delete": {
        "summary": "Delete URL",
        "tags": ["URLs"],
        "parameters": [{"name": "short_code", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {
          "204": {"description": "Deleted"},
          "404": {"description": "Not found"}
        }
      }
    },
    "/api/v1/urls/{short_code}/stats": {
      "get": {
        "summary": "Get URL analytics",
        "tags": ["Analytics"],
        "parameters": [
          {"name": "short_code", "in": "path", "required": true, "schema": {"type": "string"}},
          {"name": "period", "in": "query", "schema": {"type": "string", "enum": ["1h", "24h", "7d", "30d"]}}
        ],
        "responses": {
          "200": {"description": "Analytics data"},
          "404": {"description": "Not found"}
        }
      }
    },
    "/{short_code}": {
      "get": {
        "summary": "Redirect to original URL",
        "tags": ["Redirect"],
        "security": [],
        "parameters": [{"name": "short_code", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {
          "301": {"description": "Permanent redirect"},
          "307": {"description": "Temporary redirect"},
          "404": {"description": "Not found"},
          "410": {"description": "URL expired"}
        }
      }
    },
    "/api/v1/organizations/{org_id}/usage": {
      "get": {
        "summary": "Get usage statistics",
        "tags": ["Billing"],
        "parameters": [{"name": "org_id", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {
          "200": {"description": "Usage data"}
        }
      }
    },
    "/api/v1/organizations/{org_id}/quota": {
      "get": {
        "summary": "Get quota status",
        "tags": ["Billing"],
        "parameters": [{"name": "org_id", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {
          "200": {"description": "Quota information"}
        }
      }
    },
    "/api/v1/api-keys": {
      "get": {
        "summary": "List API keys",
        "tags": ["API Keys"],
        "responses": {"200": {"description": "API key list"}}
      },
      "post": {
        "summary": "Create API key",
        "tags": ["API Keys"],
        "responses": {"201": {"description": "API key created"}}
      }
    },
    "/admin/audit-logs": {
      "get": {
        "summary": "Query audit logs",
        "tags": ["Admin"],
        "parameters": [
          {"name": "action", "in": "query", "schema": {"type": "string"}},
          {"name": "start_time", "in": "query", "schema": {"type": "string", "format": "date-time"}}
        ],
        "responses": {"200": {"description": "Audit log entries"}}
      }
    },
    "/metrics": {
      "get": {
        "summary": "Prometheus metrics",
        "tags": ["Operations"],
        "security": [],
        "responses": {"200": {"description": "Metrics"}}
      }
    }
  },
  "components": {
    "securitySchemes": {
      "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    }
  }
}
```

---

## System Architecture

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CONTROL PLANE                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │    Config    │  │   Feature    │  │    Admin     │  │      Billing Service      │  │
│  │   Service    │  │    Flags     │  │   Portal     │  │    (Stripe Integration)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
┌─────────────────────────────────────────────┼──────────────────────────────────────────┐
│                              EDGE LAYER (Global CDN)                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │
│  │ CloudFlare │  │  Cloud CDN │  │ Edge Cache │  │  WAF/DDoS  │  │ Global Load    │   │
│  │ (DNS+SSL)  │  │  (Static)  │  │ (URL Map)  │  │ Protection │  │ Balancer       │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │
└──────────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
           ┌───────────────────────────────────┼───────────────────────────────────┐
           │                                   │                                   │
           ▼                                   ▼                                   ▼
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│      US-WEST REGION     │     │      US-EAST REGION     │     │      EU-WEST REGION     │
│  ┌───────────────────┐  │     │  ┌───────────────────┐  │     │  ┌───────────────────┐  │
│  │   API Gateway     │  │     │  │   API Gateway     │  │     │  │   API Gateway     │  │
│  │ ├─ Auth (API Key) │  │     │  │ ├─ Auth (API Key) │  │     │  │ ├─ Auth (API Key) │  │
│  │ ├─ Rate Limiting  │  │     │  │ ├─ Rate Limiting  │  │     │  │ ├─ Rate Limiting  │  │
│  │ ├─ Request ID     │  │     │  │ ├─ Request ID     │  │     │  │ ├─ Request ID     │  │
│  │ └─ Quota Check    │  │     │  │ └─ Quota Check    │  │     │  │ └─ Quota Check    │  │
│  └─────────┬─────────┘  │     │  └─────────┬─────────┘  │     │  └─────────┬─────────┘  │
│            │            │     │            │            │     │            │            │
│  ┌─────────▼─────────┐  │     │  ┌─────────▼─────────┐  │     │  ┌─────────▼─────────┐  │
│  │   URL Service     │  │     │  │   URL Service     │  │     │  │   URL Service     │  │
│  │   (K8s Pods)      │  │     │  │   (K8s Pods)      │  │     │  │   (K8s Pods)      │  │
│  │   Auto-scaling    │  │     │  │   Auto-scaling    │  │     │  │   Auto-scaling    │  │
│  │   10-100 replicas │  │     │  │   10-100 replicas │  │     │  │   10-100 replicas │  │
│  └─────────┬─────────┘  │     │  └─────────┬─────────┘  │     │  └─────────┬─────────┘  │
│            │            │     │            │            │     │            │            │
│  ┌─────────▼─────────┐  │     │  ┌─────────▼─────────┐  │     │  ┌─────────▼─────────┐  │
│  │   Redis Cluster   │  │     │  │   Redis Cluster   │  │     │  │   Redis Cluster   │  │
│  │ ├─ URL Cache      │  │     │  │ ├─ URL Cache      │  │     │  │ ├─ URL Cache      │  │
│  │ ├─ Rate Limits    │  │     │  │ ├─ Rate Limits    │  │     │  │ ├─ Rate Limits    │  │
│  │ ├─ KGS Pool       │  │     │  │ ├─ KGS Pool       │  │     │  │ ├─ KGS Pool       │  │
│  │ └─ Session Data   │  │     │  │ └─ Session Data   │  │     │  │ └─ Session Data   │  │
│  └───────────────────┘  │     │  └───────────────────┘  │     │  └───────────────────┘  │
└────────────┬────────────┘     └────────────┬────────────┘     └────────────┬────────────┘
             │                               │                               │
             └───────────────────────────────┼───────────────────────────────┘
                                             │
┌────────────────────────────────────────────┼────────────────────────────────────────────┐
│                                  DATA LAYER                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         PostgreSQL Cluster (Citus/Vitess)                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │   │
│  │  │Primary (US) │◀▶│ Replica (US)│  │ Replica (EU)│  │Replica(APAC)│            │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │   │
│  │  Sharding: Hash(organization_id) % 16 shards                                     │   │
│  │  Partitioning: Monthly on urls, Daily on click_events                            │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         Event Streaming (Kafka)                                   │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌────────────────────────────┐   │   │
│  │  │url-clicks │  │usage-event│  │audit-event│  │  Analytics Pipeline        │   │   │
│  │  │ (1M/sec)  │  │ (100K/sec)│  │ (10K/sec) │  │  (Spark/Dataflow)          │   │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   OBSERVABILITY                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Prometheus  │  │   Grafana   │  │Cloud Trace  │  │Cloud Logging│  │  PagerDuty  │  │
│  │  (Metrics)  │  │(Dashboards) │  │ (Tracing)   │  │(Structured) │  │ (Alerting)  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

**URL Creation:**
```
Client → Edge → API Gateway → URL Service → KGS (SPOP) → PostgreSQL → Redis Cache → Response
                    │               │
                    │               └──▶ Kafka (usage-events, audit-events)
                    │
                    └── Rate Limit Check (Redis INCR + EXPIRE)
                    └── Quota Check (Redis HGET)
```

**URL Redirect (99% of traffic):**
```
Client → Edge Cache (50% HIT) ──▶ 301 Redirect (< 5ms)
              │
              │ MISS
              ▼
         API Gateway → URL Service → Redis (99% HIT) → 301 Redirect (< 20ms)
                                          │
                                          │ MISS (1%)
                                          ▼
                                    PostgreSQL → Cache → Redirect
                                          │
                                          └──▶ Kafka (url-clicks) [async, non-blocking]
```

---

## Design Deep Dive

### Multi-Tenancy & Pricing Tiers

| Feature | Free | Pro ($49/mo) | Enterprise |
|---------|------|--------------|------------|
| URLs/month | 1,000 | 100,000 | 10,000,000 |
| Redirects/month | 100,000 | 10,000,000 | 1,000,000,000 |
| Rate limit (req/s) | 10 | 100 | 10,000 |
| API Keys | 2 | 10 | Unlimited |
| Custom domains | No | 1 | Unlimited |
| Analytics retention | 7 days | 90 days | 1 year |
| SLA | Best effort | 99.9% | 99.99% |
| Support | Community | Email | Dedicated |

### SLOs (Service Level Objectives)

| SLI | SLO | Error Budget |
|-----|-----|--------------|
| Availability | 99.99% | 52 min/year |
| Redirect Latency (p50) | < 10ms | - |
| Redirect Latency (p99) | < 100ms | - |
| Create Latency (p99) | < 500ms | - |
| Error Rate | < 0.1% | - |

### Security Layers

```
Layer 1: Edge
├── DDoS protection (CloudFlare/Cloud Armor)
├── WAF rules (OWASP Top 10)
├── Bot detection
└── Geo-blocking

Layer 2: API Gateway
├── API Key validation
├── Rate limiting (per-org, per-IP)
├── Request validation
└── Request ID injection

Layer 3: Application
├── URL validation (format, blocklist)
├── URL scanning (Safe Browsing API)
├── SSRF prevention (internal IP blocking)
└── Audit logging

Layer 4: Data
├── Encryption at rest (AES-256)
├── Encryption in transit (TLS 1.3)
├── PII handling (IP hashing)
└── Access control (RBAC)
```

### Monitoring & Alerting

**Key Metrics:**
```prometheus
# Request rate by endpoint
url_shortener_requests_total{endpoint, method, status, org_tier}

# Latency histogram
url_shortener_request_duration_seconds_bucket{endpoint, le}

# Cache performance
url_shortener_cache_hits_total{cache}
url_shortener_cache_misses_total{cache}

# KGS pool health
url_shortener_kgs_pool_size{shard}

# Rate limit usage
url_shortener_rate_limit_usage{org}

# Quota usage
url_shortener_quota_usage{org, resource}
```

**Alert Rules:**
- Error rate > 1% for 5 min → Page on-call
- P99 latency > 500ms for 10 min → Slack alert
- KGS pool < 1000 keys → Auto-replenish + alert
- Quota > 90% → Email warning to org
- Database replica lag > 30s → Page on-call

---

## Operational Excellence

### Runbook: High Error Rate

```
1. CHECK: Dashboard for error patterns
   - Which endpoints? Which status codes?
   - Which region/org affected?

2. IF 5xx errors:
   - Check pod health: kubectl get pods -l app=url-service
   - Check logs: kubectl logs -l app=url-service | grep ERROR
   - Check dependencies: Redis, PostgreSQL, Kafka

3. IF rate limiting (429):
   - Verify if legitimate traffic spike
   - Consider temporary limit increase

4. ESCALATE if not resolved in 15 min
```

### Disaster Recovery

| Scenario | RTO | RPO |
|----------|-----|-----|
| Single instance | 0 | 0 |
| Zone failure | < 1 min | 0 |
| Region failure | < 5 min | < 1 min |
| Data corruption | < 1 hour | < 5 min |

---

## Test Scenarios

### Functional Tests (80+ tests)

| Category | Count | Description |
|----------|-------|-------------|
| Health | 3 | `/health`, `/health/deep`, `/metrics` |
| Auth | 8 | API key validation, scopes, expiration |
| URL CRUD | 15 | Create, read, update, delete, list, bulk |
| Validation | 12 | URL format, custom codes, expiration |
| Rate Limiting | 6 | Per-org, per-key, per-IP |
| Quota | 5 | Check, enforcement, warnings |
| Analytics | 8 | Click tracking, aggregation |
| Billing | 5 | Usage tracking, quota reporting |
| Security | 10 | XSS, SSRF, injection, blocklist |
| Multi-tenancy | 8 | Org isolation, cross-org access |

### Performance Tests (Real-World)

**Traffic Distribution:**
- 90% Read (redirects)
- 8% Write (URL creation)
- 2% Analytics (stats queries)

**Targets:**
| Metric | Target | Critical |
|--------|--------|----------|
| P50 Redirect | < 10ms | < 25ms |
| P99 Redirect | < 100ms | < 500ms |
| P50 Create | < 50ms | < 100ms |
| P99 Create | < 500ms | < 1s |
| RPS (100 users) | 1000+ | 500+ |
| Error Rate | < 0.1% | < 1% |

### Chaos Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| Redis failure | Kill primary | DB fallback, degraded latency |
| DB replica lag | 5s lag | Reads succeed, eventual consistency |
| KGS exhaustion | Empty pool | Generate on-the-fly |
| Network partition | Split zone | Cross-zone reroute |
| High latency | 500ms delay | Timeouts handled |
| Instance crash | Kill 50% pods | Auto-recovery |
| Rate limit spike | 10x traffic | 429 responses, stable |
| Quota exceeded | Set to 0 | 403 responses |

---

## Summary

This L6/L7 solution demonstrates:

1. **Scale**: 50B requests/month, global distribution
2. **Operations**: SLOs, monitoring, runbooks, DR
3. **Business**: Multi-tenancy, billing, quotas
4. **Security**: Defense in depth, audit trails
5. **Reliability**: 99.99% availability, graceful degradation

Key architectural decisions:
- KGS for O(1) key allocation
- Edge caching for 50%+ redirect traffic
- Event-driven analytics (async click processing)
- Sharded database for horizontal scale
- Circuit breakers for resilience
