"""
Audit Middleware for logging all API requests.
Captures request/response information for security and debugging.
"""

import logging
import time
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.database import SessionLocal
from backend.services.audit_service import AuditService
from backend.models.audit_log import ActionType

logger = logging.getLogger(__name__)

# Mapping of endpoint paths to action types
PATH_ACTION_MAP = {
    # Auth endpoints
    "/api/auth/google": ActionType.LOGIN,
    "/api/auth/facebook": ActionType.LOGIN,
    "/api/auth/linkedin": ActionType.LOGIN,
    "/api/auth/github": ActionType.LOGIN,
    "/api/auth/logout": ActionType.LOGOUT,

    # Problem endpoints
    "/api/problems": ActionType.LIST_PROBLEMS,

    # Submission endpoints
    "/api/submissions": ActionType.LIST_SUBMISSIONS,
    "/api/submissions/validate": ActionType.VALIDATE_SUBMISSION,

    # Chat endpoints
    "/api/chat/message": ActionType.CHAT_MESSAGE,
    "/api/chat/summary": ActionType.GENERATE_SUMMARY,
    "/api/chat/evaluate-diagram": ActionType.EVALUATE_DIAGRAM,

    # User endpoints
    "/api/users/me": ActionType.VIEW_SUBMISSION,  # Viewing profile
    "/api/users/me/export": ActionType.EXPORT_DATA,
}

# Paths to skip auditing (health checks, static files, etc.)
SKIP_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def get_action_for_request(method: str, path: str) -> Optional[ActionType]:
    """
    Determine the action type based on HTTP method and path.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path

    Returns:
        ActionType or None if path should be skipped
    """
    # Skip certain paths
    if path in SKIP_PATHS or path.startswith("/static"):
        return None

    # Check user endpoints first (method-sensitive)
    if path.startswith("/api/users/me"):
        if method in ("PUT", "PATCH"):
            return ActionType.UPDATE_PROFILE
        elif method == "DELETE":
            return ActionType.DELETE_ACCOUNT
        elif method == "GET" and path == "/api/users/me/export":
            return ActionType.EXPORT_DATA
        elif method == "GET":
            return ActionType.VIEW_SUBMISSION  # Viewing profile

    # Check exact path matches
    if path in PATH_ACTION_MAP:
        return PATH_ACTION_MAP[path]

    # Check pattern matches
    if path.startswith("/api/problems/") and method == "GET":
        return ActionType.VIEW_PROBLEM

    if path.startswith("/api/submissions/"):
        if method == "POST" and path == "/api/submissions":
            return ActionType.CREATE_SUBMISSION
        elif method == "GET":
            return ActionType.VIEW_SUBMISSION

    # Default: log as generic action based on method
    return None  # Only log specific actions we care about


def get_client_ip(request: Request) -> str:
    """Get the real client IP address, handling proxies."""
    # Check X-Forwarded-For header (Cloud Run sets this)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"


def get_user_id_from_request(request: Request) -> Optional[int]:
    """
    Extract user ID from request state (set by auth middleware).
    """
    # Check if user is set in request state
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user.id

    # Check if user_id is set directly
    if hasattr(request.state, "user_id"):
        return request.state.user_id

    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests for auditing.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log audit information.
        """
        start_time = time.time()

        # Get request info before processing
        method = request.method
        path = request.url.path
        action = get_action_for_request(method, path)

        # Skip auditing for certain paths
        if action is None:
            return await call_next(request)

        # Process the request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log the action asynchronously (don't block response)
        try:
            await self._log_action(
                request=request,
                response=response,
                action=action,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")

        return response

    async def _log_action(
        self,
        request: Request,
        response: Response,
        action: ActionType,
        duration_ms: int,
    ):
        """
        Log the action to the database.
        """
        # Create a new database session for the audit log
        db = SessionLocal()
        try:
            audit_service = AuditService(db)

            # Extract request information
            user_id = get_user_id_from_request(request)
            ip_address = get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")[:512]

            # Extract resource info from path
            resource_type = None
            resource_id = None
            path_parts = request.url.path.split("/")

            if len(path_parts) >= 3:
                if path_parts[2] == "problems" and len(path_parts) >= 4:
                    resource_type = "problem"
                    try:
                        resource_id = int(path_parts[3])
                    except (ValueError, IndexError):
                        pass
                elif path_parts[2] == "submissions" and len(path_parts) >= 4:
                    resource_type = "submission"
                    try:
                        resource_id = int(path_parts[3])
                    except (ValueError, IndexError):
                        pass

            # Create audit log entry
            audit_service.log_action(
                action=action,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request.url.path,
                request_method=request.method,
                response_status=response.status_code,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"Error in audit logging: {e}")
            db.rollback()
        finally:
            db.close()
