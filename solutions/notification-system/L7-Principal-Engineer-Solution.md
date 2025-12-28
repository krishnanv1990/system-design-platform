# Notification System - L7 (Principal Engineer) Solution

## Level Requirements

**Target Role:** Principal Engineer (L7)
**Focus:** Global-scale notification platform with intelligent delivery

### What's Expected at L7

- Multi-region with geo-aware delivery
- ML-based send time optimization
- Intelligent channel selection
- Cross-channel orchestration
- Real-time personalization
- Compliance and consent management
- Cost optimization with provider arbitrage
- Zero-downtime global deployments

---

## Database Schema

```json
{
  "storage_layers": {
    "postgresql_regional": {
      "purpose": "Regional notification data",
      "tables": [
        {
          "name": "notifications",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "global_id", "type": "UUID", "constraints": "UNIQUE NOT NULL"},
            {"name": "tenant_id", "type": "UUID", "constraints": "NOT NULL"},
            {"name": "user_id", "type": "BIGINT", "constraints": "NOT NULL"},
            {"name": "journey_id", "type": "UUID"},
            {"name": "category", "type": "VARCHAR(50)"},
            {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
            {"name": "priority", "type": "INTEGER"},
            {"name": "status", "type": "VARCHAR(20)"},
            {"name": "ml_send_time", "type": "TIMESTAMP"},
            {"name": "ml_channel_score", "type": "FLOAT"},
            {"name": "provider", "type": "VARCHAR(50)"},
            {"name": "provider_cost", "type": "DECIMAL(10,6)"},
            {"name": "payload", "type": "JSONB"},
            {"name": "personalization", "type": "JSONB"},
            {"name": "consent_snapshot", "type": "JSONB"},
            {"name": "created_at", "type": "TIMESTAMP"},
            {"name": "sent_at", "type": "TIMESTAMP"},
            {"name": "delivered_at", "type": "TIMESTAMP"},
            {"name": "engaged_at", "type": "TIMESTAMP"}
          ],
          "partitioning": {
            "type": "RANGE",
            "column": "created_at",
            "interval": "1 day"
          }
        },
        {
          "name": "user_profiles",
          "description": "Enriched user data for personalization",
          "columns": [
            {"name": "user_id", "type": "BIGINT", "constraints": "PRIMARY KEY"},
            {"name": "tenant_id", "type": "UUID", "constraints": "NOT NULL"},
            {"name": "email", "type": "VARCHAR(255)"},
            {"name": "phone", "type": "VARCHAR(20)"},
            {"name": "device_tokens", "type": "JSONB"},
            {"name": "timezone", "type": "VARCHAR(50)"},
            {"name": "language", "type": "VARCHAR(10)"},
            {"name": "preferred_channel", "type": "VARCHAR(20)"},
            {"name": "engagement_scores", "type": "JSONB"},
            {"name": "optimal_send_times", "type": "JSONB"},
            {"name": "segment_memberships", "type": "JSONB"},
            {"name": "ml_features", "type": "JSONB"},
            {"name": "updated_at", "type": "TIMESTAMP"}
          ]
        },
        {
          "name": "consent_records",
          "description": "GDPR/CCPA compliance",
          "columns": [
            {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
            {"name": "user_id", "type": "BIGINT", "constraints": "NOT NULL"},
            {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
            {"name": "category", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
            {"name": "consent_given", "type": "BOOLEAN", "constraints": "NOT NULL"},
            {"name": "consent_source", "type": "VARCHAR(100)"},
            {"name": "ip_address", "type": "INET"},
            {"name": "user_agent", "type": "TEXT"},
            {"name": "created_at", "type": "TIMESTAMP"},
            {"name": "expires_at", "type": "TIMESTAMP"}
          ],
          "indexes": [
            {"columns": ["user_id", "channel", "category"], "unique": true}
          ]
        }
      ]
    },
    "cockroachdb_global": {
      "purpose": "Global coordination and metadata",
      "tables": [
        {
          "name": "journeys",
          "description": "Cross-channel notification journeys",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "tenant_id", "type": "UUID", "constraints": "NOT NULL"},
            {"name": "name", "type": "VARCHAR(100)", "constraints": "NOT NULL"},
            {"name": "trigger_event", "type": "VARCHAR(100)"},
            {"name": "steps", "type": "JSONB", "constraints": "NOT NULL"},
            {"name": "audience_rules", "type": "JSONB"},
            {"name": "status", "type": "VARCHAR(20)"},
            {"name": "version", "type": "INTEGER"},
            {"name": "created_at", "type": "TIMESTAMPTZ"}
          ]
        },
        {
          "name": "journey_instances",
          "description": "User journey state",
          "columns": [
            {"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"},
            {"name": "journey_id", "type": "UUID", "constraints": "NOT NULL"},
            {"name": "user_id", "type": "BIGINT", "constraints": "NOT NULL"},
            {"name": "current_step", "type": "INTEGER"},
            {"name": "state", "type": "JSONB"},
            {"name": "started_at", "type": "TIMESTAMPTZ"},
            {"name": "completed_at", "type": "TIMESTAMPTZ"},
            {"name": "status", "type": "VARCHAR(20)"}
          ]
        },
        {
          "name": "global_configs",
          "columns": [
            {"name": "key", "type": "VARCHAR(255)", "constraints": "PRIMARY KEY"},
            {"name": "value", "type": "JSONB"},
            {"name": "version", "type": "INTEGER"},
            {"name": "updated_at", "type": "TIMESTAMPTZ"}
          ]
        },
        {
          "name": "provider_health",
          "columns": [
            {"name": "provider", "type": "VARCHAR(50)", "constraints": "PRIMARY KEY"},
            {"name": "region", "type": "VARCHAR(50)"},
            {"name": "status", "type": "VARCHAR(20)"},
            {"name": "latency_p99_ms", "type": "INTEGER"},
            {"name": "error_rate", "type": "FLOAT"},
            {"name": "cost_per_message", "type": "DECIMAL(10,6)"},
            {"name": "updated_at", "type": "TIMESTAMPTZ"}
          ]
        }
      ]
    },
    "redis_regional": {
      "data_structures": [
        {
          "name": "queue:{region}:{channel}:{priority}",
          "type": "LIST",
          "description": "Regional priority queues"
        },
        {
          "name": "ml_send_queue",
          "type": "ZSET",
          "description": "ML-optimized send times (score = optimal_send_timestamp)"
        },
        {
          "name": "journey_state:{journey_instance_id}",
          "type": "HASH",
          "description": "Real-time journey state"
        },
        {
          "name": "user_context:{user_id}",
          "type": "HASH",
          "description": "Real-time user context for personalization"
        },
        {
          "name": "provider_circuit:{provider}",
          "type": "HASH",
          "description": "Circuit breaker state"
        },
        {
          "name": "cost_tracking:{tenant}:{date}",
          "type": "HASH",
          "description": "Real-time cost tracking"
        }
      ]
    },
    "kafka": {
      "topics": [
        {
          "name": "notification-events",
          "partitions": 32,
          "retention": "7 days",
          "events": ["sent", "delivered", "opened", "clicked", "bounced", "unsubscribed"]
        },
        {
          "name": "user-events",
          "partitions": 32,
          "description": "User behavior for ML features"
        },
        {
          "name": "journey-events",
          "partitions": 16,
          "description": "Journey progression events"
        },
        {
          "name": "cross-region-sync",
          "partitions": 8,
          "description": "Cross-region data synchronization"
        }
      ]
    },
    "ml_feature_store": {
      "type": "Feast + Redis",
      "features": [
        {
          "name": "user_engagement_features",
          "entities": ["user_id"],
          "features": [
            "email_open_rate_7d",
            "email_click_rate_7d",
            "push_open_rate_7d",
            "sms_response_rate_7d",
            "preferred_send_hour",
            "preferred_day_of_week",
            "avg_response_time_minutes",
            "engagement_recency_days",
            "channel_preference_score"
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
      "method": "POST",
      "path": "/api/v1/notifications",
      "description": "Send with ML optimization",
      "request_body": {
        "user_id": "string (required)",
        "category": "string (required)",
        "template": "string",
        "data": {},
        "priority": "integer (0-10)",
        "optimization": {
          "send_time": "now | optimal | scheduled",
          "scheduled_at": "ISO8601 (if scheduled)",
          "channel_selection": "all | optimal | specified",
          "channels": ["email", "push"]
        },
        "personalization": {
          "enabled": true,
          "context": {}
        },
        "journey_id": "uuid (optional)",
        "metadata": {}
      },
      "responses": {
        "201": {
          "notification_id": "uuid",
          "status": "queued | ml_scheduled",
          "channels": ["email"],
          "ml_predictions": {
            "optimal_send_time": "2024-01-01T10:30:00Z",
            "channel_scores": {
              "email": 0.85,
              "push": 0.72,
              "sms": 0.45
            },
            "predicted_engagement": 0.23
          }
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/journeys",
      "description": "Create notification journey",
      "request_body": {
        "name": "Onboarding Flow",
        "trigger": {
          "type": "event",
          "event_name": "user_signup"
        },
        "steps": [
          {
            "id": "welcome",
            "type": "notification",
            "delay": "0m",
            "template": "welcome_email",
            "channels": ["email"]
          },
          {
            "id": "tips",
            "type": "notification",
            "delay": "24h",
            "template": "getting_started",
            "channels": ["push"],
            "condition": "!completed_onboarding"
          },
          {
            "id": "branch",
            "type": "branch",
            "conditions": [
              {"if": "engagement_score > 0.7", "goto": "power_user"},
              {"else": "goto": "nurture"}
            ]
          }
        ],
        "exit_conditions": [
          "user_converted",
          "user_unsubscribed"
        ]
      },
      "responses": {
        "201": {"journey_id": "uuid", "status": "active"}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/journeys/{journey_id}/trigger",
      "description": "Trigger journey for user",
      "request_body": {
        "user_id": "string",
        "context": {}
      },
      "responses": {
        "201": {"journey_instance_id": "uuid"}
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/ml/predictions/{user_id}",
      "description": "Get ML predictions for user",
      "responses": {
        "200": {
          "user_id": "user_123",
          "optimal_send_times": {
            "email": ["10:00", "14:00", "19:00"],
            "push": ["08:00", "12:00", "20:00"]
          },
          "channel_preferences": {
            "email": 0.85,
            "push": 0.72,
            "sms": 0.45
          },
          "engagement_prediction": {
            "email_open_probability": 0.42,
            "push_open_probability": 0.38,
            "click_probability": 0.12
          },
          "churn_risk": 0.15,
          "segments": ["high_value", "mobile_first"]
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/analytics/cost",
      "description": "Cost analytics and optimization",
      "query_params": {
        "start_date": "ISO8601",
        "end_date": "ISO8601",
        "group_by": "channel | provider | category"
      },
      "responses": {
        "200": {
          "total_cost": 12500.00,
          "total_sent": 5000000,
          "cost_per_message": 0.0025,
          "by_provider": {
            "sendgrid": {"sent": 3000000, "cost": 6000.00, "cpm": 2.00},
            "ses": {"sent": 2000000, "cost": 2000.00, "cpm": 1.00}
          },
          "optimization_savings": 3500.00,
          "recommendations": [
            "Shift 20% of volume to SES for $500/month savings"
          ]
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/compliance/consent/{user_id}",
      "description": "Get user consent status",
      "responses": {
        "200": {
          "user_id": "user_123",
          "consents": [
            {
              "channel": "email",
              "category": "marketing",
              "consented": true,
              "source": "signup_form",
              "timestamp": "2024-01-01T00:00:00Z"
            }
          ],
          "gdpr_status": "consented",
          "ccpa_status": "not_opted_out"
        }
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/compliance/consent",
      "description": "Record consent change",
      "request_body": {
        "user_id": "string",
        "channel": "email",
        "category": "marketing",
        "consented": false,
        "source": "preference_center"
      },
      "responses": {
        "200": {"recorded": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/personalization/context",
      "description": "Update user context for personalization",
      "request_body": {
        "user_id": "string",
        "context": {
          "last_product_viewed": "product_123",
          "cart_value": 150.00,
          "session_count": 5
        }
      },
      "responses": {
        "200": {"updated": true}
      }
    }
  ]
}
```

