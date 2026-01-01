/**
 * Three-Phase Commit Protocol - Java Template
 *
 * This template provides the basic structure for implementing
 * a non-blocking atomic commitment protocol.
 *
 * Key concepts:
 * 1. CanCommit Phase - Coordinator asks if participants can commit
 * 2. PreCommit Phase - Coordinator tells participants to prepare
 * 3. DoCommit Phase - Coordinator tells participants to commit
 * 4. Timeouts - Handles failures without blocking
 *
 * Usage:
 *     java ThreePhaseCommitServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.threepc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

public class ThreePhaseCommitServer {
    private static final Logger logger = Logger.getLogger(ThreePhaseCommitServer.class.getName());
    private static final int TIMEOUT_MS = 5000;

    public enum TransactionState {
        NONE, WAITING, PRE_COMMITTED, COMMITTED, ABORTED
    }

    /**
     * Transaction holds the state of a distributed transaction.
     */
    public static class Transaction {
        public final String transactionId;
        public TransactionState state;
        public Map<String, String> data;
        public List<String> participants;
        public long timestamp;
        public final ReentrantLock lock = new ReentrantLock();

        public Transaction(String transactionId) {
            this.transactionId = transactionId;
            this.state = TransactionState.WAITING;
            this.data = new HashMap<>();
            this.participants = new ArrayList<>();
            this.timestamp = System.currentTimeMillis();
        }
    }

    /**
     * ThreePhaseCommitNode implements the 3PC protocol.
     */
    public static class ThreePhaseCommitNode extends CoordinatorServiceGrpc.CoordinatorServiceImplBase {
        private final String nodeId;
        private final int port;
        private final List<String> peers;
        private final Map<String, Transaction> transactions = new ConcurrentHashMap<>();
        private final Map<String, String> dataStore = new ConcurrentHashMap<>();
        private final Map<String, ParticipantServiceGrpc.ParticipantServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();
        private final ExecutorService executor = Executors.newCachedThreadPool();

        public ThreePhaseCommitNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, ParticipantServiceGrpc.newBlockingStub(channel)
                        .withDeadlineAfter(TIMEOUT_MS, TimeUnit.MILLISECONDS));
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        /**
         * Execute the full 3PC protocol as coordinator.
         *
         * TODO: Implement the 3PC protocol:
         * 1. Phase 1 (CanCommit): Ask all participants if they can commit
         * 2. If all say yes, Phase 2 (PreCommit): Tell all to prepare
         * 3. If all acknowledge, Phase 3 (DoCommit): Tell all to commit
         * 4. Handle failures and timeouts appropriately
         */
        public boolean executeTransaction(String txId, Map<String, String> data, List<String> participants) {
            Transaction tx = new Transaction(txId);
            tx.data = data;
            tx.participants = participants;
            transactions.put(txId, tx);

            // Phase 1 - CanCommit
            List<Future<Boolean>> canCommitFutures = new ArrayList<>();
            for (String participant : participants) {
                canCommitFutures.add(executor.submit(() -> {
                    try {
                        ParticipantServiceGrpc.ParticipantServiceBlockingStub stub = peerStubs.get(participant);
                        if (stub == null) return false;

                        ThreePhaseCommit.CanCommitResponse resp = stub.canCommit(
                            ThreePhaseCommit.CanCommitRequest.newBuilder()
                                .setTransactionId(txId)
                                .putAllData(data)
                                .build());
                        return resp.getVote();
                    } catch (Exception e) {
                        logger.warning("CanCommit failed for " + participant + ": " + e.getMessage());
                        return false;
                    }
                }));
            }

            // Check all votes
            boolean allCanCommit = true;
            for (Future<Boolean> future : canCommitFutures) {
                try {
                    if (!future.get(TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                        allCanCommit = false;
                    }
                } catch (Exception e) {
                    allCanCommit = false;
                }
            }

            if (!allCanCommit) {
                abortTransaction(tx);
                return false;
            }

            // Phase 2 - PreCommit
            List<Future<Boolean>> preCommitFutures = new ArrayList<>();
            for (String participant : participants) {
                preCommitFutures.add(executor.submit(() -> {
                    try {
                        ParticipantServiceGrpc.ParticipantServiceBlockingStub stub = peerStubs.get(participant);
                        if (stub == null) return false;

                        ThreePhaseCommit.PreCommitResponse resp = stub.preCommit(
                            ThreePhaseCommit.PreCommitRequest.newBuilder()
                                .setTransactionId(txId)
                                .build());
                        return resp.getAcknowledged();
                    } catch (Exception e) {
                        logger.warning("PreCommit failed for " + participant + ": " + e.getMessage());
                        return false;
                    }
                }));
            }

            // Check all acknowledgments
            boolean allPreCommitted = true;
            for (Future<Boolean> future : preCommitFutures) {
                try {
                    if (!future.get(TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                        allPreCommitted = false;
                    }
                } catch (Exception e) {
                    allPreCommitted = false;
                }
            }

            if (!allPreCommitted) {
                abortTransaction(tx);
                return false;
            }

            tx.lock.lock();
            tx.state = TransactionState.PRE_COMMITTED;
            tx.lock.unlock();

            // Phase 3 - DoCommit
            List<Future<Boolean>> commitFutures = new ArrayList<>();
            for (String participant : participants) {
                commitFutures.add(executor.submit(() -> {
                    try {
                        ParticipantServiceGrpc.ParticipantServiceBlockingStub stub = peerStubs.get(participant);
                        if (stub == null) return false;

                        ThreePhaseCommit.DoCommitResponse resp = stub.doCommit(
                            ThreePhaseCommit.DoCommitRequest.newBuilder()
                                .setTransactionId(txId)
                                .build());
                        return resp.getSuccess();
                    } catch (Exception e) {
                        logger.warning("DoCommit failed for " + participant + ": " + e.getMessage());
                        return false;
                    }
                }));
            }

            // Check all commits
            boolean allCommitted = true;
            for (Future<Boolean> future : commitFutures) {
                try {
                    if (!future.get(TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                        allCommitted = false;
                    }
                } catch (Exception e) {
                    allCommitted = false;
                }
            }

            if (allCommitted) {
                tx.lock.lock();
                tx.state = TransactionState.COMMITTED;
                tx.lock.unlock();

                // Commit locally
                dataStore.putAll(data);
                return true;
            }

            return false;
        }

        private void abortTransaction(Transaction tx) {
            tx.lock.lock();
            tx.state = TransactionState.ABORTED;
            tx.lock.unlock();

            for (String participant : tx.participants) {
                executor.submit(() -> {
                    try {
                        ParticipantServiceGrpc.ParticipantServiceBlockingStub stub = peerStubs.get(participant);
                        if (stub != null) {
                            stub.abort(ThreePhaseCommit.AbortRequest.newBuilder()
                                .setTransactionId(tx.transactionId)
                                .build());
                        }
                    } catch (Exception e) {
                        // Ignore abort failures
                    }
                });
            }
        }

        @Override
        public void beginTransaction(ThreePhaseCommit.BeginTransactionRequest request,
                                    StreamObserver<ThreePhaseCommit.BeginTransactionResponse> responseObserver) {
            String txId = "tx-" + nodeId + "-" + System.nanoTime();
            boolean success = executeTransaction(txId, request.getDataMap(), request.getParticipantsList());

            responseObserver.onNext(ThreePhaseCommit.BeginTransactionResponse.newBuilder()
                .setTransactionId(txId)
                .setSuccess(success)
                .setError(success ? "" : "Transaction failed")
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getTransactionStatus(ThreePhaseCommit.GetTransactionStatusRequest request,
                                        StreamObserver<ThreePhaseCommit.GetTransactionStatusResponse> responseObserver) {
            Transaction tx = transactions.get(request.getTransactionId());

            if (tx == null) {
                responseObserver.onNext(ThreePhaseCommit.GetTransactionStatusResponse.newBuilder()
                    .setState(ThreePhaseCommit.TransactionState.UNKNOWN)
                    .build());
            } else {
                tx.lock.lock();
                ThreePhaseCommit.TransactionState pbState;
                switch (tx.state) {
                    case WAITING: pbState = ThreePhaseCommit.TransactionState.WAITING; break;
                    case PRE_COMMITTED: pbState = ThreePhaseCommit.TransactionState.PRE_COMMITTED; break;
                    case COMMITTED: pbState = ThreePhaseCommit.TransactionState.COMMITTED; break;
                    case ABORTED: pbState = ThreePhaseCommit.TransactionState.ABORTED; break;
                    default: pbState = ThreePhaseCommit.TransactionState.UNKNOWN;
                }
                tx.lock.unlock();

                responseObserver.onNext(ThreePhaseCommit.GetTransactionStatusResponse.newBuilder()
                    .setTransactionId(tx.transactionId)
                    .setState(pbState)
                    .addAllParticipants(tx.participants)
                    .build());
            }
            responseObserver.onCompleted();
        }

        public String getNodeId() { return nodeId; }
        public Map<String, Transaction> getTransactions() { return transactions; }
        public Map<String, String> getDataStore() { return dataStore; }
    }

    /**
     * ParticipantService implementation.
     */
    public static class ParticipantServiceImpl extends ParticipantServiceGrpc.ParticipantServiceImplBase {
        private final ThreePhaseCommitNode node;

        public ParticipantServiceImpl(ThreePhaseCommitNode node) {
            this.node = node;
        }

        @Override
        public void canCommit(ThreePhaseCommit.CanCommitRequest request,
                             StreamObserver<ThreePhaseCommit.CanCommitResponse> responseObserver) {
            // Create transaction record
            Transaction tx = new Transaction(request.getTransactionId());
            tx.data = new HashMap<>(request.getDataMap());
            node.getTransactions().put(request.getTransactionId(), tx);

            responseObserver.onNext(ThreePhaseCommit.CanCommitResponse.newBuilder()
                .setVote(true)
                .setNodeId(node.getNodeId())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void preCommit(ThreePhaseCommit.PreCommitRequest request,
                             StreamObserver<ThreePhaseCommit.PreCommitResponse> responseObserver) {
            Transaction tx = node.getTransactions().get(request.getTransactionId());

            if (tx == null) {
                responseObserver.onNext(ThreePhaseCommit.PreCommitResponse.newBuilder()
                    .setAcknowledged(false)
                    .setError("Transaction not found")
                    .build());
            } else {
                tx.lock.lock();
                tx.state = TransactionState.PRE_COMMITTED;
                tx.lock.unlock();

                responseObserver.onNext(ThreePhaseCommit.PreCommitResponse.newBuilder()
                    .setAcknowledged(true)
                    .setNodeId(node.getNodeId())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void doCommit(ThreePhaseCommit.DoCommitRequest request,
                            StreamObserver<ThreePhaseCommit.DoCommitResponse> responseObserver) {
            Transaction tx = node.getTransactions().get(request.getTransactionId());

            if (tx == null) {
                responseObserver.onNext(ThreePhaseCommit.DoCommitResponse.newBuilder()
                    .setSuccess(false)
                    .setError("Transaction not found")
                    .build());
            } else {
                // Apply the data
                node.getDataStore().putAll(tx.data);

                tx.lock.lock();
                tx.state = TransactionState.COMMITTED;
                tx.lock.unlock();

                responseObserver.onNext(ThreePhaseCommit.DoCommitResponse.newBuilder()
                    .setSuccess(true)
                    .setNodeId(node.getNodeId())
                    .build());
            }
            responseObserver.onCompleted();
        }

        @Override
        public void abort(ThreePhaseCommit.AbortRequest request,
                         StreamObserver<ThreePhaseCommit.AbortResponse> responseObserver) {
            Transaction tx = node.getTransactions().get(request.getTransactionId());

            if (tx != null) {
                tx.lock.lock();
                tx.state = TransactionState.ABORTED;
                tx.lock.unlock();
            }

            responseObserver.onNext(ThreePhaseCommit.AbortResponse.newBuilder()
                .setAcknowledged(true)
                .setNodeId(node.getNodeId())
                .build());
            responseObserver.onCompleted();
        }
    }

    /**
     * NodeService implementation.
     */
    public static class NodeServiceImpl extends NodeServiceGrpc.NodeServiceImplBase {
        private final ThreePhaseCommitNode node;

        public NodeServiceImpl(ThreePhaseCommitNode node) {
            this.node = node;
        }

        @Override
        public void heartbeat(ThreePhaseCommit.HeartbeatRequest request,
                             StreamObserver<ThreePhaseCommit.HeartbeatResponse> responseObserver) {
            responseObserver.onNext(ThreePhaseCommit.HeartbeatResponse.newBuilder()
                .setAcknowledged(true)
                .setTimestamp(System.currentTimeMillis())
                .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getNodeState(ThreePhaseCommit.GetNodeStateRequest request,
                                StreamObserver<ThreePhaseCommit.GetNodeStateResponse> responseObserver) {
            ThreePhaseCommit.GetNodeStateResponse.Builder response = ThreePhaseCommit.GetNodeStateResponse.newBuilder()
                .setNodeId(node.getNodeId());

            for (Transaction tx : node.getTransactions().values()) {
                tx.lock.lock();
                ThreePhaseCommit.TransactionState pbState;
                switch (tx.state) {
                    case WAITING: pbState = ThreePhaseCommit.TransactionState.WAITING; break;
                    case PRE_COMMITTED: pbState = ThreePhaseCommit.TransactionState.PRE_COMMITTED; break;
                    case COMMITTED: pbState = ThreePhaseCommit.TransactionState.COMMITTED; break;
                    case ABORTED: pbState = ThreePhaseCommit.TransactionState.ABORTED; break;
                    default: pbState = ThreePhaseCommit.TransactionState.UNKNOWN;
                }
                tx.lock.unlock();

                response.addTransactions(ThreePhaseCommit.TransactionInfo.newBuilder()
                    .setTransactionId(tx.transactionId)
                    .setState(pbState)
                    .setTimestamp(tx.timestamp)
                    .build());
            }

            responseObserver.onNext(response.build());
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
            System.err.println("Usage: java ThreePhaseCommitServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        if (!peersStr.isEmpty()) {
            for (String peer : peersStr.split(",")) {
                peers.add(peer.trim());
            }
        }

        ThreePhaseCommitNode node = new ThreePhaseCommitNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(node)
                .addService(new ParticipantServiceImpl(node))
                .addService(new NodeServiceImpl(node))
                .build()
                .start();

        logger.info("Starting Three-Phase Commit node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
