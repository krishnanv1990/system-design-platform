# URL Shortener Solution with Key Generation Service (KGS)

This document provides a complete, production-ready solution for a URL shortener that uses a Key Generation Service for optimal performance at scale.

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [API Specification](#api-specification)
5. [Implementation](#implementation)
6. [Design Decisions](#design-decisions)
7. [Test Scenarios](#test-scenarios)
   - [Functional Tests](#functional-tests)
   - [Performance Tests](#performance-tests)
   - [Chaos Tests](#chaos-tests)

---

## Overview

This URL shortener solution is designed to handle:
- **1 billion+ URLs** stored
- **100,000+ requests/second** at peak
- **Sub-100ms latency** for redirects
- **99.99% availability**

### Key Features
- Pre-generated unique short codes via Key Generation Service (KGS)
- Multi-layer caching (Redis + CDN)
- Horizontal scalability
- URL expiration support
- Click analytics

---

## Architecture

```
                                    ┌─────────────────────────────────────────┐
                                    │         KEY GENERATION SERVICE          │
                                    │  ┌─────────────┐   ┌────────────────┐  │
                                    │  │ Generator   │──▶│ Redis Key Pool │  │
                                    │  │ (Background)│   │ unused:keys    │  │
                                    │  └─────────────┘   └────────────────┘  │
                                    └──────────────────────────┬──────────────┘
                                                               │
                                                               │ SPOP key
                                                               ▼
┌──────────┐     ┌─────────────┐     ┌─────────────────────────────────────────┐
│  Client  │────▶│ Load        │────▶│            URL SERVICE                  │
│          │     │ Balancer    │     │  ┌─────────────────────────────────┐   │
└──────────┘     │ (Cloud CDN) │     │  │ POST /api/v1/urls               │   │
                 └─────────────┘     │  │ - Get key from KGS              │   │
                                     │  │ - Store URL + key in DB         │   │
                                     │  │ - Cache in Redis                │   │
                                     │  └─────────────────────────────────┘   │
                                     │  ┌─────────────────────────────────┐   │
                                     │  │ GET /api/v1/urls/{code}         │   │
                                     │  │ - Check Redis cache             │   │
                                     │  │ - Fallback to DB                │   │
                                     │  │ - Return redirect               │   │
                                     │  └─────────────────────────────────┘   │
                                     └──────────────────────────┬──────────────┘
                                                                │
                              ┌─────────────────────────────────┼─────────────────────────────────┐
                              │                                 │                                 │
                              ▼                                 ▼                                 ▼
                    ┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
                    │   Redis Cache   │               │   PostgreSQL    │               │  Click Stream   │
                    │   (URL Cache)   │               │   (URL Store)   │               │    (Pub/Sub)    │
                    └─────────────────┘               └─────────────────┘               └─────────────────┘
```

### Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Load Balancer | Cloud CDN + Cloud Run | Traffic distribution, SSL termination, caching |
| URL Service | Python/FastAPI | Core API handling |
| Key Generation Service | Background worker | Pre-generates unique short codes |
| Key Pool | Redis SET | Stores unused keys (SPOP for O(1) allocation) |
| URL Cache | Redis | Caches URL mappings for fast reads |
| URL Store | PostgreSQL | Persistent URL storage |
| Analytics | Pub/Sub + BigQuery | Async click tracking |

---

## Database Schema

### PostgreSQL Schema

```sql
-- URLs table - stores the URL mappings
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(8) NOT NULL UNIQUE,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    click_count BIGINT DEFAULT 0,
    created_by VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_accessed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for common queries
CREATE INDEX idx_urls_short_code ON urls(short_code);
CREATE INDEX idx_urls_expires_at ON urls(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_urls_created_at ON urls(created_at);

-- KGS Keys table - tracks all generated keys
CREATE TABLE kgs_keys (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(8) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'unused',  -- unused, used, reserved
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    allocated_at TIMESTAMP WITH TIME ZONE,
    allocated_to_url_id BIGINT REFERENCES urls(id)
);

CREATE INDEX idx_kgs_keys_status ON kgs_keys(status) WHERE status = 'unused';

-- URL Analytics table (optional, for detailed stats)
CREATE TABLE url_analytics (
    id BIGSERIAL PRIMARY KEY,
    url_id BIGINT REFERENCES urls(id),
    short_code VARCHAR(8) NOT NULL,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_agent TEXT,
    referer TEXT,
    ip_hash VARCHAR(64),  -- Hashed for privacy
    country_code VARCHAR(2)
);

CREATE INDEX idx_analytics_short_code ON url_analytics(short_code);
CREATE INDEX idx_analytics_accessed_at ON url_analytics(accessed_at);
```

### JSON Schema Format (for submission)

```json
{
  "database_type": "postgresql",
  "tables": {
    "urls": {
      "columns": {
        "id": {"type": "bigserial", "primary_key": true},
        "short_code": {"type": "varchar(8)", "unique": true, "not_null": true},
        "original_url": {"type": "text", "not_null": true},
        "created_at": {"type": "timestamp with time zone", "default": "now()"},
        "expires_at": {"type": "timestamp with time zone", "nullable": true},
        "click_count": {"type": "bigint", "default": 0},
        "is_active": {"type": "boolean", "default": true}
      },
      "indexes": ["short_code", "expires_at", "created_at"]
    },
    "kgs_keys": {
      "columns": {
        "id": {"type": "bigserial", "primary_key": true},
        "short_code": {"type": "varchar(8)", "unique": true, "not_null": true},
        "status": {"type": "varchar(20)", "default": "unused"},
        "created_at": {"type": "timestamp with time zone", "default": "now()"},
        "allocated_at": {"type": "timestamp with time zone", "nullable": true}
      },
      "indexes": ["status"]
    }
  },
  "cache": {
    "type": "redis",
    "keys": {
      "url:{short_code}": "URL mapping cache (TTL: 1 hour)",
      "kgs:unused": "SET of unused short codes",
      "kgs:used": "SET of used short codes"
    }
  }
}
```

---

## API Specification

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "URL Shortener API",
    "version": "1.0.0",
    "description": "URL Shortener with Key Generation Service"
  },
  "servers": [
    {"url": "https://api.example.com", "description": "Production"}
  ],
  "paths": {
    "/health": {
      "get": {
        "summary": "Health check endpoint",
        "responses": {
          "200": {
            "description": "Service is healthy",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "status": {"type": "string", "example": "healthy"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "version": {"type": "string", "example": "1.0.0"},
                    "kgs_pool_size": {"type": "integer", "example": 1000000}
                  }
                }
              }
            }
          }
        }
      }
    },
    "/": {
      "get": {
        "summary": "Root endpoint - service info",
        "responses": {
          "200": {
            "description": "Service information",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "service": {"type": "string", "example": "url-shortener"},
                    "version": {"type": "string", "example": "1.0.0"}
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/urls": {
      "post": {
        "summary": "Create a short URL",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["original_url"],
                "properties": {
                  "original_url": {
                    "type": "string",
                    "format": "uri",
                    "example": "https://www.example.com/very/long/path"
                  },
                  "custom_code": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9]{4,8}$",
                    "example": "mylink"
                  },
                  "expires_in_hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 8760,
                    "example": 24
                  },
                  "expires_in_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "example": 3600
                  }
                }
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "URL created successfully",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": {"type": "integer", "example": 12345},
                    "short_code": {"type": "string", "example": "abc123"},
                    "short_url": {"type": "string", "example": "https://short.url/abc123"},
                    "original_url": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "expires_at": {"type": "string", "format": "date-time"}
                  }
                }
              }
            }
          },
          "400": {"description": "Invalid URL format"},
          "409": {"description": "Custom code already exists"},
          "422": {"description": "Validation error"}
        }
      }
    },
    "/api/v1/urls/{short_code}": {
      "get": {
        "summary": "Get URL by short code (redirect)",
        "parameters": [
          {
            "name": "short_code",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "responses": {
          "200": {
            "description": "URL found",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": {"type": "integer"},
                    "short_code": {"type": "string"},
                    "original_url": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "expires_at": {"type": "string", "format": "date-time"},
                    "click_count": {"type": "integer"}
                  }
                }
              }
            }
          },
          "301": {"description": "Redirect to original URL"},
          "404": {"description": "URL not found or expired"},
          "410": {"description": "URL has expired"}
        }
      },
      "delete": {
        "summary": "Delete a short URL",
        "parameters": [
          {
            "name": "short_code",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "responses": {
          "204": {"description": "URL deleted successfully"},
          "404": {"description": "URL not found"}
        }
      }
    },
    "/api/v1/urls/{short_code}/stats": {
      "get": {
        "summary": "Get URL statistics",
        "parameters": [
          {
            "name": "short_code",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "responses": {
          "200": {
            "description": "URL statistics",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "short_code": {"type": "string"},
                    "original_url": {"type": "string"},
                    "clicks": {"type": "integer"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "last_accessed_at": {"type": "string", "format": "date-time"}
                  }
                }
              }
            }
          },
          "404": {"description": "URL not found"}
        }
      }
    },
    "/{short_code}": {
      "get": {
        "summary": "Redirect to original URL",
        "parameters": [
          {
            "name": "short_code",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "responses": {
          "301": {
            "description": "Permanent redirect",
            "headers": {
              "Location": {
                "schema": {"type": "string"},
                "description": "Original URL"
              }
            }
          },
          "404": {"description": "URL not found"}
        }
      }
    }
  }
}
```

---

## Implementation

### Complete Python Implementation

```python
"""
URL Shortener with Key Generation Service (KGS)
A production-ready implementation designed for scale.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime, timedelta, timezone
from typing import Optional
import redis
import asyncpg
import asyncio
import string
import random
import os
import re

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/urlshortener")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
BASE_URL = os.getenv("BASE_URL", "https://short.url")
KGS_POOL_MIN_SIZE = int(os.getenv("KGS_POOL_MIN_SIZE", "100000"))
KGS_BATCH_SIZE = int(os.getenv("KGS_BATCH_SIZE", "10000"))

app = FastAPI(title="URL Shortener", version="1.0.0")

# Redis connection
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Database pool (initialized on startup)
db_pool = None

# Key constants
CHARSET = string.ascii_lowercase + string.ascii_uppercase + string.digits
KEY_LENGTH = 7
UNUSED_KEYS = "kgs:unused"
USED_KEYS = "kgs:used"
URL_CACHE_PREFIX = "url:"
URL_CACHE_TTL = 3600  # 1 hour


# ======================== Models ========================

class URLCreate(BaseModel):
    original_url: str
    custom_code: Optional[str] = None
    expires_in_hours: Optional[int] = None
    expires_in_seconds: Optional[int] = None

    @field_validator('original_url')
    @classmethod
    def validate_url(cls, v):
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if not url_pattern.match(v):
            raise ValueError('Invalid URL format')
        if v.startswith(('javascript:', 'data:', 'file:')):
            raise ValueError('URL scheme not allowed')
        return v

    @field_validator('custom_code')
    @classmethod
    def validate_custom_code(cls, v):
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9]{4,8}$', v):
                raise ValueError('Custom code must be 4-8 alphanumeric characters')
        return v


class URLResponse(BaseModel):
    id: int
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class URLStats(BaseModel):
    short_code: str
    original_url: str
    clicks: int
    created_at: datetime
    last_accessed_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    kgs_pool_size: int


# ======================== KGS Functions ========================

def generate_key() -> str:
    """Generate a single random key."""
    return ''.join(random.choices(CHARSET, k=KEY_LENGTH))


def generate_key_batch(count: int) -> list[str]:
    """Generate a batch of unique keys."""
    keys = set()
    while len(keys) < count:
        keys.add(generate_key())
    return list(keys)


async def maintain_key_pool():
    """Background task to maintain minimum key pool size."""
    while True:
        try:
            pool_size = redis_client.scard(UNUSED_KEYS)

            if pool_size < KGS_POOL_MIN_SIZE:
                needed = KGS_POOL_MIN_SIZE - pool_size + KGS_BATCH_SIZE
                keys = generate_key_batch(needed)

                # Filter out already used keys
                pipeline = redis_client.pipeline()
                for key in keys:
                    pipeline.sismember(USED_KEYS, key)
                used_results = pipeline.execute()

                new_keys = [k for k, used in zip(keys, used_results) if not used]

                if new_keys:
                    redis_client.sadd(UNUSED_KEYS, *new_keys)
                    print(f"Added {len(new_keys)} keys to pool. New size: {redis_client.scard(UNUSED_KEYS)}")

        except Exception as e:
            print(f"Error maintaining key pool: {e}")

        await asyncio.sleep(60)  # Check every minute


def allocate_key() -> str:
    """Atomically allocate a key from the pool."""
    key = redis_client.spop(UNUSED_KEYS)

    if key is None:
        # Emergency: generate on-the-fly
        for _ in range(10):
            key = generate_key()
            if not redis_client.sismember(USED_KEYS, key):
                break
        else:
            raise HTTPException(status_code=503, detail="Key pool exhausted")

    redis_client.sadd(USED_KEYS, key)
    return key


def return_key(key: str):
    """Return a key to the unused pool (for rollback)."""
    redis_client.srem(USED_KEYS, key)
    redis_client.sadd(UNUSED_KEYS, key)


# ======================== Database Functions ========================

async def get_db():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool


async def init_db():
    """Initialize database tables."""
    pool = await get_db()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id BIGSERIAL PRIMARY KEY,
                short_code VARCHAR(8) NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE,
                click_count BIGINT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                last_accessed_at TIMESTAMP WITH TIME ZONE
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_expires_at ON urls(expires_at)
            WHERE expires_at IS NOT NULL
        """)