---

## System Design

### Architecture Diagram

```
                        Notification System - L7 Global Architecture
    ════════════════════════════════════════════════════════════════════════════════════

                                    ┌────────────────────┐
                                    │    Global DNS      │
                                    │   (GeoDNS Routing) │
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
    │  │                          API GATEWAY LAYER                                  │ │
    │  │                                                                             │ │
    │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │ │
    │  │  │   API Gateway   │  │  Auth Service   │  │  Rate Limiter   │             │ │
    │  │  │                 │  │                 │  │                 │             │ │
    │  │  │ • Geo routing   │  │ • JWT/API Key   │  │ • Token bucket  │             │ │
    │  │  │ • Load balance  │  │ • Tenant auth   │  │ • Tenant quotas │             │ │
    │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘             │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                                         ▼                                        │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                      NOTIFICATION SERVICE LAYER                             │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                    INTELLIGENT ORCHESTRATOR                           │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │ │
    │  │  │  │ ML Send     │  │ ML Channel  │  │ Personaliz- │  │ Consent     │  │  │ │
    │  │  │  │ Time Opt    │  │ Selector    │  │ ation Eng   │  │ Manager     │  │  │ │
    │  │  │  │             │  │             │  │             │  │             │  │  │ │
    │  │  │  │ • Optimal   │  │ • Score     │  │ • Real-time │  │ • GDPR      │  │  │ │
    │  │  │  │   send time │  │   channels  │  │   context   │  │ • CCPA      │  │  │ │
    │  │  │  │ • User      │  │ • User pref │  │ • Dynamic   │  │ • Consent   │  │  │ │
    │  │  │  │   timezone  │  │ • Predict   │  │   content   │  │   checks    │  │  │ │
    │  │  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                      JOURNEY ENGINE                                   │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  • Multi-step workflows      • Branching logic                        │  │ │
    │  │  │  • Wait conditions           • Exit triggers                          │  │ │
    │  │  │  • Cross-channel orchestration                                        │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                                         ▼                                        │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                      SMART QUEUE SYSTEM                                     │ │
    │  │                                                                             │ │
    │  │  ┌───────────────────────────────────────────────────────────────────┐     │ │
    │  │  │                    ML-Optimized Queue                              │     │ │
    │  │  │                    (ZSET by optimal_send_time)                     │     │ │
    │  │  │                                                                    │     │ │
    │  │  │  Scheduler polls and moves to channel queues at optimal time       │     │ │
    │  │  └───────────────────────────────────────────────────────────────────┘     │ │
    │  │                              │                                              │ │
    │  │                              ▼                                              │ │
    │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │ │
    │  │  │ Email Queues    │  │ Push Queues     │  │ SMS Queues      │             │ │
    │  │  │ (by priority)   │  │ (by priority)   │  │ (by priority)   │             │ │
    │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘             │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    │                                         ▼                                        │
    │  ┌────────────────────────────────────────────────────────────────────────────┐ │
    │  │                      DELIVERY LAYER                                         │ │
    │  │                                                                             │ │
    │  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
    │  │  │                   SMART PROVIDER ROUTER                               │  │ │
    │  │  │                                                                       │  │ │
    │  │  │  • Cost optimization (cheapest healthy provider)                      │  │ │
    │  │  │  • Latency-based routing                                              │  │ │
    │  │  │  • Circuit breaker per provider                                       │  │ │
    │  │  │  • Real-time health monitoring                                        │  │ │
    │  │  └──────────────────────────────────────────────────────────────────────┘  │ │
    │  │                                                                             │ │
    │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │ │
    │  │  │ Email Workers   │  │ Push Workers    │  │ SMS Workers     │             │ │
    │  │  │                 │  │                 │  │                 │             │ │
    │  │  │ SendGrid ◄──┐   │  │ FCM ◄───────┐   │  │ Twilio ◄────┐   │             │ │
    │  │  │ SES ◄───────┼   │  │ APNS ◄──────┼   │  │ Nexmo ◄─────┼   │             │ │
    │  │  │ Mailgun ◄───┘   │  │ WebPush ◄───┘   │  │ Plivo ◄─────┘   │             │ │
    │  │  │                 │  │                 │  │                 │             │ │
    │  │  │ (Cost + Health  │  │ (Platform       │  │ (Cost + Region  │             │ │
    │  │  │  based routing) │  │  routing)       │  │  based routing) │             │ │
    │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘             │ │
    │  └────────────────────────────────────────────────────────────────────────────┘ │
    │                                         │                                        │
    └─────────────────────────────────────────┼────────────────────────────────────────┘
                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                           ML PLATFORM                                            │
    │                                                                                  │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
    │  │  Feature Store      │  │  Model Serving      │  │  Training Pipeline  │      │
    │  │  (Feast + Redis)    │  │  (TensorFlow Serving)│  │  (Vertex AI)        │      │
    │  │                     │  │                     │  │                     │      │
    │  │ • User engagement   │  │ • Send time model   │  │ • Daily retraining  │      │
    │  │ • Channel prefs     │  │ • Channel selection │  │ • A/B test analysis │      │
    │  │ • Behavior signals  │  │ • Churn prediction  │  │ • Feature discovery │      │
    │  │ • Real-time updates │  │ • < 10ms inference  │  │                     │      │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                        GLOBAL COORDINATION                                       │
    │                                                                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │                    CockroachDB (Multi-Region)                            │   │
    │  │                                                                          │   │
    │  │  • Journey definitions        • Global configs                           │   │
    │  │  • Journey instances          • Provider health                          │   │
    │  │  • Cross-region user data     • Cost tracking                            │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    │                                                                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────┐   │
    │  │                    Kafka (Cross-Region)                                  │   │
    │  │                                                                          │   │
    │  │  • notification-events (sent, delivered, engaged)                        │   │
    │  │  • user-events (behavior signals)                                        │   │
    │  │  • journey-events (progression)                                          │   │
    │  │  • cross-region-sync                                                     │   │
    │  └─────────────────────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────────────────────┘

                                              │
                                              ▼
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                        OBSERVABILITY & ANALYTICS                                 │
    │                                                                                  │
    │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐      │
    │  │  Prometheus +       │  │  ClickHouse         │  │  Cost Analytics     │      │
    │  │  Grafana            │  │                     │  │                     │      │
    │  │                     │  │ • Engagement metrics│  │ • Provider costs    │      │
    │  │ • Delivery rates    │  │ • Journey analytics │  │ • Budget tracking   │      │
    │  │ • Latency histo     │  │ • A/B test results  │  │ • Optimization recs │      │
    │  │ • Provider health   │  │ • Cohort analysis   │  │ • Forecasting       │      │
    │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘      │
    └─────────────────────────────────────────────────────────────────────────────────┘
```

