"""
WebSocket routes for real-time submission updates.
"""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
from jose import jwt, JWTError

from backend.websocket.connection_manager import manager
from backend.database import SessionLocal
from backend.models.submission import Submission
from backend.config import get_settings

websocket_router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# WebSocket connection timeout (5 minutes)
WS_TIMEOUT_SECONDS = 300


def verify_submission_access(token: Optional[str], submission_id: int) -> bool:
    """Verify user has access to the submission."""
    if settings.demo_mode:
        return True  # Demo mode allows all access

    if not token:
        return False

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        if not user_id:
            return False

        # Check if user owns the submission
        db = SessionLocal()
        try:
            submission = db.query(Submission).filter(
                Submission.id == submission_id,
                Submission.user_id == int(user_id)
            ).first()
            return submission is not None
        finally:
            db.close()
    except JWTError:
        return False
    except Exception as e:
        logger.error(f"Error verifying submission access: {e}")
        return False


@websocket_router.websocket("/ws/submissions/{submission_id}")
async def submission_websocket(
    websocket: WebSocket,
    submission_id: int,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time submission updates.

    Connect to receive live updates for a specific submission:
    - status_update: When submission status changes
    - test_result: When a test completes
    - error_analysis: When error analysis is complete

    Query Parameters:
        token: Auth token (required for authenticated sessions)

    Message format (from server):
    ```json
    {
        "type": "status_update" | "test_result" | "error_analysis",
        "submission_id": 123,
        "timestamp": "2024-01-01T00:00:00Z",
        ...
    }
    ```
    """
    # Verify user has access to this submission
    if not verify_submission_access(token, submission_id):
        await websocket.close(code=4003, reason="Unauthorized")
        return

    await manager.connect(websocket, submission_id)

    try:
        while True:
            # Keep connection alive with timeout
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                # Send ping to check if client is still alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
                continue

            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "pong":
                pass  # Client responded to our ping
            # Could handle other client messages here if needed

    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for submission {submission_id}")
    except Exception as e:
        logger.error(f"WebSocket error for submission {submission_id}: {e}")
    finally:
        await manager.disconnect(websocket, submission_id)
