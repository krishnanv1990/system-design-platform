/**
 * Sliding Window Counter Rate Limiter - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * sliding window counter rate limiter.
 *
 * Key concepts:
 * 1. Hybrid Approach - Combines fixed window efficiency with sliding window accuracy
 * 2. Weighted Average - Previous window count weighted by overlap percentage
 * 3. Memory Efficient - Only stores two counters, not individual timestamps
 * 4. Approximate - Not 100% accurate but good enough for most use cases
 *
 * Usage:
 *     java SlidingWindowCounterServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.slidingwindowcounter;

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

public class SlidingWindowCounterServer {
    private static final Logger logger = Logger.getLogger(SlidingWindowCounterServer.class.getName());

    /**
     * WindowState holds the state of a sliding window counter.
     */
    public static class WindowState {
        public final String counterId;
        public long previousCount;
        public long currentCount;
        public long currentWindowStart;
        public long windowSizeMs;
        public long requestLimit;
        public final ReentrantLock lock = new ReentrantLock();

        public WindowState(String counterId, long windowSizeMs, long requestLimit) {
            this.counterId = counterId;
            this.windowSizeMs = windowSizeMs;
            this.requestLimit = requestLimit;
            this.previousCount = 0;
            this.currentCount = 0;
            this.currentWindowStart = getCurrentWindowStart(windowSizeMs);
        }

        private static long getCurrentWindowStart(long windowSizeMs) {
            long now = System.currentTimeMillis();
            return (now / windowSizeMs) * windowSizeMs;
        }
    }

    /**
     * SlidingWindowCounterRateLimiter implements the sliding window counter algorithm.
     */
    public static class SlidingWindowCounterRateLimiter extends RateLimiterServiceGrpc.RateLimiterServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, WindowState> counters = new ConcurrentHashMap<>();
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public SlidingWindowCounterRateLimiter(String nodeId, int port, List<String> peers) {
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
         * Get the current window start time.
         */
        public long getCurrentWindowStart(long windowSizeMs) {
            long now = System.currentTimeMillis();
            return (now / windowSizeMs) * windowSizeMs;
        }

        /**
         * Check and rotate windows if needed.
         *
         * TODO: Implement window rotation:
         * 1. Calculate the current fixed window start
         * 2. If we've moved to a new window:
         *    a. Move current count to previous count
         *    b. Reset current count
         *    c. Update window start
         * 3. If we've moved past two windows:
         *    a. Reset both counts (too old)
         */
        public void checkAndRotateWindow(WindowState counter) {
            counter.lock.lock();
            try {
                long currentWindow = getCurrentWindowStart(counter.windowSizeMs);

                // Calculate how many windows have passed
                long windowsPassed = (currentWindow - counter.currentWindowStart) / counter.windowSizeMs;

                if (windowsPassed >= 2) {
                    // TODO: Too old, reset both counts
                    counter.previousCount = 0;
                    counter.currentCount = 0;
                    counter.currentWindowStart = currentWindow;
                } else if (windowsPassed == 1) {
                    // TODO: Moved to next window, rotate counts
                    counter.previousCount = counter.currentCount;
                    counter.currentCount = 0;
                    counter.currentWindowStart = currentWindow;
                }
            } finally {
                counter.lock.unlock();
            }
        }

        /**
         * Calculate the weighted request count.
         *
         * TODO: Implement weighted count calculation:
         * 1. Calculate how far we are into the current window (0.0 to 1.0)
         * 2. Weight the previous window by the overlap: prev_count * (1 - position)
         * 3. Add current window count: current_count * 1.0
         * 4. Return total weighted count
         */
        public double calculateWeightedCount(WindowState counter) {
            checkAndRotateWindow(counter);

            counter.lock.lock();
            try {
                long now = System.currentTimeMillis();

                // TODO: Calculate position within current window (0.0 to 1.0)
                double elapsed = now - counter.currentWindowStart;
                double position = elapsed / counter.windowSizeMs;
                if (position > 1.0) position = 1.0;

                // TODO: Calculate weighted count
                // Previous window weighted by overlap with sliding window
                double previousWeight = 1.0 - position;
                double weightedCount = counter.previousCount * previousWeight + counter.currentCount;

                return weightedCount;
            } finally {
                counter.lock.unlock();
            }
        }

        /**
         * Try to increment the counter.
         *
         * TODO: Implement increment logic:
         * 1. Calculate the current weighted count
         * 2. Check if adding new request would exceed limit
         * 3. If within limit, increment current count and return true
         * 4. If would exceed, return false
         */
        public boolean tryIncrement(WindowState counter, long count) {
            double weightedCount = calculateWeightedCount(counter);

            counter.lock.lock();
            try {
                // TODO: Check if request would exceed limit
                if (weightedCount + count <= counter.requestLimit) {
                    counter.currentCount += count;
                    return true;
                }
                return false;
            } finally {
                counter.lock.unlock();
            }
        }

        // =========================================================================
        // RateLimiterService RPC Implementations
        // =========================================================================

        @Override
        public void createCounter(SlidingWindowCounter.CreateCounterRequest request,
                                 StreamObserver<SlidingWindowCounter.CreateCounterResponse> responseObserver) {
            WindowState counter = getOrCreateCounter(
                request.getCounterId(),
                request.getConfig().getWindowSizeMs(),
                request.getConfig().getRequestLimit()
            );

            counter.lock.lock();
            try {
                responseObserver.onNext(SlidingWindowCounter.CreateCounterResponse.newBuilder()
                    .setSuccess(true)
                    .setState(SlidingWindowCounter.WindowState.newBuilder()
                        .setCounterId(counter.counterId)
                        .setPreviousCount(counter.previousCount)
                        .setCurrentCount(counter.currentCount)
                        .setCurrentWindowStart(counter.currentWindowStart)
                        .setWindowSizeMs(counter.windowSizeMs)
                        .setRequestLimit(counter.requestLimit)
                        .build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void allowRequest(SlidingWindowCounter.AllowRequestRequest request,
                                StreamObserver<SlidingWindowCounter.AllowRequestResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(SlidingWindowCounter.AllowRequestResponse.newBuilder()
                    .setAllowed(false)
                    .setError("Counter not found")
                    .build());
                responseObserver.onCompleted();
                return;
            }

            long count = request.getCount();
            if (count == 0) count = 1;

            boolean allowed = tryIncrement(counter, count);
            double weightedCount = calculateWeightedCount(counter);

            counter.lock.lock();
            long limit, windowEnd;
            try {
                limit = counter.requestLimit;
                windowEnd = counter.currentWindowStart + counter.windowSizeMs;
            } finally {
                counter.lock.unlock();
            }

            long retryAfter = allowed ? 0 : Math.max(0, windowEnd - System.currentTimeMillis());

            responseObserver.onNext(SlidingWindowCounter.AllowRequestResponse.newBuilder()
                .setAllowed(allowed)
                .setWeightedCount(weightedCount)
                .setRemainingCount(limit - weightedCount)
                .setRetryAfterMs(retryAfter)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getCounterState(SlidingWindowCounter.GetCounterStateRequest request,
                                   StreamObserver<SlidingWindowCounter.GetCounterStateResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(SlidingWindowCounter.GetCounterStateResponse.newBuilder().build());
                responseObserver.onCompleted();
                return;
            }

            checkAndRotateWindow(counter);

            counter.lock.lock();
            try {
                responseObserver.onNext(SlidingWindowCounter.GetCounterStateResponse.newBuilder()
                    .setState(SlidingWindowCounter.WindowState.newBuilder()
                        .setCounterId(counter.counterId)
                        .setPreviousCount(counter.previousCount)
                        .setCurrentCount(counter.currentCount)
                        .setCurrentWindowStart(counter.currentWindowStart)
                        .setWindowSizeMs(counter.windowSizeMs)
                        .setRequestLimit(counter.requestLimit)
                        .build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteCounter(SlidingWindowCounter.DeleteCounterRequest request,
                                 StreamObserver<SlidingWindowCounter.DeleteCounterResponse> responseObserver) {
            WindowState removed = counters.remove(request.getCounterId());
            responseObserver.onNext(SlidingWindowCounter.DeleteCounterResponse.newBuilder()
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
        private final SlidingWindowCounterRateLimiter limiter;

        public NodeServiceImpl(SlidingWindowCounterRateLimiter limiter) {
            this.limiter = limiter;
        }

        @Override
        public void syncState(SlidingWindowCounter.SyncStateRequest request,
                             StreamObserver<SlidingWindowCounter.SyncStateResponse> responseObserver) {
            for (SlidingWindowCounter.WindowState state : request.getStatesList()) {
                WindowState counter = limiter.counters.get(state.getCounterId());
                if (counter != null) {
                    counter.lock.lock();
                    try {
                        // For same window, use higher counts (more conservative)
                        if (state.getCurrentWindowStart() == counter.currentWindowStart) {
                            if (state.getCurrentCount() > counter.currentCount) {
                                counter.currentCount = state.getCurrentCount();
                            }
                            if (state.getPreviousCount() > counter.previousCount) {
                                counter.previousCount = state.getPreviousCount();
                            }
                        } else if (state.getCurrentWindowStart() > counter.currentWindowStart) {
                            // Newer window, adopt it
                            counter.currentWindowStart = state.getCurrentWindowStart();
                            counter.currentCount = state.getCurrentCount();
                            counter.previousCount = state.getPreviousCount();
                        }
                    } finally {
                        counter.lock.unlock();
                    }
                } else {
                    WindowState newCounter = new WindowState(
                        state.getCounterId(), state.getWindowSizeMs(), state.getRequestLimit());
                    newCounter.currentWindowStart = state.getCurrentWindowStart();
                    newCounter.currentCount = state.getCurrentCount();
                    newCounter.previousCount = state.getPreviousCount();
                    limiter.counters.put(state.getCounterId(), newCounter);
                }
            }

            responseObserver.onNext(SlidingWindowCounter.SyncStateResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(limiter.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(SlidingWindowCounter.HeartbeatRequest request,
                             StreamObserver<SlidingWindowCounter.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(SlidingWindowCounter.HeartbeatResponse.newBuilder()
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
            System.err.println("Usage: java SlidingWindowCounterServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        SlidingWindowCounterRateLimiter limiter = new SlidingWindowCounterRateLimiter(nodeId, port, peers);
        limiter.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(limiter)
                .addService(new NodeServiceImpl(limiter))
                .build()
                .start();

        logger.info("Starting Sliding Window Counter Rate Limiter node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
