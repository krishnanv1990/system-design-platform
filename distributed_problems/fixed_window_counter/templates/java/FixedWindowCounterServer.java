/**
 * Fixed Window Counter Rate Limiter - Java Template
 *
 * This template provides the basic structure for implementing a distributed
 * fixed window counter rate limiter.
 *
 * Key concepts:
 * 1. Fixed Windows - Time is divided into fixed intervals (e.g., 1 minute)
 * 2. Counter - Each window has a counter for requests
 * 3. Limit - Maximum requests allowed per window
 * 4. Reset - Counter resets at the start of each new window
 *
 * Usage:
 *     java FixedWindowCounterServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.fixedwindow;

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

public class FixedWindowCounterServer {
    private static final Logger logger = Logger.getLogger(FixedWindowCounterServer.class.getName());

    /**
     * WindowState holds the state of a fixed window counter.
     */
    public static class WindowState {
        public final String counterId;
        public long windowStart;
        public long windowSizeMs;
        public long requestCount;
        public long requestLimit;
        public final ReentrantLock lock = new ReentrantLock();

        public WindowState(String counterId, long windowSizeMs, long requestLimit) {
            this.counterId = counterId;
            this.windowSizeMs = windowSizeMs;
            this.requestLimit = requestLimit;
            this.requestCount = 0;
            this.windowStart = getCurrentWindowStart(windowSizeMs);
        }

        private static long getCurrentWindowStart(long windowSizeMs) {
            long now = System.currentTimeMillis();
            return (now / windowSizeMs) * windowSizeMs;
        }
    }

    /**
     * FixedWindowRateLimiter implements the fixed window counter algorithm.
     */
    public static class FixedWindowRateLimiter extends RateLimiterServiceGrpc.RateLimiterServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, WindowState> counters = new ConcurrentHashMap<>();
        private final Map<String, NodeServiceGrpc.NodeServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public FixedWindowRateLimiter(String nodeId, int port, List<String> peers) {
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
         *
         * TODO: Implement window calculation:
         * 1. Get the current timestamp in milliseconds
         * 2. Calculate which window we're in: window_num = current_time / window_size
         * 3. Return window start: window_start = window_num * window_size
         */
        public long getCurrentWindowStart(long windowSizeMs) {
            long now = System.currentTimeMillis();
            return (now / windowSizeMs) * windowSizeMs;
        }

        /**
         * Check and rotate window if needed.
         *
         * TODO: Implement window rotation:
         * 1. Calculate the current window start
         * 2. If window has changed, reset the counter
         * 3. Update window start time
         */
        public void checkAndRotateWindow(WindowState counter) {
            counter.lock.lock();
            try {
                long currentWindow = getCurrentWindowStart(counter.windowSizeMs);

                // TODO: Check if we've moved to a new window
                if (currentWindow > counter.windowStart) {
                    // Reset counter for new window
                    counter.windowStart = currentWindow;
                    counter.requestCount = 0;
                }
            } finally {
                counter.lock.unlock();
            }
        }

        /**
         * Try to increment the counter.
         *
         * TODO: Implement counter increment:
         * 1. First check and rotate window if needed
         * 2. Check if incrementing would exceed limit
         * 3. If within limit, increment and return true
         * 4. If would exceed, return false
         */
        public boolean tryIncrement(WindowState counter, long count) {
            checkAndRotateWindow(counter);

            counter.lock.lock();
            try {
                // TODO: Check if request would exceed limit
                if (counter.requestCount + count <= counter.requestLimit) {
                    counter.requestCount += count;
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
        public void createCounter(FixedWindowCounter.CreateCounterRequest request,
                                 StreamObserver<FixedWindowCounter.CreateCounterResponse> responseObserver) {
            WindowState counter = getOrCreateCounter(
                request.getCounterId(),
                request.getConfig().getWindowSizeMs(),
                request.getConfig().getRequestLimit()
            );

            counter.lock.lock();
            try {
                responseObserver.onNext(FixedWindowCounter.CreateCounterResponse.newBuilder()
                    .setSuccess(true)
                    .setState(FixedWindowCounter.WindowState.newBuilder()
                        .setCounterId(counter.counterId)
                        .setWindowStart(counter.windowStart)
                        .setWindowSizeMs(counter.windowSizeMs)
                        .setRequestCount(counter.requestCount)
                        .setRequestLimit(counter.requestLimit)
                        .build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void allowRequest(FixedWindowCounter.AllowRequestRequest request,
                                StreamObserver<FixedWindowCounter.AllowRequestResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(FixedWindowCounter.AllowRequestResponse.newBuilder()
                    .setAllowed(false)
                    .setError("Counter not found")
                    .build());
                responseObserver.onCompleted();
                return;
            }

            long count = request.getCount();
            if (count == 0) count = 1;

            boolean allowed = tryIncrement(counter, count);

            counter.lock.lock();
            long currentCount, limit, windowEnd;
            try {
                currentCount = counter.requestCount;
                limit = counter.requestLimit;
                windowEnd = counter.windowStart + counter.windowSizeMs;
            } finally {
                counter.lock.unlock();
            }

            long retryAfter = allowed ? 0 : Math.max(0, windowEnd - System.currentTimeMillis());

            responseObserver.onNext(FixedWindowCounter.AllowRequestResponse.newBuilder()
                .setAllowed(allowed)
                .setCurrentCount(currentCount)
                .setRemainingCount(limit - currentCount)
                .setRetryAfterMs(retryAfter)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getCounterState(FixedWindowCounter.GetCounterStateRequest request,
                                   StreamObserver<FixedWindowCounter.GetCounterStateResponse> responseObserver) {
            WindowState counter = counters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(FixedWindowCounter.GetCounterStateResponse.newBuilder().build());
                responseObserver.onCompleted();
                return;
            }

            checkAndRotateWindow(counter);

            counter.lock.lock();
            try {
                responseObserver.onNext(FixedWindowCounter.GetCounterStateResponse.newBuilder()
                    .setState(FixedWindowCounter.WindowState.newBuilder()
                        .setCounterId(counter.counterId)
                        .setWindowStart(counter.windowStart)
                        .setWindowSizeMs(counter.windowSizeMs)
                        .setRequestCount(counter.requestCount)
                        .setRequestLimit(counter.requestLimit)
                        .build())
                    .build());
            } finally {
                counter.lock.unlock();
            }
            responseObserver.onCompleted();
        }

        @Override
        public void deleteCounter(FixedWindowCounter.DeleteCounterRequest request,
                                 StreamObserver<FixedWindowCounter.DeleteCounterResponse> responseObserver) {
            WindowState removed = counters.remove(request.getCounterId());
            responseObserver.onNext(FixedWindowCounter.DeleteCounterResponse.newBuilder()
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
        private final FixedWindowRateLimiter limiter;

        public NodeServiceImpl(FixedWindowRateLimiter limiter) {
            this.limiter = limiter;
        }

        @Override
        public void syncState(FixedWindowCounter.SyncStateRequest request,
                             StreamObserver<FixedWindowCounter.SyncStateResponse> responseObserver) {
            for (FixedWindowCounter.WindowState state : request.getStatesList()) {
                WindowState counter = limiter.counters.get(state.getCounterId());
                if (counter != null) {
                    counter.lock.lock();
                    try {
                        // For same window, use higher count (more conservative)
                        if (state.getWindowStart() == counter.windowStart) {
                            if (state.getRequestCount() > counter.requestCount) {
                                counter.requestCount = state.getRequestCount();
                            }
                        } else if (state.getWindowStart() > counter.windowStart) {
                            // Newer window, adopt it
                            counter.windowStart = state.getWindowStart();
                            counter.requestCount = state.getRequestCount();
                        }
                    } finally {
                        counter.lock.unlock();
                    }
                } else {
                    WindowState newCounter = new WindowState(
                        state.getCounterId(), state.getWindowSizeMs(), state.getRequestLimit());
                    newCounter.windowStart = state.getWindowStart();
                    newCounter.requestCount = state.getRequestCount();
                    limiter.counters.put(state.getCounterId(), newCounter);
                }
            }

            responseObserver.onNext(FixedWindowCounter.SyncStateResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(limiter.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(FixedWindowCounter.HeartbeatRequest request,
                             StreamObserver<FixedWindowCounter.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(FixedWindowCounter.HeartbeatResponse.newBuilder()
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
            System.err.println("Usage: java FixedWindowCounterServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        FixedWindowRateLimiter limiter = new FixedWindowRateLimiter(nodeId, port, peers);
        limiter.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(limiter)
                .addService(new NodeServiceImpl(limiter))
                .build()
                .start();

        logger.info("Starting Fixed Window Counter Rate Limiter node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