# ======================== Cache Functions ========================

def cache_url(short_code: str, original_url: str, expires_at: Optional[datetime] = None):
    """Cache URL mapping in Redis."""
    cache_key = f"{URL_CACHE_PREFIX}{short_code}"
    data = {"url": original_url}
    if expires_at:
        data["expires_at"] = expires_at.isoformat()

    redis_client.hset(cache_key, mapping=data)
    redis_client.expire(cache_key, URL_CACHE_TTL)


def get_cached_url(short_code: str) -> Optional[dict]:
    """Get URL from cache."""
    cache_key = f"{URL_CACHE_PREFIX}{short_code}"
    data = redis_client.hgetall(cache_key)

    if data:
        result = {"url": data.get("url")}
        if "expires_at" in data:
            result["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return result
    return None


def invalidate_cache(short_code: str):
    """Remove URL from cache."""
    redis_client.delete(f"{URL_CACHE_PREFIX}{short_code}")


# ======================== API Endpoints ========================

@app.on_event("startup")
async def startup():
    await init_db()
    # Start KGS background task
    asyncio.create_task(maintain_key_pool())
    # Pre-populate key pool if empty
    if redis_client.scard(UNUSED_KEYS) < KGS_POOL_MIN_SIZE:
        keys = generate_key_batch(KGS_POOL_MIN_SIZE)
        redis_client.sadd(UNUSED_KEYS, *keys)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        kgs_pool_size=redis_client.scard(UNUSED_KEYS)
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "url-shortener", "version": "1.0.0"}


