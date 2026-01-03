# Notification System Design

## Problem Overview

Design a notification service that can send notifications across multiple channels (push, email, SMS, in-app) with high throughput and reliable delivery.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution Architecture

### High-Level Design

```
                                    ┌─────────────────────┐
                                    │   API Gateway       │
                                    └──────────┬──────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                              ▼                ▼                ▼
                    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
                    │ Notification    │ │ Template    │ │ Preference      │
                    │ Service         │ │ Service     │ │ Service         │
                    └────────┬────────┘ └─────────────┘ └─────────────────┘
                             │
                             ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              Message Queue (Kafka)                  │
                    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
                    │  │ Push    │ │ Email   │ │ SMS     │ │ In-App  │   │
                    │  │ Topic   │ │ Topic   │ │ Topic   │ │ Topic   │   │
                    │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
                    └───────┼───────────┼───────────┼───────────┼────────┘
                            │           │           │           │
          ┌─────────────────┼───────────┼───────────┼───────────┼─────────────────┐
          │                 ▼           ▼           ▼           ▼                 │
          │  ┌─────────────────┐ ┌─────────────┐ ┌─────────┐ ┌─────────────────┐ │
          │  │ Push Provider   │ │ Email       │ │ SMS     │ │ WebSocket       │ │
          │  │ (FCM/APNs)      │ │ (SendGrid)  │ │ (Twilio)│ │ Handler         │ │
          │  └─────────────────┘ └─────────────┘ └─────────┘ └─────────────────┘ │
          │                                                                       │
          │                     Channel Adapters                                  │
          └───────────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Notification Service

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
import uuid

class NotificationChannel(Enum):
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"

class NotificationPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Notification:
    id: str
    user_id: str
    channels: List[NotificationChannel]
    template_id: str
    template_data: Dict
    priority: NotificationPriority
    scheduled_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None

class NotificationService:
    def __init__(
        self,
        kafka_producer,
        template_service,
        preference_service,
        rate_limiter
    ):
        self.kafka = kafka_producer
        self.templates = template_service
        self.preferences = preference_service
        self.rate_limiter = rate_limiter

    async def send(self, notification: Notification) -> Dict:
        """
        Send notification through requested channels.
        Respects user preferences and applies rate limiting.
        """
        # Idempotency check
        if notification.idempotency_key:
            if await self._is_duplicate(notification.idempotency_key):
                return {"status": "duplicate", "id": notification.id}

        # Get user preferences
        prefs = await self.preferences.get(notification.user_id)

        # Filter channels based on preferences
        allowed_channels = [
            ch for ch in notification.channels
            if prefs.is_channel_enabled(ch)
        ]

        if not allowed_channels:
            return {"status": "suppressed", "reason": "user_preferences"}

        # Rate limiting check
        if not await self.rate_limiter.allow(
            notification.user_id,
            len(allowed_channels)
        ):
            return {"status": "rate_limited"}

        # Render template
        content = await self.templates.render(
            notification.template_id,
            notification.template_data
        )

        # Publish to channel-specific topics
        results = {}
        for channel in allowed_channels:
            message = {
                "notification_id": notification.id,
                "user_id": notification.user_id,
                "channel": channel.value,
                "content": content[channel.value],
                "priority": notification.priority.value,
                "scheduled_at": notification.scheduled_at.isoformat()
                    if notification.scheduled_at else None
            }

            topic = f"notifications.{channel.value}"
            await self.kafka.send(topic, message)
            results[channel.value] = "queued"

        # Store for tracking
        await self._store_notification(notification, results)

        return {"status": "accepted", "id": notification.id, "channels": results}
```

#### 2. Channel Adapters

```python
# Push Notification Adapter (FCM)
class PushAdapter:
    def __init__(self, fcm_client):
        self.fcm = fcm_client

    async def send(self, user_id: str, content: dict) -> dict:
        # Get user's device tokens
        tokens = await self.get_device_tokens(user_id)

        if not tokens:
            return {"status": "no_devices"}

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title=content["title"],
                body=content["body"]
            ),
            data=content.get("data", {}),
            android=messaging.AndroidConfig(
                priority="high" if content.get("priority") == "urgent" else "normal"
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=content.get("badge", 1))
                )
            )
        )

        response = self.fcm.send_multicast(message)
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
            "failed_tokens": [
                tokens[i] for i, r in enumerate(response.responses)
                if not r.success
            ]
        }

# Email Adapter (SendGrid)
class EmailAdapter:
    def __init__(self, sendgrid_client):
        self.sg = sendgrid_client

    async def send(self, user_id: str, content: dict) -> dict:
        email = await self.get_user_email(user_id)

        message = Mail(
            from_email=Email(content.get("from", "noreply@example.com")),
            to_emails=To(email),
            subject=content["subject"],
            html_content=content["html_body"],
            plain_text_content=content.get("text_body")
        )

        # Add tracking
        message.tracking_settings = TrackingSettings(
            click_tracking=ClickTracking(True),
            open_tracking=OpenTracking(True)
        )

        response = await self.sg.send(message)
        return {
            "status_code": response.status_code,
            "message_id": response.headers.get("X-Message-Id")
        }

# SMS Adapter (Twilio)
class SMSAdapter:
    def __init__(self, twilio_client):
        self.twilio = twilio_client

    async def send(self, user_id: str, content: dict) -> dict:
        phone = await self.get_user_phone(user_id)

        if not phone:
            return {"status": "no_phone"}

        message = await self.twilio.messages.create(
            body=content["body"],
            from_=content.get("from", "+15551234567"),
            to=phone,
            status_callback=f"{WEBHOOK_URL}/sms/status"
        )

        return {
            "sid": message.sid,
            "status": message.status
        }
```