### ML-Powered Send Time Optimization

```python
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

@dataclass
class MLPrediction:
    optimal_send_time: datetime
    channel_scores: Dict[str, float]
    engagement_probability: float
    confidence: float

@dataclass
class UserFeatures:
    user_id: str
    timezone: str
    email_open_rate: float
    push_open_rate: float
    sms_response_rate: float
    preferred_hours: List[int]
    preferred_channels: Dict[str, float]
    engagement_recency_days: int
    segments: List[str]

class MLSendTimeOptimizer:
    """
    ML-based send time optimization using user engagement patterns.

    Features used:
    - Historical open/click times by user
    - Timezone-aware delivery
    - Day-of-week patterns
    - Channel-specific engagement
    """

    def __init__(
        self,
        model_service,
        feature_store,
        redis_client
    ):
        self.model = model_service
        self.feature_store = feature_store
        self.redis = redis_client

    async def get_optimal_send_time(
        self,
        user_id: str,
        channel: str,
        category: str,
        priority: int
    ) -> MLPrediction:
        """
        Predict optimal send time for user/channel combination.
        """
        # Get user features
        features = await self._get_user_features(user_id)

        if features is None:
            # New user - use category defaults
            return self._get_default_prediction(channel, category)

        # Get ML prediction
        prediction = await self.model.predict_send_time({
            "user_features": features.__dict__,
            "channel": channel,
            "category": category,
            "current_time": datetime.utcnow().isoformat()
        })

        # Apply priority adjustments
        if priority <= 2:
            # High priority - send now
            return MLPrediction(
                optimal_send_time=datetime.utcnow(),
                channel_scores={channel: 1.0},
                engagement_probability=prediction["engagement_prob"],
                confidence=prediction["confidence"]
            )

        # Convert to user's timezone
        optimal_time = self._convert_to_user_timezone(
            prediction["optimal_hour"],
            features.timezone
        )

        return MLPrediction(
            optimal_send_time=optimal_time,
            channel_scores=prediction["channel_scores"],
            engagement_probability=prediction["engagement_prob"],
            confidence=prediction["confidence"]
        )

    async def _get_user_features(self, user_id: str) -> Optional[UserFeatures]:
        """Get user features from feature store."""
        # Check Redis cache first
        cache_key = f"user_features:{user_id}"
        cached = self.redis.hgetall(cache_key)

        if cached:
            return UserFeatures(**{k.decode(): v for k, v in cached.items()})

        # Fetch from feature store
        features = await self.feature_store.get_features(
            entity_name="user",
            entity_id=user_id,
            feature_names=[
                "email_open_rate_7d",
                "push_open_rate_7d",
                "sms_response_rate_7d",
                "preferred_send_hours",
                "channel_preference_score",
                "engagement_recency_days",
                "segment_memberships",
                "timezone"
            ]
        )

        if not features:
            return None

        user_features = UserFeatures(
            user_id=user_id,
            timezone=features.get("timezone", "UTC"),
            email_open_rate=features.get("email_open_rate_7d", 0.2),
            push_open_rate=features.get("push_open_rate_7d", 0.3),
            sms_response_rate=features.get("sms_response_rate_7d", 0.1),
            preferred_hours=features.get("preferred_send_hours", [9, 12, 18]),
            preferred_channels=features.get("channel_preference_score", {}),
            engagement_recency_days=features.get("engagement_recency_days", 0),
            segments=features.get("segment_memberships", [])
        )

        # Cache for 1 hour
        self.redis.hmset(cache_key, user_features.__dict__)
        self.redis.expire(cache_key, 3600)

        return user_features


class IntelligentChannelSelector:
    """
    ML-based channel selection that maximizes engagement
    while respecting user preferences and costs.
    """

    def __init__(
        self,
        model_service,
        feature_store,
        cost_service
    ):
        self.model = model_service
        self.feature_store = feature_store
        self.cost_service = cost_service

    async def select_channels(
        self,
        user_id: str,
        available_channels: List[str],
        category: str,
        budget_constraint: float = None
    ) -> List[Tuple[str, float]]:
        """
        Select optimal channel(s) for notification.

        Returns list of (channel, score) tuples, sorted by score.
        """
        # Get user engagement features
        features = await self.feature_store.get_features(
            entity_name="user",
            entity_id=user_id,
            feature_names=[
                "email_engagement_score",
                "push_engagement_score",
                "sms_engagement_score",
                "channel_fatigue_scores",
                "recent_channel_interactions"
            ]
        )

        channel_scores = []

        for channel in available_channels:
            # Get ML engagement prediction
            engagement_score = await self._predict_engagement(
                user_id, channel, category, features
            )

            # Get channel cost
            cost = await self.cost_service.get_channel_cost(channel)

            # Apply fatigue penalty
            fatigue = features.get("channel_fatigue_scores", {}).get(channel, 0)
            adjusted_score = engagement_score * (1 - fatigue * 0.3)

            # Cost-adjusted score
            if budget_constraint:
                cost_factor = 1 - (cost / budget_constraint)
                adjusted_score *= max(0.5, cost_factor)

            channel_scores.append((channel, adjusted_score, cost))

        # Sort by adjusted score
        channel_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top channels (could be multi-channel)
        return [(c, s) for c, s, _ in channel_scores if s > 0.3]

    async def _predict_engagement(
        self,
        user_id: str,
        channel: str,
        category: str,
        features: Dict
    ) -> float:
        """Predict engagement probability for channel."""
        prediction = await self.model.predict({
            "user_id": user_id,
            "channel": channel,
            "category": category,
            "features": features
        })

        return prediction["engagement_probability"]


class JourneyOrchestrator:
    """
    Orchestrates multi-step notification journeys with
    branching logic and cross-channel coordination.
    """

    def __init__(
        self,
        redis_client,
        db_connection,
        notification_service,
        event_publisher
    ):
        self.redis = redis_client
        self.db = db_connection
        self.notification_service = notification_service
        self.event_publisher = event_publisher

    async def trigger_journey(
        self,
        journey_id: str,
        user_id: str,
        context: Dict
    ) -> str:
        """Start a journey for a user."""
        # Get journey definition
        journey = await self._get_journey(journey_id)

        # Check if user is already in journey
        existing = await self._get_active_instance(journey_id, user_id)
        if existing:
            return existing["id"]  # Already in journey

        # Create journey instance
        instance_id = await self._create_instance(
            journey_id=journey_id,
            user_id=user_id,
            context=context
        )

        # Start at first step
        await self._execute_step(instance_id, journey, 0, context)

        return instance_id

    async def _execute_step(
        self,
        instance_id: str,
        journey: Dict,
        step_index: int,
        context: Dict
    ):
        """Execute a journey step."""
        if step_index >= len(journey["steps"]):
            # Journey complete
            await self._complete_journey(instance_id)
            return

        step = journey["steps"][step_index]

        # Check conditions
        if "condition" in step:
            if not await self._evaluate_condition(step["condition"], context):
                # Skip this step
                await self._execute_step(instance_id, journey, step_index + 1, context)
                return

        # Handle step type
        if step["type"] == "notification":
            await self._handle_notification_step(instance_id, step, context)
        elif step["type"] == "wait":
            await self._handle_wait_step(instance_id, journey, step_index, step, context)
        elif step["type"] == "branch":
            await self._handle_branch_step(instance_id, journey, step, context)

    async def _handle_notification_step(
        self,
        instance_id: str,
        step: Dict,
        context: Dict
    ):
        """Send notification as part of journey."""
        instance = await self._get_instance(instance_id)

        result = await self.notification_service.send_notification(
            tenant_id=instance["tenant_id"],
            user_id=instance["user_id"],
            category=step.get("category"),
            template=step["template"],
            data=context,
            channels=step.get("channels"),
            journey_id=instance_id
        )

        # Update journey state
        await self._update_instance_state(
            instance_id,
            {
                "last_notification": result,
                "current_step": step["id"]
            }
        )

        # Publish event
        await self.event_publisher.publish(
            topic="journey-events",
            event={
                "type": "step_completed",
                "instance_id": instance_id,
                "step_id": step["id"],
                "notification_id": result.get("notification_id")
            }
        )

    async def _handle_wait_step(
        self,
        instance_id: str,
        journey: Dict,
        step_index: int,
        step: Dict,
        context: Dict
    ):
        """Schedule next step after delay."""
        delay = self._parse_delay(step["delay"])
        next_execute_at = time.time() + delay.total_seconds()

        # Store continuation state
        continuation = {
            "instance_id": instance_id,
            "journey_id": journey["id"],
            "next_step": step_index + 1,
            "context": context
        }

        # Schedule in sorted set
        self.redis.zadd(
            "journey_continuations",
            {json.dumps(continuation): next_execute_at}
        )

    async def _handle_branch_step(
        self,
        instance_id: str,
        journey: Dict,
        step: Dict,
        context: Dict
    ):
        """Handle branching logic."""
        for condition in step["conditions"]:
            if "if" in condition:
                if await self._evaluate_condition(condition["if"], context):
                    target_step = self._find_step_index(journey, condition["goto"])
                    await self._execute_step(instance_id, journey, target_step, context)
                    return
            elif "else" in condition:
                target_step = self._find_step_index(journey, condition["goto"])
                await self._execute_step(instance_id, journey, target_step, context)
                return


class SmartProviderRouter:
    """
    Routes notifications to optimal provider based on:
    - Cost optimization
    - Health/availability
    - Latency
    - Region
    """

    def __init__(
        self,
        provider_registry: Dict,
        health_monitor,
        cost_tracker
    ):
        self.providers = provider_registry
        self.health = health_monitor
        self.costs = cost_tracker

    async def select_provider(
        self,
        channel: str,
        region: str,
        priority: int,
        tenant_cost_preference: str = "balanced"
    ) -> str:
        """Select optimal provider for notification."""
        candidates = self.providers.get(channel, {})

        if not candidates:
            raise ValueError(f"No providers for channel: {channel}")

        scored_providers = []

        for provider_name, provider in candidates.items():
            # Check health (circuit breaker)
            health_status = await self.health.get_status(provider_name)
            if health_status["status"] == "unhealthy":
                continue

            # Get metrics
            latency_p99 = health_status.get("latency_p99_ms", 1000)
            error_rate = health_status.get("error_rate", 0)
            cost_per_msg = await self.costs.get_cost(provider_name)

            # Calculate composite score
            score = self._calculate_score(
                latency_p99=latency_p99,
                error_rate=error_rate,
                cost=cost_per_msg,
                priority=priority,
                cost_preference=tenant_cost_preference
            )

            scored_providers.append((provider_name, score))

        if not scored_providers:
            raise Exception("No healthy providers available")

        # Sort by score (higher is better)
        scored_providers.sort(key=lambda x: x[1], reverse=True)

        return scored_providers[0][0]

    def _calculate_score(
        self,
        latency_p99: int,
        error_rate: float,
        cost: float,
        priority: int,
        cost_preference: str
    ) -> float:
        """Calculate provider selection score."""
        # Normalize metrics (0-1 scale, higher is better)
        latency_score = max(0, 1 - latency_p99 / 2000)  # 2s max
        reliability_score = 1 - error_rate
        cost_score = max(0, 1 - cost / 0.01)  # $0.01 max

        # Weight based on preference and priority
        if priority <= 2:
            # High priority - prioritize speed and reliability
            weights = {"latency": 0.4, "reliability": 0.5, "cost": 0.1}
        elif cost_preference == "cost_optimized":
            weights = {"latency": 0.2, "reliability": 0.3, "cost": 0.5}
        else:  # balanced
            weights = {"latency": 0.3, "reliability": 0.4, "cost": 0.3}

        return (
            latency_score * weights["latency"] +
            reliability_score * weights["reliability"] +
            cost_score * weights["cost"]
        )
```

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | ML send time | Request optimal send | Time within user's active hours |
| F-02 | Channel selection | ML channel choice | Highest engagement channel selected |
| F-03 | Journey trigger | Start onboarding | First step executed |
| F-04 | Journey wait | Step with delay | Next step scheduled |
| F-05 | Journey branch | Conditional path | Correct branch taken |
| F-06 | Journey exit | Exit condition met | Journey completed |
| F-07 | Personalization | Dynamic content | Variables substituted |
| F-08 | Consent check | Marketing to opted-out | Notification blocked |
| F-09 | Provider selection | Multiple providers | Optimal provider chosen |
| F-10 | Provider failover | Primary unhealthy | Fallback used |
| F-11 | Cost tracking | Send notification | Cost recorded |
| F-12 | Cross-region | EU user | EU region serves |
| F-13 | Real-time context | Update context | Personalization updated |
| F-14 | Multi-channel journey | Email then push | Both sent in sequence |
| F-15 | GDPR deletion | Delete request | All data removed |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | ML inference | Send time prediction | < 10ms p99 |
| P-02 | Channel scoring | Multi-channel scoring | < 15ms p99 |
| P-03 | Journey trigger | Start journey | < 50ms p99 |
| P-04 | Feature store | Feature retrieval | < 5ms p99 |
| P-05 | Global throughput | All regions | > 500K/s |
| P-06 | Cross-region latency | US to EU | < 100ms p99 |
| P-07 | Journey processing | Steps per second | > 10K/s |
| P-08 | Personalization | Real-time render | < 20ms p99 |
| P-09 | Provider routing | Selection latency | < 2ms |
| P-10 | Cost calculation | Per notification | < 1ms |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Region failure | Kill US-EAST-1 | Other regions serve |
| C-02 | ML service down | No predictions | Fall back to defaults |
| C-03 | Feature store down | No features | Graceful degradation |
| C-04 | All providers down | No delivery | Queue and retry |
| C-05 | Kafka partition | Message delay | Eventual delivery |
| C-06 | CockroachDB split | Network partition | Continue serving |
| C-07 | Cost spike | Provider expensive | Route to cheaper |
| C-08 | Journey timeout | Step hangs | Timeout and continue |
| C-09 | Memory pressure | OOM risk | Graceful shedding |
| C-10 | Clock skew | 30s drift | Correct behavior |