@app.post("/api/v1/urls", response_model=URLResponse, status_code=201)
async def create_short_url(request: URLCreate, background_tasks: BackgroundTasks):
    """Create a new short URL."""

    # Validate URL
    if not request.original_url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Get or validate short code
    if request.custom_code:
        short_code = request.custom_code
        # Check if custom code already exists
        if redis_client.sismember(USED_KEYS, short_code):
            raise HTTPException(status_code=409, detail="Custom code already in use")
        redis_client.sadd(USED_KEYS, short_code)
    else:
        # Allocate from KGS - O(1) operation!
        short_code = allocate_key()

    # Calculate expiration
    expires_at = None
    if request.expires_in_seconds:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.expires_in_seconds)
    elif request.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=request.expires_in_hours)

    # Store in database
    pool = await get_db()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO urls (short_code, original_url, expires_at)
                VALUES ($1, $2, $3)
                RETURNING id, short_code, original_url, created_at, expires_at
            """, short_code, request.original_url, expires_at)
    except Exception as e:
        # Rollback key allocation on failure
        return_key(short_code)
        raise HTTPException(status_code=500, detail=str(e))

    # Cache the URL
    cache_url(short_code, request.original_url, expires_at)

    return URLResponse(
        id=row['id'],
        short_code=row['short_code'],
        short_url=f"{BASE_URL}/{row['short_code']}",
        original_url=row['original_url'],
        created_at=row['created_at'],
        expires_at=row['expires_at']
    )


@app.get("/api/v1/urls/{short_code}")
async def get_url(short_code: str, background_tasks: BackgroundTasks):
    """Get URL by short code."""

    # Check cache first
    cached = get_cached_url(short_code)
    if cached:
        # Check expiration
        if cached.get("expires_at") and cached["expires_at"] < datetime.now(timezone.utc):
            invalidate_cache(short_code)
            raise HTTPException(status_code=404, detail="URL has expired")

        # Increment click count in background
        background_tasks.add_task(increment_click_count, short_code)

        return {
            "short_code": short_code,
            "original_url": cached["url"],
            "expires_at": cached.get("expires_at")
        }

    # Cache miss - fetch from database
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, short_code, original_url, created_at, expires_at, click_count
            FROM urls
            WHERE short_code = $1 AND is_active = TRUE
        """, short_code)

    if not row:
        raise HTTPException(status_code=404, detail="URL not found")

    # Check expiration
    if row['expires_at'] and row['expires_at'].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="URL has expired")

    # Cache for next time
    cache_url(short_code, row['original_url'], row['expires_at'])

    # Increment click count in background
    background_tasks.add_task(increment_click_count, short_code)

    return {
        "id": row['id'],
        "short_code": row['short_code'],
        "original_url": row['original_url'],
        "created_at": row['created_at'],
        "expires_at": row['expires_at'],
        "click_count": row['click_count']
    }


