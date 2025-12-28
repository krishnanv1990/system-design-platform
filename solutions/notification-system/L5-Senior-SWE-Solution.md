# Notification System - L5 (Senior Software Engineer) Solution

## Level Requirements

**Target Role:** Senior Software Engineer (L5)
**Focus:** Core notification delivery with basic channel support

### What's Expected at L5

- Multi-channel notification delivery (Email, Push, SMS)
- Basic message templating
- Queue-based async processing
- Delivery status tracking
- Simple retry mechanism
- User preference management

---

## Database Schema

```json
{
  "database": "PostgreSQL",
  "tables": [
    {
      "name": "users",
      "description": "User accounts and notification settings",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "email", "type": "VARCHAR(255)", "constraints": "UNIQUE NOT NULL"},
        {"name": "phone", "type": "VARCHAR(20)"},
        {"name": "device_token", "type": "VARCHAR(255)"},
        {"name": "timezone", "type": "VARCHAR(50)", "constraints": "DEFAULT 'UTC'"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
      ],
      "indexes": [
        {"name": "idx_users_email", "columns": ["email"]}
      ]
    },
    {
      "name": "notification_preferences",
      "description": "User channel preferences",
      "columns": [
        {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
        {"name": "user_id", "type": "BIGINT", "constraints": "REFERENCES users(id)"},
        {"name": "notification_type", "type": "VARCHAR(50)", "constraints": "NOT NULL"},
        {"name": "email_enabled", "type": "BOOLEAN", "constraints": "DEFAULT true"},
        {"name": "push_enabled", "type": "BOOLEAN", "constraints": "DEFAULT true"},
        {"name": "sms_enabled", "type": "BOOLEAN", "constraints": "DEFAULT false"},
        {"name": "quiet_hours_start", "type": "TIME"},
        {"name": "quiet_hours_end", "type": "TIME"}
      ],
      "indexes": [
        {"name": "idx_prefs_user_type", "columns": ["user_id", "notification_type"], "unique": true}
      ]
    },
    {
      "name": "notification_templates",
      "description": "Message templates",
      "columns": [
        {"name": "id", "type": "SERIAL", "constraints": "PRIMARY KEY"},
        {"name": "name", "type": "VARCHAR(100)", "constraints": "UNIQUE NOT NULL"},
        {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
        {"name": "subject", "type": "VARCHAR(255)"},
        {"name": "body", "type": "TEXT", "constraints": "NOT NULL"},
        {"name": "variables", "type": "JSONB", "constraints": "DEFAULT '[]'"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
      ]
    },
    {
      "name": "notifications",
      "description": "Notification records",
      "columns": [
        {"name": "id", "type": "BIGSERIAL", "constraints": "PRIMARY KEY"},
        {"name": "user_id", "type": "BIGINT", "constraints": "REFERENCES users(id)"},
        {"name": "template_id", "type": "INTEGER", "constraints": "REFERENCES notification_templates(id)"},
        {"name": "channel", "type": "VARCHAR(20)", "constraints": "NOT NULL"},
        {"name": "status", "type": "VARCHAR(20)", "constraints": "DEFAULT 'pending'"},
        {"name": "payload", "type": "JSONB", "constraints": "NOT NULL"},
        {"name": "sent_at", "type": "TIMESTAMP"},
        {"name": "delivered_at", "type": "TIMESTAMP"},
        {"name": "failed_at", "type": "TIMESTAMP"},
        {"name": "error_message", "type": "TEXT"},
        {"name": "retry_count", "type": "INTEGER", "constraints": "DEFAULT 0"},
        {"name": "created_at", "type": "TIMESTAMP", "constraints": "DEFAULT NOW()"}
      ],
      "indexes": [
        {"name": "idx_notifications_user", "columns": ["user_id", "created_at"]},
        {"name": "idx_notifications_status", "columns": ["status", "created_at"]}
      ]
    }
  ],
  "message_queue": {
    "type": "Redis",
    "queues": [
      {
        "name": "notifications:email",
        "type": "LIST",
        "description": "Email notification queue"
      },
      {
        "name": "notifications:push",
        "type": "LIST",
        "description": "Push notification queue"
      },
      {
        "name": "notifications:sms",
        "type": "LIST",
        "description": "SMS notification queue"
      },
      {
        "name": "notifications:retry",
        "type": "ZSET",
        "description": "Retry queue with scheduled time as score"
      }
    ]
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
      "description": "Send a notification",
      "request_body": {
        "user_id": "integer (required)",
        "type": "string (required, e.g., 'order_confirmation')",
        "channels": "array (optional, default: user preferences)",
        "template_id": "integer (optional)",
        "data": {
          "order_id": "string",
          "amount": "number",
          "custom_field": "any"
        },
        "scheduled_at": "ISO8601 (optional)"
      },
      "responses": {
        "201": {
          "notification_id": 12345,
          "status": "queued",
          "channels": ["email", "push"]
        },
        "400": {"error": "Invalid request"},
        "404": {"error": "User not found"}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/notifications/batch",
      "description": "Send notifications to multiple users",
      "request_body": {
        "user_ids": [1, 2, 3],
        "type": "string",
        "data": {}
      },
      "responses": {
        "202": {
          "batch_id": "uuid",
          "queued": 3,
          "estimated_completion": "2024-01-01T00:05:00Z"
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/notifications/{id}",
      "description": "Get notification status",
      "responses": {
        "200": {
          "id": 12345,
          "user_id": 1,
          "channel": "email",
          "status": "delivered",
          "sent_at": "2024-01-01T00:00:00Z",
          "delivered_at": "2024-01-01T00:00:05Z"
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/users/{user_id}/notifications",
      "description": "Get user's notification history",
      "query_params": {
        "limit": "integer (default: 20)",
        "offset": "integer (default: 0)",
        "status": "string (optional filter)"
      },
      "responses": {
        "200": {
          "notifications": [],
          "total": 100,
          "limit": 20,
          "offset": 0
        }
      }
    },
    {
      "method": "GET",
      "path": "/api/v1/users/{user_id}/preferences",
      "description": "Get notification preferences",
      "responses": {
        "200": {
          "user_id": 1,
          "preferences": [
            {
              "type": "marketing",
              "email": true,
              "push": false,
              "sms": false
            }
          ]
        }
      }
    },
    {
      "method": "PUT",
      "path": "/api/v1/users/{user_id}/preferences",
      "description": "Update notification preferences",
      "request_body": {
        "preferences": [
          {
            "type": "marketing",
            "email": false,
            "push": true
          }
        ]
      },
      "responses": {
        "200": {"updated": true}
      }
    },
    {
      "method": "POST",
      "path": "/api/v1/templates",
      "description": "Create notification template",
      "request_body": {
        "name": "order_confirmation",
        "channel": "email",
        "subject": "Order {{order_id}} Confirmed",
        "body": "Your order for ${{amount}} has been confirmed."
      },
      "responses": {
        "201": {"id": 1, "name": "order_confirmation"}
      }
    },
    {
      "method": "GET",
      "path": "/health",
      "description": "Health check",
      "responses": {
        "200": {
          "status": "healthy",
          "queues": {
            "email": 45,
            "push": 120,
            "sms": 10
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
                    Notification System - L5 Architecture
    ═══════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────┐
    │                        API CLIENTS                               │
    │             (Mobile App, Web App, Backend Services)              │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    NOTIFICATION SERVICE                          │
    │                      (Python/FastAPI)                            │
    │                                                                  │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
    │  │   API Handler   │  │ Template Engine │  │ Preference Mgr  │  │
    │  │                 │  │   (Jinja2)      │  │                 │  │
    │  │ • Validate req  │  │ • Render msgs   │  │ • Check prefs   │  │
    │  │ • Queue notifs  │  │ • Variable sub  │  │ • Filter chans  │  │
    │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      MESSAGE QUEUES (Redis)                      │
    │                                                                  │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
    │  │ Email Queue │  │ Push Queue  │  │ SMS Queue   │              │
    │  │   (LIST)    │  │   (LIST)    │  │   (LIST)    │              │
    │  └─────────────┘  └─────────────┘  └─────────────┘              │
    │                                                                  │
    │                    ┌─────────────┐                               │
    │                    │ Retry Queue │                               │
    │                    │   (ZSET)    │                               │
    │                    └─────────────┘                               │
    └────────────────────────────┬────────────────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Email Worker   │ │  Push Worker    │ │  SMS Worker     │
    │                 │ │                 │ │                 │
    │ • Dequeue msgs  │ │ • Dequeue msgs  │ │ • Dequeue msgs  │
    │ • Send via SMTP │ │ • Send via FCM/ │ │ • Send via      │
    │   / SendGrid    │ │   APNS          │ │   Twilio        │
    │ • Track status  │ │ • Track status  │ │ • Track status  │
    │ • Handle retry  │ │ • Handle retry  │ │ • Handle retry  │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │   SendGrid /    │ │   Firebase /    │ │     Twilio      │
    │   Mailgun       │ │   APNS          │ │                 │
    └─────────────────┘ └─────────────────┘ └─────────────────┘

                                 │
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      PostgreSQL                                  │
    │                                                                  │
    │  • Notification records                                          │
    │  • User preferences                                              │
    │  • Templates                                                     │
    │  • Delivery tracking                                             │
    └─────────────────────────────────────────────────────────────────┘
```

