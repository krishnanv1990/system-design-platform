# Chat Application Design (WhatsApp-like)

## Problem Overview

Design a real-time messaging application supporting 500M DAU, 100B messages per day, with sub-100ms delivery latency.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Apps                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │   iOS    │  │ Android  │  │   Web    │  │ Desktop  │                        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                        │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │ WebSocket
        ┌────────────────────▼────────────────────┐
        │          WebSocket Gateway Cluster       │
        │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
        │  │  GW 1   │ │  GW 2   │ │  GW N   │    │
        │  └────┬────┘ └────┬────┘ └────┬────┘    │
        └───────┼───────────┼───────────┼─────────┘
                │           │           │
        ┌───────▼───────────▼───────────▼─────────┐
        │              Message Router              │
        │     (Routes based on recipient)          │
        └───────────────────┬─────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Message    │   │   Presence   │   │    Group     │
│   Service    │   │   Service    │   │   Service    │
└──────┬───────┘   └──────────────┘   └──────────────┘
       │
       ├──────────────────────┬──────────────────────┐
       ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Message DB  │      │  User Cache  │      │  Push Queue  │
│ (Cassandra)  │      │   (Redis)    │      │  (Kafka)     │
└──────────────┘      └──────────────┘      └──────────────┘
```

### Core Components

#### 1. WebSocket Connection Management

```python
import asyncio
from typing import Dict, Set
import websockets

class ConnectionManager:
    """Manages WebSocket connections for all users."""

    def __init__(self):
        self.connections: Dict[str, Set[websockets.WebSocketServerProtocol]] = {}
        self.user_gateway: Dict[str, str] = {}  # user_id -> gateway_id
        self.redis = Redis()

    async def connect(self, user_id: str, websocket):
        """Handle new connection."""
        if user_id not in self.connections:
            self.connections[user_id] = set()

        self.connections[user_id].add(websocket)

        # Register in distributed registry
        await self.redis.hset(
            "user_connections",
            user_id,
            f"{GATEWAY_ID}:{time.time()}"
        )

        # Update presence
        await self.presence_service.set_online(user_id)

    async def disconnect(self, user_id: str, websocket):
        """Handle disconnection."""
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)

            if not self.connections[user_id]:
                del self.connections[user_id]
                await self.redis.hdel("user_connections", user_id)
                await self.presence_service.set_offline(user_id)

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to user's connected devices."""
        # Check local connections
        if user_id in self.connections:
            for ws in self.connections[user_id]:
                try:
                    await ws.send(json.dumps(message))
                except:
                    await self.disconnect(user_id, ws)
            return True

        # Check if user is on another gateway
        gateway = await self.redis.hget("user_connections", user_id)
        if gateway:
            gateway_id = gateway.split(":")[0]
            await self.route_to_gateway(gateway_id, user_id, message)
            return True

        return False  # User offline


class MessageRouter:
    """Routes messages to correct gateway or offline queue."""

    async def route(self, message: Message):
        """Route message to recipient."""
        recipient_id = message.recipient_id

        # Try to deliver online
        delivered = await self.connection_manager.send_to_user(
            recipient_id,
            message.to_dict()
        )

        if delivered:
            # Update delivery status
            await self.update_status(message.id, "delivered")
        else:
            # Queue for offline delivery
            await self.offline_queue.push(recipient_id, message)
            # Queue push notification
            await self.push_queue.push(recipient_id, message)