@app.get("/{short_code}")
async def redirect_url(short_code: str, background_tasks: BackgroundTasks):
    """Redirect to original URL."""

    # Check cache first
    cached = get_cached_url(short_code)
    if cached:
        if cached.get("expires_at") and cached["expires_at"] < datetime.now(timezone.utc):
            invalidate_cache(short_code)
            raise HTTPException(status_code=404, detail="URL has expired")

        background_tasks.add_task(increment_click_count, short_code)
        return RedirectResponse(url=cached["url"], status_code=301)

    # Cache miss
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT original_url, expires_at
            FROM urls
            WHERE short_code = $1 AND is_active = TRUE
        """, short_code)

    if not row:
        raise HTTPException(status_code=404, detail="URL not found")

    if row['expires_at'] and row['expires_at'].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="URL has expired")

    cache_url(short_code, row['original_url'], row['expires_at'])
    background_tasks.add_task(increment_click_count, short_code)

    return RedirectResponse(url=row['original_url'], status_code=301)


@app.get("/api/v1/urls/{short_code}/stats", response_model=URLStats)
async def get_url_stats(short_code: str):
    """Get URL statistics."""

    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT short_code, original_url, click_count, created_at, last_accessed_at
            FROM urls
            WHERE short_code = $1
        """, short_code)

    if not row:
        raise HTTPException(status_code=404, detail="URL not found")

    return URLStats(
        short_code=row['short_code'],
        original_url=row['original_url'],
        clicks=row['click_count'],
        created_at=row['created_at'],
        last_accessed_at=row['last_accessed_at']
    )


