"""
Token Bucket Rate Limiter Implementation - Python Template

This template provides the basic structure for implementing a
distributed token bucket rate limiter.

Key concepts:
1. Bucket holds tokens up to a maximum capacity
2. Tokens are added at a fixed refill rate
3. Each request consumes tokens
4. Insufficient tokens = request rejected

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

# Generated protobuf imports (will be generated from token_bucket.proto)
import token_bucket_pb2
import token_bucket_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CAPACITY = 100
DEFAULT_REFILL_RATE = 10.0  # tokens per second


@dataclass
class BucketState:
    """State of a token bucket."""
    bucket_id: str
    capacity: int
    refill_rate: float
    current_tokens: float
    last_refill_time: int  # milliseconds
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0


@dataclass
class NodeInfo:
    """Information about a cluster node."""
    node_id: str
    address: str
    is_healthy: bool = True
    buckets_count: int = 0
    last_heartbeat: int = 0


class TokenBucketRateLimiter:
    """
    Token Bucket Rate Limiter implementation.

    TODO: Implement the core token bucket algorithm:
    1. refill_tokens() - Add tokens based on elapsed time
    2. try_consume() - Attempt to consume tokens for a request
    3. get_bucket() - Get or create a bucket
    4. sync_bucket() - Synchronize bucket state across nodes
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
        self.peer_stubs: Dict[str, token_bucket_pb2_grpc.NodeServiceStub] = {}

    async def initialize(self):
        """Initialize connections to peer nodes."""
        for peer in self.peers:
            if ".run.app" in peer:
                import ssl
                ssl_creds = grpc.ssl_channel_credentials()
                channel = aio.secure_channel(peer, ssl_creds)
            else:
                channel = aio.insecure_channel(peer)
            self.peer_stubs[peer] = token_bucket_pb2_grpc.NodeServiceStub(channel)

        # Register self
        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=f"localhost:{self.port}",
        )
        logger.info(f"Node {self.node_id} initialized with peers: {self.peers}")

    def _current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def refill_tokens(self, bucket: BucketState) -> None:
        """
        Refill tokens based on elapsed time.

        TODO: Implement token refilling:
        1. Calculate elapsed time since last refill
        2. Calculate tokens to add based on refill rate
        3. Cap tokens at bucket capacity
        4. Update last_refill_time
        """
        # TODO: Implement this method
        pass

    def try_consume(self, bucket: BucketState, tokens: int) -> bool:
        """
        Try to consume tokens from a bucket.

        TODO: Implement token consumption:
        1. Refill tokens first
        2. Check if enough tokens available
        3. If yes, consume tokens and return True
        4. If no, return False

        Args:
            bucket: The bucket to consume from
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        # TODO: Implement this method
        return False

    def get_or_create_bucket(
        self,
        bucket_id: str,
        capacity: int = DEFAULT_CAPACITY,
        refill_rate: float = DEFAULT_REFILL_RATE
    ) -> BucketState:
        """
        Get an existing bucket or create a new one.

        TODO: Implement bucket management:
        1. Check if bucket exists
        2. If not, create new bucket with given config
        3. Return the bucket
        """
        # TODO: Implement this method
        # For now, return a placeholder bucket
        return BucketState(
            bucket_id=bucket_id,
            capacity=capacity,
            refill_rate=refill_rate,
            current_tokens=0.0,
            last_refill_time=0,
        )

    def calculate_retry_after(self, bucket: BucketState, tokens_needed: int) -> int:
        """
        Calculate how long to wait before tokens are available.

        Args:
            bucket: The bucket
            tokens_needed: Number of tokens needed

        Returns:
            Milliseconds to wait
        """
        tokens_missing = tokens_needed - bucket.current_tokens
        if tokens_missing <= 0:
            return 0
        seconds_to_wait = tokens_missing / bucket.refill_rate
        return int(seconds_to_wait * 1000)


class RateLimiterServicer(token_bucket_pb2_grpc.RateLimiterServiceServicer):
    """gRPC service implementation for rate limiting."""

    def __init__(self, limiter: TokenBucketRateLimiter):
        self.limiter = limiter

    async def AllowRequest(self, request, context):
        """Handle AllowRequest RPC."""
        bucket = self.limiter.get_or_create_bucket(request.bucket_id)
        tokens_requested = request.tokens_requested or 1

        allowed = self.limiter.try_consume(bucket, tokens_requested)

        return token_bucket_pb2.AllowRequestResponse(
            allowed=allowed,
            tokens_remaining=bucket.current_tokens,
            retry_after_ms=0 if allowed else self.limiter.calculate_retry_after(bucket, tokens_requested),
            served_by=self.limiter.node_id,
        )

    async def GetBucketStatus(self, request, context):
        """Handle GetBucketStatus RPC."""
        with self.limiter.lock:
            if request.bucket_id in self.limiter.buckets:
                bucket = self.limiter.buckets[request.bucket_id]
                self.limiter.refill_tokens(bucket)
                return token_bucket_pb2.GetBucketStatusResponse(
                    bucket=token_bucket_pb2.BucketState(
                        bucket_id=bucket.bucket_id,
                        current_tokens=bucket.current_tokens,
                        capacity=bucket.capacity,
                        refill_rate=bucket.refill_rate,
                        last_refill_time=bucket.last_refill_time,
                        total_requests=bucket.total_requests,
                        allowed_requests=bucket.allowed_requests,
                        rejected_requests=bucket.rejected_requests,
                    ),
                    found=True,
                )
            return token_bucket_pb2.GetBucketStatusResponse(found=False)

    async def ConfigureBucket(self, request, context):
        """Handle ConfigureBucket RPC."""
        config = request.config
        with self.limiter.lock:
            if config.bucket_id in self.limiter.buckets and not request.overwrite:
                return token_bucket_pb2.ConfigureBucketResponse(
                    success=False,
                    error="Bucket already exists",
                )

            bucket = self.limiter.get_or_create_bucket(
                config.bucket_id,
                config.capacity or DEFAULT_CAPACITY,
                config.refill_rate or DEFAULT_REFILL_RATE,
            )

            if request.overwrite:
                bucket.capacity = config.capacity or bucket.capacity
                bucket.refill_rate = config.refill_rate or bucket.refill_rate

            return token_bucket_pb2.ConfigureBucketResponse(
                success=True,
                bucket=token_bucket_pb2.BucketState(
                    bucket_id=bucket.bucket_id,
                    current_tokens=bucket.current_tokens,
                    capacity=bucket.capacity,
                    refill_rate=bucket.refill_rate,
                    last_refill_time=bucket.last_refill_time,
                ),
            )

    async def DeleteBucket(self, request, context):
        """Handle DeleteBucket RPC."""
        with self.limiter.lock:
            if request.bucket_id in self.limiter.buckets:
                del self.limiter.buckets[request.bucket_id]
                return token_bucket_pb2.DeleteBucketResponse(success=True)
            return token_bucket_pb2.DeleteBucketResponse(
                success=False,
                error="Bucket not found",
            )

    async def GetLeader(self, request, context):
        """Handle GetLeader RPC."""
        return token_bucket_pb2.GetLeaderResponse(
            node_id=self.limiter.node_id,
            node_address=f"localhost:{self.limiter.port}",
            is_leader=self.limiter.is_leader,
        )

    async def GetClusterStatus(self, request, context):
        """Handle GetClusterStatus RPC."""
        with self.limiter.lock:
            members = [
                token_bucket_pb2.NodeInfo(
                    node_id=n.node_id,
                    address=n.address,
                    is_healthy=n.is_healthy,
                    buckets_count=n.buckets_count,
                    last_heartbeat=n.last_heartbeat,
                )
                for n in self.limiter.nodes.values()
            ]

            total_requests = sum(b.total_requests for b in self.limiter.buckets.values())

            return token_bucket_pb2.GetClusterStatusResponse(
                node_id=self.limiter.node_id,
                node_address=f"localhost:{self.limiter.port}",
                is_leader=self.limiter.is_leader,
                total_nodes=len(self.limiter.nodes),
                healthy_nodes=sum(1 for n in self.limiter.nodes.values() if n.is_healthy),
                total_buckets=len(self.limiter.buckets),
                total_requests_processed=total_requests,
                members=members,
            )


class NodeServicer(token_bucket_pb2_grpc.NodeServiceServicer):
    """gRPC service for inter-node communication."""

    def __init__(self, limiter: TokenBucketRateLimiter):
        self.limiter = limiter

    async def SyncBucket(self, request, context):
        """Handle SyncBucket RPC."""
        # TODO: Implement bucket synchronization
        return token_bucket_pb2.SyncBucketResponse(success=True)

    async def Heartbeat(self, request, context):
        """Handle Heartbeat RPC."""
        with self.limiter.lock:
            if request.node_id in self.limiter.nodes:
                self.limiter.nodes[request.node_id].last_heartbeat = request.timestamp
                self.limiter.nodes[request.node_id].buckets_count = request.buckets_count

        return token_bucket_pb2.HeartbeatResponse(
            acknowledged=True,
            timestamp=self.limiter._current_time_ms(),
        )

    async def GetLocalBuckets(self, request, context):
        """Handle GetLocalBuckets RPC."""
        with self.limiter.lock:
            buckets = [
                token_bucket_pb2.BucketState(
                    bucket_id=b.bucket_id,
                    current_tokens=b.current_tokens,
                    capacity=b.capacity,
                    refill_rate=b.refill_rate,
                    last_refill_time=b.last_refill_time,
                    total_requests=b.total_requests,
                    allowed_requests=b.allowed_requests,
                    rejected_requests=b.rejected_requests,
                )
                for b in self.limiter.buckets.values()
            ]
            return token_bucket_pb2.GetLocalBucketsResponse(
                buckets=buckets,
                total_count=len(buckets),
            )


# =============================================================================
# Main Entry Point
# =============================================================================

async def serve(node_id: str, port: int, peers: List[str]):
    """Start the token bucket rate limiter server."""
    limiter = TokenBucketRateLimiter(node_id, port, peers)
    await limiter.initialize()

    server = aio.server()
    token_bucket_pb2_grpc.add_RateLimiterServiceServicer_to_server(
        RateLimiterServicer(limiter), server
    )
    token_bucket_pb2_grpc.add_NodeServiceServicer_to_server(
        NodeServicer(limiter), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    logger.info(f"Starting Token Bucket node {node_id} on {listen_addr}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(5)


def main():
    parser = argparse.ArgumentParser(description="Token Bucket Rate Limiter Node")
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
