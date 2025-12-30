"""
API routes for the system design platform.
"""

from fastapi import APIRouter

from backend.api.auth import router as auth_router
from backend.api.problems import router as problems_router
from backend.api.submissions import router as submissions_router
from backend.api.tests import router as tests_router
from backend.api.admin import router as admin_router
from backend.api.assets import router as assets_router
from backend.api.chat import router as chat_router
from backend.api.user import router as user_router
from backend.api.distributed import router as distributed_router

# Create main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(problems_router, prefix="/problems", tags=["Problems"])
api_router.include_router(submissions_router, prefix="/submissions", tags=["Submissions"])
api_router.include_router(tests_router, prefix="/tests", tags=["Tests"])
api_router.include_router(admin_router, tags=["Admin"])
api_router.include_router(assets_router, prefix="/assets", tags=["GCP Assets"])
api_router.include_router(chat_router, prefix="/chat", tags=["Design Chat"])
api_router.include_router(user_router, prefix="/user", tags=["User Profile"])
api_router.include_router(distributed_router, prefix="/distributed", tags=["Distributed Consensus"])