### Worker Implementation

```python
import json
import time
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import redis
from jinja2 import Template

class NotificationChannel(Enum):
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"

class NotificationStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"

@dataclass
class NotificationMessage:
    id: int
    user_id: int
    channel: NotificationChannel
    recipient: str
    subject: Optional[str]
    body: str
    retry_count: int = 0

class NotificationService:
    """
    L5 Notification Service implementation.

    Handles multi-channel notification delivery with:
    - Template rendering
    - User preferences
    - Queue-based async delivery
    - Basic retry logic
    """

    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min

    def __init__(
        self,
        redis_client: redis.Redis,
        db_connection,
        email_provider,
        push_provider,
        sms_provider
    ):
        self.redis = redis_client
        self.db = db_connection
        self.email_provider = email_provider
        self.push_provider = push_provider
        self.sms_provider = sms_provider

    def send_notification(
        self,
        user_id: int,
        notification_type: str,
        data: Dict,
        channels: list = None
    ) -> Dict:
        """
        Send notification to user across enabled channels.

        1. Get user preferences
        2. Filter to enabled channels
        3. Render templates
        4. Queue for delivery
        """
        # Get user
        user = self._get_user(user_id)
        if not user:
            return {"error": "User not found"}

        # Get preferences
        preferences = self._get_preferences(user_id, notification_type)

        # Determine channels
        enabled_channels = []
        if channels:
            # Use specified channels, but respect preferences
            enabled_channels = [c for c in channels if preferences.get(c, False)]
        else:
            # Use all enabled channels from preferences
            enabled_channels = [c for c, enabled in preferences.items() if enabled]

        if not enabled_channels:
            return {"error": "No enabled channels"}

        # Get templates and render
        notification_ids = []

        for channel in enabled_channels:
            template = self._get_template(notification_type, channel)
            if not template:
                continue

            rendered = self._render_template(template, data)

            # Create notification record
            notification_id = self._create_notification(
                user_id=user_id,
                channel=channel,
                template_id=template["id"],
                payload=rendered
            )

            # Queue for delivery
            self._queue_notification(
                notification_id=notification_id,
                user=user,
                channel=channel,
                rendered=rendered
            )

            notification_ids.append(notification_id)

        return {
            "notification_ids": notification_ids,
            "channels": enabled_channels,
            "status": "queued"
        }

    def _render_template(self, template: Dict, data: Dict) -> Dict:
        """Render template with data using Jinja2."""
        rendered = {}

        if template.get("subject"):
            subject_tmpl = Template(template["subject"])
            rendered["subject"] = subject_tmpl.render(**data)

        body_tmpl = Template(template["body"])
        rendered["body"] = body_tmpl.render(**data)

        return rendered

    def _queue_notification(
        self,
        notification_id: int,
        user: Dict,
        channel: str,
        rendered: Dict
    ):
        """Add notification to appropriate channel queue."""
        message = {
            "notification_id": notification_id,
            "user_id": user["id"],
            "channel": channel,
            "recipient": self._get_recipient(user, channel),
            "subject": rendered.get("subject"),
            "body": rendered["body"],
            "retry_count": 0
        }

        queue_name = f"notifications:{channel}"
        self.redis.rpush(queue_name, json.dumps(message))

        # Update status
        self._update_notification_status(notification_id, NotificationStatus.QUEUED)

    def _get_recipient(self, user: Dict, channel: str) -> str:
        """Get recipient address for channel."""
        if channel == "email":
            return user["email"]
        elif channel == "push":
            return user.get("device_token", "")
        elif channel == "sms":
            return user.get("phone", "")
        return ""


class NotificationWorker:
    """
    Worker that processes notification queue for a specific channel.
    """

    def __init__(
        self,
        channel: NotificationChannel,
        redis_client: redis.Redis,
        provider,
        db_connection
    ):
        self.channel = channel
        self.redis = redis_client
        self.provider = provider
        self.db = db_connection
        self.queue_name = f"notifications:{channel.value}"

    def run(self):
        """Main worker loop."""
        while True:
            # Block and wait for message
            result = self.redis.blpop(self.queue_name, timeout=30)

            if result:
                _, message_data = result
                message = json.loads(message_data)
                self._process_message(message)

            # Check retry queue
            self._process_retries()

    def _process_message(self, message: Dict):
        """Process a single notification message."""
        notification_id = message["notification_id"]

        try:
            # Send via provider
            result = self._send(message)

            if result["success"]:
                self._mark_sent(notification_id)
            else:
                self._handle_failure(message, result.get("error"))

        except Exception as e:
            self._handle_failure(message, str(e))

    def _send(self, message: Dict) -> Dict:
        """Send notification via provider."""
        if self.channel == NotificationChannel.EMAIL:
            return self.provider.send_email(
                to=message["recipient"],
                subject=message["subject"],
                body=message["body"]
            )
        elif self.channel == NotificationChannel.PUSH:
            return self.provider.send_push(
                device_token=message["recipient"],
                title=message["subject"],
                body=message["body"]
            )
        elif self.channel == NotificationChannel.SMS:
            return self.provider.send_sms(
                to=message["recipient"],
                body=message["body"]
            )

    def _handle_failure(self, message: Dict, error: str):
        """Handle delivery failure with retry logic."""
        notification_id = message["notification_id"]
        retry_count = message.get("retry_count", 0)

        if retry_count < NotificationService.MAX_RETRIES:
            # Schedule retry
            message["retry_count"] = retry_count + 1
            retry_time = time.time() + NotificationService.RETRY_DELAYS[retry_count]

            self.redis.zadd(
                "notifications:retry",
                {json.dumps(message): retry_time}
            )
        else:
            # Max retries exceeded - mark as failed
            self._mark_failed(notification_id, error)

    def _process_retries(self):
        """Process due retry messages."""
        now = time.time()

        # Get messages ready for retry
        messages = self.redis.zrangebyscore(
            "notifications:retry",
            "-inf",
            now,
            start=0,
            num=10
        )

        for message_data in messages:
            message = json.loads(message_data)

            # Only process if this is our channel
            if message["channel"] == self.channel.value:
                # Remove from retry queue
                self.redis.zrem("notifications:retry", message_data)

                # Re-queue for processing
                self.redis.rpush(self.queue_name, message_data)

    def _mark_sent(self, notification_id: int):
        """Update notification status to sent."""
        # Update database
        query = """
            UPDATE notifications
            SET status = 'sent', sent_at = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (notification_id,))

    def _mark_failed(self, notification_id: int, error: str):
        """Update notification status to failed."""
        query = """
            UPDATE notifications
            SET status = 'failed', failed_at = NOW(), error_message = %s
            WHERE id = %s
        """
        self.db.execute(query, (error, notification_id))
```

