"""
Performance tests for Chat Application using Locust.
Run with: locust -f locustfile_chat.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import random
import string
import time
import json


class ChatAppUser(HttpUser):
    """Simulates a user interacting with the Chat Application."""

    wait_time = between(0.5, 2)

    def on_start(self):
        """Initialize user session."""
        self.user_id = f"user_{random.randint(1, 100000)}"
        self.auth_headers = {"Authorization": f"Bearer token_{self.user_id}"}
        self.contacts = [f"user_{i}" for i in random.sample(range(1, 1000), 10)]
        self.groups = []
        self.message_count = 0

    def generate_message(self):
        """Generate a random message."""
        messages = [
            "Hey, how are you?",
            "Did you see the news?",
            "Let's meet up later!",
            "👋 Hello!",
            "Can you send me the file?",
            "Thanks for your help!",
            "See you tomorrow",
            "That's great news!",
            "I'll check and get back to you",
            "Perfect, sounds good!",
        ]
        return random.choice(messages)

    @task(20)
    def send_message(self):
        """Send a text message - most frequent action."""
        recipient = random.choice(self.contacts)

        with self.client.post("/api/v1/messages",
            headers=self.auth_headers,
            json={
                "recipient_id": recipient,
                "content": self.generate_message(),
                "type": "text"
            },
            catch_response=True) as response:

            if response.status_code in [200, 201]:
                self.message_count += 1
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Send failed: {response.status_code}")

    @task(15)
    def get_conversations(self):
        """Get list of conversations."""
        with self.client.get("/api/v1/conversations",
            headers=self.auth_headers,
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Get conversations failed: {response.status_code}")

    @task(10)
    def get_conversation_messages(self):
        """Get messages from a conversation."""
        contact = random.choice(self.contacts)

        with self.client.get(f"/api/v1/conversations/{contact}/messages",
            headers=self.auth_headers,
            params={"limit": 50},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Get messages failed: {response.status_code}")

    @task(5)
    def update_presence(self):
        """Update user presence/online status."""
        with self.client.post("/api/v1/presence",
            headers=self.auth_headers,
            json={"status": "online"},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Presence update failed: {response.status_code}")

    @task(3)
    def get_contact_presence(self):
        """Check if a contact is online."""
        contact = random.choice(self.contacts)

        with self.client.get(f"/api/v1/presence/{contact}",
            headers=self.auth_headers,
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Get presence failed: {response.status_code}")

    @task(3)
    def send_typing_indicator(self):
        """Send typing indicator."""
        contact = random.choice(self.contacts)

        with self.client.post(f"/api/v1/conversations/{contact}/typing",
            headers=self.auth_headers,
            json={"is_typing": True},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Typing indicator failed: {response.status_code}")

    @task(2)
    def mark_messages_read(self):
        """Mark messages as read."""
        contact = random.choice(self.contacts)

        with self.client.post(f"/api/v1/conversations/{contact}/read",
            headers=self.auth_headers,
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Mark read failed: {response.status_code}")

    @task(1)
    def create_group(self):
        """Create a group chat."""
        members = random.sample(self.contacts, min(5, len(self.contacts)))

        with self.client.post("/api/v1/groups",
            headers=self.auth_headers,
            json={
                "name": f"Test Group {random.randint(1, 1000)}",
                "members": members
            },
            catch_response=True) as response:

            if response.status_code in [200, 201]:
                data = response.json()
                group_id = data.get("id") or data.get("group_id")
                if group_id:
                    self.groups.append(group_id)
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Create group failed: {response.status_code}")

    @task(5)
    def send_group_message(self):
        """Send message to a group."""
        if not self.groups:
            return

        group_id = random.choice(self.groups)

        with self.client.post(f"/api/v1/groups/{group_id}/messages",
            headers=self.auth_headers,
            json={
                "content": self.generate_message(),
                "type": "text"
            },
            catch_response=True) as response:

            if response.status_code in [200, 201, 404]:
                response.success()
            else:
                response.failure(f"Group message failed: {response.status_code}")

    @task(1)
    def search_messages(self):
        """Search messages."""
        with self.client.get("/api/v1/messages/search",
            headers=self.auth_headers,
            params={"query": "hello", "limit": 20},
            catch_response=True) as response:

            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Search failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check."""
        self.client.get("/health")


class ChatAppHighVolumeUser(HttpUser):
    """High volume user for stress testing message throughput."""

    wait_time = between(0.1, 0.3)

    def on_start(self):
        self.auth_headers = {"Authorization": "Bearer stress-test-token"}

    @task
    def rapid_message(self):
        """Send messages rapidly to test throughput."""
        self.client.post("/api/v1/messages",
            headers=self.auth_headers,
            json={
                "recipient_id": "stress_target",
                "content": f"Stress test {time.time()}",
                "type": "text"
            })


class ChatAppGroupBroadcastUser(HttpUser):
    """User for testing group message fanout."""

    wait_time = between(0.5, 1)

    def on_start(self):
        self.auth_headers = {"Authorization": "Bearer broadcast-test-token"}
        self.large_group_id = "large_group_256"

    @task
    def broadcast_to_large_group(self):
        """Send message to large group to test fanout."""
        self.client.post(f"/api/v1/groups/{self.large_group_id}/messages",
            headers=self.auth_headers,
            json={
                "content": f"Broadcast test {time.time()}",
                "type": "text"
            })
