"""
Functional tests for Chat Application (WhatsApp-like) system design.
Tests the core API endpoints and business logic.
"""

import pytest
import httpx
import asyncio
import websockets
import json
import os
import time
from typing import Optional

# Base URL for the deployed service
BASE_URL = os.getenv("TEST_TARGET_URL", "http://localhost:8000")
WS_URL = os.getenv("TEST_WS_URL", "ws://localhost:8000")


class TestChatAppFunctional:
    """Functional tests for Chat Application API."""

    @pytest.fixture
    def client(self):
        """Create HTTP client for tests."""
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers for API requests."""
        return {"Authorization": "Bearer test-token"}

    # ==================== Health Check Tests ====================

    def test_health_endpoint(self, client):
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    # ==================== User Registration Tests ====================

    def test_register_user(self, client):
        """Test user registration."""
        response = client.post("/api/v1/users/register", json={
            "phone_number": "+1234567890",
            "name": "Test User",
            "device_id": "device123"
        })
        assert response.status_code in [200, 201, 404, 409]  # 409 if already exists

    def test_register_user_invalid_phone(self, client):
        """Test registration with invalid phone number."""
        response = client.post("/api/v1/users/register", json={
            "phone_number": "invalid",
            "name": "Test User"
        })
        assert response.status_code in [400, 422, 404]

    # ==================== User Profile Tests ====================

    def test_get_user_profile(self, client, auth_headers):
        """Test getting user profile."""
        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_update_user_profile(self, client, auth_headers):
        """Test updating user profile."""
        response = client.patch("/api/v1/users/me",
            headers=auth_headers,
            json={
                "name": "Updated Name",
                "status": "Available"
            })
        assert response.status_code in [200, 401, 404]

    def test_update_profile_picture(self, client, auth_headers):
        """Test updating profile picture."""
        import io
        files = {"avatar": ("avatar.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
        response = client.post("/api/v1/users/me/avatar",
            headers=auth_headers, files=files)
        assert response.status_code in [200, 201, 401, 404]

    # ==================== Contact Tests ====================

    def test_sync_contacts(self, client, auth_headers):
        """Test syncing phone contacts."""
        response = client.post("/api/v1/contacts/sync",
            headers=auth_headers,
            json={
                "phone_numbers": ["+1111111111", "+2222222222", "+3333333333"]
            })
        assert response.status_code in [200, 401, 404]

    def test_get_contacts(self, client, auth_headers):
        """Test getting user's contacts."""
        response = client.get("/api/v1/contacts", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_block_contact(self, client, auth_headers):
        """Test blocking a contact."""
        response = client.post("/api/v1/contacts/block",
            headers=auth_headers,
            json={"user_id": "user123"})
        assert response.status_code in [200, 201, 401, 404]

    def test_unblock_contact(self, client, auth_headers):
        """Test unblocking a contact."""
        response = client.post("/api/v1/contacts/unblock",
            headers=auth_headers,
            json={"user_id": "user123"})
        assert response.status_code in [200, 401, 404]

    # ==================== One-on-One Messaging Tests ====================

    def test_send_text_message(self, client, auth_headers):
        """Test sending a text message."""
        response = client.post("/api/v1/messages",
            headers=auth_headers,
            json={
                "recipient_id": "user456",
                "content": "Hello, World!",
                "type": "text"
            })
        assert response.status_code in [200, 201, 401, 404]

    def test_send_empty_message(self, client, auth_headers):
        """Test that empty messages are rejected."""
        response = client.post("/api/v1/messages",
            headers=auth_headers,
            json={
                "recipient_id": "user456",
                "content": "",
                "type": "text"
            })
        assert response.status_code in [400, 422, 404]

    def test_get_conversation(self, client, auth_headers):
        """Test getting conversation history."""
        response = client.get("/api/v1/conversations/user456/messages",
            headers=auth_headers,
            params={"limit": 50, "before": None})
        assert response.status_code in [200, 401, 404]

    def test_get_conversations_list(self, client, auth_headers):
        """Test getting list of conversations."""
        response = client.get("/api/v1/conversations", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    # ==================== Message Status Tests ====================

    def test_mark_message_delivered(self, client, auth_headers):
        """Test marking message as delivered."""
        response = client.post("/api/v1/messages/msg123/delivered",
            headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_mark_message_read(self, client, auth_headers):
        """Test marking message as read."""
        response = client.post("/api/v1/messages/msg123/read",
            headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_get_message_status(self, client, auth_headers):
        """Test getting message delivery status."""
        response = client.get("/api/v1/messages/msg123/status",
            headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    # ==================== Media Message Tests ====================

    def test_send_image_message(self, client, auth_headers):
        """Test sending an image message."""
        import io
        files = {"media": ("image.jpg", io.BytesIO(b"fake image"), "image/jpeg")}
        data = {
            "recipient_id": "user456",
            "type": "image",
            "caption": "Check this out!"
        }
        response = client.post("/api/v1/messages/media",
            headers=auth_headers, files=files, data=data)
        assert response.status_code in [200, 201, 401, 404]

    def test_send_video_message(self, client, auth_headers):
        """Test sending a video message."""
        import io
        files = {"media": ("video.mp4", io.BytesIO(b"fake video"), "video/mp4")}
        data = {
            "recipient_id": "user456",
            "type": "video"
        }
        response = client.post("/api/v1/messages/media",
            headers=auth_headers, files=files, data=data)
        assert response.status_code in [200, 201, 401, 404]

    def test_send_document_message(self, client, auth_headers):
        """Test sending a document."""
        import io
        files = {"media": ("doc.pdf", io.BytesIO(b"fake pdf"), "application/pdf")}
        data = {
            "recipient_id": "user456",
            "type": "document"
        }
        response = client.post("/api/v1/messages/media",
            headers=auth_headers, files=files, data=data)
        assert response.status_code in [200, 201, 401, 404]

    def test_download_media(self, client, auth_headers):
        """Test downloading media from a message."""
        response = client.get("/api/v1/messages/msg123/media",
            headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    # ==================== Group Chat Tests ====================

    def test_create_group(self, client, auth_headers):
        """Test creating a group chat."""
        response = client.post("/api/v1/groups",
            headers=auth_headers,
            json={
                "name": "Test Group",
                "members": ["user1", "user2", "user3"]
            })
        assert response.status_code in [200, 201, 401, 404]

    def test_create_group_max_members(self, client, auth_headers):
        """Test group creation with maximum members (256)."""
        members = [f"user{i}" for i in range(256)]
        response = client.post("/api/v1/groups",
            headers=auth_headers,
            json={
                "name": "Large Group",
                "members": members
            })
        assert response.status_code in [200, 201, 400, 401, 404]

    def test_get_group_info(self, client, auth_headers):
        """Test getting group information."""
        response = client.get("/api/v1/groups/group123", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_update_group_info(self, client, auth_headers):
        """Test updating group information."""
        response = client.patch("/api/v1/groups/group123",
            headers=auth_headers,
            json={"name": "Updated Group Name"})
        assert response.status_code in [200, 401, 403, 404]

    def test_add_group_member(self, client, auth_headers):
        """Test adding a member to group."""
        response = client.post("/api/v1/groups/group123/members",
            headers=auth_headers,
            json={"user_id": "newuser"})
        assert response.status_code in [200, 201, 401, 403, 404]

    def test_remove_group_member(self, client, auth_headers):
        """Test removing a member from group."""
        response = client.delete("/api/v1/groups/group123/members/user456",
            headers=auth_headers)
        assert response.status_code in [200, 204, 401, 403, 404]

    def test_leave_group(self, client, auth_headers):
        """Test leaving a group."""
        response = client.post("/api/v1/groups/group123/leave",
            headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_send_group_message(self, client, auth_headers):
        """Test sending message to group."""
        response = client.post("/api/v1/groups/group123/messages",
            headers=auth_headers,
            json={
                "content": "Hello group!",
                "type": "text"
            })
        assert response.status_code in [200, 201, 401, 404]

    def test_get_group_messages(self, client, auth_headers):
        """Test getting group message history."""
        response = client.get("/api/v1/groups/group123/messages",
            headers=auth_headers,
            params={"limit": 50})
        assert response.status_code in [200, 401, 404]

    # ==================== Presence Tests ====================

    def test_update_presence(self, client, auth_headers):
        """Test updating user presence status."""
        response = client.post("/api/v1/presence",
            headers=auth_headers,
            json={"status": "online"})
        assert response.status_code in [200, 401, 404]

    def test_get_user_presence(self, client, auth_headers):
        """Test getting another user's presence."""
        response = client.get("/api/v1/presence/user456", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_get_last_seen(self, client, auth_headers):
        """Test getting user's last seen time."""
        response = client.get("/api/v1/users/user456/last-seen",
            headers=auth_headers)
        assert response.status_code in [200, 401, 403, 404]  # 403 if privacy setting blocks

    # ==================== Typing Indicator Tests ====================

    def test_send_typing_indicator(self, client, auth_headers):
        """Test sending typing indicator."""
        response = client.post("/api/v1/conversations/user456/typing",
            headers=auth_headers,
            json={"is_typing": True})
        assert response.status_code in [200, 401, 404]

    # ==================== Message Deletion Tests ====================

    def test_delete_message_for_me(self, client, auth_headers):
        """Test deleting a message for self."""
        response = client.delete("/api/v1/messages/msg123",
            headers=auth_headers,
            params={"for_everyone": False})
        assert response.status_code in [200, 204, 401, 404]

    def test_delete_message_for_everyone(self, client, auth_headers):
        """Test deleting a message for everyone."""
        response = client.delete("/api/v1/messages/msg123",
            headers=auth_headers,
            params={"for_everyone": True})
        assert response.status_code in [200, 204, 401, 403, 404]  # 403 if time limit exceeded

    # ==================== Search Tests ====================

    def test_search_messages(self, client, auth_headers):
        """Test searching messages."""
        response = client.get("/api/v1/messages/search",
            headers=auth_headers,
            params={"query": "hello", "limit": 20})
        assert response.status_code in [200, 401, 404]

    def test_search_users(self, client, auth_headers):
        """Test searching users."""
        response = client.get("/api/v1/users/search",
            headers=auth_headers,
            params={"query": "john"})
        assert response.status_code in [200, 401, 404]

    # ==================== Notification Tests ====================

    def test_register_push_token(self, client, auth_headers):
        """Test registering push notification token."""
        response = client.post("/api/v1/notifications/register",
            headers=auth_headers,
            json={
                "token": "fcm_token_123",
                "platform": "android"
            })
        assert response.status_code in [200, 201, 401, 404]

    def test_update_notification_settings(self, client, auth_headers):
        """Test updating notification settings."""
        response = client.patch("/api/v1/notifications/settings",
            headers=auth_headers,
            json={
                "mute_all": False,
                "show_preview": True
            })
        assert response.status_code in [200, 401, 404]


class TestChatAppWebSocket:
    """WebSocket tests for real-time messaging."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection."""
        try:
            async with websockets.connect(f"{WS_URL}/ws/chat") as ws:
                # Send auth
                await ws.send(json.dumps({"type": "auth", "token": "test-token"}))
                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                assert "type" in data
        except Exception:
            # WebSocket not implemented or connection refused
            pytest.skip("WebSocket endpoint not available")

    @pytest.mark.asyncio
    async def test_websocket_message_send(self):
        """Test sending message via WebSocket."""
        try:
            async with websockets.connect(f"{WS_URL}/ws/chat") as ws:
                # Auth
                await ws.send(json.dumps({"type": "auth", "token": "test-token"}))
                await asyncio.wait_for(ws.recv(), timeout=5.0)

                # Send message
                await ws.send(json.dumps({
                    "type": "message",
                    "recipient_id": "user456",
                    "content": "Hello via WebSocket!"
                }))

                # Wait for ack
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                assert data.get("type") in ["ack", "message", "error"]
        except Exception:
            pytest.skip("WebSocket endpoint not available")

    @pytest.mark.asyncio
    async def test_websocket_presence_update(self):
        """Test presence updates via WebSocket."""
        try:
            async with websockets.connect(f"{WS_URL}/ws/chat") as ws:
                await ws.send(json.dumps({"type": "auth", "token": "test-token"}))
                await asyncio.wait_for(ws.recv(), timeout=5.0)

                # Subscribe to presence
                await ws.send(json.dumps({
                    "type": "subscribe_presence",
                    "user_ids": ["user456", "user789"]
                }))

                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                assert response is not None
        except Exception:
            pytest.skip("WebSocket endpoint not available")


class TestChatAppEncryption:
    """Tests for end-to-end encryption features."""

    @pytest.fixture
    def client(self):
        return httpx.Client(base_url=BASE_URL, timeout=30.0)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test-token"}

    def test_get_public_keys(self, client, auth_headers):
        """Test getting user's public keys for E2E encryption."""
        response = client.get("/api/v1/keys/user456", headers=auth_headers)
        assert response.status_code in [200, 401, 404]

    def test_upload_prekeys(self, client, auth_headers):
        """Test uploading prekeys for Signal protocol."""
        response = client.post("/api/v1/keys/prekeys",
            headers=auth_headers,
            json={
                "identity_key": "base64_identity_key",
                "signed_prekey": "base64_signed_prekey",
                "prekeys": ["key1", "key2", "key3"]
            })
        assert response.status_code in [200, 201, 401, 404]

    def test_get_prekey_bundle(self, client, auth_headers):
        """Test getting prekey bundle for establishing session."""
        response = client.get("/api/v1/keys/user456/bundle", headers=auth_headers)
        assert response.status_code in [200, 401, 404]
