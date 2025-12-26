"""
WebSocket connection manager for real-time updates.
Manages connections per submission and broadcasts messages.
"""

import json
import asyncio
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    """
    Manages WebSocket connections for real-time submission updates.

    Supports:
    - Multiple connections per submission
    - Broadcasting to all connections for a submission
    - Graceful connection handling
    """

    def __init__(self):
        # Map submission_id -> set of WebSocket connections
        self._connections: Dict[int, Set[WebSocket]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, submission_id: int) -> None:
        """
        Accept a new WebSocket connection for a submission.

        Args:
            websocket: The WebSocket connection
            submission_id: The submission to subscribe to
        """
        await websocket.accept()

        async with self._lock:
            if submission_id not in self._connections:
                self._connections[submission_id] = set()
            self._connections[submission_id].add(websocket)

        # Send initial connection message
        await self.send_to_connection(websocket, {
            "type": "connected",
            "submission_id": submission_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def disconnect(self, websocket: WebSocket, submission_id: int) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
            submission_id: The submission ID
        """
        async with self._lock:
            if submission_id in self._connections:
                self._connections[submission_id].discard(websocket)
                # Cleanup empty sets
                if not self._connections[submission_id]:
                    del self._connections[submission_id]

    async def send_to_connection(
        self, websocket: WebSocket, message: Dict[str, Any]
    ) -> bool:
        """
        Send a message to a specific connection.

        Args:
            websocket: The WebSocket connection
            message: The message to send

        Returns:
            True if successful, False if connection failed
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def broadcast_to_submission(
        self, submission_id: int, message: Dict[str, Any]
    ) -> int:
        """
        Broadcast a message to all connections watching a submission.

        Args:
            submission_id: The submission ID
            message: The message to broadcast

        Returns:
            Number of successful sends
        """
        if submission_id not in self._connections:
            return 0

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()

        # Add submission_id to message
        message["submission_id"] = submission_id

        sent_count = 0
        failed_connections: Set[WebSocket] = set()

        async with self._lock:
            connections = list(self._connections.get(submission_id, set()))

        for websocket in connections:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception:
                failed_connections.add(websocket)

        # Clean up failed connections
        if failed_connections:
            async with self._lock:
                if submission_id in self._connections:
                    self._connections[submission_id] -= failed_connections
                    if not self._connections[submission_id]:
                        del self._connections[submission_id]

        return sent_count

    def has_connections(self, submission_id: int) -> bool:
        """Check if there are active connections for a submission."""
        return submission_id in self._connections and bool(
            self._connections[submission_id]
        )

    def get_connection_count(self, submission_id: Optional[int] = None) -> int:
        """
        Get the number of active connections.

        Args:
            submission_id: If provided, count for specific submission

        Returns:
            Number of active connections
        """
        if submission_id is not None:
            return len(self._connections.get(submission_id, set()))
        return sum(len(conns) for conns in self._connections.values())


# Global connection manager instance
manager = ConnectionManager()


# Helper functions for broadcasting different message types
async def broadcast_status_update(
    submission_id: int,
    status: str,
    progress: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    """
    Broadcast a submission status update.

    Args:
        submission_id: The submission ID
        status: New status value
        progress: Optional progress percentage (0-100)
        detail: Optional status detail message
    """
    message = {
        "type": "status_update",
        "status": status,
    }
    if progress is not None:
        message["progress"] = progress
    if detail is not None:
        message["detail"] = detail

    await manager.broadcast_to_submission(submission_id, message)


async def broadcast_test_result(
    submission_id: int,
    test_id: int,
    test_name: str,
    test_type: str,
    status: str,
    duration_ms: Optional[int] = None,
    error_category: Optional[str] = None,
) -> None:
    """
    Broadcast a test result.

    Args:
        submission_id: The submission ID
        test_id: The test result ID
        test_name: Name of the test
        test_type: Type of test (functional/performance/chaos)
        status: Test status (passed/failed/error)
        duration_ms: Test duration in milliseconds
        error_category: Error category if failed
    """
    message = {
        "type": "test_result",
        "test_id": test_id,
        "test_name": test_name,
        "test_type": test_type,
        "status": status,
    }
    if duration_ms is not None:
        message["duration_ms"] = duration_ms
    if error_category is not None:
        message["error_category"] = error_category

    await manager.broadcast_to_submission(submission_id, message)


async def broadcast_error_analysis(
    submission_id: int,
    test_id: int,
    analysis: Dict[str, Any],
) -> None:
    """
    Broadcast an error analysis result.

    Args:
        submission_id: The submission ID
        test_id: The test result ID
        analysis: The error analysis data
    """
    message = {
        "type": "error_analysis",
        "test_id": test_id,
        "analysis": analysis,
    }

    await manager.broadcast_to_submission(submission_id, message)
