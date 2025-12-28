# Notification System - L6 (Staff Engineer) Solution

## Level Requirements

**Target Role:** Staff Engineer (L6)
**Focus:** Scalable notification platform with advanced features

### What's Expected at L6

- Priority-based queuing
- Rate limiting per user and globally
- Deduplication to prevent spam
- Webhook support for delivery callbacks
- A/B testing for notification content
- Advanced analytics and metrics
- Multi-tenant support
- Horizontal scaling

---

## Database Schema

```json
{
  "databases": {
    "postgresql": {
      "tables": [
        {
          "name": "tenants",
          "description": "Multi-tenant support",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY DEFAULT gen_random_uuid()"},
            {"name": "name", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "api_key", "type": "VARCHAR(64)", "constraints": "UNIQUE NOT NULL"},
            {"name": "rate_limit_per_second", "type": "INTEGER", "constraints": "DEFAULT 100"},
            {"name": "webhooks", "type": "JSONB", "constraints": "DEFAULT '{}'"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ]
        },
        {
          "name": "users",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "tenant_id", "type": "UUID", "constraints": "REFERENCES tenants(id)"},
            {"name": "external_id", "type": "VARCHAR(255)", "constraints": "NOT NULL"},
            {"name": "email", "type": "VARCHAR(255)"},
            {"name": "phone", "type": "VARCHAR(20)"},
            {"name": "device_tokens", "type": "JSONB", "constraints": "DEFAULT '[]'"},
            {"name": "timezone", "type": "VARCHAR(50)", "constraints": "DEFAULT 'UTC'"},
            {"name": "language", "type": "VARCHAR(10)", "constraints": "DEFAULT 'en'"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"columns": ["tenant_id", "external_id"], "unique": true}
          ]
        },
        {
          "name": "notification_preferences",
          "columns": [
            {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
            {"name": "user_id", "type": "BIGINT", "constraints": "REFERENCES users(id)"},
            {"name": "category", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "channels", "type": "JSONB", "constraints": "NOT NULL"},
            {"name": "frequency_cap", "type": "JSONB"},
            {"name": "quiet_hours", "type": "JSONB"}
          ],
          "indexes": [
            {"columns": ["user_id", "category"], "unique": true}
          ]
        },
        {
          "name": "notification_templates",
          "columns": [
            {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
            {"name": "tenant_id", "type": "UUID", "constraints": "REFERENCES tenants(id)"},
            {"name": "name", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
            {"name": "language", "type": "VARCHAR(10)", "constraints": "DEFAULT 'en'"},
            {"name": "subject", "type": "VARCHAR(255)"},
            {"name": "body", "type": "TEXT", "constraints": "NOT NULL"},
            {"name": "variables", "type": "JSONB"},
            {"name": "ab_variants", "type": "JSONB"},
            {"name": "version", "type": "INTEGER", "constraints": "DEFAULT 1"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"columns": ["tenant_id", "name", "channel", "language"], "unique": true}
          ]
        },
        {
          "name": "notifications",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "tenant_id", "type": "UUID", "constraints": "NOT NULL"},
            {"name": "user_id", "type": "BIGINT", "constraints": "NOT NULL"},
            {"name": "template_id", "type": "INTEGER"},
            {"name": "category", "type": "VARCHAR(50)"},
            {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
            {"name": "priority", "type": "INTEGER", "constraints": "DEFAULT 5"},
            {"name": "status", "type": "VARCHAR(20)", "constraints": "DEFAULT 'pending'"},
            {"name": "dedup_key", "type": "VARCHAR(255)"},
            {"name": "ab_variant", "type": "VARCHAR(50)"},
            {"name": "payload", "type": "JSONB", "constraints": "NOT NULL"},
            {"name": "metadata", "type": "JSONB"},
            {"name": "scheduled_at", "type": "TIMESTAMP"},
            {"name": "sent_at", "type": "TIMESTAMP"},
            {"name": "delivered_at", "type": "TIMESTAMP"},
            {"name": "read_at", "type": "TIMESTAMP"},
            {"name": "clicked_at", "type": "TIMESTAMP"},
            {"name": "failed_at", "type": "TIMESTAMP"},
            {"name": "error_message", "type": "TEXT"},
            {"name": "retry_count", "type": "INTEGER", "constraints": "DEFAULT 0"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"columns": ["tenant_id", "user_id", "created_at"]},
            {"columns": ["status", "scheduled_at"]},
            {"columns": ["dedup_key", "created_at"]}
          ],
          "partitioning": {
            "type": "RANGE",
            "column": "created_at",
            "interval": "1 month"
          }
        },
        {
          "name": "notification_events",
          "description": "Event tracking for analytics",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "notification_id", "type": "BIGINT", "constraints": "NOT NULL"},
            {"name": "event_type", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "metadata", "type": "JSONB"},
            {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
          ],
          "indexes": [
            {"columns": ["notification_id", "event_type"]}
          ]
        }
      ]
    },
    "redis": {
      "data_structures": [
        {
          "name": "queue:{channel}:{priority}",
          "type": "LIST",
          "description": "Priority queues per channel (0=highest, 10=lowest)"
        },
        {
          "name": "rate_limit:tenant:{tenant_id}",
          "type": "STRING",
          "description": "Token bucket for tenant rate limiting"
        },
        {
          "name": "rate_limit:user:{user_id}:{category}",
          "type": "STRING",
          "description": "Frequency cap per user/category"
        },
        {
          "name": "dedup:{dedup_key}",
          "type": "STRING",
          "description": "Deduplication key with TTL",
          "ttl": "24 hours"
        },
        {
          "name": "scheduled",
          "type": "ZSET",
          "description": "Scheduled notifications (score = timestamp)"
        },
        {
          "name": "retry",
          "type": "ZSET",
          "description": "Retry queue (score = retry_at timestamp)"
        },
        {
          "name": "ab_assignment:{user_id}:{experiment_id}",
          "type": "STRING",
          "description": "A/B test variant assignment"
        }
      ]
    },
    "clickhouse": {
      "purpose": "Analytics and reporting",
      "tables": [
        {
          "name": "notification_metrics",
          "columns": [
            {"name": "tenant_id", "type": "UUID"},
            {"name": "category", "type": "String"},
            {"name": "channel", "type": "String"},
            {"name": "ab_variant", "type": "Nullable(String)"},
            {"name": "sent_count", "type": "UInt64"},
            {"name": "delivered_count", "type": "UInt64"},
            {"name": "read_count", "type": "UInt64"},
            {"name": "clicked_count", "type": "UInt64"},
            {"name": "failed_count", "type": "UInt64"},
            {"name": "hour", "type": "DateTime"}
          ],
          "engine": "SummingMergeTree",
          "order_by": ["tenant_id", "category", "channel", "hour"]
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
      "method": "POST",
      "path": "/api/v1/notifications",
      "description": "Send notification with priority and deduplication",
      "headers": {
        "X-API-Key": "Tenant API key (required)"
      },
      "request_body": {
        "user_id": "string (external user ID, required)",
        "category": "string (required)",
        "channels": "array (optional)",
        "template": "string (template name)",
        "data": {},
        "priority": "integer (0-10, default: 5)",
        "dedup_key": "string (optional)",
        "dedup_ttl_seconds": "integer (default: 86400)",
        "scheduled_at": "ISO8601 (optional)",
        "metadata": {},
        "idempotency_key": "string (optional)"
      },
      "responses": {
        "201": {
          "notification_id": 12345,
          "status": "queued",
          "channels": ["email", "push"],
          "ab_variant": "variant_a"
        },
        "200": {"deduplicated": true, "original_notification_id": 12340},
        "429": {"error": "Rate limit exceeded", "retry_after": 60}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/notifications/batch",
      "description": "Send to multiple users",
      "request_body": {
        "user_ids": ["user1", "user2"],
        "category": "string",
        "template": "string",
        "data": {},
        "priority": 5
      },
      "responses": {
        "202": {
          "batch_id": "uuid",
          "accepted": 100,
          "rejected": 2,
          "rejected_reasons": [
            {"user_id": "user99", "reason": "rate_limited"}
          ]
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/webhooks/events",
      "description": "Receive delivery events from providers",
      "request_body": {
        "event_type": "delivered | bounced | complained | opened | clicked",
        "notification_id": "string",
        "timestamp": "ISO8601",
        "metadata": {}
      },
      "responses": {
        "200": {"processed": true}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics",
      "description": "Get notification analytics",
      "query_params": {
        "start_date": "ISO8601",
        "end_date": "ISO8601",
        "category": "string (optional)",
        "channel": "string (optional)",
        "granularity": "hour | day | week"
      },
      "responses": {
        "200": {
          "summary": {
            "sent": 100000,
            "delivered": 98000,
            "delivery_rate": 0.98,
            "read": 45000,
            "read_rate": 0.459,
            "clicked": 5000,
            "click_rate": 0.051
          },
          "by_channel": {
            "email": {"sent": 60000, "delivered": 58000},
            "push": {"sent": 30000, "delivered": 30000},
            "sms": {"sent": 10000, "delivered": 10000}
          },
          "ab_results": [
            {
              "experiment": "welcome_email_v2",
              "variants": [
                {"name": "control", "sent": 5000, "clicked": 200, "click_rate": 0.04},
                {"name": "variant_a", "sent": 5000, "clicked": 300, "click_rate": 0.06}
              ],
              "winner": "variant_a",
              "confidence": 0.95
            }
          ],
          "time_series": []
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/experiments",
      "description": "Create A/B experiment",
      "request_body": {
        "name": "string",
        "template": "string",
        "variants": [
          {"name": "control", "weight": 50, "template_version": 1},
          {"name": "variant_a", "weight": 50, "template_version": 2}
        ],
        "target_metric": "click_rate | open_rate",
        "min_sample_size": 1000
      },
      "responses": {
        "201": {"experiment_id": "uuid", "status": "active"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/users/{user_id}/inbox",
      "description": "Get user's notification inbox",
      "query_params": {
        "limit": 20,
        "cursor": "string",
        "unread_only": "boolean"
      },
      "responses": {
        "200": {
          "notifications": [
            {
              "id": 12345,
              "category": "order",
              "title": "Order Shipped",
              "body": "Your order has shipped!",
              "read": false,
              "created_at": "2024-01-01T00:00:00Z"
            }
          ],
          "cursor": "next_cursor",
          "unread_count": 5
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/users/{user_id}/inbox/mark-read",
      "description": "Mark notifications as read",
      "request_body": {
        "notification_ids": [12345, 12346]
      },
      "responses": {
        "200": {"marked": 2}
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                      Notification System - L6 Architecture
    ═════════════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           API CLIENTS                                    │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        API GATEWAY (Kong/Envoy)                          │
    │                                                                          │
    │  • API Key Authentication                                                │
    │  • Global Rate Limiting                                                  │
    │  • Request Routing                                                       │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      NOTIFICATION API SERVICE                            │
    │                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────┐    │
    │  │                    Request Processing Pipeline                   │    │
    │  │                                                                  │    │
    │  │  1. Validate ─► 2. Dedup ─► 3. Rate Limit ─► 4. A/B Assign      │    │
    │  │       │              │            │               │              │    │
    │  │       ▼              ▼            ▼               ▼              │    │
    │  │  5. Template ─► 6. Preference ─► 7. Queue ─► 8. Respond         │    │
    │  └─────────────────────────────────────────────────────────────────┘    │
    │                                                                          │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
    │  │ Dedup Svc    │  │ Rate Limit   │  │ A/B Testing  │                   │
    │  │              │  │ Service      │  │ Service      │                   │
    │  │ • Check key  │  │ • Token      │  │ • Assign     │                   │
    │  │ • Set w/TTL  │  │   bucket     │  │   variant    │                   │
    │  │              │  │ • Per-tenant │  │ • Track      │                   │
    │  │              │  │ • Per-user   │  │   exposure   │                   │
    │  └──────────────┘  └──────────────┘  └──────────────┘                   │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        PRIORITY QUEUE SYSTEM (Redis)                     │
    │                                                                          │
    │  ┌─────────────────────────────────────────────────────────────────┐    │
    │  │                    Priority Queues Per Channel                   │    │
    │  │                                                                  │    │
    │  │  Email                     Push                     SMS          │    │
    │  │  ┌──────────────┐          ┌──────────────┐         ┌─────────┐ │    │
    │  │  │ P0 (urgent)  │          │ P0 (urgent)  │         │   P0    │ │    │
    │  │  ├──────────────┤          ├──────────────┤         ├─────────┤ │    │
    │  │  │ P1           │          │ P1           │         │   P1    │ │    │
    │  │  ├──────────────┤          ├──────────────┤         ├─────────┤ │    │
    │  │  │ P5 (default) │          │ P5 (default) │         │   P5    │ │    │
    │  │  ├──────────────┤          ├──────────────┤         ├─────────┤ │    │
    │  │  │ P10 (low)    │          │ P10 (low)    │         │   P10   │ │    │
    │  │  └──────────────┘          └──────────────┘         └─────────┘ │    │
    │  └─────────────────────────────────────────────────────────────────┘    │
    │                                                                          │
    │  ┌────────────────────┐     ┌────────────────────┐                      │
    │  │  Scheduled Queue   │     │    Retry Queue     │                      │
    │  │  (ZSET by time)    │     │  (ZSET by time)    │                      │
    │  └────────────────────┘     └────────────────────┘                      │
    └────────────────────────────────┬────────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
    │   Email Workers     │ │   Push Workers      │ │   SMS Workers       │
    │   (Auto-scaled)     │ │   (Auto-scaled)     │ │   (Auto-scaled)     │
    │                     │ │                     │ │                     │
    │ • Priority dequeue  │ │ • Priority dequeue  │ │ • Priority dequeue  │
    │ • Provider routing  │ │ • FCM/APNS routing  │ │ • Provider routing  │
    │ • Retry handling    │ │ • Retry handling    │ │ • Retry handling    │
    │ • Event publishing  │ │ • Event publishing  │ │ • Event publishing  │
    └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
               │                       │                       │
               ▼                       ▼                       ▼
    ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
    │  Email Providers    │ │  Push Providers     │ │  SMS Providers      │
    │                     │ │                     │ │                     │
    │ • SendGrid         │ │ • FCM (Android)     │ │ • Twilio            │
    │ • Mailgun          │ │ • APNS (iOS)        │ │ • Nexmo             │
    │ • SES              │ │ • Web Push          │ │ • MessageBird       │
    │                     │ │                     │ │                     │
    │ (Failover routing) │ │ (Platform routing)  │ │ (Failover routing)  │
    └─────────────────────┘ └─────────────────────┘ └─────────────────────┘

                                     │
                                     │ Webhooks
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        EVENT PROCESSING                                  │
    │                                                                          │
    │  ┌─────────────────────┐           ┌─────────────────────┐              │
    │  │  Webhook Receiver   │           │   Event Stream      │              │
    │  │                     │           │   (Kafka)           │              │
    │  │ • Provider events   │──────────▶│                     │              │
    │  │ • Status updates    │           │ • Async processing  │              │
    │  │ • Engagement data   │           │ • Analytics pipeline│              │
    │  └─────────────────────┘           └──────────┬──────────┘              │
    │                                               │                          │
    │                                               ▼                          │
    │                              ┌─────────────────────┐                     │
    │                              │  Analytics Service  │                     │
    │                              │                     │                     │
    │                              │ • Aggregate metrics │                     │
    │                              │ • A/B test stats    │                     │
    │                              │ • Write to CH       │                     │
    │                              └─────────────────────┘                     │
    └─────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           DATA STORES                                    │
    │                                                                          │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │
    │  │    PostgreSQL       │  │      Redis          │  │   ClickHouse    │  │
    │  │                     │  │                     │  │                 │  │
    │  │ • Notifications     │  │ • Queues            │  │ • Metrics       │  │
    │  │ • Users             │  │ • Rate limits       │  │ • A/B results   │  │
    │  │ • Preferences       │  │ • Dedup keys        │  │ • Reports       │  │
    │  │ • Templates         │  │ • A/B assignments   │  │                 │  │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────┘
```

