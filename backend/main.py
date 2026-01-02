"""
Main FastAPI application entry point.
System Design Interview Platform API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sqlalchemy as sa
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import get_settings
from backend.database import engine, init_db
from backend.api import api_router
from backend.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from backend.middleware.audit_middleware import AuditMiddleware
from backend.websocket import websocket_router

settings = get_settings()


def seed_distributed_problems():
    """Seed distributed consensus problems if they don't exist."""
    from backend.database import SessionLocal
    from backend.models.problem import Problem, ProblemType

    # Define the 6 distributed problems with specific IDs
    # Using IDs 1-6 for distributed problems (assuming distributed problems are primary)
    DISTRIBUTED_PROBLEMS = [
        {
            "target_id": 1,
            "title": "Implement Raft Consensus",
            "description": "Implement the Raft consensus algorithm for leader election and log replication.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "consensus", "raft"],
        },
        {
            "target_id": 2,
            "title": "Implement Paxos Consensus",
            "description": "Implement the Multi-Paxos consensus algorithm.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "consensus", "paxos"],
        },
        {
            "target_id": 3,
            "title": "Implement Two-Phase Commit",
            "description": "Implement the Two-Phase Commit (2PC) protocol for distributed transactions.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "transactions", "2pc"],
        },
        {
            "target_id": 4,
            "title": "Implement Chandy-Lamport Snapshot",
            "description": "Implement the Chandy-Lamport distributed snapshot algorithm.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "snapshots", "chandy-lamport"],
        },
        {
            "target_id": 5,
            "title": "Implement Consistent Hashing",
            "description": "Implement consistent hashing with virtual nodes for distributed key-value storage.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "hashing", "consistent-hashing"],
        },
        {
            "target_id": 6,
            "title": "Implement Rendezvous Hashing",
            "description": "Implement rendezvous hashing (HRW) for distributed key-to-node mapping.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "hashing", "rendezvous-hashing"],
        },
        {
            "target_id": 7,
            "title": "Implement Token Bucket Rate Limiter",
            "description": "Implement a distributed token bucket rate limiter. Tokens are added at a fixed rate and consumed by requests.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "rate-limiting", "token-bucket"],
        },
        {
            "target_id": 8,
            "title": "Implement Leaky Bucket Rate Limiter",
            "description": "Implement a distributed leaky bucket rate limiter. Requests leak out at a constant rate.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "rate-limiting", "leaky-bucket"],
        },
        {
            "target_id": 9,
            "title": "Implement Fixed Window Counter Rate Limiter",
            "description": "Implement a distributed fixed window counter rate limiter. Count requests in fixed time windows.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "rate-limiting", "fixed-window"],
        },
        {
            "target_id": 10,
            "title": "Implement Sliding Window Log Rate Limiter",
            "description": "Implement a distributed sliding window log rate limiter. Track individual request timestamps.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "rate-limiting", "sliding-window"],
        },
        {
            "target_id": 11,
            "title": "Implement Sliding Window Counter Rate Limiter",
            "description": "Implement a distributed sliding window counter rate limiter. Weighted average of current and previous window.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "medium",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "rate-limiting", "sliding-window"],
        },
        {
            "target_id": 12,
            "title": "Implement Three-Phase Commit",
            "description": "Implement the Three-Phase Commit (3PC) protocol for distributed transactions with improved availability.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "transactions", "3pc"],
        },
        {
            "target_id": 13,
            "title": "Implement CRDTs",
            "description": "Implement Conflict-free Replicated Data Types (CRDTs) including G-Counter, PN-Counter, G-Set, and LWW-Register.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "eventual-consistency", "crdt"],
        },
        {
            "target_id": 14,
            "title": "Implement Log-Structured KV Store",
            "description": "Implement a distributed KV store with append-only log storage and compaction (Bitcask-style).",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "storage", "kv-store", "log-structured"],
        },
        {
            "target_id": 15,
            "title": "Implement LSM Tree KV Store",
            "description": "Implement a distributed KV store backed by LSM Tree with MemTable, WAL, SSTables, and compaction.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "storage", "kv-store", "lsm-tree"],
        },
        {
            "target_id": 16,
            "title": "Implement B+ Tree KV Store",
            "description": "Implement a distributed KV store backed by B+ Tree with buffer pool and page management.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "storage", "kv-store", "b-plus-tree"],
        },
        {
            "target_id": 17,
            "title": "Implement HNSW Index",
            "description": "Implement Hierarchical Navigable Small World (HNSW) graph for approximate nearest neighbor search. Build a multi-layer graph structure with efficient insertion, deletion, and k-NN search operations.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "vector-search", "ann", "graph-algorithms"],
        },
        {
            "target_id": 18,
            "title": "Implement Inverted File Index (IVF)",
            "description": "Implement an Inverted File Index for vector similarity search. Use k-means clustering to partition the vector space into cells, then search by probing the nearest clusters.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "vector-search", "clustering", "indexing"],
        },
        {
            "target_id": 19,
            "title": "Implement Product Quantization (PQ)",
            "description": "Implement Product Quantization for vector compression and efficient similarity search. Split vectors into subvectors, quantize each independently, and use lookup tables for fast distance computation.",
            "problem_type": ProblemType.DISTRIBUTED_CONSENSUS.value,
            "difficulty": "hard",
            "cluster_size": 3,
            "supported_languages": ["python", "go", "java", "cpp", "rust"],
            "tags": ["distributed-systems", "vector-search", "compression", "quantization"],
        },
    ]

    db = SessionLocal()
    try:
        for prob_data in DISTRIBUTED_PROBLEMS:
            target_id = prob_data.pop("target_id")
            existing = db.query(Problem).filter(Problem.id == target_id).first()

            if existing:
                # Update to distributed_consensus if it's a different type
                if existing.problem_type != ProblemType.DISTRIBUTED_CONSENSUS.value:
                    existing.title = prob_data["title"]
                    existing.description = prob_data["description"]
                    existing.problem_type = prob_data["problem_type"]
                    existing.difficulty = prob_data["difficulty"]
                    existing.cluster_size = prob_data["cluster_size"]
                    existing.supported_languages = prob_data["supported_languages"]
                    existing.tags = prob_data["tags"]
                    print(f"Updated problem {target_id} to: {prob_data['title']}")
            else:
                # Insert with specific ID using raw SQL
                from sqlalchemy import text
                from datetime import datetime
                db.execute(
                    text("""
                        INSERT INTO problems (id, title, description, problem_type, difficulty, cluster_size, supported_languages, tags, created_at)
                        VALUES (:id, :title, :description, :problem_type, :difficulty, :cluster_size, :supported_languages, :tags, :created_at)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": target_id,
                        "title": prob_data["title"],
                        "description": prob_data["description"],
                        "problem_type": prob_data["problem_type"],
                        "difficulty": prob_data["difficulty"],
                        "cluster_size": prob_data["cluster_size"],
                        "supported_languages": str(prob_data["supported_languages"]).replace("'", '"'),
                        "tags": str(prob_data["tags"]).replace("'", '"'),
                        "created_at": datetime.utcnow(),
                    }
                )
                print(f"Added distributed problem: {prob_data['title']} (ID: {target_id})")
        db.commit()
    except Exception as e:
        print(f"Error seeding distributed problems: {e}")
        db.rollback()
    finally:
        db.close()


def seed_system_design_problems():
    """Seed system design problems if they don't exist."""
    from backend.database import SessionLocal
    from backend.models.problem import Problem, ProblemType
    from datetime import datetime

    # System design problems with IDs starting from 101 to avoid conflicts
    SYSTEM_DESIGN_PROBLEMS = [
        {
            "target_id": 101,
            "title": "Design a URL Shortener",
            "description": """Design a URL shortening service like TinyURL or bit.ly.

## Requirements

### Functional Requirements
- Given a URL, generate a shorter and unique alias of it
- When users access a short link, redirect them to the original URL
- Users should optionally be able to pick a custom short link
- Links will expire after a default timespan

### Non-Functional Requirements
- The system should be highly available
- URL redirection should happen in real-time with minimal latency
- Shortened links should not be guessable (not predictable)

## Capacity Estimation
- 500 million URL shortenings per month
- 100:1 read to write ratio
- Assume each URL object is 500 bytes""",
            "difficulty": "medium",
            "tags": ["distributed-systems", "caching", "database"],
        },
        {
            "target_id": 102,
            "title": "Design a Rate Limiter",
            "description": """Design a rate limiting service that can be used to control the rate of traffic for APIs.

## Requirements

### Functional Requirements
- Limit the number of requests a client can make within a time window
- Support different rate limits for different APIs
- Return appropriate error responses when rate limit is exceeded
- Support distributed rate limiting across multiple servers

### Non-Functional Requirements
- Low latency (should not add significant delay to requests)
- High availability
- Accurate counting even in distributed environment

## Algorithms to Consider
- Token Bucket
- Leaking Bucket
- Fixed Window Counter
- Sliding Window Log
- Sliding Window Counter""",
            "difficulty": "medium",
            "tags": ["distributed-systems", "algorithms", "redis"],
        },
        {
            "target_id": 103,
            "title": "Design a Distributed Cache",
            "description": """Design a distributed caching system like Redis or Memcached.

## Requirements

### Functional Requirements
- Store key-value pairs with optional TTL
- Support GET, SET, DELETE operations
- Support atomic operations like INCR, DECR
- Handle cache invalidation

### Non-Functional Requirements
- Sub-millisecond latency for most operations
- High availability with replication
- Horizontal scalability
- Consistency guarantees (eventual or strong)

## Considerations
- Cache eviction policies (LRU, LFU, etc.)
- Data partitioning strategy
- Replication and failover
- Memory management

## Scale
- 1 million operations per second
- 100GB of cached data""",
            "difficulty": "hard",
            "tags": ["distributed-systems", "caching", "high-performance"],
        },
        {
            "target_id": 104,
            "title": "Design a Notification System",
            "description": """Design a notification service that can send notifications across multiple channels.

## Requirements

### Functional Requirements
- Support multiple notification channels (push, email, SMS, in-app)
- Allow users to set notification preferences
- Support scheduled notifications
- Handle notification templates
- Track delivery status and analytics

### Non-Functional Requirements
- High throughput (millions of notifications per day)
- Reliable delivery with retries
- Low latency for real-time notifications
- Scalable to handle traffic spikes

## Components to Design
- Notification service
- Channel adapters (push, email, SMS)
- User preference service
- Template engine
- Analytics pipeline""",
            "difficulty": "medium",
            "tags": ["messaging", "distributed-systems", "microservices"],
        },
        {
            "target_id": 105,
            "title": "Design a Search Autocomplete System",
            "description": """Design a real-time search autocomplete/typeahead system like Google Search suggestions.

## Requirements

### Functional Requirements
- Return top N suggestions based on prefix
- Suggestions should be ranked by popularity/relevance
- Support personalized suggestions
- Handle typos and fuzzy matching

### Non-Functional Requirements
- Response time under 100ms
- Support high query volume
- Update suggestions in near real-time based on search trends
- Handle international characters

## Data Characteristics
- 5 billion searches per day
- Average query length: 4 words
- Top 10 suggestions per query""",
            "difficulty": "hard",
            "tags": ["search", "data-structures", "real-time"],
        },
        {
            "target_id": 106,
            "title": "Design a File Sharing Service like Dropbox",
            "description": """Design a cloud file storage and synchronization service like Dropbox, Google Drive, or OneDrive.

## Requirements

### Functional Requirements
- Users can upload, download, and delete files
- Automatic synchronization across multiple devices
- File and folder sharing with other users (view/edit permissions)
- File versioning and revision history
- Support for large files (up to 50GB)
- Offline access and conflict resolution

### Non-Functional Requirements
- High availability (99.99% uptime)
- Low latency for file operations
- Strong consistency for metadata, eventual consistency for file content
- Secure storage with encryption at rest and in transit
- Scalable to billions of files

## Capacity Estimation
- 500 million users, 100 million DAU
- Average 200 files per user, average file size 1MB
- 2:1 read to write ratio
- Peak upload: 1 million files per minute

## Key Components to Design
- Block storage and deduplication
- Sync service and conflict resolution
- Metadata database
- Notification service for real-time updates
- CDN for downloads""",
            "difficulty": "hard",
            "tags": ["distributed-systems", "storage", "sync", "cdn"],
        },
        {
            "target_id": 107,
            "title": "Design a Video Streaming Service like YouTube",
            "description": """Design a video sharing and streaming platform like YouTube or Vimeo.

## Requirements

### Functional Requirements
- Upload videos (support various formats and sizes)
- Stream videos with adaptive bitrate
- Search and discover videos
- Like, comment, and subscribe functionality
- Video recommendations
- Live streaming support

### Non-Functional Requirements
- Support millions of concurrent viewers
- Low startup latency (<2 seconds)
- Smooth playback without buffering
- Global availability with low latency
- Support multiple video qualities (144p to 4K)

## Capacity Estimation
- 2 billion monthly active users
- 500 hours of video uploaded per minute
- Average video length: 10 minutes
- 80% of traffic is video streaming
- Peak concurrent viewers: 100 million

## Key Components to Design
- Video upload and processing pipeline
- Transcoding service (multiple resolutions/codecs)
- Content Delivery Network (CDN)
- Recommendation engine
- Comment and engagement system
- Analytics and monetization""",
            "difficulty": "hard",
            "tags": ["streaming", "cdn", "video-processing", "distributed-systems"],
        },
        {
            "target_id": 108,
            "title": "Design a Chat Application like WhatsApp",
            "description": """Design a real-time messaging application like WhatsApp, Telegram, or Signal.

## Requirements

### Functional Requirements
- One-on-one messaging
- Group chats (up to 1000 members)
- Media sharing (images, videos, documents)
- Message delivery and read receipts
- Online/offline status indicators
- End-to-end encryption
- Message search and history

### Non-Functional Requirements
- Real-time message delivery (<100ms latency)
- Message ordering guarantee
- Offline message support
- High availability (99.99% uptime)
- Support for billions of messages per day

## Capacity Estimation
- 2 billion users, 500 million DAU
- 100 billion messages per day
- Average message size: 100 bytes
- 20% of messages include media
- Peak: 50 million messages per second

## Key Components to Design
- Message queue and delivery system
- WebSocket connection management
- Message storage and retrieval
- Presence service (online status)
- Push notification service
- End-to-end encryption implementation
- Group messaging architecture""",
            "difficulty": "hard",
            "tags": ["real-time", "messaging", "websocket", "encryption"],
        },
        {
            "target_id": 109,
            "title": "Design a Realtime Gaming Leaderboard",
            "description": """Design a real-time leaderboard system for a massively multiplayer online game.

## Requirements

### Functional Requirements
- Real-time score updates and ranking
- Global leaderboard (top N players)
- Regional/country-specific leaderboards
- Friends leaderboard
- Historical leaderboards (daily, weekly, monthly, all-time)
- Player rank lookup (find my position)
- Anti-cheat score validation

### Non-Functional Requirements
- Sub-second leaderboard updates
- Handle millions of concurrent players
- Accurate ranking even under high concurrency
- Low latency for rank queries (<50ms)
- Support for multiple games/modes

## Capacity Estimation
- 100 million active players
- 1 million concurrent players at peak
- 10,000 score updates per second
- Leaderboard size: top 1 million players
- Query volume: 100,000 rank lookups per second

## Key Components to Design
- Real-time ranking algorithm
- Score ingestion and validation pipeline
- Caching layer for top ranks
- Sharding strategy for global scale
- Historical data archival
- Anti-cheat detection system""",
            "difficulty": "medium",
            "tags": ["real-time", "ranking", "gaming", "caching"],
        },
        {
            "target_id": 110,
            "title": "Design a Distributed Web Crawler",
            "description": """Design a web crawler that can crawl the entire web efficiently.

## Requirements

### Functional Requirements
- Discover and download web pages
- Extract and follow links
- Handle various content types (HTML, PDF, images)
- Respect robots.txt and crawl-delay
- Detect and handle duplicate content
- Support incremental/continuous crawling

### Non-Functional Requirements
- Crawl billions of pages
- Politeness (don't overload websites)
- Freshness (re-crawl updated content)
- Fault tolerance and resumability
- Scalable to thousands of crawlers

## Capacity Estimation
- 15 billion web pages to crawl
- Target: 1 billion pages per month
- Average page size: 100KB
- 1,000 crawler instances
- Storage: 1PB+ for raw content

## Key Components to Design
- URL Frontier (priority queue)
- DNS resolver with caching
- Content fetcher (HTTP client pool)
- Content parser and link extractor
- Duplicate detection (URL and content)
- Distributed coordination
- Storage system for crawled content
- Monitoring and analytics""",
            "difficulty": "hard",
            "tags": ["distributed-systems", "crawling", "big-data", "scheduling"],
        },
        {
            "target_id": 111,
            "title": "Design a Stock Trading Application like Robinhood",
            "description": """Design a stock trading platform that enables users to buy and sell stocks in real-time.

## Requirements

### Functional Requirements
- User account and portfolio management
- Real-time stock price updates
- Buy and sell orders (market, limit, stop-loss)
- Order matching and execution
- Transaction history and statements
- Watchlists and price alerts
- Support for stocks, ETFs, options, and crypto

### Non-Functional Requirements
- Order execution latency <10ms
- Real-time price updates (<100ms delay)
- High availability (99.999% for trading hours)
- Strong consistency for transactions
- Regulatory compliance (SEC, FINRA)
- Fraud detection and prevention

## Capacity Estimation
- 20 million users, 5 million DAU
- 10 million trades per day
- 100,000 concurrent active traders
- 10,000 price updates per second
- Peak trading: 1 million orders per hour

## Key Components to Design
- Order management system
- Order matching engine
- Real-time price feed ingestion
- Portfolio and position tracking
- Settlement and clearing
- Market data distribution
- Risk management system
- Regulatory reporting""",
            "difficulty": "hard",
            "tags": ["fintech", "real-time", "trading", "high-availability"],
        },
        {
            "target_id": 112,
            "title": "Design a Location-Based Service like Google Maps",
            "description": """Design a comprehensive mapping and navigation service like Google Maps, Apple Maps, or Waze.

## Requirements

### Functional Requirements
- Display interactive maps with multiple zoom levels
- Search for places, addresses, and points of interest
- Calculate routes with turn-by-turn navigation
- Real-time traffic updates and rerouting
- Street View imagery
- Offline maps support
- User reviews and ratings for places

### Non-Functional Requirements
- Sub-second map tile loading
- Route calculation <2 seconds for typical routes
- Real-time traffic updates (<1 minute delay)
- Global coverage with local accuracy
- Handle billions of location queries per day
- Battery-efficient mobile experience

## Capacity Estimation
- 1 billion monthly active users
- 100 million navigation sessions per day
- 10 billion location searches per month
- 500TB of map tile data
- 1 million traffic updates per minute

## Key Components to Design
- Map tile rendering and serving (vector/raster)
- Geocoding and reverse geocoding service
- Routing engine (Dijkstra/A* on road graph)
- Real-time traffic data ingestion
- Places database and search
- ETA prediction system
- Offline data packaging
- Location data collection and processing""",
            "difficulty": "hard",
            "tags": ["geospatial", "real-time", "routing", "distributed-systems"],
        },
        {
            "target_id": 113,
            "title": "Design a Chatbot System like ChatGPT",
            "description": """Design a large-scale conversational AI system like ChatGPT, Claude, or Gemini.

## Requirements

### Functional Requirements
- Natural language conversation with context retention
- Multi-turn dialogue with conversation history
- Support for multiple languages
- Code generation and execution
- File upload and analysis
- Web browsing capabilities
- Custom instructions/system prompts
- Conversation sharing and export

### Non-Functional Requirements
- Response latency <5 seconds for first token
- Support streaming responses
- Handle millions of concurrent users
- Rate limiting and fair usage policies
- Content moderation and safety filters
- 99.9% availability
- Cost-efficient inference

## Capacity Estimation
- 100 million weekly active users
- 1 billion messages per day
- Average conversation: 10 turns
- Average input: 100 tokens, output: 500 tokens
- Peak: 1 million concurrent sessions
- Model size: 100B+ parameters

## Key Components to Design
- LLM inference infrastructure (GPU clusters)
- Request routing and load balancing
- Conversation context management
- Token streaming service
- Rate limiting and quota management
- Content safety and moderation pipeline
- Model versioning and A/B testing
- User session and history storage
- Prompt caching for efficiency""",
            "difficulty": "hard",
            "tags": ["ai-ml", "real-time", "streaming", "high-availability"],
        },
        {
            "target_id": 114,
            "title": "Design a Retrieval Augmented Generation (RAG) System",
            "description": """Design a production RAG system that enables LLMs to answer questions using custom knowledge bases.

## Requirements

### Functional Requirements
- Document ingestion (PDF, HTML, Markdown, etc.)
- Automatic document chunking and processing
- Vector embedding generation and storage
- Semantic search across documents
- Context-aware answer generation
- Source citation and attribution
- Knowledge base management (CRUD)
- Multi-tenant support

### Non-Functional Requirements
- Query latency <3 seconds end-to-end
- High retrieval accuracy (>90% relevance)
- Support billions of document chunks
- Real-time document updates
- Scalable to thousands of knowledge bases
- Cost-efficient embedding and inference

## Capacity Estimation
- 10,000 organizations, 1 million users
- 100 million documents indexed
- 1 billion document chunks
- 10 million queries per day
- Vector dimension: 1536 (OpenAI) or 768 (open source)
- Average 5 chunks retrieved per query

## Key Components to Design
- Document ingestion pipeline
- Chunking strategies (fixed, semantic, recursive)
- Embedding service (batch and real-time)
- Vector database (HNSW, IVF indexes)
- Retrieval and reranking pipeline
- Context assembly and prompt construction
- LLM integration for generation
- Caching layer (query, embedding, response)
- Evaluation and monitoring system""",
            "difficulty": "hard",
            "tags": ["ai-ml", "search", "vector-database", "distributed-systems"],
        },
        {
            "target_id": 115,
            "title": "Design a Ride Sharing Service like Uber",
            "description": """Design a ride-sharing platform that connects drivers and riders in real-time.

## Requirements

### Functional Requirements
- User registration (riders and drivers)
- Real-time ride matching
- Dynamic pricing based on demand
- Live driver/ride tracking
- Multiple ride types (economy, premium, pool)
- In-app payments and receipts
- Driver/rider ratings and reviews
- Trip history and receipts

### Non-Functional Requirements
- Matching latency <10 seconds
- Location updates every 3-5 seconds
- 99.99% availability in active markets
- Handle millions of concurrent rides
- Accurate ETA predictions
- Fraud detection and prevention

## Capacity Estimation
- 100 million riders, 5 million drivers
- 20 million rides per day
- 1 million concurrent active rides at peak
- 100 million location updates per minute
- 50 million pricing calculations per day
- 200 cities across 60 countries

## Key Components to Design
- Geospatial matching service
- Supply/demand prediction and pricing
- Real-time location tracking service
- ETA and route optimization engine
- Payment processing system
- Driver dispatch algorithm
- Surge pricing engine
- Trip state machine
- Notification service""",
            "difficulty": "hard",
            "tags": ["geospatial", "real-time", "matching", "distributed-systems"],
        },
        {
            "target_id": 116,
            "title": "Design a Social Network like Facebook",
            "description": """Design a large-scale social networking platform with billions of users.

## Requirements

### Functional Requirements
- User profiles and friend connections
- News feed with personalized content
- Post creation (text, images, videos, links)
- Comments, likes, and reactions
- Friend suggestions and people search
- Groups and pages
- Messenger/chat integration
- Notifications (push, email, in-app)
- Privacy controls and settings

### Non-Functional Requirements
- News feed generation <500ms
- Support billions of users globally
- Handle millions of posts per minute
- Real-time notifications
- 99.99% availability
- Strong privacy and data protection
- Content moderation at scale

## Capacity Estimation
- 3 billion monthly active users
- 2 billion daily active users
- 1 billion posts per day
- 10 billion likes per day
- 500 million friend connections per day
- 100PB+ of user-generated content
- Average 300 friends per user

## Key Components to Design
- Social graph storage and querying
- News feed generation (push vs pull)
- Content storage and CDN
- Post ranking algorithm
- Real-time notification system
- Search service (people, posts, pages)
- Privacy and access control layer
- Content moderation pipeline
- Ads targeting and delivery
- Analytics and insights platform""",
            "difficulty": "hard",
            "tags": ["social-network", "graph", "feed-ranking", "distributed-systems"],
        },
    ]

    db = SessionLocal()
    try:
        for prob_data in SYSTEM_DESIGN_PROBLEMS:
            target_id = prob_data.pop("target_id")
            existing = db.query(Problem).filter(Problem.id == target_id).first()

            if not existing:
                from sqlalchemy import text
                db.execute(
                    text("""
                        INSERT INTO problems (id, title, description, problem_type, difficulty, tags, created_at)
                        VALUES (:id, :title, :description, :problem_type, :difficulty, :tags, :created_at)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    {
                        "id": target_id,
                        "title": prob_data["title"],
                        "description": prob_data["description"],
                        "problem_type": ProblemType.SYSTEM_DESIGN.value,
                        "difficulty": prob_data["difficulty"],
                        "tags": str(prob_data["tags"]).replace("'", '"'),
                        "created_at": datetime.utcnow(),
                    }
                )
                print(f"Added system design problem: {prob_data['title']} (ID: {target_id})")
        db.commit()
    except Exception as e:
        print(f"Error seeding system design problems: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Verifies database connection on startup.

    Note: Database schema is managed by Alembic migrations.
    Run 'alembic upgrade head' to apply migrations.
    """
    import time
    max_retries = 5
    for i in range(max_retries):
        try:
            # Verify database connection
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            print("Database connection verified successfully")
            # Create tables if they don't exist
            init_db()
            print("Database tables initialized")
            # Seed distributed problems
            seed_distributed_problems()
            print("Distributed problems seeded")
            # Seed system design problems
            seed_system_design_problems()
            print("System design problems seeded")
            break
        except Exception as e:
            if i < max_retries - 1:
                print(f"Database connection failed (attempt {i+1}/{max_retries}): {e}")
                time.sleep(2)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                print("Run 'alembic upgrade head' to create/update database schema")
    yield
    # Cleanup on shutdown (if needed)


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
    A LeetCode-like platform for system design problems.

    Features:
    - Submit system design solutions (schema, API spec, design description)
    - AI-powered validation using Claude
    - Automatic infrastructure deployment to GCP
    - Functional, performance, and chaos testing
    - Detailed feedback and scoring

    ## Authentication
    All protected endpoints require a Bearer token obtained via Google OAuth.
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS - build origins list dynamically
cors_origins = [
    settings.frontend_url,
]

# Add localhost origins for development
if settings.debug:
    cors_origins.extend([
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ])

# Remove duplicates and empty strings
cors_origins = list(set(origin for origin in cors_origins if origin))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add audit middleware for logging user actions
app.add_middleware(AuditMiddleware)

# Include API routes
app.include_router(api_router)

# Include WebSocket routes
app.include_router(websocket_router)


@app.get("/")
async def root():
    """Root endpoint - basic health check."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
    )