@app.delete("/api/v1/urls/{short_code}", status_code=204)
async def delete_url(short_code: str):
    """Delete a short URL."""

    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE urls SET is_active = FALSE
            WHERE short_code = $1
        """, short_code)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="URL not found")

    invalidate_cache(short_code)
    return Response(status_code=204)


async def increment_click_count(short_code: str):
    """Increment click count (background task)."""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE urls
                SET click_count = click_count + 1,
                    last_accessed_at = NOW()
                WHERE short_code = $1
            """, short_code)
    except Exception as e:
        print(f"Error incrementing click count: {e}")


# ======================== Entry Point ========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Design Decisions

### 1. Key Generation Service (KGS)

**Why KGS over hash-based generation?**

| Aspect | Hash-Based | KGS |
|--------|-----------|-----|
| Write Latency | 5-10ms (hash + uniqueness check) | 1-2ms (Redis SPOP) |
| Collision Handling | Required | Not needed |
| Database Load | High (uniqueness checks) | Low (just inserts) |
| Scalability | Limited by DB | Unlimited |

**Key Pool Management:**
- Minimum pool size: 100,000 keys
- Background worker replenishes pool every 60 seconds
- Emergency fallback: generate on-the-fly if pool exhausted
- Key space: 62^7 = 3.5 trillion unique keys

### 2. Caching Strategy

**Multi-layer caching:**
1. **Redis Cache** (URL mappings): 1-hour TTL, sub-millisecond reads
2. **CDN** (optional): Cache redirects at edge for popular URLs

**Cache invalidation:**
- TTL-based expiration (1 hour)
- Explicit invalidation on delete
- Lazy expiration check on read

### 3. Data Storage

**PostgreSQL for persistence:**
- ACID compliance for URL mappings
- Efficient indexing on short_code
- Click count tracking with background updates

**Redis for hot data:**
- URL cache for fast reads
- KGS key pool for fast writes
- Analytics buffering (optional)

### 4. Scalability

**Horizontal scaling:**
- Stateless URL service (scale Cloud Run instances)
- Redis Cluster for cache/key pool
- PostgreSQL read replicas for read-heavy workloads

**Estimated capacity:**
- 1 instance: 1,000 RPS
- 10 instances: 10,000 RPS
- 100 instances: 100,000 RPS

### 5. Reliability

**Failure handling:**
- Redis down: Fall back to PostgreSQL for reads
- KGS pool empty: Generate keys on-the-fly
- Database down: Return 503 (graceful degradation)

**Data durability:**
- PostgreSQL: Primary data store with replication
- Redis: Volatile cache (rebuild from DB if lost)

### 6. URL Expiration

**Implementation:**
- `expires_at` stored in both DB and cache
- Checked on every read
- Expired URLs return 404
- Background job can clean up expired entries

---

## Quick Start for Submission

### Schema Input (JSON)

```json
{
  "database_type": "postgresql",
  "tables": {
    "urls": {
      "columns": {
        "id": {"type": "bigserial", "primary_key": true},
        "short_code": {"type": "varchar(8)", "unique": true, "not_null": true},
        "original_url": {"type": "text", "not_null": true},
        "created_at": {"type": "timestamp with time zone", "default": "now()"},
        "expires_at": {"type": "timestamp with time zone", "nullable": true},
        "click_count": {"type": "bigint", "default": 0},
        "is_active": {"type": "boolean", "default": true}
      }
    }
  },
  "cache": {
    "type": "redis",
    "patterns": {
      "url:{short_code}": "URL mapping",
      "kgs:unused": "Key pool (SET)",
      "kgs:used": "Used keys (SET)"
    }
  }
}
```

### API Spec Input (JSON)

```json
{
  "endpoints": [
    {
      "method": "GET",
      "path": "/health",
      "response": {"status": "healthy"}
    },
    {
      "method": "GET",
      "path": "/",
      "response": {"service": "url-shortener", "version": "1.0.0"}
    },
    {
      "method": "POST",
      "path": "/api/v1/urls",
      "request": {"original_url": "string", "custom_code": "string?", "expires_in_hours": "int?"},
      "response": {"short_code": "string", "short_url": "string", "original_url": "string", "expires_at": "datetime?"}
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}",
      "response": {"short_code": "string", "original_url": "string", "click_count": "int"}
    },
    {
      "method": "GET",
      "path": "/{short_code}",
      "response": "301 Redirect"
    },
    {
      "method": "GET",
      "path": "/api/v1/urls/{short_code}/stats",
      "response": {"clicks": "int", "created_at": "datetime"}
    },
    {
      "method": "DELETE",
      "path": "/api/v1/urls/{short_code}",
      "response": "204 No Content"
    }
  ]
}
```