### Request Flow

**Send Notification:**
1. API receives notification request
2. Validate user exists and preferences
3. Get enabled channels for notification type
4. Render templates for each channel
5. Create notification records in PostgreSQL
6. Queue messages to Redis (per channel)
7. Return notification IDs to caller

**Worker Processing:**
1. Worker polls channel queue (BLPOP)
2. Deserialize message
3. Send via provider (SendGrid, FCM, Twilio)
4. On success: Update status to "sent"
5. On failure: Add to retry queue with delay
6. After max retries: Mark as "failed"

---

## Test Cases

### Functional Tests

| Test ID | Test Name | Description | Expected Result |
|---------|-----------|-------------|-----------------|
| F-01 | Send single notification | POST to /notifications | 201, notification queued |
| F-02 | Send to disabled channel | Channel disabled in prefs | Channel skipped |
| F-03 | Batch notification | POST to /notifications/batch | 202, batch queued |
| F-04 | Get notification status | GET /notifications/{id} | Status returned |
| F-05 | List user notifications | GET /users/{id}/notifications | Paginated list |
| F-06 | Update preferences | PUT /users/{id}/preferences | Preferences updated |
| F-07 | Template rendering | Template with variables | Variables substituted |
| F-08 | Invalid user | Send to non-existent user | 404 error |
| F-09 | Worker delivery | Message in queue | Delivered via provider |
| F-10 | Retry on failure | Provider fails | Message retried |
| F-11 | Max retry exceeded | 3 failures | Status = failed |
| F-12 | Quiet hours | Send during quiet hours | Notification delayed |
| F-13 | Email delivery | Send email | Email received |
| F-14 | Push delivery | Send push | Push received |
| F-15 | SMS delivery | Send SMS | SMS received |

