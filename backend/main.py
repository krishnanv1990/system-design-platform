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
