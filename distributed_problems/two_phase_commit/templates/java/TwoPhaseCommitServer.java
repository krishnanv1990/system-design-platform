/**
 * Two-Phase Commit (2PC) Implementation - Java Template
 *
 * This template provides the basic structure for implementing the Two-Phase Commit
 * protocol for distributed transactions. You need to implement the TODO sections.
 *
 * Usage:
 *     java TwoPhaseCommitServer --node-id coord --port 50051 --role coordinator --participants p1:50052,p2:50053
 */

package com.sdp.tpc;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.logging.Logger;

public class TwoPhaseCommitServer {
    private static final Logger logger = Logger.getLogger(TwoPhaseCommitServer.class.getName());

    public enum NodeRole { COORDINATOR, PARTICIPANT }
    public enum TxnState { UNKNOWN, ACTIVE, PREPARING, PREPARED, COMMITTING, COMMITTED, ABORTING, ABORTED }

    public static class Transaction {
        public String id;
        public TxnState state = TxnState.ACTIVE;
        public List<String> participants = new ArrayList<>();
        public Map<String, Boolean> votes = new ConcurrentHashMap<>();
    }

    public static class ParticipantTxnState {
        public String transactionId;
        public TxnState state = TxnState.ACTIVE;
        public Set<String> locksHeld = ConcurrentHashMap.newKeySet();
    }

    public static class TwoPhaseCommitNode extends CoordinatorServiceGrpc.CoordinatorServiceImplBase {
        private final String nodeId;
        private final int port;
        private final NodeRole role;
        private final List<String> participants;
        private final String coordinatorAddr;

        private final Map<String, Transaction> transactions = new ConcurrentHashMap<>();
        private final Map<String, ParticipantTxnState> participantStates = new ConcurrentHashMap<>();
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        private final Map<String, ParticipantServiceGrpc.ParticipantServiceBlockingStub> participantStubs = new ConcurrentHashMap<>();

        public TwoPhaseCommitNode(String nodeId, int port, NodeRole role, List<String> participants, String coordinator) {
            this.nodeId = nodeId;
            this.port = port;
            this.role = role;
            this.participants = participants;
            this.coordinatorAddr = coordinator;
        }

        public void initialize() {
            if (role == NodeRole.COORDINATOR) {
                for (String p : participants) {
                    ManagedChannel channel = ManagedChannelBuilder.forTarget(p).usePlaintext().build();
                    participantStubs.put(p, ParticipantServiceGrpc.newBlockingStub(channel));
                }
                logger.info("Coordinator " + nodeId + " initialized with participants: " + participants);
            } else {
                logger.info("Participant " + nodeId + " initialized");
            }
        }

