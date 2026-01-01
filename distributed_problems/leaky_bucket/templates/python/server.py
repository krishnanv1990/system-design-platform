"""
Leaky Bucket Rate Limiter Implementation - Python Template

This template provides the basic structure for implementing a
distributed leaky bucket rate limiter.

Key concepts:
1. Requests enter a queue (bucket) with fixed capacity
2. Requests are processed (leak) at a constant rate
3. If bucket is full, new requests are rejected
4. Provides smooth, consistent output rate

Usage:
    python server.py --node-id node1 --port 50051 --peers node2:50052,node3:50053
"""

import argparse
import asyncio
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque

import grpc
from grpc import aio

# Generated protobuf imports (will be generated from leaky_bucket.proto)
import leaky_bucket_pb2
import leaky_bucket_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CAPACITY = 100
DEFAULT_LEAK_RATE = 10.0  # requests per second


@dataclass
class QueuedRequest:
    """A request waiting in the bucket queue."""
    request_id: str
    enqueue_time: int  # milliseconds


@dataclass
class BucketState:
    """State of a leaky bucket."""
    bucket_id: str
    capacity: int
    leak_rate: float
    queue: Deque[QueuedRequest] = field(default_factory=deque)
    last_leak_time: int = 0  # milliseconds
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    processed_requests: int = 0


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    node_id: str
    address: str
    is_healthy: bool = True
    buckets_count: int = 0
    last_heartbeat: int = 0


class LeakyBucketRateLimiter:
    """
    Leaky Bucket Rate Limiter implementation.

    TODO: Implement the core leaky bucket algorithm:
    1. leak() - Process requests from the queue at constant rate
    2. try_enqueue() - Attempt to add a request to the queue
    3. get_bucket() - Get or create a bucket
    4. background_leak() - Continuous background processing
    """

    def __init__(self, node_id: str, port: int, peers: List[str]):
        self.node_id = node_id
        self.port = port
        self.peers = peers
        self.lock = threading.RLock()

        # Bucket storage
        self.buckets: Dict[str, BucketState] = {}

        # Cluster state
        self.nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False

        # gRPC stubs for peer communication
        self.peer_stubs: Dict[str, leaky_bucket_pb2_grpc.NodeServiceStub] = {}

        # Background leak task
        self._running = False

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = leaky_bucket_pb2_grpc.NodeServiceStub(channel)

        # Register self
        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )

        # Start background leak processing
        self._running = True
        asyncio.create_task(self._background_leak())

        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def leak(self, bucket: BucketState) -> int:
        """
        Process requests from the queue (leak).

        TODO: Implement leaking:
        1. Calculate how many requests should have leaked since last check
        2. Remove that many requests from the front of the queue
        3. Update processed_requests counter
        4. Return number of requests leaked

        Returns:
            Number of requests processed (leaked)
        """
        now = self._current_time_ms()
        elapsed_ms = now - bucket.last_leak_time
        elapsed_seconds = elapsed_ms / 1000.0

        # Calculate how many requests should leak
        requests_to_leak = int(elapsed_seconds * bucket.leak_rate)

        if requests_to_leak <= 0:
            return 0

        # Leak requests from the queue
        leaked = 0
        while leaked < requests_to_leak and bucket.queue:
            bucket.queue.popleft()
            bucket.processed_requests += 1
            leaked += 1

        bucket.last_leak_time = now
        return leaked

    def try_enqueue(self, bucket: BucketState, request_id: Optional[str] = None) -> tuple:
        """
        Try to add a request to the bucket queue.

        TODO: Implement enqueueing:
        1. First, leak any pending requests
        2. Check if queue has space
        3. If yes, add request to queue and return (True, position, wait_time)
        4. If no, reject and return (False, 0, 0)

        Returns:
            Tuple of (allowed, queue_position, estimated_wait_ms)
        """
        with self.lock:
            # First, process any pending leaks
            self.leak(bucket)

            bucket.total_requests += 1

            # Check if queue is full
            if len(bucket.queue) >= bucket.capacity:
                bucket.rejected_requests += 1
                return (False, 0, 0)

            # Add to queue
            if not request_id:
                request_id = str(uuid.uuid4())

            queued_req = QueuedRequest(
                request_id=request_id,
                enqueue_time=self._current_time_ms(),
            )
            bucket.queue.append(queued_req)
            bucket.allowed_requests += 1

            # Calculate position and estimated wait
            position = len(bucket.queue)
            estimated_wait_ms = int((position / bucket.leak_rate) * 1000)

            return (True, position, estimated_wait_ms)

    def get_or_create_bucket(
        self,
        bucket_id: str,
        capacity: int = DEFAULT_CAPACITY,
        leak_rate: float = DEFAULT_LEAK_RATE
    ) -> BucketState:
        """Get an existing bucket or create a new one."""
        with self.lock:
            if bucket_id not in self.buckets:
                self.buckets[bucket_id] = BucketState(
                    bucket_id=bucket_id,
                    capacity=capacity,
                    leak_rate=leak_rate,
                    last_leak_time=self._current_time_ms(),
                )
                logger.info(f"Created bucket {bucket_id} with capacity={capacity}, leak_rate={leak_rate}")
            return self.buckets[bucket_id]

    async def _background_leak(self):
        """Background task to continuously process leaks."""
        while self._running:
            with self.lock:
                for bucket in self.buckets.values():
                    self.leak(bucket)
            await asyncio.sleep(0.1)  # Check every 100ms


