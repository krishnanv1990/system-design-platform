"""
WebSocket routes for real-time submission updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from backend.websocket.connection_manager import manager

websocket_router = APIRouter()


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
        token: Optional auth token (for authenticated sessions)

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
    await manager.connect(websocket, submission_id)

    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()

            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
            # Could handle other client messages here if needed

    except WebSocketDisconnect:
        await manager.disconnect(websocket, submission_id)
    except Exception:
        await manager.disconnect(websocket, submission_id)