```

#### 2. Message Service

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"

class MessageStatus(Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

@dataclass
class Message:
    id: str
    conversation_id: str
    sender_id: str
    recipient_id: str
    message_type: MessageType
    content: str  # Encrypted
    media_url: Optional[str]
    status: MessageStatus
    timestamp: datetime
    reply_to: Optional[str]

class MessageService:
    def __init__(self, db, cache, router):
        self.db = db
        self.cache = cache
        self.router = router

    async def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        media_url: Optional[str] = None
    ) -> Message:
        """Send a message to a user."""
        # Get or create conversation
        conversation_id = await self.get_conversation_id(
            sender_id, recipient_id
        )

        # Create message
        message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            media_url=media_url,
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow(),
            reply_to=None
        )

        # Store message
        await self.db.insert("messages", message)

        # Route to recipient
        await self.router.route(message)

        return message

    async def send_group_message(
        self,
        sender_id: str,
        group_id: str,
        content: str
    ) -> List[Message]:
        """Send message to a group."""
        # Get group members
        members = await self.get_group_members(group_id)

        messages = []
        for member_id in members:
            if member_id != sender_id:
                msg = await self.send_message(
                    sender_id, member_id, content
                )
                messages.append(msg)

        return messages

    async def mark_as_read(
        self,
        user_id: str,
        message_ids: List[str]
    ):
        """Mark messages as read and send receipts."""
        await self.db.update_many(
            "messages",
            {"id": {"$in": message_ids}},
            {"status": MessageStatus.READ}
        )

        # Send read receipts to senders
        messages = await self.db.find_many(
            "messages",
            {"id": {"$in": message_ids}}
        )

        for msg in messages:
            await self.router.send_to_user(msg.sender_id, {
                "type": "read_receipt",
                "message_id": msg.id,
                "read_by": user_id,
                "read_at": datetime.utcnow().isoformat()
            })
```

#### 3. Presence Service

```python
class PresenceService:
    """Tracks user online/offline status."""

    def __init__(self, redis):
        self.redis = redis
        self.PRESENCE_TTL = 60  # Seconds

    async def set_online(self, user_id: str):
        """Mark user as online."""
        await self.redis.setex(
            f"presence:{user_id}",
            self.PRESENCE_TTL,
            "online"
        )

        # Notify contacts
        await self.notify_contacts(user_id, "online")

    async def set_offline(self, user_id: str):
        """Mark user as offline."""
        # Set last seen time
        await self.redis.set(
            f"last_seen:{user_id}",
            datetime.utcnow().isoformat()
        )
        await self.redis.delete(f"presence:{user_id}")

        await self.notify_contacts(user_id, "offline")

    async def heartbeat(self, user_id: str):
        """Extend presence TTL."""
        await self.redis.expire(
            f"presence:{user_id}",
            self.PRESENCE_TTL
        )

    async def get_status(self, user_id: str) -> dict:
        """Get user's online status."""
        is_online = await self.redis.exists(f"presence:{user_id}")

        if is_online:
            return {"status": "online"}

        last_seen = await self.redis.get(f"last_seen:{user_id}")
        return {
            "status": "offline",
            "last_seen": last_seen
        }

    async def get_bulk_status(self, user_ids: List[str]) -> Dict[str, dict]:
        """Get status for multiple users efficiently."""
        pipeline = self.redis.pipeline()
        for uid in user_ids:
            pipeline.exists(f"presence:{uid}")

        results = await pipeline.execute()
        return {
            uid: {"status": "online" if online else "offline"}
            for uid, online in zip(user_ids, results)
        }
```

#### 4. End-to-End Encryption

```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class E2EEncryption:
    """Signal Protocol-based E2E encryption."""

    async def generate_keys(self, user_id: str) -> dict:
        """Generate identity keys for a user."""
        identity_key = x25519.X25519PrivateKey.generate()
        signed_prekey = x25519.X25519PrivateKey.generate()

        # Store private keys securely (on client)
        # Upload public keys to server
        await self.key_service.store_public_keys(user_id, {
            "identity_key": identity_key.public_key().public_bytes_raw(),
            "signed_prekey": signed_prekey.public_key().public_bytes_raw()
        })

        return {
            "identity_key": identity_key,
            "signed_prekey": signed_prekey
        }

    async def create_session(
        self,
        sender_id: str,
        recipient_id: str
    ) -> bytes:
        """Create encrypted session using X3DH."""
        # Fetch recipient's keys
        recipient_keys = await self.key_service.get_public_keys(recipient_id)

        # Perform X3DH key agreement
        shared_secret = self.x3dh_key_agreement(
            sender_keys=await self.get_my_keys(sender_id),
            recipient_keys=recipient_keys
        )

        return shared_secret

    def encrypt_message(
        self,
        plaintext: str,
        session_key: bytes
    ) -> bytes:
        """Encrypt message using AES-GCM."""
        nonce = os.urandom(12)
        aesgcm = AESGCM(session_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ciphertext

    def decrypt_message(
        self,
        ciphertext: bytes,
        session_key: bytes
    ) -> str:
        """Decrypt message using AES-GCM."""
        nonce = ciphertext[:12]
        encrypted = ciphertext[12:]
        aesgcm = AESGCM(session_key)
        plaintext = aesgcm.decrypt(nonce, encrypted, None)
        return plaintext.decode()
```