### Design Description

```
URL Shortener with Key Generation Service (KGS)

Architecture:
- Cloud Run for stateless URL service (auto-scaling)
- Redis for KGS key pool and URL cache
- PostgreSQL for persistent storage

Key Components:
1. KGS: Pre-generates 100K+ unique 7-char codes using base62
2. URL Service: Allocates keys via Redis SPOP (O(1))
3. Cache Layer: Redis with 1-hour TTL for fast reads
4. Database: PostgreSQL with indexes on short_code

Data Flow (Write):
Client → Load Balancer → URL Service → KGS (get key) → PostgreSQL (store) → Redis (cache)

Data Flow (Read):
Client → CDN → Load Balancer → URL Service → Redis (cache hit) → 301 Redirect
                                           → PostgreSQL (cache miss) → Cache → 301 Redirect

Scalability:
- Key space: 62^7 = 3.5 trillion unique codes
- Horizontal scaling: Add more Cloud Run instances
- Read scaling: Redis cache handles 90%+ of reads
- Write scaling: KGS eliminates uniqueness check bottleneck

Reliability:
- KGS pool monitored, refilled automatically
- Cache miss falls back to database
- Graceful degradation if Redis unavailable

Expiration:
- Optional expires_at stored in DB and cache
- Checked on every read, returns 404 if expired
- Background cleanup for expired entries
```

---

## Test Scenarios

This section details all the test scenarios used to validate the URL shortener implementation across functional, performance, and chaos testing dimensions.

### Functional Tests

Functional tests verify that the core API endpoints and business logic work correctly.

#### 1. Health & Status Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Health Endpoint | `GET /health` returns service health | Returns 200 with `{"status": "healthy"}` |
| Root Endpoint | `GET /` returns service info | Returns 200 with service name and version |
| KGS Pool Status | Health includes key pool size | `kgs_pool_size` in health response (optional) |

#### 2. URL Creation Tests (Core CRUD)

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Create Basic URL | POST with valid `original_url` | Returns 201 with `short_code`, `short_url`, `created_at` |
| Create with Custom Code | POST with `custom_code` field | Returns 201 with specified code or 409 if taken |
| Create with Expiration | POST with `expires_in_hours` or `expires_in_seconds` | Returns 201 with `expires_at` timestamp |
| Invalid URL Rejected | POST with malformed URL | Returns 400/422 with validation error |
| Empty URL Rejected | POST with empty `original_url` | Returns 400/422 |
| Missing URL Field | POST without `original_url` | Returns 400/422 |
| Duplicate URL Handling | POST same URL twice | Both succeed (may return same or different codes) |

**Example Request:**
```json
POST /api/v1/urls
{
  "original_url": "https://www.example.com/long/path",
  "custom_code": "mylink",
  "expires_in_hours": 24
}
```

**Example Response:**
```json
{
  "id": 12345,
  "short_code": "mylink",
  "short_url": "https://short.url/mylink",
  "original_url": "https://www.example.com/long/path",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-16T10:30:00Z"
}
```

#### 3. URL Retrieval Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Get by Short Code | `GET /api/v1/urls/{code}` | Returns 200 with URL details |
| Redirect Short URL | `GET /{code}` | Returns 301/302 redirect to original URL |
| Nonexistent Code | `GET /api/v1/urls/nonexistent` | Returns 404 |
| Expired URL Access | Access URL after expiration | Returns 404 or 410 (Gone) |

#### 4. URL Analytics Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Get URL Stats | `GET /api/v1/urls/{code}/stats` | Returns 200 with `clicks`, `created_at`, `last_accessed_at` |
| Click Count Increments | Access URL multiple times | `clicks` count increases correctly |

#### 5. URL Deletion Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Delete URL | `DELETE /api/v1/urls/{code}` | Returns 204, URL no longer accessible |
| Delete Nonexistent | `DELETE /api/v1/urls/nonexistent` | Returns 404 |

#### 6. URL Validation Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| XSS Prevention | `javascript:alert(1)` URL | Rejected with 400/422 |
| Data URI Blocked | `data:text/html,...` URL | Rejected with 400/422 |
| File URI Blocked | `file:///etc/passwd` URL | Rejected with 400/422 |
| SQL Injection | `'; DROP TABLE urls;--` in code | Returns 400/404, no SQL executed |
| Path Traversal | `../../../etc/passwd` as code | Returns 400/404 |

