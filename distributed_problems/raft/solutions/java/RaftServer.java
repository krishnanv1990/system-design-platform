/**
 * Raft Consensus Implementation - Java Solution
 *
 * A complete implementation of the Raft consensus algorithm supporting:
 * - Leader election with randomized timeouts
 * - Log replication with consistency guarantees
 * - Heartbeat mechanism for leader authority
 * - Key-value store as the state machine
 *
 * Usage:
 *     java RaftServer --node-id node1 --port 50051 --peers node2:50052,node3:50053
 */

package com.sdp.raft;

import io.grpc.*;
import io.grpc.stub.StreamObserver;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.Condition;
import java.util.logging.Logger;

public class RaftServer {
    private static final Logger logger = Logger.getLogger(RaftServer.class.getName());

    enum NodeState {
        FOLLOWER("follower"),
        CANDIDATE("candidate"),
        LEADER("leader");

        private final String value;
        NodeState(String value) { this.value = value; }
        public String getValue() { return value; }
    }

    static class LogEntry {
        long index;
        long term;
        byte[] command;
        String commandType;

        LogEntry(long index, long term, byte[] command, String commandType) {
            this.index = index;
            this.term = term;
            this.command = command;
            this.commandType = commandType;
        }
    }

    static class RaftState {
        long currentTerm = 0;
        String votedFor = null;
        List<LogEntry> log = new ArrayList<>();
        long commitIndex = 0;
        long lastApplied = 0;
        Map<String, Long> nextIndex = new ConcurrentHashMap<>();
        Map<String, Long> matchIndex = new ConcurrentHashMap<>();

        RaftState() {
            // Dummy entry at index 0
            log.add(new LogEntry(0, 0, new byte[0], ""));
        }
    }

    private final String nodeId;
    private final int port;
    private final List<String> peers;
    private final RaftState state = new RaftState();
    private volatile NodeState nodeState = NodeState.FOLLOWER;
    private volatile String leaderId = "";

    private final Map<String, String> kvStore = new ConcurrentHashMap<>();

    private final int electionTimeoutMin = 150;
    private final int electionTimeoutMax = 300;
    private final int heartbeatInterval = 50;

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition applyCondition = lock.newCondition();
    private volatile long electionDeadline;
    private volatile boolean running = true;

    private final Map<String, ManagedChannel> channels = new ConcurrentHashMap<>();
    private final Map<String, RaftServiceGrpc.RaftServiceBlockingStub> peerStubs = new ConcurrentHashMap<>();
    private final Random random = new Random();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(4);

    public RaftServer(String nodeId, int port, List<String> peers) {
        this.nodeId = nodeId;
        this.port = port;
        this.peers = peers;
    }

    public void initialize() {
        for (String peer : peers) {
            ManagedChannel channel = ManagedChannelBuilder.forTarget(peer)
                    .usePlaintext()
                    .build();
            channels.put(peer, channel);
            peerStubs.put(peer, RaftServiceGrpc.newBlockingStub(channel));
        }
        logger.info("Node " + nodeId + " initialized with peers: " + peers);
    }