#### 3. Database Schema

```sql
-- Notification templates
CREATE TABLE notification_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    channels JSONB NOT NULL,  -- {push: {...}, email: {...}, sms: {...}}
    variables JSONB,  -- Schema for template variables
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User notification preferences
CREATE TABLE notification_preferences (
    user_id BIGINT PRIMARY KEY,
    email_enabled BOOLEAN DEFAULT TRUE,
    push_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    category_preferences JSONB,  -- Per-category settings
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Notification history (partitioned)
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL,
    template_id INTEGER REFERENCES notification_templates(id),
    channels TEXT[] NOT NULL,
    priority INTEGER DEFAULT 2,
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Delivery status per channel
CREATE TABLE notification_deliveries (
    id SERIAL,
    notification_id UUID REFERENCES notifications(id),
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255),
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Device tokens for push
CREATE TABLE device_tokens (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    platform VARCHAR(20) NOT NULL,  -- ios, android, web
    token TEXT NOT NULL UNIQUE,
    app_version VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    last_active_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### API Design

```yaml
openapi: 3.0.0
paths:
  /api/v1/notifications:
    post:
      summary: Send notification
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [user_id, template_id]
              properties:
                user_id: { type: string }
                channels: { type: array, items: { enum: [push, email, sms, in_app] } }
                template_id: { type: string }
                template_data: { type: object }
                priority: { enum: [low, normal, high, urgent] }
                scheduled_at: { type: string, format: date-time }
                idempotency_key: { type: string }
      responses:
        202:
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: { type: string }
                  status: { type: string }

  /api/v1/notifications/{id}:
    get:
      summary: Get notification status
      responses:
        200:
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: { type: string }
                  status: { type: string }
                  deliveries: { type: array }

  /api/v1/preferences/{user_id}:
    get:
      summary: Get user preferences
    put:
      summary: Update user preferences
```

---

## Platform Deployment

### Deployment Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          GCP Deployment                            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                     Cloud Run Services                        │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ │ │
│  │  │Notification│ │ Template   │ │ Preference │ │ Analytics  │ │ │
│  │  │  Service   │ │  Service   │ │  Service   │ │  Service   │ │ │
│  │  └─────┬──────┘ └────────────┘ └────────────┘ └────────────┘ │ │
│  └────────┼─────────────────────────────────────────────────────┘ │
│           │                                                        │
│  ┌────────▼─────────────────────────────────────────────────────┐ │
│  │                    Pub/Sub Topics                             │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐  │ │
│  │  │  Push  │ │ Email  │ │  SMS   │ │ In-App │ │   DLQ      │  │ │
│  │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └────────────┘  │ │
│  └──────┼──────────┼──────────┼──────────┼──────────────────────┘ │
│         │          │          │          │                        │
│  ┌──────▼──────────▼──────────▼──────────▼──────────────────────┐ │
│  │                    Channel Workers                            │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                 │ │
│  │  │  FCM   │ │SendGrid│ │ Twilio │ │WebSocket│                │ │
│  │  │ Worker │ │ Worker │ │ Worker │ │ Handler │                │ │
│  │  └────────┘ └────────┘ └────────┘ └────────┘                 │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## Realistic Testing

### 1. Functional Tests

```python
class TestNotificationSystem:
    async def test_send_push_notification(self, client):
        """Test sending a push notification."""
        response = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push"],
            "template_id": "welcome",
            "template_data": {"name": "John"}
        })

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

        # Wait and check delivery
        await asyncio.sleep(5)
        status = await client.get(f"/api/v1/notifications/{data['id']}")
        assert status.json()["deliveries"][0]["status"] == "delivered"

    async def test_multi_channel_notification(self, client):
        """Test sending to multiple channels."""
        response = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push", "email", "in_app"],
            "template_id": "order_confirmation",
            "template_data": {"order_id": "12345"}
        })

        assert response.status_code == 202
        assert len(response.json()["channels"]) == 3

    async def test_preference_respect(self, client):
        """Test that user preferences are respected."""
        # Disable email
        await client.put("/api/v1/preferences/user123", json={
            "email_enabled": False
        })

        response = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["email", "push"],
            "template_id": "test"
        })

        # Should only queue push
        assert "email" not in response.json()["channels"]
        assert "push" in response.json()["channels"]

    async def test_scheduled_notification(self, client):
        """Test scheduled notifications."""
        scheduled_time = datetime.utcnow() + timedelta(minutes=5)

        response = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push"],
            "template_id": "reminder",
            "scheduled_at": scheduled_time.isoformat()
        })

        assert response.status_code == 202

        # Check it's not delivered yet
        status = await client.get(f"/api/v1/notifications/{response.json()['id']}")
        assert status.json()["status"] == "scheduled"

    async def test_idempotency(self, client):
        """Test idempotency key prevents duplicates."""
        idem_key = str(uuid.uuid4())

        # First request
        r1 = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push"],
            "template_id": "test",
            "idempotency_key": idem_key
        })

        # Second request with same key
        r2 = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push"],
            "template_id": "test",
            "idempotency_key": idem_key
        })

        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["status"] == "duplicate"
