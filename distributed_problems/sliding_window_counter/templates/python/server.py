"""
Sliding Window Counter Rate Limiter Implementation - Python Template

This template provides the basic structure for implementing a
distributed sliding window counter rate limiter.

Key concepts:
1. Hybrid of fixed window counter and sliding window
2. Maintains counters for current and previous windows
3. Uses weighted average based on position in current window
4. Formula: count = prev_count * (1 - elapsed/window) + curr_count

Trade-off: Low memory (only 2 counters) with good accuracy

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import grpc
from grpc import aio

# Generated protobuf imports
import sliding_window_counter_pb2
import sliding_window_counter_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_REQUESTS = 100
DEFAULT_WINDOW_SIZE_MS = 60000  # 1 minute


@dataclass
class WindowState:
    """State of sliding window counters."""
    limit_id: str
    max_requests: int
    window_size_ms: int

    # Current window
    current_window_start: int = 0  # milliseconds
    current_count: int = 0

    # Previous window
    previous_window_start: int = 0
    previous_count: int = 0

    # Statistics
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
    last_heartbeat: int = 0


class SlidingWindowCounterRateLimiter:
    """
    Sliding Window Counter Rate Limiter implementation.

    TODO: Implement the core sliding window counter algorithm:
    1. get_sliding_count() - Calculate weighted count using both windows
    2. maybe_rotate_window() - Rotate windows when crossing boundary
    3. check_and_increment() - Check limit using sliding estimate
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Window storage
        self.windows: Dict[str, WindowState] = {}

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, sliding_window_counter_pb2_grpc.NodeServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = sliding_window_counter_pb2_grpc.NodeServiceStub(channel)

        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def get_window_start(self, window_size_ms: int, timestamp_ms: int) -> int:
        """Calculate window start time for a timestamp."""
        return (timestamp_ms // window_size_ms) * window_size_ms

    def maybe_rotate_window(self, window: WindowState, now: Optional[int] = None) -> bool:
        """
        Rotate windows if we've crossed into a new window.

        TODO: Implement window rotation:
        1. Check if current time is in a new window
        2. If crossing one window, move current to previous
        3. If crossing multiple windows, clear previous
        4. Reset current count
        """
        # TODO: Implement this method
        return False

    def get_sliding_count(self, window: WindowState, now: Optional[int] = None) -> float:
        """
        Calculate the sliding window count estimate.

        TODO: Implement sliding count calculation:
        1. Calculate position in current window (0.0 to 1.0)
        2. Weight = 1 - position (how much of previous window to count)
        3. sliding_count = prev_count * weight + curr_count

        Returns:
            Weighted count estimate
        """
        # TODO: Implement this method
        return 0.0

    def check_and_increment(self, window: WindowState, cost: int = 1, timestamp: Optional[int] = None) -> tuple:
        """
        Check if request is allowed using sliding window estimate.

        TODO: Implement check and increment:
        1. Calculate sliding count
        2. Check if sliding_count + cost <= max_requests
        3. If yes, increment current_count and return success
        4. If no, reject

        Returns:
            Tuple of (allowed, sliding_count, remaining)
        """
        # TODO: Implement this method
        return (False, 0.0, 0)

    def get_or_create_window(
        self,
        limit_id: str,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_size_ms: int = DEFAULT_WINDOW_SIZE_MS
    ) -> WindowState:
        """
        Get an existing window or create a new one.

        TODO: Implement window management:
        1. Check if window exists
        2. If not, create new window with given config
        3. Return the window
        """
        # TODO: Implement this method
        # For now, return a placeholder window
        return WindowState(
            limit_id=limit_id,
            max_requests=max_requests,
            window_size_ms=window_size_ms,
            current_window_start=0,
            previous_window_start=0,
        )


class RateLimiterServicer(sliding_window_counter_pb2_grpc.RateLimiterServiceServicer):
    """gRPC service implementation for rate limiting."""

    def __init__(self, limiter: SlidingWindowCounterRateLimiter):
        self.limiter = limiter

    async def AllowRequest(self, request, context):
        """Handle AllowRequest RPC."""
        window = self.limiter.get_or_create_window(request.limit_id)
        cost = request.cost or 1
        timestamp = request.timestamp if request.timestamp else None

        allowed, sliding_count, remaining = self.limiter.check_and_increment(window, cost, timestamp)

        reset_at = window.current_window_start + window.window_size_ms

        return sliding_window_counter_pb2.AllowRequestResponse(
            allowed=allowed,
            sliding_count=sliding_count,
            remaining=remaining,
            reset_at=reset_at,
            served_by=self.limiter.node_id,
        )

    async def GetWindowStatus(self, request, context):
        """Handle GetWindowStatus RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                window = self.limiter.windows[request.limit_id]
                sliding_estimate = self.limiter.get_sliding_count(window)

                return sliding_window_counter_pb2.GetWindowStatusResponse(
                    window=sliding_window_counter_pb2.WindowState(
                        limit_id=window.limit_id,
                        window_size_ms=window.window_size_ms,
                        max_requests=window.max_requests,
                        current_window_start=window.current_window_start,
                        current_count=window.current_count,
                        previous_window_start=window.previous_window_start,
                        previous_count=window.previous_count,
                        sliding_estimate=sliding_estimate,
                        total_requests=window.total_requests,
                        total_allowed=window.total_allowed,
                        total_rejected=window.total_rejected,
                    ),
                    found=True,
                )
            return sliding_window_counter_pb2.GetWindowStatusResponse(found=False)

    async def ConfigureLimit(self, request, context):
        """Handle ConfigureLimit RPC."""
        config = request.config
        with self.limiter.lock:
            if config.limit_id in self.limiter.windows and not request.overwrite:
                return sliding_window_counter_pb2.ConfigureLimitResponse(
                    success=False,
                    error="Limit already exists",
                )

            window = self.limiter.get_or_create_window(
                config.limit_id,
                config.max_requests or DEFAULT_MAX_REQUESTS,
                config.window_size_ms or DEFAULT_WINDOW_SIZE_MS,
            )

            if request.overwrite:
                window.max_requests = config.max_requests or window.max_requests
                window.window_size_ms = config.window_size_ms or window.window_size_ms

            return sliding_window_counter_pb2.ConfigureLimitResponse(
                success=True,
                window=sliding_window_counter_pb2.WindowState(
                    limit_id=window.limit_id,
                    window_size_ms=window.window_size_ms,
                    max_requests=window.max_requests,
                    current_window_start=window.current_window_start,
                    current_count=window.current_count,
                ),
            )

    async def DeleteLimit(self, request, context):
        """Handle DeleteLimit RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                del self.limiter.windows[request.limit_id]
                return sliding_window_counter_pb2.DeleteLimitResponse(success=True)
            return sliding_window_counter_pb2.DeleteLimitResponse(
                success=False,
                error="Limit not found",
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return sliding_window_counter_pb2.GetLeaderResponse(
            node_id=self.limiter.node_id,
            node_address=f"localhost:{self.limiter.port}",
            is_leader=self.limiter.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.limiter.lock:
            members = [
                sliding_window_counter_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    limits_count=n.limits_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.limiter.nodes.values()
            ]

            total_requests = sum(w.total_requests for w in self.limiter.windows.values())

            return sliding_window_counter_pb2.GetClusterStatusResponse(
                node_id=self.limiter.node_id,
                node_address=f"localhost:{self.limiter.port}",
                is_leader=self.limiter.is_leader,
                total_nodes=len(self.limiter.nodes),
                healthy_nodes=sum(1 for n in self.limiter.nodes.values() if n.is_healthy),
                total_limits=len(self.limiter.windows),
                total_requests_processed=total_requests,
                members=members,
            )


class NodeServicer(sliding_window_counter_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, limiter: SlidingWindowCounterRateLimiter):
        self.limiter = limiter

    async def SyncWindow(self, request, context):
        """Handle SyncWindow RPC."""
        return sliding_window_counter_pb2.SyncWindowResponse(success=True)

    async def IncrementCounter(self, request, context):
        """Handle IncrementCounter RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                window = self.limiter.windows[request.limit_id]
                if window.current_window_start == request.window_start:
                    window.current_count += request.increment
                    return sliding_window_counter_pb2.IncrementCounterResponse(
                        success=True,
                        new_count=window.current_count,
                    )
        return sliding_window_counter_pb2.IncrementCounterResponse(
            success=False,
            error="Window not found or mismatched",
        )

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.limiter.lock:
            if request.node_id in self.limiter.nodes:
                self.limiter.nodes[request.node_id].last_heartbeat = request.timestamp
                self.limiter.nodes[request.node_id].limits_count = request.limits_count

        return sliding_window_counter_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.limiter._current_time_ms(),
        )

    async def GetLocalWindows(self, request, context):
        """Handle GetLocalWindows RPC."""
        with self.limiter.lock:
            windows = [
                sliding_window_counter_pb2.WindowState(
                    limit_id=w.limit_id,
                    window_size_ms=w.window_size_ms,
                    max_requests=w.max_requests,
                    current_window_start=w.current_window_start,
                    current_count=w.current_count,
                    previous_window_start=w.previous_window_start,
                    previous_count=w.previous_count,
                    total_requests=w.total_requests,
                    total_allowed=w.total_allowed,
                    total_rejected=w.total_rejected,
                )
                for w in self.limiter.windows.values()
            ]
            return sliding_window_counter_pb2.GetLocalWindowsResponse(
                windows=windows,
                total_count=len(windows),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the sliding window counter rate limiter server."""
    limiter = SlidingWindowCounterRateLimiter(node_id, port, peers)
    await limiter.initialize()

    server = aio.server()
    sliding_window_counter_pb2_grpc.add_RateLimiterServiceServicer_to_server(
        RateLimiterServicer(limiter), server
    )
    sliding_window_counter_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(limiter), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Sliding Window Counter node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Sliding Window Counter Rate Limiter Node")
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
