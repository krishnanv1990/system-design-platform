/**
 * CRDT (Conflict-free Replicated Data Types) - Java Template
 *
 * This template provides the basic structure for implementing
 * various CRDTs for eventually consistent distributed systems.
 *
 * Key concepts:
 * 1. Convergence - All replicas converge to the same state
 * 2. Commutativity - Operations can be applied in any order
 * 3. Idempotence - Applying the same operation twice has no effect
 * 4. No Coordination - No consensus required for updates
 *
 * Usage:
 *     java CRDTServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.crdt;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class CRDTServer {
    private static final Logger logger = Logger.getLogger(CRDTServer.class.getName());

    // =========================================================================
    // G-Counter (Grow-only Counter)
    // =========================================================================

    public static class GCounter {
        public final String id;
        private final Map<String, Long> counts = new ConcurrentHashMap<>();
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public GCounter(String id) {
            this.id = id;
        }

        /**
         * Increment this node's count.
         * TODO: Only increment this node's counter
         */
        public void increment(String nodeId, long amount) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("increment not implemented");
        }

        /**
         * Get total count across all nodes.
         * TODO: Sum all node counters
         */
        public long value() {
            // TODO: Implement this method
            return 0;
        }

        /**
         * Merge another G-Counter.
         * TODO: Take maximum of each node's counter
         */
        public void merge(Map<String, Long> other) {
            // TODO: Implement this method
            throw new UnsupportedOperationException("merge not implemented");
        }

        public Map<String, Long> getCounts() {
            lock.readLock().lock();
            try {
                return new HashMap<>(counts);
            } finally {
                lock.readLock().unlock();
            }
        }
    }

    // =========================================================================
    // PN-Counter (Positive-Negative Counter)
    // =========================================================================

    public static class PNCounter {
        public final String id;
        private final GCounter positive;
        private final GCounter negative;

        public PNCounter(String id) {
            this.id = id;
            this.positive = new GCounter(id + "-pos");
            this.negative = new GCounter(id + "-neg");
        }

        public void increment(String nodeId, long amount) {
            positive.increment(nodeId, amount);
        }

        public void decrement(String nodeId, long amount) {
            negative.increment(nodeId, amount);
        }

        /**
         * Get value: P - N
         */
        public long value() {
            return positive.value() - negative.value();
        }

        public GCounter getPositive() { return positive; }
        public GCounter getNegative() { return negative; }
    }

    // =========================================================================
    // G-Set (Grow-only Set)
    // =========================================================================

    public static class GSet {
        public final String id;
        private final Set<String> elements = ConcurrentHashMap.newKeySet();

        public GSet(String id) {
            this.id = id;
        }

        public void add(String element) {
            elements.add(element);
        }

        public boolean contains(String element) {
            return elements.contains(element);
        }

        public void merge(Set<String> other) {
            elements.addAll(other);
        }

        public Set<String> getElements() {
            return new HashSet<>(elements);
        }
    }

    // =========================================================================
    // LWW-Register (Last-Writer-Wins Register)
    // =========================================================================

    public static class LWWRegister {
        public final String id;
        private String value = "";
        private long timestamp = 0;
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public LWWRegister(String id) {
            this.id = id;
        }

        /**
         * Set value if timestamp is newer.
         * TODO: Only update if new timestamp > current timestamp
         */
        public boolean set(String value, long timestamp) {
            // TODO: Implement this method
            return false;
        }

        public String getValue() {
            lock.readLock().lock();
            try {
                return value;
            } finally {
                lock.readLock().unlock();
            }
        }

        public long getTimestamp() {
            lock.readLock().lock();
            try {
                return timestamp;
            } finally {
                lock.readLock().unlock();
            }
        }
    }

    // =========================================================================
    // CRDTNode - Main Node Implementation
    // =========================================================================

    public static class CRDTNode extends CRDTServiceGrpc.CRDTServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, GCounter> gCounters = new ConcurrentHashMap<>();
        private final Map<String, PNCounter> pnCounters = new ConcurrentHashMap<>();
        private final Map<String, GSet> gSets = new ConcurrentHashMap<>();
        private final Map<String, LWWRegister> lwwRegisters = new ConcurrentHashMap<>();
        private final Map<String, ReplicationServiceGrpc.ReplicationServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public CRDTNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, ReplicationServiceGrpc.newBlockingStub(channel));
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        // G-Counter operations
        @Override
        public void gCounterIncrement(CRDT.GCounterIncrementRequest request,
                                      StreamObserver<CRDT.GCounterIncrementResponse> responseObserver) {
            GCounter counter = gCounters.computeIfAbsent(request.getCounterId(), GCounter::new);
            long amount = request.getAmount() == 0 ? 1 : request.getAmount();
            counter.increment(nodeId, amount);

            responseObserver.onNext(CRDT.GCounterIncrementResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(nodeId)
                .setNodeCount(counter.getCounts().getOrDefault(nodeId, 0L))
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void gCounterGet(CRDT.GCounterGetRequest request,
                               StreamObserver<CRDT.GCounterGetResponse> responseObserver) {
            GCounter counter = gCounters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(CRDT.GCounterGetResponse.newBuilder().setValue(0).build());
            } else {
                responseObserver.onNext(CRDT.GCounterGetResponse.newBuilder()
                    .setValue(counter.value())
                    .putAllNodeCounts(counter.getCounts())
                    .build());
            }
            responseObserver.onCompleted();
        }

        // PN-Counter operations
        @Override
        public void pnCounterIncrement(CRDT.PNCounterIncrementRequest request,
                                       StreamObserver<CRDT.PNCounterIncrementResponse> responseObserver) {
            PNCounter counter = pnCounters.computeIfAbsent(request.getCounterId(), PNCounter::new);
            long amount = request.getAmount() == 0 ? 1 : request.getAmount();
            counter.increment(nodeId, amount);

            responseObserver.onNext(CRDT.PNCounterIncrementResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(nodeId)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void pnCounterDecrement(CRDT.PNCounterDecrementRequest request,
                                       StreamObserver<CRDT.PNCounterDecrementResponse> responseObserver) {
            PNCounter counter = pnCounters.computeIfAbsent(request.getCounterId(), PNCounter::new);
            long amount = request.getAmount() == 0 ? 1 : request.getAmount();
            counter.decrement(nodeId, amount);

            responseObserver.onNext(CRDT.PNCounterDecrementResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(nodeId)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void pnCounterGet(CRDT.PNCounterGetRequest request,
                                StreamObserver<CRDT.PNCounterGetResponse> responseObserver) {
            PNCounter counter = pnCounters.get(request.getCounterId());

            if (counter == null) {
                responseObserver.onNext(CRDT.PNCounterGetResponse.newBuilder().setValue(0).build());
            } else {
                responseObserver.onNext(CRDT.PNCounterGetResponse.newBuilder()
                    .setValue(counter.value())
                    .build());
            }
            responseObserver.onCompleted();
        }

        // G-Set operations
        @Override
        public void gSetAdd(CRDT.GSetAddRequest request,
                           StreamObserver<CRDT.GSetAddResponse> responseObserver) {
            GSet set = gSets.computeIfAbsent(request.getSetId(), GSet::new);
            set.add(request.getElement());

            responseObserver.onNext(CRDT.GSetAddResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(nodeId)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void gSetContains(CRDT.GSetContainsRequest request,
                                StreamObserver<CRDT.GSetContainsResponse> responseObserver) {
            GSet set = gSets.get(request.getSetId());

            responseObserver.onNext(CRDT.GSetContainsResponse.newBuilder()
                .setContains(set != null && set.contains(request.getElement()))
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void gSetElements(CRDT.GSetElementsRequest request,
                                StreamObserver<CRDT.GSetElementsResponse> responseObserver) {
            GSet set = gSets.get(request.getSetId());

            CRDT.GSetElementsResponse.Builder response = CRDT.GSetElementsResponse.newBuilder();
            if (set != null) {
                response.addAllElements(set.getElements());
            }

            responseObserver.onNext(response.build());
            responseObserver.onCompleted();
        }

        // LWW-Register operations
        @Override
        public void lwwRegisterSet(CRDT.LWWRegisterSetRequest request,
                                   StreamObserver<CRDT.LWWRegisterSetResponse> responseObserver) {
            LWWRegister reg = lwwRegisters.computeIfAbsent(request.getRegisterId(), LWWRegister::new);
            long timestamp = request.getTimestamp() == 0 ? System.nanoTime() : request.getTimestamp();
            boolean success = reg.set(request.getValue(), timestamp);

            responseObserver.onNext(CRDT.LWWRegisterSetResponse.newBuilder()
                .setSuccess(success)
                .setNodeId(nodeId)
                .setTimestamp(timestamp)
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void lwwRegisterGet(CRDT.LWWRegisterGetRequest request,
                                  StreamObserver<CRDT.LWWRegisterGetResponse> responseObserver) {
            LWWRegister reg = lwwRegisters.get(request.getRegisterId());

            if (reg == null) {
                responseObserver.onNext(CRDT.LWWRegisterGetResponse.newBuilder()
                    .setValue("")
                    .setTimestamp(0)
                    .build());
            } else {
                responseObserver.onNext(CRDT.LWWRegisterGetResponse.newBuilder()
                    .setValue(reg.getValue())
                    .setTimestamp(reg.getTimestamp())
                    .build());
            }
            responseObserver.onCompleted();
        }

        public String getNodeId() { return nodeId; }
        public Map<String, GCounter> getGCounters() { return gCounters; }
        public Map<String, GSet> getGSets() { return gSets; }
        public Map<String, LWWRegister> getLWWRegisters() { return lwwRegisters; }
    }

    // =========================================================================
    // ReplicationService Implementation
    // =========================================================================

    public static class ReplicationServiceImpl extends ReplicationServiceGrpc.ReplicationServiceImplBase {
        private final CRDTNode node;

        public ReplicationServiceImpl(CRDTNode node) {
            this.node = node;
        }

        @Override
        public void replicateGCounter(CRDT.ReplicateGCounterRequest request,
                                      StreamObserver<CRDT.ReplicateGCounterResponse> responseObserver) {
            GCounter counter = node.getGCounters().computeIfAbsent(request.getCounterId(), GCounter::new);
            counter.merge(request.getNodeCountsMap());

            responseObserver.onNext(CRDT.ReplicateGCounterResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(node.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void replicateGSet(CRDT.ReplicateGSetRequest request,
                                 StreamObserver<CRDT.ReplicateGSetResponse> responseObserver) {
            GSet set = node.getGSets().computeIfAbsent(request.getSetId(), GSet::new);
            set.merge(new HashSet<>(request.getElementsList()));

            responseObserver.onNext(CRDT.ReplicateGSetResponse.newBuilder()
                .setSuccess(true)
                .setNodeId(node.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void replicateLWWRegister(CRDT.ReplicateLWWRegisterRequest request,
                                         StreamObserver<CRDT.ReplicateLWWRegisterResponse> responseObserver) {
            LWWRegister reg = node.getLWWRegisters().computeIfAbsent(request.getRegisterId(), LWWRegister::new);
            boolean success = reg.set(request.getValue(), request.getTimestamp());

            responseObserver.onNext(CRDT.ReplicateLWWRegisterResponse.newBuilder()
                .setSuccess(success)
                .setNodeId(node.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void heartbeat(CRDT.HeartbeatRequest request,
                             StreamObserver<CRDT.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(CRDT.HeartbeatResponse.newBuilder()
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
            System.err.println("Usage: java CRDTServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        CRDTNode node = new CRDTNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(node)
                .addService(new ReplicationServiceImpl(node))
                .build()
                .start();

        logger.info("Starting CRDT node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