### Performance Tests

| Test ID | Test Name | Description | Target |
|---------|-----------|-------------|--------|
| P-01 | Queue latency | Time to queue notification | < 50ms p99 |
| P-02 | Worker throughput | Notifications per second | > 1,000/s per worker |
| P-03 | End-to-end latency | Request to delivery | < 5s p99 |
| P-04 | Batch processing | 10,000 user batch | < 30s complete |
| P-05 | Database queries | Queries per notification | < 5 |
| P-06 | Queue depth | Sustained load | Queue depth stable |
| P-07 | Memory usage | Per worker | < 256MB |
| P-08 | Concurrent sends | 1000 concurrent requests | No failures |

### Chaos Tests

| Test ID | Test Name | Description | Expected Behavior |
|---------|-----------|-------------|-------------------|
| C-01 | Redis down | Kill Redis | API returns error, data safe |
| C-02 | Worker crash | Kill worker | Messages remain in queue |
| C-03 | Provider timeout | SendGrid slow | Retry with backoff |
| C-04 | Database down | PostgreSQL unavailable | Queued messages wait |
| C-05 | High load | 10x normal traffic | Graceful degradation |
| C-06 | Provider rate limit | Rate limited by provider | Automatic backoff |

---

## Capacity Estimates

- **Daily notifications**: 10M
- **Peak rate**: 500 notifications/second
- **Channels**: Email (60%), Push (30%), SMS (10%)
- **Queue size**: ~50,000 messages max
- **Database size**: ~50GB (90-day retention)
- **Latency target**: < 5s end-to-end (email), < 1s (push)