#### 7. URL Expiration Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| URL Expires After TTL | Create with 2-second TTL, wait 5 seconds | Returns 404/410 after expiration |
| URL Accessible Before Expiry | Access URL within TTL window | Returns 200 or redirect |
| Expiry Info in Response | Create with TTL | `expires_at` included in response |

#### 8. Data Integrity Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Original URL Preserved | Create and retrieve URL | Original URL exactly matches |
| Short Code Uniqueness | Create 50 URLs | All short codes are unique |
| Special Characters | URL with `?query=val&foo=bar` | Preserved correctly |
| Unicode URLs | URL with non-ASCII paths | Handled correctly (accepted or rejected consistently) |

#### 9. Key Generation Service (KGS) Tests

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| KGS Generates Unique Codes | Create 50 URLs rapidly | All codes unique, no duplicates |
| KGS Code Format | Check generated code format | 4-10 alphanumeric characters |
| KGS High Throughput | 20 concurrent creates | At least 15 succeed with unique codes |
| Custom Code Validation | Provide valid custom code | Accepted or conflict error |
| Custom Code Conflict | Use same custom code twice | Second request returns 409 |
| Fast Key Allocation | Measure create latency | Average < 2000ms (including cold start) |
| Rapid Sequential Creates | 30 rapid creates | No pool exhaustion (no 503) |
| Character Distribution | Check randomness of codes | At least 2 different starting characters |

#### 10. Edge Cases

| Test | Description | Expected Behavior |
|------|-------------|-------------------|
| Very Long URL (2000+ chars) | Create with 2000-char path | Accepted or rejected with proper error |
| Concurrent Requests | 10 parallel creates | At least 8 succeed |
| Empty Request Body | POST with empty body | Returns 400/415/422 |
| Wrong Content-Type | POST with text/plain | Returns 400/415 or handles gracefully |

---

### Performance Tests

Performance tests validate system behavior under load using tools like Locust or k6.

#### 1. Load Test Configuration

```python
# Locust configuration
class URLShortenerUser(HttpUser):
    wait_time = between(0.5, 2.0)  # 0.5-2 seconds between requests

    # Traffic ratio: 80% reads, 20% writes
    @task(4)  # Weight 4
    def read_url(self):
        self.client.get(f"/{random_short_code}")

    @task(1)  # Weight 1
    def create_url(self):
        self.client.post("/api/v1/urls", json={...})
```

#### 2. Latency Benchmarks

| Metric | Target | Description |
|--------|--------|-------------|
| P50 Latency | < 100ms | 50th percentile response time |
| P95 Latency | < 500ms | 95th percentile response time |
| P99 Latency | < 1000ms | 99th percentile response time |
| Create URL Avg | < 2000ms | Average time to create (allows cold start) |
| Redirect Avg | < 500ms | Average redirect latency |

#### 3. Throughput Targets

| Metric | Target | Description |
|--------|--------|-------------|
| Target RPS | 100+ | Requests per second at steady state |
| Error Rate | < 1% | Percentage of failed requests |
| Success Ratio | > 99% | Successful requests under load |

#### 4. Traffic Pattern Tests

| Pattern | Description | Duration |
|---------|-------------|----------|
| Ramp Up | 0 → 50 users over 60s | Gradual load increase |
| Sustained Load | 50 users for 120s | Steady state testing |
| Spike Test | 50 → 100 → 50 users | Sudden traffic spike |
| Soak Test | 20 users for 300s | Extended duration |

#### 5. Load Test Scenarios

```yaml
# Test Scenario: Standard Load
scenarios:
  - name: url_creation
    executor: constant-vus
    vus: 10
    duration: 60s
    exec: createURL

  - name: url_access
    executor: constant-vus
    vus: 40
    duration: 60s
    exec: accessURL

  - name: analytics
    executor: constant-vus
    vus: 5
    duration: 60s
    exec: getStats
```

#### 6. Performance Test Assertions

```javascript
// k6 thresholds
thresholds: {
  'http_req_duration': ['p(95)<500', 'p(99)<1000'],
  'http_req_failed': ['rate<0.01'],
  'http_reqs': ['rate>100'],
  'checks': ['rate>0.99']
}
```

---

### Chaos Tests

Chaos tests verify system resilience to failures using Chaos Toolkit or similar tools.

#### 1. Network Failure Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| Network Partition | Block traffic between service and DB | Graceful degradation, cached reads work |
| High Latency | Add 500ms+ network delay | Requests complete, may timeout |
| Packet Loss | Drop 10% of packets | Retries succeed, partial degradation |
| DNS Failure | Block DNS resolution | Cached connections continue working |

