# Realtime Gaming Leaderboard Design

## Problem Overview

Design a real-time leaderboard system for 100M players with sub-second updates and efficient rank queries.

**Difficulty:** Medium (L6 - Staff Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Game Clients                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │ Player 1 │  │ Player 2 │  │ Player N │  │ Viewer   │                        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                        │
└───────┼─────────────┼─────────────┼─────────────┼───────────────────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │           API Gateway + LB              │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │          Score Ingestion Service         │
        │    (Validates, rate limits, queues)      │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │              Kafka                       │
        │    ┌─────────────────────────────┐      │
        │    │  Score Updates Topic         │      │
        │    └─────────────────────────────┘      │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │        Leaderboard Workers               │
        │   (Update Redis sorted sets)             │
        └────────────────────┬────────────────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │           Redis Cluster                  │
        │   ┌─────────────────────────────┐       │
        │   │  Global Leaderboard (ZSET)   │       │
        │   │  Regional Leaderboards       │       │
        │   │  Friends Leaderboards        │       │
        │   └─────────────────────────────┘       │
        └─────────────────────────────────────────┘
```

### Core Components

#### 1. Score Ingestion

```python
from dataclasses import dataclass
from datetime import datetime
import hashlib

@dataclass
class ScoreUpdate:
    player_id: str
    game_id: str
    score: int
    metadata: dict
    timestamp: datetime
    signature: str  # Anti-cheat signature

class ScoreIngestionService:
    def __init__(self, kafka_producer, rate_limiter, validator):
        self.kafka = kafka_producer
        self.rate_limiter = rate_limiter
        self.validator = validator

    async def submit_score(self, update: ScoreUpdate) -> bool:
        """
        Submit a score update with validation and anti-cheat checks.
        """
        # Rate limiting (10 updates/second per player)
        if not await self.rate_limiter.allow(
            f"score:{update.player_id}",
            limit=10,
            window=1
        ):
            raise RateLimitExceeded()

        # Validate score integrity
        if not await self.validator.validate_score(update):
            raise InvalidScoreError("Score validation failed")

        # Anti-cheat checks
        if await self.is_suspicious(update):
            await self.flag_for_review(update)
            return False

        # Queue for processing
        await self.kafka.send("score-updates", {
            "player_id": update.player_id,
            "game_id": update.game_id,
            "score": update.score,
            "timestamp": update.timestamp.isoformat()
        })

        return True

    async def is_suspicious(self, update: ScoreUpdate) -> bool:
        """Check for suspicious score patterns."""
        # Get player's recent scores
        recent_scores = await self.get_recent_scores(update.player_id)

        # Check for impossible improvement
        if recent_scores:
            max_recent = max(s.score for s in recent_scores)
            if update.score > max_recent * 2:  # 2x improvement suspicious
                return True

        # Check score reasonableness for game
        game_config = await self.get_game_config(update.game_id)
        if update.score > game_config.max_possible_score:
            return True

        return False
```

#### 2. Leaderboard Service

```python
import redis.asyncio as redis

class LeaderboardService:
    """
    Manages leaderboards using Redis Sorted Sets.
    Supports global, regional, and friends leaderboards.
    """

    def __init__(self, redis_cluster):
        self.redis = redis_cluster

    # ========== Score Updates ==========

    async def update_score(
        self,
        leaderboard_id: str,
        player_id: str,
        score: int,
        mode: str = "max"  # max, latest, sum
    ):
        """Update player's score in leaderboard."""
        key = f"lb:{leaderboard_id}"

        if mode == "max":
            # Only update if new score is higher
            current = await self.redis.zscore(key, player_id)
            if current is None or score > current:
                await self.redis.zadd(key, {player_id: score})
        elif mode == "latest":
            await self.redis.zadd(key, {player_id: score})
        elif mode == "sum":
            await self.redis.zincrby(key, score, player_id)

    async def update_multiple_leaderboards(
        self,
        player_id: str,
        score: int,
        region: str,
        game_mode: str
    ):
        """Update score across all relevant leaderboards."""
        pipe = self.redis.pipeline()

        # Global leaderboard
        pipe.zadd(f"lb:global:{game_mode}", {player_id: score}, gt=True)

        # Regional leaderboard
        pipe.zadd(f"lb:region:{region}:{game_mode}", {player_id: score}, gt=True)

        # Daily leaderboard
        today = datetime.utcnow().strftime("%Y-%m-%d")
        pipe.zadd(f"lb:daily:{today}:{game_mode}", {player_id: score}, gt=True)
        pipe.expire(f"lb:daily:{today}:{game_mode}", 86400 * 7)  # Keep 7 days

        await pipe.execute()

    # ========== Queries ==========

    async def get_top_n(
        self,
        leaderboard_id: str,
        n: int = 100
    ) -> List[dict]:
        """Get top N players."""
        key = f"lb:{leaderboard_id}"
        results = await self.redis.zrevrange(
            key, 0, n - 1, withscores=True
        )

        return [
            {"rank": i + 1, "player_id": player, "score": int(score)}
            for i, (player, score) in enumerate(results)
        ]

    async def get_player_rank(
        self,
        leaderboard_id: str,
        player_id: str
    ) -> dict:
        """Get player's rank and score."""
        key = f"lb:{leaderboard_id}"

        pipe = self.redis.pipeline()
        pipe.zrevrank(key, player_id)
        pipe.zscore(key, player_id)
        rank, score = await pipe.execute()

        if rank is None:
            return {"rank": None, "score": None}

        return {
            "rank": rank + 1,  # 0-indexed to 1-indexed
            "score": int(score)
        }

    async def get_rank_range(
        self,
        leaderboard_id: str,
        player_id: str,
        range_size: int = 5
    ) -> List[dict]:
        """Get players around a specific player's rank."""
        key = f"lb:{leaderboard_id}"

        # Get player's rank
        rank = await self.redis.zrevrank(key, player_id)
        if rank is None:
            return []

        start = max(0, rank - range_size)
        end = rank + range_size

        results = await self.redis.zrevrange(
            key, start, end, withscores=True
        )

        return [
            {"rank": start + i + 1, "player_id": player, "score": int(score)}
            for i, (player, score) in enumerate(results)
        ]

    async def get_friends_leaderboard(
        self,
        player_id: str,
        friend_ids: List[str],
        game_mode: str
    ) -> List[dict]:
        """Get leaderboard for player's friends."""
        key = f"lb:global:{game_mode}"
        all_players = [player_id] + friend_ids

        # Get scores for all friends
        pipe = self.redis.pipeline()
        for pid in all_players:
            pipe.zscore(key, pid)

        scores = await pipe.execute()

        # Build and sort leaderboard
        leaderboard = [
            {"player_id": pid, "score": int(score) if score else 0}
            for pid, score in zip(all_players, scores)
        ]
        leaderboard.sort(key=lambda x: x["score"], reverse=True)

        # Add ranks
        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1

        return leaderboard


class LeaderboardWorker:
    """Consumes score updates from Kafka and updates Redis."""

    async def process(self, message: dict):
        player_id = message["player_id"]
        game_id = message["game_id"]
        score = message["score"]

        # Get player metadata for regional leaderboard
        player = await self.get_player(player_id)

        # Update all leaderboards
        await self.leaderboard.update_multiple_leaderboards(
            player_id=player_id,
            score=score,
            region=player.region,
            game_mode=game_id
        )
```

#### 3. Real-time Updates (WebSocket)

```python
class LeaderboardWebSocket:
    """Push leaderboard updates to connected clients."""

    async def subscribe_top_n(
        self,
        websocket,
        leaderboard_id: str,
        n: int = 10
    ):
        """Subscribe to top N changes."""
        channel = f"lb_updates:{leaderboard_id}:top_{n}"
        await self.redis.subscribe(channel)

        # Send initial state
        top_n = await self.leaderboard.get_top_n(leaderboard_id, n)
        await websocket.send(json.dumps({
            "type": "initial",
            "leaderboard": top_n
        }))

        # Listen for updates
        async for message in self.redis.listen(channel):
            await websocket.send(json.dumps({
                "type": "update",
                "changes": message
            }))

    async def notify_rank_change(
        self,
        leaderboard_id: str,
        player_id: str,
        old_rank: int,
        new_rank: int
    ):
        """Notify about significant rank changes."""
        # Only notify for top 100 changes
        if new_rank <= 100 or old_rank <= 100:
            await self.redis.publish(
                f"lb_updates:{leaderboard_id}:top_100",
                json.dumps({
                    "player_id": player_id,
                    "old_rank": old_rank,
                    "new_rank": new_rank
                })
            )
```

### Database Schema

```sql
-- PostgreSQL for persistent storage and analytics

-- Player profiles
CREATE TABLE players (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    region VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    total_games_played INTEGER DEFAULT 0,
    highest_score BIGINT DEFAULT 0
);

-- Historical scores (for analytics)
CREATE TABLE score_history (
    id BIGSERIAL,
    player_id VARCHAR(50) REFERENCES players(id),
    game_mode VARCHAR(50),
    score BIGINT NOT NULL,
    rank_at_time INTEGER,
    recorded_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (player_id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Leaderboard snapshots (hourly)
CREATE TABLE leaderboard_snapshots (
    id SERIAL,
    leaderboard_id VARCHAR(100),
    snapshot_time TIMESTAMP,
    top_100 JSONB,  -- Snapshot of top 100
    total_players INTEGER,
    PRIMARY KEY (leaderboard_id, snapshot_time)
);
```

---

## Realistic Testing

### 1. Functional Tests

```python
class TestLeaderboard:
    async def test_score_update(self, client, redis):
        """Test score submission and rank update."""
        # Submit score
        response = await client.post("/api/v1/scores", json={
            "player_id": "player1",
            "game_id": "game1",
            "score": 1000
        })
        assert response.status_code == 200

        # Check rank
        rank = await client.get("/api/v1/leaderboard/global/player1")
        assert rank.json()["score"] == 1000

    async def test_leaderboard_ordering(self, client):
        """Test correct ordering of leaderboard."""
        # Submit multiple scores
        scores = [(f"player{i}", i * 100) for i in range(1, 11)]
        for player, score in scores:
            await client.post("/api/v1/scores", json={
                "player_id": player,
                "game_id": "game1",
                "score": score
            })

        # Get top 10
        top = await client.get("/api/v1/leaderboard/global?limit=10")
        results = top.json()["leaderboard"]

        # Verify descending order
        for i in range(len(results) - 1):
            assert results[i]["score"] >= results[i + 1]["score"]

        # Highest scorer should be rank 1
        assert results[0]["player_id"] == "player10"
        assert results[0]["rank"] == 1

    async def test_rank_around_player(self, client):
        """Test getting ranks around a player."""
        # Create 100 players
        for i in range(1, 101):
            await client.post("/api/v1/scores", json={
                "player_id": f"player{i}",
                "game_id": "game1",
                "score": i * 10
            })

        # Get ranks around player50
        response = await client.get(
            "/api/v1/leaderboard/global/player50/around?range=5"
        )
        results = response.json()

        # Should have 11 entries (5 above, player, 5 below)
        assert len(results) == 11
        assert any(r["player_id"] == "player50" for r in results)

    async def test_friends_leaderboard(self, client):
        """Test friends-only leaderboard."""
        friends = ["friend1", "friend2", "friend3"]

        # Submit scores
        for i, friend in enumerate(friends):
            await client.post("/api/v1/scores", json={
                "player_id": friend,
                "game_id": "game1",
                "score": (i + 1) * 100
            })

        # Get friends leaderboard
        response = await client.get(
            "/api/v1/leaderboard/friends/me",
            params={"friends": friends}
        )

        assert len(response.json()) == 3
        assert response.json()[0]["player_id"] == "friend3"
```

### 2. Performance Tests

```python
from locust import HttpUser, task, between

class LeaderboardUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(10)
    def submit_score(self):
        self.client.post("/api/v1/scores", json={
            "player_id": f"player_{random.randint(1, 1000000)}",
            "game_id": "game1",
            "score": random.randint(1, 1000000)
        })

    @task(50)
    def get_top_100(self):
        self.client.get("/api/v1/leaderboard/global?limit=100")

    @task(30)
    def get_my_rank(self):
        player_id = f"player_{random.randint(1, 1000000)}"
        self.client.get(f"/api/v1/leaderboard/global/{player_id}")

    @task(10)
    def get_around_me(self):
        player_id = f"player_{random.randint(1, 1000000)}"
        self.client.get(f"/api/v1/leaderboard/global/{player_id}/around")
```

**Targets:**
| Operation | Target |
|-----------|--------|
| Score Update | < 10ms |
| Get Top N | < 5ms |
| Get My Rank | < 5ms |
| Throughput | > 50K ops/sec |

### 3. Chaos Tests

```python
class LeaderboardChaosTests:
    async def test_redis_failover(self):
        """Test during Redis failover."""
        # Submit baseline score
        await client.post("/api/v1/scores", json={
            "player_id": "test_player",
            "score": 1000
        })

        # Trigger failover
        await platform_api.trigger_redis_failover()

        # Try operations during failover
        errors = 0
        for _ in range(100):
            try:
                await client.get("/api/v1/leaderboard/global?limit=10")
            except:
                errors += 1
            await asyncio.sleep(0.1)

        # Should recover quickly
        assert errors < 20  # < 20% error rate
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Score Update Latency | < 10ms |
| Rank Query Latency | < 5ms |
| Top N Query | < 5ms |
| Update Throughput | > 10K/sec |
| Query Throughput | > 50K/sec |