### Database Schema

```sql
-- Using Cassandra for message storage (high write throughput)

-- Messages by conversation (for fetching chat history)
CREATE TABLE messages_by_conversation (
    conversation_id UUID,
    message_id TIMEUUID,
    sender_id BIGINT,
    recipient_id BIGINT,
    message_type TEXT,
    content BLOB,  -- Encrypted
    media_url TEXT,
    status TEXT,
    reply_to UUID,
    PRIMARY KEY (conversation_id, message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- Messages by user (for sync)
CREATE TABLE messages_by_user (
    user_id BIGINT,
    bucket DATE,  -- Daily partitioning
    message_id TIMEUUID,
    conversation_id UUID,
    direction TEXT,  -- 'sent' or 'received'
    status TEXT,
    PRIMARY KEY ((user_id, bucket), message_id)
) WITH CLUSTERING ORDER BY (message_id DESC);

-- Conversations
CREATE TABLE conversations (
    user_id BIGINT,
    conversation_id UUID,
    other_user_id BIGINT,
    last_message_id TIMEUUID,
    unread_count INT,
    updated_at TIMESTAMP,
    PRIMARY KEY (user_id, conversation_id)
);

-- Groups
CREATE TABLE groups (
    group_id UUID PRIMARY KEY,
    name TEXT,
    description TEXT,
    avatar_url TEXT,
    created_by BIGINT,
    created_at TIMESTAMP
);

CREATE TABLE group_members (
    group_id UUID,
    user_id BIGINT,
    role TEXT,  -- admin, member
    joined_at TIMESTAMP,
    PRIMARY KEY (group_id, user_id)
);
```

---

## Realistic Testing

### 1. Functional Tests

```python
class TestChatApplication:
    async def test_send_and_receive_message(self, ws_client1, ws_client2):
        """Test real-time message delivery."""
        # User1 sends message to User2
        await ws_client1.send(json.dumps({
            "type": "send_message",
            "recipient_id": "user2",
            "content": "Hello!"
        }))

        # User2 should receive immediately
        message = await asyncio.wait_for(
            ws_client2.recv(),
            timeout=1.0
        )
        data = json.loads(message)

        assert data["type"] == "new_message"
        assert data["content"] == "Hello!"
        assert data["sender_id"] == "user1"

    async def test_delivery_receipts(self, ws_client1, ws_client2):
        """Test message delivery confirmation."""
        await ws_client1.send(json.dumps({
            "type": "send_message",
            "recipient_id": "user2",
            "content": "Test"
        }))

        # Wait for message on client2
        msg = await ws_client2.recv()
        msg_data = json.loads(msg)

        # Client1 should receive delivery receipt
        receipt = await ws_client1.recv()
        receipt_data = json.loads(receipt)

        assert receipt_data["type"] == "delivery_receipt"
        assert receipt_data["message_id"] == msg_data["message_id"]

    async def test_offline_message_delivery(self, client):
        """Test message delivery to offline user."""
        # User2 is offline
        await client.post("/api/v1/messages", json={
            "recipient_id": "user2",
            "content": "While you were away"
        })

        # User2 comes online
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({
                "type": "authenticate",
                "user_id": "user2"
            }))

            # Should receive pending messages
            msg = await ws.recv()
            data = json.loads(msg)
            assert data["content"] == "While you were away"

    async def test_group_messaging(self, clients):
        """Test group message broadcast."""
        # Create group
        group = await clients[0].post("/api/v1/groups", json={
            "name": "Test Group",
            "members": ["user1", "user2", "user3"]
        })
        group_id = group.json()["id"]

        # Send to group
        await clients[0].ws.send(json.dumps({
            "type": "send_group_message",
            "group_id": group_id,
            "content": "Hello group!"
        }))

        # All members should receive
        for i in range(1, 3):
            msg = await clients[i].ws.recv()
            assert json.loads(msg)["content"] == "Hello group!"

    async def test_presence_updates(self, ws_client1, ws_client2):
        """Test online status updates."""
        # Subscribe to user2's presence
        await ws_client1.send(json.dumps({
            "type": "subscribe_presence",
            "user_ids": ["user2"]
        }))

        # User2 goes offline
        await ws_client2.close()

        # Client1 should receive presence update
        update = await ws_client1.recv()
        data = json.loads(update)

        assert data["type"] == "presence_update"
        assert data["user_id"] == "user2"
        assert data["status"] == "offline"
```

