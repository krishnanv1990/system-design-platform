# Chatbot System Design (ChatGPT-like)

## Problem Overview

Design an LLM-powered chatbot system handling 100M weekly users, 1B messages/day, with streaming responses and <5s first token latency.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Web App    │  │  Mobile App  │  │     API      │  │  Plugins     │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┘
          │                 │                 │                 │
          └─────────────────┴────────┬────────┴─────────────────┘
                                     │
          ┌──────────────────────────▼──────────────────────────┐
          │                    API Gateway                       │
          │   (Auth, Rate Limiting, Request Routing)             │
          └──────────────────────────┬──────────────────────────┘
                                     │
          ┌──────────────────────────▼──────────────────────────┐
          │                  Chat Service                        │
          │   (Session Management, Context Assembly)             │
          └──────────────────────────┬──────────────────────────┘
                                     │
     ┌───────────────────────────────┼───────────────────────────────┐
     │                               │                               │
     ▼                               ▼                               ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Prompt Cache   │       │    LLM Router   │       │   Safety Filter │
│   (Redis)       │       │                 │       │                 │
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GPU Cluster   │     │   GPU Cluster   │     │   GPU Cluster   │
│   (Region A)    │     │   (Region B)    │     │   (Region C)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Core Components

#### 1. Chat Service

```python
from dataclasses import dataclass
from typing import List, AsyncIterator
import uuid

@dataclass
class Message:
    role: str  # user, assistant, system
    content: str
    timestamp: datetime

@dataclass
class Conversation:
    id: str
    user_id: str
    messages: List[Message]
    system_prompt: str
    model: str
    created_at: datetime

class ChatService:
    def __init__(self, llm_router, cache, safety_filter):
        self.llm = llm_router
        self.cache = cache
        self.safety = safety_filter

    async def chat(
        self,
        conversation_id: str,
        user_message: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Process a chat message and stream response."""
        # Get conversation
        conversation = await self.get_conversation(conversation_id)

        # Safety check on input
        if not await self.safety.is_safe(user_message):
            yield "I cannot respond to that request."
            return

        # Add user message
        conversation.messages.append(Message(
            role="user",
            content=user_message,
            timestamp=datetime.utcnow()
        ))

        # Check prompt cache
        cache_key = self.compute_cache_key(conversation)
        cached = await self.cache.get(cache_key)
        if cached:
            yield cached
            return

        # Build prompt
        prompt = self.build_prompt(conversation)

        # Stream response from LLM
        full_response = ""
        async for token in self.llm.generate(
            prompt=prompt,
            model=conversation.model,
            stream=True
        ):
            # Safety check on output
            if await self.safety.contains_unsafe(token):
                continue

            full_response += token
            yield token

        # Store assistant response
        conversation.messages.append(Message(
            role="assistant",
            content=full_response,
            timestamp=datetime.utcnow()
        ))
        await self.save_conversation(conversation)

        # Cache if appropriate
        if len(conversation.messages) <= 4:
            await self.cache.set(cache_key, full_response, ttl=3600)

    def build_prompt(self, conversation: Conversation) -> List[dict]:
        """Build prompt from conversation history."""
        messages = [
            {"role": "system", "content": conversation.system_prompt}
        ]

        # Truncate history if too long
        history = conversation.messages[-20:]  # Last 20 messages

        for msg in history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages

    def compute_cache_key(self, conversation: Conversation) -> str:
        """Compute cache key for prompt caching."""
        # Only cache for conversations with few messages
        if len(conversation.messages) > 4:
            return None

        content = json.dumps([
            {"role": m.role, "content": m.content}
            for m in conversation.messages
        ])
        return hashlib.sha256(content.encode()).hexdigest()
```

#### 2. LLM Router