class RateLimiterServicer(leaky_bucket_pb2_grpc.RateLimiterServiceServicer):
    """gRPC service implementation for rate limiting."""

    def __init__(self, limiter: LeakyBucketRateLimiter):
        self.limiter = limiter

    async def AllowRequest(self, request, context):
        """Handle AllowRequest RPC."""
        bucket = self.limiter.get_or_create_bucket(request.bucket_id)

        allowed, position, estimated_wait = self.limiter.try_enqueue(
            bucket,
            request.request_id if request.request_id else None
        )

        return leaky_bucket_pb2.AllowRequestResponse(
            allowed=allowed,
            queue_position=position,
            estimated_wait_ms=estimated_wait,
            served_by=self.limiter.node_id,
        )

    async def GetBucketStatus(self, request, context):
        """Handle GetBucketStatus RPC."""
        with self.limiter.lock:
            if request.bucket_id in self.limiter.buckets:
                bucket = self.limiter.buckets[request.bucket_id]
                self.limiter.leak(bucket)

                queued = [
                    leaky_bucket_pb2.QueuedRequest(
                        request_id=q.request_id,
                        enqueue_time=q.enqueue_time,
                    )
                    for q in bucket.queue
                ]

                return leaky_bucket_pb2.GetBucketStatusResponse(
                    bucket=leaky_bucket_pb2.BucketState(
                        bucket_id=bucket.bucket_id,
                        queue_size=len(bucket.queue),
                        capacity=bucket.capacity,
                        leak_rate=bucket.leak_rate,
                        last_leak_time=bucket.last_leak_time,
                        total_requests=bucket.total_requests,
                        allowed_requests=bucket.allowed_requests,
                        rejected_requests=bucket.rejected_requests,
                        processed_requests=bucket.processed_requests,
                    ),
                    found=True,
                    queued_requests=queued,
                )
            return leaky_bucket_pb2.GetBucketStatusResponse(found=False)

    async def ConfigureBucket(self, request, context):
        """Handle ConfigureBucket RPC."""
        config = request.config
        with self.limiter.lock:
            if config.bucket_id in self.limiter.buckets and not request.overwrite:
                return leaky_bucket_pb2.ConfigureBucketResponse(
                    success=False,
                    error="Bucket already exists",
                )

            bucket = self.limiter.get_or_create_bucket(
                config.bucket_id,
                config.capacity or DEFAULT_CAPACITY,
                config.leak_rate or DEFAULT_LEAK_RATE,
            )

            if request.overwrite:
                bucket.capacity = config.capacity or bucket.capacity
                bucket.leak_rate = config.leak_rate or bucket.leak_rate

            return leaky_bucket_pb2.ConfigureBucketResponse(
                success=True,
                bucket=leaky_bucket_pb2.BucketState(
                    bucket_id=bucket.bucket_id,
                    queue_size=len(bucket.queue),
                    capacity=bucket.capacity,
                    leak_rate=bucket.leak_rate,
                    last_leak_time=bucket.last_leak_time,
                ),
            )

    async def DeleteBucket(self, request, context):
        """Handle DeleteBucket RPC."""
        with self.limiter.lock:
            if request.bucket_id in self.limiter.buckets:
                del self.limiter.buckets[request.bucket_id]
                return leaky_bucket_pb2.DeleteBucketResponse(success=True)
            return leaky_bucket_pb2.DeleteBucketResponse(
                success=False,
                error="Bucket not found",
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return leaky_bucket_pb2.GetLeaderResponse(
            node_id=self.limiter.node_id,
            node_address=f"localhost:{self.limiter.port}",
            is_leader=self.limiter.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.limiter.lock:
            members = [
                leaky_bucket_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    buckets_count=n.buckets_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.limiter.nodes.values()
            ]

            total_queued = sum(len(b.queue) for b in self.limiter.buckets.values())
            total_processed = sum(b.processed_requests for b in self.limiter.buckets.values())

            return leaky_bucket_pb2.GetClusterStatusResponse(
                node_id=self.limiter.node_id,
                node_address=f"localhost:{self.limiter.port}",
                is_leader=self.limiter.is_leader,
                total_nodes=len(self.limiter.nodes),
                healthy_nodes=sum(1 for n in self.limiter.nodes.values() if n.is_healthy),
                total_buckets=len(self.limiter.buckets),
                total_queued_requests=total_queued,
                total_processed_requests=total_processed,
                members=members,
            )


class NodeServicer(leaky_bucket_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, limiter: LeakyBucketRateLimiter):
        self.limiter = limiter

    async def SyncBucket(self, request, context):
        """Handle SyncBucket RPC."""
        return leaky_bucket_pb2.SyncBucketResponse(success=True)

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.limiter.lock:
            if request.node_id in self.limiter.nodes:
                self.limiter.nodes[request.node_id].last_heartbeat = request.timestamp
                self.limiter.nodes[request.node_id].buckets_count = request.buckets_count

        return leaky_bucket_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.limiter._current_time_ms(),
        )

    async def GetLocalBuckets(self, request, context):
        """Handle GetLocalBuckets RPC."""
        with self.limiter.lock:
            buckets = [
                leaky_bucket_pb2.BucketState(
                    bucket_id=b.bucket_id,
                    queue_size=len(b.queue),
                    capacity=b.capacity,
                    leak_rate=b.leak_rate,
                    last_leak_time=b.last_leak_time,
                    total_requests=b.total_requests,
                    allowed_requests=b.allowed_requests,
                    rejected_requests=b.rejected_requests,
                    processed_requests=b.processed_requests,
                )
                for b in self.limiter.buckets.values()
            ]
            return leaky_bucket_pb2.GetLocalBucketsResponse(
                buckets=buckets,
                total_count=len(buckets),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the leaky bucket rate limiter server."""
    limiter = LeakyBucketRateLimiter(node_id, port, peers)
    await limiter.initialize()

    server = aio.server()
    leaky_bucket_pb2_grpc.add_RateLimiterServiceServicer_to_server(
        RateLimiterServicer(limiter), server
    )
    leaky_bucket_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(limiter), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Leaky Bucket node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        limiter._running = False
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Leaky Bucket Rate Limiter Node")
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