### 2. Load Testing

```python
from locust import User, task, between
import websocket

class ChatUser(User):
    wait_time = between(1, 5)

    def on_start(self):
        self.user_id = f"user_{random.randint(1, 100000)}"
        self.ws = websocket.create_connection(WS_URL)
        self.ws.send(json.dumps({
            "type": "authenticate",
            "user_id": self.user_id
        }))

    @task(10)
    def send_message(self):
        recipient = f"user_{random.randint(1, 100000)}"
        self.ws.send(json.dumps({
            "type": "send_message",
            "recipient_id": recipient,
            "content": "Load test message"
        }))

    @task(5)
    def check_presence(self):
        targets = [f"user_{random.randint(1, 100000)}" for _ in range(10)]
        self.ws.send(json.dumps({
            "type": "get_presence",
            "user_ids": targets
        }))

    @task(1)
    def send_group_message(self):
        self.ws.send(json.dumps({
            "type": "send_group_message",
            "group_id": random.choice(GROUP_IDS),
            "content": "Group message"
        }))
```

### 3. Chaos Tests

```python
class ChatChaosTests:
    async def test_gateway_failover(self):
        """Test message delivery during gateway failure."""
        # Connect users to different gateways
        ws1 = await connect_to_gateway("gateway-1", "user1")
        ws2 = await connect_to_gateway("gateway-2", "user2")

        # Kill gateway-1
        await platform_api.kill_pod("chat-gateway-1")

        # User1 should reconnect
        await asyncio.sleep(5)

        # Message should still be delivered
        await ws2.send(json.dumps({
            "type": "send_message",
            "recipient_id": "user1",
            "content": "After failover"
        }))

        # Should eventually be delivered
        msg = await asyncio.wait_for(ws1.recv(), timeout=30)
        assert json.loads(msg)["content"] == "After failover"

    async def test_message_ordering(self):
        """Test message ordering under load."""
        messages_sent = []
        messages_received = []

        async def sender():
            for i in range(1000):
                await ws1.send(json.dumps({
                    "type": "send_message",
                    "recipient_id": "user2",
                    "content": f"msg_{i}"
                }))
                messages_sent.append(i)

        async def receiver():
            while len(messages_received) < 1000:
                msg = await ws2.recv()
                data = json.loads(msg)
                idx = int(data["content"].split("_")[1])
                messages_received.append(idx)

        await asyncio.gather(sender(), receiver())

        # Verify ordering preserved
        assert messages_received == sorted(messages_received)
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Message Latency (p50) | < 50ms |
| Message Latency (p99) | < 200ms |
| Delivery Rate | > 99.99% |
| Connection Stability | < 1% drops/hour |
| Group Fanout | < 100ms for 1000 members |
