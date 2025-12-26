"""
API routes for the system design platform.
"""

from fastapi import APIRouter

from backend.api.auth import router as auth_router
from backend.api.problems import router as problems_router
from backend.api.submissions import router as submissions_router
from backend.api.tests import router as tests_router

# Create main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(problems_router, prefix="/problems", tags=["Problems"])
api_router.include_router(submissions_router, prefix="/submissions", tags=["Submissions"])
api_router.include_router(tests_router, prefix="/tests", tags=["Tests"])