        @Override
        public void beginTransaction(TPC.BeginTransactionRequest request, StreamObserver<TPC.BeginTransactionResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                String txnId = UUID.randomUUID().toString();
                Transaction txn = new Transaction();
                txn.id = txnId;
                txn.participants = new ArrayList<>(participants);
                transactions.put(txnId, txn);

                responseObserver.onNext(TPC.BeginTransactionResponse.newBuilder()
                        .setSuccess(true)
                        .setTransactionId(txnId)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        @Override
        public void commitTransaction(TPC.CommitTransactionRequest request, StreamObserver<TPC.CommitTransactionResponse> responseObserver) {
            lock.writeLock().lock();
            try {
                if (!transactions.containsKey(request.getTransactionId())) {
                    responseObserver.onNext(TPC.CommitTransactionResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Transaction not found")
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                // TODO: Implement 2PC protocol
                responseObserver.onNext(TPC.CommitTransactionResponse.newBuilder()
                        .setSuccess(false)
                        .setError("Not implemented")
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.writeLock().unlock();
            }
        }

        @Override
        public void abortTransaction(TPC.AbortTransactionRequest request, StreamObserver<TPC.AbortTransactionResponse> responseObserver) {
            responseObserver.onNext(TPC.AbortTransactionResponse.newBuilder().setSuccess(true).build());
            responseObserver.onCompleted();
        }

        @Override
        public void getTransactionStatus(TPC.GetTransactionStatusRequest request, StreamObserver<TPC.GetTransactionStatusResponse> responseObserver) {
            lock.readLock().lock();
            try {
                Transaction txn = transactions.get(request.getTransactionId());
                TPC.GetTransactionStatusResponse.Builder resp = TPC.GetTransactionStatusResponse.newBuilder();
                if (txn != null) {
                    resp.setFound(true).setTransactionId(txn.id).setState(TPC.TransactionState.forNumber(txn.state.ordinal()));
                } else {
                    resp.setFound(false);
                }
                responseObserver.onNext(resp.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }

        @Override
        public void executeOperation(TPC.ExecuteOperationRequest request, StreamObserver<TPC.ExecuteOperationResponse> responseObserver) {
            responseObserver.onNext(TPC.ExecuteOperationResponse.newBuilder().setSuccess(false).setError("Not implemented").build());
            responseObserver.onCompleted();
        }
    }

    public static class ParticipantNode extends ParticipantServiceGrpc.ParticipantServiceImplBase {
        private final String nodeId;
        private final Map<String, ParticipantTxnState> states = new ConcurrentHashMap<>();
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        public ParticipantNode(String nodeId) {
            this.nodeId = nodeId;
        }

        @Override
        public void prepare(TPC.PrepareRequest request, StreamObserver<TPC.PrepareResponse> responseObserver) {
            responseObserver.onNext(TPC.PrepareResponse.newBuilder().setVote(false).build());
            responseObserver.onCompleted();
        }

        @Override
        public void commit(TPC.CommitRequest request, StreamObserver<TPC.CommitResponse> responseObserver) {
            responseObserver.onNext(TPC.CommitResponse.newBuilder().setSuccess(true).build());
            responseObserver.onCompleted();
        }

        @Override
        public void abort(TPC.AbortRequest request, StreamObserver<TPC.AbortResponse> responseObserver) {
            responseObserver.onNext(TPC.AbortResponse.newBuilder().setSuccess(true).build());
            responseObserver.onCompleted();
        }

        @Override
        public void getStatus(TPC.GetStatusRequest request, StreamObserver<TPC.GetStatusResponse> responseObserver) {
            lock.readLock().lock();
            try {
                ParticipantTxnState state = states.get(request.getTransactionId());
                TPC.GetStatusResponse.Builder resp = TPC.GetStatusResponse.newBuilder();
                if (state != null) {
                    resp.setFound(true).setState(TPC.TransactionState.forNumber(state.state.ordinal()));
                } else {
                    resp.setFound(false);
                }
                responseObserver.onNext(resp.build());
                responseObserver.onCompleted();
            } finally {
                lock.readLock().unlock();
            }
        }

        @Override
        public void executeLocal(TPC.ExecuteLocalRequest request, StreamObserver<TPC.ExecuteLocalResponse> responseObserver) {
            responseObserver.onNext(TPC.ExecuteLocalResponse.newBuilder().setSuccess(false).setError("Not implemented").build());
            responseObserver.onCompleted();
        }
    }

    public static class KeyValueNode extends KeyValueServiceGrpc.KeyValueServiceImplBase {
        private final String nodeId;
        private final NodeRole role;
        private final String coordinatorAddr;
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();

        public KeyValueNode(String nodeId, NodeRole role, String coordinatorAddr) {
            this.nodeId = nodeId;
            this.role = role;
            this.coordinatorAddr = coordinatorAddr;
        }

        @Override
        public void get(TPC.GetRequest request, StreamObserver<TPC.GetResponse> responseObserver) {
            String value = kvStore.get(request.getKey());
            responseObserver.onNext(TPC.GetResponse.newBuilder()
                    .setFound(value != null)
                    .setValue(value != null ? value : "")
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void put(TPC.PutRequest request, StreamObserver<TPC.PutResponse> responseObserver) {
            if (role != NodeRole.COORDINATOR) {
                responseObserver.onNext(TPC.PutResponse.newBuilder()
                        .setSuccess(false)
                        .setError("Not the coordinator")
                        .setCoordinatorHint(coordinatorAddr != null ? coordinatorAddr : "")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            responseObserver.onNext(TPC.PutResponse.newBuilder().setSuccess(false).setError("Not implemented").build());
            responseObserver.onCompleted();
        }

        @Override
        public void delete(TPC.DeleteRequest request, StreamObserver<TPC.DeleteResponse> responseObserver) {
            if (role != NodeRole.COORDINATOR) {
                responseObserver.onNext(TPC.DeleteResponse.newBuilder()
                        .setSuccess(false)
                        .setError("Not the coordinator")
                        .setCoordinatorHint(coordinatorAddr != null ? coordinatorAddr : "")
                        .build());
                responseObserver.onCompleted();
                return;
            }
            responseObserver.onNext(TPC.DeleteResponse.newBuilder().setSuccess(false).setError("Not implemented").build());
            responseObserver.onCompleted();
        }

        @Override
        public void getLeader(TPC.GetLeaderRequest request, StreamObserver<TPC.GetLeaderResponse> responseObserver) {
            responseObserver.onNext(TPC.GetLeaderResponse.newBuilder()
                    .setCoordinatorId(nodeId)
                    .setIsCoordinator(role == NodeRole.COORDINATOR)
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void getClusterStatus(TPC.GetClusterStatusRequest request, StreamObserver<TPC.GetClusterStatusResponse> responseObserver) {
            responseObserver.onNext(TPC.GetClusterStatusResponse.newBuilder()
                    .setNodeId(nodeId)
                    .setRole(role == NodeRole.COORDINATOR ? "coordinator" : "participant")
                    .build());
            responseObserver.onCompleted();
        }
    }

    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = null, roleStr = null, participantsStr = "", coordinator = "";
        int port = 50051;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--node-id": nodeId = args[++i]; break;
                case "--port": port = Integer.parseInt(args[++i]); break;
                case "--role": roleStr = args[++i]; break;
                case "--participants": participantsStr = args[++i]; break;
                case "--coordinator": coordinator = args[++i]; break;
            }
        }

        if (nodeId == null || roleStr == null) {
            System.err.println("Usage: java TwoPhaseCommitServer --node-id <id> --port <port> --role <coordinator|participant>");
            System.exit(1);
        }

        NodeRole role = roleStr.equals("coordinator") ? NodeRole.COORDINATOR : NodeRole.PARTICIPANT;
        List<String> participants = new ArrayList<>();
        for (String p : participantsStr.split(",")) {
            if (!p.trim().isEmpty()) participants.add(p.trim());
        }

        ServerBuilder<?> builder = ServerBuilder.forPort(port);

        if (role == NodeRole.COORDINATOR) {
            TwoPhaseCommitNode coordNode = new TwoPhaseCommitNode(nodeId, port, role, participants, coordinator);
            coordNode.initialize();
            builder.addService(coordNode);
        } else {
            builder.addService(new ParticipantNode(nodeId));
        }
        builder.addService(new KeyValueNode(nodeId, role, coordinator));

        Server server = builder.build().start();
        logger.info("Starting 2PC " + roleStr + " node " + nodeId + " on port " + port);
        server.awaitTermination();
    }
}
