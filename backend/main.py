"""
Main FastAPI application entry point.
System Design Interview Platform API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config import get_settings
from backend.database import engine, Base
from backend.api import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Creates database tables on startup.
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


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
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
