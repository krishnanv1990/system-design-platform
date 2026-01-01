/**
 * Token Bucket Rate Limiter - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * token bucket rate limiter.
 *
 * Key concepts:
 * 1. Token Bucket - Requests consume tokens; tokens refill at a fixed rate
 * 2. Burst Capacity - Maximum tokens that can accumulate
 * 3. Refill Rate - How quickly tokens are replenished
 * 4. Distributed Coordination - Share state across nodes
 *
 * Usage:
 *     java TokenBucketServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.tokenbucket;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

public class TokenBucketServer {
    private static final Logger logger = Logger.getLogger(TokenBucketServer.class.getName());

    /**
     * BucketState holds the state of a token bucket.
     */
    public static class BucketState {
        public final String bucketId;
        public double tokens;
        public double capacity;
        public double refillRate;
        public long lastRefillTime;
        public final ReentrantLock lock = new ReentrantLock();

        public BucketState(String bucketId, double capacity, double refillRate) {
            this.bucketId = bucketId;
            this.tokens = capacity;
            this.capacity = capacity;
            this.refillRate = refillRate;
            this.lastRefillTime = System.currentTimeMillis();
        }
    }

    /**
     * TokenBucketRateLimiter implements the token bucket algorithm.
     */
    public static class TokenBucketRateLimiter extends RateLimiterServiceGrpc.RateLimiterServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, BucketState> buckets = new ConcurrentHashMap<>();
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public TokenBucketRateLimiter(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, NodeServiceGrpc.newBlockingStub(channel));
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        /**
         * Get or create a bucket with the given configuration.
         */
        public BucketState getOrCreateBucket(String bucketId, double capacity, double refillRate) {
            return buckets.computeIfAbsent(bucketId,
                id -> new BucketState(id, capacity, refillRate));
        }

        /**
         * Refill tokens based on elapsed time.
         *
         * TODO: Implement token refill logic:
         * 1. Calculate time elapsed since last refill
         * 2. Add tokens based on refill rate: tokens += elapsed_seconds * refill_rate
         * 3. Cap tokens at capacity
         * 4. Update last refill time
         */
        public void refillTokens(BucketState bucket) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("refillTokens not implemented");
        }

        /**
         * Try to consume tokens from the bucket.
         *
         * TODO: Implement token consumption:
         * 1. First refill tokens based on elapsed time
         * 2. Check if enough tokens are available
         * 3. If yes, deduct tokens and return true
         * 4. If no, return false (request should be rate limited)
         */
        public boolean tryConsume(BucketState bucket, double tokens) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("tryConsume not implemented");
        }

        // =========================================================================
        // RateLimiterService RPC Implementations
        // =========================================================================

        @Override
        public void createBucket(TokenBucket.CreateBucketRequest request,
                                StreamObserver<TokenBucket.CreateBucketResponse> responseObserver) {
            BucketState bucket = getOrCreateBucket(
                request.getBucketId(),
                request.getConfig().getCapacity(),
                request.getConfig().getRefillRate()
            );

            bucket.lock.lock();
            try {
                responseObserver.onNext(TokenBucket.CreateBucketResponse.newBuilder()
                    .setSuccess(true)
                    .setState(TokenBucket.BucketState.newBuilder()
                        .setBucketId(bucket.bucketId)
                        .setCurrentTokens(bucket.tokens)
                        .setCapacity(bucket.capacity)
                        .setRefillRate(bucket.refillRate)
                        .setLastRefillTime(bucket.lastRefillTime)
                        .build())
                    .build());
            } finally {
                bucket.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void allowRequest(TokenBucket.AllowRequestRequest request,
                                StreamObserver<TokenBucket.AllowRequestResponse> responseObserver) {
            BucketState bucket = buckets.get(request.getBucketId());

            if (bucket == null) {
                responseObserver.onNext(TokenBucket.AllowRequestResponse.newBuilder()
                    .setAllowed(false)
                    .setError("Bucket not found")
                    .build());
                responseObserver.onCompleted();
                return;
            }

            double tokens = request.getTokensRequested();
            if (tokens == 0) tokens = 1;

            boolean allowed = tryConsume(bucket, tokens);

            bucket.lock.lock();
            double remaining;
            try {
                remaining = bucket.tokens;
            } finally {
                bucket.lock.unlock();
            }

            responseObserver.onNext(TokenBucket.AllowRequestResponse.newBuilder()
                .setAllowed(allowed)
                .setRemainingTokens(remaining)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getBucketState(TokenBucket.GetBucketStateRequest request,
                                  StreamObserver<TokenBucket.GetBucketStateResponse> responseObserver) {
            BucketState bucket = buckets.get(request.getBucketId());

            if (bucket == null) {
                responseObserver.onNext(TokenBucket.GetBucketStateResponse.newBuilder().build());
                responseObserver.onCompleted();
                return;
            }

            refillTokens(bucket);

            bucket.lock.lock();
            try {
                responseObserver.onNext(TokenBucket.GetBucketStateResponse.newBuilder()
                    .setState(TokenBucket.BucketState.newBuilder()
                        .setBucketId(bucket.bucketId)
                        .setCurrentTokens(bucket.tokens)
                        .setCapacity(bucket.capacity)
                        .setRefillRate(bucket.refillRate)
                        .setLastRefillTime(bucket.lastRefillTime)
                        .build())
                    .build());
            } finally {
                bucket.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteBucket(TokenBucket.DeleteBucketRequest request,
                                StreamObserver<TokenBucket.DeleteBucketResponse> responseObserver) {
            BucketState removed = buckets.remove(request.getBucketId());
            responseObserver.onNext(TokenBucket.DeleteBucketResponse.newBuilder()
                .setSuccess(removed != null)
                .setError(removed == null ? "Bucket not found" : "")
                .build());
            responseObserver.onCompleted();
        }

        public String getNodeId() {
            return nodeId;
        }
    }

    /**
     * NodeService implementation for peer communication.
     */
    public static class NodeServiceImpl extends NodeServiceGrpc.NodeServiceImplBase {
        private final TokenBucketRateLimiter limiter;

        public NodeServiceImpl(TokenBucketRateLimiter limiter) {
            this.limiter = limiter;
        }

        @Override
        public void syncState(TokenBucket.SyncStateRequest request,
                             StreamObserver<TokenBucket.SyncStateResponse> responseObserver) {
            for (TokenBucket.BucketState state : request.getStatesList()) {
                BucketState bucket = limiter.buckets.get(state.getBucketId());
                if (bucket != null) {
                    bucket.lock.lock();
                    try {
                        // Use state with lower token count (more conservative)
                        if (state.getCurrentTokens() < bucket.tokens) {
                            bucket.tokens = state.getCurrentTokens();
                        }
                    } finally {
                        bucket.lock.unlock();
                    }
                } else {
                    limiter.buckets.put(state.getBucketId(),
                        new BucketState(state.getBucketId(), state.getCapacity(), state.getRefillRate()));
                }
            }

            responseObserver.onNext(TokenBucket.SyncStateResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(limiter.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(TokenBucket.HeartbeatRequest request,
                             StreamObserver<TokenBucket.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(TokenBucket.HeartbeatResponse.newBuilder()
                .setAcknowledged(true)
                .setTimestamp(System.currentTimeMillis())
                .build());
            responseObserver.onCompleted();
        }
    }

    // =============================================================================
    // Main Entry Point
    // =============================================================================

    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = null;
        int port = 50051;
        String peersStr = "";

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--node-id":
                    nodeId = args[++i];
                    break;
                case "--port":
                    port = Integer.parseInt(args[++i]);
                    break;
                case "--peers":
                    peersStr = args[++i];
                    break;
            }
        }

        if (nodeId == null) {
            System.err.println("Usage: java TokenBucketServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        TokenBucketRateLimiter limiter = new TokenBucketRateLimiter(nodeId, port, peers);
        limiter.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(limiter)
                .addService(new NodeServiceImpl(limiter))
                .build()
                .start();

        logger.info("Starting Token Bucket Rate Limiter node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
