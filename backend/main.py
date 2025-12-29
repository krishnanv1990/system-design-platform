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
    allow_methods=["*"],
    allow_headers=["*"],
)

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
