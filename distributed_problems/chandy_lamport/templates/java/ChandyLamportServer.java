/**
 * Chandy-Lamport Snapshot Algorithm Implementation - Java Template
 *
 * This template provides the basic structure for implementing the Chandy-Lamport
 * algorithm for capturing consistent global snapshots. You need to implement the TODO sections.
 *
 * Based on: "Distributed Snapshots: Determining Global States of Distributed Systems"
 * by K. Mani Chandy and Leslie Lamport (1985)
 *
 * The algorithm:
 * 1. Initiator records local state and sends markers on all outgoing channels
 * 2. On first marker receipt, process records state and forwards markers
 * 3. Messages arriving before marker on each channel are recorded
 * 4. Snapshot complete when all channels have received markers
 *
 * Usage:
 *     java ChandyLamportServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.snapshot;

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

public class ChandyLamportServer {
    private static final Logger logger = Logger.getLogger(ChandyLamportServer.class.getName());

    /**
     * Channel state for recording messages during snapshot.
     */
    public static class ChannelState {
        public String fromProcess;
        public String toProcess;
        public List<ChandyLamport.ApplicationMessage> messages = new CopyOnWriteArrayList<>();
        public volatile boolean isRecording = false;
    }

    /**
     * State for an ongoing snapshot.
     */
    public static class SnapshotState {
        public String snapshotId;
        public String initiatorId;
        public volatile boolean localStateRecorded = false;
        public long logicalClock = 0;
        public Map<String, Long> accountBalances = new ConcurrentHashMap<>();
        public Map<String, String> kvState = new ConcurrentHashMap<>();
        public Map<String, ChannelState> channelStates = new ConcurrentHashMap<>();
        public Set<String> markersReceived = ConcurrentHashMap.newKeySet();
        public volatile boolean recordingComplete = false;
        public long initiatedAt = 0;
        public long completedAt = 0;
    }

    /**
     * Main Chandy-Lamport node implementation.
     */
    public static class ChandyLamportNode {
        private final String nodeId;
        private final int port;
        private final List<String> peers;

        // Logical clock (Lamport clock)
        private long logicalClock = 0;

        // Snapshot state
        private final Map<String, SnapshotState> snapshots = new ConcurrentHashMap<>();
        private volatile String currentSnapshotId = null;

        // Channels (for message recording)
        private final Map<String, ChannelState> incomingChannels = new ConcurrentHashMap<>();

        // Application state: Bank simulation
        private final Map<String, Long> accountBalances = new ConcurrentHashMap<>();

        // Application state: Key-value store
        private final Map<String, String> kvStore = new ConcurrentHashMap<>();

        // Statistics
        private long snapshotsInitiated = 0;
        private long snapshotsParticipated = 0;

        // Synchronization
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        // gRPC stubs
        private final Map<String, SnapshotServiceGrpc.SnapshotServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();

        public ChandyLamportNode(String nodeId, int port, List<String> peers) {
            this.nodeId = nodeId;
            this.port = port;
            this.peers = peers;

            // Initialize with default balance
            accountBalances.put(nodeId + "_account", 1000L);
        }

        public void initialize() {
            for (String peer : peers) {
                ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                        .usePlaintext()
                        .build();
                peerStubs.put(peer, SnapshotServiceGrpc.newBlockingStub(channel));

                // Initialize incoming channel state
                String peerId = peer.split(":")[0];
                ChannelState cs = new ChannelState();
                cs.fromProcess = peerId;
                cs.toProcess = nodeId;
                incomingChannels.put(peerId, cs);
            }
            logger.info("Node " + nodeId + " initialized with peers: " + peers);
        }

        public long incrementClock() {
            lock.writeLock().lock();
            try {
                return ++logicalClock;
            } finally {
                lock.writeLock().unlock();
            }
        }

        public void updateClock(long receivedClock) {
            lock.writeLock().lock();
            try {
                logicalClock = Math.max(logicalClock, receivedClock) + 1;
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Snapshot Initiation
        // =========================================================================

        /**
         * Initiate a new global snapshot.
         *
         * TODO: Implement snapshot initiation:
         * 1. Generate unique snapshot ID
         * 2. Record local state immediately
         * 3. Start recording on all incoming channels
         * 4. Send marker on all outgoing channels
         */
        public ChandyLamport.InitiateSnapshotResponse initiateSnapshot(ChandyLamport.InitiateSnapshotRequest request) {
            lock.writeLock().lock();
            try {
                String snapshotId = request.getSnapshotId().isEmpty()
                        ? UUID.randomUUID().toString()
                        : request.getSnapshotId();

                // TODO: Implement snapshot initiation
                // - Record local state (account balances, kvStore, logical clock)
                // - Create SnapshotState
                // - Start recording on all incoming channels
                // - Send markers to all peers

                snapshotsInitiated++;

                return ChandyLamport.InitiateSnapshotResponse.newBuilder()
                        .setSuccess(true)
                        .setSnapshotId(snapshotId)
                        .setInitiatedAt(System.currentTimeMillis())
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Marker Handling
        // =========================================================================

        /**
         * Handle incoming marker message.
         *
         * TODO: Implement marker handling:
         * 1. If first marker for this snapshot:
         *    - Record local state
         *    - Mark sender's channel as empty (no messages to record)
         *    - Start recording on other incoming channels
         *    - Send markers on all outgoing channels
         * 2. If not first marker:
         *    - Stop recording on sender's channel
         *    - Check if snapshot is complete (all channels done)
         */
        public ChandyLamport.MarkerResponse receiveMarker(ChandyLamport.MarkerMessage request) {
            lock.writeLock().lock();
            try {
                String snapshotId = request.getSnapshotId();
                String senderId = request.getSenderId();

                updateClock(request.getLogicalClock());

                boolean firstMarker = !snapshots.containsKey(snapshotId);

                if (firstMarker) {
                    // TODO: Implement first marker handling
                    // - Record local state
                    // - Create snapshot state
                    // - Mark sender channel as empty
                    // - Start recording other channels
                    // - Forward markers to all peers
                    snapshotsParticipated++;
                } else {
                    // TODO: Implement subsequent marker handling
                    // - Stop recording on sender's channel
                    // - Check if snapshot complete
                }

                return ChandyLamport.MarkerResponse.newBuilder()
                        .setSuccess(true)
                        .setFirstMarker(firstMarker)
                        .setProcessId(nodeId)
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Message Handling
        // =========================================================================

        /**
         * Handle sending an application message.
         *
         * TODO: For messages in transit during snapshot:
         * - Include logical clock in message
         * - Message might be recorded by receiver if channel is being recorded
         */
        public ChandyLamport.SendMessageResponse sendMessage(ChandyLamport.ApplicationMessage request) {
            lock.writeLock().lock();
            try {
                incrementClock();
                // TODO: Forward message to destination
                return ChandyLamport.SendMessageResponse.newBuilder()
                        .setSuccess(true)
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        /**
         * Record a message if the channel is being recorded.
         *
         * TODO: Check if any active snapshot is recording this channel.
         * If so, add the message to the channel state.
         */
        public void recordIncomingMessage(String senderId, ChandyLamport.ApplicationMessage message) {
            lock.writeLock().lock();
            try {
                for (SnapshotState snapshot : snapshots.values()) {
                    if (!snapshot.recordingComplete) {
                        String channelKey = senderId + "->" + nodeId;
                        ChannelState channel = snapshot.channelStates.get(channelKey);
                        if (channel != null && channel.isRecording) {
                            channel.messages.add(message);
                        }
                    }
                }
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // Snapshot Retrieval
        // =========================================================================

        public ChandyLamport.GetSnapshotResponse getSnapshot(ChandyLamport.GetSnapshotRequest request) {
            lock.readLock().lock();
            try {
                String snapshotId = request.getSnapshotId();
                ChandyLamport.GetSnapshotResponse.Builder response = ChandyLamport.GetSnapshotResponse.newBuilder();

                if (snapshots.containsKey(snapshotId)) {
                    SnapshotState snapshot = snapshots.get(snapshotId);
                    response.setFound(true);
                    response.setSnapshotId(snapshotId);
                    response.setRecordingComplete(snapshot.recordingComplete);

                    ChandyLamport.ProcessState.Builder localState = ChandyLamport.ProcessState.newBuilder();
                    localState.setProcessId(nodeId);
                    localState.setLogicalClock(snapshot.logicalClock);
                    localState.putAllAccountBalances(snapshot.accountBalances);
                    localState.putAllKvState(snapshot.kvState);
                    response.setLocalState(localState.build());

                    for (ChannelState cs : snapshot.channelStates.values()) {
                        ChandyLamport.ChannelState.Builder csBuilder = ChandyLamport.ChannelState.newBuilder();
                        csBuilder.setFromProcess(cs.fromProcess);
                        csBuilder.setToProcess(cs.toProcess);
                        csBuilder.addAllMessages(cs.messages);
                        response.addChannelStates(csBuilder.build());
                    }
                } else {
                    response.setFound(false);
                }

                return response.build();
            } finally {
                lock.readLock().unlock();
            }
        }

        public ChandyLamport.GetGlobalSnapshotResponse getGlobalSnapshot(ChandyLamport.GetGlobalSnapshotRequest request) {
            lock.readLock().lock();
            try {
                String snapshotId = request.getSnapshotId();
                ChandyLamport.GetGlobalSnapshotResponse.Builder response = ChandyLamport.GetGlobalSnapshotResponse.newBuilder();

                if (!snapshots.containsKey(snapshotId)) {
                    response.setSuccess(false);
                    response.setError("Snapshot not found");
                    return response.build();
                }

                // TODO: Collect snapshots from all peers and combine
                response.setSuccess(false);
                response.setError("Not implemented");

                return response.build();
            } finally {
                lock.readLock().unlock();
            }
        }

        // =========================================================================
        // Bank Service
        // =========================================================================

        public ChandyLamport.GetBalanceResponse getBalance(ChandyLamport.GetBalanceRequest request) {
            lock.readLock().lock();
            try {
                Long balance = accountBalances.get(request.getAccountId());
                return ChandyLamport.GetBalanceResponse.newBuilder()
                        .setFound(balance != null)
                        .setBalance(balance != null ? balance : 0)
                        .build();
            } finally {
                lock.readLock().unlock();
            }
        }

        public ChandyLamport.TransferResponse transfer(ChandyLamport.TransferRequest request) {
            lock.writeLock().lock();
            try {
                String fromAccount = request.getFromAccount();
                String toAccount = request.getToAccount();
                long amount = request.getAmount();

                if (!accountBalances.containsKey(fromAccount)) {
                    return ChandyLamport.TransferResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Source account not found")
                            .build();
                }

                if (accountBalances.get(fromAccount) < amount) {
                    return ChandyLamport.TransferResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Insufficient funds")
                            .build();
                }

                // TODO: For cross-process transfers, send message to destination
                accountBalances.put(fromAccount, accountBalances.get(fromAccount) - amount);
                accountBalances.merge(toAccount, amount, Long::sum);

                return ChandyLamport.TransferResponse.newBuilder()
                        .setSuccess(true)
                        .setFromBalance(accountBalances.get(fromAccount))
                        .setToBalance(accountBalances.getOrDefault(toAccount, 0L))
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public ChandyLamport.DepositResponse deposit(ChandyLamport.DepositRequest request) {
            lock.writeLock().lock();
            try {
                String accountId = request.getAccountId();
                accountBalances.merge(accountId, request.getAmount(), Long::sum);
                return ChandyLamport.DepositResponse.newBuilder()
                        .setSuccess(true)
                        .setNewBalance(accountBalances.get(accountId))
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        // =========================================================================
        // KeyValue Service
        // =========================================================================

        public ChandyLamport.GetResponse get(ChandyLamport.GetRequest request) {
            lock.readLock().lock();
            try {
                String value = kvStore.get(request.getKey());
                return ChandyLamport.GetResponse.newBuilder()
                        .setFound(value != null)
                        .setValue(value != null ? value : "")
                        .build();
            } finally {
                lock.readLock().unlock();
            }
        }

        public ChandyLamport.PutResponse put(ChandyLamport.PutRequest request) {
            lock.writeLock().lock();
            try {
                kvStore.put(request.getKey(), request.getValue());
                return ChandyLamport.PutResponse.newBuilder()
                        .setSuccess(true)
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public ChandyLamport.DeleteResponse delete(ChandyLamport.DeleteRequest request) {
            lock.writeLock().lock();
            try {
                kvStore.remove(request.getKey());
                return ChandyLamport.DeleteResponse.newBuilder()
                        .setSuccess(true)
                        .build();
            } finally {
                lock.writeLock().unlock();
            }
        }

        public ChandyLamport.GetLeaderResponse getLeader(ChandyLamport.GetLeaderRequest request) {
            return ChandyLamport.GetLeaderResponse.newBuilder()
                    .setInitiatorId(nodeId)
                    .setIsInitiator(true)
                    .build();
        }

        public ChandyLamport.GetClusterStatusResponse getClusterStatus(ChandyLamport.GetClusterStatusRequest request) {
            lock.readLock().lock();
            try {
                ChandyLamport.GetClusterStatusResponse.Builder response = ChandyLamport.GetClusterStatusResponse.newBuilder();
                response.setNodeId(nodeId);
                response.setLogicalClock(logicalClock);
                response.setIsRecording(currentSnapshotId != null);
                response.setCurrentSnapshotId(currentSnapshotId != null ? currentSnapshotId : "");
                response.setSnapshotsInitiated(snapshotsInitiated);
                response.setSnapshotsParticipated(snapshotsParticipated);

                for (String peer : peers) {
                    ChandyLamport.ClusterMember.Builder member = ChandyLamport.ClusterMember.newBuilder();
                    member.setAddress(peer);
                    member.setIsHealthy(true);
                    response.addMembers(member.build());
                }

                return response.build();
            } finally {
                lock.readLock().unlock();
            }
        }
    }

    // =========================================================================
    // gRPC Service Implementations
    // =========================================================================

    public static class SnapshotServicer extends SnapshotServiceGrpc.SnapshotServiceImplBase {
        private final ChandyLamportNode node;

        public SnapshotServicer(ChandyLamportNode node) {
            this.node = node;
        }

        @Override
        public void initiateSnapshot(ChandyLamport.InitiateSnapshotRequest request,
                                     StreamObserver<ChandyLamport.InitiateSnapshotResponse> responseObserver) {
            responseObserver.onNext(node.initiateSnapshot(request));
            responseObserver.onCompleted();
        }

        @Override
        public void receiveMarker(ChandyLamport.MarkerMessage request,
                                  StreamObserver<ChandyLamport.MarkerResponse> responseObserver) {
            responseObserver.onNext(node.receiveMarker(request));
            responseObserver.onCompleted();
        }

        @Override
        public void sendMessage(ChandyLamport.ApplicationMessage request,
                                StreamObserver<ChandyLamport.SendMessageResponse> responseObserver) {
            responseObserver.onNext(node.sendMessage(request));
            responseObserver.onCompleted();
        }

        @Override
        public void getSnapshot(ChandyLamport.GetSnapshotRequest request,
                                StreamObserver<ChandyLamport.GetSnapshotResponse> responseObserver) {
            responseObserver.onNext(node.getSnapshot(request));
            responseObserver.onCompleted();
        }

        @Override
        public void getGlobalSnapshot(ChandyLamport.GetGlobalSnapshotRequest request,
                                      StreamObserver<ChandyLamport.GetGlobalSnapshotResponse> responseObserver) {
            responseObserver.onNext(node.getGlobalSnapshot(request));
            responseObserver.onCompleted();
        }
    }

    public static class BankServicer extends BankServiceGrpc.BankServiceImplBase {
        private final ChandyLamportNode node;

        public BankServicer(ChandyLamportNode node) {
            this.node = node;
        }

        @Override
        public void getBalance(ChandyLamport.GetBalanceRequest request,
                               StreamObserver<ChandyLamport.GetBalanceResponse> responseObserver) {
            responseObserver.onNext(node.getBalance(request));
            responseObserver.onCompleted();
        }

        @Override
        public void transfer(ChandyLamport.TransferRequest request,
                             StreamObserver<ChandyLamport.TransferResponse> responseObserver) {
            responseObserver.onNext(node.transfer(request));
            responseObserver.onCompleted();
        }

        @Override
        public void deposit(ChandyLamport.DepositRequest request,
                            StreamObserver<ChandyLamport.DepositResponse> responseObserver) {
            responseObserver.onNext(node.deposit(request));
            responseObserver.onCompleted();
        }

        @Override
        public void withdraw(ChandyLamport.WithdrawRequest request,
                             StreamObserver<ChandyLamport.WithdrawResponse> responseObserver) {
            responseObserver.onNext(ChandyLamport.WithdrawResponse.newBuilder()
                    .setSuccess(false)
                    .setError("Not implemented")
                    .build());
            responseObserver.onCompleted();
        }
    }

    public static class KeyValueServicer extends KeyValueServiceGrpc.KeyValueServiceImplBase {
        private final ChandyLamportNode node;

        public KeyValueServicer(ChandyLamportNode node) {
            this.node = node;
        }

        @Override
        public void get(ChandyLamport.GetRequest request,
                        StreamObserver<ChandyLamport.GetResponse> responseObserver) {
            responseObserver.onNext(node.get(request));
            responseObserver.onCompleted();
        }

        @Override
        public void put(ChandyLamport.PutRequest request,
                        StreamObserver<ChandyLamport.PutResponse> responseObserver) {
            responseObserver.onNext(node.put(request));
            responseObserver.onCompleted();
        }

        @Override
        public void delete(ChandyLamport.DeleteRequest request,
                           StreamObserver<ChandyLamport.DeleteResponse> responseObserver) {
            responseObserver.onNext(node.delete(request));
            responseObserver.onCompleted();
        }

        @Override
        public void getLeader(ChandyLamport.GetLeaderRequest request,
                              StreamObserver<ChandyLamport.GetLeaderResponse> responseObserver) {
            responseObserver.onNext(node.getLeader(request));
            responseObserver.onCompleted();
        }

        @Override
        public void getClusterStatus(ChandyLamport.GetClusterStatusRequest request,
                                     StreamObserver<ChandyLamport.GetClusterStatusResponse> responseObserver) {
            responseObserver.onNext(node.getClusterStatus(request));
            responseObserver.onCompleted();
        }
    }

    // =========================================================================
    // Main Entry Point
    // =========================================================================

    public static void main(String[] args) throws IOException, InterruptedException {
        String nodeId = null;
        int port = 50051;
        String peersStr = null;

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

        if (nodeId == null || peersStr == null) {
            System.err.println("Usage: java ChandyLamportServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = new ArrayList<>();
        for (String peer : peersStr.split(",")) {
            peers.add(peer.trim());
        }

        ChandyLamportNode node = new ChandyLamportNode(nodeId, port, peers);
        node.initialize();

        Server server = ServerBuilder.forPort(port)
                .addService(new SnapshotServicer(node))
                .addService(new BankServicer(node))
                .addService(new KeyValueServicer(node))
                .build()
                .start();

        logger.info("Starting Chandy-Lamport node " + nodeId + " on port " + port);

        server.awaitTermination();
    }
}