### Priority Queue Implementation

```python
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum
import redis
import hashlib

class Priority(IntEnum):
    URGENT = 0      # OTP, security alerts
    HIGH = 2        # Transactional
    NORMAL = 5      # Default
    LOW = 8         # Marketing
    BULK = 10       # Mass campaigns

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[int] = None

class NotificationServiceL6:
    """
    L6 Notification Service with:
    - Priority queues
    - Rate limiting (tenant + user)
    - Deduplication
    - A/B testing
    - Multi-provider routing
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        db_connection,
        kafka_producer
    ):
        self.redis = redis_client
        self.db = db_connection
        self.kafka = kafka_producer

    async def send_notification(
        self,
        tenant_id: str,
        user_id: str,
        category: str,
        template: str,
        data: Dict,
        priority: int = Priority.NORMAL,
        dedup_key: str = None,
        dedup_ttl: int = 86400,
        scheduled_at: float = None,
        metadata: Dict = None
    ) -> Dict:
        """
        Send notification with full L6 pipeline:
        1. Deduplication check
        2. Tenant rate limiting
        3. User frequency cap
        4. A/B variant assignment
        5. Template rendering
        6. Channel filtering
        7. Priority queue insertion
        """

        # Step 1: Deduplication
        if dedup_key:
            dedup_result = await self._check_dedup(dedup_key)
            if dedup_result:
                return {
                    "deduplicated": True,
                    "original_notification_id": dedup_result
                }

        # Step 2: Tenant rate limiting
        rate_result = await self._check_tenant_rate_limit(tenant_id)
        if not rate_result.allowed:
            return {
                "error": "rate_limit_exceeded",
                "retry_after": rate_result.retry_after
            }

        # Step 3: User frequency cap
        freq_result = await self._check_user_frequency(user_id, category)
        if not freq_result.allowed:
            return {
                "error": "frequency_cap_exceeded",
                "retry_after": freq_result.retry_after
            }

        # Step 4: Get user and preferences
        user = await self._get_user(tenant_id, user_id)
        preferences = await self._get_preferences(user["id"], category)

        # Step 5: A/B variant assignment
        ab_variant = await self._assign_ab_variant(user_id, template)

        # Step 6: Render template
        template_obj = await self._get_template(tenant_id, template, ab_variant)
        rendered = self._render_template(template_obj, data, user["language"])

        # Step 7: Filter channels
        enabled_channels = self._filter_channels(preferences, user)

        # Step 8: Create notification records and queue
        notification_ids = []

        for channel in enabled_channels:
            notification_id = await self._create_notification(
                tenant_id=tenant_id,
                user_id=user["id"],
                category=category,
                channel=channel,
                priority=priority,
                ab_variant=ab_variant,
                payload=rendered[channel],
                scheduled_at=scheduled_at,
                metadata=metadata
            )

            if scheduled_at and scheduled_at > time.time():
                # Schedule for later
                await self._schedule_notification(notification_id, scheduled_at)
            else:
                # Queue immediately
                await self._queue_notification(
                    notification_id=notification_id,
                    channel=channel,
                    priority=priority,
                    user=user,
                    payload=rendered[channel]
                )

            notification_ids.append(notification_id)

        # Set dedup key
        if dedup_key:
            await self._set_dedup(dedup_key, notification_ids[0], dedup_ttl)

        return {
            "notification_ids": notification_ids,
            "channels": enabled_channels,
            "status": "queued" if not scheduled_at else "scheduled",
            "ab_variant": ab_variant
        }

    async def _check_dedup(self, dedup_key: str) -> Optional[int]:
        """Check if notification was recently sent."""
        key = f"dedup:{dedup_key}"
        result = self.redis.get(key)
        return int(result) if result else None

    async def _set_dedup(self, dedup_key: str, notification_id: int, ttl: int):
        """Set deduplication key."""
        key = f"dedup:{dedup_key}"
        self.redis.setex(key, ttl, notification_id)

    async def _check_tenant_rate_limit(self, tenant_id: str) -> RateLimitResult:
        """Token bucket rate limiting per tenant."""
        key = f"rate_limit:tenant:{tenant_id}"
        now = time.time()

        # Get tenant config
        tenant = await self._get_tenant(tenant_id)
        rate = tenant["rate_limit_per_second"]
        capacity = rate * 10  # 10 second burst

        # Lua script for atomic token bucket
        lua_script = """
        local key = KEYS[1]
        local rate = tonumber(ARGV[1])
        local capacity = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])

        local data = redis.call('HMGET', key, 'tokens', 'last_update')
        local tokens = tonumber(data[1]) or capacity
        local last_update = tonumber(data[2]) or now

        local elapsed = now - last_update
        local new_tokens = elapsed * rate
        tokens = math.min(capacity, tokens + new_tokens)

        local allowed = 0
        if tokens >= cost then
            tokens = tokens - cost
            allowed = 1
        end

        redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
        redis.call('EXPIRE', key, 60)

        local reset_at = now + (capacity - tokens) / rate
        return {allowed, tokens, reset_at}
        """

        result = self.redis.eval(lua_script, 1, key, rate, capacity, now, 1)

        return RateLimitResult(
            allowed=bool(result[0]),
            remaining=int(result[1]),
            reset_at=float(result[2]),
            retry_after=int(result[2] - now) if not result[0] else None
        )

    async def _check_user_frequency(
        self,
        user_id: str,
        category: str
    ) -> RateLimitResult:
        """Frequency cap per user per category."""
        key = f"rate_limit:user:{user_id}:{category}"

        # Get user preference frequency cap (default: 10 per hour)
        cap = 10
        window = 3600

        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, window)

        ttl = self.redis.ttl(key)

        return RateLimitResult(
            allowed=current <= cap,
            remaining=max(0, cap - current),
            reset_at=time.time() + ttl,
            retry_after=ttl if current > cap else None
        )

    async def _assign_ab_variant(
        self,
        user_id: str,
        template: str
    ) -> Optional[str]:
        """Assign user to A/B test variant (sticky assignment)."""
        # Check for active experiment
        experiment = await self._get_active_experiment(template)
        if not experiment:
            return None

        # Check existing assignment
        key = f"ab_assignment:{user_id}:{experiment['id']}"
        existing = self.redis.get(key)
        if existing:
            return existing.decode()

        # Assign based on user_id hash for consistency
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        cumulative_weight = 0

        for variant in experiment["variants"]:
            cumulative_weight += variant["weight"]
            if hash_val % 100 < cumulative_weight:
                # Store assignment
                self.redis.setex(key, 86400 * 30, variant["name"])
                return variant["name"]

        return experiment["variants"][0]["name"]

    async def _queue_notification(
        self,
        notification_id: int,
        channel: str,
        priority: int,
        user: Dict,
        payload: Dict
    ):
        """Add to priority queue."""
        message = {
            "notification_id": notification_id,
            "channel": channel,
            "recipient": self._get_recipient(user, channel),
            "payload": payload,
            "priority": priority,
            "created_at": time.time()
        }

        queue_name = f"queue:{channel}:{priority}"
        self.redis.rpush(queue_name, json.dumps(message))


class PriorityWorker:
    """
    Worker that processes priority queues.
    Dequeues from highest priority first.
    """

    def __init__(
        self,
        channel: str,
        redis_client: redis.Redis,
        providers: Dict,
        db_connection
    ):
        self.channel = channel
        self.redis = redis_client
        self.providers = providers
        self.db = db_connection
        self.priorities = [0, 2, 5, 8, 10]

    async def run(self):
        """Main worker loop with priority processing."""
        while True:
            message = await self._dequeue_priority()

            if message:
                await self._process_message(message)
            else:
                # No messages - check scheduled and retry
                await self._process_scheduled()
                await self._process_retries()
                await asyncio.sleep(0.1)

    async def _dequeue_priority(self) -> Optional[Dict]:
        """Dequeue from highest priority queue first."""
        for priority in self.priorities:
            queue_name = f"queue:{self.channel}:{priority}"
            result = self.redis.lpop(queue_name)

            if result:
                return json.loads(result)

        return None

    async def _process_message(self, message: Dict):
        """Process single notification."""
        notification_id = message["notification_id"]

        try:
            # Select provider (with failover)
            provider = self._select_provider(message)

            # Send
            result = await provider.send(message)

            if result["success"]:
                await self._handle_success(notification_id, result)
            else:
                await self._handle_failure(message, result["error"])

        except Exception as e:
            await self._handle_failure(message, str(e))

    def _select_provider(self, message: Dict):
        """Select provider with failover support."""
        primary = self.providers["primary"]
        fallback = self.providers.get("fallback")

        # Check primary health
        if primary.is_healthy():
            return primary

        if fallback and fallback.is_healthy():
            return fallback

        # Use primary anyway
        return primary

    async def _handle_success(self, notification_id: int, result: Dict):
        """Handle successful delivery."""
        # Update database
        await self._update_status(notification_id, "sent", result)

        # Publish event
        await self._publish_event(notification_id, "sent", result)

    async def _handle_failure(self, message: Dict, error: str):
        """Handle delivery failure with retry."""
        notification_id = message["notification_id"]
        retry_count = message.get("retry_count", 0)

        if retry_count < 3:
            # Schedule retry with exponential backoff
            retry_delay = 60 * (2 ** retry_count)
            retry_at = time.time() + retry_delay

            message["retry_count"] = retry_count + 1
            self.redis.zadd("retry", {json.dumps(message): retry_at})
        else:
            # Max retries - mark failed
            await self._update_status(notification_id, "failed", {"error": error})
            await self._publish_event(notification_id, "failed", {"error": error})
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Priority ordering | P0 before P5 | Higher priority processed first |
| F-02 | Deduplication | Same dedup_key twice | Second request returns original ID |
| F-03 | Tenant rate limit | Exceed rate | 429 with retry_after |
| F-04 | User frequency cap | Exceed cap | Notification rejected |
| F-05 | A/B assignment | Same user twice | Same variant assigned |
| F-06 | A/B distribution | 50/50 split | Roughly equal distribution |
| F-07 | Scheduled delivery | Future timestamp | Delivered at scheduled time |
| F-08 | Webhook processing | Provider callback | Status updated |
| F-09 | Provider failover | Primary fails | Fallback used |
| F-10 | Batch send | 100 users | All queued |
| F-11 | Multi-tenant isolation | Two tenants | Separate rate limits |
| F-12 | Inbox retrieval | GET inbox | Paginated results |
| F-13 | Mark read | POST mark-read | Read status updated |
| F-14 | Analytics query | GET analytics | Aggregated metrics |
| F-15 | Experiment creation | Create A/B test | Experiment active |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | API latency | Send notification | < 50ms p99 |
| P-02 | Queue throughput | Per channel | > 10,000/s |
| P-03 | Worker throughput | Per worker | > 500/s |
| P-04 | Priority latency | P0 vs P10 | P0 < 1s faster |
| P-05 | Batch processing | 10,000 users | < 60s |
| P-06 | Dedup check | Lookup time | < 1ms |
| P-07 | Rate limit check | Token bucket | < 1ms |
| P-08 | Analytics query | 30-day range | < 5s |
| P-09 | Webhook processing | Events/s | > 5,000/s |
| P-10 | End-to-end P0 | Urgent delivery | < 3s |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Worker crash | Kill workers | Messages remain queued |
| C-02 | Provider outage | Primary down | Failover to secondary |
| C-03 | Redis failure | Redis down | Graceful degradation |
| C-04 | Kafka lag | Consumer behind | Eventual processing |
| C-05 | Database slow | High latency | Timeouts, retries |
| C-06 | Rate limit storm | Burst traffic | Fair rejection |
| C-07 | Memory pressure | High memory | Stable operation |
| C-08 | Network partition | Split brain | No duplicate sends |

---

## Capacity Estimates

- **Daily notifications**: 100M
- **Peak rate**: 10,000/second
- **Tenants**: 1,000
- **Users**: 100M
- **Channels**: Email (50%), Push (40%), SMS (10%)
- **Queue depth**: ~500,000 peak
- **Database size**: ~500GB (90-day retention)
- **Analytics retention**: 1 year
