"""
Sliding Window Log Rate Limiter Implementation - Python Template

This template provides the basic structure for implementing a
distributed sliding window log rate limiter.

Key concepts:
1. Each request's timestamp is stored in a sorted log
2. When request arrives, remove entries older than the window
3. Count remaining entries; if under limit, allow and add entry
4. Provides precise rate limiting with no boundary issues

Trade-off: More memory usage but more accurate than fixed window

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import bisect
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import grpc
from grpc import aio

# Generated protobuf imports
import sliding_window_log_pb2
import sliding_window_log_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_REQUESTS = 100
DEFAULT_WINDOW_SIZE_MS = 60000  # 1 minute


@dataclass
class LogEntry:
    """A timestamp entry in the log."""
    timestamp: int  # milliseconds
    request_id: str = ""


@dataclass
class LogState:
    """State of a sliding window log."""
    limit_id: str
    max_requests: int
    window_size_ms: int
    entries: List[int] = field(default_factory=list)  # Sorted timestamps
    total_requests: int = 0
    total_allowed: int = 0
    total_rejected: int = 0


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    node_id: str
    address: str
    is_healthy: bool = True
    limits_count: int = 0
    entries_count: int = 0
    last_heartbeat: int = 0


class SlidingWindowLogRateLimiter:
    """
    Sliding Window Log Rate Limiter implementation.

    TODO: Implement the core sliding window log algorithm:
    1. cleanup_old_entries() - Remove entries outside the window
    2. check_and_add() - Check limit and add new entry if allowed
    3. get_log() - Get or create a log for a limit
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Log storage
        self.logs: Dict[str, LogState] = {}

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, sliding_window_log_pb2_grpc.NodeServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = sliding_window_log_pb2_grpc.NodeServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def cleanup_old_entries(self, log: LogState, now: Optional[int] = None) -> int:
        """
        Remove entries older than the sliding window.

        TODO: Implement cleanup:
        1. Calculate the window start time (now - window_size)
        2. Use binary search to find the cutoff point
        3. Remove all entries before that point
        4. Return number of entries removed
        """
        if now is None:
            now = self._current_time_ms()

        window_start = now - log.window_size_ms

        # Binary search for cutoff point
        cutoff_idx = bisect.bisect_left(log.entries, window_start)

        # Remove old entries
        removed = cutoff_idx
        log.entries = log.entries[cutoff_idx:]

        return removed

    def check_and_add(self, log: LogState, timestamp: Optional[int] = None) -> tuple:
        """
        Check if request is allowed and add to log.

        TODO: Implement check and add:
        1. Clean up old entries first
        2. Check if current count < max_requests
        3. If yes, add timestamp and return (True, count, remaining)
        4. If no, return (False, count, 0)

        Returns:
            Tuple of (allowed, current_count, remaining)
        """
        with self.lock:
            if timestamp is None:
                timestamp = self._current_time_ms()

            # Clean up old entries
            self.cleanup_old_entries(log, timestamp)

            log.total_requests += 1
            current_count = len(log.entries)

            if current_count < log.max_requests:
                # Use bisect to insert in sorted order
                bisect.insort(log.entries, timestamp)
                log.total_allowed += 1
                remaining = log.max_requests - len(log.entries)
                return (True, len(log.entries), remaining)
            else:
                log.total_rejected += 1
                return (False, current_count, 0)

    def get_or_create_log(
        self,
        limit_id: str,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_size_ms: int = DEFAULT_WINDOW_SIZE_MS
    ) -> LogState:
        """Get an existing log or create a new one."""
        with self.lock:
            if limit_id not in self.logs:
                self.logs[limit_id] = LogState(
                    limit_id=limit_id,
                    max_requests=max_requests,
                    window_size_ms=window_size_ms,
                )
                logger.info(f"Created log {limit_id} with max={max_requests}, window={window_size_ms}ms")
            return self.logs[limit_id]


