/**
 * Sliding Window Log Rate Limiter - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * sliding window log rate limiter.
 *
 * Key concepts:
 * 1. Timestamp Log - Keep a log of request timestamps
 * 2. Sliding Window - Window slides with current time
 * 3. Precise Counting - Count requests in the sliding window
 * 4. Memory Usage - Need to clean up old timestamps
 *
 * Usage:
 *     java SlidingWindowLogServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.slidingwindowlog;

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

public class SlidingWindowLogServer {
    private static final Logger logger = Logger.getLogger(SlidingWindowLogServer.class.getName());

    /**
     * WindowState holds the state of a sliding window log.
     */
    public static class WindowState {
        public final String counterId;
        public final List<Long> timestamps;
        public long windowSizeMs;
        public long requestLimit;
        public final ReentrantLock lock = new ReentrantLock();

        public WindowState(String counterId, long windowSizeMs, long requestLimit) {
            this.counterId = counterId;
            this.timestamps = new ArrayList<>();
            this.windowSizeMs = windowSizeMs;
            this.requestLimit = requestLimit;
        }
    }

    /**
     * SlidingWindowLogRateLimiter implements the sliding window log algorithm.
     */
    public static class SlidingWindowLogRateLimiter extends RateLimiterServiceGrpc.RateLimiterServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, WindowState> counters = new ConcurrentHashMap<>();
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public SlidingWindowLogRateLimiter(String nodeId, int port, List<String> peers) {
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
         * Get or create a counter with the given configuration.
         */
        public WindowState getOrCreateCounter(String counterId, long windowSizeMs, long requestLimit) {
            return counters.computeIfAbsent(counterId,
                id -> new WindowState(id, windowSizeMs, requestLimit));
        }

        /**
         * Cleanup old timestamps outside the sliding window.
         *
         * TODO: Implement cleanup logic:
         * 1. Calculate the window start (current_time - window_size)
         * 2. Remove all timestamps before window start
         * 3. Maintain sorted order for efficient cleanup
         */
        public void cleanupOldTimestamps(WindowState counter) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("cleanupOldTimestamps not implemented");
        }

        /**
         * Count requests in the current sliding window.
         *
         * TODO: Implement counting logic:
         * 1. First cleanup old timestamps
         * 2. Return the count of remaining timestamps
         */
        public long countRequestsInWindow(WindowState counter) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("countRequestsInWindow not implemented");
        }

        /**
         * Try to record a request.
         *
         * TODO: Implement recording logic:
         * 1. Cleanup old timestamps
         * 2. Check if adding new request would exceed limit
         * 3. If within limit, add current timestamp and return true
         * 4. If would exceed, return false
         */
        public boolean tryRecord(WindowState counter, long count) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("tryRecord not implemented");
        }

        // =========================================================================
        // RateLimiterService RPC Implementations
        // =========================================================================

        @Override
        public void createCounter(SlidingWindowLog.CreateCounterRequest request,
                                 StreamObserver<SlidingWindowLog.CreateCounterResponse> responseObserver) {
            WindowState counter = getOrCreateCounter(
                request.getCounterId(),
                request.getConfig().getWindowSizeMs(),
                request.getConfig().getRequestLimit()
            );

            counter.lock.lock();
            try {
                SlidingWindowLog.WindowState.Builder stateBuilder = SlidingWindowLog.WindowState.newBuilder()
                    .setCounterId(counter.counterId)
                    .setWindowSizeMs(counter.windowSizeMs)
                    .setRequestLimit(counter.requestLimit);
                for (Long ts : counter.timestamps) {
                    stateBuilder.addTimestamps(ts);
                }

                responseObserver.onNext(SlidingWindowLog.CreateCounterResponse.newBuilder()
                    .setSuccess(true)
                    .setState(stateBuilder.build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void allowRequest(SlidingWindowLog.AllowRequestRequest request,
                                StreamObserver<SlidingWindowLog.AllowRequestResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(SlidingWindowLog.AllowRequestResponse.newBuilder()
                    .setAllowed(false)
                    .setError("Counter not found")
                    .build());
                responseObserver.onCompleted();
                return;
            }

            long count = request.getCount();
            if (count == 0) count = 1;

            boolean allowed = tryRecord(counter, count);
            long currentCount = countRequestsInWindow(counter);

            counter.lock.lock();
            long limit, oldestTs = 0;
            try {
                limit = counter.requestLimit;
                if (!counter.timestamps.isEmpty()) {
                    oldestTs = counter.timestamps.get(0);
                }
            } finally {
                counter.lock.unlock();
            }

            long retryAfter = 0;
            if (!allowed && oldestTs > 0) {
                retryAfter = Math.max(0, oldestTs + counter.windowSizeMs - System.currentTimeMillis());
            }

            responseObserver.onNext(SlidingWindowLog.AllowRequestResponse.newBuilder()
                .setAllowed(allowed)
                .setCurrentCount(currentCount)
                .setRemainingCount(limit - currentCount)
                .setRetryAfterMs(retryAfter)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getCounterState(SlidingWindowLog.GetCounterStateRequest request,
                                   StreamObserver<SlidingWindowLog.GetCounterStateResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(SlidingWindowLog.GetCounterStateResponse.newBuilder().build());
                responseObserver.onCompleted();
                return;
            }

            cleanupOldTimestamps(counter);

            counter.lock.lock();
            try {
                SlidingWindowLog.WindowState.Builder stateBuilder = SlidingWindowLog.WindowState.newBuilder()
                    .setCounterId(counter.counterId)
                    .setWindowSizeMs(counter.windowSizeMs)
                    .setRequestLimit(counter.requestLimit);
                for (Long ts : counter.timestamps) {
                    stateBuilder.addTimestamps(ts);
                }

                responseObserver.onNext(SlidingWindowLog.GetCounterStateResponse.newBuilder()
                    .setState(stateBuilder.build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteCounter(SlidingWindowLog.DeleteCounterRequest request,
                                 StreamObserver<SlidingWindowLog.DeleteCounterResponse> responseObserver) {
            WindowState removed = counters.remove(request.getCounterId());
            responseObserver.onNext(SlidingWindowLog.DeleteCounterResponse.newBuilder()
                .setSuccess(removed != null)
                .setError(removed == null ? "Counter not found" : "")
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
        private final SlidingWindowLogRateLimiter limiter;

        public NodeServiceImpl(SlidingWindowLogRateLimiter limiter) {
            this.limiter = limiter;
        }

        @Override
        public void syncState(SlidingWindowLog.SyncStateRequest request,
                             StreamObserver<SlidingWindowLog.SyncStateResponse> responseObserver) {
            for (SlidingWindowLog.WindowState state : request.getStatesList()) {
                WindowState counter = limiter.counters.get(state.getCounterId());
                if (counter != null) {
                    counter.lock.lock();
                    try {
                        // Merge timestamps (union of both logs)
                        Set<Long> timestampSet = new TreeSet<>(counter.timestamps);
                        for (Long ts : state.getTimestampsList()) {
                            timestampSet.add(ts);
                        }
                        counter.timestamps.clear();
                        counter.timestamps.addAll(timestampSet);
                    } finally {
                        counter.lock.unlock();
                    }
                } else {
                    WindowState newCounter = new WindowState(
                        state.getCounterId(), state.getWindowSizeMs(), state.getRequestLimit());
                    newCounter.timestamps.addAll(state.getTimestampsList());
                    Collections.sort(newCounter.timestamps);
                    limiter.counters.put(state.getCounterId(), newCounter);
                }
            }

            responseObserver.onNext(SlidingWindowLog.SyncStateResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(limiter.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(SlidingWindowLog.HeartbeatRequest request,
                             StreamObserver<SlidingWindowLog.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(SlidingWindowLog.HeartbeatResponse.newBuilder()
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
            System.err.println("Usage: java SlidingWindowLogServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        SlidingWindowLogRateLimiter limiter = new SlidingWindowLogRateLimiter(nodeId, port, peers);
        limiter.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(limiter)
                .addService(new NodeServiceImpl(limiter))
                .build()
                .start();

        logger.info("Starting Sliding Window Log Rate Limiter node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