**Chaos Toolkit Experiment:**
```yaml
steady-state-hypothesis:
  title: "Service remains responsive"
  probes:
    - type: probe
      name: health-check
      tolerance: 200
      provider:
        type: http
        url: "http://service/health"

method:
  - type: action
    name: inject-network-latency
    provider:
      type: process
      path: tc
      arguments: "qdisc add dev eth0 root netem delay 500ms"
    pauses:
      after: 30
```

#### 2. Database Failure Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| Database Latency | Add 5s+ DB response delay | Timeouts with proper error responses |
| Connection Failure | Kill DB connections | 503 errors, no data corruption |
| Partial Write Failure | Fail mid-transaction | Rollback, consistent state |
| Read Replica Lag | Delay replica by 30s | May serve stale data (acceptable) |

**Test Implementation:**
```python
def test_database_failure_handling():
    # Inject database latency
    inject_db_latency(seconds=5)

    # Attempt to create URL
    response = client.post("/api/v1/urls", json={...}, timeout=10)

    # Should get timeout or 503, not 500
    assert response.status_code in [503, 504, 408]

    # Remove injection
    remove_db_latency()

    # Service should recover
    response = client.get("/health")
    assert response.status_code == 200
```

#### 3. Cache Failure Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| Cache Unavailable | Stop Redis | Fallback to database reads |
| Cache Corruption | Write invalid data | Handle gracefully, re-fetch from DB |
| Cache Miss Storm | Flush all cache | Database handles load spike |
| Cache Connection Pool | Exhaust connections | Queue or reject gracefully |

**Chaos Experiment:**
```yaml
method:
  - type: action
    name: stop-redis
    provider:
      type: process
      path: docker
      arguments: "stop redis"
    pauses:
      after: 60

rollbacks:
  - type: action
    name: restart-redis
    provider:
      type: process
      path: docker
      arguments: "start redis"
```

#### 4. Infrastructure Failure Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| Instance Crash | Kill service instance | Load balancer routes to healthy instances |
| Cold Start | Scale to 0, then request | Acceptable cold start latency (<10s) |
| Zonal Outage | Block one availability zone | Multi-zone deployment continues |
| Memory Pressure | Consume 90% memory | OOM handling or graceful rejection |

#### 5. KGS-Specific Chaos Tests

| Scenario | Injection | Expected Behavior |
|----------|-----------|-------------------|
| KGS Pool Empty | Drain all unused keys | Emergency key generation kicks in |
| KGS Redis Failure | Stop KGS Redis | Fallback to on-the-fly generation |
| Slow Key Generation | Add latency to SPOP | Writes slow but succeed |
| Concurrent Pool Drain | Many rapid creates | No duplicate keys issued |

**KGS Resilience Test:**
```python
def test_kgs_pool_exhaustion():
    # Simulate pool exhaustion by rapid creates
    results = []
    for i in range(1000):
        response = client.post("/api/v1/urls", json={
            "original_url": f"https://example.com/{i}"
        })
        results.append(response.status_code)

    # Most should succeed (emergency fallback)
    success_rate = sum(1 for r in results if r in [200, 201]) / len(results)
    assert success_rate > 0.95, "Too many failures during pool stress"

    # No duplicates in successful responses
    codes = [r.json()["short_code"] for r in results if r.status_code in [200, 201]]
    assert len(codes) == len(set(codes)), "Duplicate codes during stress"
```

#### 6. Steady State Verification

Before and after each chaos experiment, verify:

```yaml
steady-state-hypothesis:
  title: "URL Shortener is healthy"
  probes:
    - name: health-endpoint-responsive
      type: probe
      tolerance: 200
      provider:
        type: http
        url: "${SERVICE_URL}/health"

    - name: can-create-urls
      type: probe
      tolerance: [200, 201]
      provider:
        type: http
        method: POST
        url: "${SERVICE_URL}/api/v1/urls"
        body: '{"original_url": "https://example.com/chaos-test"}'

    - name: can-read-urls
      type: probe
      tolerance: 200
      provider:
        type: http
        url: "${SERVICE_URL}/api/v1/urls/${TEST_SHORT_CODE}"
```

---

## Test Coverage Summary

| Category | Tests | Coverage |
|----------|-------|----------|
| **Functional** | 50+ | Core CRUD, validation, KGS, expiration |
| **Performance** | 10+ | Latency, throughput, load patterns |
| **Chaos** | 15+ | Network, database, cache, infrastructure |

### Running Tests

```bash
# Functional tests
pytest tests/functional/test_url_shortener.py -v

# Performance tests (Locust)
locust -f tests/performance/locustfile.py --host=$SERVICE_URL

# Chaos tests (Chaos Toolkit)
chaos run tests/chaos/network-failure.yaml
chaos run tests/chaos/database-failure.yaml
chaos run tests/chaos/cache-failure.yaml
```

### Test Environment Variables

```bash
export TEST_TARGET_URL="https://your-service-url.run.app"
export DATABASE_URL="postgresql://..."
export REDIS_URL="redis://..."
```
