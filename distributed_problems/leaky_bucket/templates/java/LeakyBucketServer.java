/**
 * Leaky Bucket Rate Limiter - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * leaky bucket rate limiter.
 *
 * Key concepts:
 * 1. Leaky Bucket - Requests enter a queue that drains at a constant rate
 * 2. Queue Size - Maximum number of pending requests
 * 3. Leak Rate - Constant rate at which requests are processed
 * 4. Overflow - When queue is full, new requests are rejected
 *
 * Usage:
 *     java LeakyBucketServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.leakybucket;

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

public class LeakyBucketServer {
    private static final Logger logger = Logger.getLogger(LeakyBucketServer.class.getName());

    /**
     * BucketState holds the state of a leaky bucket.
     */
    public static class BucketState {
        public final String bucketId;
        public double queueSize;
        public double capacity;
        public double leakRate;
        public long lastLeakTime;
        public final ReentrantLock lock = new ReentrantLock();

        public BucketState(String bucketId, double capacity, double leakRate) {
            this.bucketId = bucketId;
            this.queueSize = 0;
            this.capacity = capacity;
            this.leakRate = leakRate;
            this.lastLeakTime = System.currentTimeMillis();
        }
    }

    /**
     * LeakyBucketRateLimiter implements the leaky bucket algorithm.
     */
    public static class LeakyBucketRateLimiter extends RateLimiterServiceGrpc.RateLimiterServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, BucketState> buckets = new ConcurrentHashMap<>();
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public LeakyBucketRateLimiter(String nodeId, int port, List<String> peers) {
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
        public BucketState getOrCreateBucket(String bucketId, double capacity, double leakRate) {
            return buckets.computeIfAbsent(bucketId,
                id -> new BucketState(id, capacity, leakRate));
        }

        /**
         * Leak the bucket based on elapsed time.
         *
         * TODO: Implement leak logic:
         * 1. Calculate time elapsed since last leak
         * 2. Calculate how many requests have leaked: leaked = elapsed_seconds * leak_rate
         * 3. Reduce queue size by leaked amount (minimum 0)
         * 4. Update last leak time
         */
        public void leak(BucketState bucket) {
            bucket.lock.lock();
            try {
                long now = System.currentTimeMillis();
                double elapsed = (now - bucket.lastLeakTime) / 1000.0;

                // TODO: Calculate how many items have leaked
                double leaked = elapsed * bucket.leakRate;

                // TODO: Reduce queue size, but don't go below 0
                bucket.queueSize = Math.max(0, bucket.queueSize - leaked);

                bucket.lastLeakTime = now;
            } finally {
                bucket.lock.unlock();
            }
        }

        /**
         * Try to enqueue a request.
         *
         * TODO: Implement enqueue logic:
         * 1. First leak the bucket based on elapsed time
         * 2. Check if queue has space (queue_size < capacity)
         * 3. If yes, increment queue size and return true
         * 4. If no, return false (request should be rejected)
         */
        public boolean tryEnqueue(BucketState bucket, double count) {
            leak(bucket);

            bucket.lock.lock();
            try {
                // TODO: Check if there's room in the queue
                if (bucket.queueSize + count <= bucket.capacity) {
                    bucket.queueSize += count;
                    return true;
                }
                return false;
            } finally {
                bucket.lock.unlock();
            }
        }

        // =========================================================================
        // RateLimiterService RPC Implementations
        // =========================================================================

        @Override
        public void createBucket(LeakyBucket.CreateBucketRequest request,
                                StreamObserver<LeakyBucket.CreateBucketResponse> responseObserver) {
            BucketState bucket = getOrCreateBucket(
                request.getBucketId(),
                request.getConfig().getCapacity(),
                request.getConfig().getLeakRate()
            );

            bucket.lock.lock();
            try {
                responseObserver.onNext(LeakyBucket.CreateBucketResponse.newBuilder()
                    .setSuccess(true)
                    .setState(LeakyBucket.BucketState.newBuilder()
                        .setBucketId(bucket.bucketId)
                        .setQueueSize(bucket.queueSize)
                        .setCapacity(bucket.capacity)
                        .setLeakRate(bucket.leakRate)
                        .setLastLeakTime(bucket.lastLeakTime)
                        .build())
                    .build());
            } finally {
                bucket.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void allowRequest(LeakyBucket.AllowRequestRequest request,
                                StreamObserver<LeakyBucket.AllowRequestResponse> responseObserver) {
            BucketState bucket = buckets.get(request.getBucketId());

            if (bucket == null) {
                responseObserver.onNext(LeakyBucket.AllowRequestResponse.newBuilder()
                    .setAllowed(false)
                    .setError("Bucket not found")
                    .build());
                responseObserver.onCompleted();
                return;
            }

            double count = request.getCount();
            if (count == 0) count = 1;

            boolean allowed = tryEnqueue(bucket, count);

            bucket.lock.lock();
            double queueSize, capacity;
            try {
                queueSize = bucket.queueSize;
                capacity = bucket.capacity;
            } finally {
                bucket.lock.unlock();
            }

            responseObserver.onNext(LeakyBucket.AllowRequestResponse.newBuilder()
                .setAllowed(allowed)
                .setCurrentQueue(queueSize)
                .setRemainingSpace(capacity - queueSize)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getBucketState(LeakyBucket.GetBucketStateRequest request,
                                  StreamObserver<LeakyBucket.GetBucketStateResponse> responseObserver) {
            BucketState bucket = buckets.get(request.getBucketId());

            if (bucket == null) {
                responseObserver.onNext(LeakyBucket.GetBucketStateResponse.newBuilder().build());
                responseObserver.onCompleted();
                return;
            }

            leak(bucket);

            bucket.lock.lock();
            try {
                responseObserver.onNext(LeakyBucket.GetBucketStateResponse.newBuilder()
                    .setState(LeakyBucket.BucketState.newBuilder()
                        .setBucketId(bucket.bucketId)
                        .setQueueSize(bucket.queueSize)
                        .setCapacity(bucket.capacity)
                        .setLeakRate(bucket.leakRate)
                        .setLastLeakTime(bucket.lastLeakTime)
                        .build())
                    .build());
            } finally {
                bucket.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteBucket(LeakyBucket.DeleteBucketRequest request,
                                StreamObserver<LeakyBucket.DeleteBucketResponse> responseObserver) {
            BucketState removed = buckets.remove(request.getBucketId());
            responseObserver.onNext(LeakyBucket.DeleteBucketResponse.newBuilder()
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
        private final LeakyBucketRateLimiter limiter;

        public NodeServiceImpl(LeakyBucketRateLimiter limiter) {
            this.limiter = limiter;
        }

        @Override
        public void syncState(LeakyBucket.SyncStateRequest request,
                             StreamObserver<LeakyBucket.SyncStateResponse> responseObserver) {
            for (LeakyBucket.BucketState state : request.getStatesList()) {
                BucketState bucket = limiter.buckets.get(state.getBucketId());
                if (bucket != null) {
                    bucket.lock.lock();
                    try {
                        // Use state with higher queue size (more conservative)
                        if (state.getQueueSize() > bucket.queueSize) {
                            bucket.queueSize = state.getQueueSize();
                        }
                    } finally {
                        bucket.lock.unlock();
                    }
                } else {
                    BucketState newBucket = new BucketState(
                        state.getBucketId(), state.getCapacity(), state.getLeakRate());
                    newBucket.queueSize = state.getQueueSize();
                    limiter.buckets.put(state.getBucketId(), newBucket);
                }
            }

            responseObserver.onNext(LeakyBucket.SyncStateResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(limiter.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(LeakyBucket.HeartbeatRequest request,
                             StreamObserver<LeakyBucket.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(LeakyBucket.HeartbeatResponse.newBuilder()
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
            System.err.println("Usage: java LeakyBucketServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        LeakyBucketRateLimiter limiter = new LeakyBucketRateLimiter(nodeId, port, peers);
        limiter.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(limiter)
                .addService(new NodeServiceImpl(limiter))
                .build()
                .start();

        logger.info("Starting Leaky Bucket Rate Limiter node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