```

### 2. Load Testing

```python
from locust import HttpUser, task, between
import random

class NotificationUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(10)
    def send_push(self):
        self.client.post("/api/v1/notifications", json={
            "user_id": f"user{random.randint(1, 10000)}",
            "channels": ["push"],
            "template_id": "activity",
            "template_data": {"action": "liked your post"}
        })

    @task(5)
    def send_email(self):
        self.client.post("/api/v1/notifications", json={
            "user_id": f"user{random.randint(1, 10000)}",
            "channels": ["email"],
            "template_id": "weekly_digest",
            "template_data": {"items": [1, 2, 3]}
        })

    @task(2)
    def send_multi_channel(self):
        self.client.post("/api/v1/notifications", json={
            "user_id": f"user{random.randint(1, 10000)}",
            "channels": ["push", "email", "in_app"],
            "template_id": "important_alert",
            "priority": "high"
        })
```

### 3. Integration Tests with Real Providers

```python
class TestProviderIntegration:
    """Tests that actually send to real providers (staging)."""

    @pytest.mark.integration
    async def test_fcm_delivery(self, client, test_device_token):
        """Test actual FCM delivery."""
        response = await client.post("/api/v1/notifications", json={
            "user_id": "test_user_fcm",
            "channels": ["push"],
            "template_id": "test",
            "template_data": {"message": "Integration test"}
        })

        # Wait for delivery webhook
        delivery = await wait_for_webhook(
            notification_id=response.json()["id"],
            timeout=30
        )
        assert delivery["status"] == "delivered"

    @pytest.mark.integration
    async def test_sendgrid_delivery(self, client):
        """Test actual SendGrid delivery."""
        response = await client.post("/api/v1/notifications", json={
            "user_id": "test_user_email",
            "channels": ["email"],
            "template_id": "test_email",
            "template_data": {"subject": "Integration Test"}
        })

        # Check SendGrid webhook for delivery event
        delivery = await wait_for_sendgrid_event(
            notification_id=response.json()["id"],
            event_type="delivered",
            timeout=60
        )
        assert delivery is not None
```

### 4. Chaos Tests

```python
class NotificationChaosTests:
    async def test_provider_failure(self):
        """Test graceful handling of provider failures."""
        # Inject FCM failure
        await platform_api.inject_failure(
            service="fcm",
            failure_rate=1.0,
            duration_seconds=60
        )

        # Send notification
        response = await client.post("/api/v1/notifications", json={
            "user_id": "user123",
            "channels": ["push"],
            "template_id": "test"
        })

        # Should be queued for retry
        await asyncio.sleep(5)
        status = await client.get(f"/api/v1/notifications/{response.json()['id']}")
        assert status.json()["deliveries"][0]["status"] in ["pending", "retrying"]

    async def test_queue_backpressure(self):
        """Test handling of queue backpressure."""
        # Send burst of notifications
        tasks = [
            client.post("/api/v1/notifications", json={
                "user_id": f"user{i}",
                "channels": ["push"],
                "template_id": "test"
            })
            for i in range(10000)
        ]

        responses = await asyncio.gather(*tasks)

        # All should be accepted
        accepted = sum(1 for r in responses if r.status_code == 202)
        assert accepted == len(tasks)
```

---

## Success Criteria

| Metric | Target | Verification |
|--------|--------|--------------|
| API Latency (p99) | < 100ms | Performance test |
| Throughput | > 100K/min | Load test |
| Delivery Rate | > 99.5% | Integration test |
| Retry Success | > 95% | Chaos test |
| FCM Latency | < 1s | Integration test |
| Email Latency | < 30s | Integration test |