### ML Model Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| M-01 | Model accuracy | Send time prediction | > 70% within optimal window |
| M-02 | Channel accuracy | Channel selection | > 60% correct top channel |
| M-03 | Cold start | New user | Reasonable defaults |
| M-04 | Model staleness | Old model | Automatic refresh |
| M-05 | Feature drift | Changed patterns | Model adapts |

---

## Capacity Estimates

### Global Scale

- **Daily notifications**: 1B
- **Peak rate**: 100K/second
- **Regions**: 3 (US, EU, APAC)
- **Tenants**: 10K
- **Users**: 1B

### Per-Region Resources

- **API instances**: 50 (auto-scaled)
- **Worker instances**: 100 (auto-scaled)
- **Redis**: 500GB
- **PostgreSQL**: 2TB

### ML Platform

- **Feature store**: 100GB
- **Model inference**: 50K predictions/second
- **Training data**: 1TB (30-day retention)

### Cost Targets

- **Average cost per notification**: $0.001
- **ML inference cost**: $0.0001/prediction
- **Provider optimization savings**: 30%

---

## Key Considerations for L7

1. **ML integration**: Send time, channel selection, and engagement prediction
2. **Journey orchestration**: Complex multi-step, cross-channel workflows
3. **Global scale**: Multi-region with geo-aware routing
4. **Cost optimization**: Provider arbitrage and budget management
5. **Compliance**: GDPR, CCPA, and consent management
6. **Real-time personalization**: Context-aware content
7. **Observability**: End-to-end tracing across regions and providers
