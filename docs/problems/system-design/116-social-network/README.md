# Social Network Design (Facebook-like)

## Problem Overview

Design a social network with 3B MAU, 1B posts/day, and personalized news feed generation in <500ms.

**Difficulty:** Hard (L7 - Principal Engineer)

---

## Best Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                          │
│  │  Mobile App  │  │   Web App    │  │     API      │                          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                          │
└─────────┼─────────────────┼─────────────────┼───────────────────────────────────┘
          │                 │                 │
          └─────────────────┴────────┬────────┘
                                     │
          ┌──────────────────────────▼──────────────────────────┐
          │                    API Gateway                       │
          └──────────────────────────┬──────────────────────────┘
                                     │
     ┌───────────────────────────────┼───────────────────────────────┐
     │                               │                               │
     ▼                               ▼                               ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    Post         │       │     Feed        │       │   Graph         │
│    Service      │       │    Service      │       │   Service       │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   Post Store    │       │   Feed Cache    │       │  Graph Store    │
│   (Cassandra)   │       │   (Redis)       │       │   (Neo4j)       │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

### Core Components

#### 1. Social Graph

```python
from neo4j import AsyncGraphDatabase

class GraphService:
    """Manages social connections using graph database."""

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver

    async def add_friend(self, user_id: str, friend_id: str):
        """Create bidirectional friendship."""
        async with self.driver.session() as session:
            await session.run("""
                MATCH (a:User {id: $user_id})
                MATCH (b:User {id: $friend_id})
                MERGE (a)-[:FRIENDS_WITH {since: datetime()}]->(b)
                MERGE (b)-[:FRIENDS_WITH {since: datetime()}]->(a)
            """, user_id=user_id, friend_id=friend_id)

    async def get_friends(self, user_id: str) -> List[str]:
        """Get all friends of a user."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (u:User {id: $user_id})-[:FRIENDS_WITH]->(friend)
                RETURN friend.id as friend_id
            """, user_id=user_id)
            return [record["friend_id"] async for record in result]

    async def get_friends_of_friends(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[dict]:
        """Get friend suggestions (friends of friends)."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (u:User {id: $user_id})-[:FRIENDS_WITH]->(friend)
                      -[:FRIENDS_WITH]->(fof)
                WHERE NOT (u)-[:FRIENDS_WITH]->(fof)
                AND fof.id <> $user_id
                RETURN fof.id as user_id, COUNT(friend) as mutual_friends
                ORDER BY mutual_friends DESC
                LIMIT $limit
            """, user_id=user_id, limit=limit)
            return [dict(record) async for record in result]

    async def get_mutual_friends(
        self,
        user_id: str,
        other_id: str
    ) -> List[str]:
        """Get mutual friends between two users."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (a:User {id: $user_id})-[:FRIENDS_WITH]->(mutual)
                      <-[:FRIENDS_WITH]-(b:User {id: $other_id})
                RETURN mutual.id as mutual_id
            """, user_id=user_id, other_id=other_id)
            return [record["mutual_id"] async for record in result]
```

#### 2. Post Service

```python
from cassandra.cluster import Cluster

class PostService:
    """Manages posts and content."""

    def __init__(self, cassandra_session, kafka_producer):
        self.db = cassandra_session
        self.kafka = kafka_producer

    async def create_post(
        self,
        user_id: str,
        content: str,
        media_urls: List[str] = None,
        visibility: str = "friends"
    ) -> Post:
        """Create a new post."""
        post = Post(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=content,
            media_urls=media_urls or [],
            visibility=visibility,
            like_count=0,
            comment_count=0,
            share_count=0,
            created_at=datetime.utcnow()
        )

        # Store post
        await self.db.execute("""
            INSERT INTO posts (id, user_id, content, media_urls, visibility,
                             like_count, comment_count, share_count, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (post.id, post.user_id, post.content, post.media_urls,
              post.visibility, 0, 0, 0, post.created_at))

        # Fanout to feeds
        await self.kafka.send("post-created", {
            "post_id": post.id,
            "user_id": post.user_id,
            "visibility": post.visibility,
            "created_at": post.created_at.isoformat()
        })

        return post

    async def like_post(self, post_id: str, user_id: str):
        """Like a post."""
        # Check if already liked
        existing = await self.db.execute("""
            SELECT * FROM post_likes
            WHERE post_id = %s AND user_id = %s
        """, (post_id, user_id))

        if existing:
            return

        # Add like
        await self.db.execute("""
            INSERT INTO post_likes (post_id, user_id, created_at)
            VALUES (%s, %s, %s)
        """, (post_id, user_id, datetime.utcnow()))

        # Increment counter
        await self.db.execute("""
            UPDATE posts SET like_count = like_count + 1
            WHERE id = %s
        """, (post_id,))

        # Notify post owner
        await self.notify_owner(post_id, "like", user_id)
```

#### 3. Feed Service

