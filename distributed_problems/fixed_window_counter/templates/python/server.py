"""
Fixed Window Counter Rate Limiter Implementation - Python Template

This template provides the basic structure for implementing a
distributed fixed window counter rate limiter.

Key concepts:
1. Time is divided into fixed windows (e.g., 1 minute each)
2. Each window has a counter tracking requests
3. Counter resets when new window starts
4. Requests rejected when counter exceeds limit

Note: This algorithm has the "boundary problem" - traffic can spike at window edges

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

# Generated protobuf imports (will be generated from fixed_window_counter.proto)
import fixed_window_counter_pb2
import fixed_window_counter_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_REQUESTS = 100
DEFAULT_WINDOW_SIZE_MS = 60000  # 1 minute


@dataclass
class WindowState:
    """State of a fixed window counter."""
    limit_id: str
    max_requests: int
    window_size_ms: int
    window_start: int  # milliseconds
    window_end: int  # milliseconds
    current_count: int = 0
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


class FixedWindowRateLimiter:
    """
    Fixed Window Counter Rate Limiter implementation.

    TODO: Implement the core fixed window algorithm:
    1. get_current_window() - Calculate current window boundaries
    2. check_and_increment() - Check limit and increment counter atomically
    3. rotate_window() - Reset counter when entering new window
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
        self.peer_stubs: Dict[str, fixed_window_counter_pb2_grpc.NodeServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = fixed_window_counter_pb2_grpc.NodeServiceStub(channel)

        # Register self
        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def get_window_boundaries(self, window_size_ms: int, timestamp_ms: Optional[int] = None) -> tuple:
        """
        Calculate window boundaries for a given timestamp.

        TODO: Implement window boundary calculation:
        1. Align to window size boundaries
        2. Return (window_start, window_end)
        """
        if timestamp_ms is None:
            timestamp_ms = self._current_time_ms()

        # Align to window boundaries
        window_start = (timestamp_ms // window_size_ms) * window_size_ms
        window_end = window_start + window_size_ms

        return (window_start, window_end)

    def maybe_rotate_window(self, window: WindowState) -> bool:
        """
        Check if window needs rotation and rotate if necessary.

        TODO: Implement window rotation:
        1. Check if current time is past window_end
        2. If yes, calculate new window boundaries
        3. Reset counter to 0
        4. Return True if rotated, False otherwise
        """
        now = self._current_time_ms()

        if now >= window.window_end:
            # Rotate to new window
            new_start, new_end = self.get_window_boundaries(window.window_size_ms, now)
            window.window_start = new_start
            window.window_end = new_end
            window.current_count = 0
            return True

        return False

    def check_and_increment(self, window: WindowState, cost: int = 1) -> tuple:
        """
        Check if request is allowed and increment counter.

        TODO: Implement check and increment:
        1. Rotate window if necessary
        2. Check if current_count + cost <= max_requests
        3. If yes, increment and return (True, new_count, remaining)
        4. If no, return (False, current_count, 0)

        Returns:
            Tuple of (allowed, current_count, remaining)
        """
        with self.lock:
            self.maybe_rotate_window(window)

            window.total_requests += 1

            if window.current_count + cost <= window.max_requests:
                window.current_count += cost
                window.total_allowed += 1
                remaining = window.max_requests - window.current_count
                return (True, window.current_count, remaining)
            else:
                window.total_rejected += 1
                return (False, window.current_count, 0)

    def get_or_create_window(
        self,
        limit_id: str,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_size_ms: int = DEFAULT_WINDOW_SIZE_MS
    ) -> WindowState:
        """Get an existing window or create a new one."""
        with self.lock:
            if limit_id not in self.windows:
                window_start, window_end = self.get_window_boundaries(window_size_ms)
                self.windows[limit_id] = WindowState(
                    limit_id=limit_id,
                    max_requests=max_requests,
                    window_size_ms=window_size_ms,
                    window_start=window_start,
                    window_end=window_end,
                )
                logger.info(f"Created window {limit_id} with max={max_requests}, size={window_size_ms}ms")
            return self.windows[limit_id]


class RateLimiterServicer(fixed_window_counter_pb2_grpc.RateLimiterServiceServicer):
    """gRPC service implementation for rate limiting."""

    def __init__(self, limiter: FixedWindowRateLimiter):
        self.limiter = limiter

    async def AllowRequest(self, request, context):
        """Handle AllowRequest RPC."""
        window = self.limiter.get_or_create_window(request.limit_id)
        cost = request.cost or 1

        allowed, current_count, remaining = self.limiter.check_and_increment(window, cost)

        return fixed_window_counter_pb2.AllowRequestResponse(
            allowed=allowed,
            current_count=current_count,
            remaining=remaining,
            reset_at=window.window_end,
            served_by=self.limiter.node_id,
        )

    async def GetWindowStatus(self, request, context):
        """Handle GetWindowStatus RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                window = self.limiter.windows[request.limit_id]
                self.limiter.maybe_rotate_window(window)

                return fixed_window_counter_pb2.GetWindowStatusResponse(
                    window=fixed_window_counter_pb2.WindowState(
                        limit_id=window.limit_id,
                        window_start=window.window_start,
                        window_end=window.window_end,
                        current_count=window.current_count,
                        max_requests=window.max_requests,
                        window_size_ms=window.window_size_ms,
                        total_requests=window.total_requests,
                        total_allowed=window.total_allowed,
                        total_rejected=window.total_rejected,
                    ),
                    found=True,
                )
            return fixed_window_counter_pb2.GetWindowStatusResponse(found=False)

    async def ConfigureLimit(self, request, context):
        """Handle ConfigureLimit RPC."""
        config = request.config
        with self.limiter.lock:
            if config.limit_id in self.limiter.windows and not request.overwrite:
                return fixed_window_counter_pb2.ConfigureLimitResponse(
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

            return fixed_window_counter_pb2.ConfigureLimitResponse(
                success=True,
                window=fixed_window_counter_pb2.WindowState(
                    limit_id=window.limit_id,
                    window_start=window.window_start,
                    window_end=window.window_end,
                    current_count=window.current_count,
                    max_requests=window.max_requests,
                    window_size_ms=window.window_size_ms,
                ),
            )

    async def DeleteLimit(self, request, context):
        """Handle DeleteLimit RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                del self.limiter.windows[request.limit_id]
                return fixed_window_counter_pb2.DeleteLimitResponse(success=True)
            return fixed_window_counter_pb2.DeleteLimitResponse(
                success=False,
                error="Limit not found",
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return fixed_window_counter_pb2.GetLeaderResponse(
            node_id=self.limiter.node_id,
            node_address=f"localhost:{self.limiter.port}",
            is_leader=self.limiter.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.limiter.lock:
            members = [
                fixed_window_counter_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    limits_count=n.limits_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.limiter.nodes.values()
            ]

            total_requests = sum(w.total_requests for w in self.limiter.windows.values())

            return fixed_window_counter_pb2.GetClusterStatusResponse(
                node_id=self.limiter.node_id,
                node_address=f"localhost:{self.limiter.port}",
                is_leader=self.limiter.is_leader,
                total_nodes=len(self.limiter.nodes),
                healthy_nodes=sum(1 for n in self.limiter.nodes.values() if n.is_healthy),
                total_limits=len(self.limiter.windows),
                total_requests_processed=total_requests,
                members=members,
            )


class NodeServicer(fixed_window_counter_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, limiter: FixedWindowRateLimiter):
        self.limiter = limiter

    async def SyncWindow(self, request, context):
        """Handle SyncWindow RPC."""
        return fixed_window_counter_pb2.SyncWindowResponse(success=True)

    async def IncrementCounter(self, request, context):
        """Handle IncrementCounter RPC."""
        with self.limiter.lock:
            if request.limit_id in self.limiter.windows:
                window = self.limiter.windows[request.limit_id]
                if window.window_start == request.window_start:
                    window.current_count += request.increment
                    return fixed_window_counter_pb2.IncrementCounterResponse(
                        success=True,
                        new_count=window.current_count,
                    )
        return fixed_window_counter_pb2.IncrementCounterResponse(
            success=False,
            error="Window not found or mismatched",
        )

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.limiter.lock:
            if request.node_id in self.limiter.nodes:
                self.limiter.nodes[request.node_id].last_heartbeat = request.timestamp
                self.limiter.nodes[request.node_id].limits_count = request.limits_count

        return fixed_window_counter_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.limiter._current_time_ms(),
        )

    async def GetLocalWindows(self, request, context):
        """Handle GetLocalWindows RPC."""
        with self.limiter.lock:
            windows = [
                fixed_window_counter_pb2.WindowState(
                    limit_id=w.limit_id,
                    window_start=w.window_start,
                    window_end=w.window_end,
                    current_count=w.current_count,
                    max_requests=w.max_requests,
                    window_size_ms=w.window_size_ms,
                    total_requests=w.total_requests,
                    total_allowed=w.total_allowed,
                    total_rejected=w.total_rejected,
                )
                for w in self.limiter.windows.values()
            ]
            return fixed_window_counter_pb2.GetLocalWindowsResponse(
                windows=windows,
                total_count=len(windows),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the fixed window rate limiter server."""
    limiter = FixedWindowRateLimiter(node_id, port, peers)
    await limiter.initialize()

    server = aio.server()
    fixed_window_counter_pb2_grpc.add_RateLimiterServiceServicer_to_server(
        RateLimiterServicer(limiter), server
    )
    fixed_window_counter_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(limiter), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Fixed Window Counter node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Fixed Window Counter Rate Limiter Node")
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
