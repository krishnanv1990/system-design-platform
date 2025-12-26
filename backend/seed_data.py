"""
Seed data for initial problems.
Run this script to populate the database with sample problems.
"""

import sys
sys.path.insert(0, '.')

from backend.database import SessionLocal, engine, Base
from backend.models.problem import Problem

# Create tables
Base.metadata.create_all(bind=engine)

# Sample problems
PROBLEMS = [
    {
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
- Assume each URL object is 500 bytes

## Example
- Input: https://www.example.com/very/long/path/to/resource?with=many&query=params
- Output: https://short.url/abc123
""",
        "difficulty": "medium",
        "expected_schema": {
            "required_tables": ["urls", "users"]
        },
        "expected_api_spec": {
            "required_endpoints": [
                "POST /api/v1/urls",
                "GET /api/v1/urls/{short_code}"
            ]
        },
        "validation_rules": {
            "must_include": ["database", "caching", "load balancer"],
            "should_discuss": ["sharding", "replication", "rate limiting"]
        },
        "hints": [
            "Consider using Base62 encoding for short URLs",
            "Think about how to handle collisions",
            "Caching can significantly improve read performance"
        ],
        "tags": ["distributed-systems", "caching", "database"]
    },
    {
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
- Sliding Window Counter

## Example
- Allow 100 requests per minute per user
- Allow 1000 requests per hour per API key
""",
        "difficulty": "medium",
        "expected_schema": {
            "required_tables": ["rate_limits", "request_logs"]
        },
        "expected_api_spec": {
            "required_endpoints": [
                "POST /api/v1/check-rate-limit",
                "GET /api/v1/rate-limit-status"
            ]
        },
        "hints": [
            "Redis is commonly used for distributed rate limiting",
            "Consider the trade-offs between accuracy and performance",
            "Think about race conditions in a distributed environment"
        ],
        "tags": ["distributed-systems", "algorithms", "redis"]
    },
    {
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
- 100GB of cached data
""",
        "difficulty": "hard",
        "expected_schema": {},
        "expected_api_spec": {
            "required_endpoints": [
                "GET /api/v1/cache/{key}",
                "PUT /api/v1/cache/{key}",
                "DELETE /api/v1/cache/{key}"
            ]
        },
        "hints": [
            "Consistent hashing is key for distributed caching",
            "Consider read and write paths separately",
            "Think about hot key problems"
        ],
        "tags": ["distributed-systems", "caching", "high-performance"]
    },
    {
        "title": "Design a Notification System",
        "description": """Design a notification service that can send notifications across multiple channels (push, email, SMS).

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
- Analytics pipeline
""",
        "difficulty": "medium",
        "expected_schema": {
            "required_tables": ["notifications", "user_preferences", "templates"]
        },
        "expected_api_spec": {
            "required_endpoints": [
                "POST /api/v1/notifications",
                "GET /api/v1/notifications/{id}",
                "PUT /api/v1/preferences"
            ]
        },
        "hints": [
            "Consider using message queues for reliability",
            "Think about priority levels for different notifications",
            "Handle rate limiting for external providers"
        ],
        "tags": ["messaging", "distributed-systems", "microservices"]
    },
    {
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
- Top 10 suggestions per query
""",
        "difficulty": "hard",
        "expected_schema": {},
        "expected_api_spec": {
            "required_endpoints": [
                "GET /api/v1/suggestions?prefix={prefix}"
            ]
        },
        "hints": [
            "Trie data structure is commonly used",
            "Consider caching popular prefixes",
            "Think about how to aggregate and update rankings"
        ],
        "tags": ["search", "data-structures", "real-time"]
    }
]


def seed_problems():
    """Insert sample problems into the database."""
    db = SessionLocal()
    try:
        # Check if problems already exist
        existing = db.query(Problem).count()
        if existing > 0:
            print(f"Database already has {existing} problems. Skipping seed.")
            return

        for problem_data in PROBLEMS:
            problem = Problem(**problem_data)
            db.add(problem)

        db.commit()
        print(f"Successfully seeded {len(PROBLEMS)} problems.")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_problems()