class RateLimiterServicer(sliding_window_log_pb2_grpc.RateLimiterServiceServicer):
    """gRPC service implementation for rate limiting."""

    def __init__(self, limiter: SlidingWindowLogRateLimiter):
        self.limiter = limiter

    async def AllowRequest(self, request, context):
        """Handle AllowRequest RPC."""
        log = self.limiter.get_or_create_log(request.limit_id)
        timestamp = request.timestamp if request.timestamp else None

        allowed, current_count, remaining = self.limiter.check_and_add(log, timestamp)

        oldest = log.entries[0] if log.entries else 0

        return sliding_window_log_pb2.AllowRequestResponse(
            allowed=allowed,
            current_count=current_count,
            remaining=remaining,
            oldest_entry=oldest,
            served_by=self.limiter.node_id,
        )

    async def GetLogStatus(self, request, context):
        """Handle GetLogStatus RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.logs:
                log = self.limiter.logs[request.limit_id]
                self.limiter.cleanup_old_entries(log)

                entries = []
                if request.include_entries:
                    entries = [
                        sliding_window_log_pb2.LogEntry(timestamp=ts)
                        for ts in log.entries
                    ]

                return sliding_window_log_pb2.GetLogStatusResponse(
                    log=sliding_window_log_pb2.LogState(
                        limit_id=log.limit_id,
                        window_size_ms=log.window_size_ms,
                        max_requests=log.max_requests,
                        entries=entries,
                        current_count=len(log.entries),
                        total_requests=log.total_requests,
                        total_allowed=log.total_allowed,
                        total_rejected=log.total_rejected,
                    ),
                    found=True,
                )
            return sliding_window_log_pb2.GetLogStatusResponse(found=False)

    async def ConfigureLimit(self, request, context):
        """Handle ConfigureLimit RPC."""
        config = request.config
        with self.limiter.lock:
            if config.limit_id in self.limiter.logs and not request.overwrite:
                return sliding_window_log_pb2.ConfigureLimitResponse(
                    success=False,
                    error="Limit already exists",
                )

            log = self.limiter.get_or_create_log(
                config.limit_id,
                config.max_requests or DEFAULT_MAX_REQUESTS,
                config.window_size_ms or DEFAULT_WINDOW_SIZE_MS,
            )

            if request.overwrite:
                log.max_requests = config.max_requests or log.max_requests
                log.window_size_ms = config.window_size_ms or log.window_size_ms

            return sliding_window_log_pb2.ConfigureLimitResponse(
                success=True,
                log=sliding_window_log_pb2.LogState(
                    limit_id=log.limit_id,
                    window_size_ms=log.window_size_ms,
                    max_requests=log.max_requests,
                    current_count=len(log.entries),
                ),
            )

    async def DeleteLimit(self, request, context):
        """Handle DeleteLimit RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.logs:
                del self.limiter.logs[request.limit_id]
                return sliding_window_log_pb2.DeleteLimitResponse(success=True)
            return sliding_window_log_pb2.DeleteLimitResponse(
                success=False,
                error="Limit not found",
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return sliding_window_log_pb2.GetLeaderResponse(
            node_id=self.limiter.node_id,
            node_address=f"localhost:{self.limiter.port}",
            is_leader=self.limiter.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.limiter.lock:
            members = [
                sliding_window_log_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    limits_count=n.limits_count,
                    entries_count=n.entries_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.limiter.nodes.values()
            ]

            total_entries = sum(len(l.entries) for l in self.limiter.logs.values())
            total_requests = sum(l.total_requests for l in self.limiter.logs.values())

            return sliding_window_log_pb2.GetClusterStatusResponse(
                node_id=self.limiter.node_id,
                node_address=f"localhost:{self.limiter.port}",
                is_leader=self.limiter.is_leader,
                total_nodes=len(self.limiter.nodes),
                healthy_nodes=sum(1 for n in self.limiter.nodes.values() if n.is_healthy),
                total_limits=len(self.limiter.logs),
                total_log_entries=total_entries,
                total_requests_processed=total_requests,
                members=members,
            )


class NodeServicer(sliding_window_log_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, limiter: SlidingWindowLogRateLimiter):
        self.limiter = limiter

    async def SyncLog(self, request, context):
        """Handle SyncLog RPC."""
        return sliding_window_log_pb2.SyncLogResponse(success=True)

    async def AddEntry(self, request, context):
        """Handle AddEntry RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.logs:
                log = self.limiter.logs[request.limit_id]
                bisect.insort(log.entries, request.entry.timestamp)
                return sliding_window_log_pb2.AddEntryResponse(
                    success=True,
                    new_count=len(log.entries),
                )
        return sliding_window_log_pb2.AddEntryResponse(
            success=False,
            error="Log not found",
        )

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.limiter.lock:
            if request.node_id in self.limiter.nodes:
                self.limiter.nodes[request.node_id].last_heartbeat = request.timestamp
                self.limiter.nodes[request.node_id].limits_count = request.limits_count

        return sliding_window_log_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.limiter._current_time_ms(),
        )

    async def GetLocalLogs(self, request, context):
        """Handle GetLocalLogs RPC."""
        with self.limiter.lock:
            logs = [
                sliding_window_log_pb2.LogState(
                    limit_id=l.limit_id,
                    window_size_ms=l.window_size_ms,
                    max_requests=l.max_requests,
                    current_count=len(l.entries),
                    total_requests=l.total_requests,
                    total_allowed=l.total_allowed,
                    total_rejected=l.total_rejected,
                )
                for l in self.limiter.logs.values()
            ]
            return sliding_window_log_pb2.GetLocalLogsResponse(
                logs=logs,
                total_count=len(logs),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the sliding window log rate limiter server."""
    limiter = SlidingWindowLogRateLimiter(node_id, port, peers)
    await limiter.initialize()

    server = aio.server()
    sliding_window_log_pb2_grpc.add_RateLimiterServiceServicer_to_server(
        RateLimiterServicer(limiter), server
    )
    sliding_window_log_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(limiter), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Sliding Window Log node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Sliding Window Log Rate Limiter Node")
    parser.add_argument("--node-id", required=True, help="Unique node identifier")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument(
        "--peers",
        required=True,
        help="Comma-separated list of peer addresses (host:port)",
    )
    args = parser.parse_args()

    peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    asyncio.run(serve(args.node_id, args.port, peers))


if __name__ == "__main__":
    main()