```python
class FeedService:
    """Generates personalized news feeds."""

    def __init__(
        self,
        redis_client,
        post_service,
        graph_service,
        ranker
    ):
        self.redis = redis_client
        self.posts = post_service
        self.graph = graph_service
        self.ranker = ranker

    async def get_feed(
        self,
        user_id: str,
        cursor: str = None,
        limit: int = 20
    ) -> List[Post]:
        """Get personalized feed for user."""
        # Check cache first
        cache_key = f"feed:{user_id}"
        cached = await self.redis.lrange(cache_key, 0, limit - 1)

        if cached and not cursor:
            post_ids = [json.loads(p)["post_id"] for p in cached]
            return await self.posts.get_posts(post_ids)

        # Generate feed
        feed = await self.generate_feed(user_id, limit * 3)

        # Cache feed
        pipe = self.redis.pipeline()
        pipe.delete(cache_key)
        for post in feed[:100]:  # Cache top 100
            pipe.rpush(cache_key, json.dumps({
                "post_id": post.id,
                "score": post.score
            }))
        pipe.expire(cache_key, 300)  # 5 min TTL
        await pipe.execute()

        return feed[:limit]

    async def generate_feed(
        self,
        user_id: str,
        limit: int
    ) -> List[Post]:
        """Generate feed using pull model with ranking."""
        # Get friends' posts
        friends = await self.graph.get_friends(user_id)
        posts = []

        for friend_id in friends[:500]:  # Limit friends checked
            friend_posts = await self.posts.get_user_posts(
                friend_id,
                since=datetime.utcnow() - timedelta(days=7),
                limit=10
            )
            posts.extend(friend_posts)

        # Rank posts
        ranked = await self.ranker.rank(posts, user_id)

        return ranked[:limit]


class FeedRanker:
    """Ranks posts for personalized feed."""

    async def rank(
        self,
        posts: List[Post],
        user_id: str
    ) -> List[Post]:
        """Rank posts using engagement and relevance signals."""
        scored = []

        for post in posts:
            score = await self.calculate_score(post, user_id)
            scored.append((score, post))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [post for _, post in scored]

    async def calculate_score(
        self,
        post: Post,
        user_id: str
    ) -> float:
        """Calculate post score for a user."""
        score = 0.0

        # Engagement score
        score += post.like_count * 0.1
        score += post.comment_count * 0.3
        score += post.share_count * 0.5

        # Recency decay
        age_hours = (datetime.utcnow() - post.created_at).total_seconds() / 3600
        decay = 1 / (1 + age_hours / 24)  # Half-life of 24 hours
        score *= decay

        # Affinity to author
        affinity = await self.get_user_affinity(user_id, post.user_id)
        score *= (1 + affinity)

        # Content type boost
        if post.media_urls:
            score *= 1.2  # Boost posts with media

        return score

    async def get_user_affinity(
        self,
        user_id: str,
        author_id: str
    ) -> float:
        """Calculate affinity between user and author."""
        # Based on past interactions
        interactions = await self.get_interactions(user_id, author_id)

        affinity = 0.0
        affinity += interactions.get("likes", 0) * 0.1
        affinity += interactions.get("comments", 0) * 0.3
        affinity += interactions.get("messages", 0) * 0.5
        affinity += interactions.get("profile_views", 0) * 0.05

        return min(affinity, 2.0)  # Cap at 2x
```

#### 4. Feed Fanout Worker

```python
class FeedFanoutWorker:
    """Handles feed updates on new posts (push model for active users)."""

    async def process_post_created(self, event: dict):
        """Fanout new post to followers' feeds."""
        post_id = event["post_id"]
        author_id = event["user_id"]

        # Get followers
        followers = await self.graph.get_followers(author_id)

        # For celebrity accounts, use pull model
        if len(followers) > 10000:
            await self.mark_for_pull(author_id, post_id)
            return

        # Push to active followers' feeds
        active_followers = await self.filter_active(followers)

        pipe = self.redis.pipeline()
        for follower_id in active_followers:
            cache_key = f"feed:{follower_id}"
            pipe.lpush(cache_key, json.dumps({
                "post_id": post_id,
                "score": 100,  # High score for new posts
                "pushed_at": datetime.utcnow().isoformat()
            }))
            pipe.ltrim(cache_key, 0, 999)  # Keep last 1000

        await pipe.execute()
```

### Testing

```python
class TestSocialNetwork:
    async def test_create_post(self, client):
        """Test post creation."""
        response = await client.post("/api/v1/posts", json={
            "content": "Hello, world!",
            "visibility": "public"
        })

        assert response.status_code == 201
        assert response.json()["content"] == "Hello, world!"

    async def test_feed_generation(self, client):
        """Test feed contains friends' posts."""
        # Create friendship
        await client.post("/api/v1/friends", json={"friend_id": "friend1"})

        # Friend creates post
        await create_post_as("friend1", "Friend's post")

        # Check feed
        feed = await client.get("/api/v1/feed")
        posts = feed.json()["posts"]

        assert any(p["content"] == "Friend's post" for p in posts)

    async def test_feed_ranking(self, client):
        """Test that engaged posts rank higher."""
        # Create two posts
        post1 = await create_post_as("friend1", "Post 1")
        post2 = await create_post_as("friend1", "Post 2")

        # Add likes to post2
        for _ in range(10):
            await like_post(post2["id"])

        # Post2 should rank higher
        feed = await client.get("/api/v1/feed")
        posts = feed.json()["posts"]

        post2_idx = next(i for i, p in enumerate(posts) if p["id"] == post2["id"])
        post1_idx = next(i for i, p in enumerate(posts) if p["id"] == post1["id"])

        assert post2_idx < post1_idx

    async def test_friend_suggestions(self, client):
        """Test friend suggestions (friends of friends)."""
        suggestions = await client.get("/api/v1/friends/suggestions")

        assert len(suggestions.json()) > 0
        assert "mutual_friends" in suggestions.json()[0]
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Feed Generation | < 500ms |
| Post Creation | < 100ms |
| Fanout Latency | < 5 seconds |
| Feed Freshness | < 1 minute |