```python
class LLMRouter:
    """Routes requests to optimal GPU cluster."""

    def __init__(self, clusters: List[GPUCluster]):
        self.clusters = clusters

    async def generate(
        self,
        prompt: List[dict],
        model: str,
        stream: bool = True,
        **kwargs
    ) -> AsyncIterator[str]:
        """Generate response, routing to best cluster."""
        # Find optimal cluster
        cluster = await self.select_cluster(model)

        if stream:
            async for token in cluster.stream_generate(prompt, model, **kwargs):
                yield token
        else:
            response = await cluster.generate(prompt, model, **kwargs)
            yield response

    async def select_cluster(self, model: str) -> GPUCluster:
        """Select cluster based on load and latency."""
        available = [c for c in self.clusters if c.supports_model(model)]

        if not available:
            raise ModelNotAvailableError(model)

        # Score clusters by latency and load
        scores = []
        for cluster in available:
            latency = await cluster.ping()
            load = cluster.current_load
            score = latency * (1 + load)  # Lower is better
            scores.append((score, cluster))

        scores.sort(key=lambda x: x[0])
        return scores[0][1]


class GPUCluster:
    """GPU cluster for LLM inference."""

    def __init__(self, endpoint: str, models: List[str]):
        self.endpoint = endpoint
        self.models = set(models)
        self.current_load = 0.0

    def supports_model(self, model: str) -> bool:
        return model in self.models

    async def stream_generate(
        self,
        prompt: List[dict],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Stream tokens from the model."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.endpoint}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                }
            ) as response:
                async for line in response.content:
                    if line.startswith(b"data: "):
                        data = json.loads(line[6:])
                        if "choices" in data:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
```

#### 3. Safety Filter

```python
class SafetyFilter:
    """Content safety filtering using classifiers."""

    def __init__(self, classifier_endpoint: str):
        self.classifier = classifier_endpoint

    async def is_safe(self, text: str) -> bool:
        """Check if input is safe."""
        result = await self.classify(text)
        return result["safe"]

    async def contains_unsafe(self, text: str) -> bool:
        """Check if output contains unsafe content."""
        result = await self.classify(text)
        return not result["safe"]

    async def classify(self, text: str) -> dict:
        """Classify text safety."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.classifier}/classify",
                json={"text": text}
            ) as response:
                return await response.json()

    def get_filtered_response(self) -> str:
        """Return a safe response when filtering."""
        return "I'm not able to provide that type of response."
```

### Database Schema

```sql
-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    title TEXT,
    model VARCHAR(50),
    system_prompt TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Messages
CREATE TABLE messages (
    id BIGSERIAL,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (conversation_id, id)
);

CREATE INDEX idx_messages_conv ON messages(conversation_id);

-- Usage tracking
CREATE TABLE usage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    conversation_id UUID,
    input_tokens INTEGER,
    output_tokens INTEGER,
    model VARCHAR(50),
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Realistic Testing

```python
class TestChatbot:
    async def test_basic_chat(self, client):
        """Test basic chat functionality."""
        # Create conversation
        conv = await client.post("/api/v1/conversations", json={
            "model": "gpt-4"
        })
        conv_id = conv.json()["id"]

        # Send message
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Hello, how are you?"}
        )

        assert response.status_code == 200
        assert len(response.json()["content"]) > 0

    async def test_streaming(self, ws_client):
        """Test streaming responses."""
        conv_id = await create_conversation()

        await ws_client.send(json.dumps({
            "conversation_id": conv_id,
            "content": "Write a short poem"
        }))

        tokens = []
        while True:
            msg = await asyncio.wait_for(ws_client.recv(), timeout=30)
            data = json.loads(msg)
            if data["type"] == "token":
                tokens.append(data["content"])
            elif data["type"] == "done":
                break

        assert len(tokens) > 10  # Should have multiple tokens

    async def test_context_retention(self, client):
        """Test conversation context."""
        conv_id = await create_conversation()

        # First message
        await client.post(f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "My name is Alice"})

        # Second message referencing first
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "What is my name?"}
        )

        assert "Alice" in response.json()["content"]

    async def test_rate_limiting(self, client):
        """Test rate limiting."""
        conv_id = await create_conversation()

        # Send many requests
        responses = []
        for _ in range(100):
            r = await client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={"content": "Hi"}
            )
            responses.append(r.status_code)

        # Some should be rate limited
        assert 429 in responses
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| First Token Latency | < 5 seconds |
| Token Throughput | > 50 tokens/sec |
| Availability | 99.9% |
| Safety Filter Accuracy | > 99% |