    private long getLastLogIndex() {
        return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).index;
    }

    private long getLastLogTerm() {
        return state.log.isEmpty() ? 0 : state.log.get(state.log.size() - 1).term;
    }

    private int randomTimeout() {
        return electionTimeoutMin + random.nextInt(electionTimeoutMax - electionTimeoutMin);
    }

    private void resetElectionTimer() {
        electionDeadline = System.currentTimeMillis() + randomTimeout();
    }

    private void stepDown(long newTerm) {
        state.currentTerm = newTerm;
        state.votedFor = null;
        nodeState = NodeState.FOLLOWER;
        resetElectionTimer();
    }

    private void electionTimerLoop() {
        resetElectionTimer();
        while (running) {
            try {
                Thread.sleep(10);
                lock.lock();
                try {
                    if (nodeState != NodeState.LEADER && System.currentTimeMillis() >= electionDeadline) {
                        startElection();
                    }
                } finally {
                    lock.unlock();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    private void startElection() {
        nodeState = NodeState.CANDIDATE;
        state.currentTerm++;
        state.votedFor = nodeId;
        resetElectionTimer();

        long term = state.currentTerm;
        long lastIdx = getLastLogIndex();
        long lastTerm = getLastLogTerm();

        logger.info("Node " + nodeId + " starting election for term " + term);

        AtomicInteger votesReceived = new AtomicInteger(1);
        int majority = (peers.size() + 1) / 2 + 1;

        for (String peer : peers) {
            scheduler.submit(() -> {
                try {
                    RaftServiceGrpc.RaftServiceBlockingStub stub = peerStubs.get(peer)
                            .withDeadlineAfter(100, TimeUnit.MILLISECONDS);

                    RequestVoteResponse response = stub.requestVote(RequestVoteRequest.newBuilder()
                            .setTerm(term)
                            .setCandidateId(nodeId)
                            .setLastLogIndex(lastIdx)
                            .setLastLogTerm(lastTerm)
                            .build());

                    lock.lock();
                    try {
                        if (response.getTerm() > state.currentTerm) {
                            stepDown(response.getTerm());
                        } else if (nodeState == NodeState.CANDIDATE &&
                                response.getVoteGranted() &&
                                term == state.currentTerm) {
                            if (votesReceived.incrementAndGet() >= majority) {
                                becomeLeader();
                            }
                        }
                    } finally {
                        lock.unlock();
                    }
                } catch (Exception e) {
                    // Peer unavailable
                }
            });
        }
    }

    private void becomeLeader() {
        if (nodeState != NodeState.CANDIDATE) return;
        nodeState = NodeState.LEADER;
        leaderId = nodeId;
        logger.info("Node " + nodeId + " became leader for term " + state.currentTerm);

        for (String peer : peers) {
            state.nextIndex.put(peer, getLastLogIndex() + 1);
            state.matchIndex.put(peer, 0L);
        }
    }

    private void heartbeatLoop() {
        while (running) {
            try {
                Thread.sleep(heartbeatInterval);
                lock.lock();
                try {
                    if (nodeState == NodeState.LEADER) {
                        sendAppendEntriesToAll();
                    }
                } finally {
                    lock.unlock();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }

    private void sendAppendEntriesToAll() {
        for (String peer : peers) {
            long nextIdx = state.nextIndex.getOrDefault(peer, 1L);
            long prevIdx = nextIdx - 1;
            long prevTerm = prevIdx < state.log.size() ? state.log.get((int) prevIdx).term : 0;

            AppendEntriesRequest.Builder reqBuilder = AppendEntriesRequest.newBuilder()
                    .setTerm(state.currentTerm)
                    .setLeaderId(nodeId)
                    .setPrevLogIndex(prevIdx)
                    .setPrevLogTerm(prevTerm)
                    .setLeaderCommit(state.commitIndex);

            for (int i = (int) nextIdx; i < state.log.size(); i++) {
                LogEntry entry = state.log.get(i);
                reqBuilder.addEntries(com.sdp.raft.LogEntry.newBuilder()
                        .setIndex(entry.index)
                        .setTerm(entry.term)
                        .setCommand(com.google.protobuf.ByteString.copyFrom(entry.command))
                        .setCommandType(entry.commandType)
                        .build());
            }

            AppendEntriesRequest req = reqBuilder.build();
            long term = state.currentTerm;
            int entriesCount = req.getEntriesCount();

            scheduler.submit(() -> {
                try {
                    RaftServiceGrpc.RaftServiceBlockingStub stub = peerStubs.get(peer)
                            .withDeadlineAfter(100, TimeUnit.MILLISECONDS);

                    AppendEntriesResponse response = stub.appendEntries(req);

                    lock.lock();
                    try {
                        if (response.getTerm() > state.currentTerm) {
                            stepDown(response.getTerm());
                        } else if (nodeState == NodeState.LEADER && term == state.currentTerm) {
                            if (response.getSuccess()) {
                                state.nextIndex.put(peer, prevIdx + entriesCount + 1);
                                state.matchIndex.put(peer, state.nextIndex.get(peer) - 1);
                                updateCommitIndex();
                            } else {
                                state.nextIndex.put(peer, Math.max(1, state.nextIndex.get(peer) - 1));
                            }
                        }
                    } finally {
                        lock.unlock();
                    }
                } catch (Exception e) {
                    // Peer unavailable
                }
            });
        }
    }

    private void updateCommitIndex() {
        for (long n = state.commitIndex + 1; n < state.log.size(); n++) {
            if (state.log.get((int) n).term != state.currentTerm) continue;
            int count = 1;
            for (String peer : peers) {
                if (state.matchIndex.getOrDefault(peer, 0L) >= n) count++;
            }
            if (count >= (peers.size() + 1) / 2 + 1) {
                state.commitIndex = n;
                applyToStateMachine();
            }
        }
    }

    private void applyToStateMachine() {
        while (state.lastApplied < state.commitIndex) {
            state.lastApplied++;
            LogEntry entry = state.log.get((int) state.lastApplied);
            String cmd = new String(entry.command);

            if ("put".equals(entry.commandType)) {
                int sep = cmd.indexOf(':');
                if (sep != -1) {
                    String key = cmd.substring(0, sep);
                    String value = cmd.substring(sep + 1);
                    kvStore.put(key, value);
                }
            } else if ("delete".equals(entry.commandType)) {
                kvStore.remove(cmd);
            }
        }
        applyCondition.signalAll();
    }

    // RaftService implementation
    class RaftServiceImpl extends RaftServiceGrpc.RaftServiceImplBase {
        @Override
        public void requestVote(RequestVoteRequest request, StreamObserver<RequestVoteResponse> responseObserver) {
            lock.lock();
            try {
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }

                boolean logOk = request.getLastLogTerm() > getLastLogTerm() ||
                        (request.getLastLogTerm() == getLastLogTerm() &&
                                request.getLastLogIndex() >= getLastLogIndex());

                boolean voteGranted = false;
                if (request.getTerm() == state.currentTerm && logOk &&
                        (state.votedFor == null || state.votedFor.equals(request.getCandidateId()))) {
                    state.votedFor = request.getCandidateId();
                    voteGranted = true;
                    resetElectionTimer();
                }

                responseObserver.onNext(RequestVoteResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .setVoteGranted(voteGranted)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        @Override
        public void appendEntries(AppendEntriesRequest request, StreamObserver<AppendEntriesResponse> responseObserver) {
            lock.lock();
            try {
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }

                if (request.getTerm() < state.currentTerm) {
                    responseObserver.onNext(AppendEntriesResponse.newBuilder()
                            .setTerm(state.currentTerm)
                            .setSuccess(false)
                            .setMatchIndex(getLastLogIndex())
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                leaderId = request.getLeaderId();
                nodeState = NodeState.FOLLOWER;
                resetElectionTimer();

                if (request.getPrevLogIndex() >= state.log.size() ||
                        state.log.get((int) request.getPrevLogIndex()).term != request.getPrevLogTerm()) {
                    responseObserver.onNext(AppendEntriesResponse.newBuilder()
                            .setTerm(state.currentTerm)
                            .setSuccess(false)
                            .setMatchIndex(getLastLogIndex())
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                int logPtr = (int) request.getPrevLogIndex() + 1;
                for (com.sdp.raft.LogEntry entry : request.getEntriesList()) {
                    if (logPtr < state.log.size()) {
                        if (state.log.get(logPtr).term != entry.getTerm()) {
                            state.log.subList(logPtr, state.log.size()).clear();
                        }
                    }
                    if (logPtr >= state.log.size()) {
                        state.log.add(new LogEntry(
                                entry.getIndex(),
                                entry.getTerm(),
                                entry.getCommand().toByteArray(),
                                entry.getCommandType()
                        ));
                    }
                    logPtr++;
                }

                if (request.getLeaderCommit() > state.commitIndex) {
                    state.commitIndex = Math.min(request.getLeaderCommit(), getLastLogIndex());
                    applyToStateMachine();
                }

                responseObserver.onNext(AppendEntriesResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .setSuccess(true)
                        .setMatchIndex(getLastLogIndex())
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        @Override
        public void installSnapshot(InstallSnapshotRequest request, StreamObserver<InstallSnapshotResponse> responseObserver) {
            lock.lock();
            try {
                if (request.getTerm() > state.currentTerm) {
                    stepDown(request.getTerm());
                }
                responseObserver.onNext(InstallSnapshotResponse.newBuilder()
                        .setTerm(state.currentTerm)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }
    }

    // KeyValueService implementation
    class KeyValueServiceImpl extends KeyValueServiceGrpc.KeyValueServiceImplBase {
        @Override
        public void get(GetRequest request, StreamObserver<GetResponse> responseObserver) {
            String value = kvStore.get(request.getKey());
            responseObserver.onNext(GetResponse.newBuilder()
                    .setValue(value != null ? value : "")
                    .setFound(value != null)
                    .build());
            responseObserver.onCompleted();
        }

        @Override
        public void put(PutRequest request, StreamObserver<PutResponse> responseObserver) {
            lock.lock();
            try {
                if (nodeState != NodeState.LEADER) {
                    responseObserver.onNext(PutResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Not the leader")
                            .setLeaderHint(leaderId)
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                LogEntry entry = new LogEntry(
                        getLastLogIndex() + 1,
                        state.currentTerm,
                        (request.getKey() + ":" + request.getValue()).getBytes(),
                        "put"
                );
                state.log.add(entry);
                long waitIdx = entry.index;

                while (state.lastApplied < waitIdx && nodeState == NodeState.LEADER) {
                    try {
                        applyCondition.await(100, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }

                boolean success = state.lastApplied >= waitIdx;
                responseObserver.onNext(PutResponse.newBuilder()
                        .setSuccess(success)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        @Override
        public void delete(DeleteRequest request, StreamObserver<DeleteResponse> responseObserver) {
            lock.lock();
            try {
                if (nodeState != NodeState.LEADER) {
                    responseObserver.onNext(DeleteResponse.newBuilder()
                            .setSuccess(false)
                            .setError("Not the leader")
                            .setLeaderHint(leaderId)
                            .build());
                    responseObserver.onCompleted();
                    return;
                }

                LogEntry entry = new LogEntry(
                        getLastLogIndex() + 1,
                        state.currentTerm,
                        request.getKey().getBytes(),
                        "delete"
                );
                state.log.add(entry);
                long waitIdx = entry.index;

                while (state.lastApplied < waitIdx && nodeState == NodeState.LEADER) {
                    try {
                        applyCondition.await(100, TimeUnit.MILLISECONDS);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }

                boolean success = state.lastApplied >= waitIdx;
                responseObserver.onNext(DeleteResponse.newBuilder()
                        .setSuccess(success)
                        .build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        @Override
        public void getLeader(GetLeaderRequest request, StreamObserver<GetLeaderResponse> responseObserver) {
            lock.lock();
            try {
                GetLeaderResponse.Builder builder = GetLeaderResponse.newBuilder()
                        .setLeaderId(leaderId)
                        .setIsLeader(nodeState == NodeState.LEADER);

                for (String peer : peers) {
                    if (peer.contains(leaderId)) {
                        builder.setLeaderAddress(peer);
                        break;
                    }
                }

                if (nodeState == NodeState.LEADER) {
                    builder.setLeaderAddress("localhost:" + port);
                }

                responseObserver.onNext(builder.build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }

        @Override
        public void getClusterStatus(GetClusterStatusRequest request, StreamObserver<GetClusterStatusResponse> responseObserver) {
            lock.lock();
            try {
                GetClusterStatusResponse.Builder builder = GetClusterStatusResponse.newBuilder()
                        .setNodeId(nodeId)
                        .setState(nodeState.getValue())
                        .setCurrentTerm(state.currentTerm)
                        .setVotedFor(state.votedFor != null ? state.votedFor : "")
                        .setCommitIndex(state.commitIndex)
                        .setLastApplied(state.lastApplied)
                        .setLogLength(state.log.size())
                        .setLastLogTerm(getLastLogTerm());

                for (String peer : peers) {
                    ClusterMember.Builder memberBuilder = ClusterMember.newBuilder().setAddress(peer);
                    if (nodeState == NodeState.LEADER) {
                        memberBuilder.setMatchIndex(state.matchIndex.getOrDefault(peer, 0L));
                        memberBuilder.setNextIndex(state.nextIndex.getOrDefault(peer, 1L));
                    }
                    builder.addMembers(memberBuilder.build());
                }

                responseObserver.onNext(builder.build());
                responseObserver.onCompleted();
            } finally {
                lock.unlock();
            }
        }
    }

    public void start() throws IOException {
        Server server = ServerBuilder.forPort(port)
                .addService(new RaftServiceImpl())
                .addService(new KeyValueServiceImpl())
                .build()
                .start();

        scheduler.submit(this::electionTimerLoop);
        scheduler.submit(this::heartbeatLoop);

        logger.info("Starting Raft node " + nodeId + " on port " + port);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            running = false;
            scheduler.shutdown();
            server.shutdown();
        }));

        try {
            server.awaitTermination();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public static void main(String[] args) {
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
            System.err.println("Usage: java RaftServer --node-id <id> --port <port> --peers <peer1:port1,peer2:port2>");
            System.exit(1);
        }

        List<String> peers = Arrays.asList(peersStr.split(","));
        peers.replaceAll(String::trim);

        RaftServer server = new RaftServer(nodeId, port, peers);
        server.initialize();

        try {
            server.start();
        } catch (IOException e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
